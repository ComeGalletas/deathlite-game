"""`spawn/locality.py`: current / heading / grace islands and their
hysteresis (spawn master S4)."""
import unittest

import pygame

from game.content import get_content
from spawn import Locality
from tests.spawn.fakehost import BRIDGE, FakeHost


def _loc() -> Locality:
    return Locality(get_content().spawn_tables.locality)


def _run(loc, host, seconds: float, dt: float = 0.1) -> list:
    """Advance `seconds`, returning the ticks on which the zone changed."""
    changed = []
    t = host.elapsed
    end = t + seconds
    while t < end:
        t += dt
        host.elapsed = t
        if loc.update(host, t):
            changed.append(t)
    return changed


class CurrentAndGraceTests(unittest.TestCase):
    def test_current_is_the_island_under_the_player(self):
        host, loc = FakeHost(), _loc()
        self.assertTrue(loc.update(host, 0.0))
        self.assertEqual(loc.current, 0)
        self.assertIsNone(loc.heading)
        self.assertIsNone(loc.grace_room)
        self.assertEqual(loc.active(), {0})
        self.assertEqual(loc.weights(), {0: 1.0})

    def test_leaving_an_island_keeps_it_in_grace_for_a_while(self):
        host, loc = FakeHost(), _loc()
        loc.update(host, 0.0)
        host.player = pygame.Vector2(3000, 2000)              # now on island 1
        host.elapsed = 10.0
        self.assertTrue(loc.update(host, 10.0))
        self.assertEqual((loc.current, loc.grace_room), (1, 0))
        self.assertEqual(loc.weights(), {0: loc.grace_weight, 1: 1.0})
        _run(loc, host, loc.grace - 0.5)
        self.assertEqual(loc.grace_room, 0)
        _run(loc, host, 1.0)
        self.assertIsNone(loc.grace_room)
        self.assertEqual(loc.active(), {1})

    def test_returning_to_the_grace_island_clears_grace(self):
        host, loc = FakeHost(), _loc()
        loc.update(host, 0.0)
        host.player = pygame.Vector2(3000, 2000)
        loc.update(host, 1.0)
        host.player = pygame.Vector2(1000, 2000)
        loc.update(host, 2.0)
        self.assertEqual((loc.current, loc.grace_room), (0, 1))   # island 1 is the grace now
        self.assertNotIn(0, (loc.grace_room,))

    def test_off_every_island_and_off_the_bridge_changes_nothing(self):
        host, loc = FakeHost(), _loc()
        loc.update(host, 0.0)
        host.player = pygame.Vector2(-50, -50)
        self.assertFalse(loc.update(host, 1.0))
        self.assertEqual(loc.current, 0)

    def test_no_island_yet_means_no_weights(self):
        host, loc = FakeHost(), _loc()
        host.player = pygame.Vector2(-50, -50)
        loc.update(host, 0.0)
        self.assertEqual(loc.weights(), {})
        self.assertEqual(loc.active(), set())


class HeadingTests(unittest.TestCase):
    def test_moving_toward_a_neighbour_sets_the_heading_after_the_dwell(self):
        host, loc = FakeHost(), _loc()
        host.heading = pygame.Vector2(1, 0)                   # east, toward island 1
        loc.update(host, 0.0)
        self.assertIsNone(loc.heading)
        _run(loc, host, loc.dwell - 0.15)
        self.assertIsNone(loc.heading)                        # not yet
        changed = _run(loc, host, 0.3)
        self.assertEqual(loc.heading, 1)
        self.assertEqual(len(changed), 1)
        self.assertEqual(loc.weights(), {0: 1.0, 1: loc.heading_weight})

    def test_moving_away_never_sets_a_heading(self):
        host, loc = FakeHost(), _loc()
        host.heading = pygame.Vector2(-1, 0)                  # west, away from island 1
        loc.update(host, 0.0)
        _run(loc, host, loc.dwell * 3)
        self.assertIsNone(loc.heading)

    def test_standing_still_clears_the_heading_after_the_dwell(self):
        host, loc = FakeHost(), _loc()
        host.heading = pygame.Vector2(1, 0)
        loc.update(host, 0.0)
        _run(loc, host, loc.dwell + 0.2)
        self.assertEqual(loc.heading, 1)
        host.heading = pygame.Vector2()
        _run(loc, host, loc.dwell - 0.15)
        self.assertEqual(loc.heading, 1)                      # hysteresis
        _run(loc, host, 0.3)
        self.assertIsNone(loc.heading)

    def test_strafing_across_the_threshold_does_not_flap(self):
        host, loc = FakeHost(), _loc()
        loc.update(host, 0.0)
        flips = 0
        t = 0.0
        for i in range(60):
            t += 0.1
            host.elapsed = t
            # alternate: toward island 1, then straight north (below `align`)
            host.heading = pygame.Vector2(1, 0) if i % 2 == 0 else pygame.Vector2(0, -1)
            if loc.update(host, t):
                flips += 1
        self.assertEqual(flips, 0)
        self.assertIsNone(loc.heading)

    def test_alignment_threshold_is_the_knob(self):
        host, loc = FakeHost(), _loc()
        # a little east of north: cos ~ 0.26 against island 1's direction
        host.heading = pygame.Vector2(0.26, -0.97)
        loc.update(host, 0.0)
        _run(loc, host, loc.dwell * 2)
        self.assertIsNone(loc.heading)
        loc.align = 0.2
        _run(loc, host, loc.dwell * 2)
        self.assertEqual(loc.heading, 1)


class BridgeTests(unittest.TestCase):
    def test_on_the_bridge_the_other_end_is_the_heading_at_once(self):
        host, loc = FakeHost(), _loc()
        loc.update(host, 0.0)
        host.player = pygame.Vector2(BRIDGE.center)
        self.assertTrue(loc.update(host, 0.5))
        self.assertEqual((loc.current, loc.heading), (0, 1))
        self.assertEqual(loc.weights(), {0: 1.0, 1: loc.heading_weight})
        # stepping off onto island 1: it becomes current, island 0 grace
        host.player = pygame.Vector2(2200, 2000)
        loc.update(host, 1.0)
        self.assertEqual((loc.current, loc.heading, loc.grace_room), (1, None, 0))

    def test_a_bridge_that_does_not_touch_the_current_island_is_ignored(self):
        host, loc = FakeHost(), _loc()
        host.player = pygame.Vector2(-50, -50)
        loc.update(host, 0.0)                                  # no current island
        host.player = pygame.Vector2(BRIDGE.center)
        self.assertFalse(loc.update(host, 1.0))
        self.assertIsNone(loc.heading)


if __name__ == "__main__":
    unittest.main()
