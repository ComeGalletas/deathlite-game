"""Room-shape carving and multi-chunk growth (W1 split of world/procedural.py)."""
from __future__ import annotations

import random

import pygame

from game import config
from world.layout import Room
from world.gen.tuning import (
    SPECIAL_KINDS, _DIRS, _SIZE_FRAC, _BIG_ROOM_FRAC, _BIG_ROOM_CHANCE,
    _LEGACY_SIZE_FRAC, _NOTCH_MIN, _NOTCH_MAX, _MIN_ROOM_CELLS,
    _MULTICHUNK_ROOM_CHANCE, _GROW_TILES,
)


def _cell_rect(cell: tuple[int, int], chunk) -> pygame.Rect:
    """The lattice cell a room is placed in. `chunk` is a scalar for a square
    cell, or `(w, h)` -- height-map rooms are much wider than they are tall, so
    a square cell leaves a chunk-height of empty sea above and below every
    island and the bridges spanning it come out twice as long as the
    side-to-side ones."""
    cw, ch = chunk if isinstance(chunk, tuple) else (chunk, chunk)
    return pygame.Rect(cell[0] * cw, cell[1] * ch, cw, ch)


def _room_frac(rng: random.Random, irregular: bool) -> float:
    if not irregular:
        return rng.uniform(*_LEGACY_SIZE_FRAC)
    band = _BIG_ROOM_FRAC if rng.random() < _BIG_ROOM_CHANCE else _SIZE_FRAC
    return rng.uniform(*band)


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


def _borders_intact(cells: set, w: int, h: int) -> bool:
    """Every border row / column still has a cell -- so the room's bounding box
    (which the renderer + corridors use) does not shrink."""
    return (any(c[0] == 0 for c in cells) and any(c[0] == w - 1 for c in cells)
            and any(c[1] == 0 for c in cells) and any(c[1] == h - 1 for c in cells))


def _try_one_notch(cells: set, w: int, h: int, rng: random.Random) -> None:
    """Remove one 2-3-cell block from a random corner, in place, if it keeps the
    room 4-connected, above the min size, and with its bounding box intact.
    Always draws the same 3 rng values so generation stays deterministic."""
    nw = min(rng.randint(_NOTCH_MIN, _NOTCH_MAX), w // 2 - 1)
    nh = min(rng.randint(_NOTCH_MIN, _NOTCH_MAX), h // 2 - 1)
    corner_x, corner_y = rng.choice(((0, 0), (1, 0), (0, 1), (1, 1)))
    if nw < _NOTCH_MIN or nh < _NOTCH_MIN:
        return
    xs = range(nw) if corner_x == 0 else range(w - nw, w)
    ys = range(nh) if corner_y == 0 else range(h - nh, h)
    trial = cells - {(x, y) for x in xs for y in ys}
    if (len(trial) >= _MIN_ROOM_CELLS and _borders_intact(trial, w, h)
            and _four_connected(trial)):
        cells.clear()
        cells.update(trial)


def _carve_room_shapes(rooms: list[Room], rng: random.Random,
                       start_id: int, boss_id: int) -> None:
    """Bite corner blocks out of each room's cell mask. `start` / `boss` stay
    rectangular arenas; special rooms get at most one bite; combat rooms 1-3.
    Corners only (never edge midpoints) with a centre-line clearance, so a
    corridor -- which always attaches at an edge midpoint -- is never blocked."""
    for room in rooms:
        w, h = room.tile_dims
        cells = set(_full_cells(w, h))
        if room.id in (start_id, boss_id) or w < 6 or h < 6:
            room.cells = frozenset(cells)
            continue
        n = rng.randint(0, 1) if room.kind in SPECIAL_KINDS else rng.randint(1, 3)
        for _ in range(n):
            _try_one_notch(cells, w, h, rng)
        room.cells = frozenset(cells)


def _grow_rooms(rooms, corridors, occupied, rng, start_id, boss_id) -> bool:
    """W5: a combat room may extend a tile-aligned, full-width/height block into
    one **empty** adjacent chunk cell, making a large 2-chunk arena. Skips any
    growth that would overlap another room or a corridor, or push past
    `config.ROOM_SIZE_MAX_CELLS`. Runs before `_carve_room_shapes`, so the corner
    bites then apply to the grown shape. Returns whether any room grew."""
    px = config.TILE_PX
    chunk = config.CHUNK_SIZE
    grew = False
    for room in rooms:
        if room.id in (start_id, boss_id) or room.kind in SPECIAL_KINDS:
            continue
        if rng.random() >= _MULTICHUNK_ROOM_CHANCE:
            continue
        cx, cy = room.cell
        empties = [d for d in _DIRS if (cx + d[0], cy + d[1]) not in occupied]
        if not empties:
            continue
        dx, dy = rng.choice(sorted(empties))
        w, h = room.tile_dims
        depth = rng.randint(*_GROW_TILES)
        span = h if dx else w
        while depth >= 2 and len(room.cells) + depth * span > config.ROOM_SIZE_MAX_CELLS:
            depth -= 1
        if depth < 2:
            continue
        r = room.rect
        block = {
            (-1, 0): pygame.Rect(r.left - depth * px, r.top, depth * px, r.height),
            (1, 0): pygame.Rect(r.right, r.top, depth * px, r.height),
            (0, -1): pygame.Rect(r.left, r.top - depth * px, r.width, depth * px),
            (0, 1): pygame.Rect(r.left, r.bottom, r.width, depth * px),
        }[(dx, dy)]
        # must stay within the home chunk + the one target empty chunk
        reach = _cell_rect(room.cell, chunk).union(
            _cell_rect((cx + dx, cy + dy), chunk)).inflate(px, px)
        if not reach.contains(block):
            continue
        if any(block.colliderect(o.rect) for o in rooms if o is not room):
            continue
        if any(block.colliderect(c.rect) for c in corridors):
            continue

        room.rect = r.union(block)
        off_c = (r.left - room.rect.left) // px       # 0, or `depth` if grew west
        off_r = (r.top - room.rect.top) // px         # 0, or `depth` if grew north
        merged = {(c[0] + off_c, c[1] + off_r) for c in room.cells}
        bx = (block.left - room.rect.left) // px
        by = (block.top - room.rect.top) // px
        for bc in range(block.width // px):
            for br in range(block.height // px):
                merged.add((bx + bc, by + br))
        room.cells = frozenset(merged)
        grew = True
    return grew
