"""Screen shake (spec 3.6: "for major events, used sparingly").

A decaying trauma value drives a small random camera offset. Callers `add()`
trauma on big events (boss spawn, player hit, elite death); it decays to zero on
its own.
"""
from __future__ import annotations

import random

import pygame


class ScreenShake:
    def __init__(self, max_offset: float = 14.0) -> None:
        self.trauma = 0.0          # 0..1
        self.max_offset = max_offset
        self._offset = pygame.Vector2()

    def add(self, amount: float) -> None:
        self.trauma = min(1.0, self.trauma + amount)

    def update(self, dt: float) -> None:
        # Decay ~1.5 trauma/sec so a single hit settles in well under a second.
        self.trauma = max(0.0, self.trauma - 1.5 * dt)
        shake = self.trauma * self.trauma  # ease-out: subtle at low trauma
        self._offset.update(
            random.uniform(-1, 1) * self.max_offset * shake,
            random.uniform(-1, 1) * self.max_offset * shake,
        )

    @property
    def offset(self) -> pygame.Vector2:
        return self._offset
