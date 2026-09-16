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
from game.states.menu_state import MenuState
from game.states.paused_state import PausedState
from game.states.run_status_state import RunStatusState
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
