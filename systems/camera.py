"""Camera: maps world coordinates to screen coordinates.

The camera follows a target (the player) with light smoothing and is clamped so
it never shows anything outside the world rectangle (spec 5.1: "Camera never
reveals invalid map regions"). Implemented in Phase 1 already because every
render call needs world->screen translation.
"""
from __future__ import annotations

import pygame

from game import config


class Camera:
    def __init__(self, world_width: int, world_height: int,
                 view_width: int = config.SCREEN_WIDTH,
                 view_height: int = config.SCREEN_HEIGHT) -> None:
        self.world_width = world_width
        self.world_height = world_height
        self.view_width = view_width
        self.view_height = view_height
        # Top-left of the view in world space.
        self.pos = pygame.Vector2(0, 0)
        # Higher = snappier. Frame-rate independent (see update()).
        self.follow_lerp = 8.0

    def _clamp(self) -> None:
        max_x = max(0, self.world_width - self.view_width)
        max_y = max(0, self.world_height - self.view_height)
        self.pos.x = min(max(self.pos.x, 0), max_x)
        self.pos.y = min(max(self.pos.y, 0), max_y)

    def snap_to(self, target: pygame.Vector2) -> None:
        """Instantly centre on target (used on run start / respawn)."""
        self.pos.x = target.x - self.view_width / 2
        self.pos.y = target.y - self.view_height / 2
        self._clamp()

    def update(self, dt: float, target: pygame.Vector2) -> None:
        desired = pygame.Vector2(target.x - self.view_width / 2,
                                 target.y - self.view_height / 2)
        # Exponential smoothing that behaves the same at any frame rate.
        t = 1.0 - pow(2.718281828, -self.follow_lerp * dt)
        self.pos += (desired - self.pos) * t
        self._clamp()

    # --- coordinate transforms -----------------------------------------
    def world_to_screen(self, world_pos: pygame.Vector2) -> tuple[float, float]:
        return (world_pos.x - self.pos.x, world_pos.y - self.pos.y)

    def screen_to_world(self, screen_pos: tuple[float, float]) -> pygame.Vector2:
        return pygame.Vector2(screen_pos[0] + self.pos.x,
                              screen_pos[1] + self.pos.y)

    def visible_rect(self) -> pygame.Rect:
        """World-space rectangle currently on screen (for culling / spawning)."""
        return pygame.Rect(int(self.pos.x), int(self.pos.y),
                           self.view_width, self.view_height)
