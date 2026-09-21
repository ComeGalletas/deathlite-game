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
from ui.menu_nav import MenuNav
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
        # The ribbons run left to right and 1 / 2 / 3 pick one; Up / Down
        # come back as the cross axis and move the pane's selection. TAB
        # closes as ESC does. Tabs and rows are registered in draw().
        self._nav = MenuNav(axis="h", numbers=True,
                            back_keys=(pygame.K_TAB, pygame.K_ESCAPE))
        self._mouse = self._nav.mouse

    @property
    def pane(self):
        return self._panes[PANES[self.tab]]

    # --- input -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            self.pane.move(-int(event.y))
            return
        verb = self._nav.event(event, index=self.tab, count=len(PANES))
        if verb is None:
            return
        what, v = verb
        if what == "back":
            self._close()
        elif what in ("move", "activate"):
            if isinstance(v, tuple):               # a registered target
                kind, i = v
                if kind == "tab":
                    self.tab = i
                elif kind == "row" and hasattr(self.pane, "select"):
                    self.pane.select(i)
            else:
                self.tab = v
        elif what == "number":
            self.tab = v
        elif what == "axis":
            self.pane.move(v)

    def _close(self) -> None:
        self.game.state_machine.pop()

    # --- render ------------------------------------------------------
    def draw_backdrop(self, surface: pygame.Surface) -> None:
        c.draw_dim(surface)                  # the whole surface, margins included

    def draw(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        mx, top, bottom = c.S(_MARGIN_X), c.S(_TOP), c.S(_BOTTOM)
        panel = pygame.Rect(mx, top, w - 2 * mx, h - top - bottom)
        c.draw_panel(surface, panel)
        hits = self._mouse.hits
        hits.clear()
        assets = getattr(self.game, "assets", None)
        c.draw_tabs(surface, assets, panel, [LABELS[p] for p in PANES], self.tab,
                    self._fonts.ribbon, hits)
        area = pygame.Rect(panel.left + c.S(28), panel.top + c.S(c.RIBBON_H) // 2 + c.S(8 + 18),
                           panel.width - c.S(56), 0)
        area.height = panel.bottom - c.S(24) - area.top
        if self.playing is None:
            t = self._fonts.row.render("no run", True, config.COLOR_TEXT_DIM)
            surface.blit(t, t.get_rect(center=panel.center))
        else:
            self.pane.draw(surface, area, self.playing, hits)

        hint = self._hint.render(
            "TAB / ESC close   -   Left / Right or 1 2 3 switch pane   -   "
            "Up / Down or wheel select", True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(w // 2, h - bottom // 2)))
