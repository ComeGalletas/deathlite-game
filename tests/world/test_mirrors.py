"""Rules that are implemented twice on purpose agree everywhere.

The runtime cannot import the generator and the generator cannot afford the
runtime's indirection, so a few rules live in two places and each is
documented as a mirror of the other. Three bugs in the terrace-margin
milestone came from such pairs drifting, and every one was found by
measurement rather than by a test: the suites checked each half on its own,
never that the two agree *in general*.

Two pairs stopped existing instead of being tested: the floor test and the
terrace-margin test are one function each in `world/rules/floor.py`, read by
the collider and the navigation grid alike; `FloorTests` pins that they stay
one. Two more pairs are covered in `test_elevation`: `walk_links` against
`can_cross` (`CanCrossTests`) and `can_step` against the baked `step_mask`
(`NavTests`). The clearance pair below is a real mirror still.

Each test here was seen red once, by breaking one half on purpose, before it
was trusted.
"""
import random
import unittest

from game import config
from tests import worlds as W
from world.gen import repair
from world.map import GameMap
from world.pathfinding import NavGrid, _point_inset_ok, _point_on_floor
from world.rules import floor, inset as terrain_inset


class FloorTests(unittest.TestCase):
    def test_the_floor_and_margin_tests_have_one_body(self):
        self.assertIs(_point_on_floor, floor.point_on_floor)
        self.assertIs(_point_inset_ok, floor.inset_ok)
        # ... and the collider reads the same one, not a copy of its own.
        gm = W.game_map(W.SEEDS[0])
        rng = random.Random(3)
        b = gm.layout.bounds
        margin = terrain_inset.body_inset()
        for _ in range(500):
            x, y = rng.uniform(b.left, b.right), rng.uniform(b.top, b.bottom)
            self.assertEqual(gm._point_ok(x, y), floor.point_on_floor(gm.layout, x, y))
            self.assertEqual(gm.inset_ok(x, y), floor.inset_ok(gm.layout, x, y, margin))

    def test_the_layoutless_map_keeps_its_one_big_room(self):
        gm = GameMap()
        self.assertTrue(gm._point_ok(gm.width / 2, gm.height / 2))
        self.assertFalse(gm._point_ok(-1, -1))
        self.assertEqual(gm.inset_at(gm.width / 2, gm.height / 2),
                         float(terrain_inset.CAP))


class ClearanceTests(unittest.TestCase):
    def test_killers_mirror_the_clearance_transform(self):
        """`repair._killers` names the obstacles that make a cell impassable
        for the widest body; `NavGrid._clearance_transform` folds the same
        obstacles into one clearance number. They agree when: a cell with a
        killer has clearance under the body radius, and a cell whose bare
        terrain leaves room but whose clearance does not has a killer."""
        cell, radius = repair._widest_class()
        for seed in W.SEEDS:
            layout = W.layout(seed)
            with_obs = NavGrid(layout, layout.obstacles, cell)
            bare = NavGrid(layout, [], cell)
            killers = repair._killers(with_obs, layout.obstacles, radius)
            n = with_obs.cols * with_obs.rows
            for i in range(n):
                if not with_obs.walkable[i]:
                    continue
                if killers[i]:
                    self.assertLess(with_obs.clearance[i], radius,
                                    f"seed {seed} cell {i}: a killer, but room")
                elif bare.clearance[i] >= radius:
                    self.assertGreaterEqual(with_obs.clearance[i], radius,
                                            f"seed {seed} cell {i}: no killer, "
                                            f"bare terrain fits, yet blocked")


if __name__ == "__main__":
    unittest.main()
