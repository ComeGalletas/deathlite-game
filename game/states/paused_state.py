"""PAUSED: overlay that freezes the run beneath it.

A small cursor menu (CB-5): Up / Down (also W / S) move, ENTER / SPACE picks.
The mouse drives the same cursor: hovering a row selects it, a click (press
and release on one row) picks it (`ui.mouse`). Each row is one of the pack's
wide buttons (`ui.widgets`): the selected row is the gold one, a held row
sinks, and Quit to menu is red.

  * Resume        -- back to the run (ESC / P do the same from anywhere here)
  * Key layout    -- cycles `config.KEY_LAYOUTS`; persisted at once (also in
                     the Options screen)
  * Quit to menu  -- abandons the run

There is deliberately no single-letter quit: `Q` is the in-run auto-attack
toggle, and a habit of tapping it must never cost the run from this screen.
`M` is the global mute key and never reaches this state.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from game.state import State
from ui import widgets
from ui.mouse import MouseNav

_ROWS = ("resume", "key_layout", "quit")
# 64-px `wide` buttons on a 72-px step; the Quit row on the red sheet.
_ROW_TOP, _ROW_STEP, _ROW_H, _ROW_W = 330, 72, 64, 560
_DANGER = {"quit"}
_LABELS = {"resume": "Resume", "key_layout": "Key layout", "quit": "Quit to menu"}


class PausedState(State):
    draw_below = True      # keep the frozen game visible behind the dim layer
    update_below = False   # ...but do not advance it

    def enter(self, **kwargs) -> None:
        self.sel = 0
        self._title_font = fonts.heading(48)
        self._font = fonts.body(26)
        self._hint = fonts.body(16)
        self._mouse = MouseNav()     # rows registered in draw(); see ui/mouse.py

    # --- input -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        act = self._mouse.event(event)
        if act is not None:
            kind, i = act
            self.sel = i
            if kind == "click":
                self._activate()
            return
        if event.type != pygame.KEYDOWN:
            return
        k = event.key
        if k in (pygame.K_ESCAPE, pygame.K_p):
            self._resume()
        elif k in (pygame.K_UP, pygame.K_w):
            self.sel = (self.sel - 1) % len(_ROWS)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.sel = (self.sel + 1) % len(_ROWS)
        elif k in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
            if _ROWS[self.sel] == "key_layout":
                self.game.cycle_key_layout()
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate()

    def _activate(self) -> None:
        rid = _ROWS[self.sel]
        if rid == "resume":
            self._resume()
        elif rid == "key_layout":
            self.game.cycle_key_layout()
        elif rid == "quit":
            from game.states.menu_state import MenuState
            self.game.state_machine.change(MenuState(self.game))

    def _resume(self) -> None:
        self.game.state_machine.pop()

    # --- render ------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        surface.blit(dim, (0, 0))

        cx = config.SCREEN_WIDTH // 2
        title = self._title_font.render("Paused", True, config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(cx, 250)))

        hits = self._mouse.hits
        hits.clear()
        for i, rid in enumerate(_ROWS):
            rect = pygame.Rect(0, 0, _ROW_W, _ROW_H)
            rect.center = (cx, _ROW_TOP + i * _ROW_STEP)
            hits.add(rect, i)                 # the button *is* the mouse target
            state = ("pressed" if self._mouse.pressed_on == i
                     else "hover" if i == self.sel else "normal")
            # The label sits on the left half so the Key layout row can show
            # its value on the right. Hand-blitted, so the lift that
            # `draw_button` gives its own labels (`LABEL_DY`, the art's
            # visual centre) is applied here too; a sunk row shifts both
            # with the art. Black label, dark-grey value: the sheets are light.
            widgets.draw_button(surface, self.game.assets, rect, None, state=state,
                                shape="wide",
                                variant="danger" if rid in _DANGER else "primary")
            dy = widgets.LABEL_DY + (widgets.PRESSED_DY if state == "pressed" else 0)
            lab = self._font.render(_LABELS[rid], True, config.COLOR_ON_BUTTON)
            surface.blit(lab, lab.get_rect(midleft=(rect.left + 40, rect.centery + dy)))
            if rid == "key_layout":
                val = self._font.render(
                    config.KEY_LAYOUT_LABELS[self.game.key_layout], True,
                    config.COLOR_ON_BUTTON_DIM)
                surface.blit(val, val.get_rect(midright=(rect.right - 40, rect.centery + dy)))

        hint = self._hint.render(
            "Up / Down select    -    ENTER pick    -    ESC / P resume",
            True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(
            center=(cx, _ROW_TOP + (len(_ROWS) - 1) * _ROW_STEP + _ROW_H // 2 + 30)))
