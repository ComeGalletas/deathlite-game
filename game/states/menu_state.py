"""MENU: title screen and entry point into a run.

A keyboard-navigated option list sits under the title. ENTER / SPACE activates
the highlighted entry; Up / Down (also W / S and the arrow keys) move the cursor
and wrap; ESC quits.

Start-screen milestones: M1 gave the list its navigation; M2 wired "Options" to
the Options screen; M3 gave this screen its own black / white palette and an
optional full-screen title image (`config.MENU_TITLE_IMAGE`) drawn over a text
fallback, with a translucent scrim behind the content so the white text stays
readable over the art. Developer-mode milestone D1 wired the "developer mode"
entry to a non-persistent sandbox run. The game instructions that M4 put in a
left-hand column here later moved to the character-select screen (they read
better next to the hero preview); see `config.MENU_INSTRUCTIONS`.
"""
from __future__ import annotations

import pygame

from game import config
from game.state import State


class MenuState(State):
    def enter(self, **kwargs) -> None:
        self._menu_font_px = 24
        self._title_font = pygame.font.SysFont("georgia", 64, bold=True)
        self._font = pygame.font.SysFont("georgia", self._menu_font_px)
        self._small = pygame.font.SysFont("georgia", 16)

        # (label, action). `action` is dispatched in _activate(); an entry whose
        # action is None is drawn but does nothing when selected.
        self._options: list[tuple[str, str | None]] = [
            ("Start new game", "start"),
            ("Start new developer mode game", "dev_start"),
            ("Rankings", "rankings"),
            ("Options", "options"),
            ("Exit", "exit"),
        ]
        self._index = 0

    # --- input ---------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self._index = (self._index - 1) % len(self._options)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self._index = (self._index + 1) % len(self._options)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate(self._options[self._index][1])
        elif event.key == pygame.K_ESCAPE:
            self.game.quit()

    def _activate(self, action: str | None) -> None:
        # Imported here to avoid a circular import at module load.
        if action in ("start", "dev_start"):
            from game.states.character_select_state import CharacterSelectState
            self.game.state_machine.change(CharacterSelectState(self.game),
                                           dev=(action == "dev_start"))
        elif action == "rankings":
            from game.states.rankings_state import RankingsState
            self.game.state_machine.change(RankingsState(self.game))
        elif action == "options":
            from game.states.options_state import OptionsState
            self.game.state_machine.change(OptionsState(self.game))
        elif action == "exit":
            self.game.quit()
        # action is None -> inert (drawn but does nothing).

    # --- render ------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        w, h = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        cx = w // 2
        surface.fill(config.MENU_BG)

        art = self.game.assets.picture(config.MENU_TITLE_IMAGE, size=(w, h))
        if art is not None:
            surface.blit(art, (0, 0))
        else:
            # Fallback: the title as text when the art file is absent.
            title = self._title_font.render(config.TITLE, True, config.MENU_FG)
            surface.blit(title, title.get_rect(center=(cx, 170)))

        panel_width = 500
        band = pygame.Rect((w - panel_width) // 2, 500, panel_width, 320)
        scrim = pygame.Surface(band.size, pygame.SRCALPHA)
        pygame.draw.rect(scrim, config.MENU_SCRIM, scrim.get_rect(), border_radius=16)
        surface.blit(scrim, band.topleft)

        # --- option list, centred ---
        top, step = 550, 44
        for i, (label, _action) in enumerate(self._options):
            selected = i == self._index
            colour = config.MENU_FG if selected else config.MENU_FG_DIM
            text = self._font.render(label, True, colour)
            rect = text.get_rect(center=(cx, top + i * step))
            surface.blit(text, rect)
            if selected:
                mark = self._font.render(">", True, config.MENU_FG)
                surface.blit(mark, mark.get_rect(midright=(rect.left - 16, rect.centery)))

        nav = self._small.render("Up / Down    -    ENTER select    -    ESC quit",
                                 True, config.MENU_FG_DIM)
        surface.blit(nav, nav.get_rect(center=(cx, top + len(self._options) * step + 6)))

        # --- save summary, bottom centre ---
        save = self.game.save
        best = save.best
        summary = (f"Salvage {save.currency}    "
                   f"Best: {best.get('time', 0):.0f}s / Lv {int(best.get('level', 1))} / "
                   f"{int(best.get('kills', 0))} kills    "
                   f"Items found {len(save.discovered_items)}")
        s = self._small.render(summary, True, config.MENU_FG_DIM)
        surface.blit(s, s.get_rect(center=(cx, h - 40)))
