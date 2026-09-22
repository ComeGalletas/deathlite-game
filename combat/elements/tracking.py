"""Damage and application tracking for the elemental system (design §3.6).

Two questions the run summary and the dev overlay answer, and they are not
the same question:

* **which effect dealt the damage** -- a Fire hit, a burn tick, a Thunder
  jump, an Overload shockwave. This is what "Overload: 12,400" means.
* **which weapon it belongs to** -- every record also carries the weapon
  whose hit started the chain, so the per-weapon totals the game-over
  screen already shows stay whole.

So every row is keyed by the pair. The run ledger keeps its existing
`damage[source]` untouched (source being the weapon id), which is what
`stats["damage_dealt"]` is pinned against; this adds the second dimension
beside it rather than replacing it.

**Source rules** (§3.6, confirmed): base element damage and its bound
status belong to the weapon that applied it; a reaction and everything it
spawns belong to the weapon whose hit *triggered* it; Thunder jump nodes
and the reactions they set off belong to the original Thunder hit's weapon;
frozen contact damage belongs to the weapon whose knockback pushed the
frozen enemy.
"""
from __future__ import annotations

from combat.elements.ids import (ELEMENTS, REACTIONS, ElementId,
                                 ReactionId)

# --- effect ids -------------------------------------------------------------------
# What dealt a piece of elemental damage. Strings, like every other damage
# source in this project (`RunLedger.damage` is keyed by weapon id), so the
# summary and the dev log need no translation table.
FIRE_HIT = "fire_hit"
BURN = "burn"
WIND_HIT = "wind_hit"
WIND_AREA = "wind_area"
THUNDER_CHAIN = "thunder_chain"
FROZEN_CONTACT = "frozen_contact"
FROSTBURN = "frostburn"
OVERLOAD = "overload"
OVERLOAD_WAVE = "overload_wave"
SUPERCONDUCT = "superconduct"
FIREWIND = "firewind"
ICEWIND = "icewind"
THUNDERWIND = "thunderwind"
THUNDER_STRIKE = "thunder_strike"

EFFECTS: tuple[str, ...] = (
    FIRE_HIT, BURN, WIND_HIT, WIND_AREA, THUNDER_CHAIN, FROZEN_CONTACT,
    FROSTBURN, OVERLOAD, OVERLOAD_WAVE, SUPERCONDUCT, FIREWIND, ICEWIND,
    THUNDERWIND, THUNDER_STRIKE)

_LABELS = {
    FIRE_HIT: "Fire", BURN: "Burn", WIND_HIT: "Wind", WIND_AREA: "Wind area",
    THUNDER_CHAIN: "Thunder chain", FROZEN_CONTACT: "Frozen contact",
    FROSTBURN: "Frostburn", OVERLOAD: "Overload",
    OVERLOAD_WAVE: "Overload shockwave", SUPERCONDUCT: "Superconduct",
    FIREWIND: "FireWind", ICEWIND: "IceWind", THUNDERWIND: "ThunderWind",
    THUNDER_STRIKE: "Thunder strike",
}

UNATTRIBUTED = "other"      # matches `RunLedger.UNATTRIBUTED`

# Which element or reaction a piece of damage came from (M11). Keyed the
# same way `_LABELS` is, and living beside it for the same reason: the
# effect id is the one name every part of the system already agrees on.
#
# Deliberately *not* a colour. This module is combat-side and has no
# business knowing what an element looks like; it answers "whose damage
# was this" and the visual layer turns that into a colour.
_SOURCE: dict[str, object] = {
    FIRE_HIT: ElementId.FIRE, BURN: ElementId.FIRE,
    WIND_HIT: ElementId.WIND, WIND_AREA: ElementId.WIND,
    THUNDER_CHAIN: ElementId.THUNDER, THUNDER_STRIKE: ElementId.THUNDER,
    FROZEN_CONTACT: ElementId.ICE,
    FROSTBURN: ReactionId.FROSTBURN,
    OVERLOAD: ReactionId.OVERLOAD, OVERLOAD_WAVE: ReactionId.OVERLOAD,
    SUPERCONDUCT: ReactionId.SUPERCONDUCT,
    FIREWIND: ReactionId.FIREWIND, ICEWIND: ReactionId.ICEWIND,
    THUNDERWIND: ReactionId.THUNDERWIND,
}


