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
from world.gen.graph import _assign_floors, _distances, _assign_kinds
from world.gen.links import _connection_lane, _relink_corridors, _split_links
from world.gen.verticality import (
    _plan_ramps, _ramp_steps, _collect_annex, _carve_cliffs, _build_tile_meta,
)
from world.gen import heightmap
from world.gen.heightmap import build_grid
from world.gen.scatter import _scatter_obstacles

__all__ = ["generate_world"]


def generate_world(seed: int, room_count: int | None = None) -> WorldLayout:
    rng = random.Random(seed)
    # LD-9: a height-map room carries several terraces and the walls between
    # them, so it needs far more room than a flat one -- fewer, larger rooms in
    # bigger chunks.
    heightmap = config.HEIGHTMAP_ROOMS
    chunk = config.HEIGHTMAP_CHUNK_SIZE if heightmap else config.CHUNK_SIZE
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
        _seat_corridors(rooms, corridors)
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
    if heightmap:
        _grid_tile_meta(rooms)
    else:
        _build_tile_meta(rooms, plan)

    return WorldLayout(seed, rooms, corridors, union, start_id, boss_id,
                       obstacles, stairs)


def _build_room_grids(rooms, corridors, rng) -> None:
    """LD-9: give every room a height map, then re-derive the fields the rest
    of the engine reads from it -- `cells` is the walkable subset (so collision
    and the nav grid need no changes) and `floor` collapses to the room's base
    level, which is all the palette lookup still wants.

    Cliffs in this tileset only face south, so a room's terraces have to
    descend northward: its south edge is the base level and its north edge is
    the highest one. A bridge dropping onto a room's north edge therefore meets
    that room at its summit, so any room a bridge enters from the north has its
    summit capped -- the standing "never more than two levels between connected
    areas" rule, applied across open water."""
    caps = {room.id: heightmap.MAX_LEVEL for room in rooms}
    for c in corridors:
        if c.axis != "v":
            continue
        south = max((c.a, c.b), key=lambda rid: rooms[rid].rect.centery)
        caps[south] = min(caps[south], heightmap.MAX_DROP)
    for room in rooms:
        cols, rows = room.tile_dims
        # The tree's corner-bite shapes are replaced by a coastline: a jittered
        # inset on all four sides, so the terraces no longer all begin and end
        # in the same column and the island stops reading as a stack of bars.
        # Every stage after the coastline erodes further -- the shore ring, the
        # lakes, then pruning whatever ended up walled off. Judge the finished
        # grid, not the mask, and back the coast off until the island is worth
        # calling one; an islet of a dozen tiles carries no terraces and leaves
        # its bridges running to almost nothing.
        # Not every island is a mountain. A plain one-level island is a room in
        # its own right, and it connects to its neighbours with no elevation to
        # reconcile at all.
        tiers = (config.HEIGHTMAP_TIERS
                 if rng.random() < config.HEIGHTMAP_VOLCANO_CHANCE else 0)
        want = 0.35 * cols * rows
        grid = None
        for margin in range(config.HEIGHTMAP_COAST_MARGIN, -1, -1):
            shape = heightmap.coast_mask(cols, rows, rng, margin)
            grid = build_grid(shape, cols, rows, rng, base=0,
                              stairs_per_wall=config.HEIGHTMAP_STAIRS_PER_REGION,
                              lakes=config.HEIGHTMAP_LAKES, top=caps[room.id],
                              shore=config.HEIGHTMAP_SHORE_RING, tiers=tiers,
                              cap_inset=(config.HEIGHTMAP_CAP_INSET_S,
                                         config.HEIGHTMAP_CAP_INSET_N,
                                         config.HEIGHTMAP_CAP_INSET_W,
                                         config.HEIGHTMAP_CAP_INSET_E),
                              cap_roughness=config.HEIGHTMAP_CAP_ROUGHNESS,
                              cap_min_cells=config.HEIGHTMAP_CAP_MIN_CELLS,
                              region=config.HEIGHTMAP_STAIR_REGION,
                              spacing=config.HEIGHTMAP_STAIR_SPACING,
                              canyons=config.HEIGHTMAP_CANYONS,
                              canyon_depth=config.HEIGHTMAP_CANYON_DEPTH,
                              canyon_width=config.HEIGHTMAP_CANYON_WIDTH)
            if sum(1 for c in grid.values()
                   if c.kind in WALKABLE_KINDS) >= want:
                break
        room.grid = grid
        room.cells = frozenset(p for p, cell in grid.items()
                               if cell.kind in WALKABLE_KINDS)
        room.floor = min((cell.level for cell in grid.values()
                          if cell.kind == GROUND), default=0)


