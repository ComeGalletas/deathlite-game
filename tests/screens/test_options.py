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
        for _ in range(3):
            _key(game, pygame.K_DOWN)                   # -> Options
        _key(game, pygame.K_RETURN)
        self.assertIsInstance(game.state_machine.current, OptionsState)


class _FakeDisplay:
    """A scaled window that opened (the dummy driver never gives one)."""

    def __init__(self):
        self.available = True
        self.mode = "windowed"
        self.windowed_size = (1600, 900)
        self.entries = [(1280, 720), (1600, 900), (1920, 1080)]
        self.dirty = False

    def resolution_selectable(self):
        return self.available and self.mode == "windowed"

    def set_mode(self, mode):
        if mode == self.mode:
            return False
        self.mode = mode
        return True

    def cycle_resolution(self, direction):
        if not self.resolution_selectable():
            return False
        i = (self.entries.index(self.windowed_size) + direction) % len(self.entries)
        self.windowed_size = self.entries[i]
        return True

    def mode_label(self):
        return {"windowed": "Windowed", "borderless": "Borderless"}[self.mode]

    def resolution_label(self):
        if self.mode == "borderless":
            return "1920x1080"
        return "%dx%d" % self.windowed_size

    def settings(self):
        return {"mode": self.mode, "window": list(self.windowed_size)}


class WindowRowTests(unittest.TestCase):
    """The Display mode and Resolution rows (journal "Dynamic window
    scaling", 2026-09-15): the only place the window changes."""

    def test_without_a_scaled_window_both_rows_are_skipped(self):
        game, opt = _options()
        self.assertFalse(game.display.available)
        opt.sel = opt._rows.index("key_layout")
        _key(game, pygame.K_DOWN)
        self.assertEqual(opt._row_id(), "sanctuary")
        _key(game, pygame.K_UP)
        self.assertEqual(opt._row_id(), "key_layout")
        opt.draw(pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT)))   # draws "Unavailable"

    def test_display_mode_row_switches_and_persists(self):
        game, opt = _options()
        game.display = _FakeDisplay()
        opt.sel = opt._rows.index("display")
        _key(game, pygame.K_RIGHT)
        self.assertEqual(game.display.mode, "borderless")
        self.assertEqual(save_mod.load(game.save_path).settings["display"]["mode"], "borderless")
        _key(game, pygame.K_RETURN)
        self.assertEqual(game.display.mode, "windowed")

    def test_resolution_row_steps_and_persists_in_windowed(self):
        game, opt = _options()
        game.display = _FakeDisplay()
        opt.sel = opt._rows.index("resolution")
        _key(game, pygame.K_RIGHT)
        self.assertEqual(game.display.windowed_size, (1920, 1080))
        self.assertEqual(save_mod.load(game.save_path).settings["display"]["window"],
                         [1920, 1080])
        _key(game, pygame.K_LEFT)
        self.assertEqual(game.display.windowed_size, (1600, 900))

    def test_in_borderless_the_resolution_row_is_skipped_and_reads_the_desktop(self):
        game, opt = _options()
        game.display = _FakeDisplay()
        game.display.mode = "borderless"
        opt.sel = opt._rows.index("display")
        _key(game, pygame.K_DOWN)
        self.assertEqual(opt._row_id(), "sanctuary")
        _key(game, pygame.K_UP)
        self.assertEqual(opt._row_id(), "display")
        self.assertEqual(game.display.resolution_label(), "1920x1080")
        opt.draw(pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT)))   # dim row

    def test_the_save_carries_the_display_block_alongside_the_others(self):
        game, opt = _options()
        game.display = _FakeDisplay()
        opt.sel = opt._rows.index("mute")
        _key(game, pygame.K_RETURN)
        loaded = save_mod.load(game.save_path).settings
        self.assertEqual(loaded["display"], {"mode": "windowed", "window": [1600, 900]})


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


class KeyLayoutRowTests(unittest.TestCase):
    """CB-5: the key-layout row cycles the layouts and persists at once."""

    def test_enter_cycles_and_persists(self):
        game, opt = _options()
        opt.sel = opt._rows.index("key_layout")
        self.assertEqual(game.key_layout, config.DEFAULT_KEY_LAYOUT)
        _key(game, pygame.K_RETURN)
        self.assertEqual(game.key_layout, "arrows_move")
        self.assertEqual(save_mod.load(game.save_path).settings["key_layout"],
                         "arrows_move")
        _key(game, pygame.K_RETURN)
        self.assertEqual(game.key_layout, config.DEFAULT_KEY_LAYOUT)

    def test_left_right_cycle_on_the_row_only(self):
        game, opt = _options()
        opt.sel = opt._rows.index("key_layout")
        _key(game, pygame.K_RIGHT)
        self.assertEqual(game.key_layout, "arrows_move")
        _key(game, pygame.K_LEFT)
        self.assertEqual(game.key_layout, config.DEFAULT_KEY_LAYOUT)
        opt.sel = opt._rows.index("mute")
        _key(game, pygame.K_RIGHT)
        self.assertEqual(game.key_layout, config.DEFAULT_KEY_LAYOUT)

    def test_layout_survives_reload_into_a_fresh_game(self):
        game, opt = _options()
        opt.sel = opt._rows.index("key_layout")
        _key(game, pygame.K_RETURN)
        self.assertEqual(Game(save_path=game.save_path).key_layout, "arrows_move")

    def test_row_draws_the_layout_label(self):
        game, opt = _options()
        opt.draw(game.screen)            # must not raise; the label is looked up
        self.assertIn(game.key_layout, config.KEY_LAYOUT_LABELS)
