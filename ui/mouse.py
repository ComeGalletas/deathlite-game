"""Mouse support for the menu screens (journal: "Mouse support in menus and
UI", 2026-09-04).

Two small pieces every keyboard-driven screen can adopt without changing
its logic:

* `HitMap` -- the rects a screen painted last frame, each tagged with the
  selection key it stands for. `draw` clears it and re-registers as it
  paints; `handle_event` asks `at(pos)`. Screens here are static, so last
  frame's rects are exact.
* `MouseNav` -- turns raw mouse events into `("hover", key)` /
  `("click", key)`. Hover *selects* (the same index Up / Down moves); a click
  is a press and a release over the **same** key, reported on the release.
  Activating on release matters: the run's manual aim polls the held button
  every frame, so a pick on the press would fire an attack the moment an
  overlay closed.

`install_cursor` sets the hardware cursor from `config.UI_CURSOR_IMAGE`,
and `system_match_scale` says what to draw it at so it is the size the
desktop draws its own arrow.
"""
from __future__ import annotations

import logging

import pygame

from game import config
from game.display import native

log = logging.getLogger(__name__)

BUTTON_LEFT = 1


class HitMap:
    def __init__(self) -> None:
        self._items: list[tuple[pygame.Rect, object]] = []

    def clear(self) -> None:
        self._items.clear()

    def add(self, rect: pygame.Rect, key) -> pygame.Rect:
        """Register `rect` for `key`; returns the rect for chaining."""
        self._items.append((pygame.Rect(rect), key))
        return rect

    def at(self, pos):
        """The key of the topmost (last added) rect under `pos`, else None."""
        for rect, key in reversed(self._items):
            if rect.collidepoint(pos):
                return key
        return None

    def rect_of(self, key) -> pygame.Rect | None:
        for rect, k in self._items:
            if k == key:
                return rect
        return None

    def __len__(self) -> int:
        return len(self._items)


class MouseNav:
    """Press / release bookkeeping over a `HitMap`."""

    def __init__(self, hits: HitMap | None = None) -> None:
        self.hits = hits if hits is not None else HitMap()
        self._pressed_on = None
        self._hover = None

    @property
    def hover(self):
        """The key under the cursor as of the last motion event (None off
        every rect) -- the `("hover", key)` result alone cannot tell a
        screen the cursor *left*, this can."""
        return self._hover

    @property
    def pressed_on(self):
        """The key the current left press landed on (None when the button is
        up or the press missed every rect) -- so a screen can paint that
        element in its pressed state while the button is held."""
        return self._pressed_on

    def event(self, event: pygame.event.Event):
        """`("hover", key)` for motion over a registered rect, `("click",
        key)` for a left release over the rect the press landed on, else
        None. A press or release off every rect resets the press."""
        if event.type == pygame.MOUSEMOTION:
            key = self.hits.at(event.pos)
            self._hover = key
            return ("hover", key) if key is not None else None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == BUTTON_LEFT:
            self._pressed_on = self.hits.at(event.pos)
            return None
        if event.type == pygame.MOUSEBUTTONUP and event.button == BUTTON_LEFT:
            key = self.hits.at(event.pos)
            pressed = self._pressed_on
            self._pressed_on = None
            if key is not None and key == pressed:
                return ("click", key)
        return None


def cursor_ink(assets) -> pygame.Rect | None:
    """The arrow's ink inside `config.UI_CURSOR_IMAGE` (22x30 in the shipped
    file, which is 64x64 with the arrow off-centre). None when the image is
    missing or wholly transparent."""
    base = assets.picture(config.UI_CURSOR_IMAGE)
    if base is None:
        return None
    ink = base.get_bounding_rect()
    return ink if ink.width and ink.height else None


def system_match_scale(assets) -> float | None:
    """The scale that draws our arrow at the size the desktop draws its own:
    the system arrow's ink height over ours, times `config.UI_CURSOR_SCALE`.

    A hardware cursor is in screen pixels, so this match is *absolute* --
    neither the render scale nor the window scale enters it, and the arrow
    keeps one physical size windowed, fullscreen and at every render width.
    None where the platform will not say its cursor size, which leaves the
    caller its own sizing."""
    ink = cursor_ink(assets)
    target = native.system_cursor_ink_height()
    if ink is None or not target:
        return None
    return float(config.UI_CURSOR_SCALE) * float(target) / float(ink.height)


def install_cursor(assets, scale: float | None = None) -> bool:
    """Set the hardware cursor to the arrow in `config.UI_CURSOR_IMAGE`:
    cropped to its ink, scaled by `scale` (default `config.UI_CURSOR_SCALE`;
    the game passes what `system_match_scale` measured, so the arrow is the
    size the player's desktop cursor is), hotspot on the ink's top-left
    pixel (the arrow tip). Returns True when installed; a missing image or a
    refusing driver / build leaves the system cursor and returns False."""
    ink = cursor_ink(assets)
    if ink is None:
        return False
    surf = assets.picture(config.UI_CURSOR_IMAGE).subsurface(ink).copy()
    scale = float(config.UI_CURSOR_SCALE if scale is None else scale)
    if scale != 1.0:
        surf = pygame.transform.smoothscale(
            surf, (max(1, round(ink.width * scale)), max(1, round(ink.height * scale))))
    try:
        pygame.mouse.set_cursor(pygame.cursors.Cursor((0, 0), surf))
    except (pygame.error, TypeError, AttributeError) as exc:
        log.info("surface cursor refused (%s); system cursor stays", exc)
        return False
    return True
