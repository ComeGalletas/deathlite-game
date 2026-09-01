"""Turning a room into an island: its height map, and the per-tile metadata.

Split out of `world/gen/__init__.py`. `_build_room_grids` is the bridge between
the lattice of room rects and `world.gen.height`, which knows how to build one
island; `_grid_tile_meta` is the straight projection of a finished grid into the
`TileMeta` the renderer reads.
"""
from __future__ import annotations

import pygame

from game import config
from world.layout import TileMeta, GROUND, VSTAIR, EWSTAIR, WALKABLE_KINDS
from world.gen import heightmap
from world.gen.height import build_grid
from world.gen.placement import topography_of

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
        spec = topography_of(room)
        # The floor count is now *drawn from the topography's range* rather
        # than being a coin flip between all three floors and one. A volcanic
        # island can come out two-floor, which the old generator had no way to
        # express at all.
        tiers = rng.randint(*spec["tiers"])
        coast = heightmap.coast_shape(spec["coast"])
        want = coast["grid_keep"] * cols * rows
        grid = None
        for margin in range(coast["margin"], -1, -1):
            shape = heightmap.coast_mask(cols, rows, rng, margin,
                                         keep=config.HEIGHTMAP_COAST_KEEP,
                                         shape=coast)
            grid = build_grid(shape, cols, rows, rng, base=0,
                              stairs_per_wall=config.HEIGHTMAP_STAIRS_PER_REGION,
                              lakes=config.HEIGHTMAP_LAKES,
                              lake_size=config.HEIGHTMAP_LAKE_SIZE, top=caps[room.id],
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
