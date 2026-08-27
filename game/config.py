"""Central configuration.

All tunable constants live here so systems never hardcode magic numbers.
Keep this module dependency-free: everything may import it, it imports nothing
from the project.
"""
from __future__ import annotations

import pygame

# --- Display -----------------------------------------------------------------
SCREEN_WIDTH: int = 1280
SCREEN_HEIGHT: int = 720
FPS: int = 60
TITLE: str = "Death Lite Die"

# Largest delta time (seconds) a single frame is allowed to represent. Without
# this a stall (e.g. window drag) produces a huge dt that tunnels entities
# through walls / each other -- the classic "spiral of death".
MAX_DT: float = 1.0 / 20.0

# --- World -----------------------------------------------------------------
# Fallback size used only before a procedural layout exists (menus / tests).
WORLD_WIDTH: int = 3200
WORLD_HEIGHT: int = 3200

# Procedural world (Phase 3): a lattice of chunk cells, one room per cell,
# joined into a tree of corridors. See world/procedural.py.
CHUNK_SIZE: int = 720
WORLD_ROOM_COUNT: int = 16

# --- Colours (RGB) ---------------------------------------------------------
COLOR_BG = (16, 16, 22)
COLOR_GRID = (32, 33, 44)
COLOR_WORLD_BORDER = (70, 72, 96)
COLOR_PLAYER = (90, 200, 255)
COLOR_PLAYER_OUTLINE = (220, 245, 255)
COLOR_TEXT = (230, 230, 238)
COLOR_TEXT_DIM = (150, 150, 165)
COLOR_ACCENT = (255, 205, 90)
COLOR_DEBUG = (120, 255, 140)

# --- Entity limits (graceful degradation, not crashes, when exceeded) -----
MAX_ENEMIES: int = 600
MAX_PROJECTILES: int = 800
MAX_PARTICLES: int = 1200
MAX_DAMAGE_NUMBERS: int = 200

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
PLAYER_RADIUS: int = 16

# --- Run structure (spec 3.8) ----------------------------------------
# Target run length. Spec suggests ~15-20 min but explicitly allows tuning
# "after playtesting". Milestone 10 playtests: at 900 s a solid run stalls
# around 7-8 min, so the boss was almost never reached. Pulled to 10 min so a
# competent run actually finishes the loop; the boss still lands near the end.
RUN_DURATION_SECONDS: float = 600.0
BOSS_FRACTION: float = 0.95   # boss spawns at 95% of the run (~570 s)

# --- Spatial grid -------------------------------------------------------
# Broad-phase collision cell size. Roughly 2x the biggest common entity.
GRID_CELL_SIZE: int = 96

# --- Debug key bindings (see spec section 9) ---------------------------
DEBUG_KEYS = {
    "toggle_overlay": pygame.K_F1,
    "spawn_enemy": pygame.K_F2,
    "grant_xp": pygame.K_F3,
    "force_level_up": pygame.K_F4,
    "spawn_boss": pygame.K_F5,
    "toggle_invuln": pygame.K_F6,
    "toggle_collision_vis": pygame.K_F7,
}

# Start with the debug overlay hidden; F1 toggles it. Debug tools are never
# required for normal play.
DEBUG_OVERLAY_DEFAULT: bool = False
