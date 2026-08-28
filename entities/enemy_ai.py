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
    nav_dir: Callable[..., pygame.Vector2] = (
        lambda pos, radius: pygame.Vector2())   # flow-field steering; zero -> fall back
    nav_enabled: bool = False                   # config.ENEMY_PATHFINDING
    neighbors: Callable[..., list] = (
        lambda pos, radius: [])                 # SpatialGrid.query_circle -- for separation
    obstacles_near: Callable[..., list] = (
        lambda pos, radius: [])                 # static obstacle grid -- for local avoidance


def _toward(enemy, target: pygame.Vector2) -> pygame.Vector2:
    d = target - enemy.pos
    return d.normalize() if d.length_squared() > 1e-6 else pygame.Vector2()


def _approach(enemy, ctx) -> pygame.Vector2:
    """Unit direction for a *move toward the player* phase: the shared flow field
    when navigation is on and has a route from here, else a straight line (M5).
    Retreat / kite-back phases keep calling `_toward` -- the field only knows the
    way *to* the player, not away from them."""
    if ctx.nav_enabled:
        d = ctx.nav_dir(enemy.pos, enemy.radius)
        if d.length_squared() > 1e-6:
            return d
    return _toward(enemy, ctx.player_pos)


def chase(enemy, ctx: EnemyContext) -> None:
    enemy.vel = _toward(enemy, ctx.player_pos) * enemy.speed


# --- flow-field chaser (M4) ----------------------------------------
_SLEW_RATE = 9.0            # ease the heading toward the field direction, per second
_SEP_RADIUS_MULT = 1.6     # separation query radius = this * collider radius
_SEP_MAX = 0.6             # cap on the separation push (the field heading is unit 1)
_STUCK_SECONDS = 0.4      # below-par progress for this long -> perpendicular nudge
_STUCK_PROGRESS_FRAC = 0.3  # "made progress" = moved >= this fraction of speed * window
_NUDGE_SECONDS = 0.35
_NUDGE_STRENGTH = 1.5     # perp push during the nudge -- dominates the heading to break free
_OBSTACLE_MARGIN = 14.0  # start easing off a prop once within this of its edge
_OBSTACLE_MAX = 0.7      # cap on the combined obstacle push (heading is unit 1)


def _separation(enemy, ctx: EnemyContext) -> pygame.Vector2:
    """A weak, capped push away from crowding neighbours -- prevents a swarm
    collapsing onto one point on top of the player."""
    r = enemy.radius * _SEP_RADIUS_MULT
    acc = pygame.Vector2()
    for other in ctx.neighbors(enemy.pos, r):
        if other is enemy or not getattr(other, "alive", True):
            continue
        away = enemy.pos - other.pos
        dsq = away.length_squared()
        if dsq < 1e-6 or dsq >= r * r:
            continue
        away.scale_to_length((r - dsq ** 0.5) / r)      # 0..1, stronger up close
        acc += away
    if acc.length_squared() > _SEP_MAX * _SEP_MAX:
        acc.scale_to_length(_SEP_MAX)
    return acc


def _obstacle_avoid(enemy, ctx: EnemyContext) -> pygame.Vector2:
    """A capped push away from any obstacle the enemy has drifted within
    `_OBSTACLE_MARGIN` of -- belt-and-braces on top of the flow field for the
    wall-hug / clearance-slop cases. `resolve_movement` is still the hard stop."""
    acc = pygame.Vector2()
    reach = enemy.radius + _OBSTACLE_MARGIN
    for o in ctx.obstacles_near(enemy.pos, reach + 40.0):    # +slack for big props
        away = enemy.pos - o.pos
        gap = away.length() - o.radius - enemy.radius
        if gap >= _OBSTACLE_MARGIN or away.length_squared() < 1e-6:
            continue
        away.scale_to_length(min(1.0, (_OBSTACLE_MARGIN - gap) / _OBSTACLE_MARGIN))
        acc += away
    if acc.length_squared() > _OBSTACLE_MAX * _OBSTACLE_MAX:
        acc.scale_to_length(_OBSTACLE_MAX)
    return acc


