"""XP and leveling (spec 3.5). Pure logic, no pygame -- unit tested (spec 8).

The curve is intentionally simple and monotonic: each level costs a base amount
plus a linear ramp, so early levels come fast (dopamine) and later ones slow
down without ever spiking unfairly. Past `LATE_LEVEL` the ramp is deliberately
flattened again, so a long run keeps levelling instead of stalling.
"""
from __future__ import annotations

from dataclasses import dataclass

BASE_XP = 5
LINEAR = 4      # extra xp per level
QUADRATIC = 0.9  # gentle acceleration
# Flat pacing cut applied to every level's cost, so levels arrive faster
# across the whole run without changing the shape of the curve. Calibrated
# against the level-15 milestone: 0.75 was the first pass, then 0.75 * 0.8
# to make reaching level 15 cost 20 % less again (1165 -> 870 -> 696 XP).
XP_SCALE = 0.60
# --- Late-game flattening ------------------------------------------------
# Above `LATE_LEVEL` the quadratic ramp outruns the run's XP income and the
# last third of a run stalls, so late levels take a further `LATE_CUT` off.
# The cut phases in over `LATE_RAMP` levels rather than landing as a step:
# the curve only grows about 9 % a level here, so applying 25 % at once would
# make level 21 *cheaper* than level 20 and break the monotonicity the whole
# curve (and `test_strictly_increasing`) rests on. A four-level phase-in is
# monotonic but puts levels 23 and 24 on the same cost; five is the shortest
# that still rises every level, so the full cut is in effect from level 25.
LATE_LEVEL = 20
LATE_CUT = 0.25
LATE_RAMP = 5


def _late_factor(level: int) -> float:
    """The late-game discount on `level`: 1.0 up to `LATE_LEVEL`, easing down
    to `1 - LATE_CUT` over the next `LATE_RAMP` levels and flat after that."""
    t = (level - LATE_LEVEL) / LATE_RAMP
    return 1.0 - LATE_CUT * min(1.0, max(0.0, t))


def xp_for_level(level: int) -> int:
    """XP needed to go from `level` to `level + 1` (level >= 1)."""
    if level < 1:
        raise ValueError("level must be >= 1")
    n = level - 1
    base = BASE_XP + LINEAR * n + QUADRATIC * n * n
    return int(XP_SCALE * _late_factor(level) * base)


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
