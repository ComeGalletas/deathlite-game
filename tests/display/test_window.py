"""`game/display/window.DisplayWindow` with the SDL shims and pygame's
display calls mocked: what it does when the scaled window opens, when it
is refused, on a mode switch, on a drag resize, and what it saves. The
real window behaviour behind these calls was established by the probes in
the journal ("Dynamic window scaling", 2026-09-15)."""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config, save as save_mod
from game.display import window as win_mod
from game.display.window import DisplayWindow

DESKTOP = (1920, 1080)


class _Harness:
    """Every outside call the manager makes, recorded."""

    def __init__(self, window_size=(1600, 900), refuse=False):
        self.window_size = tuple(window_size)
        self.refuse = refuse
        self.native = mock.MagicMock()
        self.native.usable_bounds.return_value = (1920, 1040)
        self.native.dpi_scale.return_value = 1.0
        self.native.set_window_size.side_effect = self._resize
        self.toggles = 0
        self.opened_flags = None

    def _resize(self, w, h, centre=True):
        self.window_size = (w, h)
        return True

    def open_surface(self, flags=0):
        self.opened_flags = flags
        if self.refuse:
            return pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT)), False
        return pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT)), True

    def toggle(self):
        self.toggles += 1
        return 0

    def patches(self):
        return [
            mock.patch.object(win_mod, "native", self.native),
            mock.patch.object(DisplayWindow, "open_surface", staticmethod(self.open_surface)),
            mock.patch.object(pygame.display, "get_window_size", lambda: self.window_size),
            mock.patch.object(pygame.display, "get_desktop_sizes", lambda: [DESKTOP]),
            mock.patch.object(pygame.display, "toggle_fullscreen", self.toggle),
            mock.patch.object(config, "WINDOW_RESIZABLE", True),
            mock.patch("game.display.window.sys.platform", "win32"),
        ]


def _open(harness, settings=None):
    dw = DisplayWindow()
    dw.restore(settings)
    dw.open()
    return dw


class OpenTests(unittest.TestCase):
    def setUp(self):
        self.h = _Harness()
        self._ps = self.h.patches()
        for p in self._ps:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._ps])

    def test_a_scaled_window_is_made_shrinkable_and_freely_scalable(self):
        dw = _open(self.h)
        self.assertTrue(dw.available)
        self.h.native.set_minimum_size.assert_called_with(*config.WINDOW_MIN)
        self.h.native.set_integer_scale.assert_any_call(False)
        self.assertEqual(self.h.opened_flags & pygame.RESIZABLE, pygame.RESIZABLE)
        self.assertFalse(self.h.opened_flags & pygame.FULLSCREEN)

    def test_first_launch_fits_the_window_to_the_desktop(self):
        dw = _open(self.h)
        # 1920x1040 usable at 1.0 DPI: the logical size fits as it is.
        self.assertEqual(dw.windowed_size, (1600, 900))
        self.h.native.set_window_size.assert_called_with(1600, 900)

    def test_a_saved_size_is_applied_clamped_to_the_desktop(self):
        dw = _open(self.h, {"display": {"mode": "windowed", "window": [4000, 2250]}})
        self.assertEqual(dw.windowed_size, DESKTOP)
        self.h.native.set_window_size.assert_called_with(*DESKTOP)

    def test_a_saved_borderless_mode_opens_windowed_then_toggles(self):
        # Never the FULLSCREEN flag: pygame's scaled path would pick a
        # display mode for the logical size (a real mode switch); the toggle
        # is SDL's desktop fullscreen.
        dw = _open(self.h, {"display": {"mode": "borderless", "window": [1280, 720]}})
        self.assertEqual(dw.mode, "borderless")
        self.assertFalse(self.h.opened_flags & pygame.FULLSCREEN)
        self.assertEqual(self.h.toggles, 1)
        self.h.native.set_window_size.assert_not_called()
        self.assertEqual(dw.windowed_size, (1280, 720))

    def test_the_scale_is_the_window_over_the_logical_size(self):
        self.h.window_size = (1920, 1080)
        seen = []
        dw = DisplayWindow()
        dw.on_scale_changed = seen.append
        dw.restore({"display": {"mode": "windowed", "window": [1920, 1080]}})
        dw.open()
        self.assertAlmostEqual(dw.scale, 1.2)
        self.assertEqual(seen, [dw.scale])


