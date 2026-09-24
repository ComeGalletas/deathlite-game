"""Start-screen milestone M1: the title screen is a navigable option list.
The hero select it leads to is `test_character_select.py`.

ENTER on the default selection still starts a run (the smoke / integration tests
rely on two RETURNs walking menu -> character select -> playing), the cursor
wraps, Exit and ESC quit, "Options" / developer mode are inert for now, and the
old S -> Sanctuary shortcut is gone.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.states.character_select_state import CharacterSelectState
from game.states.menu_state import MenuState
from game.states.meta_state import MetaState
from game.states.options_state import OptionsState
from tests.screens.drive import (bright_pixels as _bright_pixels, key as _key,
                                 menu as _menu, mouse as _mouse)


class MenuMouseTests(unittest.TestCase):
    """Mouse support, group A: hover selects a row, a click activates it.
    The rows are registered while drawing, so every test draws first."""

    def _menu_drawn(self):
        game, menu = _menu()
        menu.draw(game.screen)
        return game, menu

    def _row_centre(self, menu, i):
        return menu._mouse.hits.rect_of(i).center

    def test_draw_registers_one_band_per_option_without_overlap(self):
        _, menu = self._menu_drawn()
        rects = [menu._mouse.hits.rect_of(i) for i in range(len(menu._options))]
        self.assertTrue(all(r is not None for r in rects))
        for a, b in zip(rects, rects[1:]):
            self.assertLessEqual(a.bottom, b.top)

    def test_hover_moves_the_selection(self):
        game, menu = self._menu_drawn()
        _mouse(game, pygame.MOUSEMOTION, self._row_centre(menu, 3))
        self.assertEqual(menu._index, 3)
        _mouse(game, pygame.MOUSEMOTION, self._row_centre(menu, 1))
        self.assertEqual(menu._index, 1)

    def test_hover_between_rows_changes_nothing(self):
        game, menu = self._menu_drawn()
        _mouse(game, pygame.MOUSEMOTION, (10, 10))
        self.assertEqual(menu._index, 0)

    def test_click_on_options_row_opens_options(self):
        game, menu = self._menu_drawn()
        pos = self._row_centre(menu, 3)
        _mouse(game, pygame.MOUSEBUTTONDOWN, pos)
        self.assertIsInstance(game.state_machine.current, MenuState)   # not yet
        _mouse(game, pygame.MOUSEBUTTONUP, pos)
        self.assertIsInstance(game.state_machine.current, OptionsState)

    def test_click_without_a_prior_hover_still_selects_and_activates(self):
        game, menu = self._menu_drawn()
        pos = self._row_centre(menu, 2)
        _mouse(game, pygame.MOUSEBUTTONDOWN, pos)
        _mouse(game, pygame.MOUSEBUTTONUP, pos)
        from game.states.rankings_state import RankingsState
        self.assertIsInstance(game.state_machine.current, RankingsState)

    def test_release_on_another_row_does_nothing(self):
        game, menu = self._menu_drawn()
        _mouse(game, pygame.MOUSEBUTTONDOWN, self._row_centre(menu, 4))   # Exit
        _mouse(game, pygame.MOUSEBUTTONUP, self._row_centre(menu, 3))
        self.assertTrue(game.running)
        self.assertIsInstance(game.state_machine.current, MenuState)

    def test_click_off_every_row_does_nothing(self):
        game, menu = self._menu_drawn()
        _mouse(game, pygame.MOUSEBUTTONDOWN, (20, 20))
        _mouse(game, pygame.MOUSEBUTTONUP, (20, 20))
        self.assertIsInstance(game.state_machine.current, MenuState)
        self.assertEqual(menu._index, 0)

    def test_keyboard_and_mouse_share_the_index(self):
        game, menu = self._menu_drawn()
        _mouse(game, pygame.MOUSEMOTION, self._row_centre(menu, 2))
        _key(game, pygame.K_DOWN)
        self.assertEqual(menu._index, 3)


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
        self.assertEqual(config.MENU_FG, (170, 170, 170))

    def test_title_art_loads_at_screen_size(self):
        game, _ = _menu()
        art = game.assets.picture(
            config.MENU_TITLE_IMAGE,
            size=(config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        self.assertIsNotNone(art, "assets/ui/start_screen/title.png is missing")
        self.assertEqual(art.get_size(), (config.SCREEN_WIDTH, config.SCREEN_HEIGHT))

    def test_missing_background_images_fall_back_to_black(self):
        import logging
        game, menu = _menu()
        orig_bg, orig_title = config.MENU_BACKGROUND_IMAGE, config.MENU_TITLE_IMAGE
        config.MENU_BACKGROUND_IMAGE = "definitely missing bg 98765.png"
        config.MENU_TITLE_IMAGE = "definitely missing 98765.png"
        logging.disable(logging.CRITICAL)
        try:
            menu.draw(game.screen)                      # must not raise
            self.assertEqual(tuple(game.screen.get_at((2, 2)))[:3], config.MENU_BG)
        finally:
            logging.disable(logging.NOTSET)
            config.MENU_BACKGROUND_IMAGE, config.MENU_TITLE_IMAGE = orig_bg, orig_title

    def test_missing_logo_image_falls_back_to_text(self):
        import logging
        game, menu = _menu()
        original = config.MENU_LOGO_IMAGE
        config.MENU_LOGO_IMAGE = "definitely missing logo 98765.png"
        logging.disable(logging.CRITICAL)
        try:
            menu.draw(game.screen)                      # must not raise
            logo_box = pygame.Rect(0, 0, config.SCREEN_WIDTH, 890 - 495 - 20)
            self.assertGreater(_bright_pixels(game.screen, logo_box), 0,
                              "no fallback text drawn when the logo art is missing")
        finally:
            logging.disable(logging.NOTSET)
            config.MENU_LOGO_IMAGE = original


class MenuHasNoScrollPanelTests(unittest.TestCase):
    """2026-09-11: the parchment "scroll" panel behind the option list is gone
    -- rows draw straight over the ocean backdrop and no banner rig is left."""

    def test_draw_requests_no_banner_rig(self):
        from unittest import mock
        game, menu = _menu()
        asked = []
        for name in ("image", "picture"):
            real = getattr(game.assets, name)
            def spy(rig, *a, _real=real, **kw):
                asked.append(rig)
                return _real(rig, *a, **kw)
            setattr(game.assets, name, spy)
        menu.draw(game.screen)
        self.assertFalse([r for r in asked if "banner" in str(r) or "scroll" in str(r)],
                         f"menu still reaches for the scroll art: {asked}")

    def test_no_scroll_panel_rigs_are_declared(self):
        """The three `ui_banner_*` rigs over `assets/ui/banners/scroll_*.png`
        went with the panel. Named, not matched on "banner": the end-of-run
        banners (`end_banner_win`/`end_banner_loss`) are unrelated art that
        the menu never touches, and a substring ban catches them too."""
        _, _ = _menu()
        from game.assets import Assets
        meta = Assets().meta
        self.assertFalse([k for k in meta if k.startswith("ui_banner")])
        self.assertFalse([k for k, r in meta.items()
                          if str(r.get("file", "")).startswith("ui/banners/")])

    def test_panels_module_has_no_three_slice_builder(self):
        from ui import panels
        self.assertFalse(hasattr(panels, "three_slice_h"))
        self.assertFalse(hasattr(panels, "_native_size"))

    def test_config_has_no_menu_scrim(self):
        self.assertFalse(hasattr(config, "MENU_SCRIM"))


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
        orig_title, orig_bg = config.MENU_TITLE_IMAGE, config.MENU_BACKGROUND_IMAGE
        config.MENU_TITLE_IMAGE = "no image 4242.png"      # pure black bg
        config.MENU_BACKGROUND_IMAGE = "no image 4243.png"
        logging.disable(logging.CRITICAL)
        try:
            menu.draw(game.screen)
            left_box = pygame.Rect(56, 350, 300, 240)
            self.assertEqual(_bright_pixels(game.screen, left_box), 0,
                             "menu still draws something in the old instr column")
        finally:
            logging.disable(logging.NOTSET)
            config.MENU_TITLE_IMAGE, config.MENU_BACKGROUND_IMAGE = orig_title, orig_bg


class MenuButtonArtTests(unittest.TestCase):
    """UI art, group F: the start-menu rows are wide buttons -- the selected
    row gold, a held row sunk, Exit red."""

    def _menu_drawn(self):
        game, menu = _menu()
        menu.draw(game.screen)
        return game, menu

    def _calls(self, game, menu):
        from unittest import mock
        from ui import widgets
        with mock.patch.object(widgets, "draw_button", wraps=widgets.draw_button) as m:
            menu.draw(game.screen)
        calls = [c for c in m.call_args_list if c.kwargs.get("shape") == "wide"]
        self.assertEqual(len(calls), len(menu._options))
        return calls

    def test_one_native_button_per_row_inside_the_panel(self):
        game, menu = self._menu_drawn()
        calls = self._calls(game, menu)
        rects = [c.args[2] for c in calls]
        for i, r in enumerate(rects):
            self.assertEqual(r.height, 64)
            self.assertEqual(menu._mouse.hits.rect_of(i), r)       # hit rect == art rect
        for a, b in zip(rects, rects[1:]):
            self.assertLess(a.bottom, b.top)                       # a gap between rows
        self.assertLess(rects[-1].bottom, 890)                     # inside the panel
        self.assertEqual([c.args[3] for c in calls], [l for l, _ in menu._options])

    def test_rows_are_tight_and_clear_the_save_summary(self):
        """2026-09-11: rows on a 68-px step (a 4-px gap, was 8) and 25 px
        higher, so the salvage / best-run line at the screen foot stays
        readable."""
        game, menu = self._menu_drawn()
        rects = [c.args[2] for c in self._calls(game, menu)]
        self.assertEqual(rects[0].centery, 525)
        for a, b in zip(rects, rects[1:]):
            self.assertEqual(b.top - a.bottom, 4)
        self.assertLess(rects[-1].bottom, config.SCREEN_HEIGHT - 60)   # summary sits at h - 40

    def test_selected_row_is_gold_and_follows_the_keyboard(self):
        game, menu = self._menu_drawn()
        self.assertEqual([c.kwargs["state"] for c in self._calls(game, menu)],
                         ["hover", "normal", "normal", "normal", "normal"])
        _key(game, pygame.K_DOWN)
        _key(game, pygame.K_DOWN)
        self.assertEqual([c.kwargs["state"] for c in self._calls(game, menu)][2], "hover")

    def test_held_row_sinks_and_exit_is_red(self):
        game, menu = self._menu_drawn()
        _mouse(game, pygame.MOUSEBUTTONDOWN, menu._mouse.hits.rect_of(3).center)
        calls = self._calls(game, menu)
        self.assertEqual(calls[3].kwargs["state"], "pressed")
        self.assertEqual(calls[4].kwargs["variant"], "danger")
        self.assertTrue(all(c.kwargs["variant"] == "primary" for c in calls[:4]))
        _mouse(game, pygame.MOUSEBUTTONUP, (5, 5))
        self.assertNotIn("pressed", [c.kwargs["state"] for c in self._calls(game, menu)])

    def test_labels_are_black_and_lifted(self):
        from unittest import mock
        from ui import widgets
        game, menu = self._menu_drawn()
        seen = []
        real = widgets.draw_button

        def spy(*a, **k):
            r = real(*a, **k)
            seen.append((a[2], k, r))
            return r

        with mock.patch.object(widgets, "draw_button", side_effect=spy):
            menu.draw(game.screen)
        self.assertEqual(len(seen), len(menu._options))
        for rect, kwargs, label_rect in seen:
            self.assertNotIn("text_colour", kwargs)              # the black default
            self.assertEqual(label_rect.centery, rect.centery + widgets.LABEL_DY)
        row = menu._mouse.hits.rect_of(0)                           # selected -> gold
        black = tuple(config.COLOR_ON_BUTTON) + (255,)
        self.assertTrue(any(tuple(game.screen.get_at((x, y))) == black
                            for x in range(row.left + 64, row.right - 64)
                            for y in range(row.top + 8, row.bottom - 12)),
                        "no black glyph pixel on the selected row")

    def test_art_lands_on_screen(self):
        game, menu = self._menu_drawn()
        rect = menu._mouse.hits.rect_of(1)                          # not selected -> blue
        sheet = game.assets.image("btn_blue_wide")
        self.assertEqual(game.screen.get_at((rect.left + 20, rect.top + 30)),
                         sheet.get_at((20, 30)))
