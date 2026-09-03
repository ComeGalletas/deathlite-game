"""`spawn/placement.py`: the six-step filter, the weighted pick, the
cooldown, deferral relaxation, and the follower ring (spawn master S3)."""
import math
import unittest

import pygame

from game.content import get_content
from spawn import PointIndex, Placement, SpawnRequest
from tests.spawn.fakehost import FakeHost, ROOM0, ROOM1, grid_points
from world.layout import SpawnPoint


def _placement(host) -> Placement:
    return Placement(PointIndex(host.layout), get_content().spawn_tables.placement)


def _req(host, **kw) -> SpawnRequest:
    kw.setdefault("radius", 14.0)
    kw.setdefault("room_weights", {0: 1.0, 1: 1.0})
    kw.setdefault("player_floor", host.floor)
    return SpawnRequest(**kw)


class FilterTests(unittest.TestCase):
    def test_the_zone_is_the_first_gate(self):
        host = FakeHost()
        pl = _placement(host)
        only1 = pl.candidates(_req(host, room_weights={1: 1.0}), host, 0.0)
        self.assertTrue(only1)
        self.assertTrue(all(p.room_id == 1 for p, _w in only1))
        self.assertEqual(pl.candidates(_req(host, room_weights={}), host, 0.0), [])

    def test_nothing_inside_the_padded_view_or_near_the_player(self):
        host = FakeHost()
        pl = _placement(host)
        pad = pl.view_pad
        padded = host.view.inflate(2 * pad, 2 * pad)
        for p, _w in pl.candidates(_req(host), host, 0.0):
            self.assertFalse(padded.collidepoint(p.x, p.y), p)
            self.assertGreaterEqual((p.pos - host.player).length(), pl.min_distance)

    def test_a_large_request_only_takes_large_points(self):
        pts = grid_points(0, ROOM0, clearance="small") + grid_points(1, ROOM1, clearance="large")
        host = FakeHost(points=pts)
        pl = _placement(host)
        big = pl.candidates(_req(host, radius=22.0, clearance="large"), host, 0.0)
        self.assertTrue(big)
        self.assertTrue(all(p.clearance == "large" for p, _w in big))
        small = pl.candidates(_req(host, clearance="small"), host, 0.0)
        self.assertTrue(any(p.clearance == "small" for p, _w in small))

    def test_a_live_body_on_the_point_excludes_it(self):
        host = FakeHost()
        pl = _placement(host)
        before = pl.candidates(_req(host), host, 0.0)
        target = before[0][0]
        host.make_enemy("chaser", target.x + 5, target.y, 1.0, 1.0)
        after = pl.candidates(_req(host), host, 0.0)
        self.assertNotIn(target, [p for p, _w in after])
        self.assertEqual(len(after), len(before) - 1)

    def test_same_floor_and_preferred_tags_weight_up(self):
        def floor_of(x, y):
            return 1 if y < 2000 else 0
        pts = grid_points(0, ROOM0, floor_of=floor_of) + grid_points(1, ROOM1, floor_of=floor_of)
        pts = [p._replace(tags=frozenset({"upper"}) if p.floor == 1 else frozenset()) for p in pts]
        host = FakeHost(points=pts)
        host.floor = 0
        pl = _placement(host)
        weights = {p: w for p, w in pl.candidates(_req(host), host, 0.0)}
        floors = {p.floor: w for p, w in weights.items()}
        self.assertAlmostEqual(floors[0], pl.same_floor_weight)
        self.assertAlmostEqual(floors[1], 1.0)
        # prefer "upper": the same-floor bonus is off and the upper points win
        weights = {p: w for p, w in pl.candidates(_req(host, prefer=("upper",)), host, 0.0)}
        floors = {p.floor: w for p, w in weights.items()}
        self.assertAlmostEqual(floors[0], 1.0)
        self.assertAlmostEqual(floors[1], pl.prefer_weight)


