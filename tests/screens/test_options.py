"""The Options screen: the three-level mixer (master over music and sound
effects), mute, the key layout, the window rows and the Sanctuary entry point.
Reached from the menu's "Options" entry, or pushed over a run from the pause
menu; every change is persisted immediately. Started as start-screen milestone
M2 and has grown with `audio_mixer_journal.md` and `options_mouse_journal.md`.
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


def _mouse(game, event_type, pos, button=1):
    kw = {"pos": pos}
    if event_type == pygame.MOUSEMOTION:
        kw.update(rel=(0, 0), buttons=(0, 0, 0))
    else:
        kw["button"] = button
    game.state_machine.handle_event(pygame.event.Event(event_type, **kw))


def _click(game, pos):
    _mouse(game, pygame.MOUSEBUTTONDOWN, pos)
    _mouse(game, pygame.MOUSEBUTTONUP, pos)


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
        opt.sel = opt._rows.index("tutorials")
        _key(game, pygame.K_DOWN)
        self.assertEqual(opt._row_id(), "sanctuary")
        _key(game, pygame.K_UP)
        self.assertEqual(opt._row_id(), "tutorials")
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
    """The **Sound effects** row: the level every cue `systems/audio.py` plays
    is heard at, synthesised and recorded alike (journal
    `audio_mixer_journal.md`, 2026-09-16). It kept the save key `volume`,
    which is what it has always been."""

    def _on_sfx_row(self):
        game, opt = _options()
        opt.sel = opt._rows.index("sfx")
        return game, opt

    def test_right_raises_volume_by_one_step_and_persists(self):
        game, _ = self._on_sfx_row()
        start = game.audio.volume
        _key(game, pygame.K_RIGHT)
        self.assertAlmostEqual(game.audio.volume, start + config.VOLUME_STEP, places=6)
        self.assertAlmostEqual(save_mod.load(game.save_path).settings["volume"],
                               game.audio.volume, places=6)

    def test_left_lowers_volume_by_one_step(self):
        game, _ = self._on_sfx_row()
        start = game.audio.volume
        _key(game, pygame.K_LEFT)
        self.assertAlmostEqual(game.audio.volume, start - config.VOLUME_STEP, places=6)

    def test_volume_clamps_to_unit_range(self):
        game, _ = self._on_sfx_row()
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
        game, _ = self._on_sfx_row()
        _key(game, pygame.K_RIGHT)
        _key(game, pygame.K_RIGHT)
        v = game.audio.volume
        self.assertAlmostEqual(Game(save_path=game.save_path).audio.volume, v, places=6)


class MusicVolumeTests(unittest.TestCase):
    """The music level is its own row and its own saved value, independent of
    the sound-effects level (journals `music_tracks_journal.md` and
    `audio_mixer_journal.md`, 2026-09-16)."""

    def _on_music_row(self):
        game, opt = _options()
        opt.sel = opt._rows.index("music")
        return game, opt

    def test_right_raises_music_volume_by_one_step_and_persists(self):
        game, _ = self._on_music_row()
        start = game.music.volume
        _key(game, pygame.K_RIGHT)
        self.assertAlmostEqual(game.music.volume, start + config.VOLUME_STEP, places=6)
        self.assertAlmostEqual(
            save_mod.load(game.save_path).settings["music_volume"],
            game.music.volume, places=6)

    def test_left_lowers_music_volume_by_one_step(self):
        game, _ = self._on_music_row()
        start = game.music.volume
        _key(game, pygame.K_LEFT)
        self.assertAlmostEqual(game.music.volume, start - config.VOLUME_STEP, places=6)

    def test_music_volume_clamps_to_unit_range(self):
        game, _ = self._on_music_row()
        for _ in range(40):
            _key(game, pygame.K_RIGHT)
        self.assertEqual(game.music.volume, 1.0)
        for _ in range(60):
            _key(game, pygame.K_LEFT)
        self.assertEqual(game.music.volume, 0.0)

    def test_the_two_sliders_are_independent(self):
        game, opt = self._on_music_row()
        cue_before = game.audio.volume
        _key(game, pygame.K_RIGHT)
        self.assertEqual(game.audio.volume, cue_before)
        opt.sel = opt._rows.index("sfx")
        music_before = game.music.volume
        _key(game, pygame.K_RIGHT)
        self.assertEqual(game.music.volume, music_before)

    def test_music_volume_survives_reload_into_a_fresh_game(self):
        game, _ = self._on_music_row()
        _key(game, pygame.K_RIGHT)
        _key(game, pygame.K_RIGHT)
        v = game.music.volume
        self.assertAlmostEqual(Game(save_path=game.save_path).music.volume, v, places=6)

    def test_the_default_is_the_configured_one(self):
        game, _ = _options()
        self.assertAlmostEqual(game.music.volume, config.MUSIC_VOLUME_DEFAULT, places=6)


class MusicRoutingTests(unittest.TestCase):
    def test_the_standalone_screen_plays_the_menu_track(self):
        _, opt = _options()
        self.assertEqual(opt.music, "menu")

    def test_opened_over_a_run_it_inherits_instead(self):
        """Pushed from the pause menu, Options is an overlay -- switching to
        the menu track there would interrupt the run's music."""
        from game.state import MUSIC_INHERIT
        game = _game()
        opt = OptionsState(game)
        game.state_machine.change(opt, in_run=True)
        self.assertIs(opt.music, MUSIC_INHERIT)


