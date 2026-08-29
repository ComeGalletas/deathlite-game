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
# Soft round canopy shadow cast on the ground by each tree, drawn *over* the
# characters so a hero / enemy standing under a tree is slightly darkened
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
