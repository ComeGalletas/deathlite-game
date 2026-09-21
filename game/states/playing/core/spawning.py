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
import math
import random
from types import SimpleNamespace

import pygame

from entities.ai.components.aggro import is_aggroed
from entities.boss import Boss
from entities.enemy import Enemy
from game import config
from game.events import Events
from spawn.master import SpawnMaster
from spawn.population import DormantEnemy

log = logging.getLogger(__name__)


def boss_spawn_point(player_pos, rng, width: float, height: float,
                     distance: float | None = None, walkable=None) -> pygame.Vector2:
    """Where the boss appears: `distance` (`config.BOSS_SPAWN_DISTANCE`) from
    the hero on a random side, clamped to the world rect. No room is consulted:
    the boss room stays the spawn master's.

    `walkable(pos) -> bool` is the collider test for a boss that **walks**, and
    the whole reason this is a search rather than one point. A flyer is over the
    world, so what is under the spot -- floor, cliff, lake, sea -- does not
    matter and it passes None; a ground boss dropped on water is simply stuck
    there for the rest of the run. With a test supplied, the ring is sampled at
    `BOSS_SPAWN_RING_SAMPLES` angles from the random start, at each radius in
    `BOSS_SPAWN_RING_SCALES`, and the first accepted spot wins. The random side
    survives: the sweep starts at the drawn angle and only walks on from there.

    The unconstrained point is the fallback when nothing in the sweep is
    walkable -- the old behaviour, and better than a boss that never spawns.
    """
    d = float(config.BOSS_SPAWN_DISTANCE if distance is None else distance)
    ang = rng.uniform(0.0, math.tau)

    def at(angle: float, radius: float) -> pygame.Vector2:
        return pygame.Vector2(
            min(max(player_pos.x + math.cos(angle) * radius, 0.0), float(width)),
            min(max(player_pos.y + math.sin(angle) * radius, 0.0), float(height)))

    if walkable is None:
        return at(ang, d)
    samples = max(1, int(config.BOSS_SPAWN_RING_SAMPLES))
    step = math.tau / samples
    for scale in config.BOSS_SPAWN_RING_SCALES:
        for i in range(samples):
            spot = at(ang + i * step, d * float(scale))
            if walkable(spot):
                return spot
    return at(ang, d)


