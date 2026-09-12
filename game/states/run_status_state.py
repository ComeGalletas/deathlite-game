"""RUN_STATUS: the build screen, an overlay over the frozen run (journal:
`documentation/journals/run_status_journal.md`).

TAB opens it from the run and closes it; ESC closes it too; the pause menu's
"Run status" row opens it as well. Like PAUSED it draws the world beneath a
dim layer and does not advance it (`update_below = False`).

Three panes under three ribbons -- Overview (the run, the hero, the equipped
items with their bonuses, the stats), Build (the weapons with their live
numbers, Forgings and the Forge gate, then the synergies) and Blessings (the
owned blessings and the selected one's card text at its current level).
Left / Right (A / D, or 1 / 2 / 3) switch panes; Up / Down (W / S) and the
mouse wheel move a pane's selection; the mouse hovers and clicks the ribbons
and the rows through `ui.mouse.MouseNav`.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from game.state import State
from ui import widgets
from ui.mouse import MouseNav
from ui.run_status import BlessingsPane, BuildPane, OverviewPane
from ui.run_status import common as c

PANES = ("overview", "build", "blessings")
LABELS = {"overview": "Overview", "build": "Build", "blessings": "Blessings"}
_MARGIN_X, _TOP, _BOTTOM = 60, 96, 56


def find_playing(state_machine):
    """The run under the overlays: the lowest state on the stack that has a
    `player` (the pause menu opens this screen from one level up)."""
    for state in getattr(state_machine, "_stack", ()):
        if hasattr(state, "player") and hasattr(state, "stats"):
            return state
    return None


class RunStatusState(State):
    draw_below = True
    update_below = False

    def enter(self, *, playing=None, pane: str = "overview", **kwargs) -> None:
        self.playing = playing if playing is not None else find_playing(self.game.state_machine)
        self.tab = PANES.index(pane) if pane in PANES else 0
        self._fonts = c.Fonts()
        self._hint = fonts.body(16)
        self._panes = {"overview": OverviewPane(self._fonts),
                       "build": BuildPane(self._fonts),
                       "blessings": BlessingsPane(self._fonts)}
        self._mouse = MouseNav()     # tabs and rows registered in draw()

    @property
    def pane(self):
        return self._panes[PANES[self.tab]]

    # --- input -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            self.pane.move(-int(event.y))
            return
        act = self._mouse.event(event)
        if act is not None:
            kind, key = act
            what, i = key
            if what == "tab":
                self.tab = i
            elif what == "row" and hasattr(self.pane, "select"):
                self.pane.select(i)
            return
        if event.type != pygame.KEYDOWN:
            return
        k = event.key
        if k in (pygame.K_TAB, pygame.K_ESCAPE):
            self._close()
        elif k in (pygame.K_LEFT, pygame.K_a):
            self.tab = (self.tab - 1) % len(PANES)
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.tab = (self.tab + 1) % len(PANES)
        elif k in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.tab = k - pygame.K_1
        elif k in (pygame.K_UP, pygame.K_w):
            self.pane.move(-1)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.pane.move(1)

    def _close(self) -> None:
        self.game.state_machine.pop()

    # --- render ------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        c.draw_dim(surface)
        w, h = surface.get_size()
        panel = pygame.Rect(_MARGIN_X, _TOP, w - 2 * _MARGIN_X, h - _TOP - _BOTTOM)
        c.draw_panel(surface, panel)
        hits = self._mouse.hits
        hits.clear()
        assets = getattr(self.game, "assets", None)
        c.draw_tabs(surface, assets, panel, [LABELS[p] for p in PANES], self.tab,
                    self._fonts.ribbon, hits)
        area = pygame.Rect(panel.left + 28, panel.top + c.RIBBON_H // 2 + 8 + 18,
                           panel.width - 56, 0)
        area.height = panel.bottom - 24 - area.top
        if self.playing is None:
            t = self._fonts.row.render("no run", True, config.COLOR_TEXT_DIM)
            surface.blit(t, t.get_rect(center=panel.center))
        else:
            self.pane.draw(surface, area, self.playing, hits)

        hint = self._hint.render(
            "TAB / ESC close   -   Left / Right or 1 2 3 switch pane   -   "
            "Up / Down or wheel select", True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(w // 2, h - _BOTTOM // 2)))
