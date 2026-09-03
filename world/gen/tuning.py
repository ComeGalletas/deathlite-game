"""Generation tuning constants -- one leaf module so every stage in
`world.gen` can import these without an import cycle.
"""
# Room kinds. `combat` is the filler; the rest are special locations with an
# interactable at their centre. `elite_arena` is not placed any more -- the
# brief retired it -- but the feature's own code (the interactable kind,
# `locations.update_elite_arenas`, its render branch) stays in place and
# dormant rather than being ripped out.
SPECIAL_KINDS = ("shrine", "treasure", "fountain", "altar", "merchant")

# _DIRS is the four orthogonal neighbor offsets — ((1,0), (-1,0), (0,1), (0,-1)) 
# (east, west, south, north) defined once in tuning.py:11 so every world.gen stage 
# shares the same definition without an import cycle.
_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))

# Trees have a small collision ring (entities/obstacle.py KINDS["tree"]) so a
# denser canopy still leaves rooms walkable. After the main scatter, `_topup_trees`
# adds this fraction more trees world-wide, each seeded next to a randomly chosen
# existing tree so the extra growth thickens the groves already there rather than
# sprinkling the open floor. 0.0 disables the pass.
_TREE_DENSITY_BOOST = 0.25
# Placement separation: every pairing but tree-to-tree keeps this clear.
_OBSTACLE_GAP = 46

# Trees space their *canopies*, not their trunks. The gap above is measured
# off the collider, which is a 15 px trunk ring, so two trees could stand
# 37 px apart -- while the art they wear is 93 to 138 px wide. A third of all
# trees were closer than 70 px to a neighbour and the grove read as one green
# mass with no trunks in it.
#
# 70 px between centres puts the near edge of a canopy inside its neighbour by
# about a third, which is a grove with depth rather than a blob, and the median
# lands near 120 px where two canopies just touch. It costs nothing: the top-up
# offsets widen with it, so the same ~265 trees a world still place.
_TREE_TREE_GAP_GRID = 55
# Offset of a top-up tree from its anchor tree, in px.
_TREE_THICKET_MIN_GRID = 70.0
_TREE_THICKET_MAX_GRID = 128.0

# Houses (config.TERRAIN_BUILDINGS): a circular `Obstacle` skinned per colour,
# placed off-centre in big rooms; a roomy room grows a colour-matched village
# cluster. `variant` = colour_band * 3 + (type - 1) + 1, indexing the 15-entry
# data/terrain.json `obstacle_decor.rigs["house"]` list. Keep in sync with
# entities/obstacle.py KINDS["house"]; the sprite scales off this radius.
_HOUSE_RADIUS = 31
_HOUSE_ROOM_CHANCE = 0.35
_HOUSE_MIN_ROOM_CELLS = 60
_HOUSE_GLOBAL_CAP = 7
_VILLAGE_MIN_ROOM_CELLS = 100
_VILLAGE_EXTRA = (1, 3)                 # extra buildings beyond the first
_VILLAGE_RADIUS = (3, 5)               # cluster spread, in tiles, from the first


# --- obstacle density ------------------------------------------------------
#
# Attempts scale with floor area. An island is 700-1000 cells, and a per-room
# count written for 60-cell rooms gave it two obstacles: measured at 1.8 per
# thousand floor cells against the retired flat world's 56.2, which is why islands
# rendered bare. Placement still has to clear the bridge mouths, the flights
# and the other obstacles' spacing, so the count achieved is lower than the
# count attempted.
_GRID_OBSTACLES_PER_1000 = 85.0
_GRID_PLACE_TRIES = 20
_GRID_CLEAR_RADIUS = 176.0             # ~2.75 tiles kept clear round a special island's centre

# The boss island is scattered like any other, less an arena in the middle.
# Eight tiles clears about a fifth of a ~1,000-cell island -- enough to fight
# in without the rim reading as a bare slab, which is what the whole island
# was while the scatter skipped it outright.
_GRID_BOSS_CLEAR_RADIUS = 512.0        # 8 tiles
# The start island is scattered like any other full stop; this is only the
# bubble around the pixel the hero spawns at, big enough for the widest
# obstacle radius (34) plus the player's (16) plus a margin.
_GRID_SPAWN_CLEAR = 96.0               # 1.5 tiles
