"""Enemy navigation: the lattice, its clearance, and the flow field.

    lattice     `NavGrid` -- walkable / corridor / clearance / step masks
    clearance   the chamfer transform behind `NavGrid.clearance`
    field       `FlowField`, `NavField` -- the shared distance field

`world.pathfinding` re-exports these under the names the game and the tests
grew up with.
"""
from world.nav.clearance import CLEARANCE_CAP, clearance_transform  # noqa: F401
from world.nav.field import FlowField, NavField, _INF, _NAV_CLASSES  # noqa: F401
from world.nav.lattice import NAV_DIRS, NavGrid  # noqa: F401
