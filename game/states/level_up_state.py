"""LEVEL_UP: overlay that pauses the run and presents 3 weighted upgrade
choices (spec 3.5). Pushed by PlayingState when a level-up is pending; pops
itself once a choice is applied.
"""
from __future__ import annotations

import pygame

from game.state import State
from progression.upgrades import apply_choice
from ui.level_up import LevelUpPanel


class LevelUpState(State):
    draw_below = True      # show the frozen battlefield behind the panel
    update_below = False   # ...frozen: no simulation while choosing

    def enter(self, *, player, choices, on_done=None, **kwargs) -> None:
        self.player = player
        self.choices = list(choices)
        self.on_done = on_done
        self.selected = 0
        self.panel = LevelUpPanel()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN or not self.choices:
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
        self.panel.draw(surface, self.choices, self.selected)
