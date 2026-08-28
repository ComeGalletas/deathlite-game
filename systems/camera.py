"""Camera: maps world coordinates to screen coordinates.

The camera follows a target (the player) with light smoothing and is clamped so
it never shows anything outside the world rectangle (spec 5.1: "Camera never
reveals invalid map regions"). Implemented in Phase 1 already because every
render call needs world->screen translation.

`zoom` is a draw-time magnification. `world_to_screen` multiplies by it, so the
view shows `view_width / zoom` x `view_height / zoom` world pixels blown up to
fill the `view_width` x `view_height` screen. `zoom = 1.0` is a plain
translation, identical to the pre-zoom camera. `pos` is always the world-space
top-left of the visible region, so world-space callers (`worldx - camera.pos.x`)
stay valid regardless of zoom -- only the final pixel step is scaled.
"""
from __future__ import annotations

import pygame

from game import config


class Camera:
    def __init__(self, world_width: int, world_height: int,
                 view_width: int = config.SCREEN_WIDTH,
                 view_height: int = config.SCREEN_HEIGHT,
                 zoom: float = 1.0) -> None:
        self.world_width = world_width
        self.world_height = world_height
        self.view_width = view_width
        self.view_height = view_height
        self.zoom = max(0.01, float(zoom))
        # Top-left of the visible world region, in world space.
        self.pos = pygame.Vector2(0, 0)
        # Higher = snappier. Frame-rate independent (see update()).
        self.follow_lerp = 8.0

    # --- geometry -----------------------------------------------------
    def world_span(self) -> tuple[float, float]:
        """Size, in world pixels, of the region currently on screen."""
        return (self.view_width / self.zoom, self.view_height / self.zoom)

    def _clamp(self) -> None:
        span_w, span_h = self.world_span()
        # A world smaller than the visible span is centred; otherwise the view
        # is kept fully inside the world.
        if self.world_width <= span_w:
            self.pos.x = (self.world_width - span_w) / 2.0
        else:
            self.pos.x = min(max(self.pos.x, 0.0), self.world_width - span_w)
        if self.world_height <= span_h:
            self.pos.y = (self.world_height - span_h) / 2.0
        else:
            self.pos.y = min(max(self.pos.y, 0.0), self.world_height - span_h)

    def snap_to(self, target: pygame.Vector2) -> None:
        """Instantly centre on target (used on run start / respawn)."""
        span_w, span_h = self.world_span()
        self.pos.x = target.x - span_w / 2.0
        self.pos.y = target.y - span_h / 2.0
        self._clamp()

    def update(self, dt: float, target: pygame.Vector2) -> None:
        span_w, span_h = self.world_span()
        desired = pygame.Vector2(target.x - span_w / 2.0,
                                 target.y - span_h / 2.0)
        # Exponential smoothing that behaves the same at any frame rate.
        t = 1.0 - pow(2.718281828, -self.follow_lerp * dt)
        self.pos += (desired - self.pos) * t
        self._clamp()

    # --- coordinate transforms -----------------------------------------
    def world_to_screen(self, world_pos: pygame.Vector2) -> tuple[float, float]:
        return ((world_pos.x - self.pos.x) * self.zoom,
                (world_pos.y - self.pos.y) * self.zoom)

    def screen_to_world(self, screen_pos: tuple[float, float]) -> pygame.Vector2:
        return pygame.Vector2(screen_pos[0] / self.zoom + self.pos.x,
                              screen_pos[1] / self.zoom + self.pos.y)

    def visible_rect(self) -> pygame.Rect:
        """World-space rectangle currently on screen (for culling / spawning)."""
        span_w, span_h = self.world_span()
        return pygame.Rect(int(self.pos.x), int(self.pos.y),
                           int(round(span_w)), int(round(span_h)))