def _seat_corridors(rooms, corridors) -> None:
    """Slide each bridge along the rooms' shared edge until both of its mouths
    land on walkable ground, preferring a lane where the two ends are at the
    same level so the planks read as flat, then stretch it to actually reach
    that ground.

    Two things changed under these bridges. A height-map room's edge is no
    longer uniform floor -- it may be cliff, or lake, or a terrace met
    side-on -- so the lane the tree picked before the grids existed has to be
    re-seated. And the coastline now wanders *inside* the room's rect, so a
    bridge drawn between the two rects stops short and hangs over open water;
    it has to span coast to coast instead."""
    px = config.TILE_PX

    def reach(room, axis, fixed, along, step, limit, strict=True):
        """The cell a bridge may land on along one line, scanning in from the
        rect edge, as `(index, cell)` -- or `(None, None)`.

        A bridge belongs on the beach. Taking the *first* land the scan reaches
        keeps it on the outer shore rather than striking inland, and it must be
        plain ground so it never meets the middle of a flight. `strict` also
        demands sea level, so the planks do not run up onto a terrace or stop
        on a cliff top; the caller drops that only when no lane at all offers a
        beach on both sides, since a bridge onto raised ground still beats one
        left hanging over the water."""
        for i in range(limit):
            idx = along + step * i
            # Grid keys are `(col, row)`. A horizontal bridge holds the row and
            # scans columns, a vertical one the reverse -- get this the wrong
            # way round and the scan silently reads a transposed cell, which is
            # how horizontal bridges ended up starting in open water.
            pos = (idx, fixed) if axis == "h" else (fixed, idx)
            cell = room.grid.get(pos)
            if cell is None:
                continue
            if cell.kind != GROUND:
                return None, None       # first land is a flight or a wall
            if strict and cell.level != 0:
                return None, None       # ... or a terrace: no beach on this line
            return idx, cell
        return None, None

    for c in corridors:
        a, b = rooms[c.a], rooms[c.b]
        if c.axis == "h":
            west, east = (a, b) if a.rect.centerx < b.rect.centerx else (b, a)
            wcols, _ = west.tile_dims
            ecols, _ = east.tile_dims
            # Any lane where both islands offer a beach will do -- scan the
            # whole span either room reaches, not just where the two rects
            # happen to overlap.
            lo = min(west.rect.top, east.rect.top) + px // 2
            hi = max(west.rect.bottom, east.rect.bottom) - px // 2
            # Bridges meet **sea level only**. The island always keeps a
            # walkable shore right round it, so a mouth is always there to be
            # found, and no bridge ever has to reconcile a height difference.
            best = None
            for strict in (True,):
                for y in range(lo, hi + 1, px):
                    wi, wc = reach(west, "h", (y - west.rect.top) // px,
                                   wcols - 1, -1, wcols, strict)
                    ei, ec = reach(east, "h", (y - east.rect.top) // px, 0, 1,
                                   ecols, strict)
                    if wc is None or ec is None:
                        continue
                    # prefer the shortest crossing of the ones that work
                    span = (east.rect.x + ei * px) - (west.rect.x + wi * px)
                    if best is None or span < best[0]:
                        best = (span, y, wi, ei)
                if best is not None:
                    break
            if best is not None:
                _s, c.lane, wi, ei = best
                # The end caps sit *on* the ground tile they meet, so the
                # planks land square on it rather than stopping beside it.
                x0 = west.rect.x + wi * px
                x1 = east.rect.x + (ei + 1) * px
                c.rect = pygame.Rect(x0, c.lane - px // 2, x1 - x0, px)
        else:
            north, south = (a, b) if a.rect.centery < b.rect.centery else (b, a)
            _, nrows = north.tile_dims
            _, srows = south.tile_dims
            lo = min(north.rect.left, south.rect.left) + px // 2
            hi = max(north.rect.right, south.rect.right) - px // 2
            best = None
            for strict in (True,):
                for x in range(lo, hi + 1, px):
                    ni, nc = reach(north, "v", (x - north.rect.left) // px,
                                   nrows - 1, -1, nrows, strict)
                    si, sc = reach(south, "v", (x - south.rect.left) // px, 0, 1,
                                   srows, strict)
                    if nc is None or sc is None:
                        continue
                    span = (south.rect.y + si * px) - (north.rect.y + ni * px)
                    if best is None or span < best[0]:
                        best = (span, x, ni, si)
                if best is not None:
                    break
            if best is not None:
                _s, c.lane, ni, si = best
                y0 = north.rect.y + ni * px
                y1 = south.rect.y + (si + 1) * px
                c.rect = pygame.Rect(c.lane - px // 2, y0, px, y1 - y0)


def _grid_tile_meta(rooms) -> None:
    """`TileMeta` for every walkable cell of a height-map room.

    The grid already knows each cell's level, so this is a straight projection
    -- no rim/lip derivation, which is the whole point of LD-9. Only sea-level
    ground can carry shoreline foam; a terrace's edge is a cliff, not a beach."""
    for room in rooms:
        meta = {}
        for pos, cell in room.grid.items():
            if cell.kind not in WALKABLE_KINDS:
                continue
            meta[pos] = TileMeta(floor=cell.level, surface="room",
                                 foam=(cell.level == 0), room_id=room.id,
                                 ramp=("s" if cell.kind == VSTAIR
                                       else cell.tag if cell.kind == EWSTAIR
                                       else ""))
        room.tile_meta = meta
