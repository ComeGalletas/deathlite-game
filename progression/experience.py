"""XP and leveling (spec 3.5). Pure logic, no pygame -- unit tested (spec 8).

The curve is intentionally simple and monotonic: each level costs a base amount
plus a linear ramp, so early levels come fast (dopamine) and later ones slow
down without ever spiking unfairly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

BASE_XP = 5
LINEAR = 4      # extra xp per level
QUADRATIC = 0.9  # gentle acceleration


def xp_for_level(level: int) -> int:
    """XP needed to go from `level` to `level + 1` (level >= 1)."""
    if level < 1:
        raise ValueError("level must be >= 1")
    n = level - 1
    return int(BASE_XP + LINEAR * n + QUADRATIC * n * n)


@dataclass
class LevelTracker:
    level: int = 1
    xp_into_level: int = 0
    # Levels gained but not yet "spent" on an upgrade choice.
    pending_level_ups: int = 0
    total_xp: int = 0

    def add_xp(self, amount: int) -> int:
        """Add XP, rolling over multiple levels if needed. Returns the number of
        new level-ups this call produced (also added to pending_level_ups)."""
        if amount < 0:
            raise ValueError("xp amount must be non-negative")
        self.total_xp += amount
        self.xp_into_level += amount
        gained = 0
        while self.xp_into_level >= xp_for_level(self.level):
            self.xp_into_level -= xp_for_level(self.level)
            self.level += 1
            gained += 1
        self.pending_level_ups += gained
        return gained

    def consume_pending(self) -> bool:
        """Claim one pending level-up (call after the player picks an upgrade).
        Returns True if one was consumed."""
        if self.pending_level_ups > 0:
            self.pending_level_ups -= 1
            return True
        return False

    @property
    def progress_fraction(self) -> float:
        need = xp_for_level(self.level)
        return 0.0 if need <= 0 else min(1.0, self.xp_into_level / need)
