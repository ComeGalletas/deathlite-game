"""Generation tuning constants -- one leaf module so every stage in
`world.gen` can import these without an import cycle (W1 of
journals/world_refactor.md).
"""
# Room kinds. `combat` is the filler; the rest are special locations whose
# interactions arrive in Milestone 10 -- Milestone 8 only places and labels them.
SPECIAL_KINDS = ("shrine", "treasure", "fountain", "altar", "merchant", "elite_arena")

_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))

# Room floor size as a fraction of the chunk. `IRREGULAR_ROOMS` widens the band
# and rolls a bigger room now and then; off keeps the original single band.
_SIZE_FRAC = (0.42, 0.88)
_BIG_ROOM_FRAC = (0.78, 0.94)
_BIG_ROOM_CHANCE = 0.18
_LEGACY_SIZE_FRAC = (0.55, 0.86)

# Corner-bite ("notch") shaping: a few 2-3-cell blocks removed from the room's
# corners -> L / T / plus / stepped floors, all tile-aligned.
_NOTCH_MIN, _NOTCH_MAX = 2, 3
_MIN_ROOM_CELLS = 9

# Multi-chunk growth (W5): a combat room may extend a tile-aligned block into one
# empty adjacent chunk cell, capped at config.ROOM_SIZE_MAX_CELLS.
_MULTICHUNK_ROOM_CHANCE = 0.16
_GROW_TILES = (3, 7)

# Trees have a small collision ring (entities/obstacle.py KINDS["tree"]) so a
# denser canopy still leaves rooms walkable. After the main scatter, `_topup_trees`
# adds this fraction more trees world-wide, each seeded next to a randomly chosen
# existing tree so the extra growth thickens the groves already there rather than
# sprinkling the open floor. 0.0 disables the pass.
_TREE_DENSITY_BOOST = 0.25
# Offset of a top-up tree from its anchor tree: ~0.55 to ~1.5 tiles.
_TREE_THICKET_MIN = 36.0
_TREE_THICKET_MAX = 96.0
# Placement separation: a tree keeps only this clear of another tree (a small
# trunk gap -> groves), but the full `_OBSTACLE_GAP` off rocks / pillars / houses.
_TREE_TREE_GAP = 22
_OBSTACLE_GAP = 46

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


# --- LD-1: layered verticality ----------------------------------------------
_VERT_REGIONS = (1, 2)          # raised plateaus per world
_VERT_REGION_ROOMS = (3, 6)     # rooms flooded into a floor-1 plateau
_VERT_F2_CHANCE = 0.65          # a plateau escalates an inner part to floor 2
_VERT_F3_CHANCE = 0.40          # a floor-2 area sprouts a 1-room floor-3 pocket
# A stair is 2 tiles wide only for a gentle 1-floor step between two roomy
# rooms with a generous shared edge; a steep 2-floor climb or a tight fit stays
# 1 tile. So width tracks how the rooms came out, not a coin flip.
_STAIR_WIDE_OVERLAP_TILES = 6
_STAIR_WIDE_ROOM_TILES = 7
