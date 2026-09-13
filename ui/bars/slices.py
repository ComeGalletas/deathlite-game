"""One-dimensional 3-slice for the HUD bar sheets.

`assets/ui/04.png` draws every bar inside a 48x16 cell, but a HUD bar wants
around 300 px. Each sprite on that sheet is a run of pixel-identical columns
between two authored end caps, so a bar of any length is those caps at their
native width with the middle stretched between them. That is the rule
`ui/panels.py` already applies to the 64-px Tiny Swords buttons, but on one
axis only and driven by the `caps` a rig declares in `data/ui/ui_sprites.json`
rather than by a tile grid -- these sheets have no uniform tile.

Nearest-neighbour throughout (pixel art), cached per `(rig, width)` because
the HUD asks for its bars every frame and must never rebuild a surface.
`None` when the rig or its file is missing -- the same degrade contract as
`game.assets`, so the HUD falls back to its primitive rectangles.
"""
from __future__ import annotations

import pygame

_cache: dict[tuple, pygame.Surface | None] = {}
_CACHE_MAX = 512


def caps(assets, rig: str) -> tuple[int, int]:
    """The `(left, right)` cap widths the rig declares, in native px."""
    spec = assets.rig(rig) or {}
    left, right = spec.get("caps", (0, 0))
    return int(left), int(right)


def hslice(assets, rig: str, width: int) -> pygame.Surface | None:
    """`rig`'s art rebuilt at `width` native px: caps kept, middle stretched.

    A `width` below the two caps together would make them overlap, so it is
    clamped -- callers that must not draw a stub (a nearly empty fill bar)
    check the length against `caps()` first and skip the blit instead.
    """
    left, right = caps(assets, rig)
    width = max(int(width), left + right)
    key = (rig, width)
    if key in _cache:
        return _cache[key]

    src = assets.image(rig)
    if src is None:
        _cache[key] = None
        return None

    w, h = src.get_size()
    out = pygame.Surface((width, h), pygame.SRCALPHA)
    if left:
        out.blit(src, (0, 0), (0, 0, left, h))
    middle = width - left - right
    if middle > 0:
        band = src.subsurface(pygame.Rect(left, 0, w - left - right, h))
        out.blit(pygame.transform.scale(band, (middle, h)), (left, 0))
    if right:
        out.blit(src, (width - right, 0), (w - right, 0, right, h))

    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    _cache[key] = out
    return out


def clear_cache() -> None:
    """Test helper: drop cached slices (mirrors `ui.panels.clear_cache`)."""
    _cache.clear()
