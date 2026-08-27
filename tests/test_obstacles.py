"""Milestone 9: obstacles -- collision, projectile blocking, deterministic
placement that keeps rooms navigable (spec 5.3)."""
import unittest

import pygame

from entities.obstacle import Obstacle
from world.map import GameMap
from world.procedural import generate_world


class ObstacleCollisionTests(unittest.TestCase):
    def setUp(self):
        self.gm = GameMap()  # one big room, no procedural obstacles
        self.gm.obstacles = [Obstacle("rock", 1600, 1600),
                             Obstacle("tree", 1600, 1200)]

    def test_cannot_stand_inside_a_rock(self):
        self.assertFalse(self.gm.is_walkable(pygame.Vector2(1600, 1600), 10))
        self.assertTrue(self.gm.is_walkable(pygame.Vector2(1600, 800), 10))

    def test_movement_slides_around_an_obstacle(self):
        prev = pygame.Vector2(1600, 1540)
        # push straight into the rock; should be redirected, not stuck at prev
        out = self.gm.resolve_movement(prev, pygame.Vector2(1600, 1585), 12)
        self.assertLessEqual(out.y, prev.y + 1)   # blocked on the Y axis

    def test_only_solid_obstacles_block_projectiles(self):
        self.assertIsNotNone(
            self.gm.blocking_obstacle_hit(pygame.Vector2(1600, 1600), 4))
        # the tree at (1600,1200) does not block shots
        self.assertIsNone(
            self.gm.blocking_obstacle_hit(pygame.Vector2(1600, 1200), 4))


class ObstacleGenerationTests(unittest.TestCase):
    def test_deterministic_with_seed(self):
        a = generate_world(77).obstacles
        b = generate_world(77).obstacles
        self.assertEqual([(o.kind, tuple(o.pos)) for o in a],
                         [(o.kind, tuple(o.pos)) for o in b])

    def test_none_in_start_or_boss_room(self):
        w = generate_world(5)
        for rid in (w.start_id, w.boss_id):
            r = w.room(rid).rect
            self.assertFalse(any(r.collidepoint(o.pos.x, o.pos.y)
                                 for o in w.obstacles))

    def test_room_centres_kept_clear(self):
        w = generate_world(9)
        for room in w.rooms:
            cx, cy = room.rect.center
            clear = min(room.rect.width, room.rect.height) * 0.2
            for o in w.obstacles:
                if (o.pos.x - cx) ** 2 + (o.pos.y - cy) ** 2 < clear ** 2:
                    self.fail(f"obstacle blocks the centre of room {room.id}")

    def test_some_obstacles_exist(self):
        self.assertGreater(len(generate_world(1).obstacles), 5)


if __name__ == "__main__":
    unittest.main()
