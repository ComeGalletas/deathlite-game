"""`spawn/placement.py`: the six-step filter, the weighted pick, the
cooldown, deferral relaxation, and the company packer (spawn master S3,
G0a).
Since S11 the filter's distance rule is a band around the player and the
camera is not an input; the tests here move the view and expect nothing."""
import math
import unittest

import pygame

from game.content import get_content
from spawn import PointIndex, Placement, SpawnRequest
from spawn.placement import FAR, NEAR, STARVED
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
        host.player = pygame.Vector2(1900, 2000)     # at the bridge: both islands in the band
        pl = _placement(host)
        only1 = pl.candidates(_req(host, room_weights={1: 1.0}), host, 0.0)
        self.assertTrue(only1)
        self.assertTrue(all(p.room_id == 1 for p, _w in only1))
        self.assertEqual(pl.candidates(_req(host, room_weights={}), host, 0.0), [])

    def test_the_strict_rung_is_a_band_around_the_player(self):
        host = FakeHost()
        pl = _placement(host)
        cands = pl.candidates(_req(host), host, 0.0)
        self.assertTrue(cands)
        for p, _w in cands:
            d = (p.pos - host.player).length()
            self.assertGreaterEqual(d, pl.far_min_distance, p)
            self.assertLessEqual(d, pl.far_max_distance, p)

    def test_the_camera_never_moves_a_spawn(self):
        # S11 (owner, 2026-09-15): the same request lands the same way
        # wherever the view is and however wide it is. Move the camera away
        # from the hero, then make it cover the whole world: nothing changes
        # at any rung.
        host = FakeHost()
        pl = _placement(host)
        want = {tier: [p for p, _w in pl.candidates(_req(host), host, 0.0, tier=tier)]
                for tier in (FAR, NEAR, STARVED)}
        host.view = pygame.Rect(3000, 3000, 1000, 600)
        for tier in (FAR, NEAR, STARVED):
            self.assertEqual([p for p, _w in pl.candidates(_req(host), host, 0.0, tier=tier)],
                             want[tier])
        host.view = pygame.Rect(-100, -100, 4200, 4200)
        for tier in (FAR, NEAR, STARVED):
            self.assertEqual([p for p, _w in pl.candidates(_req(host), host, 0.0, tier=tier)],
                             want[tier])

    def test_the_ceiling_drops_at_the_near_rung(self):
        inside = SpawnPoint(0, 0, 1000.0, 2000.0 + 900.0)
        beyond = SpawnPoint(0, 0, 1000.0, 2000.0 - 1500.0)
        host = FakeHost(points=[inside, beyond])
        pl = _placement(host)
        self.assertEqual([p for p, _w in pl.candidates(_req(host), host, 0.0, tier=FAR)],
                         [inside])
        self.assertEqual(set(p for p, _w in pl.candidates(_req(host), host, 0.0, tier=NEAR)),
                         {inside, beyond})

    def test_a_large_request_only_takes_large_points(self):
        pts = grid_points(0, ROOM0, clearance="small") + grid_points(1, ROOM1, clearance="large")
        host = FakeHost(points=pts)
        host.player = pygame.Vector2(1900, 2000)     # at the bridge: both islands in the band
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
        host.make_enemy("skull", target.x + 5, target.y, 1.0, 1.0)
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

    def test_the_ladder_seats_a_point_inside_the_near_keep_away(self):
        # Every point closer than the near rung allows but outside the
        # starved keep-away. This used to be the give-up case; the owner
        # asked (2026-09-12) for spawns to continue even when the camera can
        # see them, so the starved rung seats it.
        host = FakeHost()
        d = 450.0
        host.layout.spawn_points = [SpawnPoint(0, 0, 1000.0 + d, 2000.0),
                                    SpawnPoint(0, 0, 1000.0, 2000.0 - d)]
        pl = _placement(host)
        self.assertLess(d, pl.near_min_distance)
        self.assertGreaterEqual(d, pl.starved_min_distance)
        self.assertEqual(pl.candidates(_req(host), host, 0.0, tier=NEAR), [])
        got = pl.choose(_req(host), host, 0.0)
        self.assertIsNotNone(got)
        self.assertGreaterEqual((got.pos - host.player).length(),
                                pl.starved_min_distance)

    def test_none_means_nothing_is_usable_at_any_rung(self):
        # Every point inside the keep-away: no rung can offer one, so the
        # master still gets `None` and keeps the request as debt.
        host = FakeHost(points=[SpawnPoint(0, 0, 1000.0, 2000.0 + d)
                                for d in (0.0, 60.0, 120.0)])
        pl = _placement(host)
        self.assertIsNone(pl.choose(_req(host), host, 0.0))

    def test_the_starved_rung_leans_to_the_far_edge(self):
        # Candidates are weighted by distance there, so of two usable points
        # the further one is drawn far more often.
        near = SpawnPoint(0, 0, 1000.0, 2000.0 + 450.0)
        far = SpawnPoint(0, 0, 1000.0, 2000.0 + 1800.0)
        host = FakeHost(points=[near, far])
        pl = _placement(host)
        picks = [p for p, _w in pl.candidates(_req(host), host, 0.0, tier=STARVED)]
        self.assertEqual(set(picks), {near, far})
        weights = dict((p, w) for p, w in
                       pl.candidates(_req(host), host, 0.0, tier=STARVED))
        self.assertGreater(weights[far], weights[near] * 3)

    def test_the_starved_rung_recycles_points_sooner(self):
        host = FakeHost()
        pl = _placement(host)
        point = pl.choose(_req(host), host, 10.0)
        self.assertTrue(pl.on_cooldown(point, 11.0))
        # The same point, at the same moment, is free at the starved rung.
        self.assertFalse(pl.on_cooldown(point, 10.0 + pl.starved_cooldown, STARVED))
        self.assertTrue(pl.on_cooldown(point, 10.0 + pl.starved_cooldown))

    def test_an_aged_debt_still_skips_the_keep_away(self):
        knobs = get_content().spawn_tables.placement
        # Points between the near keep-away and the strict rung's floor:
        # refused fresh, accepted once the debt is old enough.
        d = (float(knobs["near_min_distance"]) + float(knobs["far_min_distance"])) / 2.0
        pts = [SpawnPoint(0, 0, 1000.0 - d, 2000.0), SpawnPoint(0, 0, 1000.0, 2000.0 - d)]
        host = FakeHost(points=pts)
        pl = _placement(host)
        self.assertEqual(pl.candidates(_req(host), host, 0.0, tier=FAR), [],
                         "inside the strict floor")
        got = pl.choose(_req(host), host, 0.0, debt_age=pl.relax_after)
        self.assertIn(got, pts)

    def test_the_pick_is_weighted_and_reproducible(self):
        a, b = FakeHost(seed=5), FakeHost(seed=5)
        pa, pb = _placement(a), _placement(b)
        self.assertEqual([pa.choose(_req(a), a, t) for t in range(0, 30, 4)],
                         [pb.choose(_req(b), b, t) for t in range(0, 30, 4)])


