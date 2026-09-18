"""`spawn/master.py` against a stub host (spawn master S3): packs land
together on one vetted point, the cap holds for every entry point, debt
is kept and retried, templates roll, modifiers scale the cadence, the
event fires, and a world with no points falls back."""
import math
import random
import unittest

import pygame

from game.content import get_content
from spawn import ENEMY_SPAWNED, SpawnMaster
from spawn.budget import SpawnDirector
from tests.spawn.fakehost import FakeHost
from world.layout import SpawnPoint


def _master(host, seed: int = 3, duration: float = 600.0) -> SpawnMaster:
    director = SpawnDirector(run_duration=duration, rng=random.Random(seed))
    return SpawnMaster(host, director)


def _reach(master, biggest: float = 26.0, followers: int = 3) -> float:
    """How far from its leader the furthest body of a director pack can sit.
    The packer's own bound -- the ring limit it derives for the company, plus
    one cell of jitter -- rather than a number copied out of it."""
    pl = master.placement
    start = biggest + biggest + pl.pack_gap
    step = 2.0 * biggest + pl.pack_gap
    limit = min(pl.pack_max_radius,
                max(start + step, start + step * pl.pack_spread * math.sqrt(followers)))
    return limit + pl.pack_jitter * step


def _run(master, host, seconds: float, dt: float = 1 / 30) -> None:
    t = 0.0
    while t < seconds:
        master.update(dt)
        t += dt
        host.elapsed = t


def _settle(master, host) -> None:
    """Let a committed company finish materialising (G0b) without letting
    the director emit another one.

    `frozen` is the run's own "emit nothing new" switch, and a release
    happens before that gate because the company has already been decided
    and paid for. A zero `dt` would not do: the director's timer is already
    negative after a tick, so it fires again whatever `dt` says.
    """
    was, master.frozen = master.frozen, True
    host.elapsed += master.company_stagger
    master.update(0.0)
    master.frozen = was


class PackTests(unittest.TestCase):
    def test_the_director_pack_lands_together_on_a_point(self):
        host = FakeHost()
        m = _master(host)
        host.elapsed = 400.0                        # late: packs of 2-4
        m.update(1.0)                               # one tick past the timer
        self.assertTrue(host.live)
        company = len(host.live) + m.pending
        self.assertGreater(company, 1, "a late pack has followers")
        _settle(m, host)
        self.assertEqual(m.pending, 0)
        self.assertEqual(len(host.live), company)
        points = {(p.x, p.y) for p in host.layout.spawn_points}
        leader = host.live[0]
        self.assertIn((leader.pos.x, leader.pos.y), points)
        reach = _reach(m)
        for e in host.live[1:]:
            self.assertLess((e.pos - leader.pos).length(), reach)
            self.assertNotIn((e.pos.x, e.pos.y), points)      # followers pack, not stack
        self.assertEqual(m.spawned, len(host.live))

    def test_no_spawn_lands_on_top_of_the_player(self):
        """The guarantee after the relaxation ladder (owner, 2026-09-12),
        restated for S11 (owner, 2026-09-15): the camera is not part of it.

        Every rung is a distance band around the hero, and the starved
        keep-away is the smallest of them, so every arrival -- leaders on
        their points, followers on the ring around them -- is at least that
        far from the player, wherever the view is.
        """
        host = FakeHost()
        m = _master(host)
        host.view = pygame.Rect(3000, 3000, 1000, 600)       # looking elsewhere
        _run(m, host, 60.0)
        self.assertGreater(len(host.live), 10)
        keep = m.placement.starved_min_distance
        ring = _reach(m)                   # how far a follower can sit from its leader
        for e in host.live:
            self.assertGreaterEqual((e.pos - host.player).length(), keep - ring,
                                    f"{e.pos} is inside the keep-away")

    def test_a_quiet_zone_keeps_spawning(self):
        """The reason the ladder exists: a player who does not move used to
        starve the strict rung -- its points are all either on cooldown or
        inside the keep-away -- and most packs became debt."""
        host = FakeHost()
        m = _master(host)
        _run(m, host, 60.0)
        moving = len(host.live)
        still = FakeHost()
        still.view = pygame.Rect(-100, -100, 4200, 4200)   # the whole zone in view
        m2 = _master(still)
        _run(m2, still, 60.0)
        self.assertGreater(len(still.live), 10)
        self.assertGreater(len(still.live), moving * 0.5)

    def test_stat_multipliers_come_from_the_director(self):
        host = FakeHost()
        m = _master(host)
        host.elapsed = 300.0
        e = m.spawn_at("skull", pygame.Vector2(50, 50))
        hp, spd = m.director.stat_multipliers(300.0)
        self.assertEqual((e.hp_mult, e.spd_mult), (hp, spd))

    def test_the_event_names_enemy_owner_and_room(self):
        host = FakeHost()
        m = _master(host)
        m.spawn_at("skull")
        ev, payload = host.events[-1]
        self.assertEqual(ev, ENEMY_SPAWNED)
        self.assertEqual(payload["enemy_id"], "skull")
        self.assertEqual(payload["owner"], "direct")
        self.assertIn(payload["room"], (0, 1))
        m.spawn_at("skull", pygame.Vector2(10, 10), owner="summon")
        self.assertEqual(host.events[-1][1]["owner"], "summon")
        self.assertIsNone(host.events[-1][1]["room"])


