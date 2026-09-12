"""GAME_OVER: the run résumé after the player dies.

The readout itself is `ui.run_summary.RunSummaryPanel` -- three ribboned
columns: the run (time, level, kills, gold, salvage, items acquired), the
enemies slain per type with the blessings and their levels, and the damage
done per weapon with its DPS over the time the weapon was held (journal:
`documentation/journals/game_over_journal.md`).

Under it, three of the pack's wide buttons, driven like every other menu
(`ui.mouse`): hovering selects, a click (press and release on one button)
picks. Left / Right (also A / D) move the cursor; ENTER / SPACE pick it. The
direct keys the screen always had still work from anywhere on it -- S opens
the Sanctuary, ESC returns to the menu -- and the cursor starts on New run,
so ENTER alone starts another run as it always did.

Only KEYDOWN and a completed click leave: the *release* of the key that
killed the run must not skip the summary before it was read.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from game.state import State
from ui import widgets
from ui.mouse import MouseNav
from ui.run_summary import RunSummaryPanel

BACKDROP = (22, 10, 12)
_BUTTONS = ("new_run", "sanctuary", "menu")
_LABELS = {"new_run": "New run", "sanctuary": "Sanctuary", "menu": "Main menu"}
_KEYS = {"new_run": "ENTER", "sanctuary": "S", "menu": "ESC"}
# 64-px `wide` buttons in a row above the hint line.
_BTN_W, _BTN_H, _BTN_GAP, _BTN_CY = 400, 64, 40, 812
_PANEL_TOP, _PANEL_BOTTOM = 178, 762


class GameOverState(State):
    def enter(self, *, stats: dict | None = None, **kwargs) -> None:
        self.stats = stats or {}
        self.sel = 0
        self._title_font = fonts.heading(64)
        self._sub_font = fonts.body(22)
        self._btn_font = fonts.body(26)
        self._hint_font = fonts.body(16)
        self._panel = RunSummaryPanel(self.stats)
        self._mouse = MouseNav()     # buttons registered in draw(); see ui/mouse.py

    # --- input -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        act = self._mouse.event(event)
        if act is not None:
            kind, i = act
            self.sel = i
            if kind == "click":
                self._activate(_BUTTONS[i])
            return
        if event.type != pygame.KEYDOWN:
            return
        k = event.key
        if k in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate(_BUTTONS[self.sel])
        elif k == pygame.K_s:
            self._activate("sanctuary")
        elif k == pygame.K_ESCAPE:
            self._activate("menu")
        elif k in (pygame.K_LEFT, pygame.K_a):
            self.sel = (self.sel - 1) % len(_BUTTONS)
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.sel = (self.sel + 1) % len(_BUTTONS)

    def _activate(self, bid: str) -> None:
        if bid == "new_run":
            from game.states.character_select_state import CharacterSelectState
            self.game.state_machine.change(CharacterSelectState(self.game))
        elif bid == "sanctuary":
            from game.states.meta_state import MetaState
            self.game.state_machine.change(MetaState(self.game))
        elif bid == "menu":
            from game.states.menu_state import MenuState
            self.game.state_machine.change(MenuState(self.game))

    # --- render ------------------------------------------------------
    def _subtitle(self) -> str:
        s = self.stats
        parts = [str(s.get("character", "-"))]
        diff = s.get("difficulty")
        if diff:
            parts.append(config.DIFFICULTY_LABELS.get(diff, str(diff)))
        if s.get("seed") is not None:
            parts.append(f"seed {s['seed']}")
        return "   -   ".join(parts)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BACKDROP)
        assets = getattr(self.game, "assets", None)
        cx = surface.get_width() // 2

        title = self._title_font.render("Game Over", True, (230, 90, 90))
        surface.blit(title, title.get_rect(center=(cx, 66)))
        sub = self._sub_font.render(self._subtitle(), True, config.COLOR_TEXT_DIM)
        surface.blit(sub, sub.get_rect(center=(cx, 118)))

        self._panel.draw(surface, assets, _PANEL_TOP, _PANEL_BOTTOM)

        hits = self._mouse.hits
        hits.clear()
        total_w = len(_BUTTONS) * _BTN_W + (len(_BUTTONS) - 1) * _BTN_GAP
        x0 = cx - total_w // 2
        for i, bid in enumerate(_BUTTONS):
            rect = pygame.Rect(x0 + i * (_BTN_W + _BTN_GAP), 0, _BTN_W, _BTN_H)
            rect.centery = _BTN_CY
            hits.add(rect, i)                 # the button *is* the mouse target
            state = ("pressed" if self._mouse.pressed_on == i
                     else "hover" if i == self.sel else "normal")
            widgets.draw_button(surface, assets, rect, _LABELS[bid], state=state,
                                shape="wide", variant="danger" if bid == "menu" else "primary",
                                font=self._btn_font)

        hint = self._hint_font.render(
            "   -   ".join(f"{_KEYS[b]} {_LABELS[b].lower()}" for b in _BUTTONS)
            + "   -   Left / Right select",
            True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(cx, _BTN_CY + _BTN_H // 2 + 30)))
