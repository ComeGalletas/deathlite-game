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


class Content:
    """Immutable-ish container for all loaded definitions."""

    def __init__(self) -> None:
        self.weapons: dict[str, dict] = _load("weapons.json")
        self.weapon_visuals: dict[str, dict] = _load("weapon_visuals.json")
        self.enemies: dict[str, dict] = _load("enemies.json")
        self.bosses: dict[str, dict] = _load("bosses.json")
        self.characters: dict[str, dict] = _load("characters.json")
        self.blessings: dict[str, dict] = _load("blessings.json")
        self.items: dict = _load("items.json")
        self.meta_upgrades: dict[str, dict] = _load("meta_upgrades.json")
        # Sprite rigs are split by domain; a rig shared by two domains (e.g.
        # `dead`, used by heroes and enemies) is copied into both files. They
        # merge back into one flat `sprites` namespace here.
        self.sprites: dict[str, dict] = _merge_sprites(
            "character_sprites.json", "enemy_sprites.json",
            "weapon_sprites.json", "prop_sprites.json")
        self.terrain: dict = _load("terrain.json")
        self.ui_sprites: dict[str, dict] = _load("ui_sprites.json")
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
