"""Island lattice geometry: the chunk rect an island is placed in, the full
cell mask a height map starts from, and the four-connectivity check."""
from __future__ import annotations

import pygame

from world.gen.tuning import _DIRS


def _cell_rect(cell: tuple[int, int], chunk) -> pygame.Rect:
    """The lattice cell a room is placed in. `chunk` is a scalar for a square
    cell, or `(w, h)` -- height-map rooms are much wider than they are tall, so
    a square cell leaves a chunk-height of empty sea above and below every
    island and the bridges spanning it come out twice as long as the
    side-to-side ones."""
    cw, ch = chunk if isinstance(chunk, tuple) else (chunk, chunk)
    return pygame.Rect(cell[0] * cw, cell[1] * ch, cw, ch)



def _full_cells(w: int, h: int) -> frozenset:
    return frozenset((cx, cy) for cx in range(w) for cy in range(h))


def _four_connected(cells: set) -> bool:
    if not cells:
        return False
    start = next(iter(cells))
    seen = {start}
    stack = [start]
    while stack:
        cx, cy = stack.pop()
        for dx, dy in _DIRS:
            nb = (cx + dx, cy + dy)
            if nb in cells and nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return len(seen) == len(cells)


