"""LEVEL_UP: overlay that pauses the run and presents 3 weighted upgrade
choices (spec 3.5). Pushed by PlayingState when a level-up is pending; pops
itself once a choice is applied.

Mouse (journal: "Mouse support in menus and UI"): hovering a card selects
it, one click (press and release on the same card) picks it -- a mis-pick
here is cheap and the keyboard already picks with a single key. The pick
lands on the *release*, so the run underneath, which polls the held button
every frame, never sees the click as an attack (and `PlayingState` disarms
the mouse while this overlay is up regardless).
"""
from __future__ import annotations

import pygame

from game.state import State
from progression.upgrades import apply_choice
from ui.level_up import LevelUpPanel
from ui.mouse import MouseNav


class LevelUpState(State):
    draw_below = True      # show the frozen battlefield behind the panel
    update_below = False   # ...frozen: no simulation while choosing

    def enter(self, *, player, choices, on_done=None, **kwargs) -> None:
        self.player = player
        self.choices = list(choices)
        self.on_done = on_done
        self.selected = 0
        self.panel = LevelUpPanel()
        self._mouse = MouseNav(self.panel.hits)   # the panel records the cards

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.choices:
            return
        act = self._mouse.event(event)
        if act is not None:
            kind, i = act
            self.selected = i
            if kind == "click":
                self._pick(i)
            return
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        if key in (pygame.K_LEFT, pygame.K_a):
            self.selected = (self.selected - 1) % len(self.choices)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.selected = (self.selected + 1) % len(self.choices)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._pick(self.selected)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            idx = key - pygame.K_1
            if idx < len(self.choices):
                self._pick(idx)

    def _pick(self, index: int) -> None:
        upgrade = self.choices[index]
        apply_choice(self.player, upgrade)
        if self.on_done is not None:
            self.on_done(upgrade)
        self.game.state_machine.pop()

    def draw(self, surface: pygame.Surface) -> None:
        self.panel.draw(surface, self.choices, self.selected,
                        assets=self.game.assets, pressed=self._mouse.pressed_on)