class StaggerTests(unittest.TestCase):
    """`company_stagger` (G0b, owner 2026-09-17): a company materialises
    over a window instead of appearing on one frame. Everything that decides
    the company -- its point, its packed spots, the cap it pays -- still
    happens when it is seated, so the only difference is *when* each body
    shows up. 0 is a supported value, not a degenerate one."""

    def _commit(self, stagger: float):
        host = FakeHost()
        m = _master(host)
        m.company_stagger = stagger
        host.elapsed = 400.0                       # late: packs of 2-4
        m.update(1.0)
        return host, m

    def test_a_company_lands_on_one_frame_at_zero(self):
        host, m = self._commit(0.0)
        self.assertEqual(m.pending, 0)
        self.assertGreater(len(host.live), 1)
        self.assertEqual(m.spawned, len(host.live))

    def test_the_same_company_arrives_at_the_same_spots_just_later(self):
        # The owner's requirement in one assertion: staggering changes the
        # clock and nothing else. Same seed, same world, same company.
        at_once, m0 = self._commit(0.0)
        spread, m1 = self._commit(0.35)
        self.assertGreater(m1.pending, 0, "the followers are still waiting")
        self.assertEqual(len(spread.live), 1, "only the leader has landed")
        _settle(m1, spread)
        self.assertEqual(m1.pending, 0)
        seats = lambda live: [(e.enemy_id, e.pos.x, e.pos.y) for e in live]
        self.assertEqual(seats(spread.live), seats(at_once.live))

    def test_the_bodies_arrive_spread_across_the_window(self):
        host, m = self._commit(0.35)
        waiting = m.pending
        self.assertGreater(waiting, 1)
        m.frozen = True                            # release only, emit nothing
        seen = [len(host.live)]
        for _ in range(8):
            host.elapsed += 0.35 / 7
            m.update(0.0)
            seen.append(len(host.live))
        self.assertEqual(m.pending, 0)
        self.assertEqual(seen[-1], waiting + 1)
        # not all on one frame: the count climbed more than once
        steps = sum(1 for a, b in zip(seen, seen[1:]) if b > a)
        self.assertGreater(steps, 1, f"arrived in one jump: {seen}")

    def test_each_body_lands_once_and_the_queue_empties(self):
        host, m = self._commit(0.35)
        m.frozen = True
        for _ in range(20):
            host.elapsed += 0.05
            m.update(0.0)
        self.assertEqual(m.pending, 0, "no body is left stranded")
        self.assertEqual(m.spawned, len(host.live), "and none landed twice")
        spots = [(e.pos.x, e.pos.y) for e in host.live]
        self.assertEqual(len(set(spots)), len(spots), "two bodies share a spot")

    def test_a_waiting_body_already_counts_against_the_cap(self):
        # The gate is paid once, when the company is seated. A body still in
        # flight has to count as live or the run would overshoot the cap by
        # the size of every company in the air.
        host = FakeHost()
        m = _master(host)
        cap = m.director.enemy_count_cap(0.0)
        _run(m, host, 40.0)
        self.assertGreater(m.spawned, 10)
        self.assertLessEqual(len(host.live) + m.pending, cap)

    def test_dropping_a_company_stops_the_rest_from_landing(self):
        host, m = self._commit(0.35)
        waiting, landed = m.pending, len(host.live)
        self.assertEqual(m.drop_pending(), waiting)
        self.assertEqual(m.pending, 0)
        m.frozen = True
        for _ in range(10):
            host.elapsed += 0.1
            m.update(0.0)
        self.assertEqual(len(host.live), landed)

    def test_a_frozen_run_still_finishes_a_committed_company(self):
        # `frozen` is the dev switch for "emit nothing new". A company whose
        # cap has been paid and whose spots are reserved is not new, so it
        # finishes rather than being stranded until the run thaws.
        host, m = self._commit(0.35)
        waiting = m.pending
        self.assertGreater(waiting, 0)
        m.frozen = True
        host.elapsed += m.company_stagger
        m.update(1.0)                              # a real tick, still frozen
        self.assertEqual(m.pending, 0)
        self.assertEqual(m.spawned, waiting + 1)


