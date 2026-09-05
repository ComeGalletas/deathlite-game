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


def _mouse(game, event_type, pos, button=1):
    kw = {"pos": pos}
    if event_type == pygame.MOUSEMOTION:
        kw.update(rel=(0, 0), buttons=(0, 0, 0))
    else:
        kw["button"] = button
    game.state_machine.handle_event(pygame.event.Event(event_type, **kw))


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


def _select():
    game, _menu_state = _menu()
    _key(game, pygame.K_RETURN)                     # -> character select
    cs = game.state_machine.current
    assert isinstance(cs, CharacterSelectState)
    return game, cs


class CharacterSelectInstructionsTests(unittest.TestCase):
    """The game instructions moved here from the start menu; they render from
    `config.MENU_INSTRUCTIONS` between the difficulty line and the nav hint."""

    def test_instruction_block_renders_below_the_begin_button(self):
        game, cs = _select()
        cs.draw(game.screen)
        cx = config.SCREEN_WIDTH // 2
        lay = cs._layout
        # Order down the screen: difficulty line, Begin button, instructions.
        self.assertGreater(lay["begin"].top, lay["diff_y"])
        self.assertGreater(lay["instr_top"], lay["begin"].bottom)
        band = pygame.Rect(cx - 420, lay["instr_top"] - 12, 840,
                           lay["instr_bottom"] - lay["instr_top"] + 24)
        self.assertGreater(_bright_pixels(game.screen, band), 60,
                           "no instruction text under the Begin button")
        self.assertLessEqual(lay["hint_bottom"], config.SCREEN_HEIGHT)   # the hint stays on screen   # hint still fits

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
        _key(game, pygame.K_RETURN)                 # begin -> loading -> run
        from tests.boot import settle
        run = settle(game)
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


