"""Composable UI panels.

Two builders, both cached per (inputs, size) so callers that draw every frame
never recompose a Surface, and both `None` when a rig / file is missing --
the same degrade contract as `game.assets`, so callers fall back to their
own primitive drawing.

* `three_slice_h` -- a bar from three **separate** rig images (left cap,
  middle, right cap), the caps at their native aspect scaled to the height.
  The start-menu parchment panel.
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


def _native_size(meta: dict) -> tuple[int, int]:
    """Aspect source for a cap: the `content` crop if present, else the full
    `frame` -- a cropped cap must scale by its own cropped size, not the sheet."""
    crop = meta.get("content")
    if crop:
        return int(crop[2]), int(crop[3])
    return int(meta["frame"][0]), int(meta["frame"][1])


def three_slice_h(assets, *, left: str, mid: str, right: str,
                  width: int, height: int) -> pygame.Surface | None:
    key = (left, mid, right, width, height)
    if key in _cache:
        return _cache[key]

    meta_l, meta_r = assets.rig(left), assets.rig(right)
    if not meta_l or not meta_r or not assets.rig(mid):
        _cache[key] = None
        return None

    lw, lh = _native_size(meta_l)
    rw, rh = _native_size(meta_r)
    cap_l_w = max(1, round(lw * height / lh))
    cap_r_w = max(1, round(rw * height / rh))
    mid_w = max(1, width - cap_l_w - cap_r_w)

    cap_l = assets.image(left, size=(cap_l_w, height))
    cap_r = assets.image(right, size=(cap_r_w, height))
    strip = assets.image(mid, size=(mid_w, height))
    if cap_l is None or cap_r is None or strip is None:
        _cache[key] = None
        return None

    panel = pygame.Surface((width, height), pygame.SRCALPHA)
    panel.blit(cap_l, (0, 0))
    panel.blit(strip, (cap_l_w, 0))
    panel.blit(cap_r, (cap_l_w + mid_w, 0))
    _cache[key] = panel
    return panel


def clear_cache() -> None:
    """Test helper: drop cached panels (mirrors game.assets.reset_assets)."""
    _cache.clear()