class CapTests(unittest.TestCase):
    def test_every_entry_point_stops_at_the_cap(self):
        host = FakeHost()
        m = _master(host)
        cap = m.director.enemy_count_cap(0.0)
        for _ in range(cap):
            host.make_enemy("skull", 5, 5, 1.0, 1.0)
        self.assertIsNone(m.spawn_at("skull"))
        self.assertIsNone(m.spawn_at("skull", pygame.Vector2(1, 1)))
        self.assertEqual(m.spawn_group("dark"), [])
        _run(m, host, 5.0)
        self.assertEqual(len(host.live), cap)

    def test_scripted_owners_are_always_seated(self):
        host = FakeHost()
        m = _master(host)
        cap = m.director.enemy_count_cap(0.0)
        for _ in range(cap):
            host.make_enemy("skull", 5, 5, 1.0, 1.0)
        self.assertIsNone(m.spawn_at("bear", pygame.Vector2(1, 1)))          # direct: refused
        self.assertIsNone(m.spawn_at("bear", pygame.Vector2(1, 1), owner="summon"))
        scripted = m.spawn_at("bear", pygame.Vector2(1, 1), owner="dev")    # scripted: seated
        self.assertIsNotNone(scripted)
        self.assertEqual(len(host.live), cap + 1)
        pack = m.spawn_group("wild_beasts", at=pygame.Vector2(500, 500), owner="dev")
        self.assertGreaterEqual(len(pack), 3)                                # whole pack lands
        # The exact list, deliberately: the cap is a performance guard, so an
        # owner that bypasses it has to be added on purpose and seen here.
        # `dummy` is the dev menu's training dummy (`training_dummy_journal.md`).
        # `arena` left the list when the elite arena was removed (2026-09-12,
        # `placement_review_journal.md`): nothing produces that owner now.
        self.assertEqual(get_content().spawn_tables.owners["cap_exempt"],
                         ["dev", "dummy"])
        self.assertIsNotNone(m.spawn_at("skull", pygame.Vector2(1, 1), owner="dev"))

    def test_a_pack_spawns_short_rather_than_over_the_cap(self):
        host = FakeHost()
        m = _master(host)
        cap = m.director.enemy_count_cap(0.0)
        for _ in range(cap - 1):
            host.make_enemy("skull", 5, 5, 1.0, 1.0)
        made = m.spawn_group("swarm")                # 20..30 wanted
        self.assertEqual(len(made), 1)
        self.assertEqual(len(host.live), cap)


class DebtTests(unittest.TestCase):
    def test_an_unseatable_pack_is_kept_and_retried(self):
        # Unseatable now means unseatable at every rung of the ladder: an
        # on-screen view no longer refuses a spawn on its own, so the points
        # are put inside the starved keep-away instead.
        host = FakeHost(points=[SpawnPoint(0, 0, 1000.0, 2000.0 + d)
                                for d in (0.0, 60.0, 120.0)])
        host.view = pygame.Rect(-100, -100, 4200, 4200)
        m = _master(host)
        host.elapsed = 100.0
        m.update(2.0)
        self.assertEqual(host.live, [])
        self.assertEqual(m.debt, 1)
        self.assertEqual(m.deferred, 1)
        host.player = pygame.Vector2(1000, 100)     # the points are far now
        m.update(0.0)                               # the retry seats it
        self.assertEqual(m.debt, 0)
        self.assertTrue(host.live)

    def test_debt_is_capped(self):
        host = FakeHost(points=[SpawnPoint(0, 0, 1000.0, 2000.0 + d)
                                for d in (0.0, 60.0, 120.0)])
        host.view = pygame.Rect(-100, -100, 4200, 4200)
        m = _master(host)
        host.elapsed = 500.0
        for _ in range(200):
            m.update(1.0)
        self.assertLessEqual(m.debt, 20)


