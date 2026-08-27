"""Ground hazards (spec 5.6 area-denial): a lingering circle that damages the
player while they stand in it. Spawned by the Warlock enemy after a telegraph.
Plain list-managed (few exist at once); short-lived.

Damage lands as timed "bites", not once per frame: every `tick_interval`
seconds of exposure the pool deals `dps * tick_interval` before armor. This
keeps the pre-armor DPS equal to `dps` while letting flat armor bite a
meaningful chunk (see journals/BUG_JOURNAL.md #1). `tick_interval` defaults to
`config.INCOMING_TICK_INTERVAL`; a faster/heavier pool can pass its own.
"""
from __future__ import annotations

import pygame

from game import config


class Hazard:
    __slots__ = ("pos", "radius", "dps", "life", "max_life", "color",
                 "tick_interval", "_tick_accum")

    def __init__(self, x: float, y: float, radius: float, dps: float,
                 duration: float, color=(200, 90, 220),
                 tick_interval: float | None = None) -> None:
        self.pos = pygame.Vector2(x, y)
        self.radius = radius
        self.dps = dps
        self.life = self.max_life = duration
        self.color = color
        self.tick_interval = float(tick_interval or config.INCOMING_TICK_INTERVAL)
        self._tick_accum = 0.0

    @property
    def alive(self) -> bool:
        return self.life > 0.0

    def update(self, dt: float) -> None:
        self.life -= dt

    def contains(self, point: pygame.Vector2, pad: float = 0.0) -> bool:
        return (point - self.pos).length_squared() <= (self.radius + pad) ** 2

    def due_damage(self, dt: float) -> float:
        """Advance the exposure clock by `dt` and return the pre-armor damage
        owed this frame -- `dps * tick_interval` for every whole interval that
        has piled up, else 0.0. Call once per frame while the player is inside;
        reset the accumulator (`reset_ticks()`) once they leave."""
        self._tick_accum += dt
        owed = 0.0
        while self._tick_accum >= self.tick_interval:
            self._tick_accum -= self.tick_interval
            owed += self.dps * self.tick_interval
        return owed

    def reset_ticks(self) -> None:
        self._tick_accum = 0.0