def label(effect: str) -> str:
    return _LABELS.get(effect, effect.replace("_", " ").title())


def source_of(effect: str):
    """The `ElementId` or `ReactionId` behind an effect id, or None for a
    weapon's own damage."""
    return _SOURCE.get(effect)


class ElementTracking:
    """The run's elemental books. One dictionary increment per event; no
    allocation on the hot path once a key exists."""

    def __init__(self) -> None:
        # (weapon id, effect id) -> damage
        self.damage: dict[tuple[str, str], float] = {}
        # (weapon id, element key) -> how many times that weapon applied it
        self.applications: dict[tuple[str, str], int] = {}
        # (weapon id, reaction key) -> how many of that reaction it triggered
        self.reactions: dict[tuple[str, str], int] = {}

    # --- recording -----------------------------------------------------
    def record_damage(self, amount: float, weapon_id: str, effect: str) -> None:
        if amount <= 0.0 or not effect:
            return
        key = (weapon_id or UNATTRIBUTED, effect)
        self.damage[key] = self.damage.get(key, 0.0) + amount

    def record_application(self, weapon_id: str, element) -> None:
        key = (weapon_id or UNATTRIBUTED, element.key)
        self.applications[key] = self.applications.get(key, 0) + 1

    def record_reaction(self, weapon_id: str, reaction) -> None:
        key = (weapon_id or UNATTRIBUTED, reaction.key)
        self.reactions[key] = self.reactions.get(key, 0) + 1

    # --- readout -------------------------------------------------------
    @property
    def total_damage(self) -> float:
        return sum(self.damage.values())

    def damage_by_effect(self) -> dict[str, float]:
        """`{effect: damage}`, every weapon pooled -- the "Overload: 12,400"
        line."""
        out: dict[str, float] = {}
        for (_weapon, effect), amount in self.damage.items():
            out[effect] = out.get(effect, 0.0) + amount
        return out

    def damage_by_weapon(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for (weapon, _effect), amount in self.damage.items():
            out[weapon] = out.get(weapon, 0.0) + amount
        return out

    def effect_rows(self) -> list[dict]:
        """One row per effect, biggest first: id, display name, damage, and
        the per-weapon split."""
        pooled = self.damage_by_effect()
        rows = []
        for effect, amount in sorted(pooled.items(), key=lambda kv: -kv[1]):
            by_weapon = {w: d for (w, e), d in self.damage.items() if e == effect}
            rows.append({"id": effect, "name": label(effect), "damage": amount,
                         "by_weapon": by_weapon})
        return rows

    def application_rows(self) -> list[dict]:
        """One row per (weapon, element) pair, most applications first."""
        return [{"weapon": weapon, "element": element, "count": count}
                for (weapon, element), count in
                sorted(self.applications.items(), key=lambda kv: (-kv[1], kv[0]))]

    def reaction_rows(self) -> list[dict]:
        return [{"weapon": weapon, "reaction": reaction, "count": count}
                for (weapon, reaction), count in
                sorted(self.reactions.items(), key=lambda kv: (-kv[1], kv[0]))]

    def counts_for(self, weapon_id: str) -> dict[str, int]:
        """`{element key: applications}` for one weapon (the build screen)."""
        return {element: count for (weapon, element), count
                in self.applications.items() if weapon == weapon_id}

    def snapshot(self) -> dict:
        """What the run summary is handed at the end of a run. Plain types
        only, so it survives into the end screens like every other stat."""
        return {
            "effects": self.effect_rows(),
            "applications": self.application_rows(),
            "reactions": self.reaction_rows(),
            "total": self.total_damage,
        }

    def __bool__(self) -> bool:
        return bool(self.damage or self.applications or self.reactions)


def known_element_keys() -> tuple[str, ...]:
    return tuple(e.key for e in ELEMENTS)


def known_reaction_keys() -> tuple[str, ...]:
    return tuple(r.key for r in REACTIONS)