class PlayingHost:
    def __init__(self, ps) -> None:
        self.ps = ps
        self.run = getattr(ps, "run", ps)
        self._subs: list = []

    @property
    def elapsed(self) -> float:
        return self.run.stats["time"]

    @property
    def rng(self):
        return self.run.rng

    @property
    def layout(self):
        return self.run.game_map.layout

    @property
    def difficulty(self) -> str:
        return self.run.difficulty

    def player_pos(self) -> pygame.Vector2:
        return self.run.player.pos

    def player_heading(self) -> pygame.Vector2:
        return pygame.Vector2(self.run.player._move_dir)

    def player_floor(self):
        layout = self.layout
        if layout is None:
            return None
        p = self.run.player.pos
        meta = layout.tile_at(p.x, p.y)
        return meta.floor if meta is not None else None

    def visible_rect(self) -> pygame.Rect:
        return self.run.camera.visible_rect()

    def is_walkable(self, pos, radius: float, flying: bool = False) -> bool:
        return self.run.game_map.is_walkable(pos, radius, flying=flying)

    def floor_at(self, pos) -> int:
        layout = self.layout
        if layout is None:
            return 0
        meta = layout.tile_at(pos.x, pos.y)
        return meta.floor if meta is not None else 0

    def room_at(self, pos):
        return self.run.game_map.room_at(pos)

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
        # The no-layout world (or one generated with no points): the same
        # band the placement uses, around the hero, never the camera (S11).
        knobs = self.run.content.spawn_tables.placement
        return self.run.game_map.spawn_point_near(
            self.run.player.pos, self.run.rng,
            float(knobs["far_min_distance"]), float(knobs["far_max_distance"]))

    def live_count(self) -> int:
        return len(self.run.enemies)

    def live_enemies(self) -> list:
        return self.run.enemies

    def enemy_radius(self, enemy_id: str) -> float:
        return float(self.run.content.enemy(enemy_id)["radius"])

    def make_enemy(self, enemy_id: str, x: float, y: float,
                   hp_mult: float, spd_mult: float, owner: str = "direct") -> Enemy:
        enemy = Enemy(enemy_id, self.run.content.enemy(enemy_id), x, y)
        enemy.ledger = self.run.ledger
        enemy.max_hp *= hp_mult
        enemy.hp = enemy.max_hp
        enemy.speed *= spd_mult
        enemy.spawn_owner = owner
        enemy.spawned_at = self.elapsed
        self.run.enemies.append(enemy)
        self.ps.fx.spawn_spawn_fx(enemy)      # the burst it appears out of
        return enemy

    # --- live <-> dormant (S4) ----------------------------------------
    def owner_of(self, enemy) -> str:
        return getattr(enemy, "spawn_owner", "direct")

    def is_pursuing(self, enemy) -> bool:
        return is_aggroed(enemy, SimpleNamespace(now=self.elapsed))

    def sleep(self, enemy) -> DormantEnemy:
        """Strip a live enemy to its record and take it out of the run.
        What survives: kind, spot, HP, shield, speed, status effects, the
        elemental aura and its lock, owner. What does not: the behaviour
        machine, the animator, any knockback in flight -- rebuilt fresh on
        wake."""
        self.run.enemies.remove(enemy)
        return DormantEnemy(enemy.enemy_id, enemy.pos.x, enemy.pos.y,
                            enemy.hp, enemy.max_hp, enemy.shield_hp, enemy.speed,
                            status=enemy.status, owner=self.owner_of(enemy),
                            spawned_at=getattr(enemy, "spawned_at", 0.0),
                            recycles=getattr(enemy, "recycles", 0),
                            elemental=getattr(enemy, "elemental", None))

    def wake(self, rec: DormantEnemy, x: float, y: float) -> Enemy:
        enemy = Enemy(rec.enemy_id, self.run.content.enemy(rec.enemy_id), x, y)
        enemy.ledger = self.run.ledger
        enemy.max_hp = rec.max_hp
        enemy.hp = rec.hp
        enemy.shield_hp = rec.shield_hp
        enemy.speed = rec.speed
        if rec.status is not None:
            enemy.status = rec.status
        if rec.elemental is not None:
            enemy.elemental = rec.elemental
        enemy.spawn_owner = rec.owner
        enemy.spawned_at = rec.spawned_at
        enemy.recycles = rec.recycles
        self.run.enemies.append(enemy)
        return enemy

    def relocate(self, enemy, x: float, y: float) -> None:
        enemy.pos.update(x, y)
        enemy._knock.update(0, 0)

    # --- the watchdog's questions (S5) ---------------------------------
    def player_radius(self) -> float:
        return float(self.run.player.radius)

    def wants_to_move(self, enemy) -> bool:
        return enemy.vel.length_squared() > 1.0

    def is_attacking(self, enemy) -> bool:
        return bool(enemy._attacking)

    def poof(self, pos) -> None:
        self.ps.fx.spawn_death_fx(pos, radius=float(config.PLAYER_RADIUS))

    def neighbors_near(self, pos, radius: float) -> list:
        return self.run.grid.query_circle(pos.x, pos.y, radius)

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
        p = self.run.player
        return (p.hp / p.max_hp) if p.max_hp > 0 else 0.0

    def player_max_hp(self) -> float:
        return float(self.run.player.max_hp)


