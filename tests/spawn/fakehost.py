"""A stub `spawn.host.Host` for the placement, master, locality and
population tests.

A flat 4000 x 4000 world with two islands side by side (id 0 on the left,
id 1 on the right, tree neighbours) joined by a one-tile bridge across
the middle, a hand-laid set of spawn points, a player, a view rectangle,
and a list of "live" bodies. Everything is a plain attribute the test can
poke. Enemies are `SimpleNamespace`s; `sleep` / `wake` round-trip them
through `DormantEnemy` the way the run does.
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import pygame

from spawn.population import DormantEnemy
from world.layout import ResourcePoint, SpawnPoint

W = 4000
ROOM0 = pygame.Rect(0, 0, 1900, 4000)
ROOM1 = pygame.Rect(2100, 0, 1900, 4000)
BRIDGE = pygame.Rect(1900, 1968, 200, 64)      # joins the two islands


def grid_points(room_id: int, rect: pygame.Rect, step: int = 400,
                floor_of=lambda x, y: 0, clearance="large", tags=frozenset()) -> list:
    out = []
    for y in range(rect.top + step // 2, rect.bottom, step):
        for x in range(rect.left + step // 2, rect.right, step):
            out.append(SpawnPoint(room_id, floor_of(x, y), float(x), float(y),
                                  clearance, frozenset(tags)))
    return out


class FakeHost:
    def __init__(self, points=None, seed: int = 1) -> None:
        self.elapsed = 0.0
        self.rng = random.Random(seed)
        self.difficulty = "normal"
        pts = points if points is not None else (grid_points(0, ROOM0) + grid_points(1, ROOM1))
        self.layout = SimpleNamespace(spawn_points=pts, resource_points=[
            ResourcePoint(0, 0, 100.0, 100.0, "chest")])
        self.rooms = {
            0: SimpleNamespace(id=0, kind="start", neighbors=[1], rect=ROOM0,
                               center=pygame.Vector2(ROOM0.center)),
            1: SimpleNamespace(id=1, kind="combat", neighbors=[0], rect=ROOM1,
                               center=pygame.Vector2(ROOM1.center))}
        self.player = pygame.Vector2(1000, 2000)
        self.heading = pygame.Vector2()          # current move direction
        self.view = pygame.Rect(0, 0, 1000, 600)
        self.view.center = (int(self.player.x), int(self.player.y))
        self.floor = 0
        self.floor_of = lambda pos: 0
        self.blocked = []            # (centre, radius) discs that are not floor
        self.live: list = []
        # Every shipped enemy's radius, so the late phases can roll anything.
        from game.content import get_content
        self.radii = {eid: float(d["radius"]) for eid, d in get_content().enemies.items()}
        self.events: list = []
        self.handlers: dict = {}
        self.hp_fraction = 1.0
        self.poofs: list = []
        self.fallback = None         # what `fallback_point` answers
        # `None` -> every enemy counts as pursuing (the S3 tests never sleep
        # anything); a set -> only those enemies are.
        self.pursuing: set | None = None

    # --- protocol -------------------------------------------------------
    def player_pos(self):
        return self.player

    def player_heading(self):
        return pygame.Vector2(self.heading)

    def player_floor(self):
        return self.floor

    def visible_rect(self):
        return self.view.copy()

    def is_walkable(self, pos, radius) -> bool:
        if not (0 <= pos.x <= W and 0 <= pos.y <= W):
            return False
        return not any((pos - c).length() < r + radius for c, r in self.blocked)

    def floor_at(self, pos) -> int:
        return self.floor_of(pos)

    def room_at(self, pos):
        for r in self.rooms.values():
            if r.rect.collidepoint(pos.x, pos.y):
                return r
        return None

    def room(self, room_id):
        return self.rooms[room_id]

    def corridor_at(self, pos):
        return (0, 1) if BRIDGE.collidepoint(pos.x, pos.y) else None

    def fallback_point(self):
        return self.fallback

    def live_count(self) -> int:
        return len(self.live)

    def live_enemies(self):
        return self.live

    def enemy_radius(self, enemy_id) -> float:
        return self.radii[enemy_id]

    def make_enemy(self, enemy_id, x, y, hp_mult, spd_mult, owner="direct"):
        e = SimpleNamespace(enemy_id=enemy_id, pos=pygame.Vector2(x, y),
                            radius=self.radii[enemy_id], hp_mult=hp_mult,
                            spd_mult=spd_mult, alive=True, owner=owner,
                            hp=10.0 * hp_mult, max_hp=10.0 * hp_mult, shield_hp=0.0,
                            speed=100.0 * spd_mult, status=None,
                            spawned_at=self.elapsed, recycles=0,
                            moving=False, attacking=False)
        self.live.append(e)
        return e

    def neighbors_near(self, pos, radius):
        return [e for e in self.live if (e.pos - pos).length() <= radius + 100]

    def owner_of(self, enemy) -> str:
        return enemy.owner

    def is_pursuing(self, enemy) -> bool:
        return True if self.pursuing is None else (id(enemy) in self.pursuing)

    def sleep(self, enemy) -> DormantEnemy:
        self.live.remove(enemy)
        return DormantEnemy(enemy.enemy_id, enemy.pos.x, enemy.pos.y, enemy.hp,
                            enemy.max_hp, enemy.shield_hp, enemy.speed,
                            status=enemy.status, owner=enemy.owner,
                            spawned_at=enemy.spawned_at, recycles=enemy.recycles)

    def wake(self, rec: DormantEnemy, x, y):
        e = SimpleNamespace(enemy_id=rec.enemy_id, pos=pygame.Vector2(x, y),
                            radius=self.radii[rec.enemy_id], hp_mult=1.0, spd_mult=1.0,
                            alive=True, owner=rec.owner, hp=rec.hp, max_hp=rec.max_hp,
                            shield_hp=rec.shield_hp, speed=rec.speed, status=rec.status,
                            spawned_at=rec.spawned_at, woke_from=rec,
                            recycles=rec.recycles, moving=False, attacking=False)
        self.live.append(e)
        return e

    def relocate(self, enemy, x, y):
        enemy.pos.update(x, y)

    # --- the watchdog's questions (S5) ---------------------------------
    def player_radius(self) -> float:
        return 16.0

    def wants_to_move(self, enemy) -> bool:
        return enemy.moving

    def is_attacking(self, enemy) -> bool:
        return enemy.attacking

    def poof(self, pos):
        self.poofs.append((pos.x, pos.y))

    def publish(self, event, **payload):
        self.events.append((event, payload))
        for h in self.handlers.get(event, ()):
            h(**payload)

    def subscribe(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    # --- the pacing's questions (S6) -----------------------------------
    def player_hp_fraction(self) -> float:
        return self.hp_fraction

    def player_max_hp(self) -> float:
        return 100.0
