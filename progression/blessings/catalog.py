"""The blessing catalog: `data/blessings.json` validated and typed.

A `BlessingDef` is pure data. Every effect carries a `levels` list of
cumulative values (level I is `levels[0]`); the catalog's `max_level` is the
common length of those lists. Validation is strict on purpose (design ground
rule: a missing field is bad data, never a silent default): an unknown kind,
rarity, category, effect type, display or weapon id raises at load.
"""
from __future__ import annotations

from dataclasses import dataclass, field

KINDS = ("stat", "weapon")
RARITIES = ("common", "uncommon", "rare", "forge")
CATEGORIES = ("power", "coverage", "behavior", "synergy")
EFFECT_TYPES = ("stat", "weapon_bonus", "weapon_effect")
STAT_OPS = ("flat", "pct", "mult")
BONUS_MODES = ("add", "mult")
DISPLAYS = ("flat", "pct", "pct_drop", "chance", "seconds", "mult", "raw",
            "degrees", "hidden")
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")


def roman(level: int) -> str:
    return ROMAN[level - 1] if 1 <= level <= len(ROMAN) else str(level)


def format_value(value: float, display: str) -> str:
    """The value as the card prints it."""
    if display == "flat":
        return f"+{value:g}"
    if display == "pct":
        return f"+{value * 100:.0f}%"
    if display == "pct_drop":
        return f"{(1.0 - value) * 100:.0f}%"
    if display == "chance":
        return f"{value * 100:.0f}%"
    if display == "seconds":
        return f"+{value:g}s"
    if display == "mult":
        return f"x{value:g}"
    if display == "degrees":
        return f"+{value:g}°"
    return f"{value:g}"                                       # raw / hidden


@dataclass(frozen=True)
class Effect:
    type: str                       # stat | weapon_bonus | weapon_effect
    levels: tuple[float, ...]
    display: str
    stat: str = ""                  # stat: the StatSet stat
    op: str = "flat"                # stat: flat | pct | mult
    heal: bool = False              # stat: also heal by the delta (max HP)
    field: str = ""                 # weapon_bonus: the Weapon.bonus key
    mode: str = "add"               # weapon_bonus: add | mult
    key: str = ""                   # weapon_effect: the Weapon.effects key

    def value_at(self, level: int) -> float:
        return float(self.levels[level - 1])

    def delta(self, level: int) -> float:
        """What applying `level` adds (or, for a mult bonus, multiplies by)
        on top of `level - 1`."""
        cur = self.value_at(level)
        if level == 1:
            return cur if not (self.type == "weapon_bonus" and self.mode == "mult") else cur
        prev = self.value_at(level - 1)
        if self.type == "weapon_bonus" and self.mode == "mult":
            return cur / prev
        return cur - prev


@dataclass(frozen=True)
class BlessingDef:
    id: str
    name: str
    kind: str
    category: str
    rarity: str
    description: str                # template: {0}, {1}... = effect values
    effects: tuple[Effect, ...]
    weapon: str | None = None       # weapon blessings only
    requires_weapons: tuple[str, ...] = ()
    requires_forge: str | None = None
    tags: tuple[str, ...] = ()

    @property
    def max_level(self) -> int:
        return len(self.effects[0].levels)

    def describe(self, level: int) -> str:
        values = [format_value(e.value_at(level), e.display) for e in self.effects]
        return self.description.format(*values)

    def title(self, level: int) -> str:
        return f"{self.name} {roman(level)}"


class Catalog:
    def __init__(self, data: dict[str, dict], weapons: dict[str, dict],
                 forges: dict | None = None) -> None:
        self.by_id: dict[str, BlessingDef] = {}
        for bid, d in data.items():
            if bid.startswith("_"):
                continue                                   # "_comment"
            self.by_id[bid] = _parse(bid, d, weapons, forges or {})
        self.weapon_classes = {wid: w["class"] for wid, w in weapons.items()}

    def get(self, bid: str) -> BlessingDef:
        return self.by_id[bid]

    def of_kind(self, kind: str) -> list[BlessingDef]:
        return [b for b in self.by_id.values() if b.kind == kind]

    def for_weapon(self, weapon_id: str) -> list[BlessingDef]:
        return [b for b in self.by_id.values() if b.weapon == weapon_id]

    def is_summon(self, bdef: BlessingDef) -> bool:
        return bdef.weapon is not None and self.weapon_classes[bdef.weapon] == "summon"


