"""Broad-phase spatial hash grid (spec 6.1: avoid unbounded O(N^2)).

Enemies are inserted each frame; weapons/projectiles query a small radius rather
than scanning every enemy. Cell size comes from config.GRID_CELL_SIZE.

This is deliberately simple (rebuild-per-frame). Profiling decides if a smarter
incremental structure is ever needed.
"""
from __future__ import annotations

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


def circles_overlap(ax: float, ay: float, ar: float,
                    bx: float, by: float, br: float) -> bool:
    dx = ax - bx
    dy = ay - by
    rr = ar + br
    return dx * dx + dy * dy <= rr * rr
