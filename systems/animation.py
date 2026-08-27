"""Frame-timed sprite animation.

An `Animator` tracks *time*, nothing else. It reads frame count / fps / loop
from `game.assets.Assets` for the current `(rig, anim)` and hands back the frame
to draw. It never touches gameplay state -- callers push an animation name each
frame (`play`) based on what the entity is doing.
"""
from __future__ import annotations


class Animator:
    def __init__(self, assets, rig: str, start: str = "idle") -> None:
        self.assets = assets
        self.rig = rig
        self.anim = start
        self.t = 0.0

    def play(self, anim: str, *, restart: bool = False) -> None:
        """Switch animation. A no-op if already playing `anim` (unless
        `restart`), so a held state keeps its phase."""
        if anim != self.anim or restart:
            self.anim = anim
            self.t = 0.0

    def update(self, dt: float) -> None:
        self.t += dt

    @property
    def index(self) -> int:
        n = max(1, self.assets.frame_count(self.rig, self.anim))
        raw = int(self.t * self.assets.fps(self.rig, self.anim))
        return raw % n if self.assets.loops(self.rig, self.anim) else min(raw, n - 1)

    @property
    def finished(self) -> bool:
        """True once a one-shot animation has shown its last frame. Loops are
        never finished."""
        if self.assets.loops(self.rig, self.anim):
            return False
        n = self.assets.frame_count(self.rig, self.anim)
        return self.t * self.assets.fps(self.rig, self.anim) >= n

    def frame(self, *, size=None, flip: bool = False):
        return self.assets.frame(self.rig, self.anim, self.index,
                                 size=size, flip=flip)