class PackTests(unittest.TestCase):
    """`pack` replaced the single follower circle in G0a (2026-09-17). The
    circle only ever checked the terrain, so above a handful of bodies a pack
    stacked on itself; these pin what the packer owes instead -- everyone
    seated, nobody overlapping, every spot walkable, and a graceful short
    company when the ground runs out."""

    CENTRE = pygame.Vector2(1000, 1000)

    def _pack(self, pl, host, leader_r, radii):
        return pl.pack(self.CENTRE, leader_r, radii, host.is_walkable, host.rng)

    def _assert_legal(self, spots, leader_r, radii, host, limit=None):
        """No body overlaps the leader or another body, and every spot is
        walkable for the body that took it."""
        bodies = [(self.CENTRE, leader_r)]
        for fr, s in zip(radii, spots):
            if s is None:
                continue
            self.assertTrue(host.is_walkable(s, fr), f"{s} is not walkable for r{fr}")
            if limit is not None:
                self.assertLessEqual((s - self.CENTRE).length(), limit + 1e-6)
            for q, qr in bodies:
                self.assertGreaterEqual((s - q).length(), fr + qr - 1e-6,
                                        f"{s} (r{fr}) overlaps a body at {q} (r{qr})")
            bodies.append((s, fr))

    def test_a_forty_body_company_seats_whole_and_never_overlaps(self):
        # The measurement that justified the packer: the old circle capped
        # near 24 seated with 75 overlapping pairs at this size.
        host = FakeHost()
        pl = _placement(host)
        radii = [10.0] * 40
        spots = self._pack(pl, host, 10.0, radii)
        self.assertEqual(len(spots), 40)
        self.assertNotIn(None, spots)
        self._assert_legal(spots, 10.0, radii, host)
        # and it stays a company: a screen's worth of ground, not the island
        self.assertLess(max((s - self.CENTRE).length() for s in spots), 300.0)

    def test_a_small_pack_stays_tight_against_the_leader(self):
        host = FakeHost()
        pl = _placement(host)
        radii = [14.0, 14.0, 26.0]
        spots = self._pack(pl, host, 22.0, radii)
        self.assertEqual(len(spots), 3)
        self.assertNotIn(None, spots)
        self._assert_legal(spots, 22.0, radii, host)
        # The first ring clears the leader by the largest follower plus the
        # gap; on open ground three bodies all fit on it, jitter included.
        first = 22.0 + 26.0 + pl.pack_gap
        step = 2.0 * 26.0 + pl.pack_gap
        for s in spots:
            self.assertLessEqual((s - self.CENTRE).length(),
                                 first + pl.pack_jitter * step)

    def test_the_radius_grows_with_the_company_and_the_bodies(self):
        host = FakeHost()
        pl = _placement(host)
        small = self._pack(pl, host, 10.0, [10.0] * 6)
        crowd = self._pack(pl, host, 10.0, [10.0] * 40)
        heavy = self._pack(pl, host, 24.0, [24.0] * 6)
        reach = lambda spots: max((s - self.CENTRE).length() for s in spots if s)
        self.assertLess(reach(small), reach(crowd))
        self.assertLess(reach(small), reach(heavy))
        self.assertLessEqual(reach(crowd), pl.pack_max_radius)

    def test_the_jitter_breaks_the_rings_without_costing_a_body(self):
        # Measured (2026-09-17): jitter at 0.35 fills as well as the exact
        # rings. What it buys is that the company is not laid out in visible
        # circles -- so on open ground the same 40 bodies seat, but they no
        # longer sit at a handful of discrete radii.
        host = FakeHost()
        radii = [10.0] * 40
        exact = _placement(host)
        exact.pack_jitter = 0.0
        plain = self._pack(exact, host, 10.0, radii)
        jittered = self._pack(_placement(host), host, 10.0, radii)
        self.assertEqual(sum(s is not None for s in jittered),
                         sum(s is not None for s in plain))
        self.assertEqual(len(jittered), 40)
        bands = lambda spots: {round((s - self.CENTRE).length(), 3) for s in spots if s}
        self.assertLess(len(bands(plain)), 10, "the exact rings are banded")
        self.assertGreater(len(bands(jittered)), 30, "the jittered ones are not")

    def test_a_blocked_spot_is_retried_wider_then_dropped(self):
        host = FakeHost()
        pl = _placement(host)
        # a wall disc that swallows the first ring but not the ones past it
        first = 22.0 + 14.0 + pl.pack_gap
        host.blocked = [(self.CENTRE, first + 2.0)]
        spots = self._pack(pl, host, 22.0, [14.0])
        self.assertIsNotNone(spots[0])
        self.assertGreater((spots[0] - self.CENTRE).length(), first)
        # a wall past every ring this company is allowed -> dropped, not stacked
        host.blocked = [(self.CENTRE, 2000.0)]
        self.assertEqual(self._pack(pl, host, 22.0, [14.0]), [None])

    def test_a_company_spawns_short_when_the_ground_runs_out(self):
        host = FakeHost()
        pl = _placement(host)
        radii = [10.0] * 40
        # open ground out to 120 px, wall beyond: only the inner rings exist
        host.blocked = [(self.CENTRE + pygame.Vector2(math.cos(a), math.sin(a)) * 260.0,
                         180.0) for a in [i * math.tau / 12 for i in range(12)]]
        spots = self._pack(pl, host, 10.0, radii)
        self.assertEqual(len(spots), 40)
        seated = [s for s in spots if s is not None]
        self.assertTrue(0 < len(seated) < 40, f"{len(seated)} seated")
        self._assert_legal(spots, 10.0, radii, host)
        # the shortfall is a tail of None, never a hole in the middle
        self.assertEqual(spots[:len(seated)], seated)

    def test_no_followers_is_no_pack(self):
        host = FakeHost()
        self.assertEqual(_placement(host).pack(pygame.Vector2(), 1.0, [], host.is_walkable,
                                               host.rng), [])


if __name__ == "__main__":
    unittest.main()
