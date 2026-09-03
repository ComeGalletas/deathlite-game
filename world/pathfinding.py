"""Enemy navigation -- see the `world.nav` package.

It exists only so old imports (from world.pathfinding import NavGrid, etc.) keep working, 
while the real logic moved to a nav package. 

Runs after world generation, alongside runtime geometry, not during bake/render:
`NavGrid` rasterises the finished layout into a walkable/clearance/elevation
grid, `clearance_transform` scores per-cell room for obstacle avoidance, and
`FlowField`/`NavField` build a shared steering field enemies sample instead of
each pathing individually. Reads the same floor/elevation rules as the player
collider so enemies never route where a player couldn't walk.
"""
from world.nav.clearance import CLEARANCE_CAP as _CLEARANCE_CAP
from world.nav.field import FlowField, NavField, _INF, _NAV_CLASSES
from world.nav.lattice import ( NAV_DIRS, NavGrid, _ORTH, _TILE_BIT,
    _point_in_corridor, _point_inset_ok, _point_on_floor,
)
