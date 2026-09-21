"""The run's opening hints: Move, then Attack (journal:
key_icons_journal.md, pass 5).

Every run opens with them (owner, 2026-09-19: not a first-run flag -- the
player switches them off with the **Tutorials** row in Options,
`game.tutorials`). Two stages, one after the other, each a cluster of blue
keycaps over the hero's head (`visual/hints.py` draws them):

  * ``move``   -- the layout's four move keys. Done once the hero has
                  travelled `config.HINT_MOVE_DISTANCE` from the spawn.
  * ``attack`` -- the mouse cap and the four aim keys. Done on the first
                  attack the player aims themselves (a click or a held aim
                  key -- `ps._aim.source`), or after
                  `config.HINT_ATTACK_SECONDS`: auto attack is on by
                  default, so the hero may already be fighting.

A finished cluster fades over `config.HINT_FADE` before the next appears.
ESC (the pause menu, which lists every key) dismisses the lot for this run.
There is no Interact stage: the floating `E` over a chest is that hint.
"""
from __future__ import annotations

import pygame

from game import config
from ui import keycap

STAGES = ("move", "attack")
_DIRECTIONS = ("up", "left", "down", "right")


class RunHints:
    def __init__(self, ps) -> None:
        self.ps = ps
        self.run = getattr(ps, "run", ps)
        self.enabled = bool(config.TUTORIAL_HINTS) and bool(ps.game.tutorials)
        self.stage: str | None = "move" if self.enabled else None
        self.spawn = pygame.Vector2(ps.player.pos)
        self.t = 0.0                    # seconds in the current stage
        # `(clusters, seconds left)` of the stage that just finished, while
        # it fades; the next stage waits for it.
        self.fading: tuple[list, float] | None = None

    # --- state -------------------------------------------------------
    @property
    def active(self) -> bool:
        return self.stage is not None

    @property
    def visible(self) -> bool:
        return self.stage is not None or self.fading is not None

    def update(self, dt: float) -> None:
        if self.fading is not None:
            clusters, left = self.fading
            left -= dt
            self.fading = (clusters, left) if left > 0.0 else None
        if self.stage is None:
            return
        self.t += dt
        if self.stage == "move":
            if (self.run.player.pos - self.spawn).length() >= config.HINT_MOVE_DISTANCE:
                self._advance("attack")
        elif self.stage == "attack":
            aim = getattr(self.ps, "_aim", None)
            aimed = aim is not None and getattr(aim, "source", None) is not None
            if aimed or self.t >= config.HINT_ATTACK_SECONDS:
                self._advance(None)

    def _advance(self, nxt: str | None) -> None:
        self.fading = (self.clusters(), float(config.HINT_FADE))
        self.stage = nxt
        self.t = 0.0

    def dismiss(self) -> None:
        """ESC: the pause menu lists every key; nothing more to teach."""
        self.stage = None
        self.fading = None

    # --- what to draw ------------------------------------------------
    def _keys(self, group: str) -> dict[str, tuple[int, ...]]:
        return config.KEY_LAYOUTS[self.ps.game.key_layout][group]

    @staticmethod
    def _cluster(keys: dict[str, tuple[int, ...]]) -> list[list[str]]:
        """A keyboard-shaped cluster: the up key over left / down / right."""
        lab = {d: keycap.label_for(keys[d][0]) for d in _DIRECTIONS}
        return [[lab["up"]], [lab["left"], lab["down"], lab["right"]]]

    def clusters(self, stage: str | None = None) -> list[tuple[str, list[list[str]]]]:
        """`[(word, rows of cap labels), ...]` for `stage` (the current one
        by default): what the hint shows, left to right."""
        stage = self.stage if stage is None else stage
        if stage == "move":
            return [("Move", self._cluster(self._keys("move")))]
        if stage == "attack":
            return [("Attack", [[keycap.MOUSE]]), ("Aim", self._cluster(self._keys("aim")))]
        return []

    def keycodes_for(self, label: str) -> tuple[int, ...]:
        """The keys a cap with `label` stands for, so the drawing can show
        it pressed while one of them is held."""
        out = []
        for group in ("move", "aim"):
            for d in _DIRECTIONS:
                codes = self._keys(group)[d]
                if codes and keycap.label_for(codes[0]) == label:
                    out.extend(codes)
        return tuple(out)

    def held(self, label: str) -> bool:
        """Is the key (or the mouse button) this cap stands for down now?
        False when the input cannot be read (no display -- the suite)."""
        try:
            if label == keycap.MOUSE:
                return bool(pygame.mouse.get_pressed()[0])
            pressed = pygame.key.get_pressed()
            return any(pressed[k] for k in self.keycodes_for(label))
        except (pygame.error, IndexError):
            return False
