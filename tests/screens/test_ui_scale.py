"""The interface at a native scale (journal "Native-resolution rendering",
stage 2, 2026-09-16): with `config.RENDER_SCALE` at 1.6 every screen lays
itself out 1.6x larger inside the 1.6x box, fonts follow, and hit rects
follow the layout. At scale 1 every helper is the identity, which the
rest of the screen tests pin without knowing it."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config, fonts
from game.display import uibox
from game.game import Game
from game.states.character_select_state import CharacterSelectState
from game.states.dev_menu_state import DevMenuState
from game.states.game_over_state import GameOverState
from game.states.menu_state import MenuState
from game.states.meta_state import MetaState
from game.states.options_state import OptionsState
from game.states.paused_state import PausedState
from game.states.rankings_state import RankingsState
from game.states.victory_state import VictoryState
from ui import scale
from ui.hud import HUD
from ui.level_up import LevelUpPanel

S = 1.6
NATIVE = (3440, 1440)           # the owner's desktop: the box is 2560x1440 with 440 px margins


def _game():
    return Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))


class _Scaled(unittest.TestCase):
    def setUp(self):
        # The game boots first: opening the (refused, headless) display resets
        # `RENDER_SCALE` to 1, so the patch goes on after it.
        self.game = _game()
        pygame.font.init()
        p = mock.patch.object(config, "RENDER_SCALE", S)
        p.start()
        self.addCleanup(p.stop)
        self.surface = pygame.Surface(NATIVE)
        self.box = uibox.box(self.surface)


class HelperTests(_Scaled):
    def test_px_rect_and_box(self):
        self.assertEqual(scale.px(100), 160)
        self.assertEqual(scale.rect(10, 20, 30, 40), pygame.Rect(16, 32, 48, 64))
        self.assertEqual(scale.box_size(), (2560, 1440))
        self.assertEqual(uibox.rect(self.surface), pygame.Rect(440, 0, 2560, 1440))
        self.assertEqual(scale.int_scale(3), 5)

    def test_at_scale_one_the_helpers_are_the_identity(self):
        with mock.patch.object(config, "RENDER_SCALE", 1.0):
            self.assertEqual(scale.px(37), 37)
            self.assertEqual(scale.box_size(), (1600, 900))
            self.assertEqual(scale.int_scale(3), 3)

    def test_fonts_follow_the_scale_but_world_text_does_not(self):
        with mock.patch.object(config, "RENDER_SCALE", 1.0):
            one = fonts.body(20).get_height()
        big = fonts.body(20).get_height()
        self.assertAlmostEqual(big / one, S, delta=0.15)
        self.assertEqual(fonts.body(20, scaled=False).get_height(), one)


class ScreensAtScaleTests(_Scaled):
    def test_the_pause_buttons_are_scaled_and_centred_in_the_box(self):
        st = PausedState(self.game)
        st.enter()
        st.draw(self.box)
        rects = [st._mouse.hits.rect_of(i) for i in range(4)]
        for r in rects:
            self.assertEqual(r.width, scale.px(560))
            self.assertEqual(r.height, scale.px(64))
            self.assertEqual(r.centerx, self.box.get_width() // 2)
        self.assertEqual(rects[1].centery - rects[0].centery, scale.px(72))

    def test_the_options_rows_step_by_the_scaled_step(self):
        game = self.game
        game.state_machine.change(OptionsState(game))
        opt = game.state_machine.current
        opt.draw(self.box)                                    # must not raise
        self.assertEqual((scale.px(240), scale.px(74)), (384, 118))   # the first row and the step

    def test_the_hud_cluster_sits_at_the_scaled_offsets(self):
        from tests.screens.test_hud import _Player, STATS, GROUND
        s = pygame.Surface((2560, 1440))
        s.fill(GROUND)
        HUD().draw(s, _Player(), dict(STATS), xp_fraction=0.5)
        # The gem's top-left corner: 16 x 39 design px, scaled.
        gem = pygame.Rect(scale.px(16), scale.px(config.HUD_LEFT_TOP),
                          scale.px(config.HUD_GEM_PX), scale.px(config.HUD_GEM_PX))
        inked = [(x, y) for y in range(gem.top, gem.bottom, 4) for x in range(gem.left, gem.right, 4)
                 if s.get_at((x, y))[:3] != GROUND]
        self.assertGreater(len(inked), 50)
        outside = [(x, y) for y in range(0, gem.top, 4) for x in range(0, gem.left, 4)
                   if s.get_at((x, y))[:3] != GROUND]
        self.assertEqual(outside, [])

    def test_the_level_up_cards_are_scaled(self):
        from types import SimpleNamespace
        choices = [SimpleNamespace(title=f"Boon {i}", description="A short description of the boon.",
                                   tags=("sword",), rarity="common") for i in range(3)]
        panel = LevelUpPanel()
        panel.draw(self.box, choices, 0, dim=False)
        r = panel.hits.rect_of(0)
        self.assertEqual(r.width, scale.px(340))
        self.assertEqual(r.height, scale.px(295))

    def test_the_menu_rows_are_scaled_and_centred(self):
        st = MenuState(self.game)
        st.enter()
        st.draw(self.box)
        r = st._mouse.hits.rect_of(0)
        self.assertLessEqual(abs(r.centerx - self.box.get_width() // 2), 1)
        self.assertEqual(r.height, scale.px(64))
        self.assertGreater(r.width, 560)                      # 625 - 2 x inset, at 1.6x

    def test_every_other_screen_draws_inside_the_box_at_scale(self):
        game = self.game
        for cls in (CharacterSelectState, MetaState, RankingsState, GameOverState, VictoryState):
            st = cls(game)
            st.enter()
            st.draw(self.box)                                 # must not raise
        dev = DevMenuState(game)
        dev.enter()
        dev.draw(self.box)

    def test_end_screen_buttons_are_scaled(self):
        st = GameOverState(self.game)
        st.enter()
        st.draw(self.box)
        r = st._screen.mouse.hits.rect_of(0)
        self.assertEqual(r.width, scale.px(400))
        self.assertEqual(r.height, scale.px(64))
        self.assertEqual(r.centery, scale.px(812))


if __name__ == "__main__":
    unittest.main()
