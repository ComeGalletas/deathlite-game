"""Floating damage numbers (spec 3.6). Pooled and capped.

Numbers rise and fade. Crits render larger and in the accent colour; damage the
hero *takes* renders red and 25% larger than the common number, so the player
reads build spikes -- and their own health draining -- at a glance.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from systems.object_pool import Pool

_BASE_PT = 16
_CRIT_PT = 22
_IN_PT = round(_BASE_PT * 1.25)       # incoming damage: 25% bigger than common


class DamageNumber:
    __slots__ = ("active", "pos", "text", "life", "max_life", "crit", "incoming")

    def __init__(self) -> None:
        self.active = False
        self.pos = pygame.Vector2()
        self.text = ""
        self.life = 0.0
        self.max_life = 0.6
        self.crit = False
        self.incoming = False

    def update(self, dt: float) -> None:
        self.pos.y -= 38 * dt  # drift upward
        self.life -= dt
        if self.life <= 0.0:
            self.active = False


class DamageNumbers:
    def __init__(self, max_numbers: int = config.MAX_DAMAGE_NUMBERS) -> None:
        self._pool: Pool[DamageNumber] = Pool(DamageNumber, max_numbers, prefill=32)
        self._font_cache: dict[int, tuple] = {}   # zoom-key -> (common, crit, incoming)

    def __len__(self) -> int:
        return len(self._pool)

    def _fonts(self, zoom: float = 1.0):
        """The (common, crit, incoming) font trio, sized for the camera zoom so
        world-space numbers scale with everything else. Cached per zoom."""
        key = max(1, round(zoom * 100))
        trio = self._font_cache.get(key)
        if trio is None:
            def f(pt):
                return fonts.body(max(6, round(pt * zoom)), bold=True)
            trio = (f(_BASE_PT), f(_CRIT_PT), f(_IN_PT))
            self._font_cache[key] = trio
        return trio

    def add(self, pos: pygame.Vector2, amount: float, crit: bool = False,
            incoming: bool = False) -> None:
        n = self._pool.acquire()
        if n is None:
            return
        n.pos.update(pos.x, pos.y - 10)
        n.text = str(int(round(amount)))
        n.life = n.max_life = 0.6
        n.crit = crit
        n.incoming = incoming

    def update(self, dt: float) -> None:
        for n in self._pool:
            n.update(dt)
        self._pool.sweep()

    def draw(self, surface: pygame.Surface, camera) -> None:
        font, font_crit, font_in = self._fonts(getattr(camera, "zoom", 1.0))
        for n in self._pool:
            frac = max(0.0, min(1.0, n.life / n.max_life))
            if n.incoming:
                fnt, colour = font_in, config.COLOR_DAMAGE_IN
            elif n.crit:
                fnt, colour = font_crit, config.COLOR_ACCENT
            else:
                fnt, colour = font, config.COLOR_TEXT
            glyph = fnt.render(n.text, True, colour)
            glyph.set_alpha(int(255 * frac))
            sx, sy = camera.world_to_screen(n.pos)
            surface.blit(glyph, glyph.get_rect(center=(sx, sy)))

    def clear(self) -> None:
        self._pool.clear()