class CompanyTests(unittest.TestCase):
    """G2: a company is one social group -- a count rolled in the group's
    `common_range`, drawn by weight, plus the elites its ladder allows.

    The leader+followers templates these tests used to drive are gone; a
    company has no leader, only a body that happens to be seated first.
    `test_a_group_that_prefers_upper_lands_upper` went with them: `prefer`
    was a per-template placement hint and no group declares one now, so
    there is nothing left to assert. The `prefer` machinery in `Placement`
    is untouched and still covered by `test_placement.py`.
    """

    def test_a_company_is_sized_in_its_span_and_drawn_from_its_group(self):
        host = FakeHost()
        m = _master(host)
        members = set(m.roster.get("dark").commons)
        lo, hi = m.roster.get("dark").common_range
        for _ in range(12):
            ids = m.compose("dark")
            self.assertLessEqual(lo, len(ids))
            self.assertLessEqual(len(ids), hi)
            self.assertTrue(set(ids) <= members, set(ids) - members)

    def test_an_elite_company_carries_the_ladder_count(self):
        host = FakeHost()
        m = _master(host)
        g = m.roster.get("goblin")
        commons, elites = set(g.commons), set(g.elites)
        lo, hi = g.common_range
        for steps in (0, 1, 4, 99):
            ids = m.compose("goblin", steps=steps)
            want = g.elite_count(steps)
            got = sum(1 for e in ids if e in elites)
            with self.subTest(steps=steps):
                self.assertEqual(got, want)
                self.assertLessEqual(lo, len(ids) - got)
                self.assertLessEqual(len(ids) - got, hi)
                self.assertTrue(set(ids) <= commons | elites)

    def test_a_common_group_never_produces_an_elite(self):
        host = FakeHost()
        m = _master(host)
        every_elite = set()
        for name in m.roster.names(elite=True):
            every_elite |= set(m.roster.get(name).elites)
        for name in m.roster.names(elite=False):
            for steps in (0, 99):
                ids = m.compose(name, steps=steps)
                self.assertEqual(set(ids) & every_elite, set(), f"{name} @ {steps}")

    def test_the_elites_are_not_all_left_on_the_rim(self):
        """`_place_pack` seats the first id on the point and packs the rest
        outward, so an unshuffled company would put every elite outside.
        Over many companies the elites must appear at many positions."""
        host = FakeHost()
        m = _master(host)
        elites = set(m.roster.get("goblin").elites)
        seen = set()
        for _ in range(40):
            ids = m.compose("goblin", steps=3)
            seen.update(i for i, e in enumerate(ids) if e in elites)
        self.assertGreater(len(seen), 6, f"elites clustered at {sorted(seen)}")
        self.assertIn(True, [i < 3 for i in seen], "no elite ever seated early")

    def test_a_company_lands_together_and_reports_its_owner(self):
        host = FakeHost()
        m = _master(host)
        made = m.spawn_group("dark", at=pygame.Vector2(300, 300), owner="dev")
        self.assertEqual((made[0].pos.x, made[0].pos.y), (300.0, 300.0))
        self.assertTrue(all(e is not None for e in made))
        self.assertEqual(host.events[-1][1]["owner"], "dev")

    def test_the_same_seed_composes_the_same_company(self):
        a, b = FakeHost(seed=9), FakeHost(seed=9)
        ma, mb = _master(a), _master(b)
        self.assertEqual(ma.compose("wild_beasts", steps=2),
                         mb.compose("wild_beasts", steps=2))

    def test_modifiers_multiply_and_scale_the_cadence(self):
        host = FakeHost()
        m = _master(host)
        base = m.pacing.base                                 # the standing x5 (S9)
        self.assertEqual(m.pressure, base)
        m.set_modifier("dev", 2.0)
        m.set_modifier("blessing", 1.5)
        self.assertAlmostEqual(m.pressure, base * 3.0)
        self.assertEqual(m.modifiers, {"dev": 2.0, "blessing": 1.5})
        m.clear_modifier("dev")
        self.assertAlmostEqual(m.pressure, base * 1.5)
        m.clear_modifier("blessing")
        # twice the pressure -> about twice the spawns over the same window,
        # with the crowd trimmed each tick so the live cap never decides it
        # (at the standing base of 5 both runs would fill the cap in seconds)
        def spawned_in(master, host, seconds: float) -> int:
            t = 0.0
            while t < seconds:
                master.update(1 / 30)
                t += 1 / 30
                host.elapsed = t
                host.live = host.live[-5:]
            return master.spawned
        slow_host, fast_host = FakeHost(seed=2), FakeHost(seed=2)
        slow, fast = _master(slow_host, seed=8), _master(fast_host, seed=8)
        # From base 1: the shipped base is high enough that x2 on top of it
        # saturates the director (one pack per `update` is its ceiling), so
        # the doubling would not show.
        slow.pacing.base = fast.pacing.base = 1.0
        fast.set_modifier("test", 2.0)
        n_slow = spawned_in(slow, slow_host, 30.0)
        n_fast = spawned_in(fast, fast_host, 30.0)
        self.assertGreater(n_fast, n_slow * 1.6)


