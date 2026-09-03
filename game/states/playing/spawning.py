"""Enemy / boss spawning for PLAYING: the run's side of the spawn master.

`PlayingHost` is the `spawn.host.Host` protocol over `PlayingState` -- the
only view of the run the master gets -- and the one place `Enemy` objects
are constructed, with the run's HP/speed scaling applied. `EnemyControl`
keeps the names the rest of the state and the tests call (`tick_director`,
`spawn_enemy`, `summon`, `spawn_boss`) and forwards them to the master.

Reads `ps.director`, `ps.content`, `ps.game_map`, `ps.camera`, `ps.rng`,
`ps.stats`, `ps.grid`; appends to `ps.enemies` / sets `ps.boss`.
"""
from __future__ import annotations

import logging

import pygame

from types import SimpleNamespace

from entities.ai.components.aggro import is_aggroed
from entities.boss import Boss
from entities.enemy import Enemy
from game import config
from game.events import Events
from spawn.master import SpawnMaster
from spawn.population import DormantEnemy

log = logging.getLogger(__name__)


class PlayingHost:
    def __init__(self, ps) -> None:
        self.ps = ps
        self._subs: list = []

    @property
    def elapsed(self) -> float:
        return self.ps.stats["time"]

    @property
    def rng(self):
        return self.ps.rng

    @property
    def layout(self):
        return self.ps.game_map.layout

    @property
    def difficulty(self) -> str:
        return self.ps.difficulty

    def player_pos(self) -> pygame.Vector2:
        return self.ps.player.pos

    def player_heading(self) -> pygame.Vector2:
        return pygame.Vector2(self.ps.player._move_dir)

    def player_floor(self):
        layout = self.layout
        if layout is None:
            return None
        p = self.ps.player.pos
        meta = layout.tile_at(p.x, p.y)
        return meta.floor if meta is not None else None

    def visible_rect(self) -> pygame.Rect:
        return self.ps.camera.visible_rect()

    def is_walkable(self, pos, radius: float) -> bool:
        return self.ps.game_map.is_walkable(pos, radius)

    def floor_at(self, pos) -> int:
        layout = self.layout
        if layout is None:
            return 0
        meta = layout.tile_at(pos.x, pos.y)
        return meta.floor if meta is not None else 0

    def room_at(self, pos):
        return self.ps.game_map.room_at(pos)

    def room(self, room_id: int):
        return self.layout.room(room_id)

    def corridor_at(self, pos):
        layout = self.layout
        if layout is None:
            return None
        for c in layout.corridors:
            if c.rect.collidepoint(pos.x, pos.y):
                return (c.a, c.b)
        return None

    def fallback_point(self):
        return self.ps.game_map.offscreen_spawn_point(self.ps.camera, self.ps.rng)

    def live_count(self) -> int:
        return len(self.ps.enemies)

    def live_enemies(self) -> list:
        return self.ps.enemies

    def enemy_radius(self, enemy_id: str) -> float:
        return float(self.ps.content.enemy(enemy_id)["radius"])

    def make_enemy(self, enemy_id: str, x: float, y: float,
                   hp_mult: float, spd_mult: float, owner: str = "direct") -> Enemy:
        enemy = Enemy(enemy_id, self.ps.content.enemy(enemy_id), x, y)
        enemy.max_hp *= hp_mult
        enemy.hp = enemy.max_hp
        enemy.speed *= spd_mult
        enemy.spawn_owner = owner
        enemy.spawned_at = self.elapsed
        self.ps.enemies.append(enemy)
        return enemy

    # --- live <-> dormant (S4) ----------------------------------------
    def owner_of(self, enemy) -> str:
        return getattr(enemy, "spawn_owner", "direct")

    def is_pursuing(self, enemy) -> bool:
        return is_aggroed(enemy, SimpleNamespace(now=self.elapsed))

    def sleep(self, enemy) -> DormantEnemy:
        """Strip a live enemy to its record and take it out of the run.
        What survives: kind, spot, HP, shield, speed, status effects,
        owner. What does not: the behaviour machine, the animator, any
        knockback in flight -- rebuilt fresh on wake."""
        self.ps.enemies.remove(enemy)
        return DormantEnemy(enemy.enemy_id, enemy.pos.x, enemy.pos.y,
                            enemy.hp, enemy.max_hp, enemy.shield_hp, enemy.speed,
                            status=enemy.status, owner=self.owner_of(enemy),
                            spawned_at=getattr(enemy, "spawned_at", 0.0),
                            recycles=getattr(enemy, "recycles", 0))

    def wake(self, rec: DormantEnemy, x: float, y: float) -> Enemy:
        enemy = Enemy(rec.enemy_id, self.ps.content.enemy(rec.enemy_id), x, y)
        enemy.max_hp = rec.max_hp
        enemy.hp = rec.hp
        enemy.shield_hp = rec.shield_hp
        enemy.speed = rec.speed
        if rec.status is not None:
            enemy.status = rec.status
        enemy.spawn_owner = rec.owner
        enemy.spawned_at = rec.spawned_at
        enemy.recycles = rec.recycles
        self.ps.enemies.append(enemy)
        return enemy

    def relocate(self, enemy, x: float, y: float) -> None:
        enemy.pos.update(x, y)
        enemy._knock.update(0, 0)

    # --- the watchdog's questions (S5) ---------------------------------
    def player_radius(self) -> float:
        return float(self.ps.player.radius)

    def wants_to_move(self, enemy) -> bool:
        return enemy.vel.length_squared() > 1.0

    def is_attacking(self, enemy) -> bool:
        return bool(enemy._attacking)

    def poof(self, pos) -> None:
        self.ps.fx.spawn_death_fx(pos, radius=float(config.PLAYER_RADIUS))

    def neighbors_near(self, pos, radius: float) -> list:
        return self.ps.grid.query_circle(pos.x, pos.y, radius)

    def publish(self, event: str, **payload) -> None:
        self.ps.game.events.publish(event, **payload)

    def subscribe(self, event: str, handler) -> None:
        self.ps.game.events.subscribe(event, handler)
        self._subs.append((event, handler))

    def close(self) -> None:
        """Drop the master's subscriptions when the run ends."""
        for event, handler in self._subs:
            self.ps.game.events.unsubscribe(event, handler)
        self._subs.clear()

    # --- the pacing's questions (S6) -----------------------------------
    def player_hp_fraction(self) -> float:
        p = self.ps.player
        return (p.hp / p.max_hp) if p.max_hp > 0 else 0.0

    def player_max_hp(self) -> float:
        return float(self.ps.player.max_hp)


