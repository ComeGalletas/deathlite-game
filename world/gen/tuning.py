"""Generation tuning constants -- one leaf module so every stage in
`world.gen` can import these without an import cycle.
"""
# Room kinds. `combat` is the filler; the rest are special locations with an
# interactable at their centre. `elite_arena` was retired by the brief and its
# code was removed on 2026-09-12 (`placement_review_journal.md`, C2): it had
# been dormant but wired through the interactable kinds, a per-frame update, a
# render branch and a spawn owner.
# `fountain` left this tuple with HI-1: the heal is the village's sanctuary
# prop now (`journals/human_island_journal.md`), not an island of its own.
SPECIAL_KINDS = ("shrine", "treasure", "altar", "merchant")
# HI-1: the human island. Not a special kind -- nothing sits at its centre
# by the special-room rule, no obstacle scatters on it, no enemy spawns
# there. `world/gen/village.py` decides what stands on it.
VILLAGE_KIND = "village"

# The four orthogonal neighbour offsets -- east, west, south, north -- defined
# here so every `world.gen` stage shares one definition without an import cycle.
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
# The world scatter's pairing table, the same idea as `_V_PAIR_GAPS` for the
# village: the pass carries a default (`_OBSTACLE_GAP`) and this lists the
# pairings that answer differently. One entry today -- tree beside tree, the
# grove spacing above. Deliberately *not* shared with the village's table:
# the numbers differ (55 out here, 40 in a village, where the settlement is
# tight and the trees frame it), and merging them would move every world.
_PAIR_GAPS = {("tree", "tree"): _TREE_TREE_GAP_GRID}
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

