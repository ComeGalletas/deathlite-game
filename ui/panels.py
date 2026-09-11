"""Composable UI panels.

One builder, cached per (rig, size) so callers that draw every frame never
recompose a Surface, and `None` when a rig / file is missing -- the same
degrade contract as `game.assets`, so callers fall back to their own
primitive drawing.

* `slice` -- one **sheet** cut on its tile grid and rebuilt at a size. The
  Tiny Swords buttons and ribbons: a `192x64` strip is three 64-px tiles
  (cap, middle, cap) and becomes a 3-slice; a `192x192` sheet is 3x3 and
  becomes a 9-slice (corners kept, edges stretched one way, the centre
  both); a `64x64` single is plainly scaled. When a target is smaller than
  the caps need (two tiles on a sliced axis, one on a plain axis) the whole
  sheet is pre-scaled uniformly first, so a short button keeps its
  proportions instead of squashing its caps.
"""
from __future__ import annotations

import pygame

_cache: dict[tuple, pygame.Surface | None] = {}

TILE = 64          # the pack's grid


def slice(assets, rig: str, size: tuple[int, int], *,
          tile: int = TILE) -> pygame.Surface | None:
    """The sheet behind `rig`, cut on its `tile` grid and rebuilt at `size`.
    See the module docstring for the rules. Nearest-neighbour scaling
    throughout (pixel art)."""
    size = (int(size[0]), int(size[1]))
    key = ("<slice>", rig, size, tile)
    if key in _cache:
        return _cache[key]
    sheet = assets.image(rig)
    if sheet is None or size[0] <= 0 or size[1] <= 0:
        _cache[key] = None
        return None

    cols = 3 if sheet.get_width() >= 3 * tile else 1
    rows = 3 if sheet.get_height() >= 3 * tile else 1
    # Pre-scale so the caps fit: a sliced axis needs two tiles, a plain axis
    # one, and the factor is shared so the art keeps its aspect.
    need_w = (2 if cols == 3 else 1) * tile
    need_h = (2 if rows == 3 else 1) * tile
    f = min(1.0, size[0] / need_w, size[1] / need_h)
    t = max(1, round(tile * f))
    if t != tile:
        sheet = pygame.transform.scale(sheet, (cols * t, rows * t))
    else:
        sheet = sheet.subsurface(pygame.Rect(0, 0, cols * t, rows * t))

    out = pygame.Surface(size, pygame.SRCALPHA)
    w, h = size

    def spans(n: int, total: int):
        """(src offset, src length, dst offset, dst length) per cell along
        one axis: caps at `t`, the middle takes what is left."""
        if n == 1:
            return [(0, t, 0, total)]
        mid = max(0, total - 2 * t)
        return [(0, t, 0, t), (t, t, t, mid), (2 * t, t, t + mid, t)]

    for sy, sh, dy, dh in spans(rows, h):
        for sx, sw, dx, dw in spans(cols, w):
            if dw <= 0 or dh <= 0:
                continue
            cell = sheet.subsurface(pygame.Rect(sx, sy, sw, sh))
            if (dw, dh) != (sw, sh):
                cell = pygame.transform.scale(cell, (dw, dh))
            out.blit(cell, (dx, dy))
    _cache[key] = out
    return out


def clear_cache() -> None:
    """Test helper: drop cached panels (mirrors game.assets.reset_assets)."""
    _cache.clear()
