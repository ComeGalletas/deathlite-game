"""`TimedVisual`: one short-lived effect drawn at a point (SYS-009).

The blast rings and bursts on `run._explosions` and the death poofs on
`run._death_fx` used to be a `{pos, radius, t, dur, ...}` dict and a
positional `[anim, pos, facing, scale, radius]` list. Both are now this.

An entry either has a fixed `dur` (the plain expanding ring: `t` runs up to
it) or plays its `anim` out (`dur` is None, and it is finished with the
strip). The Bomb's burst has both, sized so the strip ends at `dur`.

It compares by identity (`eq=False`), as the containers' readers expect: an
entry is found in, and swept out of, its list as the object it is.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pygame


@dataclass(eq=False)
class TimedVisual:
    pos: pygame.Vector2
    anim: Any = None                 # a `systems.animation.Animator`, or None
    radius: float = 0.0              # world px: the blast, or the poofed body
    dur: float | None = None         # seconds; None = as long as `anim` plays
    t: float = 0.0
    facing: int = 1                  # a poof mirrors the body it replaces
    scale: float = 1.0               # a poof's size against its rig
    infusion: Any = None             # a burst's element tint (M13)

    @property
    def finished(self) -> bool:
        if self.dur is not None:
            return self.t >= self.dur
        return self.anim is None or self.anim.finished

    @property
    def progress(self) -> float:
        """0 -> 1 across `dur` (1 when there is none)."""
        return min(1.0, self.t / self.dur) if self.dur else 1.0

    def update(self, dt: float) -> None:
        self.t += dt
        if self.anim is not None:
            self.anim.update(dt)
