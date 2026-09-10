"""Forging (six-weapon system P3; design §7, §8, §13).

A Forging permanently transforms a weapon. In data (`data/forges.json`) it
is a variant: `overrides` merged over the base weapon definition (numbers,
the special effect, even the category -- Fan of Blades throws, Arcane Storm
orbits) plus `effects` keys the fire path and the hit resolver read
(shockwave, crater hazard, twin cones, cluster bomblets, mines).

Rules: one Forge per weapon, the two options mutually exclusive; the weapon
must have taken `forge_requires_levels` blessing levels first
(`data/offering.json`). Forgings are delivered by the village Forge and, at
Forge rarity, by the level-up offering (`progression/blessings/offer.py`).
Post-Forge blessings gate on `requires.forge` in the catalog.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from combat.weapons.core import CATEGORIES, CLASSES, SPECIAL_EFFECTS, Weapon

# Definition keys a Forging may override. Anything else is bad data.
OVERRIDABLE = frozenset((
    "name", "description", "damage", "cooldown", "projectile_count",
    "projectile_speed", "projectile_lifetime", "spread_deg", "area", "weight",
    "targeting_mode", "pierce", "special_effect", "category", "tags", "reach",
    "aim_assist_deg", "cone_half_angle", "stun_chance", "stun_duration",
    "fuse", "throw_time", "blast_radius", "blast_lifetime", "orbit_radius",
    "orbit_speed", "rehit_interval", "chain_count", "chain_range",
    "swing_time", "impact_offset", "impact_rig",
))
# Effect keys with code behind them (core.py, effects.py, combat.py).
EFFECT_KEYS = frozenset((
    "shockwave_radius", "shockwave_damage_mult",
    "hazard_radius", "hazard_dps_mult", "hazard_duration",
    "twin_offset_deg",
    "cluster_count", "cluster_damage_mult", "cluster_radius_mult",
    "cluster_fuse", "cluster_speed",
    "mine", "mine_arm_delay", "mine_lifetime",
))


@dataclass(frozen=True)
class ForgeDef:
    id: str
    name: str
    weapon: str
    identity: str
    description: str
    overrides: dict = field(default_factory=dict)
    effects: dict = field(default_factory=dict)


class Forges:
    def __init__(self, data: dict[str, dict], weapons: dict[str, dict]) -> None:
        self.by_id: dict[str, ForgeDef] = {}
        for fid, d in data.items():
            self.by_id[fid] = _parse(fid, d, weapons)
        per_weapon: dict[str, list[ForgeDef]] = {}
        for f in self.by_id.values():
            per_weapon.setdefault(f.weapon, []).append(f)
        self._per_weapon = per_weapon

    def get(self, fid: str) -> ForgeDef:
        return self.by_id[fid]

    def for_weapon(self, weapon_id: str) -> list[ForgeDef]:
        return list(self._per_weapon.get(weapon_id, ()))


def _parse(fid: str, d: dict, weapons: dict) -> ForgeDef:
    for key in ("name", "weapon", "identity", "description", "overrides", "effects"):
        if key not in d:
            raise ValueError(f"forge {fid!r}: missing {key!r}")
    if d["weapon"] not in weapons:
        raise ValueError(f"forge {fid!r}: weapon {d['weapon']!r} is not a weapon")
    if weapons[d["weapon"]]["class"] == "summon":
        raise ValueError(f"forge {fid!r}: summons cannot be forged (design §3.7)")
    ov = dict(d["overrides"])
    bad = set(ov) - OVERRIDABLE
    if bad:
        raise ValueError(f"forge {fid!r}: cannot override {sorted(bad)}")
    if "category" in ov and ov["category"] not in CATEGORIES:
        raise ValueError(f"forge {fid!r}: category {ov['category']!r}")
    if "special_effect" in ov and ov["special_effect"] not in SPECIAL_EFFECTS:
        raise ValueError(f"forge {fid!r}: special_effect {ov['special_effect']!r}")
    fx = dict(d["effects"])
    bad = set(fx) - EFFECT_KEYS
    if bad:
        raise ValueError(f"forge {fid!r}: unknown effects {sorted(bad)}")
    return ForgeDef(fid, d["name"], d["weapon"], d["identity"], d["description"], ov, fx)


# --- per-content cache -------------------------------------------------
_FORGES: dict[int, Forges] = {}


def get_forges(content) -> Forges:
    key = id(content)
    if key not in _FORGES:
        _FORGES[key] = Forges(content.forges, content.weapons)
    return _FORGES[key]


# --- eligibility + application -------------------------------------------
def blessing_levels(weapon: Weapon) -> int:
    """How many weapon-blessing levels the weapon has taken (the HUD level
    is 1 + that)."""
    return max(0, int(weapon.level) - 1)


def forge_eligible(weapon: Weapon, required_levels: int) -> bool:
    return (weapon.forge is None and not weapon.is_summon
            and blessing_levels(weapon) >= required_levels)


def apply_forge(weapon: Weapon, fdef: ForgeDef) -> None:
    """Transform `weapon` in place: merge the overrides, take the effects,
    record the Forge. Exclusive: a forged weapon cannot be forged again."""
    if fdef.weapon != weapon.weapon_id:
        raise ValueError(f"{fdef.id} forges {fdef.weapon}, not {weapon.weapon_id}")
    if weapon.forge is not None:
        raise ValueError(f"{weapon.weapon_id} is already forged into {weapon.forge}")
    merged = dict(weapon.definition)
    merged.update(fdef.overrides)
    if merged.get("class") not in CLASSES:
        raise ValueError(f"{fdef.id}: the merged definition lost its class")
    weapon.definition = merged
    weapon.effects.update(fdef.effects)
    weapon.forge = fdef.id
    # A change of fire mechanism drops any persistent projectiles / summons
    # the old one kept; the new one re-forms them on its next update.
    for o in weapon._orbiters:
        o.active = False
    weapon._orbiters.clear()
    weapon._orbit_count = 0
    weapon.__post_init__()                    # re-validate category / special
