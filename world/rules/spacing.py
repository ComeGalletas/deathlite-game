"""Spatial hash for placement tests.

Pure geometry, with no knowledge of props, rigs, terrain or generation, which
is why it sits in `world/rules/` and not beside any one of its callers: the
decor scatter uses it for prop separation and for obstacle clearance, and the
spawn-point stage uses it to keep points off obstacles.

Callers want two different questions answered, so there are two queries --
`blocked` takes the larger of the two separations, `within` adds them. Both
walk the same nine buckets; the difference is only in what "too close" means
to that caller, and each is documented where it is defined.
"""
from __future__ import annotations


class _Neighbourhood:
    """Uniform spatial hash over points that reject candidates near them.

    The scatter tested every candidate against everything already placed, which
    is O(n^2) and was invisible at forty props an island. It is not invisible at
    several hundred, and the tiers below are about raising exactly that number.

    `cell` must be at least the largest separation anything stored will ask
    for; then everything that could reject a candidate lives in the nine cells
    around it, and a test costs a handful of comparisons instead of a scan.
    """

    __slots__ = ("cell", "buckets")

    def __init__(self, cell: float) -> None:
        self.cell = max(1.0, float(cell))
        self.buckets: dict = {}

    def add(self, x: float, y: float, gap: float) -> None:
        self.buckets.setdefault(
            (int(x // self.cell), int(y // self.cell)), []).append((x, y, gap))

    def blocked(self, x: float, y: float, gap: float = 0.0) -> bool:
        """Is anything stored closer than the larger of the two separations?

        Taking the *larger* is what lets a small `min_gap` bunch flora into
        patches while a default-gap prop still holds everything off it. Query
        with `gap = 0` to honour only what is stored -- which is how the
        obstacle clearance keeps its exact `(radius + 20)` meaning.
        """
        cx, cy = int(x // self.cell), int(y // self.cell)
        for bx in (cx - 1, cx, cx + 1):
            for by in (cy - 1, cy, cy + 1):
                for ox, oy, og in self.buckets.get((bx, by), ()):
                    d = gap if gap > og else og
                    if (x - ox) ** 2 + (y - oy) ** 2 < d * d:
                        return True
        return False

    def within(self, x: float, y: float, extra: float) -> bool:
        """Is anything stored closer than *its own* separation plus `extra`?

        The sum, not the larger: an obstacle keeps a spawn point its own
        radius plus the point's body radius plus a gap away, and no single
        number expresses that. Store `radius + gap` and query with the body
        radius. `cell` must then be at least the largest such *sum* any query
        can produce -- the widest stored separation plus the widest `extra` --
        or a rejecting neighbour could sit outside the nine cells searched.
        """
        cx, cy = int(x // self.cell), int(y // self.cell)
        for bx in (cx - 1, cx, cx + 1):
            for by in (cy - 1, cy, cy + 1):
                for ox, oy, og in self.buckets.get((bx, by), ()):
                    d = og + extra
                    if (x - ox) ** 2 + (y - oy) ** 2 < d * d:
                        return True
        return False

