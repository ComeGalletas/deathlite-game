"""Loads static game data from data/*.json into plain dicts.

Spec section 7: content lives in data files, code provides behavior. This module
is the single load point. Missing files or malformed JSON raise a clear
`ContentError` at startup rather than failing mysteriously deep in gameplay.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from progression.blessings.catalog import RARITIES as BLESSING_RARITIES
from spawn.tables import SpawnTables, TableError

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class ContentError(RuntimeError):
    pass


def _load(name: str) -> dict[str, Any]:
    path = DATA_DIR / name
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise ContentError(f"missing data file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContentError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContentError(f"{path} must contain a JSON object at top level")
    return data


def _merge_sprites(*names: str) -> dict[str, Any]:
    """Load several sprite-rig files into one flat namespace. A rig may appear
    in more than one file (a shared rig, copied on purpose) as long as the
    copies are identical."""
    merged: dict[str, Any] = {}
    for name in names:
        for rig, spec in _load(name).items():
            if rig in merged and merged[rig] != spec:
                raise ContentError(
                    f"sprite rig {rig!r} differs between files (last: {name})")
            merged[rig] = spec
    return merged


def _check_potions(data: dict[str, Any]) -> dict[str, Any]:
    """Validate `potions.json` (CB-8) against its own `rarities` order.

    Strict on purpose, like the blessing catalog: a table missing a rarity, a
    negative heal or an enemy-rarity row that does not sum to something
    rollable is bad data and should stop the boot.
    """
    rarities = data.get("rarities")
    if not isinstance(rarities, list) or not rarities:
        raise ContentError("potions.json: `rarities` must be a non-empty list")
    order = list(rarities)

    def rows(key: str) -> dict:
        table = data.get(key)
        if not isinstance(table, dict):
            raise ContentError(f"potions.json: `{key}` must be an object")
        got = {k for k in table if not k.startswith("_")}
        if got != set(order):
            raise ContentError(
                f"potions.json: `{key}` covers {sorted(got)}, expected {order}")
        return table

    for rarity, spec in rows("potions").items():
        if rarity.startswith("_"):
            continue
        for field in ("sprite", "heal"):
            if field not in spec:
                raise ContentError(f"potions.json: {rarity} potion has no {field!r}")
        if float(spec["heal"]) <= 0.0:
            raise ContentError(f"potions.json: {rarity} potion heals {spec['heal']}")

    for enemy_rarity, weights in rows("rarity_weights").items():
        if enemy_rarity.startswith("_"):
            continue
        missing = set(order) - {k for k in weights if not k.startswith("_")}
        if missing:
            raise ContentError(
                f"potions.json: rarity_weights[{enemy_rarity}] misses {sorted(missing)}")
        if any(float(w) < 0.0 for k, w in weights.items() if not k.startswith("_")):
            raise ContentError(
                f"potions.json: rarity_weights[{enemy_rarity}] has a negative weight")
        if sum(float(w) for k, w in weights.items() if not k.startswith("_")) <= 0.0:
            raise ContentError(
                f"potions.json: rarity_weights[{enemy_rarity}] sums to zero")

    curve = data.get("drop_chance")
    if not isinstance(curve, dict):
        raise ContentError("potions.json: `drop_chance` must be an object")
    for field in ("floor", "cap", "exponent", "hp_min", "hp_max"):
        if field not in curve:
            raise ContentError(f"potions.json: drop_chance has no {field!r}")
    if not 0.0 <= float(curve["floor"]) <= float(curve["cap"]) <= 1.0:
        raise ContentError("potions.json: drop_chance needs 0 <= floor <= cap <= 1")
    if float(curve["hp_min"]) <= 0.0 or float(curve["hp_max"]) <= float(curve["hp_min"]):
        raise ContentError("potions.json: drop_chance needs 0 < hp_min < hp_max")

    bands = data.get("enemy_rarity_hp")
    if not isinstance(bands, dict):
        raise ContentError("potions.json: `enemy_rarity_hp` must be an object")
    for rarity in order[1:]:
        if rarity not in bands:
            raise ContentError(f"potions.json: enemy_rarity_hp has no {rarity!r} bound")
    bounds = [float(bands[r]) for r in order[1:]]
    if bounds != sorted(bounds) or len(set(bounds)) != len(bounds):
        raise ContentError("potions.json: enemy_rarity_hp bounds must strictly ascend")
    return data


def _check_chests(data: dict[str, Any], potions: dict[str, Any]) -> dict[str, Any]:
    """Validate `chests.json` (CB-9) against its own `rarities` order, and its
    potion references against the CB-8 table it draws from.

    Strict like the potion check: a tier missing from the table, a gold range
    that runs backwards, or a potion rarity that does not exist is bad data and
    should stop the boot rather than surface as an empty chest an hour in.
    """
    rarities = data.get("rarities")
    if not isinstance(rarities, list) or not rarities:
        raise ContentError("chests.json: `rarities` must be a non-empty list")
    order = list(rarities)

    table = data.get("chests")
    if not isinstance(table, dict):
        raise ContentError("chests.json: `chests` must be an object")
    got = {k for k in table if not k.startswith("_")}
    if got != set(order):
        raise ContentError(
            f"chests.json: `chests` covers {sorted(got)}, expected {order}")

    potion_rarities = set(potions.get("rarities", ()))
    blessing_rarities = set(BLESSING_RARITIES)
    for rarity in order:
        spec = table[rarity]
        for field in ("sprite", "gold", "potion"):
            if field not in spec:
                raise ContentError(f"chests.json: {rarity} chest has no {field!r}")
        lo, hi = (float(v) for v in spec["gold"])
        if lo < 0.0 or hi < lo:
            raise ContentError(
                f"chests.json: {rarity} chest gold range {spec['gold']} is not ascending")
        if spec["potion"] not in potion_rarities:
            raise ContentError(
                f"chests.json: {rarity} chest drops a {spec['potion']!r} potion, "
                f"which potions.json does not define")
        blessing = spec.get("blessing")
        if blessing is None:
            continue
        if not 0.0 <= float(blessing.get("chance", 0.0)) <= 1.0:
            raise ContentError(f"chests.json: {rarity} chest blessing chance is not 0..1")
        weights = blessing.get("weights")
        if not isinstance(weights, dict) or not weights:
            raise ContentError(f"chests.json: {rarity} chest blessing has no weights")
        unknown = {k for k in weights if not k.startswith("_")} - blessing_rarities
        if unknown:
            raise ContentError(
                f"chests.json: {rarity} chest offers blessing rarities "
                f"{sorted(unknown)}, which the catalog does not use")
        if sum(float(w) for k, w in weights.items() if not k.startswith("_")) <= 0.0:
            raise ContentError(f"chests.json: {rarity} chest blessing weights sum to zero")
    return data


class Content:
    """Immutable-ish container for all loaded definitions."""

    def __init__(self) -> None:
        self.weapons: dict[str, dict] = _load("weapons.json")
        self.weapon_visuals: dict[str, dict] = _load("weapon_visuals.json")
        self.enemies: dict[str, dict] = _load("enemies.json")
        self.bosses: dict[str, dict] = _load("bosses.json")
        self.characters: dict[str, dict] = _load("characters.json")
        self.blessings: dict[str, dict] = _load("blessings.json")
        self.offering: dict = _load("offering.json")        # P2 weights
        self.forges: dict[str, dict] = _load("forges.json")   # P3 Forgings
        self.items: dict = _load("items.json")
        self.meta_upgrades: dict[str, dict] = _load("meta_upgrades.json")
        # CB-8: health potion drops. Validated here so a table that does not
        # cover every rarity fails at boot, not on the first kill.
        self.potions: dict = _check_potions(_load("potions.json"))
        # CB-9: what a treasure chest contains. Checked against the potion
        # table it draws from, so a tier naming a potion rarity that does not
        # exist fails at boot rather than on the first chest opened.
        self.chests: dict = _check_chests(_load("chests.json"), self.potions)
        # Sprite rigs are split by domain; a rig shared by two domains (e.g.
        # `dead`, used by heroes and enemies) is copied into both files. They
        # merge back into one flat `sprites` namespace here.
        self.sprites: dict[str, dict] = _merge_sprites(
            "character_sprites.json", "enemy_sprites.json",
            "weapon_sprites.json", "prop_sprites.json")
        self.terrain: dict = _load("terrain.json")
        self.ui_sprites: dict[str, dict] = _load("ui_sprites.json")
        # Village NPC tuning (HI-3): speeds, idle bands, leashes, counts.
        self.npcs: dict = _load("npcs.json")
        # The spawn schedule (spawn master S2). Checked here, against the
        # enemies just loaded, so a phase that names an enemy that does not
        # exist fails at boot rather than at minute eight.
        try:
            self.spawn_tables = SpawnTables(_load("spawn_tables.json"),
                                            enemy_ids=self.enemies)
        except TableError as exc:
            raise ContentError(str(exc)) from exc
        log.info("content loaded: %d weapons, %d enemies, %d bosses, "
                 "%d characters, %d blessings, %d affixes, %d meta upgrades, "
                 "%d sprite rigs, %d terrain rigs, %d ui rigs, "
                 "%d spawn phases",
                 len(self.weapons), len(self.enemies), len(self.bosses),
                 len(self.characters), len(self.blessings),
                 len(self.items.get("affixes", {})), len(self.meta_upgrades),
                 len(self.sprites), len(self.terrain.get("rigs", {})),
                 len(self.ui_sprites), len(self.spawn_tables.phases()))

    def weapon(self, weapon_id: str) -> dict:
        try:
            return self.weapons[weapon_id]
        except KeyError as exc:
            raise ContentError(f"unknown weapon id: {weapon_id!r}") from exc

    def weapon_visual(self, weapon_id: str):
        """Presentation for a weapon (`combat.weapon_visuals.WeaponVisual`).
        A missing entry -> the neutral default (white, no style)."""
        from combat.weapon_visuals import WeaponVisual
        return WeaponVisual.from_dict(self.weapon_visuals.get(weapon_id))

    def enemy(self, enemy_id: str) -> dict:
        try:
            return self.enemies[enemy_id]
        except KeyError as exc:
            raise ContentError(f"unknown enemy id: {enemy_id!r}") from exc

    def boss(self, boss_id: str) -> dict:
        try:
            return self.bosses[boss_id]
        except KeyError as exc:
            raise ContentError(f"unknown boss id: {boss_id!r}") from exc

    def character(self, char_id: str) -> dict:
        try:
            return self.characters[char_id]
        except KeyError as exc:
            raise ContentError(f"unknown character id: {char_id!r}") from exc


_cache: Content | None = None


def get_content() -> Content:
    """Process-wide singleton; loaded on first use."""
    global _cache
    if _cache is None:
        _cache = Content()
    return _cache
