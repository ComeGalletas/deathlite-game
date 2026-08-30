"""The two narrow interfaces the AI package needs from the running game.

`entities/ai/` depends only on these Protocols -- never on `PlayingState`. The
host (PlayingState in the game, a small fake in tests) supplies one object that
satisfies both. This replaces the 11-field `EnemyContext` grab-bag.
"""
from __future__ import annotations

from typing import Protocol

import pygame


class Perception(Protocol):
    """Read-only view of the world for one AI tick."""

    dt: float
    now: float                       # elapsed run time, seconds (was ctx has none)
    player_pos: pygame.Vector2
    player: object
    rng: object

    def nav_dir(self, pos: pygame.Vector2, radius: float) -> pygame.Vector2:
        """Flow-field steering unit vector toward the player from `pos` for an
        enemy of `radius`; a zero vector means "no route -- steer straight"."""

    def neighbors(self, pos: pygame.Vector2, radius: float) -> list:
        """Other enemies whose broad-phase cell overlaps the circle."""

    def obstacles_near(self, pos: pygame.Vector2, radius: float) -> list:
        """Static obstacles whose broad-phase cell overlaps the circle."""

    def is_walkable(self, pos: pygame.Vector2, radius: float) -> bool: ...

    def resolve_movement(self, prev: pygame.Vector2, new: pygame.Vector2,
                         radius: float) -> pygame.Vector2: ...


class Combat(Protocol):
    """Side-effecting actions an AI may request of the game."""

    def fire_projectile(self, **kwargs) -> None: ...

    def summon(self, enemy_id: str, pos: pygame.Vector2, count: int) -> None: ...

    def explosion(self, pos: pygame.Vector2, radius: float,
                  damage: float) -> None: ...

    def spawn_hazard(self, pos: pygame.Vector2, radius: float, dps: float,
                     duration: float,
                     tick_interval: float | None = None) -> None: ...

    def melee_hit(self, pos: pygame.Vector2, radius: float, damage: float,
                 duration: float) -> None: ...

    def report_damage(self, amount: float) -> None: ...