class EnemyControl:
    def __init__(self, ps) -> None:
        self.ps = ps
        self.host = PlayingHost(ps)
        self.master = SpawnMaster(self.host, ps.director)

    def close(self) -> None:
        self.host.close()

    def lod_eligible(self, enemy, view) -> bool:
        """May this enemy tick at the reduced rate (S7)? Only one that is
        neither chasing nor inside the padded view: what the player can see
        or is fighting always ticks every frame."""
        if view.collidepoint(enemy.pos.x, enemy.pos.y):
            return False
        return not self.host.is_pursuing(enemy)

    def tick_director(self, dt: float) -> None:
        ps = self.ps
        if ps.director.should_spawn_boss(ps.stats["time"]):
            self.spawn_boss()
        self.master.update(dt)

    def spawn_enemy(self, enemy_id: str, at: pygame.Vector2 | None = None,
                    owner: str = "direct"):
        """One enemy, at `at` or at a point the master chooses. Debug keys,
        the dev menu, the arena (`owner="arena"`) and the tests come
        through here. Returns the enemy, or None when the master refused."""
        return self.master.spawn_at(enemy_id, at, owner=owner)

    def summon(self, enemy_id: str, origin: pygame.Vector2, count: int) -> None:
        for _ in range(count):
            offset = pygame.Vector2(self.ps.rng.uniform(-40, 40),
                                    self.ps.rng.uniform(-40, 40))
            self.master.spawn_at(enemy_id, origin + offset, owner="summon")

    def spawn_boss(self) -> None:
        ps = self.ps
        if ps.boss is not None:
            return
        ps.director.mark_boss_spawned()
        boss_id = next(iter(ps.content.bosses))
        pos = self.boss_arena_point()
        ps.boss = Boss(boss_id, ps.content.boss(boss_id), pos.x, pos.y)
        ps.shake.add(0.7)
        ps.game.events.publish(Events.BOSS_SPAWNED, name=ps.boss.name)
        log.info("boss spawned: %s", ps.boss.name)

    def boss_arena_point(self) -> pygame.Vector2:
        """Centre of the boss room if there is a layout, else just off-screen."""
        ps = self.ps
        if ps.game_map.layout is not None:
            room = ps.game_map.layout.room(ps.game_map.layout.boss_id)
            return room.center
        return ps.game_map.offscreen_spawn_point(ps.camera, ps.rng)
