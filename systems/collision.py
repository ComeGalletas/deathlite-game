"""Broad-phase spatial hash grid (spec 6.1: avoid unbounded O(N^2)).

Enemies are inserted each frame; weapons/projectiles query a small radius rather
than scanning every enemy. Cell size comes from config.GRID_CELL_SIZE.

This is deliberately simple (rebuild-per-frame). Profiling decides if a smarter
incremental structure is ever needed.
"""
from __future__ import annotations

import heapq
import math
from typing import Iterable, TypeVar

from game import config

T = TypeVar("T")


class SpatialGrid:
    def __init__(self, cell_size: int = config.GRID_CELL_SIZE) -> None:
        self.cell_size = cell_size
        self._cells: dict[tuple[int, int], list] = {}

    def _key(self, x: float, y: float) -> tuple[int, int]:
        return (int(x // self.cell_size), int(y // self.cell_size))

    def clear(self) -> None:
        self._cells.clear()

    def rebuild(self, entities: Iterable) -> None:
        self._cells.clear()
        for e in entities:
            self._cells.setdefault(self._key(e.pos.x, e.pos.y), []).append(e)

    def query_circle(self, x: float, y: float, radius: float) -> list:
        """All inserted entities whose cell overlaps the circle. Broad-phase:
        may return a few extra; caller does the precise distance check."""
        r_cells = int(math.ceil(radius / self.cell_size))
        cx, cy = self._key(x, y)
        out: list = []
        for gx in range(cx - r_cells, cx + r_cells + 1):
            for gy in range(cy - r_cells, cy + r_cells + 1):
                bucket = self._cells.get((gx, gy))
                if bucket:
                    out.extend(bucket)
        return out

    def nearest(self, x: float, y: float, count: int, radius: float,
                exclude=(), alive_only: bool = True) -> list:
        """The `count` inserted entities closest to (x, y) inside
        `radius`, nearest first.

        The elemental system asks this a lot -- every Thunder jump
        level, every Superconduct spread, every ThunderWind strike --
        and the answer has to be bounded work, so it is a grid query
        followed by a partial sort rather than a scan of the field.
        `exclude` is a container of `id()`s already taken by this
        chain, which is how "never hit twice" is enforced.
        """
        if count <= 0 or radius <= 0.0:
            return []
        r2 = radius * radius
        scored = []
        for e in self.query_circle(x, y, radius):
            if id(e) in exclude:
                continue
            if alive_only and not getattr(e, 'alive', True):
                continue
            dx, dy = e.pos.x - x, e.pos.y - y
            d2 = dx * dx + dy * dy
            if d2 <= r2:
                scored.append((d2, id(e), e))
        if len(scored) <= count:
            scored.sort(key=lambda s: s[0])
            return [e for _d, _i, e in scored]
        return [e for _d, _i, e in heapq.nsmallest(count, scored,
                                                   key=lambda s: s[0])]


def circles_overlap(ax: float, ay: float, ar: float,
                    bx: float, by: float, br: float) -> bool:
    dx = ax - bx
    dy = ay - by
    rr = ar + br
    return dx * dx + dy * dy <= rr * rr
