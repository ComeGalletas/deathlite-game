"""Central configuration.

All tunable constants live here so systems never hardcode magic numbers.
Keep this module dependency-free: everything may import it, it imports nothing
from the project.
"""
from __future__ import annotations

# --- Display -----------------------------------------------------------------
# The window / render target. The world is drawn straight to it at this
# resolution (no intermediate buffer), so a larger screen = more pixels per
# sprite / tile. 16:9.
SCREEN_WIDTH: int = 1600
SCREEN_HEIGHT: int = 900
FPS: int = 120
TITLE: str = "Death Lite Game"

# Largest delta time (seconds) a single frame is allowed to represent. Without
# this a stall (e.g. window drag) produces a huge dt that tunnels entities
# through walls / each other -- the classic "spiral of death".
MAX_DT: float = 1.0 / 20.0

# Draw-time camera magnification: `Camera.world_to_screen` multiplies world
# positions by this, and every renderer scales its sprite / tile sizes to match,
# so the picture is a "closer" view that stays crisp (sprites scale *down* from
# their large source frames -- no upscale blur). The HUD and feedback overlays
# are drawn afterwards at full resolution and are unaffected. 1.0 == no zoom.
# The visible world extent is therefore SCREEN_* / CAMERA_ZOOM.
CAMERA_ZOOM: float = 1.5

# --- Persistence -----------------------------------------------------------
# When True the game reads `save.json` at boot and writes it back on every
# persist() (settings, run rewards, records). When False it never touches the
# disk: each launch starts from a fresh SaveData() and progression lasts only
# for the session. The browser build (pygbag / emscripten) has no durable,
# writable filesystem, so `main_web.py` -- and `main.py` when it detects an
# emscripten runtime -- flips this to False. Desktop leaves it True.
SAVE_ENABLED: bool = True

# --- World -----------------------------------------------------------------
# Fallback size used only before a procedural layout exists (menus / tests).
WORLD_WIDTH: int = 3200
WORLD_HEIGHT: int = 3200

# Procedural world (Phase 3): a lattice of chunk cells, one room per cell,
# joined into a tree of corridors. See world/procedural.py.
CHUNK_SIZE: int = 720
WORLD_ROOM_COUNT: int = 16
# World grid unit. Room rects and corridor widths are snapped to this so the
# tiled renderer covers each cell exactly (terrain T7). Keep in sync with
# data/terrain.json "tile_px" (Assets.tile uses that for sheet slicing).
TILE_PX: int = 64

# Rooms are tile-aligned irregular (rectilinear) polygons -- a rectangle with
# 2-3-cell corner bites (L / T / plus / stepped) -- and their size varies more.
# Off -> the old plain rectangles + old size band, for reproducing pinned-seed
# layouts. See world/procedural.py (`Room.cells`, `_carve_room_shapes`).
IRREGULAR_ROOMS: bool = True
# Hard ceiling on one room's tile-cell count (a room can't eat the world); also
# the cap for the deferred multi-chunk "large room" pass.
ROOM_SIZE_MAX_CELLS: int = 160

# --- LD-9: rooms are height maps ----------------------------------------
# Each room gets a per-cell grid (`world/gen/heightmap.py`) with its own
# terraces, cliffs and stairs, instead of one `floor` integer plus a cliff band
# hanging off its south rim. Off -> the LD-8 model, byte-identical layouts.
#
# On by default since phase D. What had to land first: nav and collision read
# the grid (D0-D4), so a flank or a terrace's back edge is a wall and only a
# flight crosses it; obstacle scatter keeps flights clear (D5); enemies have an
# aggro range and give up (D7), without which a flow field routes one the length
# of an island to reach a player across a drop; and the field is bounded (D9),
# without which a repath on these much larger worlds cost 37.9 ms.
HEIGHTMAP_ROOMS: bool = True
# With the flag on: fewer, larger rooms, because a room now has to hold several
# terraces and the walls between them. A terrace needs 3 walkable rows plus its
# wall, so a room wants ~14 rows to carry three of them.
# Big enough that the widest room still leaves a water gap to its neighbours --
# rooms are islands, and overlapping ones would fuse into one landmass.
# Lattice cell for a height-map room, per axis, in tiles.
#
# Was one square 58-tile cell, which is why vertical bridges ran at a median of
# 34 tiles against 17 for the horizontal ones: a room is 36-50 tiles wide but
# only 22-30 tall, so a square cell left a chunk-height of empty sea above and
# below every island. Sized per axis to the largest room instead, bridges come
# out at a median of 10 / 6.
#
# Packed closer than the rects alone would allow, which needs two things
# together: `HEIGHTMAP_COAST_KEEP` guarantees a void band inside every rect so
# the rects may overlap without the islands meeting, and the room size *range*
# is narrow (44-50 x 26-30 rather than 36-50 x 22-30) so a small island no
# longer leaves a cell's worth of extra sea around it. Measured over 14 seeds:
#
#     50x30, rooms 36-50   bridges h 10/15  v  7/10
#     46x26, rooms 36-50   bridges h  9/15  v  6/9
#     46x26, rooms 44-50   bridges h  5/8   v  4/6   rect overlap 2/4
#     48x28, rooms 44-50   bridges h  7/10  v  6/8   rect overlap 0/2  <- chosen
#     50x30, rooms 44-50   bridges h  9/12  v  8/10  rect overlap 0/0
#
# 48x28 backs the islands apart again after 46x26 read as too tight: the median
# rect overlap goes to zero and the worst case halves, for two tiles of extra
# sea. 50x30 removes overlap entirely if the islands still crowd.
#
# Zero land-cell collisions between rooms in every row above; tighter than this
# and islands start to merge.
# Tiles of void guaranteed inside a room rect on every side. The coast walk
# alone leaves none (measured minimum inset: 0), so without this a rect is not a
# safe proxy for where its island is and neighbouring rects cannot overlap.
HEIGHTMAP_COAST_KEEP: int = 2

