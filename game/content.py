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

from combat.elements import config as element_schema
from combat.elements.ids import ELEMENTS as ELEMENT_IDS
from combat.elements.ids import REACTIONS as REACTION_IDS
from combat.elements.schema import ElementDataError
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
    copies are identical.

    A top-level `_`-prefixed key is documentation, not a rig -- the same
    convention the tuning blocks use. `infused_sprites.json` is generated
    and leads with a `_doc` saying so, and everything that walks this
    namespace would otherwise have to know that."""
    merged: dict[str, Any] = {}
    for name in names:
        for rig, spec in _load(name).items():
            if rig.startswith("_"):
                continue
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


BUFF_FIELDS = ("name", "duration", "palette", "fx_rig", "icon_rig")


def _check_buildings(data: dict[str, Any]) -> dict[str, Any]:
    """Validate `buildings.json`: every buff names what the run, the HUD and
    the feedback read, and every building kind has an obstacle entry and a
    skin, so a half-declared kind fails at boot rather than as a bare
    circle on some island."""
    buffs = data.get("buffs")
    if not isinstance(buffs, dict) or not buffs:
        raise ContentError("buildings.json: `buffs` must be a non-empty object")
    obstacles = data.get("obstacles", {})
    skins = data.get("obstacle_decor", {}).get("rigs", {})
    rigs = data.get("rigs", {})
    for kind, spec in buffs.items():
        for field in BUFF_FIELDS:
            if field not in spec:
                raise ContentError(f"buildings.json: buff {kind!r} has no {field!r}")
        if float(spec["duration"]) <= 0.0:
            raise ContentError(f"buildings.json: buff {kind!r} lasts {spec['duration']}")
        if len(spec["palette"]) < 2:
            raise ContentError(f"buildings.json: buff {kind!r} needs two palette colours")
        if kind not in obstacles:
            raise ContentError(f"buildings.json: no `obstacles` entry for {kind!r}")
        if not skins.get(kind):
            raise ContentError(f"buildings.json: no skin rig listed for {kind!r}")
        images = data.get("image_rigs", {})
        for rig in (*skins[kind], spec["fx_rig"], spec["icon_rig"], *spec.get("dressing", ())):
            if rig not in rigs and rig not in images and not rig.startswith("deco_"):
                raise ContentError(f"buildings.json: buff {kind!r} names unknown rig {rig!r}")
    _check_building_elements(data)
    return data


def _check_building_elements(data: dict[str, Any]) -> None:
    """The optional `elements` block (M7): how often a buff building
    also hands out an element, and which. Absent means none ever do."""
    block = data.get("elements")
    if block is None:
        return
    if not isinstance(block, dict):
        raise ContentError("buildings.json: `elements` must be an object")
    chance = float(block.get("chance", 0.0))
    if not 0.0 <= chance <= 1.0:
        raise ContentError(f"buildings.json: elements.chance {chance} is not 0..1")
    weights = block.get("weights", {})
    if not isinstance(weights, dict):
        raise ContentError("buildings.json: elements.weights must be an object")
    known = {e.key for e in ELEMENT_IDS}
    unknown = {k for k in weights if not k.startswith("_")} - known
    if unknown:
        raise ContentError(
            f"buildings.json: elements.weights names {sorted(unknown)}, "
            f"which are not elements")
    if chance > 0.0 and sum(
            float(w) for k, w in weights.items() if not k.startswith("_")) <= 0.0:
        raise ContentError("buildings.json: elements.weights sum to zero")
    _check_building_glow(block.get("glow"))


def _check_building_glow(glow) -> None:
    """`elements.glow` (CMB-009.1): the disc under an elemental building.
    Required with the `elements` block -- the renderer reads it with no
    defaults of its own."""
    if not isinstance(glow, dict):
        raise ContentError("buildings.json: elements.glow must be an object")
    for field in ("scale", "alpha_min", "alpha_max", "period", "steps"):
        if field not in glow:
            raise ContentError(f"buildings.json: elements.glow has no {field!r}")
    lo, hi = int(glow["alpha_min"]), int(glow["alpha_max"])
    if not 0 <= lo <= hi <= 255:
        raise ContentError(
            "buildings.json: elements.glow needs 0 <= alpha_min <= alpha_max <= 255")
    if float(glow["scale"]) <= 0.0:
        raise ContentError("buildings.json: elements.glow.scale must be positive")
    if int(glow["steps"]) < 1:
        raise ContentError("buildings.json: elements.glow.steps must be at least 1")


def _check_elements(data: dict[str, Any]) -> dict[str, Any]:
    """Validate `elements.json` against `combat.elements.config`."""
    try:
        return element_schema.check_elements(data)
    except ElementDataError as exc:
        raise ContentError(str(exc)) from exc


def _check_reactions(data: dict[str, Any]) -> dict[str, Any]:
    """Validate `reactions.json` against `combat.elements.config`."""
    try:
        return element_schema.check_reactions(data)
    except ElementDataError as exc:
        raise ContentError(str(exc)) from exc


def _check_element_visuals(data: dict[str, Any]) -> dict[str, Any]:
    """Validate `element_visuals.json`: every element styled, every marker a
    shape the renderer knows, every reaction given a burst.

    That the named *rigs* exist is checked separately, by
    `_check_element_rigs` once the sprite files have merged -- they load
    after this one, and a rig name that resolves to nothing is exactly the
    kind of thing that should stop the boot rather than show up as an
    invisible aura."""
    from game.states.playing.visual.elements.markers import SHAPES

    elements = data.get("elements")
    if not isinstance(elements, dict):
        raise ContentError("element_visuals.json: `elements` must be an object")
    got = {k for k in elements if not k.startswith("_")}
    want = {e.key for e in ELEMENT_IDS}
    if got != want:
        raise ContentError(
            f"element_visuals.json: covers {sorted(got)}, expected {sorted(want)}")
    for key in sorted(want):
        spec = elements[key]
        for field in ("colour", "marker", "particles"):
            if field not in spec:
                raise ContentError(
                    f"element_visuals.json: {key} has no {field!r}")
        if len(spec["colour"]) != 3:
            raise ContentError(f"element_visuals.json: {key} colour is not RGB")
        if spec["marker"] not in SHAPES:
            raise ContentError(
                f"element_visuals.json: {key} marker {spec['marker']!r} is not a known shape")
        for field in ("rate", "speed", "life", "radius"):
            if float(spec["particles"][field]) <= 0.0:
                raise ContentError(
                    f"element_visuals.json: {key} particles.{field} must be > 0")
    for block, fields in (("aura", ("ring_pad", "ring_width", "alpha",
                                    "locked_alpha", "marker_size",
                                    "marker_gap", "rig_scale")),
                          ("wash", ("lift", "alpha")),
                          ("budget", ("per_frame", "per_element"))):
        if not isinstance(data.get(block), dict):
            raise ContentError(f"element_visuals.json: `{block}` must be an object")
        for field in fields:
            if field not in data[block]:
                raise ContentError(
                    f"element_visuals.json: {block} has no {field!r}")

    # M10: every reaction draws a burst over the whole scene, so every
    # reaction needs one. A missing entry would silently fall back to the
    # procedural flash for that pair alone, which is the sort of gap nobody
    # notices until they wonder why one reaction looks different.
    reactions = data.get("reactions")
    if not isinstance(reactions, dict):
        raise ContentError("element_visuals.json: `reactions` must be an object")
    got = {k for k in reactions if not k.startswith("_")}
    want = {r.key for r in REACTION_IDS}
    if got != want:
        raise ContentError(
            f"element_visuals.json: reactions covers {sorted(got)}, "
            f"expected {sorted(want)}")
    for key in sorted(want):
        spec = reactions[key]
        for field in ("rig", "seconds", "size"):
            if field not in spec:
                raise ContentError(
                    f"element_visuals.json: reaction {key} has no {field!r}")
        for field in ("seconds", "size"):
            if float(spec[field]) <= 0.0:
                raise ContentError(
                    f"element_visuals.json: reaction {key}.{field} must be > 0")
        _check_reaction_label(key, spec.get("label"))

    statuses = data.get("statuses")
    if not isinstance(statuses, dict):
        raise ContentError("element_visuals.json: `statuses` must be an object")
    return data


def _check_reaction_label(key: str, label: Any) -> None:
    """A reaction's optional label order names two *different* elements of
    that reaction's own pair.

    Checked rather than trusted: naming the wrong element would silently
    colour a word in a hue that has nothing to do with the reaction, and
    naming the same one twice would draw a ring the same colour as its
    fill, which reads as no ring at all."""
    if label is None:
        return
    from combat.elements.config import REACTION_PAIRS
    from combat.elements.ids import reaction_from_key

    if not isinstance(label, dict):
        raise ContentError(
            f"element_visuals.json: reaction {key}.label must be an object")
    missing = {"fill", "ring"} - set(label)
    if missing:
        raise ContentError(
            f"element_visuals.json: reaction {key}.label has no "
            f"{sorted(missing)} -- name both or neither")
    allowed = {e.key for e in REACTION_PAIRS[reaction_from_key(key)]}
    for field in ("fill", "ring"):
        if label[field] not in allowed:
            raise ContentError(
                f"element_visuals.json: reaction {key}.label.{field} is "
                f"{label[field]!r}, which is not one of {sorted(allowed)}")
    if label["fill"] == label["ring"]:
        raise ContentError(
            f"element_visuals.json: reaction {key}.label names "
            f"{label['fill']!r} twice -- the ring would vanish")


def _check_element_rigs(visuals: dict[str, Any], sprites: dict[str, dict]) -> None:
    """Every rig `element_visuals.json` names is a real one.

    Run after the sprite files merge, because that is when the rigs exist.
    An unresolvable name is a boot failure and not a warning: an aura is
    the only in-game sign of what an enemy will react to, and once the
    sprite is the whole indicator (M10 rule 1) a typo here would leave a
    primed enemy with nothing drawn on it at all."""
    named: list[tuple[str, str]] = []
    for key, spec in visuals["elements"].items():
        if key.startswith("_"):
            continue
        if spec.get("aura_rig"):
            named.append((f"{key}.aura_rig", spec["aura_rig"]))
    for status, rig in visuals["statuses"].items():
        if not status.startswith("_"):
            named.append((f"statuses.{status}", rig))
    for key, spec in visuals["reactions"].items():
        if not key.startswith("_"):
            named.append((f"reactions.{key}.rig", spec["rig"]))

    for where, rig in named:
        if not isinstance(rig, str):
            raise ContentError(
                f"element_visuals.json: {where} is not a rig name")
        if rig not in sprites:
            raise ContentError(
                f"element_visuals.json: {where} names rig {rig!r}, "
                "which no sprite file declares")
        if "loop" not in sprites[rig].get("anims", {}):
            raise ContentError(
                f"element_visuals.json: {where} rig {rig!r} has no `loop` "
                "animation (this project's name for a rig's only anim, "
                "whether or not it repeats)")


def _merge_buildings(terrain: dict[str, Any], ui_sprites: dict[str, Any],
                     buildings: dict[str, Any]) -> None:
    """Fold the buildings' obstacle kinds, skins and rigs into the terrain
    blocks, and its single-image rigs (the HUD stills, the pinball) into the
    UI rigs. A kind or rig already declared elsewhere is left alone."""
    for rig, meta in buildings.get("image_rigs", {}).items():
        ui_sprites.setdefault(rig, meta)
    for kind, spec in buildings.get("obstacles", {}).items():
        terrain.setdefault("obstacles", {}).setdefault(kind, spec)
    decor = terrain.setdefault("obstacle_decor", {})
    bdecor = buildings.get("obstacle_decor", {})
    for kind, names in bdecor.get("rigs", {}).items():
        decor.setdefault("rigs", {}).setdefault(kind, list(names))
    for kind, drop in bdecor.get("sprite_drop", {}).items():
        decor.setdefault("sprite_drop", {}).setdefault(kind, drop)
    for kind, scale in bdecor.get("render_scale", {}).items():
        decor.setdefault("render_scale", {}).setdefault(kind, scale)
    ghost = decor.setdefault("ghost", {}).setdefault("kinds", [])
    for kind in bdecor.get("ghost_kinds", ()):
        if kind not in ghost:
            ghost.append(kind)
    for rig, meta in buildings.get("rigs", {}).items():
        terrain.setdefault("rigs", {}).setdefault(rig, meta)


class Content:
    """Immutable-ish container for all loaded definitions."""

    def __init__(self) -> None:
        self.weapons: dict[str, dict] = _load("weapons/weapons.json")
        self.weapon_visuals: dict[str, dict] = _load("weapons/weapon_visuals.json")
        self.enemies: dict[str, dict] = _load("enemies/enemies.json")
        self.bosses: dict[str, dict] = _load("enemies/bosses.json")
        # ENT-017: the behaviour templates `entities/ai/templates.py` builds.
        self.behaviors: dict = _load("enemies/behaviors.json")
        self.characters: dict[str, dict] = _load("heroes/characters.json")
        self.blessings: dict[str, dict] = _load("weapons/blessings.json")
        self.offering: dict = _load("weapons/offering.json")        # P2 weights
        self.forges: dict[str, dict] = _load("weapons/forges.json")   # P3 Forgings
        self.items: dict = _load("weapons/items.json")
        # Elemental infusions (journal: elemental_system_journal.md). The
        # schema lives in `combat.elements.config`; both files are content,
        # so a missing, unknown or out-of-range value stops the boot.
        self.elements: dict = _check_elements(_load("weapons/elements.json"))
        self.reactions: dict = _check_reactions(_load("weapons/reactions.json"))
        # Presentation only, split from the tuning the way
        # `weapon_visuals.json` is split from `weapons.json`.
        self.element_visuals: dict = _check_element_visuals(
            _load("weapons/element_visuals.json"))
        # RND-007: how a status is drawn on the enemy carrying it.
        self.status_visuals: dict = _load("weapons/status_visuals.json")
        self.meta_upgrades: dict[str, dict] = _load("heroes/meta_upgrades.json")
        # CB-8: health potion drops. Validated here so a table that does not
        # cover every rarity fails at boot, not on the first kill.
        self.potions: dict = _check_potions(_load("loot/potions.json"))
        # CB-9: what a treasure chest contains. Checked against the potion
        # table it draws from, so a tier naming a potion rarity that does not
        # exist fails at boot rather than on the first chest opened.
        self.chests: dict = _check_chests(_load("loot/chests.json"), self.potions)
        # Sprite rigs are split by domain; a rig shared by two domains (e.g.
        # `dead`, used by heroes and enemies) is copied into both files. They
        # merge back into one flat `sprites` namespace here.
        self.sprites: dict[str, dict] = _merge_sprites(
            "heroes/character_sprites.json", "enemies/enemy_sprites.json",
            "weapons/weapon_sprites.json", "weapons/infused_sprites.json",
            "loot/prop_sprites.json")
        _check_element_rigs(self.element_visuals, self.sprites)
        self.terrain: dict = _load("world/terrain.json")
        # Buff buildings (journal: buff_buildings_journal.md): the five
        # interactive buildings and their timed buffs. Their obstacle kinds,
        # skins and rigs are folded into the terrain blocks here so the
        # generator, the bake and the renderer treat them as any other kind.
        self.buildings: dict = _check_buildings(_load("world/buildings.json"))
        self.ui_sprites: dict[str, dict] = _load("ui/ui_sprites.json")
        _merge_buildings(self.terrain, self.ui_sprites, self.buildings)
        # Village NPC tuning (HI-3): speeds, idle bands, leashes, counts.
        self.npcs: dict = _load("village/npcs.json")
        # The spawn schedule (spawn master S2). Checked here, against the
        # enemies just loaded, so a phase that names an enemy that does not
        # exist fails at boot rather than at minute eight.
        try:
            self.spawn_tables = SpawnTables(_load("enemies/spawn_tables.json"),
                                            enemy_ids=self.enemies)
        except TableError as exc:
            raise ContentError(str(exc)) from exc
        log.info("content loaded: %d weapons, %d enemies, %d bosses, "
                 "%d characters, %d blessings, %d affixes, %d meta upgrades, "
                 "%d sprite rigs, %d terrain rigs, %d ui rigs, "
                 "%d spawn groups",
                 len(self.weapons), len(self.enemies), len(self.bosses),
                 len(self.characters), len(self.blessings),
                 len(self.items.get("affixes", {})), len(self.meta_upgrades),
                 len(self.sprites), len(self.terrain.get("rigs", {})),
                 len(self.ui_sprites), len(self.spawn_tables.groups))

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

    def widest_walker_radius(self) -> float:
        """The largest collider radius among the enemies and bosses that walk
        -- a `flying` tag ignores terrain, so it is left out. World generation
        keeps every bridge deck this clear (WLD-012), so a wider walker added
        to the data is covered without a code change."""
        return max(float(spec["radius"])
                   for table in (self.enemies, self.bosses)
                   for spec in table.values()
                   if "flying" not in spec.get("tags", ()))

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
