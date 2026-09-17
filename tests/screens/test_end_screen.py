"""`ui/end_screen.py`: the frame game over and victory now share.

The point of the split is that the frame decides *nothing*: it tracks the
selection and the mouse, and `handle_event` hands back the id of the button to
fire so the state does the acting. So these tests never touch a state -- they
assert the ids that come back, which is the whole contract between the two.

`tests/screens/test_game_over.py` and `test_victory.py` cover the two states'
wiring on top of this.
"""
import itertools
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from ui import end_screen
from ui.end_screen import Button, EndScreen

BUTTONS = (
    Button("first", "First", "ENTER"),
    Button("middle", "Middle", "M", pygame.K_m),
    Button("last", "Last", "ESC", pygame.K_ESCAPE, variant="danger"),
)
STATS = {"character": "Aegis", "difficulty": "fast", "seed": 35,
         "time": 305.5, "level": 12, "kills": 240}


def _key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def _screen(buttons=BUTTONS, stats=None, lock=0.0):
    """`lock=0` by default: every test below is about the frame's input
    contract, which is what the screen does *after* the input lock has run
    out. `InputLockTests` is the one that asks for the lock."""
    return EndScreen(dict(STATS if stats is None else stats), title="Title",
                     title_colour=(255, 255, 255), backdrop=(10, 10, 10),
                     buttons=buttons, subtitle="sub", lock=lock)