# How many plank bridges each link between two islands carries, and how far
# apart two bridges on the same link must be, in tiles. `_seat_corridors` places
# them at random among the lanes where both islands offer a beach -- all of them
# would otherwise take the shortest crossing and land on top of each other,
# since they are seated by the same deterministic rule. A link's first bridge
# always survives even if the gap leaves no room; the extras are dropped.
# LD-10: how many bridges a link carries is a property of the two **islands**
# now, not one global number -- see `bridges` in `HEIGHTMAP_TOPOGRAPHIES`.
HEIGHTMAP_BRIDGE_MIN_GAP: int = 6

# Deliberately **two tiles smaller than the largest room** on each axis, which
# is the relationship D11 arrived at: rects overlap by that much and the islands
# still cannot meet, because `HEIGHTMAP_COAST_KEEP` guarantees a band of void
# inside every rect. Setting the chunk to the full room size instead spreads the
# world out -- measured, land fell from 24% of the bounds to 20% and the median
# bridge went from 5 tiles to 13.
# Both must be an **even** number of tiles. The world's bounds are inflated by
# one whole chunk before everything is shifted to the origin, and `Rect.inflate`
# moves the top-left by half of that -- so an odd chunk dimension shifts every
# room half a tile off the world grid, and `LevelIndex` can then no longer place
# a room's cells at all. Found the hard way with 29 rows.
HEIGHTMAP_CHUNK_COLS: int = 50
HEIGHTMAP_CHUNK_ROWS: int = 30
# Fewer, much larger islands. A room has to hold a shore ring, several terraces
# and the walls between them, and the coastline erodes it further -- so size it
# generously and cut the count to pay for it, rather than ending up with a
# scatter of islets too small to carry any of that.
HEIGHTMAP_ROOM_COUNT: int = 9
# Rooms are markedly **wider than they are tall**: terraces stack northward, so
# height buys more of the same climb while width buys room for several separate
# ways up on the same wall, which is what stops a room reading as one long
# staircase.
# LD-10: widened to pay for the coast margin's growth. A margin of 6 eats 6
# tiles off each side instead of 4, and at the old size that cost the islands
# their top terrace -- the level-2 count fell from 54 of 84 to 25 of 60 purely
# by erosion, which is topography deciding itself instead of being chosen.
# Growing the room in step restores it (49 of 84) at almost the same mean land
# area, 928 tiles against 952.
HEIGHTMAP_ROOM_COLS: tuple = (46, 52)
HEIGHTMAP_ROOM_ROWS: tuple = (28, 32)
# Ways up are placed per **region** of the island rather than per island, so
# every stretch of rim gets its own crossings -- an island-wide quota gets spent
# wherever the shuffle falls and reliably leaves the north rim with no way up.
# REGION is the region's side in tiles, SPACING how far apart two may sit.
HEIGHTMAP_STAIRS_PER_REGION: int = 2
HEIGHTMAP_STAIR_REGION: int = 8
HEIGHTMAP_STAIR_SPACING: int = 4
# LD-10: how ragged a shoreline is, as one named set of parameters.
#
#   margin       how far the walk may come in from the rect edge -- the
#                *amplitude*, which is what actually controlled straightness
#   north_delta  added to `margin` for the north wall alone
#   hold         how many positions one inset value is held for
#   run_cap      never hold a value longer than this; 0 disables the cap
#   mask_keep    fraction of the rect a mask must keep to be accepted
#   grid_keep    the same test applied to the finished grid, in world/gen
#
# One preset for now. It stays a *table* because a topography names the preset
# it wants: a "castle" island is described as more squared, which is this table
# with a low margin and a long hold, not a new algorithm.
HEIGHTMAP_COAST_PRESET: str = "rugged"
HEIGHTMAP_COAST_PRESETS: dict = {
    "rugged": {"margin": 6, "north_delta": 0, "hold": (2, 3), "run_cap": 4,
               "mask_keep": 0.34, "grid_keep": 0.26},
}
# Rings of sea-level ground around the island before the terraces start, so it
# reads as land rising out of the water instead of a slab floating in it.
HEIGHTMAP_SHORE_RING: int = 1
# LD-9: after the scatter, check that the widest navigating body can still
# reach everywhere bare terrain allows, and take back the handful of obstacles
# that say otherwise (`world/gen/repair.py`). Costs one coarse navigation grid
# per world. Off is only for isolating placement from repair -- with it off,
# roughly one seed in three walls an island away from the large enemies.
HEIGHTMAP_UNSEAL: bool = True
# LD-10: after the tree's own bridges are seated, join islands that ended up
# close together but were never linked. The lattice grows a tree, so without
# this every route between two islands is unique and a run backtracks over the
# bridge it arrived by. Gap is measured between the two rects, in tiles.
# Longest bridge worth building, in tiles. A link the tree *needs* is never
# refused for being long -- dropping it would cut the world in two -- but it
# always takes the shortest lane it has when every lane is over the cap, and an
# **optional** crossing (a second bridge on a link, or a shortcut) is simply not
# built. See `_offset_in_chunk` for the other half: an island is nudged toward
# the neighbours it is linked to, not away from them, which is what actually
# shortens the long tail.
# 16 rather than 20: swept over five seeds at 8 / 12 / 16 / 20 / 24, the two
# middle values build the *same* graph -- same bridge count, same links, same
# 1.6 loops a world, same 38% of links being the only way somewhere -- and 16
# is simply shorter, max 18 tiles against 20 and p90 16 against 17. Below that
# it stops being free: at 8 the loops collapse to 0.2 a world and 90% of links
# go back to being the only way anywhere, while the longest crossing stays 18,
# because half of them are tree links already on their shortest lane. Above it
# the cap stops filtering and the maximum runs away again -- 25 tiles at 24.
HEIGHTMAP_BRIDGE_MAX: int = 16
HEIGHTMAP_SHORTCUTS: bool = True
HEIGHTMAP_SHORTCUT_GAP: int = 12
HEIGHTMAP_LAKES: int = 2
# Accretion steps per lake blob. Wider and larger -> bigger, raggeder pools;
# fewer cells than steps survive, since a step onto another terrace does
# nothing. A blob touching anything but its own terrace's ground is discarded,
# so pushing this much higher mostly costs rejections rather than size.
HEIGHTMAP_LAKE_SIZE: tuple = (10, 34)
# LD-10: island topography, which is **not** a room kind -- a shrine can sit on
# a small island. Kind says what happens on an island; topography says what
# shape it is. Declared as a table so a new type is data, in the same spirit as
# `SPECIAL_KINDS`: "castle" islands are already asked for, and want nothing more
# than a squarer `coast` preset and a flat `tiers`.
#
#   tiers    inclusive range of floors *above* sea level, drawn per island.
#            (1, 2) is the one the old generator could not express: it was a
#            coin flip between all three floors and one, with nothing between.
#   size     linear scale on the room rect. **It may not take a room past
#            `HEIGHTMAP_CHUNK_* + 2` tiles**: the packing guarantee is that a
#            rect overhangs its cell by at most one tile, so two neighbours
#            overlap by at most two and `HEIGHTMAP_COAST_KEEP` holds each
#            island's land that far inside its own rect. The boss island tried
#            1.15 and broke exactly that -- it overhung by five tiles and shared
#            land cells with the island beside it. It is 1.0 and still far the
#            biggest, because a flat island spends none of its area on cliff
#            faces: 1,150 walkable tiles against a volcanic island's 923.
#            Note this is *not* the area ratio:
#            the coast margin is an absolute number of tiles, so it eats
#            proportionally more of a smaller island. 0.76 linear measures out
#            at 0.49 of a volcanic island's walkable area, which is the "about
#            half" the brief asked for; 0.7 gives 0.38.
#   coast    which `HEIGHTMAP_COAST_PRESETS` entry shapes its shoreline
#   sheets   the tilesets this topography may wear, level 0 included. Level 0
#            is chosen from here now rather than from `room_palettes`, which
#            keyed it on room *kind* -- and kind is orthogonal to shape, so a
#            shrine on a small island was picking its ground from the wrong
#            axis entirely. `room_palettes` stays for the LD-8 generator, which
#            has no topographies.
#   allow_beachless_shore
#            let a sheet with `shoreline: false` sit at level 0. Off by
#            default, and it is not a taste setting: level 0 is the only
#            terrace that meets the sea, and a sheet without a surf block draws
#            that meeting from its raised block instead -- a hard rim rather
#            than foam. The rule is derived from `sheet_flags` rather than
#            listed per topography, so a ninth tileset cannot silently end up
#            on a shoreline it has no art for.
#   bridges  how many bridges may land on any one **side** of the island. Where
#            two islands disagree the lower wins, since both have to accept it.
#            Small islands are held to one; there is not enough beach on a
#            37-tile shore for two crossings to sit apart without one of them
#            landing somewhere silly.
#   weight   relative chance of being drawn; 0 means never drawn at random,
#            only assigned by role
HEIGHTMAP_TOPOGRAPHIES: dict = {
    "volcanic": {"tiers": (1, 2), "size": 1.0,  "coast": "rugged",
                 "bridges": 2, "weight": 3,
                 "sheets": ["terrain/tiles/tilemap_1.png",
                            "terrain/tiles/tilemap_2.png",
                            "terrain/tiles/tilemap_3.png",
                            "terrain/tiles/tilemap_4.png",
                            "terrain/tiles/tilemap_5.png",
                            "terrain/tiles/tilemap_6.png",
                            "terrain/tiles/tilemap_7.png",
                            "terrain/tiles/tilemap_8.png"]},
    "small":    {"tiers": (0, 1), "size": 0.76, "coast": "rugged",
                 "bridges": 1, "weight": 2,
                 "sheets": ["terrain/tiles/tilemap_1.png",
                            "terrain/tiles/tilemap_2.png",
                            "terrain/tiles/tilemap_3.png",
                            "terrain/tiles/tilemap_4.png",
                            "terrain/tiles/tilemap_5.png"]},
    "boss":     {"tiers": (0, 0), "size": 1.0,  "coast": "rugged",
                 "bridges": 1, "weight": 0,
                 # Deliberately includes a sheet with no surf block, to see
                 # what a beachless coastline looks like. A boss island is
                 # flat, so its *whole* shore is drawn that way -- an
                 # all-or-nothing look rather than a subtle one.
                 "allow_beachless_shore": True,
                 "sheets": ["terrain/tiles/tilemap_4.png",
                            "terrain/tiles/tilemap_5.png",
                            "terrain/tiles/tilemap_6.png"]},
}
HEIGHTMAP_BOSS_TOPOGRAPHY: str = "boss"
# The shape of the mountain. Each plateau is the one below it eroded inward by
# these amounts, per side. **South is the one that matters**: it is the only
# face the camera sees, so pulling each cap back from the south rim is what
# gives the island a visible slope, while barely insetting the north keeps the
# caps hugging its back. Raise SOUTH for a longer, gentler climb; even them all
# out for a dome rather than a mountain.
HEIGHTMAP_CAP_INSET_S: int = 5
HEIGHTMAP_CAP_INSET_N: int = 1
HEIGHTMAP_CAP_INSET_W: int = 3
HEIGHTMAP_CAP_INSET_E: int = 3
# How granular a plateau's rim is: the chance a rim cell is nibbled away.
# 0 gives smooth contour lines, higher values a broken, rocky edge.
HEIGHTMAP_CAP_ROUGHNESS: float = 0.35
# Below this many cells a plateau is not worth having, and the stack stops.
HEIGHTMAP_CAP_MIN_CELLS: int = 24
# Canyons cut up into each plateau from its southern rim. A south-facing wall
# only exists where the level drops going south, which around a concentric cap
# is the southern arc alone -- so a canyon's **head** is the only south-facing
# wall the northern half of an island can have, and these are what put ways up
# there. They also break a big plateau into lobes. Raise the count or the depth
# for a more densely broken, more climbable north side.
HEIGHTMAP_CANYONS: int = 5
HEIGHTMAP_CANYON_DEPTH: tuple = (4, 10)
HEIGHTMAP_CANYON_WIDTH: tuple = (3, 5)

