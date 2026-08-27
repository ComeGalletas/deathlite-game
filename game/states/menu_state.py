"""MENU: title screen and entry point into a run."""
from __future__ import annotations

import pygame

from game import config
from game.state import State


class MenuState(State):
    def enter(self, **kwargs) -> None:
        self._title_font = pygame.font.SysFont("georgia", 64, bold=True)
        self._font = pygame.font.SysFont("georgia", 24)
        self._small = pygame.font.SysFont("georgia", 18)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            # Imported here to avoid a circular import at module load.
            from game.states.character_select_state import CharacterSelectState
            self.game.state_machine.change(CharacterSelectState(self.game))
        elif event.key == pygame.K_s:
            from game.states.meta_state import MetaState
            self.game.state_machine.change(MetaState(self.game))
        elif event.key == pygame.K_ESCAPE:
            self.game.quit()

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(config.COLOR_BG)
        cx = config.SCREEN_WIDTH // 2

        title = self._title_font.render(config.TITLE, True, config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(cx, 200)))

        for i, line in enumerate((
            "Press  ENTER  or  SPACE  to begin",
            "S  -  Sanctuary (spend Salvage, equip items)",
            "WASD / Arrows to move    -    ESC to pause    -    M to mute",
            "Weapons fire on their own. Survive, level up, beat the boss.",
            "F1 toggles the debug overlay",
        )):
            colour = config.COLOR_TEXT if i == 0 else config.COLOR_TEXT_DIM
            text = self._font.render(line, True, colour)
            surface.blit(text, text.get_rect(center=(cx, 320 + i * 38)))

        save = self.game.save
        best = save.best
        summary = (f"Salvage {save.currency}    "
                   f"Best: {best.get('time', 0):.0f}s / Lv {int(best.get('level', 1))} / "
                   f"{int(best.get('kills', 0))} kills    "
                   f"Items found {len(save.discovered_items)}")
        s = self._small.render(summary, True, config.COLOR_TEXT_DIM)
        surface.blit(s, s.get_rect(center=(cx, 320 + 5 * 38 + 16)))
