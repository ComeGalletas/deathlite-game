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
from world.layout import (
    Corridor, Room, TileMeta, WorldLayout,
    GROUND, VSTAIR, EWSTAIR, WALKABLE_KINDS,
)
from world.gen.tuning import _DIRS
from world.gen.rooms import (
    _cell_rect, _room_frac, _full_cells, _carve_room_shapes, _grow_rooms,
)
from world.gen.graph import assign_topography, _assign_floors, _distances, _assign_kinds
from world.gen.links import _connection_lane, _relink_corridors, _split_links
from world.legacy.verticality import (
    _plan_ramps, _ramp_steps, _collect_annex, _carve_cliffs, _build_tile_meta,
)
from world.gen import heightmap
from world.gen.heightmap import build_grid
from world.gen.repair import unseal
from world.gen.bridges import _seat_corridors
from world.gen.islands import _build_room_grids, _grid_tile_meta
from world.gen.placement import (
    topography_of, _resize_by_topography, _offset_in_chunk,
)
from world.gen.biomes import assign_palettes
from world.gen.scatter import _scatter_obstacles

__all__ = ["generate_world"]


def generate_world(seed: int, room_count: int | None = None) -> WorldLayout:
    rng = random.Random(seed)
    # LD-9: a height-map room carries several terraces and the walls between
    # them, so it needs far more room than a flat one -- fewer, larger rooms in
    # bigger chunks.
    heightmap = config.HEIGHTMAP_ROOMS
    chunk = ((config.HEIGHTMAP_CHUNK_COLS * config.TILE_PX,
              config.HEIGHTMAP_CHUNK_ROWS * config.TILE_PX) if heightmap
             else config.CHUNK_SIZE)
    room_count = room_count or (config.HEIGHTMAP_ROOM_COUNT if heightmap
                                else config.WORLD_ROOM_COUNT)

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
        if heightmap:
            w = rng.randint(*config.HEIGHTMAP_ROOM_COLS) * px
            h = rng.randint(*config.HEIGHTMAP_ROOM_ROWS) * px
        else:
            w = max(3 * px,
                    round(full.width * _room_frac(rng, irregular) / px) * px)
            h = max(3 * px,
                    round(full.height * _room_frac(rng, irregular) / px) * px)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = full.center
        if heightmap:
            # Centring a room of odd tile-width in its chunk leaves it half a
            # tile off the world grid, and then no two rooms share one. A
            # bridge between them can never sit squarely on a tile at both
            # ends -- its end caps land mid-tile and the planks read crooked.
            # Snap every room to the global grid so they all agree.
            rect.x = round(rect.x / px) * px
            rect.y = round(rect.y / px) * px
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
        # LD-9: a link may carry more than one bridge. They are created here as
        # copies on the tree's own lane and then spread out by `_seat_corridors`,
        # which is the only place that knows where each island's beaches
        # actually are. One is the legacy behaviour and leaves the flag-off
        # world byte-identical.
        # LD-10: one per link here, always. How many a link actually carries is
        # a property of the two islands, and neither their topography nor their
        # shape exists yet at this point -- `_seat_corridors` clones them once
        # both are known and it can see where the beaches are.
        corridors.append(Corridor(a, b, rect.copy(), axis,
                                  e_lo, e_hi, lo, hi, lane))

    # --- assign roles ------------------------------------------
    start_id = 0
    dist = _distances(rooms, start_id)
    boss_id = max(dist, key=dist.get)
    _assign_kinds(rooms, rng, start_id, boss_id, dist)
    # LD-10: shape type, then resize to match it. Both have to happen before the
    # cells are filled in below and long before the grids are built, because
    # every later stage -- the coastline, the terrace count, the tile mask --
    # reads one or the other.
    assign_topography(rooms, rng, boss_id)
    _resize_by_topography(rooms)
    _offset_in_chunk(rooms, chunk, rng)

    # --- room floor shape (tile masks) -----------------------
    # Plain rectangle by default. `IRREGULAR_ROOMS`: some combat rooms first grow
    # a block into one empty neighbour chunk (W5), then every combat room may get
    # 2-3-cell corner bites (L / T / plus / stepped).
    if heightmap:
        # LD-9 supplies its own outline -- the coastline in `_build_room_grids`
        # overwrites `cells` wholesale, so the corner-bite pass has nothing to
        # contribute. Skipping the growth pass also matters: it moves a room's
        # rect off the world tile grid, and then a bridge cannot land square on
        # a tile at both ends.
        for room in rooms:
            room.cells = _full_cells(*room.tile_dims)
    elif irregular:
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
    if heightmap:
        # LD-9: every room becomes a height map -- its own terraces, the walls
        # between them and the flights cut through those walls. Cross-room
        # links stay plank corridors for now (LD-9 B2 matches their levels).
        _build_room_grids(rooms, corridors, rng)
        corridors = _seat_corridors(rooms, corridors, seed)
        # LD-10: which tileset each terrace wears. Generation decides it, not
        # the bake -- the scatter below picks its obstacle mix from the biome,
        # so the world and the tile painter have to read one answer. Keyed by
        # seed and room id, so it draws nothing from `rng`.
        assign_palettes(rooms, seed)
    elif config.WORLD_VERTICALITY:
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
        plan = (_plan_ramps(rooms, edges, corridors, seed)
                if config.RAMP_STAIRS else [])
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
    cw, ch = chunk if isinstance(chunk, tuple) else (chunk, chunk)
    union.inflate_ip(cw, ch)

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
    if heightmap:
        _grid_tile_meta(rooms)
    else:
        _build_tile_meta(rooms, plan)

    layout = WorldLayout(seed, rooms, corridors, union, start_id, boss_id,
                         obstacles, stairs)
    # LD-9: the keep-clear rectangles above protect the chokes we knew about.
    # This checks the one that matters -- can the widest body still reach
    # everywhere bare terrain allows -- and takes back the few obstacles that
    # say no. See `world/gen/repair.py`. Height-map worlds only: that is where
    # the seals were measured, and the legacy generator is pinned seed by seed
    # in the tests that describe it.
    if heightmap and config.HEIGHTMAP_UNSEAL:
        unseal(layout)
    return layout