# --- Layered verticality (journals/level_design_journal.md LD-1) ---------
# Rooms carry a `floor` (0 = ground, up to 3). A cross-floor room link is a
# `Stair` (1-2 tiles wide) instead of a plank `Corridor`; the raised room's
# south edge grows a stone cliff-face skirt. Off -> every room stays floor 0,
# no stairs, and the generated `WorldLayout` is byte-identical to the
# pre-verticality world (reproduces pinned-seed layouts).
WORLD_VERTICALITY: bool = True
# LD-8 #2: one cliff-face tile per floor of elevation. Plateau face height is
# the floor number, uncapped (floor 3 sits one tile above floor 2). A
# cross-floor link therefore drops 1 tile (Delta 1) or 2 tiles (Delta 2); the
# 2-floor-max connectivity rule keeps it from ever being deeper. Provisional --
# raise back toward 2 if a 1-tile ledge clips character sprites too much.
CLIFF_TILES: int = 1
# Whether generation insets a raised room's walkable cells to make room for an
# inset cliff face (LD-1 V5, render). Off for now: the plateau rim already
# borders void, so pathing is correct without it, and an aggressive inset can
# choke the flow field through a raised room. Turn on with the render pass.
CLIFF_CARVE: bool = False

# LD-3: replace the cross-floor plank "stair" with a sideways **ramp run** cut
# into the cliff band -- `face_h` ramp pieces stepping one column and one row
# each (see the level-design journal). Needs the two rooms in contact, so
# generation snaps the low room's top edge to the plateau's cliff base; a pair
# is skipped (and stays a bridge) when that move exceeds `RAMP_SNAP_TILES` or
# the run's footprint does not fit. Off -> layouts are byte-identical to LD-2.
RAMP_STAIRS: bool = True
# How far a room may be moved to bring it flush with a cliff base, in tiles,
# per floor of drop (a Delta 2 link is allowed twice this). Deliberately a
# constant, not a literal: longer approaches later just raise it.
RAMP_SNAP_TILES: int = 2
# LD-8a: chance a cross-floor ramp unit renders as the rock `vstairs.png`
# overlay instead of the biome grass sideways ramp, keyed by the plateau's
# floor. A seeded per-link roll -- higher / rockier floors lean rock. Missing
# floor -> the fallback below. Pure render tag; draws no world RNG.
RAMP_ROCK_BIAS: dict = {1: 0.35, 2: 0.8, 3: 1.0}
RAMP_ROCK_BIAS_DEFAULT: float = 0.5
# LD-8 #1: chance a cross-floor link renders as the LD-4 **side-landing** unit
# (stair column with a grass landing jogged one tile to each side) instead of a
# straight one-column flight. Seeded per link; consumes no world RNG.
RAMP_LANDING_BIAS: float = 0.4

