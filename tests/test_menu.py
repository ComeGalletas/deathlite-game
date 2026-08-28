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
            "Rankings",
            "Options",
            "Exit",
        ])

    def test_down_moves_and_wraps(self):
        game, menu = _menu()
        for expected in (1, 2, 3, 4, 0):
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

    def test_rankings_entry_opens_rankings_state(self):
        from game.states.rankings_state import RankingsState
        game, menu = _menu()
        _key(game, pygame.K_DOWN)
        _key(game, pygame.K_DOWN)                       # -> Rankings
        self.assertEqual(menu._options[menu._index][0], "Rankings")
        _key(game, pygame.K_RETURN)
        self.assertIsInstance(game.state_machine.current, RankingsState)

    def test_options_entry_opens_options_state(self):
        game, menu = _menu()
        for _ in range(3):
            _key(game, pygame.K_DOWN)                   # -> Options
        self.assertEqual(menu._index, 3)
        _key(game, pygame.K_RETURN)
        self.assertIsInstance(game.state_machine.current, OptionsState)

    def test_exit_entry_quits(self):
        game, menu = _menu()
        for _ in range(4):
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
        self.assertIsNotNone(art, "assets/ui/title.png is missing")
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


class MenuHasNoInstructionsTests(unittest.TestCase):
    """The game instructions moved to the character-select screen (they now sit
    beside the hero preview); the start menu carries no trace of them."""

    def test_menu_state_has_no_instructions_members(self):
        _, menu = _menu()
        for attr in ("_instr_rows", "_instr_notes", "_instr_font",
                     "_instr_font_px", "_draw_instructions"):
            self.assertFalse(hasattr(menu, attr), attr)

    def test_menu_left_column_is_empty(self):
        import logging
        game, menu = _menu()
        original = config.MENU_TITLE_IMAGE
        config.MENU_TITLE_IMAGE = "no image 4242.png"      # pure black bg
        logging.disable(logging.CRITICAL)
        try:
            menu.draw(game.screen)
            left_box = pygame.Rect(56, 350, 300, 240)
            self.assertEqual(_bright_pixels(game.screen, left_box), 0,
                             "menu still draws something in the old instr column")
        finally:
            logging.disable(logging.NOTSET)
            config.MENU_TITLE_IMAGE = original


def _select():
    game, _menu_state = _menu()
    _key(game, pygame.K_RETURN)                     # -> character select
    cs = game.state_machine.current
    assert isinstance(cs, CharacterSelectState)
    return game, cs


class CharacterSelectInstructionsTests(unittest.TestCase):
    """The game instructions moved here from the start menu; they render from
    `config.MENU_INSTRUCTIONS` between the difficulty line and the nav hint."""

    def test_instruction_block_renders_below_the_difficulty_line(self):
        game, cs = _select()
        cs.draw(game.screen)
        cx = config.SCREEN_WIDTH // 2
        band = pygame.Rect(cx - 420, 690, 840, 70)   # where _draw_instructions lands
        self.assertGreater(_bright_pixels(game.screen, band), 60,
                           "no instruction text under the difficulty line")

    def test_content_comes_from_config(self):
        game, cs = _select()
        old = config.MENU_INSTRUCTIONS
        config.MENU_INSTRUCTIONS = {"rows": [("Jump", "SPACE")],
                                    "notes": ["one", "two"]}
        try:
            bottom = cs._draw_instructions(game.screen, config.SCREEN_WIDTH // 2, 700)
            # heading line + 2 notes -> bottom is two line-heights below `top`
            self.assertEqual(bottom, 700 + 2 * cs._instr.get_linesize())
        finally:
            config.MENU_INSTRUCTIONS = old


class CharacterSelectPreviewTests(unittest.TestCase):
    """A looping idle -> walk -> attack preview of the focused hero, rebuilt
    when the selection changes; primitive-disc fallback if the rig is absent."""

    def test_preview_animator_targets_the_focused_hero_rig(self):
        _game, cs = _select()
        self.assertIsNotNone(cs._preview)
        want = cs.content.characters[cs.ids[cs.index]]["sprite"]
        self.assertEqual(cs._preview.rig, want)

    def test_update_cycles_through_idle_walk_attack(self):
        _game, cs = _select()
        seen = set()
        for _ in range(2000):                       # a few whole cycles
            cs.update(1 / 60)
            seen.add(("idle", "walk", "attack")[cs._phase_i])
        self.assertEqual(seen, {"idle", "walk", "attack"})

    def test_changing_hero_rebuilds_the_preview_and_resets_the_phase(self):
        game, cs = _select()
        for _ in range(90):
            cs.update(1 / 60)                        # get off phase 0
        first_rig = cs._preview.rig
        _key(game, pygame.K_RIGHT)
        cs.update(1 / 60)
        self.assertNotEqual(cs._preview.rig, first_rig)
        self.assertEqual(cs._phase_i, 0)

    def test_draw_falls_back_to_a_disc_when_there_is_no_animator(self):
        game, cs = _select()
        cs._preview = None
        cs.draw(game.screen)
        cx = config.SCREEN_WIDTH // 2
        box = pygame.Rect(cx - 60, 500, 120, 160)   # the preview slot
        self.assertGreater(_bright_pixels(game.screen, box), 20,
                           "no fallback disc drawn for a rig-less hero")


class CharacterSelectDifficultyTests(unittest.TestCase):
    """Phase 4 D3: the run's difficulty is picked here (per run, not persisted).
    Up / Down cycles it; the choice is forwarded into PlayingState."""

    def _select(self):
        return _select()

    def test_defaults_to_normal(self):
        _, cs = self._select()
        self.assertEqual(cs.difficulty, config.DIFFICULTY_DEFAULT)

    def test_down_and_up_cycle_the_difficulty(self):
        game, cs = self._select()
        _key(game, pygame.K_DOWN)
        self.assertEqual(cs.difficulty, "fast")
        _key(game, pygame.K_DOWN)
        self.assertEqual(cs.difficulty, "super_fast")
        _key(game, pygame.K_DOWN)
        self.assertEqual(cs.difficulty, "normal")   # wraps
        _key(game, pygame.K_UP)
        self.assertEqual(cs.difficulty, "super_fast")

    def test_left_right_still_change_hero_not_difficulty(self):
        game, cs = self._select()
        before = cs.difficulty
        _key(game, pygame.K_RIGHT)
        self.assertEqual(cs.index, 1)
        self.assertEqual(cs.difficulty, before)

    def test_choice_reaches_the_playing_state(self):
        from game.states.playing_state import PlayingState
        game, cs = self._select()
        _key(game, pygame.K_DOWN)                   # -> fast
        _key(game, pygame.K_RETURN)                 # begin
        run = game.state_machine.current
        self.assertIsInstance(run, PlayingState)
        self.assertEqual(run.difficulty, "fast")
        self.assertEqual(run.director.difficulty, "fast")

    def test_draw_runs_headless_for_every_difficulty(self):
        game, cs = self._select()
        for _ in config.DIFFICULTY_ORDER:
            cs.draw(game.screen)                    # must not raise
            _key(game, pygame.K_DOWN)


if __name__ == "__main__":
    unittest.main()
