"""Floating damage numbers (spec 3.6). Pooled and capped.

Numbers rise and fade. Crits render larger and in the accent colour so the
player reads build spikes at a glance.
"""
from __future__ import annotations

import pygame

from game import config
from systems.object_pool import Pool


class DamageNumber:
    __slots__ = ("active", "pos", "text", "life", "max_life", "crit")

    def __init__(self) -> None:
        self.active = False
        self.pos = pygame.Vector2()
        self.text = ""
        self.life = 0.0
        self.max_life = 0.6
        self.crit = False

    def update(self, dt: float) -> None:
        self.pos.y -= 38 * dt  # drift upward
        self.life -= dt
        if self.life <= 0.0:
            self.active = False


class DamageNumbers:
    def __init__(self, max_numbers: int = config.MAX_DAMAGE_NUMBERS) -> None:
        self._pool: Pool[DamageNumber] = Pool(DamageNumber, max_numbers, prefill=32)
        self._font: pygame.font.Font | None = None
        self._font_crit: pygame.font.Font | None = None

    def __len__(self) -> int:
        return len(self._pool)

    def _fonts(self):
        if self._font is None:
            self._font = pygame.font.SysFont("arialrounded", 16, bold=True)
            self._font_crit = pygame.font.SysFont("arialrounded", 22, bold=True)
        return self._font, self._font_crit

    def add(self, pos: pygame.Vector2, amount: float, crit: bool = False) -> None:
        n = self._pool.acquire()
        if n is None:
            return
        n.pos.update(pos.x, pos.y - 10)
        n.text = str(int(round(amount)))
        n.life = n.max_life = 0.6
        n.crit = crit

    def update(self, dt: float) -> None:
        for n in self._pool:
            n.update(dt)
        self._pool.sweep()

    def draw(self, surface: pygame.Surface, camera) -> None:
        font, font_crit = self._fonts()
        for n in self._pool:
            frac = max(0.0, min(1.0, n.life / n.max_life))
            colour = config.COLOR_ACCENT if n.crit else config.COLOR_TEXT
            glyph = (font_crit if n.crit else font).render(n.text, True, colour)
            glyph.set_alpha(int(255 * frac))
            sx, sy = camera.world_to_screen(n.pos)
            surface.blit(glyph, glyph.get_rect(center=(sx, sy)))

    def clear(self) -> None:
        self._pool.clear()