# LD-5: give every generation-placed tile that is in no room's cell mask (plank
# planks, plank-stair strips, staircase-unit landings) an owning room, so it
# draws in that room's palette and is folded into the room's autotiled shape.
# Off -> `tile_meta` and the baked terrain are byte-identical to LD-4.
STRUCT_ANNEX: bool = True
# One plank stair in `STAIR_WIDE_EVERY` is 2 tiles wide (deterministic count,
# no RNG). The rest are 1 wide. Both render as plank bridges.
STAIR_WIDE_EVERY: int = 7

# Animated shoreline foam where a room floor meets the water (terrain T3).
# Off falls back to the baked autotile edge tiles alone.
TERRAIN_FOAM: bool = True
# Obstacle skins: every convex obstacle is drawn as a bush / rock decoration
# sprite scaled to its collider (terrain T4). Off -> plain drawn circles.
TERRAIN_DECORATIONS: bool = True
# Non-colliding scenery scatter (terrain T8): clutter on room interiors and
# water scenery (rocks / a duck) in the void. Purely cosmetic -- no effect on
# walkability. Data-driven from data/terrain.json "decorations".
TERRAIN_DECOR: bool = True
# Soft round canopy shadow cast on the ground by each tree, depth-sorted just
# before its owner and alpha-masked over intersecting character sprites
# (terrain B3). Needs TERRAIN_DECORATIONS on. Off -> no tree shade.
TERRAIN_SHADOWS: bool = True
# Buildings: a `house` obstacle (large circular collider, blocks shots) placed
# off-centre in big rooms; the roomiest rooms grow a small colour-matched village
# cluster. Off -> no house obstacles at all: the `_scatter_houses` pass is
# skipped and draws no RNG, so the small-obstacle scatter stream is undisturbed.
TERRAIN_BUILDINGS: bool = True

