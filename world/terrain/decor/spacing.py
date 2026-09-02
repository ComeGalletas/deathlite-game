"""Spatial hash for placement tests.

Its own module because it is pure geometry with no knowledge of props, rigs or
terrain -- the room scatter uses it for prop separation and for obstacle
clearance, with different query conventions each time.
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
