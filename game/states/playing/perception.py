"""The per-frame view handed to every enemy and the boss.

`PlayingPerception` is the typed replacement for the `SimpleNamespace` that
`_enemy_context` used to build. It satisfies the `entities.ai` `Perception` +
`Combat` protocols (the boss duck-types the same attributes). One instance is
built per frame in `PlayingState._enemy_context` and shared across all actors.

Part of the split tracked in `journals/playing_state_refactor.md` (P6).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame


@dataclass
class PlayingPerception:
    # --- Perception -------------------------------------------------
    dt: float
    now: float
    player_pos: pygame.Vector2
    player: object
    rng: object
    nav_dir: Callable            # (pos, radius) -> Vector2  (zero == no route)
    neighbors: Callable          # (pos, radius) -> list[entity]
    obstacles_near: Callable     # (pos, radius) -> list[obstacle]
    is_walkable: Callable        # (pos, radius) -> bool
    resolve_movement: Callable   # (prev, new, radius) -> Vector2
    # --- Combat -----------------------------------------------------
    fire_projectile: Callable    # (**kwargs) -> None
    summon: Callable             # (enemy_id, pos, count) -> None
    explosion: Callable          # (pos, radius, damage) -> None
    spawn_hazard: Callable       # (pos, radius, dps, duration, tick_interval=None)
    melee_hit: Callable          # (pos, radius, damage, duration) -> None
    report_damage: Callable      # (amount) -> None
