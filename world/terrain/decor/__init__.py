"""Decoration: everything placed on the world that is not terrain or an entity.

Split from a single `decor.py` once the module carried five separable concerns.
Each leaf answers one question:

  `rigs`            -- what does a prop's art look like at this size?
  `spacing`         -- is anything already too close to here?
  `budget`          -- how many props does this terrace get, and of what tiers?
  `obstacle_skins`  -- which rig skins this obstacle, on which clock?
  `shadows`         -- the soft shade under a tree
  `scatter_room`    -- where may a prop stand on an island's floor?
  `scatter_water`   -- ...and on the sea, the shoreline and the lakes

The frontier rules the two scatters share -- what counts as a terrace edge, and
how far a sprite's art reaches -- live in `world/frontier.py`, which the
obstacle scatter in `world/gen/scatter.py` imports too and which therefore
cannot live in here.

Everything the bake and the tests used to reach for on the flat module is
re-exported below, so `from world.terrain import decor` keeps working.
"""
from world.terrain.decor.budget import (
    FEATURE, GROUND_COVER, LANDMARK, TIERS,
    _cell_biomes, _terraces, _tier_scales,
)
from world.terrain.decor.obstacle_skins import build_obstacle_decor
from world.terrain.decor.rigs import load_rig
from world.terrain.decor.scatter_room import build_decor_scatter
from world.terrain.decor.scatter_water import build_water_decor
from world.terrain.decor.shadows import build_tree_shadows
from world.terrain.decor.spacing import _Neighbourhood

__all__ = [
    "FEATURE", "GROUND_COVER", "LANDMARK", "TIERS",
    "build_decor_scatter", "build_obstacle_decor", "build_tree_shadows",
    "build_water_decor", "load_rig",
]