def _parse(bid: str, d: dict, weapons: dict, forges: dict) -> BlessingDef:
    def need(key):
        if key not in d:
            raise ValueError(f"blessing {bid!r}: missing {key!r}")
        return d[key]

    kind = need("kind")
    if kind not in KINDS:
        raise ValueError(f"blessing {bid!r}: kind {kind!r} not in {KINDS}")
    rarity = need("rarity")
    if rarity not in RARITIES:
        raise ValueError(f"blessing {bid!r}: rarity {rarity!r} not in {RARITIES}")
    category = need("category")
    if category not in CATEGORIES:
        raise ValueError(f"blessing {bid!r}: category {category!r} not in {CATEGORIES}")
    weapon = d.get("weapon")
    if kind == "weapon":
        if weapon not in weapons:
            raise ValueError(f"blessing {bid!r}: weapon {weapon!r} is not a weapon")
    elif weapon is not None:
        raise ValueError(f"blessing {bid!r}: a stat blessing names a weapon")
    req = d.get("requires", {})
    for wid in req.get("weapons", ()):
        if wid not in weapons:
            raise ValueError(f"blessing {bid!r}: requires unknown weapon {wid!r}")
    forge = req.get("forge")
    if forge is not None:
        if forge not in forges:
            raise ValueError(f"blessing {bid!r}: requires unknown forge {forge!r}")
        if kind != "weapon" or forges[forge]["weapon"] != weapon:
            raise ValueError(f"blessing {bid!r}: a post-Forge blessing belongs to the forged weapon")

    raw_effects = need("effects")
    if not raw_effects:
        raise ValueError(f"blessing {bid!r}: no effects")
    effects = tuple(_parse_effect(bid, e) for e in raw_effects)
    n = len(effects[0].levels)
    if n == 0 or any(len(e.levels) != n for e in effects):
        raise ValueError(f"blessing {bid!r}: every effect needs the same non-empty levels")
    for e in effects:
        if e.type == "stat" and kind != "stat":
            raise ValueError(f"blessing {bid!r}: a weapon blessing cannot carry a stat effect")
        if e.type != "stat" and kind == "weapon" and weapon is None:
            raise ValueError(f"blessing {bid!r}: weapon effect without a weapon")
    return BlessingDef(
        id=bid, name=need("name"), kind=kind, category=category, rarity=rarity,
        description=need("description"), effects=effects, weapon=weapon,
        requires_weapons=tuple(req.get("weapons", ())),
        requires_forge=req.get("forge"), tags=tuple(d.get("tags", ())))


def _parse_effect(bid: str, e: dict) -> Effect:
    t = e.get("type")
    if t not in EFFECT_TYPES:
        raise ValueError(f"blessing {bid!r}: effect type {t!r} not in {EFFECT_TYPES}")
    display = e.get("display", "raw")
    if display not in DISPLAYS:
        raise ValueError(f"blessing {bid!r}: display {display!r} not in {DISPLAYS}")
    levels = tuple(float(v) for v in e.get("levels", ()))
    if t == "stat":
        op = e.get("op", "flat")
        if op not in STAT_OPS:
            raise ValueError(f"blessing {bid!r}: op {op!r} not in {STAT_OPS}")
        if not e.get("stat"):
            raise ValueError(f"blessing {bid!r}: stat effect without a stat")
        return Effect(t, levels, display, stat=e["stat"], op=op,
                      heal=bool(e.get("heal", False)))
    if t == "weapon_bonus":
        mode = e.get("mode", "add")
        if mode not in BONUS_MODES:
            raise ValueError(f"blessing {bid!r}: mode {mode!r} not in {BONUS_MODES}")
        if not e.get("field"):
            raise ValueError(f"blessing {bid!r}: weapon_bonus without a field")
        return Effect(t, levels, display, field=e["field"], mode=mode)
    if not e.get("key"):
        raise ValueError(f"blessing {bid!r}: weapon_effect without a key")
    return Effect(t, levels, display, key=e["key"])


# --- offering rules (data/offering.json) --------------------------------
@dataclass(frozen=True)
class OfferingRules:
    choices: int
    kind_weights: dict
    summon_factor: float
    level_falloff: tuple[float, ...]
    rarity_weights: dict
    grant_bundle_level: int
    forge_requires_levels: int = 2

    @classmethod
    def from_data(cls, d: dict) -> "OfferingRules":
        kw = dict(d["kind_weights"])
        for k in ("stat", "weapon", "grant", "forge"):
            if k not in kw:
                raise ValueError(f"offering.json: kind_weights lacks {k!r}")
        rw = dict(d["rarity_weights"])
        for r in RARITIES:
            if r not in rw:
                raise ValueError(f"offering.json: rarity_weights lacks {r!r}")
        falloff = tuple(float(x) for x in d["level_falloff"])
        if not falloff:
            raise ValueError("offering.json: level_falloff is empty")
        return cls(int(d["choices"]), kw, float(d["summon_factor"]), falloff, rw,
                   int(d["grant_bundle_level"]), int(d["forge_requires_levels"]))

    def falloff(self, level: int) -> float:
        """Multiplier for a blessing that would reach `level`; past the table
        the last entry holds."""
        i = min(len(self.level_falloff), max(1, level)) - 1
        return self.level_falloff[i]


# --- per-content cache -------------------------------------------------
_CATALOGS: dict[int, Catalog] = {}
_RULES: dict[int, OfferingRules] = {}


def get_catalog(content) -> Catalog:
    key = id(content)
    if key not in _CATALOGS:
        _CATALOGS[key] = Catalog(content.blessings, content.weapons,
                                 getattr(content, "forges", {}))
    return _CATALOGS[key]


def get_rules(content) -> OfferingRules:
    key = id(content)
    if key not in _RULES:
        _RULES[key] = OfferingRules.from_data(content.offering)
    return _RULES[key]
