"""What the spawn master is allowed to know about the run.

The master never imports `entities` or `game.states`. Everything it needs
-- where the player is, what is on screen, whether a spot is floor, how to
make an enemy -- comes through this protocol, implemented once on the run
side (`game/states/playing/spawning.py`) and once as a stub in the tests.
Keep it narrow: a new method here is a new thing the master depends on.
"""
from __future__ import annotations

from typing import Protocol

import pygame


class Host(Protocol):
    # --- the run's clock and dice -------------------------------------
    @property
    def elapsed(self) -> float: ...            # in-game seconds, pause-safe
    @property
    def rng(self): ...                         # the run's `random.Random`
    @property
    def layout(self): ...                      # `WorldLayout`, or None
    @property
    def difficulty(self) -> str: ...

    # --- the player ---------------------------------------------------
    def player_pos(self) -> pygame.Vector2: ...
    def player_heading(self) -> pygame.Vector2: ...   # current move dir, zero when still
    def player_floor(self) -> int | None: ...  # terrace level under the player
    def visible_rect(self) -> pygame.Rect: ...

    # --- the world ----------------------------------------------------
    def is_walkable(self, pos: pygame.Vector2, radius: float) -> bool: ...
    def floor_at(self, pos: pygame.Vector2) -> int: ...
    def room_at(self, pos: pygame.Vector2): ...        # a `Room` (id, kind, center, neighbors) or None
    def room(self, room_id: int): ...                  # the `Room` by id
    def corridor_at(self, pos: pygame.Vector2): ...    # (a, b) island ids of the bridge, or None
    def fallback_point(self) -> pygame.Vector2 | None: ...  # no layout / no points

    # --- enemies ------------------------------------------------------
    def live_count(self) -> int: ...
    def live_enemies(self) -> list: ...                # read-only view
    def enemy_radius(self, enemy_id: str) -> float: ...
    def make_enemy(self, enemy_id: str, x: float, y: float,
                   hp_mult: float, spd_mult: float, owner: str): ...   # constructs *and* adds
    def neighbors_near(self, pos: pygame.Vector2, radius: float) -> list: ...
    def owner_of(self, enemy) -> str: ...
    def is_pursuing(self, enemy) -> bool: ...          # aggro timer still running
    def sleep(self, enemy): ...                        # remove; return a `DormantEnemy`
    def wake(self, record, x: float, y: float): ...    # construct from the record and add
    def relocate(self, enemy, x: float, y: float) -> None: ...  # same object, new spot

    # --- the watchdog's questions (S5) -------------------------------
    def player_radius(self) -> float: ...
    def wants_to_move(self, enemy) -> bool: ...        # movement intent this frame
    def is_attacking(self, enemy) -> bool: ...         # mid wind-up or strike
    def poof(self, pos: pygame.Vector2) -> None: ...   # a vanish effect at `pos`

    # --- the bus ------------------------------------------------------
    def publish(self, event: str, **payload) -> None: ...
    def subscribe(self, event: str, handler) -> None: ...   # S6: the pacing signals

    # --- the pacing's questions (S6) ----------------------------------
    def player_hp_fraction(self) -> float: ...
    def player_max_hp(self) -> float: ...
