"""Composable UI panels built from single-image cap/middle rig pieces.

Horizontal 3-slice: a left cap and a right cap at their native aspect (scaled
to the target height), a middle rig stretched to fill what remains. Built once
per (rigs, size) and cached -- callers that draw every frame never recompose
the Surface. `None` if any rig / file is missing or unreadable, same degrade
contract as `game.assets` -- callers fall back to their own primitive drawing.
"""
from __future__ import annotations

import pygame

_cache: dict[tuple, pygame.Surface | None] = {}


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
