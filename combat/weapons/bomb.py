"""The Bomb's fire path (six-weapon system, P1; design §3.6).

A bomb is an *inert* projectile: it never scores a direct hit. It flies along
the aim for `throw_time` seconds -- or less, so it lands on the target it was
aimed at -- then sits, and `fuse` seconds after the throw it detonates. The
detonation is a stationary **blast** projectile (`blast_radius`, pierce 999,
`blast_lifetime`) spawned by `TransientFx.detonate`, so the damage goes
through `CombatResolver.projectile_hits` like any other hit: damage
multipliers, crit, weight knockback and on-hit effects all apply. A bomb that
is blocked by an obstacle detonates where it stopped.

All numbers are the weapon's data fields; nothing here has a default.
"""
from __future__ import annotations

import math

import pygame

from combat.damage import outgoing_damage


def landing_time(origin: pygame.Vector2, candidates, speed: float,
                 throw_time: float) -> float:
    """How long the bomb travels: the data's `throw_time`, shortened so a
    bomb aimed at a target stops on it rather than sailing past."""
    if speed <= 0.0:
        return 0.0
    if not candidates:
        return throw_time
    nearest = min((c.pos - origin).length() for c in candidates)
    return min(throw_time, nearest / speed)


def throw_bombs(weapon, ctx, aim: pygame.Vector2, candidates, area: float,
                src_weight: float) -> None:
    d = weapon.definition
    count = weapon._projectile_count(ctx)
    speed = float(d["projectile_speed"]) * ctx.projectile_speed_multiplier
    fuse = float(d["fuse"])
    # P3 Minefield: the bomb lands, arms, and waits for an enemy instead of
    # burning a fuse; it still goes off when its long lifetime ends.
    mine = bool(weapon.effects.get("mine", 0))
    if mine:
        fuse = float(weapon.effects["mine_lifetime"])
    stop_after = landing_time(ctx.origin, candidates, speed, float(d["throw_time"]))
    if count > 1:
        spread = math.radians(float(d["spread_deg"])) * (count - 1)
        base_angle = math.atan2(aim.y, aim.x) - spread / 2
        step = spread / (count - 1)
    else:
        base_angle = math.atan2(aim.y, aim.x)
        step = 0.0
    for i in range(count):
        direction = pygame.Vector2(math.cos(base_angle + step * i),
                                   math.sin(base_angle + step * i))
        dmg = outgoing_damage(weapon._volley_damage(ctx), ctx.damage_multiplier,
                              weapon._crit_chance(ctx), ctx.crit_multiplier, ctx.rng)
        ctx.spawn_projectile(
            pos=ctx.origin, vel=direction * speed, damage=dmg.amount,
            radius=area, lifetime=fuse, pierce=weapon._pierce(),
            src_weight=src_weight, weapon_id=weapon.weapon_id,
            visual=weapon.visual_id,
            source_tags=weapon.tags, is_crit=dmg.is_crit,
            inert=True, stop_after=stop_after,
            blast_radius=float(d["blast_radius"]) + weapon.bonus["blast_radius"],
            blast_lifetime=float(d["blast_lifetime"]),
            mine=mine, arm_delay=float(weapon.effects.get("mine_arm_delay", 0.0)))
