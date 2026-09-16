"""GAME_OVER: the run résumé after the player dies.

The screen itself is `ui.end_screen.EndScreen`, shared with the victory screen
-- backdrop, title, the three-column `ui.run_summary.RunSummaryPanel`, the
button row with mouse support, and the hint line (journal:
`documentation/journals/game_over_journal.md`, and
`documentation/journals/victory_screen_journal.md` for the split). This module
is now only what makes the screen *this* screen: the words, the red, the three
destinations.

Hovering selects and a click picks; Left / Right (also A / D) move the cursor
and ENTER / SPACE pick it. The direct keys still work from anywhere -- S opens
the Sanctuary, ESC returns to the menu -- and the cursor starts on New run, so
ENTER alone starts another run as it always did.
"""
from __future__ import annotations

import pygame

from game.state import State
from ui import end_screen
from ui.end_screen import Button

BACKDROP = (22, 10, 12)
TITLE_COLOUR = (230, 90, 90)
BUTTONS = (
    Button("new_run", "New run", "ENTER"),
    Button("sanctuary", "Sanctuary", "S", pygame.K_s),
    Button("menu", "Main menu", "ESC", pygame.K_ESCAPE, variant="danger"),
)


class GameOverState(State):
    backdrop = BACKDROP     # the whole surface; the panel goes on the box
    def enter(self, *, stats: dict | None = None, **kwargs) -> None:
        self.stats = stats or {}
        self._screen = end_screen.EndScreen(
            self.stats, title="Game Over", title_colour=TITLE_COLOUR,
            backdrop=BACKDROP, buttons=BUTTONS,
            subtitle=end_screen.run_subtitle(self.stats))

    # The selection and the mouse live on the shared frame; these keep the
    # names the screen has always exposed.
    @property
    def sel(self) -> int:
        return self._screen.sel

    @sel.setter
    def sel(self, value: int) -> None:
        self._screen.sel = value

    @property
    def _mouse(self):
        return self._screen.mouse

    # --- input -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        bid = self._screen.handle_event(event)
        if bid is not None:
            self._activate(bid)

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
    def draw(self, surface: pygame.Surface) -> None:
        self._screen.draw(surface, getattr(self.game, "assets", None))