# The thin elite / shield / status-effect rings drawn at the collider edge of a
# *sprited* enemy read like a collision circle. Off by default -- a sprited enemy
# is just its sprite. Primitive-fallback enemies (no sprite) always keep the
# rings, since with no art they are the only state cue. Independent of the
# developer collider overlay (F7 / dev menu), which draws the true colliders.
SHOW_ENEMY_STATE_RINGS: bool = False

# --- Enemy navigation (flow-field pathfinding) --------------------------
# On since M6 profiling (journals/journal.md "Planned Phase -- Enemy navigation").
# PlayingState owns a dual-resolution `NavField` toward the player: chasers and
# the FSM movers sample its gradient instead of steering straight, so they route
# LD-9 D9: how far the shared flow field is filled, as **path** cost in world
# pixels (an orthogonal nav step costs one cell, 32 or 48 px, for either class).
# A full-world fill was 37.9 ms a repath on a height-map world -- the islands are
# five times the floor of an LD-8 world -- and nearly all of it went on cells no
# enemy would ever walk from.
#
# Safe only because enemies now give up (see the aggro rules): one that is not
# pursuing needs no route, and one that is has an aggro range in the hundreds of
# pixels plus a timer.
#
# The value is measured, not guessed. This bounds the **path**, not the straight
# line, and on a terraced island a cell 300 px away can be a long walk to a
# staircase and back. Sampled over three worlds, for cells within 600 px
# straight-line of the target (the widest aggro range) the path cost runs
# p50 513, p90 1858, p95 2590, p99 3655, max 6058 -- so:
#
#     cap 3000 -> 97.5% of them routed,  6.3 ms
#     cap 4500 -> 99.7%,                 9.4 ms      <- chosen
#     cap 6000 -> 99.8%,                14.1 ms
#     unbounded -> 100%,                37.9 ms
#
# An enemy outside the bound keeps `steer_at`'s bearing fallback, so it still
# moves; it just has no routed path, and its pursuit timer ends the attempt.
# `None` restores the unbounded fill.
NAV_FILL_MAX_COST: int | None = 4500