def _unstick(enemy, ctx: EnemyContext, heading: pygame.Vector2) -> pygame.Vector2:
    """If the enemy has covered less than `_STUCK_PROGRESS_FRAC` of the distance
    it should have for `_STUCK_SECONDS`, return a brief sideways nudge (random
    side, seeded) to walk it off a corner. The progress bar scales with the
    enemy's speed so a slow tank making real headway is not flagged."""
    ai = enemy.ai
    ai["nudge_t"] = ai.get("nudge_t", 0.0) - ctx.dt
    if ai["nudge_t"] > 0.0:
        return ai.get("nudge_v", pygame.Vector2())
    reset_sq = (enemy.speed * _STUCK_SECONDS * _STUCK_PROGRESS_FRAC) ** 2
    anchor = ai.get("stuck_at")
    if anchor is None or enemy.pos.distance_squared_to(anchor) > reset_sq:
        ai["stuck_at"] = pygame.Vector2(enemy.pos)
        ai["stuck_t"] = 0.0
        return pygame.Vector2()
    ai["stuck_t"] = ai.get("stuck_t", 0.0) + ctx.dt
    if ai["stuck_t"] < _STUCK_SECONDS:
        return pygame.Vector2()
    base = heading if heading.length_squared() > 1e-9 else _toward(enemy, ctx.player_pos)
    perp = pygame.Vector2(-base.y, base.x)
    if ctx.rng.random() < 0.5:
        perp = -perp
    ai["nudge_v"] = perp * _NUDGE_STRENGTH
    ai["nudge_t"] = _NUDGE_SECONDS
    ai["stuck_t"] = 0.0
    ai["stuck_at"] = pygame.Vector2(enemy.pos)
    return ai["nudge_v"]


def path_chase(enemy, ctx: EnemyContext) -> None:
    """Chase along the shared flow field: ease the heading toward `ctx.nav_dir`,
    add a weak neighbour-separation push and an unstick nudge, and fall back to a
    straight line whenever the field has nothing to say. With
    `config.ENEMY_PATHFINDING` off this is exactly `chase`."""
    if not ctx.nav_enabled:
        chase(enemy, ctx)
        return

    want = ctx.nav_dir(enemy.pos, enemy.radius)
    if want.length_squared() < 1e-6:
        want = _toward(enemy, ctx.player_pos)

    head = enemy.ai.get("nav_head")
    if head is None or head.length_squared() < 1e-9:
        head = pygame.Vector2(want)
    elif want.length_squared() > 1e-9:
        head = head.lerp(want, min(1.0, _SLEW_RATE * ctx.dt))
        if head.length_squared() < 0.04:                # near-180deg flip: just take it
            head = pygame.Vector2(want)
        else:
            head.normalize_ip()
    enemy.ai["nav_head"] = pygame.Vector2(head)

    steer = (head + _separation(enemy, ctx) + _obstacle_avoid(enemy, ctx)
             + _unstick(enemy, ctx, head))
    if steer.length_squared() < 1e-9:
        steer = _toward(enemy, ctx.player_pos)
    enemy.vel = (steer.normalize() * enemy.speed
                 if steer.length_squared() > 1e-9 else pygame.Vector2())


def kite_shoot(enemy, ctx: EnemyContext) -> None:
    """Hold at `prefer_distance`, firing on an interval."""
    to_player = ctx.player_pos - enemy.pos
    dist = to_player.length()
    pref = enemy.cfg.get("prefer_distance", 240)
    if dist < pref - 30:
        enemy.vel = -_toward(enemy, ctx.player_pos) * enemy.speed      # back off
    elif dist > pref + 30:
        enemy.vel = _approach(enemy, ctx) * enemy.speed                 # close in
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
    enemy.vel = _approach(enemy, ctx) * enemy.speed
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
        enemy.vel = _approach(enemy, ctx) * enemy.speed * 0.4

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

    enemy.vel = _approach(enemy, ctx) * enemy.speed
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
        enemy.vel = _approach(enemy, ctx) * enemy.speed
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
        enemy.vel = _approach(enemy, ctx) * enemy.speed * 0.3
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
            enemy.vel = _approach(enemy, ctx) * enemy.speed
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
    "path_chase": path_chase,
    "kite_shoot": kite_shoot,
    "exploder": exploder,
    "summoner": summoner,
    "brute": brute,
    "fsm_charger": fsm_charger,
    "fsm_teleporter": fsm_teleporter,
    "fsm_warlock": fsm_warlock,
}