class CooldownAndDeferralTests(unittest.TestCase):
    def test_a_chosen_point_cools_down_and_comes_back(self):
        host = FakeHost()
        pl = _placement(host)
        p = pl.choose(_req(host), host, 10.0)
        self.assertIsNotNone(p)
        self.assertTrue(pl.on_cooldown(p, 10.0))
        self.assertNotIn(p, [c for c, _w in pl.candidates(_req(host), host, 11.0)])
        self.assertFalse(pl.on_cooldown(p, 10.0 + pl.cooldown))
        self.assertIn(p, [c for c, _w in pl.candidates(_req(host), host, 10.0 + pl.cooldown)])

    def test_nothing_survives_returns_none_and_debt_relaxes_the_view_rule(self):
        # A view so large that every point is inside it.
        host = FakeHost()
        host.view = pygame.Rect(-100, -100, 4200, 4200)
        pl = _placement(host)
        self.assertIsNone(pl.choose(_req(host), host, 0.0))
        # Still nothing when relaxed: relaxed means "outside the view", and
        # the view covers the world.
        self.assertIsNone(pl.choose(_req(host), host, 0.0, debt_age=pl.relax_after))
        # A view that leaves points only inside the pad / min-distance band:
        # refused fresh, accepted once the debt is old enough.
        host.view = pygame.Rect(0, 0, 4000, 4000)
        host.view.center = (2000, 2000)
        host.view.inflate_ip(-2 * 1500, -2 * 1500)      # 1000 x 1000 centred
        host.player = pygame.Vector2(2000, 2000)
        # The view spans 1500..2500; padded by 96 it spans 1404..2596. Both
        # points sit in that band: outside the view, inside the pad.
        pts = [SpawnPoint(0, 0, 1450.0, 2000.0), SpawnPoint(0, 0, 2000.0, 1450.0)]
        host.layout.spawn_points = pts
        pl = _placement(host)
        self.assertIsNone(pl.choose(_req(host), host, 0.0))       # inside the 96 px pad
        got = pl.choose(_req(host), host, 0.0, debt_age=pl.relax_after)
        self.assertIn(got, pts)

    def test_the_pick_is_weighted_and_reproducible(self):
        a, b = FakeHost(seed=5), FakeHost(seed=5)
        pa, pb = _placement(a), _placement(b)
        self.assertEqual([pa.choose(_req(a), a, t) for t in range(0, 30, 4)],
                         [pb.choose(_req(b), b, t) for t in range(0, 30, 4)])


class RingTests(unittest.TestCase):
    def test_followers_ring_the_leader_at_the_right_gap(self):
        host = FakeHost()
        pl = _placement(host)
        centre = pygame.Vector2(1000, 1000)
        radii = [14.0, 14.0, 26.0]
        spots = pl.ring(centre, 22.0, radii, host.is_walkable, host.rng)
        self.assertEqual(len(spots), 3)
        for fr, s in zip(radii, spots):
            self.assertIsNotNone(s)
            self.assertAlmostEqual((s - centre).length(), 22.0 + fr + pl.ring_gap, places=6)
        # evenly spread: the two smallest angles between neighbours are ~120 deg
        angs = sorted(math.atan2(s.y - centre.y, s.x - centre.x) for s in spots)
        gaps = [angs[1] - angs[0], angs[2] - angs[1], math.tau - (angs[2] - angs[0])]
        for g in gaps:
            self.assertAlmostEqual(g, math.tau / 3, places=6)

    def test_a_blocked_spot_is_retried_wider_then_dropped(self):
        host = FakeHost()
        pl = _placement(host)
        centre = pygame.Vector2(1000, 1000)
        # a wall disc that blocks the first ring but not the wider one
        host.blocked = [(centre, 22.0 + 14.0 + pl.ring_gap + 2.0)]
        spots = pl.ring(centre, 22.0, [14.0], host.is_walkable, host.rng)
        self.assertIsNotNone(spots[0])
        self.assertGreater((spots[0] - centre).length(), 22.0 + 14.0 + pl.ring_gap)
        # a wall that blocks both -> dropped
        host.blocked = [(centre, 500.0)]
        self.assertEqual(pl.ring(centre, 22.0, [14.0], host.is_walkable, host.rng), [None])

    def test_no_followers_is_no_ring(self):
        host = FakeHost()
        self.assertEqual(_placement(host).ring(pygame.Vector2(), 1.0, [], host.is_walkable,
                                               host.rng), [])


if __name__ == "__main__":
    unittest.main()
