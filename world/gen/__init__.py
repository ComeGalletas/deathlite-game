"""Seeded procedural world generation (spec 5.2 / 5.4).

Authored chunks assembled procedurally, not per-tile noise. The world is a
lattice of chunk cells; rooms occupy single cells and are joined by short
corridors. Generation grows a *tree* from the start cell, so the connectivity
graph is always fully reachable -- "Do not generate unreachable critical rooms"
(spec 5.4).

`generate_world(seed)` is pure: the same seed and the same code produce an
identical `WorldLayout` (spec 8). W1 of journals/world_refactor.md split the
stages into sibling modules; this module keeps only the orchestrator.
"""
from __future__ import annotations

import random

import pygame

from game import config
from world.layout import Corridor, Room, WorldLayout
from world.gen.tuning import _DIRS
from world.gen.rooms import (
    _cell_rect, _room_frac, _full_cells, _carve_room_shapes, _grow_rooms,
)
from world.gen.graph import _assign_floors, _distances, _assign_kinds
from world.gen.links import _connection_lane, _relink_corridors, _split_links
from world.gen.verticality import (
    _plan_ramps, _ramp_steps, _collect_annex, _carve_cliffs, _build_tile_meta,
)
from world.gen.scatter import _scatter_obstacles

__all__ = ["generate_world"]


