"""Randomised equipment (spec 4.4 / 4.5).

`generate_item(content, seed=..., item_level=..., luck=..., slot=...)` is fully
deterministic for a given seed: same seed + same data => identical item
(spec 4.4 / 8: "Item generation", "Rarity probabilities").

An item is a base (one guaranteed stat) plus 0-4 rolled affixes by rarity, plus
a unique effect at legendary. Affixes are either plain `stat` mods or
`tag_damage` mods that feed the same synergy aggregate blessings use -- so
"of the Pyre" stacks with the Ember source (spec 4.5: affixes interact with
build tags).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

RARITIES = ("common", "uncommon", "rare", "epic", "legendary")
_AFFIX_COUNT = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4}

# Base rarity weights; luck shifts weight from common toward the top tiers.
_BASE_RARITY_WEIGHTS = {"common": 60, "uncommon": 25, "rare": 10, "epic": 4, "legendary": 1}


def roll_rarity(rng: random.Random, luck: float = 0.0) -> str:
    shift = max(0.0, luck)
    weights = {
        "common":    max(1.0, _BASE_RARITY_WEIGHTS["common"] - shift * 3.0),
        "uncommon":  _BASE_RARITY_WEIGHTS["uncommon"] + shift * 1.0,
        "rare":      _BASE_RARITY_WEIGHTS["rare"] + shift * 1.2,
        "epic":      _BASE_RARITY_WEIGHTS["epic"] + shift * 0.5,
        "legendary": _BASE_RARITY_WEIGHTS["legendary"] + shift * 0.15,
    }
    ids = list(weights)
    return rng.choices(ids, weights=[weights[i] for i in ids], k=1)[0]


@dataclass
class AffixRoll:
    affix_id: str
    name: str
    kind: str          # "stat" | "tag_damage"
    stat: str | None
    tag: str | None
    op: str | None
    value: float

    def to_dict(self) -> dict:
        return {"affix_id": self.affix_id, "name": self.name, "kind": self.kind,
                "stat": self.stat, "tag": self.tag, "op": self.op, "value": self.value}

    @classmethod
    def from_dict(cls, d: dict) -> "AffixRoll":
        return cls(d["affix_id"], d["name"], d["kind"], d.get("stat"),
                   d.get("tag"), d.get("op"), d["value"])


@dataclass
class Item:
    item_id: str            # stable, derived from the seed
    slot: str
    name: str
    rarity: str
    level: int
    base_stat: str
    base_op: str
    base_value: float
    affixes: list[AffixRoll] = field(default_factory=list)
    unique_effect: str | None = None

    # --- serialisation (spec 4.7: human-readable save) -----------------
    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id, "slot": self.slot, "name": self.name,
            "rarity": self.rarity, "level": self.level,
            "base_stat": self.base_stat, "base_op": self.base_op,
            "base_value": self.base_value,
            "affixes": [a.to_dict() for a in self.affixes],
            "unique_effect": self.unique_effect,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        return cls(
            d["item_id"], d["slot"], d["name"], d["rarity"], int(d["level"]),
            d["base_stat"], d["base_op"], float(d["base_value"]),
            [AffixRoll.from_dict(a) for a in d.get("affixes", [])],
            d.get("unique_effect"),
        )

    # --- effect contributions ---------------------------------------
    def stat_effects(self) -> list[tuple[str, str, float]]:
        """(stat, op, value) tuples for the base + every `stat` affix."""
        out = [(self.base_stat, self.base_op, self.base_value)]
        for a in self.affixes:
            if a.kind == "stat":
                out.append((a.stat, a.op, a.value))
        return out

    def tag_effects(self) -> list[tuple[str, float]]:
        return [(a.tag, a.value) for a in self.affixes if a.kind == "tag_damage"]

    def short(self) -> str:
        return f"[{self.rarity[:1].upper()}] {self.name}"


def _round(op: str, value: float) -> float:
    return round(value, 3) if op in ("flat", "mult", "pct") else value


def generate_item(content, *, seed: int, item_level: int = 1, luck: float = 0.0,
                  slot: str | None = None, base_id: str | None = None) -> Item:
    rng = random.Random(seed)
    data = content.items
    bases = data["bases"]
    slot = slot or rng.choice(list(bases))
    base = rng.choice(bases[slot])           # drawn unconditionally -> stream stable
    if base_id is not None:                  # dev menu: force a specific base
        base = next((b for b in bases[slot] if b["id"] == base_id), base)
    rarity = roll_rarity(rng, luck)

    lvl_scale = 1.0 + 0.05 * (item_level - 1)
    base_value = _round(base["op"],
                        rng.uniform(base["min"], base["max"]) * lvl_scale)

    # Eligible affixes for this slot, no stat/tag collisions.
    pool = [(aid, a) for aid, a in data["affixes"].items() if slot in a["slots"]]
    rng.shuffle(pool)
    want = _AFFIX_COUNT[rarity]
    rolled: list[AffixRoll] = []
    used: set[str] = {base["stat"]}
    for aid, a in pool:
        if len(rolled) >= want:
            break
        key = a.get("stat") or a.get("tag")
        if key in used:
            continue
        used.add(key)
        val = _round(a.get("op", "flat"), a["values"][rarity] * lvl_scale)
        rolled.append(AffixRoll(aid, a["name"], a["kind"], a.get("stat"),
                                a.get("tag"), a.get("op"), val))

    unique = None
    if rarity == "legendary":
        unique = data["unique_effects"].get(slot, {}).get("id")

    prefix = data["prefixes"][rarity]
    suffix = f" {rolled[0].name}" if rolled else ""
    name = f"{prefix} {base['name']}{suffix}"
    item_id = f"{slot}-{seed}-{rarity}"

    return Item(item_id, slot, name, rarity, item_level, base["stat"],
                base["op"], base_value, rolled, unique)
