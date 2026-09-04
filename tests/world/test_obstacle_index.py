"""The obstacle index behind `GameMap.is_walkable` answers exactly what the
whole-list scan answered, and follows the list when it is reassigned."""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.obstacle import Obstacle
from tests import worlds as W
from world.map import GameMap, _ObstacleIndex


def _linear_free(gm, pos, radius) -> bool:
    for o in gm.obstacles:
        rr = o.radius + radius
        if (pos.x - o.pos.x) ** 2 + (pos.y - o.pos.y) ** 2 < rr * rr:
            return False
    return True


class IndexTests(unittest.TestCase):
    def test_the_index_agrees_with_the_scan_on_every_seed(self):
        """Random probes across the world, at every body radius the game
        uses: the set of obstacles the index offers always contains every
        one the scan would have hit, and the verdict is identical."""
        for seed in W.SEEDS:
            gm = W.game_map(seed)
            rng = random.Random(seed)
            hits = 0
            for _ in range(4000):
                pos = pygame.Vector2(rng.uniform(0, gm.width), rng.uniform(0, gm.height))
                radius = rng.choice((0.0, 13.0, 16.0, 22.0, 26.0, 46.0))
                near = gm._obstacle_index.near(pos.x, pos.y, radius)
                for o in gm.obstacles:
                    rr = o.radius + radius
                    if (pos.x - o.pos.x) ** 2 + (pos.y - o.pos.y) ** 2 < rr * rr:
                        self.assertIn(o, near, f"seed {seed}: index missed an obstacle")
                        hits += 1
                free_idx = all((pos.x - o.pos.x) ** 2 + (pos.y - o.pos.y) ** 2 >= (o.radius + radius) ** 2
                               for o in near)
                self.assertEqual(free_idx, _linear_free(gm, pos, radius))
            self.assertGreater(hits, 20, f"seed {seed}: the probes never touched an obstacle")

    def test_walkability_and_projectile_blocking_are_unchanged(self):
        seed = W.SEEDS[0]
        gm = W.game_map(seed)
        rng = random.Random(1)
        for _ in range(3000):
            pos = pygame.Vector2(rng.uniform(0, gm.width), rng.uniform(0, gm.height))
            radius = rng.choice((0.0, 14.0, 22.0))
            if not gm._point_ok(pos.x, pos.y):
                continue
            # walkable iff the floor tests pass and no obstacle overlaps
            expect = _linear_free(gm, pos, radius) and (
                not (gm._body_inset > 0.0 and not gm.inset_ok(pos.x, pos.y)))
            if radius > 0 and not (gm._point_ok(pos.x + radius, pos.y) and gm._point_ok(pos.x - radius, pos.y)
                                   and gm._point_ok(pos.x, pos.y + radius) and gm._point_ok(pos.x, pos.y - radius)):
                expect = False
            self.assertEqual(gm.is_walkable(pos, radius), expect)
            hit = gm.blocking_obstacle_hit(pos, radius)
            linear = next((o for o in gm.obstacles if o.blocks_projectiles
                           and (pos.x - o.pos.x) ** 2 + (pos.y - o.pos.y) ** 2 < (o.radius + radius) ** 2), None)
            self.assertIs(hit is None, linear is None)

    def test_assigning_the_list_rebuilds_the_index(self):
        gm = GameMap()                                   # the one-room test world
        self.assertTrue(gm.is_walkable(pygame.Vector2(1600, 1600), 10.0))
        gm.obstacles = [Obstacle("rock", 1600, 1600)]
        self.assertFalse(gm.is_walkable(pygame.Vector2(1600, 1600), 10.0))
        self.assertIsNotNone(gm.blocking_obstacle_hit(pygame.Vector2(1600, 1600), 10.0))
        gm.obstacles = []
        self.assertTrue(gm.is_walkable(pygame.Vector2(1600, 1600), 10.0))

    def test_a_probe_spanning_bucket_edges_sees_both_sides(self):
        idx = _ObstacleIndex([Obstacle("rock", 127, 127), Obstacle("rock", 129, 129)], cell=128)
        near = idx.near(128, 128, 1.0)
        self.assertEqual(len(near), 2)
        self.assertEqual(idx.near(5000, 5000, 1.0), [])
        self.assertEqual(_ObstacleIndex([]).near(0, 0, 100.0), [])


if __name__ == "__main__":
    unittest.main()
