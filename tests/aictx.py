"""A fake AI context for tests -- one object satisfying both `entities.ai`
`Perception` and `Combat`, with no-op defaults. Replaces the retired
`entities.enemy_ai.EnemyContext`.
"""
import random
from types import SimpleNamespace

import pygame


def ai_ctx(dt=1 / 60, player=(0, 0), rng=None, **overrides):
    base = dict(
        dt=dt, now=0.0, player_pos=pygame.Vector2(player), player=object(),
        rng=rng if rng is not None else random.Random(0),
        nav_dir=lambda pos, r: pygame.Vector2(),
        neighbors=lambda pos, r: [],
        obstacles_near=lambda pos, r: [],
        is_walkable=lambda pos, r: True,
        resolve_movement=lambda prev, new, r: new,
        fire_projectile=lambda **kw: None,
        summon=lambda enemy_id, pos, n: None,
        explosion=lambda pos, r, d: None,
        spawn_hazard=lambda pos, r, dps, dur, tick_interval=None: None,
        report_damage=lambda amount: None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)
