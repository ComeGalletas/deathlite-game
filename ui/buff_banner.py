"""The flying name of a buff (journal: buff_buildings_journal.md).

When a building fires, the buff's name rises off the hero in the buff's
colour and stays readable while it fades to nothing over `seconds` (the
owner asked for seven). It is interface text -- the title face, the HUD's
size, shadowed -- drawn in screen space over the hero's screen position, so
it follows the hero and never zooms with the world. A second buff pushes the
earlier names up a line so two activations never overprint.
"""
from __future__ import annotations

import pygame

from game import fonts
from ui import scale
from ui.text import shadowed

RISE_PX = 44           # design px the name climbs in its first second
RISE_SECONDS = 1.0
LIFT_PX = 96           # design px above the hero's centre the name starts (clear of the marks)
LINE_PX = 30           # design px between stacked names
FONT_PX = 26


class BuffBanner:
    __slots__ = ("text", "colour", "age", "seconds")

    def __init__(self, text: str, colour, seconds: float) -> None:
        self.text = text
        self.colour = tuple(colour)
        self.age = 0.0
        self.seconds = seconds

    @property
    def alpha(self) -> int:
        return max(0, min(255, int(255 * (1.0 - self.age / self.seconds))))

    @property
    def rise(self) -> float:
        return min(1.0, self.age / RISE_SECONDS) * RISE_PX


class BuffBanners:
    def __init__(self, seconds: float = 7.0) -> None:
        self.seconds = float(seconds)
        self.items: list[BuffBanner] = []
        self._font = None

    def add(self, text: str, colour) -> None:
        self.items.append(BuffBanner(text, colour, self.seconds))

    def update(self, dt: float) -> None:
        for b in self.items:
            b.age += dt
        self.items = [b for b in self.items if b.age < b.seconds]

    def draw(self, surface: pygame.Surface, hero_screen_pos) -> None:
        if not self.items:
            return
        if self._font is None:
            self._font = fonts.heading(FONT_PX)
        hx, hy = hero_screen_pos
        # Newest at the bottom, each older one a line higher.
        for slot, b in enumerate(reversed(self.items)):
            text = shadowed(self._font, b.text, b.colour)
            text.set_alpha(b.alpha)
            y = hy - scale.px(LIFT_PX) - scale.px(b.rise) - slot * scale.px(LINE_PX)
            surface.blit(text, text.get_rect(center=(int(hx), int(y))))
