"""`spawn/population.py` and the master's use of it (spawn master S4):
hibernation, the round trip, budgeted waking, residents, caps, events and
the dev switches."""
import random
import unittest

import pygame

from game import config
from game.content import get_content
from spawn import ROOM_ACTIVATED, ROOM_DORMANT, PointIndex, Population, SpawnMaster
from spawn.budget import SpawnDirector
from tests.spawn.fakehost import BRIDGE, FakeHost


def _pop(never_sleep=("arena", "boss")) -> Population:
    return Population(get_content().spawn_tables.population, never_sleep)


def _master(host, seed: int = 3) -> SpawnMaster:
    director = SpawnDirector(run_duration=600.0, rng=random.Random(seed))
    m = SpawnMaster(host, director)
    m.use_locality = True
    return m


def _spawn(host, room_x: float, n: int, owner="director", eid="chaser"):
    return [host.make_enemy(eid, room_x + 40 * i, 500 + 40 * i, 1.0, 1.0, owner)
            for i in range(n)]


class HibernateTests(unittest.TestCase):
    def test_idle_enemies_outside_the_zone_sleep_and_the_rest_stay(self):
        host = FakeHost()
        host.pursuing = set()
        pop = _pop()
        inside = _spawn(host, 300, 2, owner="director")            # island 0
        outside = _spawn(host, 2500, 3, owner="director")          # island 1
        arena = _spawn(host, 2500, 1, owner="arena")
        chasing = _spawn(host, 2500, 1, owner="director")
        host.pursuing = {id(chasing[0])}
        bridge = host.make_enemy("chaser", *BRIDGE.center, 1.0, 1.0, "director")
        slept = pop.hibernate(host, {0}, 1.0)
        self.assertEqual(slept, {1: 3})
        self.assertEqual(set(map(id, host.live)),
                         set(map(id, inside + arena + chasing + [bridge])))
        self.assertEqual(pop.dormant_in(1), 3)
        self.assertEqual(pop.total_dormant, 3)
        self.assertEqual(pop.slept, 3)
        for rec in pop.dormant[1]:
            self.assertEqual((rec.room_id, rec.slept_at, rec.owner), (1, 1.0, "director"))

    def test_the_tick_spaces_the_sweeps(self):
        host = FakeHost()
        host.pursuing = set()
        pop = _pop()
        _spawn(host, 2500, 2)
        self.assertEqual(pop.hibernate(host, {0}, 0.0), {1: 2})
        _spawn(host, 2500, 2)
        self.assertEqual(pop.hibernate(host, {0}, pop.tick * 0.5), {})   # too soon
        self.assertEqual(pop.hibernate(host, {0}, pop.tick), {1: 2})

    def test_the_record_keeps_what_matters(self):
        host = FakeHost()
        host.pursuing = set()
        pop = _pop()
        e = host.make_enemy("tank", 2500, 500, 1.7, 1.2, "director")
        e.hp, e.shield_hp, e.status = 3.5, 2.0, "burning"
        pop.hibernate(host, set(), 0.0)
        rec = pop.dormant[1][0]
        self.assertEqual((rec.enemy_id, rec.x, rec.y), ("tank", 2500.0, 500.0))
        self.assertEqual((rec.hp, rec.max_hp, rec.shield_hp), (3.5, 17.0, 2.0))
        self.assertAlmostEqual(rec.speed, 120.0)
        self.assertEqual(rec.status, "burning")
        pop.activate(1, host)
        pop.wake_some(host, PointIndex(host.layout),
                      _master(host).placement, 1.0)
        w = host.live[0]
        self.assertEqual((w.enemy_id, w.hp, w.max_hp, w.shield_hp, w.speed, w.status),
                         ("tank", 3.5, 17.0, 2.0, 120.0, "burning"))
        self.assertEqual((w.pos.x, w.pos.y), (2500.0, 500.0))