# through doorways and around obstacle clusters. `resolve_movement` stays the
# final per-step guard. Crowded-scene cost (~220 enemies): steady p90 ~5 ms/frame
# for the whole update, with one staggered ~4 ms field rebuild every 0.2 s.
# Set False for the old straight-steering behaviour.
ENEMY_PATHFINDING: bool = True
# Seconds between full field rebuilds toward the player (also rebuilt early once
# the player drifts a couple of navigation cells from the last rebuild target).
ENEMY_NAV_REBUILD_INTERVAL: float = 0.4

# --- Colours (RGB) ---------------------------------------------------------
COLOR_BG = (16, 16, 22)
COLOR_GRID = (32, 33, 44)
COLOR_WORLD_BORDER = (70, 72, 96)
COLOR_PLAYER = (90, 200, 255)
COLOR_PLAYER_OUTLINE = (220, 245, 255)
COLOR_TEXT = (230, 230, 238)
COLOR_TEXT_DIM = (150, 150, 165)
COLOR_ACCENT = (255, 205, 90)
COLOR_DEBUG = (120, 255, 140)         # solid bodies in the dev collider overlay
COLOR_DEBUG_SOFT = (70, 150, 95)      # pickup / trigger radii in that overlay
COLOR_DEBUG_HIT = (255, 120, 255)     # projectile hitboxes in that overlay
COLOR_DEBUG_REACH = (255, 180, 90)    # weapon / summon reach rings (CB-2) in that overlay
COLOR_DEBUG_KNOCK = (120, 200, 255)   # live `_knock` bump/hit impulse vectors (CB-3)
COLOR_DAMAGE_IN = (235, 70, 70)      # damage the hero takes -- floating red numbers

# --- Start menu ----------------------------------------------------------
# The start screen has its own black / white palette; every other screen
# keeps the COLOR_* palette above.
MENU_BG = (0, 0, 0)
MENU_FG = (170, 170, 170)
MENU_FG_DIM = (0, 0, 0)
# Optional full-screen title art, drawn over the fallback title text (the text
# shows only when this file is missing). MENU_SCRIM is a translucent panel (RGBA)
# laid over the art behind the option list so the white text stays readable.
MENU_TITLE_IMAGE: str = "ui/start_screen/title.png"
# Full-screen backdrop, drawn under the logo; falls back to MENU_TITLE_IMAGE,
# then to the flat MENU_BG fill.
MENU_BACKGROUND_IMAGE: str = "ui/start_screen/menu_background.png"
# The game logo, drawn above the options panel; falls back to rendered text.
MENU_LOGO_IMAGE: str = "ui/start_screen/text_title.png"
MENU_SCRIM = (0, 0, 0, 185)

# Game instructions, surfaced on the character-select screen (they lived on the
# start menu until the hero-preview rework). A (label, keys) grid plus free
# notes; the select screen renders them at ~85% of its body font, between the
# difficulty line and the nav hint.
MENU_INSTRUCTIONS: dict = {
    "rows": [
        ("Move", "WASD / Arrows"),
        ("Pause", "ESC"),
        ("Mute", "M"),
        ("Debug overlay", "F1"),
    ],
    "notes": [
        "Weapons fire on their own.",
        "Survive, level up, beat the boss.",
    ],
}