class RefusedTests(unittest.TestCase):
    def test_a_plain_window_leaves_everything_dormant(self):
        h = _Harness(refuse=True)
        ps = h.patches()
        for p in ps:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in ps])
        dw = _open(h, {"display": {"mode": "borderless"}})
        self.assertFalse(dw.available)
        self.assertEqual(dw.mode, "windowed")
        h.native.set_minimum_size.assert_not_called()
        self.assertFalse(dw.set_mode("borderless"))
        self.assertFalse(dw.cycle_resolution(+1))
        self.assertFalse(dw.resolution_selectable())
        self.assertEqual(dw.mode_label(), "Unavailable")
        self.assertEqual(dw.resolution_label(), "Unavailable")
        self.assertEqual(h.toggles, 0)

    def test_the_web_profile_never_asks_for_a_resizable_window(self):
        h = _Harness()
        ps = h.patches()
        for p in ps:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in ps])
        with mock.patch.object(config, "WINDOW_RESIZABLE", False):
            dw = _open(h)
        self.assertFalse(dw.available)
        self.assertEqual(h.opened_flags, 0)


class ModeTests(unittest.TestCase):
    def setUp(self):
        self.h = _Harness()
        self._ps = self.h.patches()
        for p in self._ps:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._ps])
        self.dw = _open(self.h, {"display": {"mode": "windowed", "window": [1280, 720]}})

    def test_borderless_toggles_once_and_remembers_the_windowed_size(self):
        self.h.native.reset_mock()
        self.assertTrue(self.dw.set_mode("borderless"))
        self.assertEqual(self.h.toggles, 1)
        self.assertEqual(self.dw.mode, "borderless")
        self.assertEqual(self.dw.windowed_size, (1280, 720))
        self.h.native.set_window_size.assert_not_called()
        self.assertFalse(self.dw.resolution_selectable())
        self.assertEqual(self.dw.resolution_label(), "1920x1080")   # the desktop

    def test_back_to_windowed_restores_the_size_and_the_scaling_fix(self):
        self.dw.set_mode("borderless")
        self.h.native.reset_mock()
        self.assertTrue(self.dw.set_mode("windowed"))
        self.assertEqual(self.h.toggles, 2)
        self.h.native.set_window_size.assert_called_with(1280, 720)
        self.h.native.set_integer_scale.assert_called_with(False)

    def test_the_same_mode_again_is_a_no_op(self):
        self.assertFalse(self.dw.set_mode("windowed"))
        self.assertEqual(self.h.toggles, 0)

    def test_an_unknown_mode_is_refused_loudly(self):
        with self.assertRaises(ValueError):
            self.dw.set_mode("exclusive")


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.h = _Harness()
        self._ps = self.h.patches()
        for p in self._ps:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._ps])
        self.dw = _open(self.h, {"display": {"mode": "windowed", "window": [1280, 720]}})

    def test_the_list_is_what_fits_this_desktop(self):
        self.assertEqual(self.dw.resolution_entries(),
                         [(1280, 720), (1600, 900), (1920, 1080)])
        self.assertEqual(self.dw.resolution_index(), 0)
        self.assertEqual(self.dw.resolution_label(), "1280x720")

    def test_right_steps_up_and_wraps(self):
        self.assertTrue(self.dw.cycle_resolution(+1))
        self.assertEqual(self.dw.windowed_size, (1600, 900))
        self.dw.cycle_resolution(+1)
        self.dw.cycle_resolution(+1)
        self.assertEqual(self.dw.windowed_size, (1280, 720))

    def test_a_dragged_size_reads_custom_and_steps_to_a_neighbour(self):
        self.h.window_size = (1734, 975)
        self.dw.handle_event(pygame.event.Event(pygame.WINDOWSIZECHANGED))
        self.assertEqual(self.dw.resolution_label(), "Custom 1734x975")
        self.assertTrue(self.dw.dirty)
        self.dw.cycle_resolution(+1)
        self.assertEqual(self.dw.windowed_size, (1920, 1080))
        self.assertFalse(self.dw.dirty)
        self.h.window_size = (1734, 975)
        self.dw.handle_event(pygame.event.Event(pygame.WINDOWSIZECHANGED))
        self.dw.cycle_resolution(-1)
        self.assertEqual(self.dw.windowed_size, (1600, 900))

    def test_in_borderless_the_row_is_not_steppable(self):
        self.dw.set_mode("borderless")
        self.h.native.reset_mock()
        self.assertFalse(self.dw.cycle_resolution(+1))
        self.h.native.set_window_size.assert_not_called()