class EnemyControl:
    def __init__(self, ps) -> None:
        self.ps = ps
        self.run = getattr(ps, "run", ps)
        self.host = PlayingHost(ps)
        self.master = SpawnMaster(self.host, ps.director)

    def close(self) -> None:
        self.host.close()

    def lod_eligible(self, enemy, view) -> bool:
        """May this enemy tick at the reduced rate (S7)? Anything outside the
        padded view: what the player can *see* ticks every frame.

        The chase used to be exempt as well, on the reasoning that what the
        player is fighting must never be stepped coarsely. That exemption
        quietly switched the whole LOD off on 2026-09-19, when the aggro
        ranges were roughly doubled and then cut to 660-1200: almost every
        live body is pursuing now, so almost nothing was eligible. Measured
        at 200 live, update p50 was 6.94 ms at lod 1 against 6.70 at lod 4 --
        three per cent across the entire range, which is the LOD doing
        nothing at all.

        A body chasing from off screen is still chasing; the player simply
        cannot see it do so, and it arrives at the same moment either way
        because the skipped frames are paid back in the next tick's `dt`.
        The view is what the exemption was really protecting, and the view
        is what it keeps.
        """
        return not view.collidepoint(enemy.pos.x, enemy.pos.y)

    def tick_director(self, dt: float) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        if ps.director.should_spawn_boss(run.stats["time"]):
            self.spawn_boss()
        self.master.update(dt)

    def spawn_enemy(self, enemy_id: str, at: pygame.Vector2 | None = None,
                    owner: str = "direct"):
        """One enemy, at `at` or at a point the master chooses. Debug keys,
        the dev menu and the tests come through here. Returns the enemy, or
        None when the master refused."""
        return self.master.spawn_at(enemy_id, at, owner=owner)

    def summon(self, enemy_id: str, origin: pygame.Vector2, count: int) -> None:
        for _ in range(count):
            offset = pygame.Vector2(self.run.rng.uniform(-40, 40),
                                    self.run.rng.uniform(-40, 40))
            self.master.spawn_at(enemy_id, origin + offset, owner="summon")

    def spawn_boss(self) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        if run.boss is not None:
            return
        ps.director.mark_boss_spawned()
        boss_id = self.pick_boss()
        definition = run.content.boss(boss_id)
        pos = self.boss_spawn_point(definition)
        run.boss = Boss(boss_id, definition, pos.x, pos.y)
        run.boss.ledger = run.ledger
        ps.fx.spawn_spawn_fx(run.boss)          # sized to the boss's own rig
        run.shake.add(0.7)
        ps.game.events.publish(Events.BOSS_SPAWNED, name=run.boss.name)
        log.info("boss spawned: %s", ps.boss.name)

    def pick_boss(self) -> str:
        """Which boss this run faces: one of `data/enemies/bosses.json`, drawn from the
        run seed.

        Deliberately **not** `ps.rng`. The run's shared stream has been
        consumed an unpredictable number of times by the time a boss spawns --
        how many depends on how the run actually played -- so drawing from it
        would make the boss a function of the playthrough rather than of the
        seed, and two runs on one seed could meet different bosses. A private
        generator keyed off the seed keeps "same seed, same boss" true, which
        is the only thing that makes the choice worth reproducing. Sorted, so
        the answer does not ride on dict ordering in the JSON.
        """
        run = getattr(self, "run", self.ps)      # a bare namespace stands in (tests)
        ids = sorted(run.content.bosses)
        if not ids:
            raise ValueError("data/enemies/bosses.json defines no bosses")
        return random.Random(f"{run.run_seed}:boss").choice(ids)

    def boss_spawn_point(self, definition: dict | None = None) -> pygame.Vector2:
        """`boss_spawn_point()` for this run: beside the hero, not in the
        boss room.

        A boss that walks is given the collider test, at its own radius, so the
        ring search only offers it ground it can stand on. A flyer (and a caller
        that names no boss) gets the plain point -- the sea is walkable to it."""
        ps = self.ps
        run = getattr(self, "run", ps)
        walkable = None
        if definition is not None and "flying" not in definition.get("tags", ()):
            radius = float(definition.get("radius", 0.0))

            def walkable(spot) -> bool:          # noqa: F811 -- the ground case
                return run.game_map.is_walkable(spot, radius)

        return boss_spawn_point(run.player.pos, run.rng,
                                ps.game_map.width, ps.game_map.height,
                                walkable=walkable)