# --- Audio ---------------------------------------------------------------
# Master-volume step for the Options screen (0..1). The slider snaps to this
# grid; AudioManager.set_volume() clamps to [0, 1].
VOLUME_STEP: float = 0.05

# --- Entity limits (graceful degradation, not crashes, when exceeded) -----
# Absolute enemy concurrency ceiling -- a perf safety net, rarely the real
# limiter. The live limit is SpawnDirector.enemy_count_cap(): it starts at
# ENEMY_COUNT_BASE and grows by ENEMY_COUNT_STEP every ENEMY_COUNT_STEP_PERIOD
# seconds of *in-game* time (the value the HUD timer shows -- not wall clock),
# the step scaled by the run's difficulty. BASE + STEP are tuned so the Normal
# schedule tracks the old fixed per-phase soft caps (40 / 70 / 100 / 130 / 150).
ENEMY_COUNT_HARD_CAP: int = 600
ENEMY_COUNT_BASE: int = 40
ENEMY_COUNT_STEP: int = 5
ENEMY_COUNT_STEP_PERIOD: float = 20.0
MAX_PROJECTILES: int = 800
MAX_PARTICLES: int = 1200
MAX_DAMAGE_NUMBERS: int = 200

# --- Difficulty (chosen per run on the character-select screen) ----------
# Normal is the shipped game. A level resolves to four independent factors on
# SpawnDirector, each its own tuning knob:
#   spawn_rate             - divides the spawn interval (higher => more spawns)
#   timeline_pace          - run_duration is divided by this, so harder enemy
#                            types and the boss arrive sooner and the run ends
#                            sooner
#   stat_ramp_pace         - multiplies elapsed when ramping enemy HP / speed --
#                            the inverse of the timeline division, so the full
#                            stat ramp is still reached by the (earlier) run end
#   enemy_count_step_scale - scales the +ENEMY_COUNT_STEP growth of the live
#                            enemy ceiling, so a faster run also gets a bigger
#                            crowd (steps of +5 / +8 / +10 per period)
DIFFICULTIES: dict[str, dict[str, float]] = {
    "normal":     {"spawn_rate": 1.0,  "timeline_pace": 1.0,
                   "stat_ramp_pace": 1.0,  "enemy_count_step_scale": 1.0},
    "fast":       {"spawn_rate": 1.25, "timeline_pace": 1.25,
                   "stat_ramp_pace": 1.25, "enemy_count_step_scale": 1.5},
    "super_fast": {"spawn_rate": 1.5,  "timeline_pace": 1.5,
                   "stat_ramp_pace": 1.5,  "enemy_count_step_scale": 2.0},
}
DIFFICULTY_ORDER: tuple[str, ...] = ("normal", "fast", "super_fast")
DIFFICULTY_DEFAULT: str = "normal"
DIFFICULTY_LABELS: dict[str, str] = {
    "normal": "Normal", "fast": "Fast", "super_fast": "Super Fast"}

# --- Player defaults -----------------------------------------------------
# Mirrors the stat list in spec section 3.1. Concrete hero data will move to
# data/characters.json in Milestone 6; kept here now so Phase 1 has one source.
PLAYER_DEFAULTS = {
    "max_hp": 100.0,
    "move_speed": 260.0,          # world pixels / second
    "armor": 0.0,                  # flat damage reduction
    "damage_multiplier": 1.0,
    "attack_speed_multiplier": 1.0,
    "projectile_speed_multiplier": 1.0,
    "area_multiplier": 1.0,        # scales every weapon's area/size
    "pickup_radius": 90.0,
    "luck": 0.0,
    "crit_chance": 0.0,            # 0..1, added on top of luck
    "crit_damage": 0.0,            # added to the base 2.0x crit multiplier
    "xp_gain": 0.0,                # +fraction of XP from gems
}
PLAYER_RADIUS: int = 10

# Sprite seating: a rig's `anchor` pixel lands on `entity.pos` (the collider
# centre), and rig anchors sit at the feet -- so the body renders entirely above
# the collision circle. This drops every character sprite down by this fraction
# of the collider radius, lifting `entity.pos` into the lower torso so more of
# the sprite sits inside the circle. Render-only: collision, hit tests and the
# depth sort keep using the unshifted `entity.pos`. 0.0 == no shift.
SPRITE_ANCHOR_DROP: float = 0.83

# --- Run structure (spec 3.8) ----------------------------------------
# Target run length. Spec suggests ~15-20 min but explicitly allows tuning
# "after playtesting". Milestone 10 playtests: at 900 s a solid run stalls
# around 7-8 min, so the boss was almost never reached. Pulled to 10 min so a
# competent run actually finishes the loop; the boss still lands near the end.
RUN_DURATION_SECONDS: float = 600.0
BOSS_FRACTION: float = 0.95   # boss spawns at 95% of the run (~570 s)