# --- the village pass (`world/gen/village.py`, HI-2) -------------------------
#
# Distances are in tiles from the forge unless said otherwise. A village
# island is ~24 x 14 tiles of rect and ~185 walkable tiles (HI-4 shrank it
# twice), so the rings are tight: the ring's band is half coast and half
# road on the smallest islands, which is why the house row has a fallback
# that seats what is left beside the houses already standing, and why the
# searches here fan out until something fits rather than giving up.
# The settlement is designed round the forge on a north axis: the heal
# zone directly above the forge, the town hall (the monastery) directly
# above the heal. The houses cluster on adjacent slots of the ring, the
# military buildings group beside each bridge road, and everything loose
# -- trees, rocks, clutter -- stays outside `_V_CLUSTER_RADIUS`, spread
# round the centre.
_V_HOUSES = (3, 5)                      # houses, on adjacent slots of the ring
# Houses may crowd (owner, 2026-09-12): on the quarter-smaller island the
# ring has few slots, so two houses may stand on adjacent tile centres --
# 64 px apart, which clears their 31 px colliders by 2 px -- and their art
# may paint over another house's. It may never paint over the forge, the
# heal or the hall: those three keep `_V_GAP` and their protected boxes,
# and the tidy pass still moves anything that crosses them.
_V_HOUSE_GAP = 0.0                      # px between two houses' colliders (`_V_GAP` for every other pairing)
_V_SLOTS = 8                            # angular slots round the forge; N, NE, NW are the axis's
_V_RING = (2.0, 4.0)                    # the house ring, min..max distance from the forge
_V_HOUSE_LINK = 3.0                     # a house stands within this of the one before it
_V_HEAL_NORTH = 2.0                     # the heal zone, tiles due north of the forge
_V_HALL_ABOVE = (3.0, 4.0)              # the town hall, tiles straight above the heal (same x); 3 keeps its foot clear of the heal effect's column
_V_CLUSTER_RADIUS = 5.5                 # the settlement's extent; props stay outside it
_V_HEAL_RADIUS = 26.0                   # the disc it reserves (its interactable radius)
_V_MILITARY_INLAND = 3.0                # the military group: tiles in from the bridge mouth
_V_MILITARY_FLANK = 1.8                 # ... and off the road, the first building
_V_MILITARY_PITCH = 1.4                 # ... then this much further off, per building
_V_PEN_DIST = (4.5, 12.0)               # pen centre, away from the bridges (10 → 12 with the street, LD-Z)
_V_PEN_W = (6, 7)                       # pen size in fence tiles, ring included
_V_PEN_H = (4, 5)                       # ... so the interior is 4-5 x 2-3 fence tiles
_V_PEN_SCALE = 0.45                     # a fence tile's pitch and art, as a fraction of a world tile (0.6, then 25% less)
# How `_place_pen` searches, as `(angular step in radians, ground pad in
# tiles)` passes tried in order. The first pass is the only one most
# villages need. The second exists because the island shrank a quarter
# (0.56 → 0.51): on the smallest islands the band that is both clear of the
# settlement and far enough from the coast is thinner than the coarse fan's
# stride, and three villages in thirty-six came out penless. It runs only
# when the first pass finds nothing, so no pen that already had a spot
# moves; it looks between the angles the first pass stepped over and keeps
# a quarter tile of ground round the rail instead of half.
_V_PEN_SWEEPS = ((0.3, 0.5), (0.1, 0.25))
_V_LANE_HALF = 1.0                      # half-width kept clear on each road, tiles
_V_GAP = 12.0                           # px between any two village circles
_V_COAST_PAD = 16.0                     # px of ground a circle keeps to the coast
# The village's own scatter, after the buildings: the island's biome mix at
# this fraction of the biome's density, and this many px between a tree or
# rock and a building, so a canopy never covers a door.
_V_SCATTER_SCALE = 2.5                  # over the whole island's cells, placed in the band outside the cluster
_V_SCATTER_TREES = 2.0                  # the biome's tree weight, multiplied: a village stands among trees
_V_SCATTER_GAP = 40.0
# The fill sweep (owner, 2026-09-12): once the buildings, the pen and the
# house row are down, a second pass walks the island's own cells in order --
# rather than throwing darts the way the first scatter does -- and offers
# each empty one a prop, so the coverage is systematic and the outside of
# the island stops reading as bare lawn. Weighted to the coast: a cell
# within `_V_FILL_BAND` tiles of the shore takes `_V_FILL_CHANCE`, one
# further in only `_V_FILL_INNER` of that, and the settlement's own radius
# and the pen stay clear as before. `_V_FILL_GAP` is what keeps it a meadow
# and not a wood: a prop of this sweep stands no closer than that to
# anything already placed, which is more than the first scatter asks
# (`_V_SCATTER_GAP`) because these are the ones filling the gaps.
_V_FILL_BAND = 3                        # tiles from the shore that count as the island's outside
_V_FILL_CHANCE = 0.50                   # chance an empty cell out there takes a prop
_V_FILL_INNER = 0.30                    # ... of that chance, for a cell further in
_V_FILL_GAP = 52.0                      # px a fill prop keeps from anything already standing
# The fill sweep keeps this radius round the forge clear rather than the
# first scatter's `_V_CLUSTER_RADIUS`. The cluster radius is drawn round
# the forge, but the buildings are not: on a ragged island they all end up
# on one side of it, and the lawn on the other side is inside the circle
# with nothing in it -- which is exactly the empty space the owner asked to
# fill. This covers the square itself (the forge, the heal two tiles north
# and the hall above it) and leaves the rest to `_V_FILL_GAP`, which keeps
# every prop clear of every building anyway.
_V_FILL_SQUARE = 4.0                    # tiles round the forge the fill sweep leaves alone
# Trees, and only trees, may stand closer to each other than any other
# pairing: 15 px trunk + 15 px trunk + this = 70 px between centres, which
# is the spacing the world's own grove uses (`_TREE_TREE_GAP_GRID`) -- a
# canopy's near edge inside its neighbour by about a third, a grove with
# depth rather than one green mass.
_V_TREE_GAP = 40.0                      # px between two trees' trunks
# Then `_V_TREE_TOPUP` more trees a village (owner, 2026-09-12: four more on
# average), each grown beside a tree already standing, at the world scatter's
# thicket offsets. Beside, not anywhere: a village should gain a thicker
# grove, not a sprinkle of lone trunks across its lawn.
_V_TREE_TOPUP = 4
# Two gaps, two different questions. Each *pass* carries a default -- how far
# what it places keeps from everything already standing (`_V_GAP` for the
# buildings, `_V_SCATTER_GAP` for the first prop sweep, `_V_FILL_GAP` for the
# second) -- and this table is the short list of *pairings* that answer
# differently whoever is asking. Both entries are deliberate and both are the
# owner's: two houses may close the row up (2026-09-12), and two trees may
# stand a canopy's third apart so a grove reads as a grove. Keyed either way
# round; anything not listed uses the pass's own gap.
_V_PAIR_GAPS = {("house", "house"): _V_HOUSE_GAP,
                ("tree", "tree"): _V_TREE_GAP}
