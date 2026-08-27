"""Start-screen milestone M1: the title screen is a navigable option list.

ENTER on the default selection still starts a run (the smoke / integration tests
rely on two RETURNs walking menu -> character select -> playing), the cursor
wraps, Exit and ESC quit, "Options" / developer mode are inert for now, and the
old S -> Sanctuary shortcut is gone.
"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.game import Game
from game.states.character_select_state import CharacterSelectState
from game.states.menu_state import MenuState
from game.states.meta_state import MetaState
from game.states.options_state import OptionsState


def _menu():
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    game.running = True
    return game, game.state_machine.current


def _key(game, k):
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


class MenuNavigationTests(unittest.TestCase):
    def test_default_selection_is_start_new_game(self):
        _, menu = _menu()
        self.assertEqual(menu._index, 0)
        self.assertEqual(menu._options[0][0], "Start new game")

    def test_option_order(self):
        _, menu = _menu()
        self.assertEqual([label for label, _ in menu._options], [
            "Start new game",
            "Start new developer mode game",
            "Options",
            "Exit",
        ])

    def test_down_moves_and_wraps(self):
        game, menu = _menu()
        for expected in (1, 2, 3, 0):
            _key(game, pygame.K_DOWN)
            self.assertEqual(menu._index, expected)

    def test_up_from_top_wraps_to_last(self):
        game, menu = _menu()
        _key(game, pygame.K_UP)
        self.assertEqual(menu._index, len(menu._options) - 1)

    def test_w_and_s_also_navigate(self):
        game, menu = _menu()
        _key(game, pygame.K_s)
        self.assertEqual(menu._index, 1)
        _key(game, pygame.K_w)
        self.assertEqual(menu._index, 0)

    def test_enter_on_default_starts_character_select(self):
        game, _ = _menu()
        _key(game, pygame.K_RETURN)
        self.assertIsInstance(game.state_machine.current, CharacterSelectState)

    def test_space_also_activates(self):
        game, _ = _menu()
        _key(game, pygame.K_SPACE)
        self.assertIsInstance(game.state_machine.current, CharacterSelectState)

    def test_developer_mode_entry_starts_a_dev_character_select(self):
        game, menu = _menu()
        _key(game, pygame.K_DOWN)                       # -> developer mode
        self.assertEqual(menu._index, 1)
        _key(game, pygame.K_RETURN)
        cur = game.state_machine.current
        self.assertIsInstance(cur, CharacterSelectState)
        self.assertTrue(cur._dev)

    def test_start_new_game_is_not_a_dev_run(self):
        game, _ = _menu()
        _key(game, pygame.K_RETURN)                     # -> Start new game
        self.assertFalse(game.state_machine.current._dev)

    def test_options_entry_opens_options_state(self):
        game, menu = _menu()
        _key(game, pygame.K_DOWN)
        _key(game, pygame.K_DOWN)                       # -> Options
        self.assertEqual(menu._index, 2)
        _key(game, pygame.K_RETURN)
        self.assertIsInstance(game.state_machine.current, OptionsState)

    def test_exit_entry_quits(self):
        game, menu = _menu()
        for _ in range(3):
            _key(game, pygame.K_DOWN)                   # -> Exit
        self.assertEqual(menu._options[menu._index][0], "Exit")
        _key(game, pygame.K_RETURN)
        self.assertFalse(game.running)

    def test_escape_quits(self):
        game, _ = _menu()
        _key(game, pygame.K_ESCAPE)
        self.assertFalse(game.running)

    def test_s_key_no_longer_opens_the_sanctuary(self):
        game, _ = _menu()
        _key(game, pygame.K_s)
        self.assertIsInstance(game.state_machine.current, MenuState)
        self.assertNotIsInstance(game.state_machine.current, MetaState)

    def test_draw_runs_headless_for_every_selection(self):
        game, menu = _menu()
        for i in range(len(menu._options)):
            menu._index = i
            menu.draw(game.screen)                      # must not raise


class MenuPaletteAndTitleTests(unittest.TestCase):
    """M3: black / white palette + an optional full-screen title image over a
    text fallback."""

    def test_palette_constants(self):
        self.assertEqual(config.MENU_BG, (0, 0, 0))
        self.assertEqual(config.MENU_FG, (255, 255, 255))

    def test_title_art_loads_at_screen_size(self):
        game, _ = _menu()
        art = game.assets.picture(
            config.MENU_TITLE_IMAGE,
            size=(config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        self.assertIsNotNone(art, "assets/title screen.png is missing")
        self.assertEqual(art.get_size(), (config.SCREEN_WIDTH, config.SCREEN_HEIGHT))

    def test_missing_title_image_falls_back_to_black_plus_text(self):
        import logging
        game, menu = _menu()
        original = config.MENU_TITLE_IMAGE
        config.MENU_TITLE_IMAGE = "definitely missing 98765.png"
        logging.disable(logging.CRITICAL)
        try:
            self.assertIsNone(game.assets.picture(config.MENU_TITLE_IMAGE))
            menu.draw(game.screen)                      # must not raise
            self.assertEqual(tuple(game.screen.get_at((2, 2)))[:3], config.MENU_BG)
        finally:
            logging.disable(logging.NOTSET)
            config.MENU_TITLE_IMAGE = original


def _bright_pixels(surface, rect):
    """Count non-background (text) pixels in `rect`, sampling every 3px."""
    n = 0
    for x in range(rect.left, rect.right, 3):
        for y in range(rect.top, rect.bottom, 3):
            r, g, b = surface.get_at((x, y))[:3]
            if r + g + b > 240:
                n += 1
    return n


class MenuInstructionsLayoutTests(unittest.TestCase):
    """M4: the game instructions are their own left-hand section at ~85% of the
    option font."""

    def test_instruction_font_is_15pct_smaller_than_the_option_font(self):
        _, menu = _menu()
        self.assertEqual(menu._instr_font_px, round(menu._menu_font_px * 0.85))
        self.assertLess(menu._instr_font_px, menu._menu_font_px)

    def test_instruction_text_renders_left_of_centre(self):
        import logging
        game, menu = _menu()
        cx = config.SCREEN_WIDTH // 2
        original = config.MENU_TITLE_IMAGE
        config.MENU_TITLE_IMAGE = "no image 4242.png"      # pure black bg
        logging.disable(logging.CRITICAL)
        try:
            menu.draw(game.screen)
            left_box = pygame.Rect(56, 350, 300, 240)      # entirely left of centre
            self.assertLess(left_box.right, cx)
            self.assertGreater(_bright_pixels(game.screen, left_box), 40,
                               "no instruction text in the left column")
        finally:
            logging.disable(logging.NOTSET)
            config.MENU_TITLE_IMAGE = original


if __name__ == "__main__":
    unittest.main()