# --- Combat: incoming damage -----------------------------------------
# Contact and hazard damage land as discrete "bites" this many seconds apart,
# not once per frame. Armor is a flat per-hit subtraction, so a per-frame slice
# (rate / fps) would be fully absorbed -- see journals/BUG_JOURNAL.md #1. Each
# bite is `rate * interval` before armor, so the pre-armor DPS is unchanged.
# Individual attacks may override this via `contact_interval` (enemies / boss)
# or `hazard_tick` (warlock hazards). Keep `rate * interval` a healthy multiple
# of the largest expected armor, or an armored hero goes immune to that attack:
#     interval > armor / (rate * bulwark)
INCOMING_TICK_INTERVAL: float = 0.5

# --- Spatial grid -------------------------------------------------------
# Broad-phase collision cell size. Roughly 2x the biggest common entity.
GRID_CELL_SIZE: int = 96

# --- Physics: bumping & knockback (CB-3) --------------------------------
# Every mobile body carries a `weight` (enemies: data/enemies.json, fallback
# radius/2; hero: PLAYER_WEIGHT; boss: inf). Bumps between overlapping bodies
# and weapon hits both run through `combat.knockback.knock_split`, which shares
# the impulse by the *other* body's weight fraction and amplifies it by the
# weight gap:  total = base * (1 + BUMP_DIFF_GAIN * |dw| / sum_w).
#   * a bump's base    = BUMP_GAIN * penetration_px
#   * a hit's base      = HIT_KNOCK_GAIN * weapon_weight  (weight 0 -> no push)
# The resulting push is added to the body's `_knock` accumulator, which decays
# by pow(BUMP_DECAY, dt) each frame (same curve enemies already used for
# projectile knockback) and is integrated into movement via resolve_movement.
# All five are playtest knobs -- see journals/combat_balance_journal.md CB-3/H.
PLAYER_WEIGHT: float = 40.0
BUMP_GAIN: float = 12.0          # penetration px -> bump impulse
BUMP_DIFF_GAIN: float = 2.0      # how hard a weight mismatch amplifies the shove
BUMP_DECAY: float = 0.001        # `_knock *= pow(BUMP_DECAY, dt)` per frame (~0.7 s fade)
HIT_KNOCK_GAIN: float = 2.5      # weapon weight -> hit impulse base

# --- Debug key bindings (see spec section 9) ---------------------------
# Raw SDL2 keycodes (== pygame.K_F1 .. pygame.K_F7). Hardcoded rather than read
# from `pygame` because this module is imported before `pygame.init()` and, in
# the pygbag/browser build, `pygame.K_*` and the `pygame.constants` submodule
# are not available that early. These SDLK values are fixed by SDL and never
# change; `game/game.py` compares them against `event.key`.
DEBUG_KEYS = {
    "toggle_overlay": 1073741882,       # K_F1
    "spawn_enemy": 1073741883,          # K_F2
    "grant_xp": 1073741884,             # K_F3
    "force_level_up": 1073741885,       # K_F4
    "spawn_boss": 1073741886,           # K_F5
    "toggle_invuln": 1073741887,        # K_F6
    "toggle_collision_vis": 1073741888,  # K_F7
}

# Start with the debug overlay hidden; F1 toggles it. Debug tools are never
# required for normal play.
DEBUG_OVERLAY_DEFAULT: bool = False


# --- Browser (pygbag) profile ---------------------------------------------
def apply_web_profile() -> None:
    """Mutate the module-level constants for the WebAssembly build. Call once at
    startup, before `Game()` is constructed (see `main.py` / `main_web.py`).

    * `SAVE_ENABLED = False` -- a browser tab has no durable writable filesystem.
    * `FPS = 60` -- the page composites at ~60 Hz; targeting 120 just spends
      WASM budget on frames that are never presented.
    * `1280x720` render target at `CAMERA_ZOOM = 1.2` -- that is the pygbag
      canvas size, so there is no downscale, and `1280 / 1.2 == 1600 / 1.5`
      keeps the visible world extent (and on-screen sprite size) identical to
      the desktop build while cutting per-frame blit work by ~35%.

    Everything reads these at call time (the one default-arg capture,
    `systems.camera.Camera`, is overridden by an explicit argument in
    `PlayingState`), so a plain reassignment here propagates.
    """
    global SAVE_ENABLED, FPS, SCREEN_WIDTH, SCREEN_HEIGHT, CAMERA_ZOOM
    SAVE_ENABLED = False
    FPS = 60
    SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
    CAMERA_ZOOM = 1.2