# LD-Z, the tidy pass (`world/gen/village_tidy.py`): art clear of art.
_V_ART_TOL = 6.0                        # px two painted boxes may overlap both ways before it is a clip
_V_HEAL_NEAR = 3.5                      # tiles: a building this close keeps the heal company
_V_HEAL_COMPANY = 2                     # buildings (besides the forge and the hall) the heal wants near it
_V_HEAL_FLANK = (2.0, 3.0)              # tiles east / west of the heal a house is pulled in to (whole tiles: the spot snaps)
# How `flank_spot` searches for that house, as `(offsets along the flank,
# offsets up and down)` laps in tiles, tried in order and always inside
# `_V_HEAL_NEAR`. The first lap is the square as it was designed. The second
# is for the quarter-smaller island (0.56 -> 0.51), where four villages in
# fifty-two had houses but no spot on the tight lattice for one beside the
# heal, and the sanctuary stood alone; it runs only when the first finds
# nothing, so no house that already had its flank spot moves.
_V_HEAL_FLANK_LAPS = ((_V_HEAL_FLANK, (0.0, 1.0, -1.0)),
                      ((1.5, 2.0, 2.5, 3.0, 3.5), (0.0, 1.0, -1.0, 2.0, -2.0)))
_V_MILITARY_REACH = 8.0                 # tiles from its bridge mouth a relocated military building may stand
_V_CLUSTER_MAX = 4.0                    # tiles: no house stands farther than this from every other building
_V_STREET_REACH = 4.5                   # tiles: a road bends onto the street (the forge's row) no nearer the axis than this


# --- spawn points (`world/gen/spawnpoints.py`) ------------------------------
#
# How many per terrace is `config.SPAWN_POINTS_PER_FLOOR` (a `GenSettings`
# field); these are the geometry rules every candidate has to pass.
#
# Clear of an obstacle by this much beyond "the two discs do not touch", so a
# body that materialises on the point is not already shoving a rock.
_SPAWN_OBSTACLE_GAP = 8.0
# Two points on one floor are never closer than this many tiles. The
# farthest-point pick spreads them much wider than that on a normal terrace;
# the floor is only a guard for a cramped one.
_SPAWN_MIN_SPACING_TILES = 2
# The start island keeps this many tiles around the hero's first position
# free of spawn points, so the opening seconds are calm.
_SPAWN_START_CLEAR_TILES = 8
# A floor that seats fewer than this at the full margin gets one retry at the
# bare body inset before it is left short.
_SPAWN_RELAX_BELOW = 3
# Tag distances, in tiles: `edge` within this of the coast, `bridge` within
# this of a bridge-mouth keep-clear rect.
_SPAWN_EDGE_TILES = 4
_SPAWN_BRIDGE_TILES = 6
# Resource anchors per island, the kinds they are dealt, and the weights.
# `ambient` outnumbers `chest` on purpose: a chest is an event, a gem is not.
_RESOURCE_POINTS_PER_ISLAND = 8
_RESOURCE_KINDS = ("chest", "breakable", "ambient")
_RESOURCE_WEIGHTS = (2, 3, 5)
# --- treasure chests (CB-9, `world/gen/chests.py`) -------------------------
#
# *Placement* only. What a chest contains lives in `data/chests.json`; these
# are here because the generator is pure and never sees `Content`, and because
# they are the same class of knob as `_RESOURCE_*` above.
#
# The owner's brief: "there can only be a max of 5 chests per island, with an
# average of 2-3", and "rare chests should be a max of 1 if there are". The
# weights below mean 2.50 per island -- 1x0.20 + 2x0.35 + 3x0.25 + 4x0.15 +
# 5x0.05 -- with 5 the hard ceiling. There is no `0` entry, so every island
# that gets anchors at all gets at least one chest; adding one is how you let
# an island come up empty.
_CHEST_RARITIES = ("common", "uncommon", "rare", "epic")
_CHEST_COUNT_WEIGHTS = {1: 20, 2: 35, 3: 25, 4: 15, 5: 5}
# Per chest, before the caps. ~19 chests a world works out at roughly 11
# common, 5.6 uncommon, 1.7 rare and 0.6 epic -- a rare chest is a treat and
# an epic one is an event rather than a fixture.
_CHEST_RARITY_WEIGHTS = {"common": 58, "uncommon": 30, "rare": 9, "epic": 3}
# Per island. `rare` is the owner's rule; `epic` is capped the same way because
# capping the second-best tier and leaving the best one open cannot be the
# intent. A draw that would break a cap falls back to `common`.
_CHEST_CAPS = {"rare": 1, "epic": 1}

# A resource anchor keeps this many tiles off the straight line between two
# bridge mouths -- the path a player is most likely to walk -- so loot is
# found by looking around, not by walking through.
_RESOURCE_OFF_PATH_TILES = 2
# ...and this many off any enemy spawn point, so a chest is not a spawn pad.
_RESOURCE_OFF_SPAWN_TILES = 2

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
