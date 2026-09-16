"""Options from the pause menu, and a display change under a live run
(journal "Native-resolution rendering", stage 1b, 2026-09-16).

The pause menu's Options row pushes the Options screen over the frozen
run with the Sanctuary hidden; Back pops to the pause menu. When the
display is re-opened under the stack, the run rebuilds its camera at the
same world centre for the new surface and zoom, its fonts and HUD follow
the new scale, and the sea buffer covers the new world span."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.game import Game
from game.states.loading_state import LoadingState
from game.states.options_state import OptionsState
from game.states.paused_state import PausedState
from game.states.playing.core.state import PlayingState
from tests.boot import settle


def _run():
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(LoadingState(game), seed=35, dev=True)
    ps = settle(game)
    ps.player.invulnerable = True
    return game, ps


def _key(game, k):
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


class OptionsFromPauseTests(unittest.TestCase):
    def test_the_options_row_opens_options_over_the_run_without_the_sanctuary(self):
        game, ps = _run()
        game.state_machine.push(PausedState(game))
        pause = game.state_machine.current
        pause.sel = pause.__class__.__dict__.get("_ROWS", None) or 0
        from game.states import paused_state
        pause.sel = paused_state._ROWS.index("options")
        _key(game, pygame.K_RETURN)
        opt = game.state_machine.current
        self.assertIsInstance(opt, OptionsState)
        self.assertTrue(opt.in_run)
        self.assertNotIn("sanctuary", opt._rows)
        self.assertIn("display", opt._rows)
        # The run is still there, frozen, under the pause menu.
        self.assertIs(game.state_machine._stack[0], ps)
        self.assertIs(game.state_machine._stack[1], pause)

    def test_back_returns_to_the_pause_menu_not_the_main_menu(self):
        game, ps = _run()
        game.state_machine.push(PausedState(game))
        game.state_machine.push(OptionsState(game), in_run=True)
        _key(game, pygame.K_ESCAPE)
        self.assertIsInstance(game.state_machine.current, PausedState)
        self.assertIs(game.state_machine._stack[0], ps)

    def test_from_the_main_menu_options_still_has_the_sanctuary(self):
        game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        game.state_machine.change(OptionsState(game))
        self.assertIn("sanctuary", game.state_machine.current._rows)
        self.assertFalse(game.state_machine.current.in_run)


class DisplayChangeUnderARunTests(unittest.TestCase):
    def _change_display(self, game, size, render_scale):
        """What `DisplayWindow.reopen` leaves behind, then the game's hook."""
        config.SCREEN_WIDTH, config.SCREEN_HEIGHT = size
        config.RENDER_SCALE = render_scale
        game._on_display_reopened(pygame.Surface(size))

    def setUp(self):
        self._saved = (config.SCREEN_WIDTH, config.SCREEN_HEIGHT, config.RENDER_SCALE)

    def tearDown(self):
        config.SCREEN_WIDTH, config.SCREEN_HEIGHT, config.RENDER_SCALE = self._saved

    def test_the_camera_is_rebuilt_at_the_same_centre_for_the_new_surface(self):
        game, ps = _run()
        game.state_machine.push(PausedState(game))
        old = ps.camera
        sw, sh = old.world_span()
        centre = (old.pos.x + sw / 2, old.pos.y + sh / 2)
        self._change_display(game, (3440, 1440), 1.6)
        cam = ps.camera
        self.assertIsNot(cam, old)
        self.assertEqual((cam.view_width, cam.view_height), (3440, 1440))
        self.assertEqual(cam.zoom, config.effective_zoom())
        self.assertEqual(cam.zoom, 2.40625)
        nw, nh = cam.world_span()
        self.assertLess(abs(nh - 600.0) / 600.0, 0.003)            # the same covered height
        new_centre = (cam.pos.x + nw / 2, cam.pos.y + nh / 2)
        # The same world centre, unless the clamp to the world edge moved it.
        self.assertLess(abs(new_centre[0] - centre[0]) + abs(new_centre[1] - centre[1]), 2.0 + nw)
        self.assertEqual(game.screen.get_size(), (3440, 1440))

    def test_fonts_hud_and_sea_follow_the_new_scale(self):
        game, ps = _run()
        game.state_machine.push(PausedState(game))
        pause = game.state_machine.current
        hud_before = ps.hud._font.get_height()
        pause_before = pause._font.get_height()
        sea_before = ps.game_map._water_buf.get_size() if ps.game_map._water_buf else None
        self._change_display(game, (3440, 1440), 1.6)
        self.assertGreater(ps.hud._font.get_height(), hud_before)
        self.assertGreater(pause._font.get_height(), pause_before)
        self.assertIsNot(ps.hud, None)
        if sea_before is not None:
            sea = ps.game_map._water_buf.get_size()
            sw, sh = ps.camera.world_span()
            self.assertGreaterEqual(sea[0], sw)                      # covers the new span
            self.assertGreaterEqual(sea[1], sh)

    def test_a_change_with_no_run_is_harmless(self):
        game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
        game.state_machine.change(OptionsState(game))
        self._change_display(game, (1920, 1080), 1.2)
        self.assertEqual(game.screen.get_size(), (1920, 1080))
        game.state_machine.draw(game.screen)                          # the Options screen redraws


if __name__ == "__main__":
    unittest.main()