class InputLockTests(unittest.TestCase):
    """The lock the run-end screens get so the keypress or click already in
    flight when the run ended cannot dismiss the summary (owner, 2026-09-16;
    `documentation/journals/end_screen_input_lock_journal.md`)."""

    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        pygame.font.init()

    def _locked(self, **kw):
        return _screen(lock=config.END_SCREEN_INPUT_LOCK, **kw)

    def test_the_shipped_screen_starts_locked_for_the_configured_time(self):
        s = _screen(lock=None)
        self.assertGreater(config.END_SCREEN_INPUT_LOCK, 0.0)
        self.assertEqual(s.lock_remaining, config.END_SCREEN_INPUT_LOCK)
        self.assertTrue(s.locked)

    def test_confirm_and_the_direct_keys_do_nothing_while_locked(self):
        s = self._locked()
        for k in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_m, pygame.K_ESCAPE):
            self.assertIsNone(s.handle_event(_key(k)), pygame.key.name(k))

    def test_the_cursor_does_not_move_while_locked(self):
        s = self._locked()
        s.handle_event(_key(pygame.K_RIGHT))
        s.handle_event(_key(pygame.K_d))
        self.assertEqual(s.sel, 0)

    def test_the_lock_runs_out_on_ticks_and_the_keys_come_back(self):
        s = self._locked()
        s.tick(config.END_SCREEN_INPUT_LOCK / 2)
        self.assertTrue(s.locked)
        self.assertIsNone(s.handle_event(_key(pygame.K_RETURN)))
        s.tick(config.END_SCREEN_INPUT_LOCK)
        self.assertFalse(s.locked)
        self.assertEqual(s.lock_remaining, 0.0)      # never goes negative
        self.assertEqual(s.handle_event(_key(pygame.K_RETURN)), "first")

    def test_a_press_made_while_locked_does_not_fire_when_the_lock_lifts(self):
        """The reason the press is dropped rather than deferred: `MouseNav`
        never records what it landed on, so the release matches nothing."""
        s = self._locked()
        s.draw(pygame.Surface((1600, 900)), None)
        pos = s.mouse.hits.rect_of(0).center
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        s.tick(config.END_SCREEN_INPUT_LOCK)
        self.assertFalse(s.locked)
        self.assertIsNone(s.mouse.pressed_on)
        self.assertIsNone(s.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)))

    def test_a_whole_click_while_locked_fires_nothing(self):
        s = self._locked()
        s.draw(pygame.Surface((1600, 900)), None)
        pos = s.mouse.hits.rect_of(1).center
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        self.assertIsNone(s.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)))

    def test_hover_still_tracks_while_locked(self):
        """Motion is the one input let through: it can only move the
        highlight, and without it the screen looks frozen for 1.5 s."""
        s = self._locked()
        s.draw(pygame.Surface((1600, 900)), None)
        pos = s.mouse.hits.rect_of(2).center
        s.handle_event(pygame.event.Event(
            pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
        self.assertEqual(s.sel, 2)

    def test_a_zero_lock_is_open_from_the_first_frame(self):
        s = _screen(lock=0.0)
        self.assertFalse(s.locked)
        self.assertEqual(s.handle_event(_key(pygame.K_RETURN)), "first")


class SubtitleTests(unittest.TestCase):
    def test_it_reads_hero_difficulty_and_seed_from_the_stats(self):
        sub = end_screen.run_subtitle(STATS)
        self.assertIn("Aegis", sub)
        self.assertIn(config.DIFFICULTY_LABELS["fast"], sub)
        self.assertIn("seed 35", sub)

    def test_an_empty_run_still_yields_a_line(self):
        self.assertTrue(end_screen.run_subtitle({}))

    def test_a_seed_of_zero_is_still_shown(self):
        # `if stats.get("seed")` would drop seed 0; the check is against None.
        self.assertIn("seed 0", end_screen.run_subtitle({"seed": 0}))


class KeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        pygame.font.init()

    def test_confirm_fires_whatever_is_selected(self):
        s = _screen()
        self.assertEqual(s.handle_event(_key(pygame.K_RETURN)), "first")
        s.sel = 2
        self.assertEqual(s.handle_event(_key(pygame.K_SPACE)), "last")

    def test_a_direct_key_fires_its_button_whatever_is_selected(self):
        s = _screen()
        self.assertEqual(s.handle_event(_key(pygame.K_m)), "middle")
        self.assertEqual(s.sel, 0, "a direct key should not move the cursor")

    def test_the_cursor_wraps_both_ways(self):
        s = _screen()
        self.assertIsNone(s.handle_event(_key(pygame.K_LEFT)))
        self.assertEqual(s.sel, len(BUTTONS) - 1)
        self.assertIsNone(s.handle_event(_key(pygame.K_RIGHT)))
        self.assertEqual(s.sel, 0)

    def test_a_and_d_move_the_cursor_too(self):
        s = _screen()
        s.handle_event(_key(pygame.K_d))
        self.assertEqual(s.sel, 1)
        s.handle_event(_key(pygame.K_a))
        self.assertEqual(s.sel, 0)

    def test_an_unbound_key_does_nothing(self):
        s = _screen()
        self.assertIsNone(s.handle_event(_key(pygame.K_f)))
        self.assertEqual(s.sel, 0)

    def test_a_key_release_is_not_a_press(self):
        # The release of the key that ended the run must not skip the summary.
        s = _screen()
        self.assertIsNone(s.handle_event(
            pygame.event.Event(pygame.KEYUP, key=pygame.K_RETURN)))

    def test_a_direct_key_wins_over_the_cursor_letters(self):
        """A button bound to A or D fires instead of moving the selection --
        the reason direct keys are checked first."""
        buttons = (Button("first", "First", "ENTER"),
                   Button("away", "Away", "A", pygame.K_a))
        s = _screen(buttons)
        self.assertEqual(s.handle_event(_key(pygame.K_a)), "away")
        self.assertEqual(s.sel, 0)


class MouseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        pygame.font.init()

    def _drawn(self):
        s = _screen()
        s.draw(pygame.Surface((1600, 900)), None)   # registers the rects
        return s

    def _at(self, s, i):
        return s.mouse.hits.rect_of(i).center

    def test_drawing_registers_one_rect_per_button_left_to_right(self):
        s = self._drawn()
        self.assertEqual(len(s.mouse.hits), len(BUTTONS))
        rects = [s.mouse.hits.rect_of(i) for i in range(len(BUTTONS))]
        self.assertTrue(all(r is not None for r in rects))
        for a, b in itertools.pairwise(rects):
            self.assertLess(a.right, b.left)

    def test_hover_selects_without_firing(self):
        s = self._drawn()
        out = s.handle_event(pygame.event.Event(
            pygame.MOUSEMOTION, pos=self._at(s, 2), rel=(0, 0), buttons=(0, 0, 0)))
        self.assertIsNone(out)
        self.assertEqual(s.sel, 2)

    def test_a_press_and_release_on_one_button_fires_it(self):
        s = self._drawn()
        pos = self._at(s, 1)
        self.assertIsNone(s.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, pos=pos, button=1)))
        self.assertEqual(s.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONUP, pos=pos, button=1)), "middle")

    def test_a_press_released_on_another_button_fires_nothing(self):
        s = self._drawn()
        s.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, pos=self._at(s, 0), button=1))
        self.assertIsNone(s.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONUP, pos=self._at(s, 2), button=1)))

    def test_a_press_off_every_button_is_ignored(self):
        s = self._drawn()
        self.assertIsNone(s.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=1)))

    def test_the_row_is_centred_on_the_surface(self):
        s = self._drawn()
        rects = [s.mouse.hits.rect_of(i) for i in range(len(BUTTONS))]
        span = rects[-1].right - rects[0].left
        self.assertAlmostEqual(rects[0].left + span // 2, 1600 // 2, delta=2)


class DrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        pygame.font.init()

    def _lit(self, surface, rect, backdrop):
        return sum(1 for y in range(rect.top, rect.bottom, 3)
                   for x in range(rect.left, rect.right, 3)
                   if surface.get_at((x, y))[:3] != backdrop)

    def test_it_paints_its_own_backdrop_title_and_panel(self):
        backdrop = (10, 10, 10)
        s = _screen()
        surface = pygame.Surface((1600, 900))
        surface.fill((200, 0, 200))          # nothing of this may survive
        s.draw(surface, None)
        self.assertEqual(surface.get_at((4, 4))[:3], backdrop)
        for name, band in (
                ("title", pygame.Rect(600, 40, 400, 60)),
                ("subtitle", pygame.Rect(600, 100, 400, 36)),
                ("panel", pygame.Rect(60, end_screen.PANEL_TOP, 1480, 200)),
                ("buttons", pygame.Rect(60, end_screen.BTN_CY - 32, 1480, 64))):
            self.assertGreater(self._lit(surface, band, backdrop), 0,
                               f"nothing drawn in the {name} band")

    def test_an_empty_stats_dict_still_draws(self):
        s = EndScreen({}, title="T", title_colour=(255, 255, 255),
                      backdrop=(0, 0, 0), buttons=BUTTONS)
        s.draw(pygame.Surface((1600, 900)), None)     # must not raise

    def test_no_subtitle_means_no_subtitle_band(self):
        s = EndScreen(dict(STATS), title="T", title_colour=(255, 255, 255),
                      backdrop=(10, 10, 10), buttons=BUTTONS, subtitle="")
        surface = pygame.Surface((1600, 900))
        s.draw(surface, None)
        self.assertEqual(
            self._lit(surface, pygame.Rect(600, 104, 400, 28), (10, 10, 10)), 0)
