"""Obstacles: collision, projectile blocking, and a scatter that keeps the
world navigable.

The collision tests use the layout-less `GameMap()` -- one big room, no
procedural obstacles -- and place their own. The scatter tests read the
shared cached worlds. Determinism is `test_digest.py`'s job; that every
island is scattered and that the start and boss islands keep their clear
discs is `test_repair.py`'s.
"""
import unittest

import pygame

from entities.obstacle import Obstacle
from game import config
from tests import worlds as W
from world.gen.tuning import _GRID_CLEAR_RADIUS
from world.map import GameMap
from world.procedural import SPECIAL_KINDS, _corridor_doorways


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
        # Placed relative to the tree's own radius, not at pinned coordinates:
        # close enough that the move and both slides are blocked, far enough
        # that a short hop toward the goal is still free. Hardcoding the offsets
        # tied this test to one obstacle size, and it broke the moment those
        # moved into data/terrain.json and were retuned.
        r = Obstacle("tree", 0, 0).radius
        d = 20.0 + (r + 10.0) * 0.6
        gm.obstacles = [Obstacle("tree", 1000 + d, 1000 + d),  # blocks the move
                        Obstacle("tree", 1000 + d, 1000),      # blocks the x-slide
                        Obstacle("tree", 1000, 1000 + d)]      # blocks the y-slide
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
    def test_some_obstacles_exist(self):
        for seed in W.SEEDS:
            self.assertGreater(len(W.layout(seed).obstacles), 5, f"seed {seed}")

    def test_every_obstacle_stands_on_a_floor_cell(self):
        for seed in W.SEEDS:
            gm = W.game_map(seed)
            for o in gm.obstacles:
                self.assertTrue(gm._point_ok(o.pos.x, o.pos.y),
                                f"seed {seed}: {o.kind} at {tuple(o.pos)} is off "
                                f"the floor")

    def test_special_island_centres_keep_a_clear_disc(self):
        """A special island (shrine, altar, ...) keeps `_GRID_CLEAR_RADIUS`
        round its centre so the interactable there can be reached. The start
        and boss islands have their own discs, checked in `test_repair`; a
        combat island may fill its middle."""
        for seed in W.SEEDS:
            w = W.layout(seed)
            for room in w.rooms:
                if (room.id in (w.start_id, w.boss_id)
                        or room.kind not in SPECIAL_KINDS):
                    continue
                c = room.center
                for o in w.obstacles:
                    if not room.rect.collidepoint(o.pos.x, o.pos.y):
                        continue
                    self.assertGreaterEqual(
                        o.pos.distance_to(c), _GRID_CLEAR_RADIUS - o.radius,
                        f"seed {seed}: {o.kind} blocks the centre of "
                        f"{room.kind} island {room.id}")

    def test_nothing_stands_on_a_bridge_landing(self):
        """The two tiles at each end of every bridge -- the last plank and
        the landing beyond it -- plus one tile of margin, keep every
        obstacle's whole disc out, not just its centre. Measured off the
        bridge rects directly rather than through `_corridor_doorways`, so
        the test says what the rule promises, not what the helper computes."""
        px = config.TILE_PX
        for seed in W.SEEDS:
            w = W.layout(seed)
            for c in w.corridors:
                r = c.rect
                if c.axis == "h":
                    ends = (pygame.Rect(r.left - px, r.top, 2 * px, r.height),
                            pygame.Rect(r.right - px, r.top, 2 * px, r.height))
                else:
                    ends = (pygame.Rect(r.left, r.top - px, r.width, 2 * px),
                            pygame.Rect(r.left, r.bottom - px, r.width, 2 * px))
                for end in ends:
                    keep = end.inflate(2 * px, 2 * px)
                    for o in w.obstacles:
                        cx = min(max(o.pos.x, keep.left), keep.right)
                        cy = min(max(o.pos.y, keep.top), keep.bottom)
                        self.assertGreaterEqual(
                            (o.pos.x - cx) ** 2 + (o.pos.y - cy) ** 2,
                            o.radius ** 2,
                            f"seed {seed}: {o.kind} at {tuple(o.pos)} intrudes on "
                            f"the landing of bridge {c.a}-{c.b}")

    def test_the_doorway_helper_covers_every_bridge_end(self):
        """`_corridor_doorways` is what the scatter reads; it has to name the
        bridge end tiles, which it did not while it measured from the island
        rect (that edge is open sea once bridges are seated beach to beach)."""
        px = config.TILE_PX
        for seed in W.SEEDS:
            w = W.layout(seed)
            doors = [d for lst in _corridor_doorways(w.rooms, w.corridors).values()
                     for d in lst]
            for c in w.corridors:
                r = c.rect
                for tile in ((r.left, r.top), (r.right - px, r.bottom - px)):
                    end = pygame.Rect(tile, (px, px))
                    self.assertTrue(any(d.contains(end) for d in doors),
                                    f"seed {seed}: bridge {c.a}-{c.b} end {tile} "
                                    f"has no keep-clear rect")


if __name__ == "__main__":
    unittest.main()