class EventTests(unittest.TestCase):
    def setUp(self):
        self.h = _Harness()
        self._ps = self.h.patches()
        for p in self._ps:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._ps])
        self.dw = _open(self.h, {"display": {"mode": "windowed", "window": [1600, 900]}})

    def test_a_drag_resize_is_remembered_and_never_consumed(self):
        self.h.window_size = (1200, 675)
        seen = []
        self.dw.on_scale_changed = seen.append
        self.assertFalse(self.dw.handle_event(pygame.event.Event(pygame.WINDOWSIZECHANGED)))
        self.assertEqual(self.dw.windowed_size, (1200, 675))
        self.assertTrue(self.dw.dirty)
        self.assertAlmostEqual(self.dw.scale, 0.75)
        self.assertEqual(seen, [0.75])

    def test_a_size_change_in_borderless_is_not_a_windowed_size(self):
        self.dw.set_mode("borderless")
        self.h.window_size = DESKTOP
        self.dw.handle_event(pygame.event.Event(pygame.WINDOWSIZECHANGED))
        self.assertEqual(self.dw.windowed_size, (1600, 900))
        self.assertFalse(self.dw.dirty)

    def test_other_events_are_ignored(self):
        self.assertFalse(self.dw.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)))

    def test_the_floor_is_lifted_before_every_size(self):
        # pygame re-pins the minimum to the logical size on the way out of
        # fullscreen (probe, 2026-09-15: 1280x720 came back as 1600x900), so
        # the floor is lifted again before each size, and the order matters.
        self.dw.set_mode("borderless")
        self.h.native.reset_mock()
        self.dw.set_mode("windowed")
        self.dw.set_windowed_size((1280, 720))
        names = [c[0] for c in self.h.native.mock_calls if c[0] in ("set_minimum_size",
                                                                   "set_window_size")]
        self.assertEqual(names[:2], ["set_minimum_size", "set_window_size"])
        self.assertEqual(names[-2:], ["set_minimum_size", "set_window_size"])
        self.h.native.set_minimum_size.assert_called_with(*config.WINDOW_MIN)
        self.h.native.set_window_size.assert_called_with(1280, 720)


class RenderAspectTests(unittest.TestCase):
    """The 21:9 render (journal section "Ultrawide render extent"): the
    aspect follows the mode and the picked size, a change re-opens the
    display, a drag never does, and `config.SCREEN_WIDTH` follows."""

    def setUp(self):
        self.h = _Harness()
        self._ps = self.h.patches()
        for p in self._ps:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._ps])
        self.addCleanup(setattr, config, "SCREEN_WIDTH", 1600)
        self.reopens = []
        reopen = mock.patch.object(
            DisplayWindow, "reopen",
            lambda dw, aspect: self.reopens.append(aspect) or setattr(dw, "render_aspect", aspect))
        reopen.start()
        self.addCleanup(reopen.stop)

    def test_a_16_9_pick_opens_the_16_9_render(self):
        dw = _open(self.h, {"display": {"mode": "windowed", "window": [1920, 1080]}})
        self.assertEqual(dw.render_aspect, "16:9")
        self.assertEqual(config.SCREEN_WIDTH, 1600)
        self.assertEqual(dw.settings()["render"], "16:9")

    def test_a_saved_21_9_render_opens_2100_wide(self):
        dw = _open(self.h, {"display": {"mode": "windowed", "window": [1920, 1080],
                                        "render": "21:9"}})
        self.assertEqual(dw.render_aspect, "21:9")
        self.assertEqual(config.SCREEN_WIDTH, 2100)
        self.assertEqual(self.h.opened_flags & pygame.RESIZABLE, pygame.RESIZABLE)

    def test_borderless_on_an_ultrawide_desktop_derives_21_9(self):
        with mock.patch.object(pygame.display, "get_desktop_sizes", lambda: [(3440, 1440)]):
            dw = _open(self.h, {"display": {"mode": "borderless"}})
        self.assertEqual(dw.render_aspect, "21:9")
        self.assertEqual(config.SCREEN_WIDTH, 2100)

    def test_picking_a_21_9_size_reopens_and_a_drag_does_not(self):
        with mock.patch.object(pygame.display, "get_desktop_sizes", lambda: [(3440, 1440)]):
            dw = _open(self.h, {"display": {"mode": "windowed", "window": [1920, 1080]}})
            self.assertEqual(dw.render_aspect, "16:9")
            dw.set_windowed_size((2560, 1080))
            self.assertEqual(self.reopens, ["21:9"])
            self.h.window_size = (2000, 900)                 # a drag to a 21:9-ish shape
            dw.handle_event(pygame.event.Event(pygame.WINDOWSIZECHANGED))
            self.assertEqual(self.reopens, ["21:9"])        # no re-open for a drag
            dw.set_windowed_size((1600, 900))
            self.assertEqual(self.reopens, ["21:9", "16:9"])

    def test_the_mode_switch_settles_the_aspect_both_ways(self):
        with mock.patch.object(pygame.display, "get_desktop_sizes", lambda: [(3440, 1440)]):
            dw = _open(self.h, {"display": {"mode": "windowed", "window": [1920, 1080]}})
            dw.set_mode("borderless")
            self.assertEqual(self.reopens, ["21:9"])
            dw.set_mode("windowed")
            self.assertEqual(self.reopens, ["21:9", "16:9"])

    def test_the_plain_fallback_always_renders_16_9(self):
        refused = mock.patch.object(
            DisplayWindow, "open_surface", staticmethod(_Harness(refuse=True).open_surface))
        refused.start()
        self.addCleanup(refused.stop)
        dw = _open(self.h, {"display": {"mode": "borderless", "render": "21:9"}})
        self.assertEqual(dw.render_aspect, "16:9")
        self.assertEqual(config.SCREEN_WIDTH, 1600)
        # The surface too, not only the number: the suite's dummy driver
        # caught a 2100-wide surface left behind by the refused open.
        self.assertEqual(dw.surface.get_size(), (1600, 900))


