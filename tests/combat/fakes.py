"""Light stand-ins for the PLAYING state, for resolver / effects tests that
should not build a world: a `PlayingState`-shaped namespace with a real
projectile pool, a grid that returns every enemy, and a hero with no
blessings. Shared by `test_bomb.py` and `test_stun.py` (six-weapon P1).
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import pygame

from combat.status import StatusState
from entities.projectile import Projectile
from systems.object_pool import Pool


class FakeEnemy:
    def __init__(self, x, y, hp=100.0, radius=10.0, weight=7.0):
        self.pos = pygame.Vector2(x, y)
        self.hp = hp
        self.max_hp = hp
        self.alive = True
        self.killed_by = ""
        self._knock = pygame.Vector2()
        self.recent_hits: dict = {}
        self.hit_streak: dict = {}
        self.radius = radius
        self.weight = weight
        self.is_elite = False
        self.status = StatusState()
        self.knocks: list = []
        self.anim = None

    def take_damage(self, amount, armor=0.0):
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0.0
            self.alive = False
        return amount

    def apply_knockback(self, direction, strength):
        self.knocks.append(strength)
        if direction.length_squared() > 1e-6:
            self._knock += pygame.Vector2(direction).normalize() * strength


class _Grid:
    def __init__(self, ps):
        self.ps = ps

    def query_circle(self, x, y, r):
        return list(self.ps.enemies)


class _Fx:
    """No blessings: no tag bonus, no vulnerability, no on-hit statuses."""
    on_hit = ()
    on_kill = ()
    soul_heal = 0

    @staticmethod
    def tag_bonus(tags, is_elite):
        return 0.0

    @staticmethod
    def vuln_bonus(tags, status):
        return 0.0

    @staticmethod
    def tuned(status, key):
        return 0.0


class _Numbers:
    def __init__(self):
        self.shown = []

    def add(self, pos, amount, crit):
        self.shown.append((amount, crit))


class _Particles:
    def burst(self, *a, **kw):
        pass


class _Shake:
    def add(self, *a):
        pass


class _Map:
    """Open ground: nothing blocks, no elevation."""
    @staticmethod
    def blocking_obstacle_hit(pos, radius):
        return None


class _Events:
    def publish(self, *a, **kw):
        pass


def fake_ps(enemies=(), rng=None, blocked=False):
    ps = SimpleNamespace()
    ps.enemies = list(enemies)
    ps.boss = None
    ps.rng = rng if rng is not None else random.Random(0)
    ps.stats = {"damage_dealt": 0.0, "kills": 0, "time": 0.0}
    ps.dev_mode = False
    ps._dev_no_damage = False
    weapons: list = []
    ps.player = SimpleNamespace(
        blessing_fx=_Fx(), trait="", pos=pygame.Vector2(), radius=10.0,
        weapons=weapons, hp=100.0, max_hp=100.0,
        weapon_by_id=lambda wid: next((w for w in weapons if w.weapon_id == wid), None),
        heal=lambda amt: None)
    ps.damage_numbers = _Numbers()
    ps.particles = _Particles()
    ps.shake = _Shake()
    ps.game = SimpleNamespace(events=_Events(), audio=SimpleNamespace(play_shoot=lambda: None))
    ps.projectiles = Pool(Projectile, 64)
    ps.hostiles = Pool(Projectile, 8)
    ps._explosions = []
    ps._trail_fx = []
    ps.grid = _Grid(ps)
    ps.game_map = _Map() if not blocked else SimpleNamespace(
        blocking_obstacle_hit=lambda pos, radius: object())
    ps._in_world_margin = lambda pos, margin: True
    ps._targetables = lambda: list(ps.enemies)

    def spawn_projectile(**kw):
        p = ps.projectiles.acquire()
        if p is None:
            return None
        kw.pop("visual", None)
        kw.setdefault("color", (255, 255, 255))
        p.reset(**kw)
        return p

    ps._spawn_projectile = spawn_projectile
    ps.hazards = []
    from game.states.playing.effects import TransientFx
    ps.fx = TransientFx(ps)
    return ps
