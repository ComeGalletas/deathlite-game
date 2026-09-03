"""Baking the world into surfaces: the one-off pass that turns a layout into art.

Runs once, lazily, on the first draw (it needs a display), and returns a
`BakedTerrain` -- `GameMap._build_tiles` stores it. Nothing here touches the
map: the painters take the baked result as their store, and the floor test
they need comes from `world/rules/floor.py` like everyone else's.

`bake_steps` is the same pass as a generator, one island (or one decor pass)
per step, so the loading screen can keep animating between them; `bake`
drives it to the end. The two do the same work in the same order, which the
pinned bake digest checks.
"""
from __future__ import annotations

import pygame

from game import config
from game.assets import get_assets
from world.terrain import decor as terrain_decor, grid_paint
from world.terrain.baked import BakedTerrain
from world.terrain.sheets import TileSheets


def bake(layout) -> BakedTerrain:
    steps = bake_steps(layout)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            return done.value


def bake_steps(layout):
    """Yields a label after each island and each finishing pass; *returns*
    the `BakedTerrain` when exhausted."""
    t = BakedTerrain(layout, list(layout.obstacles) if layout is not None else [])
    if layout is None:
        return t
    a = get_assets()
    sheets = TileSheets(a, layout.seed)
    if not sheets.ok:
        return t                                 # tileset missing -> flat fallback
    t.sheets = sheets

    # One pass per island, straight off its height map: the grid already says
    # what every cell is, so there is nothing to stitch. One surface per
    # *terrace*, not one per island, tagged with the terrace's level, so the
    # renderer can composite the world band by band and slot sprites between
    # two bands.
    for r in layout.rooms:
        for blit, surf, level in grid_paint.paint_room_levels(t, sheets, layout, r):
            t.grid_surfs.append((blit, surf, level))
        t.shore.extend(grid_paint.grid_shore(r))
        yield f"painting island {r.id + 1} of {len(layout.rooms)}"
    for c in layout.corridors:
        rc = grid_paint.paint_bridge(sheets, c)
        t.corr_surfs.append((rc[0], rc[1], layout.room(c.a).floor))
    yield "bridges"

    # The water buffer, drop shadow, foam frames and scenery scatter.
    data = a.terrain
    water = a.tile(str(data.get("water_tile")), 0)
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
        t.water_buf = buf
        t.water_tile = wt

    _shdw = a.frames("terrain_shadow", "loop")
    t.shadow = _shdw[0] if _shdw else None

    if config.TERRAIN_FOAM:
        t.foam = a.frames("terrain_foam", "loop")
        routines = data.get("foam_routines", [])
        parsed = tuple((max(0.1, float(r["fps"])), int(r.get("phase", 0)))
                       for r in routines if float(r.get("fps", 0)) > 0)
        if parsed:
            t.foam_routines = parsed
    yield "water"

    if config.TERRAIN_DECORATIONS:
        terrain_decor.build_obstacle_decor(t, a)
        yield "obstacle skins"

    if config.TERRAIN_DECOR:
        terrain_decor.build_decor_scatter(t, a)
        yield "clutter"
        terrain_decor.build_water_decor(t, a)
        yield "water scenery"

    t.ok = True
    return t
