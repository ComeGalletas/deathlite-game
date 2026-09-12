"""The treasure chest prop (CB-9).

One per `world.layout.Chest`, built once at the start of a run and never
pooled -- a world holds fifteen to twenty of them and none is ever created or
destroyed mid-run. The chest is a position, a tier, and one bit of state: has
it been opened. `age` drives the lid animation after it has, and stops
climbing once the strip has played out so the frame index is stable for the
rest of the run.

The payload is not here. `game/states/playing/chests.py` rolls it from
`data/chests.json` the moment the chest is opened, so a chest's gold is
decided when it is found rather than banked into the world at generation --
`progression/chests.py` holds those rules.
"""
from __future__ import annotations

import pygame


class Chest:
    __slots__ = ("pos", "rarity", "floor", "radius", "opened", "age")

    def __init__(self, x: float, y: float, rarity: str, floor: int = 0,
                 radius: float = 24.0) -> None:
        self.pos = pygame.Vector2(x, y)
        self.rarity = rarity
        self.floor = int(floor)
        self.radius = float(radius)
        self.opened = False
        self.age = 0.0

    def in_range(self, point: pygame.Vector2, pad: float = 40.0) -> bool:
        """Is `point` close enough to open this chest? Same test and the same
        default pad as `Interactable.in_range`, so the E prompt appears at the
        same distance for a chest as it does for a shrine."""
        return (point - self.pos).length_squared() <= (self.radius + pad) ** 2

    def update(self, dt: float, duration: float) -> None:
        """Advance the open animation. Inert while closed, and it stops at
        `duration` so the held frame never drifts."""
        if self.opened and self.age < duration:
            self.age = min(duration, self.age + dt)

    def frame_index(self, frames: int, duration: float) -> int:
        """Which frame of the rig's strip to draw: 0 while closed, then across
        the strip over `duration`, holding the last one."""
        if not self.opened:
            return 0
        if duration <= 0.0:
            return frames - 1
        step = min(frames - 1, int(self.age / duration * frames))
        return max(0, step)
