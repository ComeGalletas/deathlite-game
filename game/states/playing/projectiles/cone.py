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


@style("cone")
def cone(surface, sx, sy, p, ctx) -> None:
    draw_cone(surface, sx, sy, p, ctx.zoom)          # the (dimmed) damage sector

    assets = ctx.assets
    z = ctx.zoom
    bw, bh = assets.scale_for(_SLASH_RIG) or (0, 0)
    if not bw:
        return                                       # rig absent -> sector only
    n = max(1, assets.frame_count(_SLASH_RIG, _SLASH_ANIM))
    idx = int(ctx.now * assets.fps(_SLASH_RIG, _SLASH_ANIM)) % n
    heading = math.degrees(math.atan2(p.cone_dir.y, p.cone_dir.x))
    spr = assets.frame_rotated(_SLASH_RIG, _SLASH_ANIM, idx, heading,
                               size=(max(1, round(bw * z)), max(1, round(bh * z))))
    if spr is None:
        return
    fwd = max(2.0, float(p.radius)) * _SLASH_FWD * z
    cx = sx + math.cos(math.radians(heading)) * fwd
    cy = sy + math.sin(math.radians(heading)) * fwd
    surface.blit(spr, spr.get_rect(center=(int(cx), int(cy))))
