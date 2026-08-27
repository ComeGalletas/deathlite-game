"""Developer overlay (spec section 6.4 & 9).

Toggled with F1. Shows FPS plus timing / entity counters. Never required for
normal play -- purely diagnostic. States feed it numbers via `set_metric`.
"""
from __future__ import annotations

import pygame

from game import config


class DebugOverlay:
    def __init__(self) -> None:
        self.visible = config.DEBUG_OVERLAY_DEFAULT
        self._font: pygame.font.Font | None = None
        self._metrics: dict[str, str] = {}
        # Rolling averages so the numbers are readable, not a blur.
        self._fps_samples: list[float] = []
        self._update_ms = 0.0
        self._render_ms = 0.0

    def _ensure_font(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("consolas", 16)
        return self._font

    def toggle(self) -> None:
        self.visible = not self.visible

    def set_metric(self, key: str, value) -> None:
        self._metrics[key] = str(value)

    def record_timing(self, update_ms: float, render_ms: float) -> None:
        # Light smoothing.
        self._update_ms += (update_ms - self._update_ms) * 0.1
        self._render_ms += (render_ms - self._render_ms) * 0.1

    def draw(self, surface: pygame.Surface, clock: pygame.time.Clock) -> None:
        if not self.visible:
            return
        font = self._ensure_font()
        lines = [
            f"FPS        {clock.get_fps():5.1f}",
            f"update ms  {self._update_ms:5.2f}",
            f"render ms  {self._render_ms:5.2f}",
        ]
        for key, value in self._metrics.items():
            lines.append(f"{key:<10} {value}")

        pad = 6
        line_h = font.get_linesize()
        box = pygame.Surface((260, pad * 2 + line_h * len(lines)), pygame.SRCALPHA)
        box.fill((0, 0, 0, 150))
        surface.blit(box, (8, 8))
        for i, line in enumerate(lines):
            surface.blit(font.render(line, True, config.COLOR_DEBUG),
                         (8 + pad, 8 + pad + i * line_h))
