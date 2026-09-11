"""The reaping-arc look (`cone`): a filled circular *sector* matching the region
`CombatResolver.in_cone` tests, plus (for Soul Scythe) an animated purple slash
sprite blitted over it. `draw_cone` is re-imported by `rendering.py` so
`PlayingState._draw_cone` (a `test_depth_sort` entry point) still resolves.
"""
from __future__ import annotations

import math

import pygame

from game.states.playing.projectiles import style

# Sector alphas -- dimmed 35% (was 70 / 210, i.e. round(x * 0.65)) now that
# `_SLASH_RIG` carries the read; the sector is just the honest damage footprint.
_FILL_A = 46
_EDGE_A = 136

_SLASH_RIG, _SLASH_ANIM = "soul_slash", "loop"
_SLASH_FWD = 0.40          # slash centre sits this fraction of `radius` up the cone

# `pygame.gfxdraw` is imported lazily: a top-level `import pygame.gfxdraw` trips
# pygbag's import hook, which treats the dotted name as a PyPI package. `None` ->
# fall back to `pygame.draw.polygon`.
_gfxdraw = None
_gfxdraw_tried = False


def _get_gfxdraw():
    global _gfxdraw, _gfxdraw_tried
    if not _gfxdraw_tried:
        _gfxdraw_tried = True
        try:
            import pygame.gfxdraw as _gd
            _gfxdraw = _gd
        except Exception:  # not built in this pygame (e.g. some pygbag builds)
            _gfxdraw = None
    return _gfxdraw


def draw_cone(surface, cx: float, cy: float, p, zoom: float = 1.0) -> None:
    """Draw the exact region `_resolve_projectile_hits` / `_in_cone` test: a
    circular **sector** with apex at the player, radius `p.radius`, spanning
    `cone_dir ± cone_half_angle`. (Was a full circle -- the wrong shape.)"""
    r = max(2.0, float(p.radius)) * zoom
    base = math.atan2(p.cone_dir.y, p.cone_dir.x)
    half = float(p.cone_half_angle)
    steps = max(2, int(math.degrees(half) / 4))
    pts = [(int(cx), int(cy))]
    for i in range(steps + 1):
        a = base - half + (2.0 * half) * i / steps
        pts.append((int(cx + math.cos(a) * r), int(cy + math.sin(a) * r)))
    col = tuple(p.color)
    gfx = _get_gfxdraw()
    if gfx is not None:
        gfx.filled_polygon(surface, pts, (*col, _FILL_A))
        gfx.aapolygon(surface, pts, (*col, _EDGE_A))
    else:  # pygbag / no gfxdraw: a plain translucent sector, no AA edge
        fill = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(fill, (*col, _FILL_A), pts)
        pygame.draw.polygon(fill, (*col, _EDGE_A), pts, 2)
        surface.blit(fill, (0, 0))


def slash_rig(p) -> str | None:
    """Which slash rig this cone swings (CR2). The weapon's visual `fx.slash`
    is a list of rigs to alternate through by the attack's ordinal
    (`p.swing`, 1 = the first swing -> the first rig), `true` for the old
    single rig, `false` / missing `fx` for the sector alone... except that a
    projectile with no `fx` at all (a test stand-in) keeps the old rig."""
    fx = getattr(p, "fx", None)
    if fx is None:
        return _SLASH_RIG
    if fx.get("slash_mode") == "sequence":
        return None                   # drawn by `slash_fx` as one timed sequence
    slash = fx.get("slash", True)
    if not slash:
        return None
    if isinstance(slash, (list, tuple)):
        if not slash:
            return None
        swing = max(1, int(getattr(p, "swing", 1) or 1))
        return str(slash[(swing - 1) % len(slash)])
    return _SLASH_RIG


def slash_size(p, assets, rig: str) -> tuple[int, int]:
    """The slash sprite's size in world px: the rig's own `scale`, or -- when
    the weapon's visual carries `slash_size` -- that multiple of the cone's
    diameter, so the sprite follows the reach (the Daggers draw theirs 10 %
    bigger than the cone). `(0, 0)` when the rig is absent."""
    fx = getattr(p, "fx", None) or {}
    factor = fx.get("slash_size")
    if factor:
        d = max(2, round(float(p.radius) * 2 * float(factor)))
        return d, d
    return assets.scale_for(rig) or (0, 0)


@style("cone")
def cone(surface, sx, sy, p, ctx) -> None:
    draw_cone(surface, sx, sy, p, ctx.zoom)          # the (dimmed) damage sector

    rig = slash_rig(p)
    if rig is None:
        return                                       # P1: only the Sword swings a slash rig
    assets = ctx.assets
    z = ctx.zoom
    bw, bh = slash_size(p, assets, rig)
    if not bw:
        return                                       # rig absent -> sector only
    n = max(1, assets.frame_count(rig, _SLASH_ANIM))
    if assets.loops(rig, _SLASH_ANIM):
        idx = int(ctx.now * assets.fps(rig, _SLASH_ANIM)) % n
    else:
        # CR2: a one-shot swing plays along the hit's own age.
        idx = min(n - 1, int(float(getattr(p, "age", 0.0)) * assets.fps(rig, _SLASH_ANIM)))
    heading = math.degrees(math.atan2(p.cone_dir.y, p.cone_dir.x))
    spr = assets.frame_rotated(rig, _SLASH_ANIM, idx, heading,
                               size=(max(1, round(bw * z)), max(1, round(bh * z))))
    if spr is None:
        return
    fwd = max(2.0, float(p.radius)) * _SLASH_FWD * z
    cx = sx + math.cos(math.radians(heading)) * fwd
    cy = sy + math.sin(math.radians(heading)) * fwd
    surface.blit(spr, spr.get_rect(center=(int(cx), int(cy))))
