"""Baking the world into surfaces: the one-off pass that turns a layout into art.

Split out of `world/map.py`, which was doing three unrelated jobs -- the
collision surface the game queries every frame, this bake, and a stack of
forwarders to the renderer. `GameMap._build_tiles` is now the entry point and
this is the body; the map stays what everything actually uses it for.

Runs once, lazily, on the first draw (it needs a display). Everything it builds
hangs off the `GameMap` instance, which is passed in as `gm` rather than being
`self` -- the same shape the painters in this package already take.
"""
from __future__ import annotations

import pygame

from game import config
from game.assets import get_assets
from world.layout import GROUND, VSTAIR, EWSTAIR, WALKABLE_KINDS
from world.terrain import autotile, decor as terrain_decor, grid_paint
from world.terrain.sheets import TileSheets
from world.legacy import terrain_cliffs, terrain_rooms


def bake(gm) -> None:
    gm._tiles_ready = True
    if gm.layout is None:
        return
    layout = gm.layout
    a = get_assets()
    t = a.terrain
    sheets = TileSheets(a, layout.seed)
    if not sheets.ok:
        return                                   # tileset missing -> flat fallback
    gm._sheets = sheets

    # W2/W4 (journals/world_refactor.md): the tileset adapter + tile cache
    # are `sheets` now; the room / corridor / cliff / stair painters live in
    # world/terrain/. `_build_tiles` only sequences them and still owns the
    # LD-7a cliff-cap pass, the shore filter, and the water / foam / decor
    # buffers below.
    px = sheets.px

    # LD-7a: ground-room edge cells that sit directly under a raised room's
    # cliff band. Their north side is stone, not open sea -- so `paint_room`
    # closes that side (interior tile, no shoreline autotile) and seeds no
    # foam there. Paired with the `_cliff_underlay` tile at the cliff foot
    # cell itself, this reads as the lower room extending one tile up under
    # the cliff. Only a cliff *flush* above the cell counts; a real gap
    # keeps its shoreline.
    band_rects = []
    for R in layout.rooms:
        if R.floor <= 0:
            continue
        fh = max(1, R.floor * int(config.CLIFF_TILES))
        for (bc, bro), bm in R.tile_meta.items():
            if bm.cliff == "top":
                band_rects.append(pygame.Rect(
                    R.rect.x + bc * px, R.rect.y + (bro + 1) * px,
                    px, fh * px))
    cliff_capped: set = set()
    if band_rects:
        for r in layout.rooms:
            if r.floor != 0:
                continue
            for (col, row) in r.cells:
                if (col, row - 1) in r.cells:
                    continue
                strip = pygame.Rect(r.rect.x + col * px + 4,
                                    r.rect.y + row * px - px // 2,
                                    px - 8, px)
                if any(strip.colliderect(b) for b in band_rects):
                    cliff_capped.add((r.id, col, row))
    gm._cliff_capped = cliff_capped

    if config.HEIGHTMAP_ROOMS:
        # LD-9 Phase C: one pass per room, straight off its height map.
        # Nothing else to stitch -- no separate cliff band, underlay,
        # drop shadow or ramp collection, because the grid already says
        # what every cell is. Falls through to the shared water / foam /
        # scenery setup below.
        gm._shore = []
        for r in layout.rooms:
            # One surface per terrace, not one per island. The third element is
            # the terrace's own level now (it used to be `r.floor`, which is a
            # height-map room's *base* and therefore always 0), and the renderer
            # composites the world band by band so sprites can sit between them.
            for blit, surf, level in grid_paint.paint_room_levels(
                    gm, sheets, layout, r):
                gm._grid_surfs.append((blit, surf, level))
            gm._shore.extend(grid_paint.grid_shore(r))
        for c in layout.corridors:
            rc = grid_paint.paint_bridge(sheets, c)
            gm._corr_surfs.append((rc[0], rc[1], layout.room(c.a).floor))
        _finish(gm, a, sheets)
        return

    for r in layout.rooms:
        gm._room_surfs[r.id] = terrain_rooms.paint_room(
            gm, sheets, layout, r)
    for c in layout.corridors:
        rc = terrain_rooms.paint_corridor(sheets, layout, c)
        gm._corr_surfs.append((rc[0], rc[1], layout.room(c.a).floor))
    for r in layout.rooms:
        if r.floor > 0:
            cl = terrain_cliffs.paint_cliff(gm, sheets, layout, r)
            if cl is not None:
                gm._cliff_surfs.append(cl)
    for st in layout.stairs:
        # LD-3: a ramp step is drawn by `paint_cliff` as part of the run.
        # It is a `Stair` only so collision and nav pick it up for free --
        # baking a plain grass strip here would cover the slope.
        if st.ramp:
            continue
        sc = terrain_cliffs.paint_stair(sheets, layout, st)
        gm._stair_surfs.append((sc[0], sc[1], layout.room(st.high_room).floor))

    # Keep every ground-room edge which still faces sea after all corridors,
    # stairs, and cliff geometry are known. Corridors render over this foam
    # but never create or suppress anchors of their own.
    gm._shore = list(dict.fromkeys(
        (sx, sy) for sx, sy in gm._shore
        if gm._point_ok(sx + px / 2, sy + px / 2)
        and any(not gm._point_ok(sx + px / 2 + dx, sy + px / 2 + dy)
                for dx, dy in ((px, 0), (-px, 0), (0, px), (0, -px)))
    ))

    _finish(gm, a, sheets)

def _finish(gm, a, sheets) -> None:
    """The water buffer, drop shadow, foam frames and scenery scatter --
    shared by the LD-8 painter and the LD-9 height-map one, which differ
    only in how the land itself is baked."""
    t = a.terrain
    water = a.tile(str(t.get("water_tile")), 0)
    if water is not None:
        wt = water.get_width()
        # Big enough to cover the visible world extent (SCREEN / zoom) plus
        # one tile of scroll slack; `_z_surf` blows it up to the screen.
        span_w = round(config.SCREEN_WIDTH / config.CAMERA_ZOOM) + wt
        span_h = round(config.SCREEN_HEIGHT / config.CAMERA_ZOOM) + wt
        buf = pygame.Surface((span_w, span_h)).convert()
        for y in range(0, span_h, wt):
            for x in range(0, span_w, wt):
                buf.blit(water, (x, y))
        gm._water_buf = buf
        gm._water_tile = wt

    _shdw = a.frames("terrain_shadow", "loop")
    gm._shadow = _shdw[0] if _shdw else None

    if config.TERRAIN_FOAM:
        gm._foam = a.frames("terrain_foam", "loop")
        routines = t.get("foam_routines", [])
        parsed = tuple((max(0.1, float(r["fps"])), int(r.get("phase", 0)))
                       for r in routines if float(r.get("fps", 0)) > 0)
        if parsed:
            gm._foam_routines = parsed

    if config.TERRAIN_DECORATIONS:
        terrain_decor.build_obstacle_decor(gm, a)

    if config.TERRAIN_DECOR:
        terrain_decor.build_decor_scatter(gm, a)
        terrain_decor.build_water_decor(gm, a)

    gm._tiles_ok = True

