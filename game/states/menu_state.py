"""MENU: title screen and entry point into a run.

A keyboard-navigated option list sits under the title. ENTER / SPACE activates
the highlighted entry; Up / Down (also W / S and the arrow keys) move the cursor
and wrap; ESC quits. The mouse drives the same cursor: hovering a row selects
it, a click (press and release on one row) activates it (`ui.mouse`). Each row
is one of the pack's wide buttons (`ui.widgets`): the selected row is the gold
one -- that is the cursor -- a held row sinks, and Exit is red.

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

from game import config, fonts
from game.state import State
from ui import widgets
from ui.mouse import MouseNav
from ui.panels import three_slice_h

# The option rows: 64-px `wide` buttons (the pack's native height) on a
# 72-px step, inset from the parchment panel's edges.
_ROW_TOP, _ROW_STEP, _ROW_H, _ROW_INSET = 550, 72, 64, 60
_DANGER = {"exit"}          # drawn on the red sheet


class MenuState(State):
    def enter(self, **kwargs) -> None:
        self._menu_font_px = 24
        self._title_font = fonts.heading(64)
        self._font = fonts.body(self._menu_font_px)
        self._small = fonts.body(16)

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
        self._mouse = MouseNav()     # rows registered in draw(); see ui/mouse.py

    # --- input ---------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        act = self._mouse.event(event)
        if act is not None:
            kind, i = act
            self._index = i
            if kind == "click":
                self._activate(self._options[i][1])
            return
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

        bg = (self.game.assets.picture(config.MENU_BACKGROUND_IMAGE, size=(w, h))
             or self.game.assets.picture(config.MENU_TITLE_IMAGE, size=(w, h)))
        if bg is not None:
            surface.blit(bg, (0, 0))

        panel_width, panel_height = 625, 495   # +25% on both axes (was 500x320)
        band = pygame.Rect((w - panel_width) // 2, 890 - panel_height,
                           panel_width, panel_height)  # bottom pinned at 890, clear of the save summary

        logo_native = self.game.assets.picture(config.MENU_LOGO_IMAGE)
        if logo_native is not None:
            logo_h = 390
            logo_w = round(logo_h * logo_native.get_width() / logo_native.get_height())
            logo = self.game.assets.picture(config.MENU_LOGO_IMAGE, size=(logo_w, logo_h))
            surface.blit(logo, logo.get_rect(center=(cx, band.top - logo_h // 2 + 50 )))
        else:
            # Fallback: the title as text when the logo art is absent.
            title = self._title_font.render(config.TITLE, True, config.MENU_FG)
            surface.blit(title, title.get_rect(center=(cx, band.top - 60)))

        panel = three_slice_h(self.game.assets, left="ui_banner_cap_left",
                              mid="ui_banner_mid", right="ui_banner_cap_right",
                              width=band.width, height=band.height)
        if panel is not None:
            surface.blit(panel, band.topleft)
        else:
            scrim = pygame.Surface(band.size, pygame.SRCALPHA)
            pygame.draw.rect(scrim, config.MENU_SCRIM, scrim.get_rect(), border_radius=16)
            surface.blit(scrim, band.topleft)

        # --- option list: one button per row, the selected one gold ---
        hits = self._mouse.hits
        hits.clear()
        for i, (label, action) in enumerate(self._options):
            rect = pygame.Rect(band.left + _ROW_INSET, 0, band.width - 2 * _ROW_INSET, _ROW_H)
            rect.centery = _ROW_TOP + i * _ROW_STEP
            hits.add(rect, i)                 # the button *is* the mouse target
            state = ("pressed" if self._mouse.pressed_on == i
                     else "hover" if i == self._index else "normal")
            widgets.draw_button(surface, self.game.assets, rect, label, state=state,
                                shape="wide",
                                variant="danger" if action in _DANGER else "primary",
                                font=self._font)          # black, lifted (ui.widgets)

        # --- save summary, bottom centre ---
        save = self.game.save
        best = save.best
        summary = (f"Salvage {save.currency}    "
                   f"Best: {best.get('time', 0):.0f}s / Lv {int(best.get('level', 1))} / "
                   f"{int(best.get('kills', 0))} kills    "
                   f"Items found {len(save.discovered_items)}")
        s = self._small.render(summary, True, config.MENU_FG_DIM)
        surface.blit(s, s.get_rect(center=(cx, h - 40)))
