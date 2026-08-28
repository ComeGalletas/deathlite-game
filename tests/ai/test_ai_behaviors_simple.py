"""`entities/ai/behaviors/simple.py` -- `chase`, `path_chase`, `swarm`."""
import random
import unittest
from types import SimpleNamespace

import pygame

from entities.ai import Blackboard, build_behavior, registered


def _enemy(pos, speed=180.0, radius=10.0):
    return SimpleNamespace(pos=pygame.Vector2(pos), vel=pygame.Vector2(),
                           radius=radius, speed=speed, alive=True, hp=10.0,
                           contact_damage=1.0, contact_cd=5.0, facing=-1,
                           bb=Blackboard())


def _per(player=(0.0, -400.0), nav=(0.0, 0.0), dt=1 / 120):
    nv = pygame.Vector2(nav)
    return SimpleNamespace(
        dt=dt, now=0.0, player_pos=pygame.Vector2(player), player=object(),
        rng=random.Random(0), nav_dir=lambda p, r: pygame.Vector2(nv),
        neighbors=lambda p, r: [], obstacles_near=lambda p, r: [],
        is_walkable=lambda p, r: True, resolve_movement=lambda a, b, r: b)


class RegistrationTests(unittest.TestCase):
    def test_simple_behaviours_are_registered(self):
        for name in ("chase", "chaser", "path_chase", "swarm"):
            self.assertIn(name, registered())

    def test_path_chase_state_shape(self):
        b = build_behavior("path_chase", {})
        self.assertEqual(list(b.states), ["move"])
        self.assertEqual([type(c).__name__ for c in b.states["move"]],
                         ["SeekTarget", "Separation", "AvoidObstacles", "Unstick"])

    def test_chase_is_a_bare_straight_seek(self):
        (comp,) = build_behavior("chase", {}).states["move"]
        self.assertEqual((type(comp).__name__, comp.via, comp.slew),
                         ("SeekTarget", "straight", 0.0))


class SimpleMovementTests(unittest.TestCase):
    def test_chase_heads_straight_at_the_player_at_full_speed(self):
        e = _enemy((0.0, 0.0))
        build_behavior("chase", {}).tick(e, _per(player=(0, -300)), None)
        self.assertAlmostEqual(e.vel.length(), e.speed, places=3)
        self.assertLess(e.vel.y, -e.speed * 0.99)

    def test_path_chase_follows_the_flow_field_when_it_has_a_route(self):
        e = _enemy((0.0, 0.0))
        # field points up-left; player is straight down -> must follow the field
        build_behavior("path_chase", {}).tick(e, _per(player=(0, 400), nav=(-1, -1)),
                                              None)
        self.assertLess(e.vel.x, 0)
        self.assertLess(e.vel.y, 0)

    def test_path_chase_falls_back_to_straight_when_the_field_is_silent(self):
        e = _enemy((0.0, 0.0))
        for _ in range(30):
            build_behavior("path_chase", {}).tick(e, _per(player=(0, -300),
                                                          nav=(0, 0)), None)
        self.assertLess(e.vel.y, -e.speed * 0.9)

    def test_path_chase_closes_the_gap_over_time(self):
        e = _enemy((0.0, 0.0))
        beh = build_behavior("path_chase", {})
        start = 400.0
        for _ in range(240):
            beh.tick(e, _per(player=(0, -start), nav=(0, -1)), None)
            e.pos += e.vel * (1 / 120)
        self.assertLess((e.pos - pygame.Vector2(0, -start)).length(), start * 0.5)


if __name__ == "__main__":
    unittest.main()