class MuteTests(unittest.TestCase):
    def test_enter_on_mute_row_toggles_and_persists(self):
        game, opt = _options()
        opt.sel = opt._rows.index("mute")
        before = game.audio.muted
        _key(game, pygame.K_RETURN)
        self.assertNotEqual(game.audio.muted, before)
        self.assertEqual(save_mod.load(game.save_path).settings["muted"], game.audio.muted)

    def test_the_m_key_mutes_the_music_as_well_as_the_cues(self):
        game, _ = _options()
        before = game.audio.muted
        # The M key is handled by Game, not the state, so drive it through
        # the real input pump rather than the state machine.
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m))
        game._process_input()
        self.assertNotEqual(game.audio.muted, before)
        self.assertEqual(game.music.muted, game.audio.muted)


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


class OptionsMouseTests(unittest.TestCase):
    """Mouse support on the last keyboard-only menu (journal
    `options_mouse_journal.md`, 2026-09-16): hover selects, a click does what
    ENTER does, and the two bars drag."""

    def _screen(self, *, display=None, in_run=False):
        game = _game()
        opt = OptionsState(game)
        game.state_machine.change(opt, in_run=in_run)
        game.running = True
        if display is not None:
            game.display = display
        opt.draw(game.screen)                 # registers the bands and the bars
        return game, opt

    def _row(self, opt, name):
        rect = opt._mouse.hits.rect_of(opt._rows.index(name))
        self.assertIsNotNone(rect, f"{name} registered no band")
        return rect.center

    # --- the bands ---------------------------------------------------
    def test_every_selectable_row_gets_a_band_and_they_do_not_overlap(self):
        _, opt = self._screen(display=_FakeDisplay())     # every row selectable
        rects = [opt._mouse.hits.rect_of(i) for i in range(len(opt._rows))]
        self.assertTrue(all(r is not None for r in rects))
        for a, b in zip(rects, rects[1:]):
            self.assertLessEqual(a.bottom, b.top)

    def test_a_skipped_row_registers_no_band(self):
        """With no scaled window both window rows are skipped, so the pointer
        passes over them exactly as Up / Down does."""
        game, opt = self._screen()
        self.assertFalse(game.display.available)
        for name in ("display", "resolution"):
            self.assertIsNone(opt._mouse.hits.rect_of(opt._rows.index(name)))
        self.assertIsNotNone(opt._mouse.hits.rect_of(opt._rows.index("back")))

    def test_in_borderless_only_the_resolution_row_loses_its_band(self):
        display = _FakeDisplay()
        display.mode = "borderless"
        _, opt = self._screen(display=display)
        self.assertIsNone(opt._mouse.hits.rect_of(opt._rows.index("resolution")))
        self.assertIsNotNone(opt._mouse.hits.rect_of(opt._rows.index("display")))

    def test_the_in_run_screen_registers_its_own_shorter_row_set(self):
        _, opt = self._screen(in_run=True)
        self.assertNotIn("sanctuary", opt._rows)
        self.assertEqual(len(opt._mouse.hits), len(opt._rows) - 2)   # window rows skipped

    # --- hover and click ---------------------------------------------
    def test_hover_selects_without_activating(self):
        game, opt = self._screen()
        _mouse(game, pygame.MOUSEMOTION, self._row(opt, "back"))
        self.assertEqual(opt._row_id(), "back")
        self.assertIs(game.state_machine.current, opt)

    def test_hover_off_every_band_leaves_the_selection_alone(self):
        game, opt = self._screen()
        _mouse(game, pygame.MOUSEMOTION, self._row(opt, "mute"))
        _mouse(game, pygame.MOUSEMOTION, (4, 4))
        self.assertEqual(opt._row_id(), "mute")

    def test_click_toggles_mute_and_persists(self):
        game, opt = self._screen()
        before = game.audio.muted
        _click(game, self._row(opt, "mute"))
        self.assertNotEqual(game.audio.muted, before)
        self.assertEqual(save_mod.load(game.save_path).settings["muted"], game.audio.muted)

    def test_click_cycles_the_key_layout(self):
        game, opt = self._screen()
        _click(game, self._row(opt, "key_layout"))
        self.assertEqual(game.key_layout, "arrows_move")

    def test_click_toggles_the_display_mode_and_steps_the_resolution(self):
        game, opt = self._screen(display=_FakeDisplay())
        _click(game, self._row(opt, "resolution"))
        self.assertEqual(game.display.windowed_size, (1920, 1080))     # forward, like ENTER
        _click(game, self._row(opt, "display"))
        self.assertEqual(game.display.mode, "borderless")

    def test_click_opens_the_sanctuary_and_back_returns(self):
        game, opt = self._screen()
        _click(game, self._row(opt, "sanctuary"))
        self.assertIsInstance(game.state_machine.current, MetaState)
        game, opt = self._screen()
        _click(game, self._row(opt, "back"))
        self.assertIsInstance(game.state_machine.current, MenuState)

    def test_release_on_another_row_is_inert(self):
        game, opt = self._screen()
        _mouse(game, pygame.MOUSEBUTTONDOWN, self._row(opt, "back"))
        _mouse(game, pygame.MOUSEBUTTONUP, self._row(opt, "mute"))
        self.assertIs(game.state_machine.current, opt)

    def test_click_off_every_band_is_inert(self):
        game, opt = self._screen()
        _click(game, (4, 4))
        self.assertIs(game.state_machine.current, opt)
        self.assertEqual(opt.sel, 0)

    # --- the wheel and the right button are dropped ------------------
    def test_the_wheel_never_touches_a_value(self):
        game, opt = self._screen(display=_FakeDisplay())
        opt.sel = opt._rows.index("resolution")
        game.state_machine.handle_event(
            pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1, flipped=False))
        self.assertEqual(game.display.windowed_size, (1600, 900))

    def test_the_right_button_never_activates_a_row(self):
        game, opt = self._screen()
        before = game.audio.muted
        pos = self._row(opt, "mute")
        _mouse(game, pygame.MOUSEBUTTONDOWN, pos, button=3)
        _mouse(game, pygame.MOUSEBUTTONUP, pos, button=3)
        self.assertEqual(game.audio.muted, before)
        self.assertIs(game.state_machine.current, opt)

    # --- the bars -----------------------------------------------------
    def _bar(self, opt, rid):
        bar = opt._bars[rid]
        return bar, (lambda f: (int(bar.left + f * bar.width), bar.centery))

    def test_a_click_in_the_bar_sets_the_level_on_the_step_grid(self):
        game, opt = self._screen()
        _, at = self._bar(opt, "sfx")
        _click(game, at(0.5))
        self.assertAlmostEqual(game.audio.volume, 0.5, places=6)
        _click(game, at(0.52))                            # inside the same step
        self.assertAlmostEqual(game.audio.volume, 0.5, places=6)

    def test_a_click_in_the_bar_does_not_also_activate_the_row(self):
        """The press is taken by the drag, so the release cannot read as a
        click on the row -- important on Back, and a rule the bars share."""
        game, opt = self._screen()
        _, at = self._bar(opt, "music")
        _click(game, at(0.25))
        self.assertIs(game.state_machine.current, opt)
        self.assertEqual(opt._row_id(), "music")          # the press selected it

    def test_a_drag_tracks_the_cursor_and_clamps_at_both_ends(self):
        game, opt = self._screen()
        bar, at = self._bar(opt, "sfx")
        _mouse(game, pygame.MOUSEBUTTONDOWN, at(0.2))
        self.assertAlmostEqual(game.audio.volume, 0.2, places=6)
        _mouse(game, pygame.MOUSEMOTION, at(0.8))
        self.assertAlmostEqual(game.audio.volume, 0.8, places=6)
        _mouse(game, pygame.MOUSEMOTION, (bar.right + 400, bar.centery))
        self.assertEqual(game.audio.volume, 1.0)
        _mouse(game, pygame.MOUSEMOTION, (bar.left - 400, bar.centery))
        self.assertEqual(game.audio.volume, 0.0)
        _mouse(game, pygame.MOUSEBUTTONUP, at(0.0))

    def test_a_drag_keeps_going_when_the_cursor_leaves_the_bar_vertically(self):
        game, opt = self._screen()
        bar, at = self._bar(opt, "sfx")
        _mouse(game, pygame.MOUSEBUTTONDOWN, at(0.5))
        _mouse(game, pygame.MOUSEMOTION, (int(bar.left + 0.9 * bar.width), bar.bottom + 200))
        self.assertAlmostEqual(game.audio.volume, 0.9, places=6)

    def test_the_drag_writes_the_save_once_on_release(self):
        game, opt = self._screen()
        _, at = self._bar(opt, "sfx")
        writes = []
        real = game.persist
        game.persist = lambda: (writes.append(game.audio.volume), real())[1]
        _mouse(game, pygame.MOUSEBUTTONDOWN, at(0.3))
        _mouse(game, pygame.MOUSEMOTION, at(0.6))
        _mouse(game, pygame.MOUSEMOTION, at(0.75))
        self.assertEqual(writes, [])
        _mouse(game, pygame.MOUSEBUTTONUP, at(0.75))
        self.assertEqual(len(writes), 1)
        game.persist = real
        self.assertAlmostEqual(save_mod.load(game.save_path).settings["volume"], 0.75,
                               places=6)

    def test_the_two_bars_drag_independently(self):
        game, opt = self._screen()
        _, cue = self._bar(opt, "sfx")
        _, music = self._bar(opt, "music")
        music_before = game.music.volume
        _click(game, cue(0.4))
        self.assertAlmostEqual(game.audio.volume, 0.4, places=6)
        self.assertEqual(game.music.volume, music_before)
        _click(game, music(0.15))
        self.assertAlmostEqual(game.music.volume, 0.15, places=6)
        self.assertAlmostEqual(game.audio.volume, 0.4, places=6)
        self.assertAlmostEqual(save_mod.load(game.save_path).settings["music_volume"],
                               0.15, places=6)

    def test_a_drag_blips_once_per_step_not_once_per_motion(self):
        """The master row's `xp` cue is feedback for a step crossed; dragging
        inside one step must stay silent."""
        game, opt = self._screen()
        bar, at = self._bar(opt, "sfx")
        played = []
        game.audio.play = lambda name, **kw: played.append(name)
        _mouse(game, pygame.MOUSEBUTTONDOWN, at(0.5))
        self.assertEqual(played, ["xp"])
        _mouse(game, pygame.MOUSEMOTION, (bar.left + bar.width // 2 + 1, bar.centery))
        self.assertEqual(played, ["xp"])                  # same step, no second blip
        _mouse(game, pygame.MOUSEMOTION, at(0.55))
        self.assertEqual(played, ["xp", "xp"])
        _mouse(game, pygame.MOUSEBUTTONUP, at(0.55))

    def test_the_music_bar_never_blips(self):
        game, opt = self._screen()
        _, at = self._bar(opt, "music")
        played = []
        game.audio.play = lambda name, **kw: played.append(name)
        _click(game, at(0.65))
        self.assertEqual(played, [])


class MasterVolumeTests(unittest.TestCase):
    """The **Master volume** row, the level over both children (journal
    `audio_mixer_journal.md`, 2026-09-16). It is row 0, so a fresh screen
    opens on it."""

    def _on_master_row(self):
        game, opt = _options()
        opt.sel = opt._rows.index("master")
        return game, opt

    def test_the_screen_opens_on_the_master_row(self):
        _, opt = _options()
        self.assertEqual(opt._row_id(), "master")

    def test_the_three_sliders_are_the_first_three_rows_in_order(self):
        _, opt = _options()
        self.assertEqual(opt._rows[:3], ("master", "music", "sfx"))

    def test_right_raises_the_master_on_both_players_and_persists(self):
        game, _ = self._on_master_row()
        start = game.audio.master
        _key(game, pygame.K_LEFT)                     # 1.0 is the default: step down
        self.assertAlmostEqual(game.audio.master, start - config.VOLUME_STEP, places=6)
        self.assertAlmostEqual(game.music.master, game.audio.master, places=6)
        self.assertAlmostEqual(
            save_mod.load(game.save_path).settings["master_volume"],
            game.audio.master, places=6)

    def test_the_master_clamps_to_unit_range(self):
        game, _ = self._on_master_row()
        for _ in range(40):
            _key(game, pygame.K_RIGHT)
        self.assertEqual(game.audio.master, 1.0)
        for _ in range(60):
            _key(game, pygame.K_LEFT)
        self.assertEqual(game.audio.master, 0.0)
        self.assertEqual(game.music.master, 0.0)

    def test_the_master_leaves_its_two_children_alone(self):
        game, _ = self._on_master_row()
        sfx, music = game.audio.volume, game.music.volume
        for _ in range(4):
            _key(game, pygame.K_LEFT)
        self.assertEqual(game.audio.volume, sfx)
        self.assertEqual(game.music.volume, music)

    def test_the_master_survives_reload_into_a_fresh_game(self):
        game, _ = self._on_master_row()
        _key(game, pygame.K_LEFT)
        _key(game, pygame.K_LEFT)
        m = game.audio.master
        fresh = Game(save_path=game.save_path)
        self.assertAlmostEqual(fresh.audio.master, m, places=6)
        self.assertAlmostEqual(fresh.music.master, m, places=6)

    def test_the_master_bar_drags_like_the_other_two(self):
        game, opt = _options()
        opt.draw(game.screen)
        bar = opt._bars["master"]
        _mouse(game, pygame.MOUSEBUTTONDOWN,
               (int(bar.left + 0.25 * bar.width), bar.centery))
        self.assertAlmostEqual(game.audio.master, 0.25, places=6)
        _mouse(game, pygame.MOUSEMOTION,
               (int(bar.left + 0.75 * bar.width), bar.centery))
        self.assertAlmostEqual(game.audio.master, 0.75, places=6)
        self.assertAlmostEqual(game.music.master, 0.75, places=6)
        _mouse(game, pygame.MOUSEBUTTONUP,
               (int(bar.left + 0.75 * bar.width), bar.centery))
        self.assertAlmostEqual(
            save_mod.load(game.save_path).settings["master_volume"], 0.75, places=6)

    def test_the_master_blips_and_the_music_row_stays_silent(self):
        game, opt = _options()
        played = []
        game.audio.play = lambda name, **kw: played.append(name)
        _key(game, pygame.K_LEFT)                     # master
        self.assertEqual(played, ["xp"])
        opt.sel = opt._rows.index("music")
        _key(game, pygame.K_LEFT)
        self.assertEqual(played, ["xp"])
        opt.sel = opt._rows.index("sfx")
        _key(game, pygame.K_LEFT)
        self.assertEqual(played, ["xp", "xp"])

    def test_all_ten_rows_are_drawn_above_the_hint(self):
        """Ten rows (the Tutorials row came in pass 5 of the key icons) is
        two more than the layout was built for; the last must still clear
        the hint line at the bottom of the box."""
        from game.states.options_state import _ROW_STEP, _ROW_TOP
        from ui import scale
        game, opt = _options()
        self.assertEqual(len(opt._rows), 10)
        last = scale.px(_ROW_TOP + (len(opt._rows) - 1) * _ROW_STEP)
        hint_top = game.screen.get_height() - scale.px(40) - scale.px(_ROW_STEP) // 2
        self.assertLess(last, hint_top)
        opt.draw(game.screen)                          # and it renders


class MixerMigrationTests(unittest.TestCase):
    """A save written before the master existed (journal
    `audio_mixer_journal.md`, 2026-09-16): `volume` has always been the cue
    level, so it becomes the sound-effects level and the master opens wide."""

    def _game_with(self, settings):
        import json
        path = os.path.join(tempfile.mkdtemp(), "save.json")
        game = _game()
        data = save_mod.load(game.save_path)
        data.settings.update(settings)
        for key in ("master_volume",):
            data.settings.pop(key, None)
        save_mod.save(data, path)
        raw = json.loads(open(path, encoding="utf-8").read())
        self.assertNotIn("master_volume", raw["settings"])
        return Game(save_path=path)

    def test_an_old_save_keeps_its_mix_with_the_master_wide_open(self):
        game = self._game_with({"volume": 0.35, "music_volume": 0.25})
        self.assertAlmostEqual(game.audio.volume, 0.35, places=6)
        self.assertAlmostEqual(game.music.volume, 0.25, places=6)
        self.assertEqual(game.audio.master, config.MASTER_VOLUME_DEFAULT)
        self.assertEqual(game.music.master, config.MASTER_VOLUME_DEFAULT)

    def test_a_fresh_save_starts_on_the_configured_defaults(self):
        game, _ = _options()
        self.assertEqual(game.audio.master, config.MASTER_VOLUME_DEFAULT)
        self.assertEqual(game.audio.volume, config.SFX_VOLUME_DEFAULT)
        self.assertEqual(game.music.volume, config.MUSIC_VOLUME_DEFAULT)

    def test_persisting_writes_all_three_levels(self):
        game, _ = _options()
        _key(game, pygame.K_LEFT)
        settings = save_mod.load(game.save_path).settings
        for key in ("master_volume", "volume", "music_volume"):
            self.assertIn(key, settings)
