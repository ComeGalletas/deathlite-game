"""The interface on a 21:9 render (journal "Dynamic window scaling",
"Ultrawide render extent", 2026-09-15): the overlays' dim layers cover the
side margins, the panels and the HUD stay in the centred 16:9 box, and
the menu's own black fills the margins."""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.display import uibox
from game.game import Game
from game.states.game_over_state import GameOverState
from game.states.level_up_state import LevelUpState
from game.states.loading_state import LoadingState
from game.states.menu_state import MenuState
from game.states.paused_state import PausedState
from game.states.run_status_state import RunStatusState
from game.states.victory_state import VictoryState
from ui.level_up import LevelUpPanel
from ui.run_status import common as rs_common

WIDE = (2100, 900)
MARGIN_PX = (100, 450)          # inside the left margin of a 2100-wide render
BOX_PX = (1050, 450)            # the middle of the box


def _game():
    return Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))


def _bright():
    s = pygame.Surface(WIDE)
    s.fill((255, 255, 255))
    return s


class DimCoversTheMarginsTests(unittest.TestCase):
    """Each overlay's `draw_backdrop` darkens a margin pixel exactly as much
    as a box pixel: the dim is painted on the whole render surface."""

    def _assert_dimmed_alike(self, s):
        m, b = s.get_at(MARGIN_PX)[:3], s.get_at(BOX_PX)[:3]
        self.assertEqual(m, b)
        self.assertLess(m[0], 255)

    def test_pause(self):
        game = _game()
        s = _bright()
        PausedState(game).draw_backdrop(s)
        self._assert_dimmed_alike(s)

    def test_level_up(self):
        s = _bright()
        LevelUpPanel.draw_dim(s)
        self._assert_dimmed_alike(s)

    def test_run_status(self):
        game = _game()
        s = _bright()
        RunStatusState(game).draw_backdrop(s)
        self._assert_dimmed_alike(s)
        self.assertIs(rs_common.draw_dim, rs_common.draw_dim)

    def test_the_menu_paints_its_black_behind_the_margins(self):
        game = _game()
        s = _bright()
        MenuState(game).draw_backdrop(s)
        self.assertEqual(s.get_at(MARGIN_PX)[:3], config.MENU_BG)

    def test_on_a_21_9_render_the_menu_draws_the_long_background_edge_to_edge(self):
        # Owner, 2026-09-16: the ultrawide menu uses menu_background_long.png
        # across the whole surface, so the margins carry art, not black.
        game = _game()
        game.display.render_aspect = "21:9"
        s = _bright()
        st = MenuState(game)
        st.draw_backdrop(s)
        self.assertNotEqual(s.get_at(MARGIN_PX)[:3], config.MENU_BG)
        self.assertNotEqual(s.get_at(MARGIN_PX)[:3], (255, 255, 255))
        self.assertNotEqual(s.get_at(BOX_PX)[:3], (255, 255, 255))
        # The box draw leaves that art alone (no 16:9 background over it).
        before = s.get_at((260, 20))[:3]                 # just inside the box, top-left corner
        st.enter()
        st.draw(uibox.box(s))
        self.assertEqual(s.get_at((260, 20))[:3], before)
        game.display.render_aspect = "16:9"
        s2 = _bright()
        MenuState(game).draw_backdrop(s2)
        self.assertEqual(s2.get_at(MARGIN_PX)[:3], config.MENU_BG)


class ScreenBackdropTests(unittest.TestCase):
    """A screen with a background of its own paints it on the whole
    surface (owner, 2026-09-16: the loading screen showed as a black square
    inside the loop's grey on a 21:9 render). Overlays declare none."""

    def _margin_and_box(self, state):
        s = _bright()
        state.draw_backdrop(s)
        return s.get_at(MARGIN_PX)[:3], s.get_at(BOX_PX)[:3]

    def test_the_loading_screen_is_black_edge_to_edge(self):
        game = _game()
        margin, box = self._margin_and_box(LoadingState(game))
        self.assertEqual(margin, box)
        self.assertEqual(margin, LoadingState.backdrop)
        self.assertNotEqual(margin, (255, 255, 255))

    def test_the_end_screens_paint_their_colour_edge_to_edge(self):
        game = _game()
        for cls in (GameOverState, VictoryState):
            margin, box = self._margin_and_box(cls(game))
            self.assertEqual(margin, box, cls.__name__)
            self.assertEqual(margin, cls.backdrop, cls.__name__)

    def test_overlays_declare_no_backdrop_colour(self):
        for cls in (PausedState, LevelUpState, RunStatusState):
            self.assertIsNone(cls.backdrop, cls.__name__)

    def test_a_plain_state_leaves_the_loop_fill_alone(self):
        from game.state import State
        s = _bright()
        State(_game()).draw_backdrop(s)
        self.assertEqual(s.get_at(MARGIN_PX)[:3], (255, 255, 255))


class PanelsStayInTheBoxTests(unittest.TestCase):
    def test_the_pause_buttons_are_centred_in_the_box_not_the_surface(self):
        game = _game()
        st = PausedState(game)
        st.enter()
        s = pygame.Surface(WIDE)
        box = uibox.box(s)
        st.draw(box)
        rects = [st._mouse.hits.rect_of(i) for i in range(4)]
        self.assertTrue(all(r is not None for r in rects))
        for r in rects:
            self.assertEqual(r.centerx, config.UI_WIDTH // 2)     # box coordinates
            self.assertGreaterEqual(r.left, 0)
            self.assertLessEqual(r.right, config.UI_WIDTH)

    def test_a_level_up_draw_without_the_dim_leaves_the_margins_alone(self):
        s = _bright()
        panel = LevelUpPanel()
        panel.draw(uibox.box(s), [], 0, dim=False)
        self.assertEqual(s.get_at(MARGIN_PX)[:3], (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
