"""ui/keycap.py: keyboard keys as pixel-art keycaps (journal:
key_icons_journal.md). The label rides the face -- it sits lower on the
pressed frame -- with a text-only fallback when the art is missing."""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config, fonts
from game.assets import Assets, reset_assets
from ui import keycap


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


class LabelTests(unittest.TestCase):
    def test_letters_are_upper_case(self):
        self.assertEqual(keycap.label_for(pygame.K_e), "E")
        self.assertEqual(keycap.label_for(config.KEY_INTERACT), "E")

    def test_long_names_are_what_a_keyboard_prints(self):
        self.assertEqual(keycap.label_for(pygame.K_SPACE), "SPACE")
        self.assertEqual(keycap.label_for(pygame.K_TAB), "TAB")
        self.assertEqual(keycap.label_for(pygame.K_LSHIFT), "SHIFT")
        self.assertEqual(keycap.label_for(pygame.K_ESCAPE), "ESC")


class GeometryTests(unittest.TestCase):
    """Pure placement, no drawing."""

    def test_cap_frame_puts_the_raised_face_on_the_given_point(self):
        r = keycap.cap_rect((100, 200), 32)
        self.assertEqual(r.size, (32, 32))
        self.assertEqual(r.centerx, 100)
        self.assertEqual(r.top, 200 - 12)            # FACE_Y raised 24 * 0.5

    def test_label_rides_the_face(self):
        raised = keycap.label_center((100, 200), "raised", 32)
        pressed = keycap.label_center((100, 200), "pressed", 32)
        self.assertEqual(raised, (100, 200))
        self.assertEqual(pressed[0], raised[0])
        self.assertEqual(pressed[1] - raised[1], 2)   # 4 art px at x0.5

    def test_label_shift_scales_with_the_interface(self):
        with mock.patch.object(config, "RENDER_SCALE", 1.6):
            r = keycap.cap_rect((100, 200), 32)
            raised = keycap.label_center((100, 200), "raised", 32)
            pressed = keycap.label_center((100, 200), "pressed", 32)
        self.assertEqual(r.width, 51)
        self.assertEqual(raised[1], 200)
        self.assertEqual(pressed[1] - raised[1], 3)   # round(4 * 51 / 64)

    def test_unknown_state_is_refused(self):
        with self.assertRaises(ValueError):
            keycap.label_center((0, 0), "hover")
        with self.assertRaises(ValueError):
            keycap.keycap_sheet("blue", "hover")

    def test_state_picks_the_sheet(self):
        self.assertEqual(keycap.keycap_sheet("blue", "raised"), "keycap_blue")
        self.assertEqual(keycap.keycap_sheet("blue", "pressed"), "keycap_blue_pressed")


class _SpyFont:
    """A real font that remembers the colour of its last render
    (`pygame.font.Font.render` cannot be patched on the type)."""

    def __init__(self, font):
        self.font = font
        self.colours = []

    def render(self, text, aa, colour):
        self.colours.append(tuple(colour))
        return self.font.render(text, aa, colour)


class DrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def setUp(self):
        reset_assets()
        self.assets = Assets()
        self.surface = pygame.Surface((400, 120), pygame.SRCALPHA)
        self.font = fonts.heading(20)

    def test_both_frames_load_at_cap_size(self):
        for state in keycap.STATES:
            art = self.assets.image(keycap.keycap_sheet("blue", state), size=(32, 32))
            self.assertIsNotNone(art, state)
            self.assertEqual(art.get_size(), (32, 32))

    def test_art_lands_on_the_surface(self):
        r = keycap.draw_keycap(self.surface, self.assets, (100, 60), "E")
        sheet = self.assets.image("keycap_blue", size=r.size)
        self.assertEqual(self.surface.get_at((r.left + 4, r.top + 4)), sheet.get_at((4, 4)))

    def test_pressed_draws_the_pressed_frame_in_the_same_rect(self):
        a = keycap.draw_keycap(self.surface, self.assets, (100, 60), "E", state="raised")
        b = keycap.draw_keycap(self.surface, self.assets, (100, 60), "E", state="pressed")
        self.assertEqual(a, b)

    def test_label_is_black_on_the_art(self):
        spy = _SpyFont(self.font)
        keycap.draw_keycap(self.surface, self.assets, (100, 60), "E", font=spy)
        self.assertEqual(spy.colours, [tuple(config.COLOR_ON_BUTTON)])

    def test_missing_art_draws_the_letter_in_the_prompt_colour(self):
        spy = _SpyFont(self.font)
        with mock.patch.object(Assets, "image", return_value=None):
            r = keycap.draw_keycap(self.surface, self.assets, (100, 60), "E",
                                   font=spy, fallback_colour=(1, 2, 3))
        self.assertEqual(spy.colours, [(1, 2, 3)])
        self.assertEqual(r.centerx, 100)
        self.assertGreater(self.surface.get_at((100, 60)).a, 0)         # ink under the point


if __name__ == "__main__":
    unittest.main()
