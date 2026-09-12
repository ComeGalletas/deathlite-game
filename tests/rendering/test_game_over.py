"""`game/states/game_over_state.py`: the run summary shown after a death.

The state had no coverage at all -- the only thing the suite said about it was
that a *developer* run never opens one (`tests/core/test_dev_mode.py`). What is
pinned here is the readout a real run produces: the summary survives a run that
banked nothing (the per-minute and dps rates divide by the survival time, which
is zero on a death at t=0), it reports what the run actually did, and the three
keys leave for the three places the hint line advertises.

A fake game rather than a booted one: the state only needs somewhere to record
the transition, and the states it changes to take their `game` and do the rest
of their work in `enter`, which a recorder never calls. That keeps this in the
`unit` tier.
"""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.states.character_select_state import CharacterSelectState
from game.states.game_over_state import GameOverState
from game.states.menu_state import MenuState
from game.states.meta_state import MetaState


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


def _key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


FULL_STATS = {
    "character": "Aegis",
    "time": 305.5,
    "level": 12,
    "kills": 240,
    "damage_dealt": 18400.0,
    "currency": 57,
    "blessings": {"sword_edge": 3, "bow_volley": 2},
    "dropped_items": ["ring", "cloak"],
    "weapons": [("Sword", 4), ("Bow", 2)],
}


class _Recorder:
    """A state machine that remembers what it was asked to change to without
    entering it."""

    def __init__(self):
        self.changed_to = None

    def change(self, state, **kwargs):
        self.changed_to = state


def _state(stats=None):
    game = SimpleNamespace(state_machine=_Recorder())
    s = GameOverState(game)
    s.enter(stats=stats)
    return s


class SummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def _drawn(self, stats):
        """The state and the surface it painted itself onto."""
        s = _state(stats)
        surface = pygame.Surface((1600, 900))
        s.draw(surface)
        return s, surface

    def test_a_death_at_zero_seconds_still_draws(self):
        """`kills / t` and `damage / t` are per-minute and per-second rates, so
        a run that ended before the clock moved divides by zero unless the
        state floors it."""
        s, surface = self._drawn({"time": 0, "kills": 0, "damage_dealt": 0})
        self.assertEqual(surface.get_at((4, 4))[:3], (22, 10, 12))

    def test_no_stats_at_all_draws(self):
        """`enter()` with nothing -- every field falls back to its default."""
        s, surface = self._drawn(None)
        self.assertEqual(s.stats, {})
        self.assertEqual(surface.get_at((4, 4))[:3], (22, 10, 12))

    def test_a_full_run_draws_something_over_the_backdrop(self):
        _s, surface = self._drawn(FULL_STATS)
        w, h = surface.get_size()
        lit = sum(1 for x in range(0, w, 8) for y in range(0, h, 8)
                  if surface.get_at((x, y))[:3] != (22, 10, 12))
        self.assertGreater(lit, 50, "neither the title nor the readout was drawn")

    def test_the_stats_are_kept_as_given(self):
        s = _state(FULL_STATS)
        self.assertEqual(s.stats["kills"], 240)
        self.assertEqual(s.stats["weapons"], [("Sword", 4), ("Bow", 2)])


class ExitKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def _pressed(self, key, stats=None):
        s = _state(stats)
        s.handle_event(_key(key))
        return s.game.state_machine.changed_to

    def test_enter_starts_another_run(self):
        self.assertIsInstance(self._pressed(pygame.K_RETURN), CharacterSelectState)

    def test_space_starts_another_run(self):
        self.assertIsInstance(self._pressed(pygame.K_SPACE), CharacterSelectState)

    def test_s_opens_the_sanctuary(self):
        self.assertIsInstance(self._pressed(pygame.K_s), MetaState)

    def test_escape_goes_back_to_the_menu(self):
        self.assertIsInstance(self._pressed(pygame.K_ESCAPE), MenuState)

    def test_any_other_key_stays_on_the_summary(self):
        self.assertIsNone(self._pressed(pygame.K_f))

    def test_a_key_release_is_not_a_press(self):
        """Only KEYDOWN leaves -- otherwise the release of the key that killed
        the run would skip the summary before it was read."""
        s = _state()
        s.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_RETURN))
        self.assertIsNone(s.game.state_machine.changed_to)

    def test_a_mouse_press_off_every_button_is_ignored(self):
        s = _state()
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=1))
        self.assertIsNone(s.game.state_machine.changed_to)


# The summary the ledger now builds (`PlayingState._end_run`): the rows the
# three columns draw. `FULL_STATS` above is the older shape, kept because a
# screen fed it must still draw.
LEDGER_STATS = dict(
    FULL_STATS,
    gold=41, seed=911, difficulty="fast",
    dropped_items=[{"name": "Ring of Ash", "rarity": "rare", "slot": "ring", "level": 3},
                   {"name": "Cloak", "rarity": "common", "slot": "body", "level": 1}],
    weapon_rows=[{"id": "sword", "name": "Sword", "level": 4, "damage": 12000.0,
                  "share": 0.65, "dps": 40.0},
                 {"id": "bow", "name": "Bow", "level": 2, "damage": 5000.0,
                  "share": 0.27, "dps": 25.0}],
    other_rows=[{"id": "fire_nova", "name": "Fire Nova", "level": None,
                 "damage": 1400.0, "share": 0.08, "dps": 6.0}],
    kill_rows=[("Husk", 150), ("Skitter", 80), ("Brute", 9), ("The Warden", 1)],
    blessing_rows=[("Keen Edge", 3), ("Volley", 2)],
    damage_by_source={"sword": 12000.0, "bow": 5000.0, "fire_nova": 1400.0},
)


