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


# --- terrace planning -----------------------------------------------------
