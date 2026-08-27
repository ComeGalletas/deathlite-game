"""PAUSED: overlay that freezes the run beneath it."""
from __future__ import annotations

import pygame

from game import config
from game.state import State


class PausedState(State):
    draw_below = True      # keep the frozen game visible behind the dim layer
    update_below = False   # ...but do not advance it

    def enter(self, **kwargs) -> None:
        self._title_font = pygame.font.SysFont("georgia", 48, bold=True)
        self._font = pygame.font.SysFont("georgia", 22)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.game.state_machine.pop()  # resume
            elif event.key == pygame.K_q:
                from game.states.menu_state import MenuState
                self.game.state_machine.change(MenuState(self.game))

    def draw(self, surface: pygame.Surface) -> None:
        dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        surface.blit(dim, (0, 0))

        cx = config.SCREEN_WIDTH // 2
        title = self._title_font.render("Paused", True, config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(cx, 280)))
        for i, line in enumerate((
            "ESC / P  -  resume",
            "Q  -  quit to menu",
        )):
            text = self._font.render(line, True, config.COLOR_TEXT_DIM)
            surface.blit(text, text.get_rect(center=(cx, 350 + i * 34)))