class ReopenTests(unittest.TestCase):
    def test_reopen_reinits_the_display_and_calls_the_hooks_in_order(self):
        h = _Harness()
        ps = h.patches()
        for p in ps:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in ps])
        self.addCleanup(setattr, config, "SCREEN_WIDTH", 1600)
        order = []
        with mock.patch.object(pygame.display, "quit", lambda: order.append("quit")), \
                mock.patch.object(pygame.display, "init", lambda: order.append("init")), \
                mock.patch("game.display.window.native.forget_window",
                           lambda: order.append("forget")):
            dw = _open(h, {"display": {"mode": "windowed", "window": [1920, 1080]}})
            dw.on_before_open = lambda: order.append("before")
            dw.on_reopened = lambda surf: order.append(("reopened", surf.get_size()))
            surf = dw.reopen("21:9")
        self.assertEqual(order, ["forget", "quit", "init", "before", ("reopened", (2100, 900))])
        self.assertEqual(surf.get_size(), (2100, 900))
        self.assertEqual(dw.render_aspect, "21:9")
        self.assertEqual(config.SCREEN_WIDTH, 2100)
        self.assertTrue(dw.available)
        with self.assertRaises(ValueError):
            dw.reopen("4:3")


class SettingsTests(unittest.TestCase):
    def test_the_render_aspect_round_trips_and_junk_is_dropped(self):
        d = save_mod._coerce({"settings": {"display": {"mode": "windowed", "render": "21:9"}}})
        self.assertEqual(d.settings["display"]["render"], "21:9")
        d = save_mod._coerce({"settings": {"display": {"mode": "windowed", "render": "4:3"}}})
        self.assertNotIn("render", d.settings["display"])

    def test_settings_round_trip_through_the_save_coercion(self):
        dw = DisplayWindow()
        dw.mode = "borderless"
        dw.windowed_size = (1280, 720)
        raw = {"settings": {"display": dw.settings()}}
        loaded = save_mod._coerce(raw)
        back = DisplayWindow()
        back.restore(loaded.settings)
        self.assertEqual(back.mode, "borderless")
        self.assertEqual(back.windowed_size, (1280, 720))

    def test_the_coercion_drops_what_it_does_not_know(self):
        d = save_mod._coerce({"settings": {"display": {"mode": "exclusive",
                                                       "window": [0, "x"]}}})
        self.assertNotIn("display", d.settings)
        d = save_mod._coerce({"settings": {"display": {"mode": "windowed", "window": [1, 2, 3]}}})
        self.assertEqual(d.settings["display"], {"mode": "windowed"})
        d = save_mod._coerce({"settings": {"display": "nonsense"}})
        self.assertNotIn("display", d.settings)

    def test_defaults_when_nothing_is_saved(self):
        dw = DisplayWindow()
        dw.restore({})
        self.assertEqual(dw.mode, config.WINDOW_MODE_DEFAULT)
        self.assertIsNone(dw.windowed_size)
        self.assertEqual(dw.settings(), {"mode": config.WINDOW_MODE_DEFAULT})


if __name__ == "__main__":
    unittest.main()
