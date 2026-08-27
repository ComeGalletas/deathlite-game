"""Enemy behaviors (Strategy pattern, spec 11 / 3.3).

A behavior is `fn(enemy, ctx)` that sets `enemy.vel` and may call context
callbacks (fire a hostile projectile, summon, request an explosion). Position
integration, knockback decay and hit-flash live in `Enemy.update`, so behaviors
stay small.

These use simple timers, not full finite-state machines -- the spec reserves
FSMs for the advanced Phase 3 enemies and the boss. "Do not use a state machine
for a basic enemy that only follows the player."
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame


@dataclass
class EnemyContext:
    dt: float
    player_pos: pygame.Vector2
    player: object
    rng: object
    fire_projectile: Callable[..., None]   # pos, vel, damage, radius
    summon: Callable[[str, pygame.Vector2, int], None]
    explosion: Callable[[pygame.Vector2, float, float], None]  # pos, radius, dmg
    report_damage: Callable[[float], None] = lambda amount: None   # DoT accounting
    resolve_movement: Callable[..., pygame.Vector2] = (
        lambda prev, new, radius: new)   # wall sliding; identity by default
    spawn_hazard: Callable[..., None] = (
        lambda pos, radius, dps, duration, tick_interval=None: None)   # area-denial pools


def _toward(enemy, target: pygame.Vector2) -> pygame.Vector2:
    d = target - enemy.pos
    return d.normalize() if d.length_squared() > 1e-6 else pygame.Vector2()


def chase(enemy, ctx: EnemyContext) -> None:
    enemy.vel = _toward(enemy, ctx.player_pos) * enemy.speed


def kite_shoot(enemy, ctx: EnemyContext) -> None:
    """Hold at `prefer_distance`, firing on an interval."""
    to_player = ctx.player_pos - enemy.pos
    dist = to_player.length()
    pref = enemy.cfg.get("prefer_distance", 240)
    if dist < pref - 30:
        enemy.vel = -_toward(enemy, ctx.player_pos) * enemy.speed      # back off
    elif dist > pref + 30:
        enemy.vel = _toward(enemy, ctx.player_pos) * enemy.speed        # close in
    else:
        enemy.vel = pygame.Vector2()

    enemy.ai["shoot_t"] = enemy.ai.get("shoot_t", enemy.cfg.get("shoot_interval", 2.0)) - ctx.dt
    if enemy.ai["shoot_t"] <= 0.0 and dist < pref * 1.8:
        enemy.ai["shoot_t"] = enemy.cfg.get("shoot_interval", 2.0)
        direction = _toward(enemy, ctx.player_pos)
        if direction.length_squared() > 0:
            ctx.fire_projectile(
                pos=enemy.pos, vel=direction * enemy.cfg.get("shot_speed", 220),
                damage=enemy.cfg.get("shoot_damage", 6), radius=6)


def exploder(enemy, ctx: EnemyContext) -> None:
    chase(enemy, ctx)
    fuse = enemy.cfg.get("fuse_range", 32)
    if (ctx.player_pos - enemy.pos).length() <= fuse:
        enemy.hp = 0.0
        enemy.alive = False  # cull pass triggers the blast via explode_radius


def summoner(enemy, ctx: EnemyContext) -> None:
    # Keep some distance while spawning broods.
    dist = (ctx.player_pos - enemy.pos).length()
    if dist < 200:
        enemy.vel = -_toward(enemy, ctx.player_pos) * enemy.speed
    else:
        enemy.vel = _toward(enemy, ctx.player_pos) * enemy.speed * 0.4

    enemy.ai["summon_t"] = enemy.ai.get("summon_t", enemy.cfg.get("summon_interval", 4.0)) - ctx.dt
    if enemy.ai["summon_t"] <= 0.0:
        enemy.ai["summon_t"] = enemy.cfg.get("summon_interval", 4.0)
        ctx.summon(enemy.cfg.get("summon_id", "swarm"), enemy.pos,
                   int(enemy.cfg.get("summon_count", 3)))


def brute(enemy, ctx: EnemyContext) -> None:
    """Chase, then telegraph and perform a ground slam when in range."""
    state = enemy.ai.get("slam_state")
    timer = enemy.ai.get("slam_t", enemy.cfg.get("slam_interval", 3.5))
    dist = (ctx.player_pos - enemy.pos).length()

    if state == "telegraph":
        enemy.vel = pygame.Vector2()  # rooted while winding up
        timer -= ctx.dt
        if timer <= 0.0:
            radius = enemy.cfg.get("slam_radius", 120)
            if dist <= radius:
                ctx.explosion(pygame.Vector2(enemy.pos), radius,
                              enemy.cfg.get("slam_damage", 28))
            enemy.ai["slam_state"] = None
            enemy.ai["slam_t"] = enemy.cfg.get("slam_interval", 3.5)
        else:
            enemy.ai["slam_t"] = timer
        return

    chase(enemy, ctx)
    timer -= ctx.dt
    if timer <= 0.0 and dist <= enemy.cfg.get("slam_range", 120):
        enemy.ai["slam_state"] = "telegraph"
        enemy.ai["slam_t"] = enemy.cfg.get("slam_telegraph", 0.9)
    else:
        enemy.ai["slam_t"] = timer


# --- finite-state-machine enemies (spec 5.6) --------------------------
# Shared cycle: chase -> telegraph -> attack -> recover -> chase. State in
# enemy.ai["fs"], phase timer in enemy.ai["ft"], attack cooldown in ai["cd"].

def _fsm_enter(enemy, state: str, duration: float) -> None:
    enemy.ai["fs"] = state
    enemy.ai["ft"] = duration
    if state == "attack":
        # A charge / blink is a discrete impact -- clear the contact cooldown so
        # its first overlap always lands a bite at the bumped contact damage.
        enemy.contact_cd = 0.0


def _fsm_common(enemy, ctx, *, trigger_range: float, telegraph: float,
                attack: float, recover: float, cooldown: float,
                on_attack_start, on_attack_tick=None) -> None:
    fs = enemy.ai.get("fs", "chase")
    enemy.ai["ft"] = enemy.ai.get("ft", 0.0) - ctx.dt
    enemy.ai["cd"] = enemy.ai.get("cd", cooldown) - ctx.dt
    dist = (ctx.player_pos - enemy.pos).length()

    if fs == "chase":
        enemy.vel = _toward(enemy, ctx.player_pos) * enemy.speed
        if dist <= trigger_range and enemy.ai["cd"] <= 0.0:
            _fsm_enter(enemy, "telegraph", telegraph)
    elif fs == "telegraph":
        enemy.vel = pygame.Vector2()
        if enemy.ai["ft"] <= 0.0:
            on_attack_start(enemy, ctx)
            _fsm_enter(enemy, "attack", attack)
    elif fs == "attack":
        if on_attack_tick:
            on_attack_tick(enemy, ctx)
        if enemy.ai["ft"] <= 0.0:
            _fsm_enter(enemy, "recover", recover)
    elif fs == "recover":
        enemy.vel = _toward(enemy, ctx.player_pos) * enemy.speed * 0.3
        if enemy.ai["ft"] <= 0.0:
            enemy.ai["cd"] = cooldown
            _fsm_enter(enemy, "chase", 0.0)


def fsm_charger(enemy, ctx) -> None:
    c = enemy.cfg

    def start(e, cx):
        d = cx.player_pos - e.pos
        e.ai["dir"] = d.normalize() if d.length_squared() > 1 else pygame.Vector2(1, 0)

    def tick(e, cx):
        e.vel = e.ai["dir"] * c.get("charge_speed", 620)
        e.contact_damage = c.get("charge_damage", 26)

    _fsm_common(enemy, ctx,
                trigger_range=c.get("charge_range", 340),
                telegraph=c.get("charge_telegraph", 0.7),
                attack=c.get("charge_duration", 0.5),
                recover=c.get("charge_recover", 1.1),
                cooldown=c.get("charge_interval", 3.0),
                on_attack_start=start, on_attack_tick=tick)


def fsm_teleporter(enemy, ctx) -> None:
    c = enemy.cfg

    def start(e, cx):
        rng = cx.rng
        off = pygame.Vector2(rng.uniform(-1, 1), rng.uniform(-1, 1))
        if off.length_squared() > 0:
            off.scale_to_length(rng.uniform(20, c.get("blink_range", 70)))
        dest = cx.player_pos + off
        e.pos = cx.resolve_movement(e.pos, dest, e.radius)
        e.contact_damage = c.get("blink_damage", 16)

    _fsm_common(enemy, ctx,
                trigger_range=c.get("blink_trigger", 460),
                telegraph=c.get("blink_telegraph", 0.55),
                attack=c.get("blink_duration", 0.35),
                recover=c.get("blink_recover", 0.9),
                cooldown=c.get("blink_interval", 2.6),
                on_attack_start=start)


def fsm_warlock(enemy, ctx) -> None:
    c = enemy.cfg
    dist = (ctx.player_pos - enemy.pos).length()
    pref = c.get("prefer_distance", 300)
    if enemy.ai.get("fs", "chase") == "chase":
        if dist < pref - 40:
            enemy.vel = -_toward(enemy, ctx.player_pos) * enemy.speed
        elif dist > pref + 40:
            enemy.vel = _toward(enemy, ctx.player_pos) * enemy.speed
        else:
            enemy.vel = pygame.Vector2()

    def start(e, cx):
        target = e.ai.get("cast_at", cx.player_pos)
        cx.spawn_hazard(pygame.Vector2(target),
                        c.get("hazard_radius", 90), c.get("hazard_dps", 20),
                        c.get("hazard_duration", 3.5), c.get("hazard_tick"))

    def enter_telegraph_snapshot(e, cx):
        e.ai["cast_at"] = pygame.Vector2(cx.player_pos)

    # snapshot the target the moment we begin telegraphing
    if enemy.ai.get("fs", "chase") == "chase" and dist <= c.get("cast_range", 420) \
            and enemy.ai.get("cd", 0.0) <= 0.0:
        enter_telegraph_snapshot(enemy, ctx)

    _fsm_common(enemy, ctx,
                trigger_range=c.get("cast_range", 420),
                telegraph=c.get("cast_telegraph", 0.8),
                attack=c.get("cast_duration", 0.2),
                recover=c.get("cast_recover", 1.8),
                cooldown=c.get("cast_interval", 3.4),
                on_attack_start=start)


BEHAVIORS = {
    "chase": chase,
    "chaser": chase,          # backwards-compatible alias
    "kite_shoot": kite_shoot,
    "exploder": exploder,
    "summoner": summoner,
    "brute": brute,
    "fsm_charger": fsm_charger,
    "fsm_teleporter": fsm_teleporter,
    "fsm_warlock": fsm_warlock,
}
