"""XP and leveling (spec 3.5). Pure logic, no pygame -- unit tested (spec 8).

The curve is a base cost plus a linear ramp and a gentle quadratic, so the first
levels come fast (dopamine) and later ones slow down without ever spiking. At
`KNEE_LEVEL` the quadratic term is frozen at the value it reached there and
resumes with the smaller `QUAD_FLAT` coefficient, so the second half of a run
keeps levelling instead of stalling -- the curve is genuinely flatter past the
knee rather than the same shape shifted down.
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
# --- Flattening from the knee -------------------------------------------
# Past `KNEE_LEVEL` the quadratic ramp outran the run's XP income and the last
# two thirds of a run stalled, so from there the quadratic is held at its knee
# value and grows again with `QUAD_FLAT` instead of `QUADRATIC`, under a flat
# `KNEE_CUT`. Every level from the knee on costs at least 15 % less than it did
# before this pass, deepening to about 36 % around level 20.
#
# `KNEE_CUT` is the deepest flat cut the seam tolerates: at 0.82 level 10 costs
# the same 56 XP as level 9 and the curve stops increasing. Even at 0.84 the
# level 9 -> 10 step is only +1 XP, which is forced -- level 9 is fixed and
# level 10 is capped by the 15 % floor, so those two levels are the same length.
KNEE_LEVEL = 10
KNEE_CUT = 0.84
QUAD_FLAT = 0.55

_KNEE_N = KNEE_LEVEL - 1


def xp_for_level(level: int) -> int:
    """XP needed to go from `level` to `level + 1` (level >= 1)."""
    if level < 1:
        raise ValueError("level must be >= 1")
    n = level - 1
    if level < KNEE_LEVEL:
        return int(XP_SCALE * (BASE_XP + LINEAR * n + QUADRATIC * n * n))
    base = (BASE_XP + LINEAR * n + QUADRATIC * _KNEE_N * _KNEE_N
            + QUAD_FLAT * (n * n - _KNEE_N * _KNEE_N))
    return int(XP_SCALE * KNEE_CUT * base)


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