class WakeTests(unittest.TestCase):
    def _sleeping(self, n: int, host, pop):
        host.pursuing = set()
        _spawn(host, 2500, n)
        pop.hibernate(host, set(), 0.0)
        return pop

    def test_waking_is_budgeted_per_frame_and_farthest_first(self):
        host = FakeHost()
        pop = self._sleeping(20, host, _pop())
        m = _master(host)
        self.assertEqual(pop.activate(1, host), 20)
        self.assertEqual(pop.waking, 20)
        woke = pop.wake_some(host, m.index, m.placement, 1.0)
        self.assertEqual(woke, pop.wake_budget)
        self.assertEqual(len(host.live), pop.wake_budget)
        # farthest from the player came first
        d = [(e.pos - host.player).length() for e in host.live]
        self.assertEqual(d, sorted(d, reverse=True))
        while pop.waking:
            pop.wake_some(host, m.index, m.placement, 1.0)
        self.assertEqual(len(host.live), 20)
        self.assertEqual(pop.total_dormant, 0)
        self.assertEqual(pop.woken, 20)

    def test_a_blocked_spot_moves_to_the_nearest_free_point_on_its_floor(self):
        host = FakeHost()
        pop = self._sleeping(1, host, _pop())
        rec = pop.dormant[1][0]
        host.blocked = [(pygame.Vector2(rec.x, rec.y), 60.0)]
        m = _master(host)
        pop.activate(1, host)
        pop.wake_some(host, m.index, m.placement, 1.0)
        w = host.live[0]
        pts = [p for p in m.index.by_floor[(1, 0)]]
        nearest = min(pts, key=lambda p: (p.x - rec.x) ** 2 + (p.y - rec.y) ** 2)
        self.assertEqual((w.pos.x, w.pos.y), (nearest.x, nearest.y))

    def test_long_asleep_records_scatter_onto_the_islands_points(self):
        host = FakeHost()
        pop = self._sleeping(6, host, _pop())
        m = _master(host)
        pop.activate(1, host)
        pop.wake_some(host, m.index, m.placement, pop.scatter_after + 1.0)
        pts = {(p.x, p.y) for p in m.index.by_room[1]}
        for e in host.live:
            self.assertIn((e.pos.x, e.pos.y), pts)
            self.assertNotEqual((e.pos.x, e.pos.y), (e.woke_from.x, e.woke_from.y))

    def test_nowhere_to_stand_keeps_the_record_dormant(self):
        host = FakeHost()
        pop = self._sleeping(1, host, _pop())
        host.blocked = [(pygame.Vector2(3000, 2000), 5000.0)]      # island 1 is all wall
        m = _master(host)
        pop.activate(1, host)
        self.assertEqual(pop.wake_some(host, m.index, m.placement, 1.0), 0)
        self.assertEqual(pop.dormant_in(1), 1)
        self.assertEqual(host.live, [])


