"""Start-screen milestone M2: the Options screen -- master volume, mute toggle,
and the Sanctuary entry point. Reached from the menu's "Options" entry; every
change is persisted immediately.
"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config, save as save_mod
from game.game import Game
from game.states.menu_state import MenuState
from game.states.meta_state import MetaState
from game.states.options_state import OptionsState


def _game():
    return Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))


def _options():
    game = _game()
    game.state_machine.change(OptionsState(game))
    game.running = True
    return game, game.state_machine.current


def _key(game, k):
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


class MenuWiringTests(unittest.TestCase):
    def test_menu_options_entry_opens_options_state(self):
        game = _game()
        game.state_machine.change(MenuState(game))
        _key(game, pygame.K_DOWN)
        _key(game, pygame.K_DOWN)                       # -> Options
        _key(game, pygame.K_RETURN)
        self.assertIsInstance(game.state_machine.current, OptionsState)


class VolumeTests(unittest.TestCase):
    def test_right_raises_volume_by_one_step_and_persists(self):
        game, _ = _options()
        start = game.audio.volume
        _key(game, pygame.K_RIGHT)                      # row 0 is volume
        self.assertAlmostEqual(game.audio.volume, start + config.VOLUME_STEP, places=6)
        self.assertAlmostEqual(save_mod.load(game.save_path).settings["volume"],
                               game.audio.volume, places=6)

    def test_left_lowers_volume_by_one_step(self):
        game, _ = _options()
        start = game.audio.volume
        _key(game, pygame.K_LEFT)
        self.assertAlmostEqual(game.audio.volume, start - config.VOLUME_STEP, places=6)

    def test_volume_clamps_to_unit_range(self):
        game, _ = _options()
        for _ in range(40):
            _key(game, pygame.K_RIGHT)
        self.assertEqual(game.audio.volume, 1.0)
        for _ in range(60):
            _key(game, pygame.K_LEFT)
        self.assertEqual(game.audio.volume, 0.0)

    def test_left_right_do_nothing_off_the_volume_row(self):
        game, opt = _options()
        opt.sel = opt._rows.index("mute")
        before = game.audio.volume
        _key(game, pygame.K_RIGHT)
        _key(game, pygame.K_LEFT)
        self.assertEqual(game.audio.volume, before)

    def test_volume_survives_reload_into_a_fresh_game(self):
        game, _ = _options()
        _key(game, pygame.K_RIGHT)
        _key(game, pygame.K_RIGHT)
        v = game.audio.volume
        self.assertAlmostEqual(Game(save_path=game.save_path).audio.volume, v, places=6)


class MuteTests(unittest.TestCase):
    def test_enter_on_mute_row_toggles_and_persists(self):
        game, opt = _options()
        opt.sel = opt._rows.index("mute")
        before = game.audio.muted
        _key(game, pygame.K_RETURN)
        self.assertNotEqual(game.audio.muted, before)
        self.assertEqual(save_mod.load(game.save_path).settings["muted"], game.audio.muted)


class NavigationTests(unittest.TestCase):
    def test_up_down_wrap(self):
        game, opt = _options()
        n = len(opt._rows)
        _key(game, pygame.K_UP)
        self.assertEqual(opt.sel, n - 1)
        _key(game, pygame.K_DOWN)
        self.assertEqual(opt.sel, 0)

    def test_sanctuary_row_opens_the_sanctuary(self):
        game, opt = _options()
        opt.sel = opt._rows.index("sanctuary")
        _key(game, pygame.K_RETURN)
        self.assertIsInstance(game.state_machine.current, MetaState)

    def test_back_row_returns_to_menu(self):
        game, opt = _options()
        opt.sel = opt._rows.index("back")
        _key(game, pygame.K_RETURN)
        self.assertIsInstance(game.state_machine.current, MenuState)

    def test_escape_returns_to_menu(self):
        game, _ = _options()
        _key(game, pygame.K_ESCAPE)
        self.assertIsInstance(game.state_machine.current, MenuState)

    def test_draw_runs_headless_for_every_row(self):
        game, opt = _options()
        for i in range(len(opt._rows)):
            opt.sel = i
            opt.draw(game.screen)


if __name__ == "__main__":
    unittest.main()
