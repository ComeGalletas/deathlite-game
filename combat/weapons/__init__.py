"""Weapon runtime package (six-weapon system, P1).

`core.py` holds `Weapon` / `FireContext` and the taxonomy; `bomb.py` the
fused throw. Everything public is re-exported here so `from combat.weapons
import Weapon` keeps working.
"""
from combat.weapons.core import (   # noqa: F401
    CATEGORIES, CLASSES, SPECIAL_EFFECTS, FireContext, NO_MODS, Weapon,
    WeaponMods,
)

__all__ = ["CATEGORIES", "CLASSES", "SPECIAL_EFFECTS", "FireContext",
           "NO_MODS", "Weapon", "WeaponMods"]