def generate_world(seed: int, room_count: int | None = None) -> WorldLayout:
    rng = random.Random(seed)
    chunk = config.CHUNK_SIZE
    room_count = room_count or config.WORLD_ROOM_COUNT

    # --- grow a tree of occupied cells ---------------------------
    start_cell = (0, 0)
    occupied: dict[tuple[int, int], int] = {start_cell: 0}
    order = [start_cell]
    edges: list[tuple[int, int]] = []

    while len(occupied) < room_count:
        # frontier: free cells orthogonally adjacent to an occupied cell
        frontier = []
        for cell in order:
            for dx, dy in _DIRS:
                nb = (cell[0] + dx, cell[1] + dy)
                if nb not in occupied:
                    frontier.append((nb, cell))
        if not frontier:
            break
        new_cell, parent = rng.choice(frontier)
        new_id = len(occupied)
        occupied[new_cell] = new_id
        order.append(new_cell)
        edges.append((occupied[parent], new_id))

    # --- build rooms (random floor size within each cell) --------
    # Snapped to config.TILE_PX so the tiled renderer's cell grid covers the
    # room exactly (no clipped autotile edge). Min 3 tiles -> a real interior.
    px = config.TILE_PX
    irregular = config.IRREGULAR_ROOMS
    rooms: list[Room] = []
    for cell in order:
        rid = occupied[cell]
        full = _cell_rect(cell, chunk)
        w = max(3 * px, round(full.width * _room_frac(rng, irregular) / px) * px)
        h = max(3 * px, round(full.height * _room_frac(rng, irregular) / px) * px)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = full.center
        rooms.append(Room(rid, cell, rect, "combat"))

    for a, b in edges:
        rooms[a].neighbors.append(b)
        rooms[b].neighbors.append(a)

    # --- corridors along each tree edge -----------------------
    # One tile wide -- rendered as a plank bridge over the water (terrain T7).
    # Each corridor records which edge is which (west/east or north/south) so the
    # renderer draws the matching end-cap tile at each mouth.
    corridors: list[Corridor] = []
    width = px
    for a, b in edges:
        ra, rb = rooms[a].rect, rooms[b].rect
        if rooms[a].cell[0] == rooms[b].cell[0]:           # vertical neighbour
            (lo, lo_r), (hi, hi_r) = sorted(
                ((a, ra), (b, rb)), key=lambda t: t[1].centery)
            axis, e_lo, e_hi = "v", "north", "south"
            lane = _connection_lane(seed, a, b, axis, lo_r, hi_r, px)
            rect = pygame.Rect(lane - width // 2, lo_r.centery,
                               width, hi_r.centery - lo_r.centery)
        else:                                              # horizontal neighbour
            (lo, lo_r), (hi, hi_r) = sorted(
                ((a, ra), (b, rb)), key=lambda t: t[1].centerx)
            axis, e_lo, e_hi = "h", "west", "east"
            lane = _connection_lane(seed, a, b, axis, lo_r, hi_r, px)
            rect = pygame.Rect(lo_r.centerx, lane - width // 2,
                               hi_r.centerx - lo_r.centerx, width)
        corridors.append(Corridor(a, b, rect, axis, e_lo, e_hi, lo, hi, lane))

    # --- assign roles ------------------------------------------
    start_id = 0
    dist = _distances(rooms, start_id)
    boss_id = max(dist, key=dist.get)
    _assign_kinds(rooms, rng, start_id, boss_id, dist)

    # --- room floor shape (tile masks) -----------------------
    # Plain rectangle by default. `IRREGULAR_ROOMS`: some combat rooms first grow
    # a block into one empty neighbour chunk (W5), then every combat room may get
    # 2-3-cell corner bites (L / T / plus / stepped).
    if irregular:
        grew = _grow_rooms(rooms, corridors, occupied, rng, start_id, boss_id)
        _carve_room_shapes(rooms, rng, start_id, boss_id)
        if grew:
            _relink_corridors(rooms, corridors)
    else:
        for room in rooms:
            room.cells = _full_cells(*room.tile_dims)

    # --- LD-1 verticality: floors, stairs, cliff-band carve ------
    # Fully gated: with WORLD_VERTICALITY off, `stairs` stays empty, every room
    # keeps floor 0, and the layout is byte-identical.
    stairs: list = []
    plan: list = []
    if config.WORLD_VERTICALITY:
        _assign_floors(rooms, edges, rng, start_id, boss_id)
        # Cross-floor links become stairs/ramp units below. Keep their approach
        # on the shared-span centre used by the established vertical navigation;
        # only same-floor plank corridors use the varied entrance lanes.
        for c in corridors:
            if rooms[c.a].floor == rooms[c.b].floor:
                continue
            first, second = rooms[c.a].rect, rooms[c.b].rect
            if c.axis == "h":
                c.lane = (max(first.top, second.top) +
                          min(first.bottom, second.bottom)) // 2
            else:
                c.lane = (max(first.left, second.left) +
                          min(first.right, second.right)) // 2
        _relink_corridors(rooms, corridors)
        # LD-3 R1: bring usable cross-floor pairs into contact *before* the
        # links are cut, so `_split_links` sees the snapped geometry and can
        # skip the edges a ramp run now carries.
        plan = _plan_ramps(rooms, edges, corridors) if config.RAMP_STAIRS else []
        ramped = {frozenset((hi, lo)) for hi, lo, *_ in plan}
        stairs = _split_links(rooms, corridors, rng, ramped)
        stairs += _ramp_steps(rooms, plan)
        _collect_annex(rooms, plan)
        if config.CLIFF_CARVE:
            _carve_cliffs(rooms, corridors, stairs)

    # --- bounds (union of everything + margin) ---------------
    union = rooms[0].rect.copy()
    for r in rooms:
        union.union_ip(r.rect)
    for c in corridors:
        union.union_ip(c.rect)
    for s in stairs:
        union.union_ip(s.rect)
    union.inflate_ip(chunk, chunk)

    # Shift the whole world so bounds start at (0, 0) -- keeps camera clamp simple.
    shift = pygame.Vector2(-union.x, -union.y)
    for r in rooms:
        r.rect.move_ip(shift)
    for c in corridors:
        c.rect.move_ip(shift)
        c.lane += shift.y if c.axis == "h" else shift.x
    for s in stairs:
        s.rect.move_ip(shift)
    union.move_ip(shift)

    # Scatter obstacles last, in the final (0,0)-based coordinate space, so the
    # corridor-doorway keep-clear rects match the world the game sees.
    obstacles = _scatter_obstacles(rooms, corridors, rng, start_id, boss_id,
                                   stairs=stairs)

    # LD-2 E0: per-tile classification. Reads only finalised geometry, draws no
    # RNG, so a flag-off world stays byte-identical. Built unconditionally -- a
    # flat world just gets `floor 0 / foam True` everywhere.
    _build_tile_meta(rooms, plan)

    return WorldLayout(seed, rooms, corridors, union, start_id, boss_id,
                       obstacles, stairs)
