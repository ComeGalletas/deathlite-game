"""SYS-009: `TimedVisual`, the one entry type behind `_explosions` and
`_death_fx`. Pure: a stand-in animator, no display."""
import unittest

import pygame

from game.states.playing.core.timed_visual import TimedVisual


class _Anim:
    def __init__(self, length):
        self.t, self.length = 0.0, length

    def update(self, dt):
        self.t += dt

    @property
    def finished(self):
        return self.t >= self.length


class TimedVisualTests(unittest.TestCase):
    def test_a_fixed_duration_runs_out_on_its_clock(self):
        tv = TimedVisual(pygame.Vector2(1, 2), radius=40.0, dur=0.35)
        tv.update(0.2)
        self.assertFalse(tv.finished)
        self.assertAlmostEqual(tv.progress, 0.2 / 0.35)
        tv.update(0.15)
        self.assertTrue(tv.finished)
        self.assertEqual(tv.progress, 1.0)

    def test_without_a_duration_it_lives_as_long_as_its_animation(self):
        anim = _Anim(0.5)
        tv = TimedVisual(pygame.Vector2(), anim=anim)
        tv.update(0.3)
        self.assertEqual(anim.t, 0.3)             # the animation is stepped too
        self.assertFalse(tv.finished)
        tv.update(0.3)
        self.assertTrue(tv.finished)

    def test_entries_compare_by_identity(self):
        """The sweeps and the tests find an entry as the object it is: two
        blasts at the same spot and size are still two blasts."""
        a = TimedVisual(pygame.Vector2(5, 5), radius=30.0, dur=0.3)
        b = TimedVisual(pygame.Vector2(5, 5), radius=30.0, dur=0.3)
        self.assertNotEqual(a, b)
        self.assertEqual([a, b].index(b), 1)


if __name__ == "__main__":
    unittest.main()
