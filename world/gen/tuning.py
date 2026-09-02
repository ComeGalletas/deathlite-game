"""Generation tuning constants -- one leaf module so every stage in
`world.gen` can import these without an import cycle (W1 of
journals/world_refactor.md).
"""
# Room kinds. `combat` is the filler; the rest are special locations whose
# interactions arrive in Milestone 10 -- Milestone 8 only places and labels them.
SPECIAL_KINDS = ("shrine", "treasure", "fountain", "altar", "merchant",
                 "elite_arena")
# LD-10: "elite rooms are gone" -- from the **height-map** worlds, which is
# where the brief was talking about. The legacy generator keeps them: dropping a
# kind there re-labels its rooms, and a re-labelled room is shaped and scattered
# differently, which moved four pinned-seed LD-8 tests that have nothing to do
# with elite arenas. The feature's own code -- the interactable kind,
# `locations.update_elite_arenas`, its render branch, its room palette -- stays
# in place and dormant rather than being ripped out in the same change.
_RETIRED_KINDS = ("elite_arena",)


def special_kinds(heightmap: bool) -> tuple:
    if not heightmap:
        return SPECIAL_KINDS
    return tuple(k for k in SPECIAL_KINDS if k not in _RETIRED_KINDS)

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

# The height-map world spaces its canopies instead of its trunks. The gap above
# is measured off the *collider*, which is a 15 px trunk ring, so two trees can
# stand 37 px apart -- while the art they wear is 93 to 138 px wide. A third of
# all trees were closer than 70 px to a neighbour and the grove read as one
# green mass with no trunks in it.
#
# 70 px between centres puts the near edge of a canopy inside its neighbour by
# about a third, which is a grove with depth rather than a blob, and the median
# lands near 120 px where two canopies just touch. It costs nothing: the top-up
# offsets widen with it, so the same ~265 trees a world still place.
#
# The flat LD-8 generator keeps the tight gap. It is pinned seed by seed in a
# dozen tests, and those worlds exist to describe how the old scatter behaved.
_TREE_TREE_GAP_GRID = 55
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


# LD-9 D8: obstacle density for height-map rooms.
#
# The legacy rule is `base + len(cells) // 48`, capped at 14, where `base` is 2
# for a "special" room and its area bonus is skipped entirely. That was written
# for LD-8 rooms of ~60 cells. A height-map room is 700-1000 cells, and *every*
# room in a height-map world is a special kind -- there are no `combat` rooms at
# all -- so every island got two obstacles. Measured: 1.8 obstacles per 1000
# floor cells against the flat world's 56.2, a 31x drop, which is why the
# islands render bare.
#
# Attempts scale with floor area instead. Placement still has to clear the
# doorways, the flights (D5) and the other obstacles' spacing, so the count
# achieved is lower than the count attempted.
_GRID_OBSTACLES_PER_1000 = 85.0
_GRID_PLACE_TRIES = 20
_GRID_CLEAR_RADIUS = 176.0             # ~2.75 tiles kept clear round an island's centre

# LD-10: the boss island is scattered like any other now, less an arena in the
# middle. Eight tiles clears about a fifth of a ~1,000-cell island -- enough to
# fight in without the rim reading as a bare slab, which is what the whole
# island was while the scatter skipped it outright.
_GRID_BOSS_CLEAR_RADIUS = 512.0        # 8 tiles
# The start island is scattered like any other full stop; this is only the
# bubble around the pixel the hero spawns at, big enough for the widest
# obstacle radius (34) plus the player's (16) plus a margin.
_GRID_SPAWN_CLEAR = 96.0               # 1.5 tiles