class LedgerSummaryTests(unittest.TestCase):
    """The new summary shape draws, and the columns land where the layout
    says: the ribbons over each column, the buttons in a row above the hint."""

    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def _drawn(self, stats):
        s = _state(stats)
        surface = pygame.Surface((1600, 900))
        s.draw(surface)
        return s, surface

    def _lit(self, surface, rect):
        return sum(1 for x in range(rect.left, rect.right, 4)
                   for y in range(rect.top, rect.bottom, 4)
                   if surface.get_at((x, y))[:3] != (22, 10, 12))

    def test_the_ledger_summary_draws_every_column(self):
        _s, surface = self._drawn(LEDGER_STATS)
        # Each column's content area, below its ribbon.
        for left in (60, 560, 1060):
            self.assertGreater(self._lit(surface, pygame.Rect(left, 240, 480, 500)), 100,
                               f"the column at x={left} is empty")

    def test_the_older_summary_still_draws_every_column(self):
        _s, surface = self._drawn(FULL_STATS)
        for left in (60, 560, 1060):
            self.assertGreater(self._lit(surface, pygame.Rect(left, 240, 480, 500)), 60)

    def test_long_lists_are_cut_not_overflowed(self):
        """Twenty items, twenty enemy types, four weapons, twelve procs and
        twenty blessings must stay inside their columns: nothing may be
        painted over the button row."""
        stats = dict(LEDGER_STATS,
                     dropped_items=[{"name": f"Trinket {i}", "rarity": "common"}
                                    for i in range(20)],
                     weapon_rows=[{"id": f"w{i}", "name": f"Weapon {i}", "level": 1,
                                   "damage": 100.0, "share": 0.1, "dps": 1.0}
                                  for i in range(4)],
                     kill_rows=[(f"Type {i}", 20 - i) for i in range(20)],
                     blessing_rows=[(f"Blessing {i}", 1) for i in range(20)],
                     other_rows=[{"id": f"p{i}", "name": f"Proc {i}", "level": None,
                                  "damage": 10.0, "share": 0.01, "dps": 1.0}
                                 for i in range(12)])
        _s, surface = self._drawn(stats)
        # The strip between the columns' bottom and the buttons' top.
        self.assertEqual(self._lit(surface, pygame.Rect(0, 764, 1600, 14)), 0)

    def test_three_buttons_are_registered_for_the_mouse(self):
        s, _surface = self._drawn(LEDGER_STATS)
        self.assertEqual(len(s._mouse.hits), 3)
        rects = [s._mouse.hits.rect_of(i) for i in range(3)]
        self.assertTrue(all(r is not None for r in rects))
        self.assertTrue(rects[0].right < rects[1].left < rects[1].right < rects[2].left)


class MouseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def _ready(self):
        s = _state(LEDGER_STATS)
        s.draw(pygame.Surface((1600, 900)))     # registers the button rects
        return s

    def _click(self, s, i):
        pos = s._mouse.hits.rect_of(i).center
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))
        return s.game.state_machine.changed_to

    def test_hover_selects(self):
        s = self._ready()
        pos = s._mouse.hits.rect_of(2).center
        s.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
        self.assertEqual(s.sel, 2)
        self.assertIsNone(s.game.state_machine.changed_to)

    def test_clicking_new_run(self):
        self.assertIsInstance(self._click(self._ready(), 0), CharacterSelectState)

    def test_clicking_sanctuary(self):
        self.assertIsInstance(self._click(self._ready(), 1), MetaState)

    def test_clicking_main_menu(self):
        self.assertIsInstance(self._click(self._ready(), 2), MenuState)

    def test_a_press_on_one_button_released_on_another_does_nothing(self):
        s = self._ready()
        a = s._mouse.hits.rect_of(0).center
        b = s._mouse.hits.rect_of(2).center
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=a, button=1))
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=b, button=1))
        self.assertIsNone(s.game.state_machine.changed_to)


class CursorKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def test_right_then_enter_opens_the_sanctuary(self):
        s = _state()
        s.handle_event(_key(pygame.K_RIGHT))
        self.assertEqual(s.sel, 1)
        s.handle_event(_key(pygame.K_RETURN))
        self.assertIsInstance(s.game.state_machine.changed_to, MetaState)

    def test_left_wraps_to_the_menu_button(self):
        s = _state()
        s.handle_event(_key(pygame.K_a))
        self.assertEqual(s.sel, 2)
        s.handle_event(_key(pygame.K_SPACE))
        self.assertIsInstance(s.game.state_machine.changed_to, MenuState)

    def test_s_opens_the_sanctuary_whatever_is_selected(self):
        s = _state()
        s.handle_event(_key(pygame.K_d))
        s.handle_event(_key(pygame.K_d))
        s.handle_event(_key(pygame.K_s))
        self.assertIsInstance(s.game.state_machine.changed_to, MetaState)


if __name__ == "__main__":
    unittest.main()