class MasterZoneTests(unittest.TestCase):
    def test_islands_join_and_leave_the_zone_with_events(self):
        host = FakeHost()
        host.pursuing = set()
        m = _master(host)
        m.update(0.0)
        self.assertEqual(m.active, {0})
        self.assertIn((ROOM_ACTIVATED, {"room": 0, "woke": 0, "seeded": 0}), host.events)
        # some enemies on island 1 while it is out of the zone -> they sleep
        _spawn(host, 2500, 3)
        host.elapsed = m.population.tick + 0.1
        m.update(0.0)
        self.assertIn((ROOM_DORMANT, {"room": 1, "slept": 3}), host.events)
        self.assertEqual(m.population.dormant_in(1), 3)
        # walk onto island 1: it activates, wakes them, and seeds residents
        host.player = pygame.Vector2(3000, 2000)
        host.view.center = (3000, 2000)
        host.elapsed += 1.0
        m.update(0.0)
        self.assertEqual(m.active, {0, 1})                       # 0 in grace
        ev = [p for e, p in host.events if e == ROOM_ACTIVATED and p["room"] == 1][0]
        self.assertEqual(ev["woke"], 3)
        self.assertGreater(ev["seeded"], 0)
        residents = [e for e in host.live if e.owner == "resident"]
        self.assertTrue(residents)
        self.assertTrue(all(host.room_at(e.pos).id == 1 for e in residents))
        padded = host.view.inflate(2 * m.placement.view_pad, 2 * m.placement.view_pad)
        self.assertTrue(all(not padded.collidepoint(e.pos.x, e.pos.y) for e in residents))
        # a second visit does not seed again
        self.assertIn(1, m.population.seeded)
        host.player = pygame.Vector2(1000, 2000)
        host.view.center = (1000, 2000)
        for _ in range(3):
            host.elapsed += m.locality.grace + 1
            m.update(0.0)
        host.player = pygame.Vector2(3000, 2000)
        host.view.center = (3000, 2000)
        host.elapsed += 1.0
        n_events = len(host.events)
        m.update(0.0)
        again = [p for e, p in host.events[n_events:] if e == ROOM_ACTIVATED and p["room"] == 1]
        self.assertEqual(len(again), 1)
        self.assertEqual(again[0]["seeded"], 0)                 # woke, not re-seeded
        self.assertGreater(again[0]["woke"], 0)

    def test_residents_follow_the_table(self):
        host = FakeHost()
        host.pursuing = set()
        table = get_content().spawn_tables.residents
        self.assertEqual(table["start"], 0)
        lo, hi = table["combat"]
        counts = []
        for seed in range(6):
            h = FakeHost(seed=seed)
            h.pursuing = set()
            m = _master(h, seed=seed)
            h.player = pygame.Vector2(3000, 2000)
            h.view.center = (3000, 2000)
            m.update(0.0)
            counts.append(m.population.seeded)
            packs = {e.pos.x // 1 for e in h.live if e.owner == "resident"}
            self.assertTrue(packs)
        self.assertTrue(all(1 in c for c in counts))

    def test_zone_weights_are_the_localitys(self):
        host = FakeHost()
        m = _master(host)
        host.heading = pygame.Vector2(1, 0)
        t = 0.0
        while t < m.locality.dwell + 0.3:
            t += 0.1
            host.elapsed = t
            m.update(0.0)
        self.assertEqual(m.zone(), {0: 1.0, 1: m.locality.heading_weight})

    def test_pursuers_stay_live_across_the_zone_edge(self):
        host = FakeHost()
        m = _master(host)
        chaser = _spawn(host, 2500, 1)[0]
        host.pursuing = {id(chaser)}
        for _ in range(4):
            host.elapsed += m.population.tick
            m.update(0.0)
        self.assertIn(chaser, host.live)


class CapAndSwitchTests(unittest.TestCase):
    def test_the_live_cap_clamps_the_director(self):
        host = FakeHost()
        m = _master(host)
        self.assertEqual(m.director.live_cap, config.ENEMY_LIVE_CAP)
        self.assertEqual(m.director.enemy_count_cap(10_000.0), config.ENEMY_LIVE_CAP)

    def test_the_world_cap_counts_the_dormant(self):
        host = FakeHost()
        host.pursuing = set()
        m = _master(host)
        m.world_cap = 5
        _spawn(host, 2500, 4)
        m.update(0.0)                                          # tick 0: they sleep
        self.assertEqual(m.population.total_dormant, 4)
        self.assertIsNotNone(m.spawn_at("chaser", pygame.Vector2(50, 50)))     # 4 + 1 = 5
        self.assertIsNone(m.spawn_at("chaser", pygame.Vector2(50, 50)))        # over
        self.assertIsNotNone(m.spawn_at("elite", pygame.Vector2(50, 50), owner="arena"))

    def test_frozen_stops_the_director_but_not_the_zone(self):
        host = FakeHost()
        m = _master(host)
        m.frozen = True
        host.elapsed = 100.0
        for _ in range(30):
            m.update(1.0)
        self.assertEqual(host.live, [])
        self.assertEqual(m.active, {0})

    def test_all_active_wakes_every_island(self):
        host = FakeHost()
        host.pursuing = set()
        m = _master(host)
        _spawn(host, 2500, 2)
        m.update(0.0)
        self.assertEqual(m.population.dormant_in(1), 2)
        m.all_active = True
        host.elapsed = 1.0
        m.update(0.0)
        self.assertEqual(m.active, {0, 1})
        self.assertEqual(m.zone(), {0: 1.0, 1: 1.0})
        self.assertEqual(m.population.total_dormant, 0)
        self.assertEqual(len([e for e in host.live if e.owner == "director"]), 2)

    def test_locality_off_is_the_s3_zone(self):
        host = FakeHost()
        host.pursuing = set()
        m = _master(host)
        m.use_locality = False
        _spawn(host, 2500, 2)
        for _ in range(3):
            host.elapsed += 1.0
            m.update(0.0)
        self.assertEqual(len(host.live), 2)                     # nothing sleeps
        self.assertEqual(m.zone(), {0: 1.0, 1: 1.0})


if __name__ == "__main__":
    unittest.main()
