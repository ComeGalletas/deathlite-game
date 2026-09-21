"""`ui.menu_nav.MenuNav`: the one copy of the menus' cursor and hover rules.

Pure -- synthetic events over a `HitMap`, no window. The screens' own tests
stay as the behaviour guard for each adopter (structure review, B).
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from ui.menu_nav import MenuNav
from ui.mouse import MouseNav


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def keyup(k):
    return pygame.event.Event(pygame.KEYUP, key=k)


def motion(pos):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0))


def down(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def up(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=button)


class VerticalListTests(unittest.TestCase):
    def setUp(self):
        self.nav = MenuNav()

    def test_up_and_down_move_and_wrap_on_both_keysets(self):
        self.assertEqual(self.nav.event(key(pygame.K_DOWN), index=0, count=3), ("move", 1))
        self.assertEqual(self.nav.event(key(pygame.K_s), index=2, count=3), ("move", 0))
        self.assertEqual(self.nav.event(key(pygame.K_UP), index=0, count=3), ("move", 2))
        self.assertEqual(self.nav.event(key(pygame.K_w), index=1, count=3), ("move", 0))

    def test_enter_and_space_activate_the_current_index(self):
        self.assertEqual(self.nav.event(key(pygame.K_RETURN), index=2, count=3), ("activate", 2))
        self.assertEqual(self.nav.event(key(pygame.K_SPACE), index=1, count=3), ("activate", 1))

    def test_left_and_right_are_the_cross_axis(self):
        self.assertEqual(self.nav.event(key(pygame.K_LEFT), index=0, count=3), ("axis", -1))
        self.assertEqual(self.nav.event(key(pygame.K_d), index=0, count=3), ("axis", +1))

    def test_escape_is_back_and_other_keys_are_nothing(self):
        self.assertEqual(self.nav.event(key(pygame.K_ESCAPE)), ("back", None))
        self.assertIsNone(self.nav.event(key(pygame.K_q), index=0, count=3))
        self.assertIsNone(self.nav.event(key(pygame.K_1), index=0, count=3))  # numbers off
        self.assertIsNone(self.nav.event(keyup(pygame.K_RETURN), index=0, count=3))

    def test_an_empty_list_moves_nowhere(self):
        self.assertEqual(self.nav.event(key(pygame.K_DOWN), index=0, count=0), ("move", 0))


class SkipAndClampTests(unittest.TestCase):
    def test_skipped_rows_are_passed_over_in_either_direction(self):
        nav = MenuNav()
        greyed = {1, 2}.__contains__
        self.assertEqual(nav.step(0, 4, +1, greyed), 3)
        self.assertEqual(nav.step(3, 4, -1, greyed), 0)
        self.assertEqual(nav.step(3, 4, +1, greyed), 0)          # wraps past them

    def test_every_other_row_skipped_stays_put(self):
        nav = MenuNav()
        self.assertEqual(nav.step(0, 3, +1, lambda i: i != 0), 0)

    def test_clamped_list_stops_at_the_ends(self):
        nav = MenuNav(wrap=False)
        self.assertEqual(nav.event(key(pygame.K_UP), index=0, count=3), ("move", 0))
        self.assertEqual(nav.event(key(pygame.K_DOWN), index=2, count=3), ("move", 2))
        self.assertEqual(nav.event(key(pygame.K_DOWN), index=0, count=3), ("move", 1))

    def test_clamped_list_with_a_skipped_end_stays_put(self):
        nav = MenuNav(wrap=False)
        self.assertEqual(nav.step(1, 3, +1, {2}.__contains__), 1)


class HorizontalListTests(unittest.TestCase):
    def setUp(self):
        self.nav = MenuNav(axis="h", numbers=True)

    def test_left_and_right_move_and_up_down_is_the_axis(self):
        self.assertEqual(self.nav.event(key(pygame.K_RIGHT), index=0, count=3), ("move", 1))
        self.assertEqual(self.nav.event(key(pygame.K_a), index=0, count=3), ("move", 2))
        self.assertEqual(self.nav.event(key(pygame.K_UP), index=0, count=3), ("axis", -1))
        self.assertEqual(self.nav.event(key(pygame.K_s), index=0, count=3), ("axis", +1))

    def test_number_keys_are_zero_based_and_bounded_by_count(self):
        self.assertEqual(self.nav.event(key(pygame.K_1), index=0, count=3), ("number", 0))
        self.assertEqual(self.nav.event(key(pygame.K_3), index=0, count=3), ("number", 2))
        self.assertIsNone(self.nav.event(key(pygame.K_4), index=0, count=3))
        self.assertIsNone(self.nav.event(key(pygame.K_1), index=0, count=0))


class KeysetTests(unittest.TestCase):
    def test_back_keys_and_confirm_keys_are_the_screens_to_name(self):
        nav = MenuNav(back_keys=(pygame.K_ESCAPE, pygame.K_p, pygame.K_BACKQUOTE),
                      confirm_keys=(pygame.K_e,))
        self.assertEqual(nav.event(key(pygame.K_p)), ("back", None))
        self.assertEqual(nav.event(key(pygame.K_BACKQUOTE)), ("back", None))
        self.assertEqual(nav.event(key(pygame.K_e), index=1, count=2), ("activate", 1))
        self.assertIsNone(nav.event(key(pygame.K_RETURN), index=1, count=2))

    def test_no_back_keys_means_escape_is_nothing(self):
        nav = MenuNav(back_keys=())
        self.assertIsNone(nav.event(key(pygame.K_ESCAPE)))

    def test_axis_must_be_v_or_h(self):
        with self.assertRaises(ValueError):
            MenuNav(axis="x")


class MouseTests(unittest.TestCase):
    def setUp(self):
        self.nav = MenuNav(right_click_back=True)
        self.nav.hits.add(pygame.Rect(0, 0, 100, 20), 0)
        self.nav.hits.add(pygame.Rect(0, 30, 100, 20), ("row", 1))

    def test_hover_is_a_move_to_the_registered_key(self):
        self.assertEqual(self.nav.event(motion((10, 5)), index=5, count=9), ("move", 0))
        self.assertEqual(self.nav.event(motion((10, 35))), ("move", ("row", 1)))
        self.assertIsNone(self.nav.event(motion((10, 25))))          # between rows

    def test_a_click_is_press_and_release_on_one_rect_reported_on_release(self):
        self.assertIsNone(self.nav.event(down((10, 5))))
        self.assertEqual(self.nav.event(up((90, 15))), ("activate", 0))
        self.nav.event(down((10, 5)))
        self.assertIsNone(self.nav.event(up((10, 35))))              # slid off
        self.assertIsNone(self.nav.event(up((10, 5))))               # no press stored

    def test_right_click_is_back_only_when_asked(self):
        self.assertEqual(self.nav.event(down((10, 5), button=3)), ("back", None))
        self.assertIsNone(MenuNav().event(down((10, 5), button=3)))

    def test_the_wheel_is_nothing_here(self):
        wheel = pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1, flipped=False)
        self.assertIsNone(self.nav.event(wheel))

    def test_a_screen_can_hand_in_the_mouse_it_already_owns(self):
        mouse = MouseNav()
        nav = MenuNav(mouse)
        self.assertIs(nav.mouse, mouse)
        self.assertIs(nav.hits, mouse.hits)
        mouse.hits.add(pygame.Rect(0, 0, 10, 10), "k")
        nav.event(down((5, 5)))
        self.assertEqual(mouse.pressed_on, "k")                     # the button paints sunk


if __name__ == "__main__":
    unittest.main()
