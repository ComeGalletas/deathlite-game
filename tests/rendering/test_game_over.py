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

    def test_a_mouse_event_is_ignored(self):
        s = _state()
        s.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=1))
        self.assertIsNone(s.game.state_machine.changed_to)


if __name__ == "__main__":
    unittest.main()