class CharacterSelectMouseTests(unittest.TestCase):
    """Mouse support, group B: hover selects a card, first click arms it,
    second click begins; the Begin button starts in one click; Back is
    ESC's twin; the difficulty line takes no mouse."""

    def _cs(self):
        game, cs = _select()
        cs.draw(game.screen)
        return game, cs

    def _card(self, cs, i):
        return cs._mouse.hits.rect_of(("hero", i)).center

    def _click(self, game, pos):
        _mouse(game, pygame.MOUSEBUTTONDOWN, pos)
        _mouse(game, pygame.MOUSEBUTTONUP, pos)

    def test_hover_selects_a_card_without_arming(self):
        game, cs = self._cs()
        _mouse(game, pygame.MOUSEMOTION, self._card(cs, 2))
        self.assertEqual(cs.index, 2)
        self.assertIsNone(cs._armed_hero)

    def test_first_click_arms_second_click_begins(self):
        from game.states.loading_state import LoadingState
        game, cs = self._cs()
        self._click(game, self._card(cs, 1))
        self.assertEqual(cs.index, 1)
        self.assertEqual(cs._armed_hero, 1)
        self.assertIsInstance(game.state_machine.current, CharacterSelectState)
        self._click(game, self._card(cs, 1))
        self.assertIsInstance(game.state_machine.current, LoadingState)

    def test_moving_to_another_card_disarms(self):
        game, cs = self._cs()
        self._click(game, self._card(cs, 1))
        _mouse(game, pygame.MOUSEMOTION, self._card(cs, 2))          # hover away
        self.assertIsNone(cs._armed_hero)
        self._click(game, self._card(cs, 1))                          # arms again, no start
        self.assertIsInstance(game.state_machine.current, CharacterSelectState)
        _key(game, pygame.K_RIGHT)                                    # keyboard disarms too
        self.assertIsNone(cs._armed_hero)
        self._click(game, self._card(cs, 2))
        self.assertIsInstance(game.state_machine.current, CharacterSelectState)

    def test_begin_button_starts_with_the_selected_hero_and_difficulty(self):
        from tests.boot import settle
        from game.states.playing_state import PlayingState
        game, cs = self._cs()
        _key(game, pygame.K_RIGHT)                                    # hero 1
        _key(game, pygame.K_DOWN)                                     # next difficulty
        want_hero, want_diff = cs.ids[1], cs.difficulty
        self._click(game, cs._mouse.hits.rect_of("begin").center)
        ps = settle(game)
        self.assertIsInstance(ps, PlayingState)
        self.assertEqual(ps.character_id, want_hero)
        self.assertEqual(ps.difficulty, want_diff)

    def test_begin_button_forwards_the_dev_flag(self):
        from game.states.loading_state import LoadingState
        game, menu = _menu()
        _key(game, pygame.K_DOWN)                                     # developer entry
        _key(game, pygame.K_RETURN)
        cs = game.state_machine.current
        self.assertTrue(cs._dev)
        cs.draw(game.screen)
        self._click(game, cs._mouse.hits.rect_of("begin").center)
        self.assertIsInstance(game.state_machine.current, LoadingState)

    def test_back_target_returns_to_the_menu(self):
        game, cs = self._cs()
        self._click(game, cs._mouse.hits.rect_of("back").center)
        self.assertIsInstance(game.state_machine.current, MenuState)

    def test_difficulty_ribbon_is_a_switch(self):
        game, cs = self._cs()
        pos = cs._layout["ribbon"].center
        self.assertEqual(cs.difficulty, config.DIFFICULTY_ORDER[0])
        _mouse(game, pygame.MOUSEMOTION, pos)                         # hover alone: nothing
        self.assertEqual(cs.difficulty, config.DIFFICULTY_ORDER[0])
        for want in config.DIFFICULTY_ORDER[1:] + config.DIFFICULTY_ORDER[:1]:
            self._click(game, pos)                                    # ...wraps to Normal
            self.assertEqual(cs.difficulty, want)
        self.assertIsInstance(game.state_machine.current, CharacterSelectState)

    def test_begin_sits_below_difficulty_and_above_instructions(self):
        _, cs = self._cs()
        begin = cs._mouse.hits.rect_of("begin")
        self.assertGreater(begin.top, cs._layout["diff_y"])
        self.assertLess(begin.bottom, cs._layout["instr_top"])

    def test_click_off_everything_does_nothing(self):
        game, cs = self._cs()
        self._click(game, (config.SCREEN_WIDTH // 2, 120))            # the title
        self.assertIsInstance(game.state_machine.current, CharacterSelectState)
        self.assertEqual(cs.index, 0)
        self.assertIsNone(cs._armed_hero)


class BeginButtonArtTests(unittest.TestCase):
    """UI art, group B: the Begin button is drawn from the wide button sheets
    at the native 64 px, gold under the cursor, pressed while held."""

    def _cs(self):
        game, cs = _select()
        cs.draw(game.screen)
        return game, cs

    def _state(self, game, cs):
        from unittest import mock
        from ui import widgets
        with mock.patch.object(widgets, "draw_button", wraps=widgets.draw_button) as m:
            cs.draw(game.screen)
        calls = [c for c in m.call_args_list if c.args[3] == "Begin"]
        self.assertEqual(len(calls), 1)
        return calls[0].kwargs["state"], calls[0].kwargs["shape"], calls[0].args[2]

    def test_native_height_and_wide_shape(self):
        game, cs = self._cs()
        state, shape, rect = self._state(game, cs)
        self.assertEqual(rect.height, 64)
        self.assertEqual(shape, "wide")
        self.assertEqual(cs._mouse.hits.rect_of("begin"), rect)      # hit rect == art rect

    def test_normal_then_hover_then_pressed_then_normal(self):
        game, cs = self._cs()
        self.assertEqual(self._state(game, cs)[0], "normal")
        pos = cs._mouse.hits.rect_of("begin").center
        _mouse(game, pygame.MOUSEMOTION, pos)
        self.assertEqual(self._state(game, cs)[0], "hover")
        _mouse(game, pygame.MOUSEBUTTONDOWN, pos)
        self.assertEqual(self._state(game, cs)[0], "pressed")
        self.assertIsInstance(game.state_machine.current, CharacterSelectState)  # not yet
        _mouse(game, pygame.MOUSEMOTION, (5, 5))                          # dragged off
        self.assertEqual(self._state(game, cs)[0], "pressed")             # still held
        _mouse(game, pygame.MOUSEBUTTONUP, (5, 5))                        # released off: no start
        self.assertIsInstance(game.state_machine.current, CharacterSelectState)
        self.assertEqual(self._state(game, cs)[0], "normal")

    def test_begin_label_uses_its_own_lift(self):
        from unittest import mock
        from ui import widgets
        from game.states.character_select_state import _BEGIN_TEXT_DY
        game, cs = self._cs()
        seen = []
        real = widgets.draw_button

        def spy(*a, **k):
            r = real(*a, **k)
            if a[3] == "Begin":
                seen.append((a[2], r))
            return r

        with mock.patch.object(widgets, "draw_button", side_effect=spy):
            cs.draw(game.screen)
        (rect, label), = seen
        # The lift is the owner's tuning knob -- pin that the label uses it,
        # not its value.
        self.assertEqual(label.centery, rect.centery + widgets.LABEL_DY - _BEGIN_TEXT_DY)
        self.assertEqual(rect, cs._layout["begin"])                  # the button itself unmoved

    def test_layout_still_fits_at_sixty_four(self):
        game, cs = self._cs()
        lay = cs._layout
        self.assertGreater(lay["begin"].top, lay["diff_y"])
        self.assertGreater(lay["instr_top"], lay["begin"].bottom)
        self.assertLessEqual(lay["hint_bottom"], config.SCREEN_HEIGHT)   # the hint stays on screen

    def test_art_lands_on_screen(self):
        game, cs = self._cs()
        rect = cs._mouse.hits.rect_of("begin")
        sheet = game.assets.image("btn_blue_wide")
        self.assertIsNotNone(sheet)
        # A cap pixel of the drawn button equals the sheet's.
        self.assertEqual(game.screen.get_at((rect.left + 20, rect.top + 30)),
                         sheet.get_at((20, 30)))


class HeroCardArtTests(unittest.TestCase):
    """UI art, group C: hero cards on the panel sheets -- gold for the
    selected hero, sunk (pressed sheet) while armed or held."""

    def _cs(self):
        game, cs = _select()
        cs.draw(game.screen)
        return game, cs

    def _card_states(self, game, cs):
        from unittest import mock
        from ui import widgets
        with mock.patch.object(widgets, "draw_button", wraps=widgets.draw_button) as m:
            cs.draw(game.screen)
        panels = [c for c in m.call_args_list if c.kwargs.get("shape") == "panel"]
        self.assertEqual(len(panels), len(cs.ids))
        return [c.kwargs["state"] for c in panels]

    def _click(self, game, pos):
        _mouse(game, pygame.MOUSEBUTTONDOWN, pos)
        _mouse(game, pygame.MOUSEBUTTONUP, pos)

    def test_selected_card_is_gold_the_rest_blue(self):
        game, cs = self._cs()
        self.assertEqual(self._card_states(game, cs), ["hover", "normal", "normal"])
        _key(game, pygame.K_RIGHT)
        self.assertEqual(self._card_states(game, cs), ["normal", "hover", "normal"])

    def test_first_click_sinks_the_card_and_moving_away_lifts_it(self):
        game, cs = self._cs()
        card1 = cs._mouse.hits.rect_of(("hero", 1)).center
        self._click(game, card1)                                  # arms card 1
        self.assertEqual(self._card_states(game, cs), ["normal", "pressed", "normal"])
        _mouse(game, pygame.MOUSEMOTION, cs._mouse.hits.rect_of(("hero", 2)).center)
        self.assertEqual(self._card_states(game, cs), ["normal", "normal", "hover"])

    def test_keyboard_never_sinks_a_card(self):
        game, cs = self._cs()
        for _ in range(3):
            _key(game, pygame.K_RIGHT)
        self.assertNotIn("pressed", self._card_states(game, cs))

    def test_held_button_sinks_the_card_under_it(self):
        game, cs = self._cs()
        card2 = cs._mouse.hits.rect_of(("hero", 2)).center
        _mouse(game, pygame.MOUSEBUTTONDOWN, card2)
        self.assertEqual(self._card_states(game, cs)[2], "pressed")
        _mouse(game, pygame.MOUSEBUTTONUP, (5, 5))                 # released off: no arm
        self.assertIsNone(cs._armed_hero)
        self.assertNotIn("pressed", self._card_states(game, cs))

    def test_armed_card_content_shifts_down_with_the_art(self):
        from ui import widgets
        game, cs = self._cs()
        name = cs.content.characters[cs.ids[1]]["name"]

        class _Spy(pygame.Surface):
            """A screen that records where each surface was blitted
            (`Surface.blit` itself is a C attribute and cannot be patched)."""
            def __init__(self, size):
                super().__init__(size)
                self.blits = []

            def blit(self, src, dest, *a, **k):
                self.blits.append((src.get_size(), dest))
                return super().blit(src, dest, *a, **k)

        # The name blit is found by its rendered size and its centre on card 1
        # (`Font.render` is C-level too and cannot be patched).
        want = cs._name.render(name, True, config.COLOR_TEXT).get_size()
        card = cs._mouse.hits.rect_of(("hero", 1))

        def name_y():
            screen = _Spy(game.screen.get_size())
            cs.draw(screen)
            for size, dest in screen.blits:
                r = pygame.Rect(dest, size) if not isinstance(dest, pygame.Rect) else dest
                if size == want and abs(r.centerx - card.centerx) <= 1 and r.top < card.top + 40:
                    return r.top
            self.fail("name not blitted")

        up = name_y()
        self._click(game, cs._mouse.hits.rect_of(("hero", 1)).center)
        down = name_y()
        self.assertEqual(down - up, widgets.PRESSED_DY)

    def test_art_lands_on_screen(self):
        game, cs = self._cs()
        rect = cs._mouse.hits.rect_of(("hero", 0))                 # selected -> gold
        sheet = game.assets.image("btn_gold_panel")
        self.assertEqual(game.screen.get_at((rect.left + 12, rect.top + 12)),
                         sheet.get_at((12, 12)))


class DifficultyRibbonTests(unittest.TestCase):
    """UI art, group E: the difficulty sits on a ribbon whose colour is the
    difficulty; it stays keyboard-only."""

    def _cs(self):
        game, cs = _select()
        cs.draw(game.screen)
        return game, cs

    def _ribbon_call(self, game, cs):
        from unittest import mock
        from ui import widgets
        with mock.patch.object(widgets, "draw_ribbon", wraps=widgets.draw_ribbon) as m:
            cs.draw(game.screen)
        self.assertEqual(m.call_count, 1)
        return m.call_args

    def test_config_maps_every_difficulty_to_a_pack_colour(self):
        from ui import widgets
        self.assertEqual(set(config.DIFFICULTY_RIBBON), set(config.DIFFICULTY_ORDER))
        for colour in config.DIFFICULTY_RIBBON.values():
            self.assertIn(colour, widgets.RIBBON_COLOURS)
        self.assertEqual([config.DIFFICULTY_RIBBON[d] for d in config.DIFFICULTY_ORDER],
                         ["blue", "yellow", "red"])

    def test_colour_and_label_follow_the_difficulty(self):
        game, cs = self._cs()
        for _ in config.DIFFICULTY_ORDER:
            call = self._ribbon_call(game, cs)
            self.assertEqual(call.kwargs["colour"], config.DIFFICULTY_RIBBON[cs.difficulty])
            self.assertIsNone(call.args[3])                       # the pair is blitted by the state
            a, b = cs._layout["diff_runs"]
            want_b = cs._diff_type.size(config.DIFFICULTY_LABELS[cs.difficulty])[0]
            self.assertEqual(b.width, want_b)                     # the type run follows the difficulty
            _key(game, pygame.K_DOWN)

    def test_ribbon_geometry_and_stacking(self):
        game, cs = self._cs()
        lay = cs._layout
        rib = lay["ribbon"]
        self.assertEqual(rib.height, 64)
        self.assertEqual(rib.centery, lay["diff_y"])
        self.assertEqual(rib.centerx, config.SCREEN_WIDTH // 2)
        self.assertLess(rib.centery, lay["begin"].top)              # ribbon above Begin (they may overlap)
        a, b = cs._layout["diff_runs"]
        self.assertGreaterEqual(rib.width, a.width + b.width + 128)  # forked ends clear of the text
        self.assertLessEqual(lay["hint_bottom"], config.SCREEN_HEIGHT)   # the hint stays on screen

    def test_ribbon_is_registered_and_a_click_recolours_it(self):
        game, cs = self._cs()
        rib = cs._layout["ribbon"]
        self.assertEqual(cs._mouse.hits.rect_of("difficulty"), rib)   # hit rect == drawn ribbon
        _mouse(game, pygame.MOUSEBUTTONDOWN, rib.center)
        _mouse(game, pygame.MOUSEBUTTONUP, rib.center)
        self.assertEqual(cs.difficulty, config.DIFFICULTY_ORDER[1])
        self.assertEqual(self._ribbon_call(game, cs).kwargs["colour"],
                         config.DIFFICULTY_RIBBON[config.DIFFICULTY_ORDER[1]])

    def test_press_on_the_ribbon_released_elsewhere_is_inert(self):
        game, cs = self._cs()
        rib = cs._layout["ribbon"]
        _mouse(game, pygame.MOUSEBUTTONDOWN, rib.center)
        _mouse(game, pygame.MOUSEBUTTONUP, (5, 5))
        self.assertEqual(cs.difficulty, config.DIFFICULTY_ORDER[0])

    def test_keys_still_cycle_both_ways(self):
        game, cs = self._cs()
        _key(game, pygame.K_DOWN)
        self.assertEqual(cs.difficulty, config.DIFFICULTY_ORDER[1])
        _key(game, pygame.K_UP)
        _key(game, pygame.K_UP)
        self.assertEqual(cs.difficulty, config.DIFFICULTY_ORDER[-1])      # wraps upward

    def test_art_lands_on_screen(self):
        game, cs = self._cs()
        rib = cs._layout["ribbon"]
        sheet = game.assets.image("ribbon_blue")                     # Normal
        self.assertEqual(game.screen.get_at((rib.left + 20, rib.top + 30)),
                         sheet.get_at((20, 30)))


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


class CharacterSelectTextTests(unittest.TestCase):
    """Fonts, group D: titles on the card in the title face and black, the
    rest in the dark grey; the difficulty is a title-face label plus a
    body-face type, centred as a pair on the ribbon."""

    def _cs(self):
        game, cs = _select()
        cs.draw(game.screen)
        return game, cs

    @staticmethod
    def _has_colour(screen, rect, colour):
        want = tuple(colour) + (255,)
        return any(tuple(screen.get_at((x, y))) == want
                   for x in range(rect.left, rect.right) for y in range(rect.top, rect.bottom))

    def test_card_fonts_are_the_title_face_where_asked(self):
        from game import fonts
        _, cs = self._cs()
        probe = "Aegis"
        self.assertEqual(cs._name.size(probe), fonts.heading(30).size(probe))
        self.assertEqual(cs._trait.size(probe), fonts.heading(20).size(probe))
        self.assertNotEqual(cs._trait.size(probe), fonts.body(20).size(probe))   # not the body face
        self.assertEqual(cs._diff_type.size(probe), fonts.body(26).size(probe))

    def test_card_text_colours(self):
        game, cs = self._cs()
        card = cs._mouse.hits.rect_of(("hero", 1))                    # not selected -> blue art
        name_band = pygame.Rect(card.left + 16, card.top + 12, card.width - 32, 40)
        rows_band = pygame.Rect(card.left + 16, card.top + 66, card.width - 32, 60)
        self.assertTrue(self._has_colour(game.screen, name_band, config.COLOR_ON_BUTTON))
        self.assertTrue(self._has_colour(game.screen, rows_band, config.COLOR_ON_BUTTON_DIM))
        self.assertFalse(self._has_colour(game.screen, card, config.COLOR_TEXT))       # old light text gone
        self.assertFalse(self._has_colour(game.screen, card, config.COLOR_TEXT_DIM))

    def test_difficulty_pair_is_centred_on_the_ribbon(self):
        _, cs = self._cs()
        rib = cs._layout["ribbon"]
        a, b = cs._layout["diff_runs"]
        self.assertEqual(a.right, b.left)                             # adjacent runs
        self.assertAlmostEqual((a.left + b.right) / 2, rib.centerx, delta=1)
        self.assertTrue(rib.contains(a) and rib.contains(b))
        self.assertEqual(a.width, cs._name.size("Difficulty:  ")[0])  # title face for the label

    def test_difficulty_pair_is_lifted_off_the_ribbon_centre(self):
        from game.states.character_select_state import _RIBBON_TEXT_DY
        _, cs = self._cs()
        a, b = cs._layout["diff_runs"]
        self.assertEqual(a.centery, cs._layout["diff_y"] + _RIBBON_TEXT_DY)
        self.assertEqual(b.centery, a.centery)
        self.assertEqual(cs._layout["ribbon"].centery, cs._layout["diff_y"])   # the ribbon stays put
        self.assertTrue(cs._layout["ribbon"].contains(a))

    def test_difficulty_colours(self):
        game, cs = self._cs()
        a, b = cs._layout["diff_runs"]
        self.assertTrue(self._has_colour(game.screen, a, config.COLOR_ON_BUTTON))
        self.assertTrue(self._has_colour(game.screen, b, config.COLOR_ON_BUTTON_DIM))

    def test_begin_label_is_black(self):
        game, cs = self._cs()
        self.assertTrue(self._has_colour(game.screen, cs._layout["begin"], config.COLOR_ON_BUTTON))


class CardTextFitsTests(unittest.TestCase):
    """The hero-card body wraps by pixel width: every text blit inside a card
    fits the card's inner width."""

    def test_every_body_line_fits_inside_the_card(self):
        from game.states.character_select_state import _CARD_TEXT_INSET
        game, cs = _select()

        class _Spy(pygame.Surface):
            def __init__(self, size):
                super().__init__(size); self.blits = []
            def blit(self, src, dest, *a, **k):
                r = dest if isinstance(dest, pygame.Rect) else pygame.Rect(dest, src.get_size())
                self.blits.append(pygame.Rect(r))
                return super().blit(src, dest, *a, **k)

        screen = _Spy(game.screen.get_size())
        cs.draw(screen)
        for i in range(len(cs.ids)):
            card = cs._mouse.hits.rect_of(("hero", i))
            inner = card.inflate(-2 * _CARD_TEXT_INSET, 0)
            body = [r for r in screen.blits
                    if card.contains(r) and r.height <= cs._body.get_height() + 2
                    and r.top >= card.top + 60]
            self.assertTrue(body, f"no body text found on card {i}")
            for r in body:
                self.assertLessEqual(r.width, inner.width, f"card {i}: a line is wider than the inset")
