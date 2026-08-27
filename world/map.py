"""The playable world.

Phase 3: `GameMap` wraps a procedural `WorldLayout` (rooms + corridors). It
answers "is this walkable?", slides entities along walls, picks legal spawn
points, and draws the floor / walls / void. Without a seed it degrades to one
big rectangular room (used by tests and any non-run context).
"""
from __future__ import annotations

import random

import pygame

from game import config
from world.procedural import Room, WorldLayout, generate_world

_VOID = (10, 10, 14)
_FLOOR = (26, 26, 34)
_FLOOR_SPECIAL = (34, 30, 46)
_WALL = (68, 70, 92)
_GRID = (32, 33, 44)

_SPECIAL_FLOORS = {
    "start": (24, 34, 30), "boss": (44, 22, 26),
    "shrine": (30, 34, 48), "treasure": (44, 40, 24),
    "fountain": (22, 38, 44), "altar": (40, 24, 40),
    "merchant": (40, 36, 28), "elite_arena": (46, 26, 30),
}


class GameMap:
    def __init__(self, seed: int | None = None) -> None:
        if seed is None:
            self.layout: WorldLayout | None = None
            self.width = config.WORLD_WIDTH
            self.height = config.WORLD_HEIGHT
            self._rects = [pygame.Rect(0, 0, self.width, self.height)]
            self.obstacles = []
        else:
            self.layout = generate_world(seed)
            b = self.layout.bounds
            self.width, self.height = b.width, b.height
            self._rects = self.layout.walkable_rects()
            self.obstacles = self.layout.obstacles

    # --- geometry ------------------------------------------------
    @property
    def center(self) -> pygame.Vector2:
        if self.layout is not None:
            return self.layout.room(self.layout.start_id).center
        return pygame.Vector2(self.width / 2, self.height / 2)

    def rect(self) -> pygame.Rect:
        return pygame.Rect(0, 0, self.width, self.height)

    def room_at(self, pos: pygame.Vector2) -> Room | None:
        if self.layout is None:
            return None
        for r in self.layout.rooms:
            if r.rect.collidepoint(pos.x, pos.y):
                return r
        return None

    # --- walkability / movement -------------------------------
    def _point_ok(self, x: float, y: float) -> bool:
        for rc in self._rects:
            if rc.collidepoint(x, y):
                return True
        return False

    def is_walkable(self, pos: pygame.Vector2, radius: float = 0.0) -> bool:
        if not self._point_ok(pos.x, pos.y):
            return False
        if radius > 0 and not (
                self._point_ok(pos.x + radius, pos.y)
                and self._point_ok(pos.x - radius, pos.y)
                and self._point_ok(pos.x, pos.y + radius)
                and self._point_ok(pos.x, pos.y - radius)):
            return False
        for o in self.obstacles:
            rr = o.radius + radius
            if (pos.x - o.pos.x) ** 2 + (pos.y - o.pos.y) ** 2 < rr * rr:
                return False
        return True

    def blocking_obstacle_hit(self, pos: pygame.Vector2, radius: float):
        """First projectile-blocking obstacle overlapping the circle, or None."""
        for o in self.obstacles:
            if not o.blocks_projectiles:
                continue
            rr = o.radius + radius
            if (pos.x - o.pos.x) ** 2 + (pos.y - o.pos.y) ** 2 < rr * rr:
                return o
        return None

    def resolve_movement(self, prev: pygame.Vector2, new: pygame.Vector2,
                         radius: float) -> pygame.Vector2:
        """Move toward `new`; if it hits a wall, slide along one axis."""
        if self.is_walkable(new, radius):
            return new
        slide_x = pygame.Vector2(new.x, prev.y)
        if self.is_walkable(slide_x, radius):
            return slide_x
        slide_y = pygame.Vector2(prev.x, new.y)
        if self.is_walkable(slide_y, radius):
            return slide_y
        return pygame.Vector2(prev)

    def random_point_in_room(self, room: Room, rng: random.Random,
                             margin: float = 24.0) -> pygame.Vector2:
        r = room.rect
        return pygame.Vector2(
            rng.uniform(r.left + margin, r.right - margin),
            rng.uniform(r.top + margin, r.bottom - margin))

    def offscreen_spawn_point(self, camera, rng: random.Random) -> pygame.Vector2:
        """A walkable point just outside the view: prefer the closest rooms that
        are not fully on screen, so pressure stays on the player even though the
        world is large."""
        view = camera.visible_rect()
        vc = pygame.Vector2(view.center)

        if self.layout is None:
            for _ in range(20):
                p = pygame.Vector2(rng.uniform(0, self.width), rng.uniform(0, self.height))
                if not view.collidepoint(p.x, p.y):
                    return p
            return pygame.Vector2(self.width / 2, self.height / 2)

        rooms = sorted(self.layout.rooms, key=lambda r: (r.center - vc).length_squared())
        room = rng.choice(rooms[:3])
        min_dist_sq = 220.0 ** 2
        best = room.center
        for _ in range(12):
            p = self.random_point_in_room(room, rng)
            if not view.collidepoint(p.x, p.y) and (p - vc).length_squared() > min_dist_sq:
                return p
            best = p
        return best

    # --- render -----------------------------------------------
    def draw(self, surface: pygame.Surface, camera) -> None:
        surface.fill(_VOID)
        ox, oy = camera.pos.x, camera.pos.y

        if self.layout is None:
            floor = pygame.Rect(-ox, -oy, self.width, self.height)
            pygame.draw.rect(surface, _FLOOR, floor)
            pygame.draw.rect(surface, _WALL, floor, width=3)
            self._draw_grid(surface, camera, floor)
            return

        for c in self.layout.corridors:
            pygame.draw.rect(surface, _FLOOR, c.rect.move(-ox, -oy))
        for r in self.layout.rooms:
            scr = r.rect.move(-ox, -oy)
            pygame.draw.rect(surface, _SPECIAL_FLOORS.get(r.kind, _FLOOR), scr)
            pygame.draw.rect(surface, _WALL, scr, width=3)

        view = camera.visible_rect().inflate(80, 80)
        for o in self.obstacles:
            if not view.collidepoint(o.pos.x, o.pos.y):
                continue
            pygame.draw.circle(surface, o.color,
                               (int(o.pos.x - ox), int(o.pos.y - oy)), o.radius)
            pygame.draw.circle(surface, _WALL,
                               (int(o.pos.x - ox), int(o.pos.y - oy)), o.radius, 2)

    def _draw_grid(self, surface, camera, floor_rect) -> None:
        step = 128
        for x in range(0, self.width + step, step):
            sx = x - camera.pos.x
            pygame.draw.line(surface, _GRID, (sx, floor_rect.top), (sx, floor_rect.bottom))
        for y in range(0, self.height + step, step):
            sy = y - camera.pos.y
            pygame.draw.line(surface, _GRID, (floor_rect.left, sy), (floor_rect.right, sy))
