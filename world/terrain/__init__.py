"""Terrain baking and drawing.

    sheets      `TileSheets` -- the tileset adapter and per-bake tile cache
    autotile    the autotile slot maths
    grid_paint  one surface per terrace, straight off an island's height map
    decor/      obstacle skins, tree shades, interior clutter, water scenery
    baked       `BakedTerrain` -- what the bake produces
    bake        the one-off pass: layout -> `BakedTerrain`
    render      `TerrainRenderer` -- the baked result on screen, band by band
"""
