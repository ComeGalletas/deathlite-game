"""Compatibility shim -- the height-map generator moved to `world.gen.height`.

It had grown to 1,180 lines holding six unrelated concerns; 230 of those were an
earlier band-based generator that nothing called any more. What is left is split
one module per stage under `world/gen/height/`, with `build_grid` as the
pipeline in that package's `__init__`.

Kept because `world.gen`, the terrain painters and a dozen test modules import
`world.gen.heightmap` by name.
"""
from world.gen.height import *          # noqa: F401,F403
from world.gen.height import (          # noqa: F401  -- the private helpers
    _all_neighbours_in, _cap, _carve_bays, _carve_canyons, _carve_lakes,
    _coast_once, _components, _cut_flights, _despike, _ewstair_site,
    _face_the_sea, _fill_holes, _link_levels, _one_piece, _prune_unreachable,
    _raise_walls, _trim_lake_stubs, _vstair_site, _walk, _wall_flight_sides,
    _water_blobs, _NB,
)
from world.gen.height import (          # noqa: F401  -- the public surface
    build_grid, check_grid, coast_mask, coast_shape, reachable, to_ascii,
    walk_links, CAP_INSET_E, CAP_INSET_N, CAP_INSET_S, CAP_INSET_W,
    CAP_ROUGHNESS, CANYONS, CANYON_DEPTH, CANYON_WIDTH, MAX_DROP, MAX_LEVEL,
    MIN_CAP_CELLS, MIN_TERRACE_ROWS, REGION, STAIR_SPACING,
)
