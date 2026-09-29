"""ENT-018: the cheaper enemy update gives exactly the old one's result
(`enemy_update_journal.md`).

Every change here is a way of not doing work whose result was thrown away,
and each is pinned against the code it replaced, copied verbatim as the
oracle. Positions and pushes are summed floats, so "close" would be another
game: the comparisons are `==` on the floats themselves.

* **The crowding push** (`Separation.tick`, ENT-018.2) drops far neighbour
  candidates on float products before any vector. Pinned over random crowds
  (the actor in its own list, dead bodies, coincident points, points exactly
  at the push radius and a hair inside the minimum) and over every enemy of
  seed 35's packed fight, frame after frame.
"""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.ai.components.crowd import Separation
from game import config


def _old_separation_tick(self, actor, per, cmb, acc):
    """`Separation.tick` as it was before ENT-018.2, verbatim."""
    r = actor.radius * self.radius_mult
    push = pygame.Vector2()
    for other in per.neighbors(actor.pos, r):
        if other is actor or not getattr(other, "alive", True):
            continue
        away = actor.pos - other.pos
        dsq = away.length_squared()
        if dsq < 1e-6 or dsq >= r * r:
            continue
        away.scale_to_length((r - dsq ** 0.5) / r)
        push += away
    if push.length_squared() > self.cap * self.cap:
        push.scale_to_length(self.cap)
    acc.add(push, self.weight)


class _Acc:
    """Records what a component hands the steering accumulator."""

    def __init__(self):
        self.added = []

    def add(self, vec, weight=1.0):
        self.added.append((tuple(vec), weight))


class _Body:
    def __init__(self, x, y, radius=14.0, alive=True):
        self.pos = pygame.Vector2(x, y)
        self.radius = radius
        self.alive = alive


class _Per:
    def __init__(self, crowd):
        self.crowd = crowd

    def neighbors(self, pos, radius):
        return list(self.crowd)


def _both_pushes(sep, actor, per):
    old, new = _Acc(), _Acc()
    _old_separation_tick(sep, actor, per, None, old)
    sep.tick(actor, per, None, new)
    return old.added, new.added


class SeparationRandomTests(unittest.TestCase):
    def test_random_crowds_push_exactly_as_before(self):
        rng = random.Random(18002)
        pushed = 0
        for case in range(600):
            radius = rng.choice((9.0, 13.0, 16.0, 22.0, 26.0))
            sep = Separation(radius_mult=rng.choice((1.6, 1.0, 2.3)),
                             cap=rng.choice((0.6, 0.2, 5.0)))
            r = radius * sep.radius_mult
            actor = _Body(rng.uniform(-500, 3000), rng.uniform(-500, 3000), radius)
            crowd = [actor]
            for _ in range(rng.randrange(0, 40)):
                a = rng.uniform(0, 6.283)
                d = rng.choice((rng.uniform(0, 2.5 * r), rng.uniform(0, r)))
                crowd.append(_Body(actor.pos.x + d * pygame.math.Vector2(1, 0).rotate_rad(a).x,
                                   actor.pos.y + d * pygame.math.Vector2(1, 0).rotate_rad(a).y,
                                   alive=rng.random() > 0.08))
            crowd.append(_Body(actor.pos.x, actor.pos.y))                 # coincident
            crowd.append(_Body(actor.pos.x + r, actor.pos.y))             # exactly at r
            crowd.append(_Body(actor.pos.x + 1e-3 * (1 + 1e-6), actor.pos.y))  # just past 1e-6
            rng.shuffle(crowd)
            old, new = _both_pushes(sep, actor, _Per(crowd))
            with self.subTest(case=case):
                self.assertEqual(new, old)
            pushed += old[0][0] != (0.0, 0.0)
        self.assertGreater(pushed, 400, "the crowds barely pushed")


class SeparationLimitTests(unittest.TestCase):
    """Neighbours placed on purpose within a billionth of the vector test's
    two limits, where the early drop's margin decides whether they reach it.
    At the origin, so the offsets keep their precision."""

    def _one(self, dx):
        sep = Separation()
        actor = _Body(0.0, 0.0, 14.0)
        other = _Body(dx, 0.0)
        d2 = (actor.pos - other.pos).length_squared()
        old, new = _both_pushes(sep, actor, _Per([actor, other]))
        return d2, old, new

    def test_just_past_the_minimum_distance_pushes(self):
        d2, old, new = self._one((1e-6 * (1.0 + 5e-10)) ** 0.5)
        self.assertTrue(1e-6 <= d2 < 1e-6 * (1.0 + 1e-9), d2)
        self.assertNotEqual(old[0][0], (0.0, 0.0), "the neighbour should push")
        self.assertEqual(new, old)

    def test_just_inside_the_push_radius_pushes(self):
        r = 14.0 * Separation().radius_mult
        d2, old, new = self._one(r * (1.0 - 2e-10))
        self.assertTrue(r * r * (1.0 - 1e-9) <= d2 < r * r, (d2, r * r))
        self.assertNotEqual(old[0][0], (0.0, 0.0), "the neighbour should push")
        self.assertEqual(new, old)


class SeparationFightTests(unittest.TestCase):
    """Every enemy of seed 35's packed fight, with the real neighbour query,
    frame after frame as the fight plays."""

    @classmethod
    def setUpClass(cls):
        from tools.benchmarks import spawn_stress as S

        cls.game, cls.ps = S.build(35, 100, 0, 300.0, config.ENEMY_LOD_SKIP)
        S.run(cls.ps, 20)
        S.cascade_setup(cls.ps, prime=False)

    def test_every_enemy_every_frame(self):
        ps = self.ps
        sep = Separation()
        compared = pushed = 0
        for frame in range(40):
            per = ps._enemy_context(1 / 60)
            for e in ps.enemies:
                old, new = _both_pushes(sep, e, per)
                if new != old:
                    self.fail(f"frame {frame}, enemy {ps.enemies.index(e)}: {new} != {old}")
                compared += 1
                pushed += old[0][0] != (0.0, 0.0)
            ps.update(1 / 60)
        self.assertGreater(compared, 3000)
        self.assertGreater(pushed, 1000, "the packed crowd barely pushed")


if __name__ == "__main__":
    unittest.main()
