"""Layered stat modifiers (spec 8: "Stat modifiers").

A `StatSet` holds base values plus a list of `Modifier`s contributed by
characters, level-up upgrades, blessings, items and meta-progression. The final
value of a stat is

    (base + sum FLAT) * (1 + sum PCT) * product(1 + each MULT)

FLAT and PCT are pooled (order-independent); MULT entries compound. Every
modifier carries a `source` string so a whole source (e.g. one blessing, one
item) can be removed atomically when it is unequipped.

Pure module -- no pygame, fully unit tested.
"""
from __future__ import annotations

from dataclasses import dataclass

FLAT = "flat"   # additive to the base
PCT = "pct"     # additive percentage, all summed then applied once
MULT = "mult"   # multiplicative, each (1 + value) compounds

_OPS = (FLAT, PCT, MULT)

# Stats that must never resolve below zero.
_NON_NEGATIVE = {
    "max_hp", "move_speed", "armor", "pickup_radius",
    "damage_multiplier", "attack_speed_multiplier", "projectile_speed_multiplier",
}


@dataclass(frozen=True)
class Modifier:
    stat: str
    op: str
    value: float
    source: str = ""

    def __post_init__(self) -> None:
        if self.op not in _OPS:
            raise ValueError(f"unknown modifier op: {self.op!r}")


class StatSet:
    def __init__(self, base: dict[str, float]) -> None:
        self._base = dict(base)
        self._mods: list[Modifier] = []
        self._cache: dict[str, float] = {}
        self._dirty = True

    # --- mutation --------------------------------------------------
    def add(self, *mods: Modifier) -> None:
        self._mods.extend(mods)
        self._dirty = True

    def remove_source(self, source: str) -> None:
        before = len(self._mods)
        self._mods = [m for m in self._mods if m.source != source]
        if len(self._mods) != before:
            self._dirty = True

    def set_base(self, stat: str, value: float) -> None:
        self._base[stat] = value
        self._dirty = True

    # --- query ----------------------------------------------------
    def _recompute(self) -> None:
        out: dict[str, float] = dict(self._base)
        flat: dict[str, float] = {}
        pct: dict[str, float] = {}
        mult: dict[str, float] = {}
        for m in self._mods:
            if m.op == FLAT:
                flat[m.stat] = flat.get(m.stat, 0.0) + m.value
            elif m.op == PCT:
                pct[m.stat] = pct.get(m.stat, 0.0) + m.value
            else:  # MULT
                mult[m.stat] = mult.get(m.stat, 1.0) * (1.0 + m.value)

        for stat in set(list(out) + list(flat) + list(pct) + list(mult)):
            base = out.get(stat, 0.0)
            val = (base + flat.get(stat, 0.0)) * (1.0 + pct.get(stat, 0.0))
            val *= mult.get(stat, 1.0)
            if stat in _NON_NEGATIVE:
                val = max(0.0, val)
            out[stat] = val

        self._cache = out
        self._dirty = False

    def get(self, stat: str) -> float:
        if self._dirty:
            self._recompute()
        return self._cache.get(stat, 0.0)

    def as_dict(self) -> dict[str, float]:
        if self._dirty:
            self._recompute()
        return dict(self._cache)

    def sources(self) -> set[str]:
        return {m.source for m in self._mods}
