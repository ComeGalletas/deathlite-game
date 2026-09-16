"""The one seam between the interface's design pixels and native pixels.

Every screen is laid out in *design* pixels -- the 1600x900 box, 74 px row
steps, 560-wide buttons, 26 px fonts -- and under native-resolution
rendering (journal "Native-resolution rendering", stage 2, 2026-09-16) the
surface is the window, so those numbers are multiplied by
`config.RENDER_SCALE` at the point of use:

    from ui import scale
    y = scale.px(240) + i * scale.px(74)
    rect = scale.rect(0, 0, 560, 64)

`px` rounds to a whole pixel; `rect` / `size` round each edge. Fonts go
through `game/fonts.py`, which applies the same factor to the requested
size, so a screen asks for its design size and gets the native one. At
scale 1.0 (the fixed 1600x900 frame, the plain fallback, the browser
build, the test suite) every helper is the identity.
"""
from __future__ import annotations

import pygame

from game import config


def factor() -> float:
    """Native pixels per design pixel (`config.RENDER_SCALE`)."""
    return float(config.RENDER_SCALE)


def px(n: float) -> int:
    """`n` design pixels as a whole number of native pixels."""
    return int(round(float(n) * factor()))


def size(w: float, h: float) -> tuple[int, int]:
    return (px(w), px(h))


def rect(x: float, y: float, w: float, h: float) -> pygame.Rect:
    return pygame.Rect(px(x), px(y), px(w), px(h))


def box_size() -> tuple[int, int]:
    """The UI box at the current scale: the 1600x900 design at `factor()`."""
    return (px(config.UI_WIDTH), px(config.UI_HEIGHT))


def int_scale(n: int) -> int:
    """An integer art scale (`HUD_BAR_SCALE` and the like) at the current
    factor, never below 1: pixel-art bars keep a whole-pixel grid, so at
    1.6x a x3 bar becomes x5 rather than x4.8."""
    return max(1, int(round(int(n) * factor())))
