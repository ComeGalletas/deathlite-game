"""Translucent single-colour fills at constant alpha (RND-012).

A full-screen dim or flash used to be a fresh `pygame.SRCALPHA` surface
filled with `(r, g, b, a)` and blitted: a per-pixel-alpha blend over every
pixel of the frame. In the browser build that blend is the slow path (a
1280x720 one measured 8.3 ms in Chrome, BLD-003.6); the same fill as an
opaque RGB surface blitted with `set_alpha(a)` measured 1.0 ms. It blends to
within 1 per colour channel of the per-pixel path (black is exact), which
the owner accepted (RND-012.D2).

    veil(surface, (0, 0, 0), 150)                 # the whole surface
    veil(surface, (180, 20, 20), 60, (0, 0, w, 24))   # one strip of it

The fill surfaces are cached by size and colour, so a veil costs one blit
per frame and no allocation. The cache is small and cleared when full: a
frame uses a handful of sizes (the render surface, a vignette's strips).
"""
from __future__ import annotations

import pygame

_CACHE: dict[tuple, pygame.Surface] = {}
_CACHE_CAP = 16


def fill_surface(size, rgb) -> pygame.Surface:
    """The opaque RGB surface of `size` filled with `rgb`, cached. It never
    carries per-pixel alpha; callers set its surface alpha per blit."""
    w, h = int(size[0]), int(size[1])
    key = (w, h, tuple(int(c) for c in rgb[:3]))
    surf = _CACHE.get(key)
    if surf is None:
        if len(_CACHE) >= _CACHE_CAP:
            _CACHE.clear()
        surf = pygame.Surface((max(1, w), max(1, h)))
        surf.fill(key[2])
        _CACHE[key] = surf
    return surf


def clear() -> None:
    """Drop every cached fill: after a display change the old full-frame
    sizes are dead weight (a 1440p frame is ~15 MB). `StateMachine.
    on_display_changed` calls it."""
    _CACHE.clear()


def veil(surface: pygame.Surface, rgb, alpha: float, rect=None) -> None:
    """Blend `rgb` over `surface` (or over `rect` of it) at constant `alpha`
    (0-255, clamped). Nothing is drawn at alpha 0 or over an empty rect."""
    a = int(max(0, min(255, alpha)))
    area = surface.get_rect() if rect is None else pygame.Rect(rect)
    if a <= 0 or area.width <= 0 or area.height <= 0:
        return
    fill = fill_surface(area.size, rgb)
    fill.set_alpha(a)
    surface.blit(fill, area.topleft)


def frame_strips(size, thickness: int) -> list[pygame.Rect]:
    """The four rects of a border `thickness` px wide inside `size`: top and
    bottom span the full width, left and right fill between them. The same
    pixels `pygame.draw.rect(..., width=thickness)` covers on a rect of
    that size, as four blits instead of a full-frame surface."""
    w, h = int(size[0]), int(size[1])
    t = max(0, min(int(thickness), w // 2, h // 2))
    if t <= 0:
        return []
    return [pygame.Rect(0, 0, w, t), pygame.Rect(0, h - t, w, t),
            pygame.Rect(0, t, t, h - 2 * t), pygame.Rect(w - t, t, t, h - 2 * t)]