class FallbackTests(unittest.TestCase):
    def test_a_world_with_no_points_places_through_the_fallback(self):
        host = FakeHost(points=[])
        host.fallback = pygame.Vector2(123, 456)
        m = _master(host)
        e = m.spawn_at("skull")
        self.assertEqual((e.pos.x, e.pos.y), (123.0, 456.0))
        host.elapsed = 100.0
        m.update(2.0)
        self.assertGreater(len(host.live), 1)
        self.assertEqual(m.debt, 0)

    def test_no_points_and_no_fallback_spawns_nothing(self):
        host = FakeHost(points=[])
        m = _master(host)
        self.assertIsNone(m.spawn_at("skull"))
        self.assertEqual(host.live, [])

    def test_the_zone_is_the_players_island_and_its_neighbours(self):
        host = FakeHost()
        m = _master(host)
        self.assertEqual(m.zone(), {0: 1.0, 1: 1.0})
        host.player = pygame.Vector2(-50, -50)              # off every island
        self.assertEqual(m.zone(), {0: 1.0, 1: 1.0})        # every island with points


if __name__ == "__main__":
    unittest.main()


class TrainingDummyOwnerTests(unittest.TestCase):
    """The `dummy` owner is exempt from both the live cap and hibernation.

    `dev` is cap-exempt but sleepable, and a hibernated dummy leaves
    `host.live_enemies()` while still alive -- the weapons stop reaching it and
    the DPS meter flatlines with nothing on screen to say why. Measured before
    the fix: the dummy slept nine seconds into a twenty-second bench.
    """

    def test_the_owner_is_exempt_from_the_cap_and_from_sleeping(self):
        owners = get_content().spawn_tables.owners
        self.assertIn("dummy", owners["cap_exempt"])
        self.assertIn("dummy", owners["never_sleep"])

    def test_the_plain_dev_owner_still_sleeps(self):
        """Deliberate: the F2 key and the "Spawn enemy" page pile bodies up for
        stress tests, and hibernating those is the behaviour under test there."""
        owners = get_content().spawn_tables.owners
        self.assertIn("dev", owners["cap_exempt"])
        self.assertNotIn("dev", owners["never_sleep"])

    def test_hibernation_leaves_a_dummy_alone(self):
        host = FakeHost()
        m = _master(host)
        dummy = m.spawn_at("training_dummy", pygame.Vector2(1, 1), owner="dummy")
        self.assertIsNotNone(dummy)
        other = m.spawn_at("skull", pygame.Vector2(1, 1), owner="dev")
        self.assertIsNotNone(other)
        # Hibernate with no island active: everything sleepable goes.
        m.population._next_tick = 0.0
        m.population.hibernate(host, active=set(), now=999.0)
        self.assertIn(dummy, list(host.live_enemies()))
