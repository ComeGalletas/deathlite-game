"""Seeded world generation.

The world is a lattice of chunk cells grown as a tree from the start cell,
so every island is reachable by construction. Each cell holds one island:
a height map of terraces, walls and flights (`world/gen/height/`), seated
bridges on its beaches (`bridges.py`), a palette per terrace (`biomes.py`),
and obstacles scattered last, in final coordinates (`scatter.py`).

`generate_world(seed)` is pure: one seed, one `WorldLayout`, with no asset
loaded and no display. All randomness comes from one `random.Random(seed)`
stream, except where a stage says it keys its own RNG by seed and room so
that it draws nothing from the world's. The order of the stages below is
the order that stream is consumed in; moving one moves every world.

The knobs come from one `GenSettings` (`settings.py`), snapshotted from
`game.config` at the top and handed to every stage that reads one, so a
world is generated under one setting throughout and a test can pass its
own instead of mutating the global.

This module is the pipeline. Each stage lives beside it.
"""
from __future__ import annotations

import random

import pygame

from game import config
from world.layout import Corridor, Room, WorldLayout
from world.gen.tuning import _DIRS
from world.gen.rooms import _cell_rect, _full_cells
from world.gen.graph import assign_topography, _distances, _assign_kinds
from world.gen.links import _connection_lane
from world.gen.repair import unseal
from world.gen.bridges import _seat_corridors
from world.gen.islands import (_build_room_grids, _grid_tile_meta,
                               _build_inset_fields)
from world.gen.placement import _resize_by_topography, _offset_in_chunk
from world.gen.biomes import assign_palettes
from world.gen.scatter import _scatter_obstacles
from world.gen.settings import GenSettings, settings_or_config

__all__ = ["generate_world"]


def generate_world(seed: int, room_count: int | None = None,
                   settings: GenSettings | None = None) -> WorldLayout:
    settings = settings_or_config(settings)
    rng = random.Random(seed)
    px = config.TILE_PX
    # An island carries several terraces and the walls between them, so the
    # lattice cell is large and there are few of them.
    chunk = (settings.chunk_cols * px, settings.chunk_rows * px)
    room_count = room_count or settings.room_count

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

    # --- one island rect per cell --------------------------------
    # Tile-sized, and snapped to the *world* tile lattice, not merely centred
    # in the chunk: centring a room of odd tile-width leaves it half a tile
    # off the grid, and then no two rooms share one. A bridge between them
    # could never sit squarely on a tile at both ends -- its end caps landed
    # mid-tile and the planks read crooked.
    rooms: list[Room] = []
    for cell in order:
        rid = occupied[cell]
        full = _cell_rect(cell, chunk)
        w = rng.randint(*settings.room_cols) * px
        h = rng.randint(*settings.room_rows) * px
        rect = pygame.Rect(0, 0, w, h)
        rect.center = full.center
        rect.x = round(rect.x / px) * px
        rect.y = round(rect.y / px) * px
        rooms.append(Room(rid, cell, rect, "combat"))

    for a, b in edges:
        rooms[a].neighbors.append(b)
        rooms[b].neighbors.append(a)

    # --- one bridge per tree edge --------------------------------
    # One tile wide, rendered as a plank bridge over the water. Each records
    # which edge is which (west/east or north/south) so the renderer draws
    # the matching end-cap tile at each mouth. One per link *here*, always:
    # how many a link actually carries is a property of the two islands, and
    # neither their topography nor their shape exists yet. `_seat_corridors`
    # clones them once both are known and it can see where the beaches are.
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
        corridors.append(Corridor(a, b, rect.copy(), axis,
                                  e_lo, e_hi, lo, hi, lane))

    # --- roles, then shape ---------------------------------------
    # Kind says what happens on an island; topography says what shape it is.
    # Shape type, then resize to match it, then slide each island within its
    # chunk -- all before the grids are built, because every later stage (the
    # coastline, the terrace count, the tile mask) reads one or the other.
    start_id = 0
    dist = _distances(rooms, start_id)
    boss_id = max(dist, key=dist.get)
    _assign_kinds(rooms, rng, start_id, boss_id, dist)
    assign_topography(rooms, rng, boss_id, settings)
    _resize_by_topography(rooms, settings)
    _offset_in_chunk(rooms, chunk, rng)

    # --- height maps ---------------------------------------------
    # The coastline in `_build_room_grids` overwrites `cells` wholesale; the
    # full rectangle is only the starting mask. Then the bridges are seated on
    # the beaches, each terrace picks its tileset (generation decides, not the
    # bake: the scatter reads the biome too, and one authority is the point),
    # and the terrace inset field is built once, here, before anything is
    # baked, scattered or spawned, so every later stage asks one answer for
    # how far inside its own terrace a point stands.
    for room in rooms:
        room.cells = _full_cells(*room.tile_dims)
    _build_room_grids(rooms, corridors, rng, settings)
    corridors = _seat_corridors(rooms, corridors, seed, settings)
    assign_palettes(rooms, seed, settings)
    _build_inset_fields(rooms)

    # --- bounds (union of everything + margin) ---------------
    union = rooms[0].rect.copy()
    for r in rooms:
        union.union_ip(r.rect)
    for c in corridors:
        union.union_ip(c.rect)
    cw, ch = chunk
    union.inflate_ip(cw, ch)

    # Shift the whole world so bounds start at (0, 0) -- keeps camera clamp simple.
    shift = pygame.Vector2(-union.x, -union.y)
    for r in rooms:
        r.rect.move_ip(shift)
    for c in corridors:
        c.rect.move_ip(shift)
        c.lane += shift.y if c.axis == "h" else shift.x
    union.move_ip(shift)

    # Scatter obstacles last, in the final (0,0)-based coordinate space, so the
    # bridge-mouth keep-clear rects match the world the game sees.
    obstacles = _scatter_obstacles(rooms, corridors, rng, start_id, boss_id,
                                   settings)

    # Per-tile classification, a straight projection of the finished grids.
    # Reads only finalised geometry and draws no RNG.
    _grid_tile_meta(rooms)

    layout = WorldLayout(seed, rooms, corridors, union, start_id, boss_id,
                         obstacles)
    # The keep-clear rectangles protect the chokes we knew about. This checks
    # the one that matters -- can the widest body still reach everywhere bare
    # terrain allows -- and takes back the few obstacles that say no. See
    # `world/gen/repair.py`.
    if settings.unseal:
        unseal(layout)
    return layout
