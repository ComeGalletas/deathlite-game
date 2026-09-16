"""VICTORY: the run résumé after the final encounter is beaten.

Was a "Milestone 1 stub" -- nine centred text lines, keyboard only -- while the
game-over screen grew a résumé, buttons and mouse support, even though
`PlayingState._end_run` hands both screens the identical stats dict. It now
draws the same `ui.end_screen.EndScreen` frame, so the whole résumé (the
weapon damage split, the kills per type, the blessings, the items with their
rarities) appears here too and the mouse works (owner, 2026-09-12; journal:
`documentation/journals/victory_screen_journal.md`).

The boss that fell leads the subtitle, the Run column says "Cleared in", and
a fourth **Hero** column carries the build: trait, the resolved stat block, what
was equipped, and the first-clear line that announces the main-weapon unlock.

The palette is the one thing here that is not shared with the game-over screen.
The ribbon colours *are* reused (owner, 2026-09-12) so the two read as one
family; what changes is everything around them -- a warm ground instead of the
defeat red, the title in gold, and no `danger` variant on any button. Leading a
win with a red button was the tell that the screen was a recolour of a loss.
"""
from __future__ import annotations

import pygame

from game.state import State
from ui import end_screen
from ui.end_screen import Button
from ui.run_summary import VICTORY_COLUMNS

# A warm, low-saturation ground: bright enough to read as a win against the
# game-over screen's (22, 10, 12), dark enough that the panels' translucent
# fill and the light ribbon art still carry.
BACKDROP = (38, 28, 14)
TITLE_COLOUR = (255, 214, 112)
BUTTONS = (
    Button("new_run", "New run", "ENTER"),
    Button("sanctuary", "Sanctuary", "S", pygame.K_s),
    Button("menu", "Main menu", "ESC", pygame.K_ESCAPE),
)


class VictoryState(State):
    music = None        # fades out, like GAME OVER (owner, 2026-09-16)
    backdrop = BACKDROP     # the whole surface; the panel goes on the box
    def enter(self, *, stats: dict | None = None, **kwargs) -> None:
        self.stats = stats or {}
        self._screen = end_screen.EndScreen(
            self.stats, title="Victory", title_colour=TITLE_COLOUR,
            backdrop=BACKDROP, buttons=BUTTONS,
            columns=VICTORY_COLUMNS,
            subtitle=end_screen.run_subtitle(
                self.stats, lead=(str(self.stats.get("boss", "")),)))

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
