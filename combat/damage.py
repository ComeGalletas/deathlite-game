"""Pure damage math. No pygame, no state -- fully unit testable (spec 8).

Kept small on purpose; crit / status / elemental modifiers slot in here in
later milestones so damage rules are never duplicated across weapons.
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class DamageResult:
    amount: float
    is_crit: bool


def outgoing_damage(base: float, damage_multiplier: float,
                    crit_chance: float = 0.0, crit_multiplier: float = 2.0,
                    rng: random.Random | None = None) -> DamageResult:
    """Damage a source deals before the target's mitigation.

    `crit_chance` in [0, 1]. A seeded `rng` makes this deterministic for tests
    (spec 4.4 / 8: "Use seeded random generators in tests").
    """
    amount = max(0.0, base) * max(0.0, damage_multiplier)
    is_crit = False
    if crit_chance > 0.0:
        roll = (rng or random).random()
        if roll < crit_chance:
            amount *= crit_multiplier
            is_crit = True
    return DamageResult(amount=amount, is_crit=is_crit)


def apply_armor(amount: float, armor: float) -> float:
    """Flat armor: subtracts from incoming damage, never below zero."""
    return max(0.0, amount - max(0.0, armor))
