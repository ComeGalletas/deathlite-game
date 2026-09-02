"""Shared constants for the height-map stages.

One leaf module so `coast`, `terraces`, `walls`, `flights`, `water` and
`graph` can each import what they need without importing one another --
the same trick `world/gen/tuning.py` plays for the outer package.
"""
# The four orthogonal neighbours. Every use in this module is inside an `all`,
# a `sum` or a set comprehension, so the order is not load-bearing here -- which
# is why it can be one constant. It is deliberately *not* shared with
# `tuning._DIRS` or `pathfinding._ORTH`: those two are written in a different
# order and feed a seeded shuffle and a two-pass mask respectively, where the
# order is part of the result.
_NB = ((-1, 0), (1, 0), (0, -1), (0, 1))

MIN_TERRACE_ROWS = 3          # walkable rows a terrace needs to be worth having
MAX_LEVEL = 2                 # sea level plus two floors
MAX_DROP = 2                  # "max two stacked cliffs"

# How far each plateau is inset from the one below it, per side. South is the
# deepest because that face is the one the camera sees -- pulling the cap back
# from the south rim is what gives the mountain a visible slope, while barely
# insetting the north keeps it hugging the island's back. `CAP_ROUGHNESS` then
# nibbles the rim so it does not read as a smooth contour line.
CAP_INSET_S = 5
CAP_INSET_N = 1
CAP_INSET_W = 3
CAP_INSET_E = 3
CAP_ROUGHNESS = 0.35
MIN_CAP_CELLS = 24            # below this a plateau is not worth having
# Crossings are placed per **region** rather than per island, so every stretch
# of rim gets its own way up instead of the quota being spent wherever a global
# shuffle happens to fall. `REGION` is the region's side in tiles and
# `STAIR_SPACING` how far apart two crossings must sit.
# Canyons cut up into a plateau from its southern rim. Their heads are the only
# south-facing wall the northern half of an island can have, so these are what
# put ways up there at all -- see `_carve_canyons`.
# Crossings are placed per **region** rather than per island, so every stretch
# of rim gets its own way up instead of the quota being spent wherever a global
# shuffle happens to fall. `REGION` is the region's side in tiles and
# `STAIR_SPACING` how far apart two crossings must sit.
REGION = 8
STAIR_SPACING = 4
CANYONS = 3
CANYON_DEPTH = (4, 10)
CANYON_WIDTH = (3, 5)

# Lateral stairs: crossings on a plateau's east and west faces, so an island
# can be climbed from its sides and not only from the bottom.
#
# Those faces carry no stone. `_raise_walls` only stones a *southward* drop --
# every cliff tile in the tileset is a horizontal run drawn as if seen from the
# south -- so measured over six worlds there are zero vertical stone runs, and
# a plateau's east/west boundary is a bare level change. Every existing site
# test needs a `CLIFF` to work from, which is why no stair ever landed there.
#
# A lateral crossing is the two-tile ramp unit the tileset already ships
# (`slots.ramp`, present in all eight tilemaps) laid straight onto that bare
# boundary: no stone added, no new art. It needs **two vertically adjacent**
# drop tiles so both halves of the unit have a face to connect to -- 508 such
# runs exist over six worlds, 888 distinct placements, and every multi-level
# island has at least one.
SIDE_STAIRS = (2, 3)
# A plateau above the first floor is small and already well served by the south
# rim, so it takes about a quarter of that.
SIDE_STAIRS_HIGH = (0, 1)
SIDE_STAIRS_HIGH_FROM = 2          # the first level counted as "high"
# Separation between two lateral crossings, in tiles. The unit is two tiles
# tall, so 2 lets a pair sit back to back but never overlap -- the site test
# needs plain ground under both halves, and a placed crossing is not ground.
# Measured, it is what actually reaches the target: 77% of plateau sides land
# on exactly two or three crossings against 58% at 3.
SIDE_SPACING = 2


# --- terrace planning -----------------------------------------------------
