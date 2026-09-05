"""ui/widgets.py: buttons and ribbons from the UI sheets, with the flat
fallback when a sheet is missing."""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import fonts
from game.assets import Assets, reset_assets
from ui import panels, widgets
from ui.mouse import MouseNav


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


class ButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def setUp(self):
        reset_assets()
        panels.clear_cache()
        self.assets = Assets()
        self.surface = pygame.Surface((400, 200), pygame.SRCALPHA)
        self.font = fonts.heading(24)

    def _drawn_rig(self, **kw):
        with mock.patch.object(panels, "slice", wraps=panels.slice) as m:
            widgets.draw_button(self.surface, self.assets, pygame.Rect(10, 10, 300, 64),
                                "Begin", font=self.font, **kw)
        return m.call_args[0][1]

    def test_state_picks_the_sheet(self):
        self.assertEqual(self._drawn_rig(state="normal"), "btn_blue_wide")
        self.assertEqual(self._drawn_rig(state="hover"), "btn_gold_wide")
        self.assertEqual(self._drawn_rig(state="pressed"), "btn_blue_wide_pressed")

    def test_shape_and_variant(self):
        self.assertEqual(self._drawn_rig(shape="panel"), "btn_blue_panel")
        self.assertEqual(self._drawn_rig(shape="panel", state="hover"), "btn_gold_panel")
        self.assertEqual(self._drawn_rig(shape="panel", state="pressed"), "btn_blue_panel_pressed")
        self.assertEqual(self._drawn_rig(variant="danger"), "btn_red_wide")
        self.assertEqual(self._drawn_rig(variant="danger", state="pressed"), "btn_red_wide_pressed")
        self.assertEqual(self._drawn_rig(variant="danger", state="hover"), "btn_gold_wide")

    def test_unknown_state_is_refused(self):
        with self.assertRaises(ValueError):
            widgets.draw_button(self.surface, self.assets, pygame.Rect(0, 0, 100, 64),
                                "x", state="down", font=self.font)

    def test_pressed_label_sits_four_px_lower(self):
        rect = pygame.Rect(10, 10, 300, 64)
        up = widgets.draw_button(self.surface, self.assets, rect, "Begin",
                                 state="normal", font=self.font)
        down = widgets.draw_button(self.surface, self.assets, rect, "Begin",
                                   state="pressed", font=self.font)
        self.assertEqual(down.centery - up.centery, widgets.PRESSED_DY)
        self.assertEqual(down.centerx, up.centerx)

    def test_label_is_lifted_onto_the_visual_centre(self):
        rect = pygame.Rect(10, 10, 300, 64)
        r = widgets.draw_button(self.surface, self.assets, rect, "Begin", font=self.font)
        self.assertEqual(r.centery, rect.centery + widgets.LABEL_DY)
        self.assertEqual(r.centerx, rect.centerx)
        self.assertLess(widgets.LABEL_DY, 0)
        self.assertGreaterEqual(-widgets.LABEL_DY, 5)          # the owner's 5..10 range
        self.assertLessEqual(-widgets.LABEL_DY, 10)

    def test_label_dy_overrides_the_shared_lift_and_keeps_the_press_shift(self):
        rect = pygame.Rect(10, 10, 300, 64)
        r = widgets.draw_button(self.surface, self.assets, rect, "Begin",
                                font=self.font, label_dy=-16)
        self.assertEqual(r.centery, rect.centery - 16)
        r = widgets.draw_button(self.surface, self.assets, rect, "Begin",
                                font=self.font, label_dy=-16, state="pressed")
        self.assertEqual(r.centery, rect.centery - 16 + widgets.PRESSED_DY)

    def test_default_label_colour_is_black(self):
        from game import config
        rect = pygame.Rect(10, 10, 300, 64)
        r = widgets.draw_button(self.surface, self.assets, rect, "Begin", font=self.font)
        black = tuple(config.COLOR_ON_BUTTON) + (255,)
        found = any(tuple(self.surface.get_at((x, y))) == black
                    for x in range(r.left, r.right) for y in range(r.top, r.bottom))
        self.assertTrue(found, "no black glyph pixel inside the label rect")

    def test_ribbon_label_is_black_and_not_lifted(self):
        from game import config
        rect = pygame.Rect(10, 10, 300, 64)
        r = widgets.draw_ribbon(self.surface, self.assets, rect, "Normal", font=self.font)
        self.assertEqual(r.center, rect.center)
        black = tuple(config.COLOR_ON_BUTTON) + (255,)
        self.assertTrue(any(tuple(self.surface.get_at((x, y))) == black
                            for x in range(r.left, r.right) for y in range(r.top, r.bottom)))

    def test_no_label_returns_none_and_still_paints(self):
        r = widgets.draw_button(self.surface, self.assets, pygame.Rect(10, 10, 300, 64), None)
        self.assertIsNone(r)
        self.assertGreater(self.surface.get_at((160, 40)).a, 0)

    def test_missing_sheet_falls_back_to_the_flat_button(self):
        with mock.patch.object(panels, "slice", return_value=None):
            r = widgets.draw_button(self.surface, self.assets, pygame.Rect(10, 10, 300, 64),
                                    "Begin", state="hover", font=self.font)
        self.assertIsNotNone(r)
        self.assertGreater(self.surface.get_at((160, 40)).a, 0)         # something drawn

    def test_art_actually_lands_on_the_surface(self):
        widgets.draw_button(self.surface, self.assets, pygame.Rect(10, 10, 300, 64), None)
        sheet = self.assets.image("btn_blue_wide")
        self.assertEqual(self.surface.get_at((10 + 20, 10 + 30)), sheet.get_at((20, 30)))


class RibbonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def setUp(self):
        reset_assets()
        panels.clear_cache()
        self.assets = Assets()
        self.surface = pygame.Surface((400, 100), pygame.SRCALPHA)
        self.font = fonts.heading(24)

    def test_colour_picks_the_sheet(self):
        for colour in widgets.RIBBON_COLOURS:
            with mock.patch.object(panels, "slice", wraps=panels.slice) as m:
                widgets.draw_ribbon(self.surface, self.assets, pygame.Rect(10, 10, 300, 64),
                                    "Normal", colour=colour, font=self.font)
            self.assertEqual(m.call_args[0][1], f"ribbon_{colour}")

    def test_unknown_colour_is_refused(self):
        with self.assertRaises(ValueError):
            widgets.draw_ribbon(self.surface, self.assets, pygame.Rect(0, 0, 100, 64),
                                "x", colour="green", font=self.font)

    def test_label_is_centred_and_fallback_draws(self):
        rect = pygame.Rect(10, 10, 300, 64)
        r = widgets.draw_ribbon(self.surface, self.assets, rect, "Fast",
                                colour="yellow", font=self.font)
        self.assertEqual(r.center, rect.center)
        with mock.patch.object(panels, "slice", return_value=None):
            r = widgets.draw_ribbon(self.surface, self.assets, rect, "Fast", font=self.font)
        self.assertEqual(r.center, rect.center)


class PressedOnTests(unittest.TestCase):
    def test_pressed_on_tracks_the_current_press(self):
        nav = MouseNav()
        nav.hits.add(pygame.Rect(0, 0, 100, 20), "a")
        self.assertIsNone(nav.pressed_on)
        nav.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1))
        self.assertEqual(nav.pressed_on, "a")
        nav.event(pygame.event.Event(pygame.MOUSEMOTION, pos=(500, 5), rel=(0, 0), buttons=(1, 0, 0)))
        self.assertEqual(nav.pressed_on, "a")                # still held
        nav.event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(500, 5), button=1))
        self.assertIsNone(nav.pressed_on)
        nav.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(500, 5), button=1))
        self.assertIsNone(nav.pressed_on)                    # press missed every rect


if __name__ == "__main__":
    unittest.main()
