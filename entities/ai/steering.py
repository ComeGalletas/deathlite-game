"""The movement-intent accumulator a state's components fold into.

Most components `add()` a force vector -- unit-ish, its magnitude is its
strength (heading ~1.0, separation <= 0.6, ...). A dash / blink component
instead `set_velocity()` an absolute world velocity that bypasses the sum.
`resolve()` turns whatever accumulated into the final `actor.vel`.
"""
from __future__ import annotations

import pygame


class Steering:
    __slots__ = ("_acc", "_absolute", "_any")

    def __init__(self) -> None:
        self._acc = pygame.Vector2()
        self._absolute: pygame.Vector2 | None = None
        self._any = False

    def add(self, vec: pygame.Vector2, weight: float = 1.0) -> None:
        if weight and vec.length_squared() > 1e-12:
            self._acc += pygame.Vector2(vec) * weight
            self._any = True

    def set_velocity(self, vec: pygame.Vector2) -> None:
        """Absolute velocity in world units / second; wins over any added forces."""
        self._absolute = pygame.Vector2(vec)

    @property
    def is_empty(self) -> bool:
        return self._absolute is None and not self._any

    def resolve(self, speed: float) -> pygame.Vector2:
        if self._absolute is not None:
            return pygame.Vector2(self._absolute)
        if not self._any or self._acc.length_squared() < 1e-12:
            return pygame.Vector2()
        return self._acc.normalize() * speed
