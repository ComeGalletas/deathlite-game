"""The developer overlays drawn over the world: colliders, spawn points and
the manual aim.

Draw code over the same camera as the world renderer, and dev-only -- each
returns at once unless the run is a developer run with that overlay on --
so they sit with the other developer tooling rather than in
`visual/rendering.py`, which is the picture every run draws (structure
review, C6). `WorldRenderer.collider_overlay` and friends forward here, so
`PlayingState.draw` and the tests call them where they always did.
"""
from __future__ import annotations

import math

import pygame

from game import config, fonts

# The manual-aim line's length for a main weapon with no finite reach.
_AIM_LINE_PX = 160.0
_KNOCK_VEC_SCALE = 0.15     # `_knock` px/s -> screen px line length
_SPAWN_MARK_PX = 6          # half-size of a spawn-point mark, world px


def spawn_point_overlay(surface, ps) -> None:
    """Every spawn point and resource anchor the generator decided, read
    straight off the layout. Enemy points are diamonds (bright for the large
    class, dim for small-only), resource anchors squares, each with its floor
    number. Toggle with F8 or the dev menu's 'Spawn points' row."""
    if not (ps.dev_mode and ps._dev_show_spawn_points):
        return
    layout = ps.game_map.layout
    if layout is None:
        return
    cam = ps.camera
    z = cam.zoom
    view = cam.visible_rect().inflate(200, 200)
    font = fonts.mono(10)
    half = max(3, round(_SPAWN_MARK_PX * z))

    def label(sx, sy, text, col):
        surface.blit(font.render(text, True, col), (sx + half + 2, sy - 6))

    placement = ps.spawn.master.placement
    now = ps.stats["time"]
    for p in layout.spawn_points:
        if not view.collidepoint(p.x, p.y):
            continue
        sx, sy = cam.world_to_screen(p.pos)
        sx, sy = int(sx), int(sy)
        col = (config.COLOR_DEBUG_SPAWN if p.clearance == "large"
               else config.COLOR_DEBUG_SPAWN_SMALL)
        if placement.on_cooldown(p, now):        # just used: dimmed
            col = tuple(c // 3 for c in col)
        pygame.draw.polygon(surface, col, ((sx, sy - half), (sx + half, sy),
                                           (sx, sy + half), (sx - half, sy)), 2)
        label(sx, sy, str(p.floor), col)
    for p in layout.resource_points:
        if not view.collidepoint(p.x, p.y):
            continue
        sx, sy = cam.world_to_screen(p.pos)
        sx, sy = int(sx), int(sy)
        col = config.COLOR_DEBUG_RESOURCE
        pygame.draw.rect(surface, col,
                         pygame.Rect(sx - half, sy - half, 2 * half, 2 * half), 2)
        label(sx, sy, f"{p.floor} {p.kind[0]}", col)


def aim_overlay(surface, ps) -> None:
    """CB-5: the manual aim, drawn only while one is active -- a line from
    the hero along the aim out to the main weapon's reach, plus the edges of
    the cone that decides the fire-time target pick (the assist cone for a
    shot; the swing cone itself for melee, which takes no assist). Mouse and
    key sources are tinted apart so the priority ladder is visible. Toggle
    with the dev menu's 'Aim line' row; no F-key."""
    if not (ps.dev_mode and ps._dev_show_aim):
        return
    aim = ps._aim
    if not aim.active:
        return
    cam = ps.camera
    origin = ps.player.pos
    main = ps.player.weapons[0] if ps.player.weapons else None
    reach = _AIM_LINE_PX
    half = math.radians(config.MANUAL_AIM_ASSIST_DEG)
    if main is not None:
        r = main._reach(ps.player.stats.get("area_multiplier", 1.0))
        if math.isfinite(r):
            reach = r
        if main.special == "cone":
            half = math.radians(float(main.definition["cone_half_angle"]))
        else:
            half = main._assist_half_angle()
    col = (config.COLOR_DEBUG_AIM_MOUSE if aim.source == "mouse"
           else config.COLOR_DEBUG_AIM_KEYS)
    edge = tuple(c // 2 for c in col)

    def seg(direction, colour, width):
        pygame.draw.line(surface, colour, cam.world_to_screen(origin),
                         cam.world_to_screen(origin + direction * reach), width)

    seg(aim.direction, col, 2)
    for sign in (1, -1):
        seg(aim.direction.rotate(math.degrees(half) * sign), edge, 1)


def collider_overlay(surface, ps) -> None:
    """Every true circular collider / hitbox in one pass, read straight off
    the fields the physics uses. Toggle with F7 or the dev menu's
    'Collision shapes' row."""
    if not (ps.dev_mode and ps._dev_show_colliders):
        return
    cam = ps.camera
    z = cam.zoom
    view = cam.visible_rect().inflate(200, 200)

    def ring(pos, r, col, w=2):
        sx, sy = cam.world_to_screen(pos)
        pygame.draw.circle(surface, col, (int(sx), int(sy)),
                           max(1, round(r * z)), w)

    ring(ps.player.pos, ps.player.radius, config.COLOR_DEBUG)
    ring(ps.player.pos, ps.player.pickup_radius, config.COLOR_DEBUG_SOFT, 1)
    for e in ps.enemies:
        if view.collidepoint(e.pos.x, e.pos.y):
            ring(e.pos, e.radius, config.COLOR_DEBUG)
    if ps.boss is not None and ps.boss.alive:
        ring(ps.boss.pos, ps.boss.radius, config.COLOR_DEBUG)
    for o in ps.game_map.obstacles:
        if view.collidepoint(o.pos.x, o.pos.y):
            ring(o.pos, o.radius, config.COLOR_DEBUG)
    for p in ps.projectiles:
        ring(p.pos, p.radius, config.COLOR_DEBUG_HIT, 1)
    for p in ps.hostiles:
        ring(p.pos, p.radius, config.COLOR_DEBUG_HIT, 1)
    # Melee swing rings -- one-shot contact volumes, same style as the
    # projectile hitboxes above (they used to draw unconditionally).
    for hb in ps.melee_hitboxes:
        if view.collidepoint(hb.pos.x, hb.pos.y):
            ring(hb.pos, hb.radius, config.COLOR_DEBUG_HIT, 1)

    # CB-2 reach rings: the gate that decides fire-vs-idle. One ring per
    # equipped weapon at the hero (summon weapons have no ring -- `_reach`
    # is `inf` -- so they are skipped); one leash ring per live summon,
    # hero-centred for the wolf and planted-spot-centred for the totem,
    # matching `Summon._acquire_target`.
    area_mult = ps.player.stats.get("area_multiplier", 1.0)
    for w in ps.player.weapons:
        r = w._reach(area_mult)
        if math.isfinite(r):
            ring(ps.player.pos, r, config.COLOR_DEBUG_REACH, 1)
    for s in ps.summons:
        if not getattr(s, "active", False) or not math.isfinite(s.reach):
            continue
        center = ps.player.pos if s.kind == "wolf" else s.pos
        ring(center, s.reach, config.COLOR_DEBUG_REACH, 1)

    # CB-3 physics: a `weight` tag by every mobile body, and its live
    # `_knock` (bump + hit impulse) drawn as a short blue line while it is
    # being shoved -- so `BUMP_GAIN` / `HIT_KNOCK_GAIN` can be tuned by eye.
    wf = fonts.mono(10)

    def wtag(pos, weight, rad):
        sx, sy = cam.world_to_screen(pos)
        txt = "wINF" if math.isinf(weight) else f"w{weight:g}"
        surface.blit(wf.render(txt, True, config.COLOR_DEBUG_REACH),
                     (int(sx + rad * z) + 2, int(sy) - 6))

    def knock_vec(pos, kn):
        if kn.length_squared() <= 1.0:
            return
        sx, sy = cam.world_to_screen(pos)
        pygame.draw.line(
            surface, config.COLOR_DEBUG_KNOCK, (int(sx), int(sy)),
            (int(sx + kn.x * _KNOCK_VEC_SCALE * z),
             int(sy + kn.y * _KNOCK_VEC_SCALE * z)), 2)

    wtag(ps.player.pos, ps.player.weight, ps.player.radius)
    knock_vec(ps.player.pos, ps.player._knock)
    for e in ps.enemies:
        if view.collidepoint(e.pos.x, e.pos.y):
            wtag(e.pos, e.weight, e.radius)
            knock_vec(e.pos, e._knock)
    if ps.boss is not None and ps.boss.alive:
        wtag(ps.boss.pos, ps.boss.weight, ps.boss.radius)
