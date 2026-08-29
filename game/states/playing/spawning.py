"""Enemy / boss spawning for PLAYING.

`EnemyControl` runs the phase-based spawn director each frame and constructs
enemies and the boss with the run's HP/speed scaling applied. It appends to
`ps.enemies` / sets `ps.boss` and reads `ps.director`, `ps.content`,
`ps.game_map`, `ps.camera`, `ps.rng`, `ps.stats`.

Part of the split tracked in `journals/playing_state_refactor.md` (P6).
"""
from __future__ import annotations

import logging

import pygame

from entities.boss import Boss
from entities.enemy import Enemy
from game.events import Events

log = logging.getLogger(__name__)


class EnemyControl:
    def __init__(self, ps) -> None:
        self.ps = ps

    def tick_director(self, dt: float) -> None:
        ps = self.ps
        elapsed = ps.stats["time"]
        if ps.director.should_spawn_boss(elapsed):
            self.spawn_boss()
        for enemy_id in ps.director.update(dt, elapsed, len(ps.enemies)):
            self.spawn_enemy(enemy_id)

    def spawn_enemy(self, enemy_id: str, at: pygame.Vector2 | None = None) -> None:
        ps = self.ps
        if len(ps.enemies) >= ps.director.enemy_count_cap(ps.stats["time"]):
            return
        definition = ps.content.enemy(enemy_id)
        pos = at if at is not None else ps.game_map.offscreen_spawn_point(
            ps.camera, ps.rng)
        enemy = Enemy(enemy_id, definition, pos.x, pos.y)
        hp_mult, spd_mult = ps.director.stat_multipliers(ps.stats["time"])
        enemy.max_hp *= hp_mult
        enemy.hp = enemy.max_hp
        enemy.speed *= spd_mult
        ps.enemies.append(enemy)

    def summon(self, enemy_id: str, origin: pygame.Vector2, count: int) -> None:
        for _ in range(count):
            offset = pygame.Vector2(self.ps.rng.uniform(-40, 40),
                                    self.ps.rng.uniform(-40, 40))
            self.spawn_enemy(enemy_id, at=origin + offset)

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
