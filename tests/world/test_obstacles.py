"""Milestone 9: obstacles -- collision, projectile blocking, deterministic
placement that keeps rooms navigable (spec 5.3)."""
import unittest

import pygame

from game import config
from entities.obstacle import Obstacle
from world.map import GameMap
from world.procedural import SPECIAL_KINDS, generate_world

# Pinned-seed obstacle-scatter assertions run against the flat base layout;
# LD-1 verticality shifts the RNG stream. Verticality's own stair keep-clear is
# checked in tests/world/test_verticality.py.
_SAVED_VERT = None


def setUpModule():
    global _SAVED_VERT
    _SAVED_VERT = config.WORLD_VERTICALITY
    config.WORLD_VERTICALITY = False


def tearDownModule():
    config.WORLD_VERTICALITY = _SAVED_VERT


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

    def test_resolve_movement_hops_a_fully_wedged_entity_free(self):
        gm = GameMap()
        prev = pygame.Vector2(1000, 1000)
        new = pygame.Vector2(1020, 1020)                 # a diagonal move
        gm.obstacles = [Obstacle("tree", 1030, 1030),    # blocks the full move
                        Obstacle("tree", 1030, 1000),    # blocks the x-slide
                        Obstacle("tree", 1000, 1030)]    # blocks the y-slide
        self.assertFalse(gm.is_walkable(new, 10))
        self.assertFalse(gm.is_walkable(pygame.Vector2(new.x, prev.y), 10))
        self.assertFalse(gm.is_walkable(pygame.Vector2(prev.x, new.y), 10))
        out = gm.resolve_movement(prev, new, 10)
        self.assertNotEqual(out, prev)                   # it found an out
        self.assertTrue(gm.is_walkable(out, 10))
        self.assertLessEqual((out - prev).length(), 13.0)   # a hop, not a teleport
        self.assertGreater(out.x, prev.x)               # toward the goal, not away
        self.assertGreater(out.y, prev.y)

    def test_resolve_movement_stays_put_when_every_hop_is_blocked(self):
        gm = GameMap()
        prev = pygame.Vector2(1000, 1000)
        gm.obstacles = [Obstacle("rock", 1000 + dx, 1000 + dy)
                        for dx in (-24, 0, 24) for dy in (-24, 0, 24)]
        self.assertEqual(gm.resolve_movement(prev, pygame.Vector2(1020, 1020), 10),
                         prev)

    def test_every_obstacle_kind_blocks_projectiles(self):
        self.gm.obstacles = [Obstacle("rock", 1600, 1600),
                             Obstacle("tree", 1600, 1200),
                             Obstacle("pillar", 1600, 800)]
        # a solid trunk / mass / column stops a shot -- all obstacle kinds do
        for oy in (1600, 1200, 800):
            self.assertIsNotNone(
                self.gm.blocking_obstacle_hit(pygame.Vector2(1600, oy), 4))
        # open ground does not
        self.assertIsNone(
            self.gm.blocking_obstacle_hit(pygame.Vector2(1600, 400), 4))


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

    def test_special_room_centres_kept_clear(self):
        for seed in (5, 9, 42):
            w = generate_world(seed)
            for room in w.rooms:
                if room.kind not in SPECIAL_KINDS:
                    continue                       # combat rooms may fill the middle
                cx, cy = room.rect.center
                clear = min(room.rect.width, room.rect.height) * 0.2
                for o in w.obstacles:
                    if (o.pos.x - cx) ** 2 + (o.pos.y - cy) ** 2 < clear ** 2:
                        self.fail(f"obstacle blocks the centre of {room.kind} "
                                  f"room {room.id} (seed {seed})")

    def test_combat_rooms_may_place_obstacles_near_the_centre(self):
        seen = False
        for seed in range(30):
            w = generate_world(seed)
            for room in w.rooms:
                if room.kind != "combat":
                    continue
                cx, cy = room.rect.center
                near = min(room.rect.width, room.rect.height) * 0.15
                if any((o.pos.x - cx) ** 2 + (o.pos.y - cy) ** 2 < near ** 2
                       for o in w.obstacles):
                    seen = True
        self.assertTrue(seen, "no combat room ever placed an obstacle mid-room")

    def test_some_obstacles_exist(self):
        self.assertGreater(len(generate_world(1).obstacles), 5)

    def test_no_obstacle_on_a_corridor_doorway_tile(self):
        from world.procedural import _corridor_doorways
        px = 64
        for seed in (1, 3, 7, 9, 42, 77, 123):
            w = generate_world(seed)
            slabs = _corridor_doorways(w.rooms, w.corridors)
            door_tiles = [d.inflate(-2 * px, -2 * px)          # back to the bare 64px cell
                          for lst in slabs.values() for d in lst]
            for o in w.obstacles:
                for tile in door_tiles:
                    if tile.width > 0 and tile.collidepoint(o.pos.x, o.pos.y):
                        self.fail(f"seed {seed}: {o.kind} sits on a corridor doorway")

    def test_doorway_clearance_leaves_combat_rooms_populated(self):
        w = generate_world(9)
        combat = [r for r in w.rooms if r.kind == "combat"]
        with_obstacles = sum(
            1 for r in combat
            if any(r.rect.collidepoint(o.pos.x, o.pos.y) for o in w.obstacles))
        self.assertGreaterEqual(with_obstacles, max(1, len(combat) - 1))


if __name__ == "__main__":
    unittest.main()
