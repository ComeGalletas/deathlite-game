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


def _pop(never_sleep=("dummy", "boss")) -> Population:
    return Population(get_content().spawn_tables.population, never_sleep)


def _master(host, seed: int = 3) -> SpawnMaster:
    director = SpawnDirector(run_duration=600.0, rng=random.Random(seed))
    m = SpawnMaster(host, director)
    m.use_locality = True
    return m


def _spawn(host, room_x: float, n: int, owner="director", eid="skull"):
    return [host.make_enemy(eid, room_x + 40 * i, 500 + 40 * i, 1.0, 1.0, owner)
            for i in range(n)]


class HibernateTests(unittest.TestCase):
    def test_the_ring_and_the_zone_rule_each_take_their_own(self):
        """Both hibernation rules at once, with the geometry chosen so each
        body is decided by exactly one of them.

        The hero stands at (1000, 2000) and `despawn_radius` is 1400, so the
        cases that matter are: on the hero's *own*, active island but beyond
        the ring (the case that did not exist before), and on a left island
        but still inside it.
        """
        host = FakeHost()
        host.pursuing = set()
        pop = _pop()
        at = lambda x, y, owner="director": host.make_enemy(
            "skull", x, y, 1.0, 1.0, owner)

        near_own = at(1200, 2000)          # island 0, active, 200 px -> stays
        far_own = at(100, 500)             # island 0, active, 1749 px -> RING
        near_left = at(2150, 2000)         # island 1, idle, 1150 px -> ZONE
        near_chaser = at(2150, 2100)       # island 1, chasing, inside -> stays
        far_chaser = at(2600, 2000)        # island 1, chasing, 1600 px -> RING
        exempt = at(2600, 2100, owner="dummy")     # never_sleep -> stays
        bridge = host.make_enemy("skull", *BRIDGE.center, 1.0, 1.0, "director")
        host.pursuing = {id(near_chaser), id(far_chaser)}

        slept = pop.hibernate(host, {0}, 1.0)

        self.assertEqual(slept, {0: 1, 1: 2})
        self.assertEqual(set(map(id, host.live)),
                         set(map(id, [near_own, near_chaser, exempt, bridge])))
        self.assertEqual(pop.slept, 3)
        self.assertEqual(pop.ringed, 2, "the ring took the two far bodies")
        self.assertEqual(pop.dormant_in(0), 1)
        self.assertEqual(pop.dormant_in(1), 2)
        for recs in pop.dormant.values():
            for rec in recs:
                self.assertEqual((rec.slept_at, rec.owner), (1.0, "director"))

    def test_a_body_on_the_heros_own_island_sleeps_once_it_is_far_enough(self):
        """The whole point of the ring. Before it, the hero's island was
        always in the zone, so a body three screens away on it stayed fully
        simulated for the rest of the run."""
        host = FakeHost()
        host.pursuing = set()
        pop = _pop()
        ring = pop.despawn_radius
        near = host.make_enemy("skull", 1000 + ring - 50, 2000, 1.0, 1.0)
        far = host.make_enemy("skull", 1000 + ring + 50, 2000, 1.0, 1.0)
        pop.hibernate(host, {0, 1}, 1.0)       # every island active
        self.assertIn(near, host.live)
        self.assertNotIn(far, host.live)

    def test_the_ring_beats_a_chase(self):
        """owner, 2026-09-19: no pursuit exemption -- distance wins. A body
        that far cannot re-aggro anyway; the widest `aggro_range` is 640."""
        host = FakeHost()
        pop = _pop()
        chaser = host.make_enemy("skull", 1000 + pop.despawn_radius + 100, 2000,
                                 1.0, 1.0)
        host.pursuing = {id(chaser)}
        pop.hibernate(host, {0, 1}, 1.0)
        self.assertNotIn(chaser, host.live)

    def test_a_record_wakes_when_the_hero_comes_back_to_it(self):
        """The ring's other half: `activate` only fires on a zone entry, so
        a body slept on the island underfoot would otherwise be stranded."""
        host = FakeHost()
        host.pursuing = set()
        pop = _pop()
        body = host.make_enemy("skull", 1000 + pop.despawn_radius + 100, 2000,
                               1.0, 1.0)
        spot = pygame.Vector2(body.pos)
        pop.hibernate(host, {0, 1}, 1.0)
        self.assertEqual(pop.total_dormant, 1)

        # still out of reach: nothing is queued
        self.assertEqual(pop.wake_nearby(host, 2.0), 0)
        self.assertEqual(pop.waking, 0)

        # walk the hero to within the wake band
        host.player = pygame.Vector2(spot.x - pop.wake_radius + 50, spot.y)
        self.assertEqual(pop.wake_nearby(host, 3.0), 1)
        self.assertEqual(pop.waking, 1)
        self.assertEqual(pop.total_dormant, 1, "queued still counts as dormant")

    def test_the_wake_band_sits_inside_the_ring_so_nothing_flaps(self):
        """Without the gap a body on the boundary would sleep and wake on
        alternate ticks for as long as the hero stood there."""
        pop = _pop()
        self.assertLess(pop.wake_radius, pop.despawn_radius)

    def test_the_dormant_cap_drops_the_oldest_slept_first(self):
        """A rail, not a mechanism. It should never fire in play -- the
        measured peak is 1304 records for a hero touring every island, well
        under the cap -- so this drives it directly rather than trying to
        generate four thousand records."""
        from spawn.population import DormantEnemy
        pop = _pop()
        pop.dormant_cap = 5
        for i in range(8):
            rec = DormantEnemy("skull", i * 10.0, 0.0, 1.0, 1.0, 0.0, 1.0,
                               room_id=i % 2, slept_at=float(i))
            pop.dormant.setdefault(rec.room_id, []).append(rec)
        self.assertEqual(pop.total_dormant, 8)
        pop._evict()
        self.assertEqual(pop.total_dormant, 5)
        self.assertEqual(pop.evicted, 3)
        # the three oldest (slept_at 0, 1, 2) are the ones gone
        left = sorted(r.slept_at for recs in pop.dormant.values() for r in recs)
        self.assertEqual(left, [3.0, 4.0, 5.0, 6.0, 7.0])

    def test_under_the_cap_nothing_is_evicted(self):
        from spawn.population import DormantEnemy
        pop = _pop()
        for i in range(10):
            pop.dormant.setdefault(0, []).append(
                DormantEnemy("skull", 0.0, 0.0, 1.0, 1.0, 0.0, 1.0,
                             room_id=0, slept_at=float(i)))
        self.assertEqual(pop._evict(), 0)
        self.assertEqual(pop.evicted, 0)
        self.assertEqual(pop.total_dormant, 10)

    def test_a_wake_band_outside_the_ring_is_refused_outright(self):
        from spawn.population import Population
        knobs = dict(get_content().spawn_tables.population)
        knobs["wake_radius"] = knobs["despawn_radius"]
        with self.assertRaises(ValueError) as caught:
            Population(knobs)
        self.assertIn("flap", str(caught.exception))

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
        e = host.make_enemy("turtle", 2500, 500, 1.7, 1.2, "director")
        e.hp, e.shield_hp, e.status = 3.5, 2.0, "burning"
        pop.hibernate(host, set(), 0.0)
        rec = pop.dormant[1][0]
        self.assertEqual((rec.enemy_id, rec.x, rec.y), ("turtle", 2500.0, 500.0))
        self.assertEqual((rec.hp, rec.max_hp, rec.shield_hp), (3.5, 17.0, 2.0))
        self.assertAlmostEqual(rec.speed, 120.0)
        self.assertEqual(rec.status, "burning")
        pop.activate(1, host)
        pop.wake_some(host, PointIndex(host.layout),
                      _master(host).placement, 1.0)
        w = host.live[0]
        self.assertEqual((w.enemy_id, w.hp, w.max_hp, w.shield_hp, w.speed, w.status),
                         ("turtle", 3.5, 17.0, 2.0, 120.0, "burning"))
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
        # S11: seated by the distance band around the hero, never the view.
        keep = m.placement.starved_min_distance
        self.assertTrue(all((e.pos - host.player).length() >= keep for e in residents))
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
        # `combat` may be a [lo, hi] span or a flat count -- both are valid
        # table shapes and it has been each of them (it became a flat 1 on
        # 2026-09-18, when residents started meaning whole companies).
        spec = table["combat"]
        lo, hi = spec if isinstance(spec, list) else (spec, spec)
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

    def test_pursuers_stay_live_across_the_zone_edge_while_inside_the_ring(self):
        """The zone rule still exempts a chase -- but only inside the ring.
        Beyond it distance wins (`test_the_ring_beats_a_chase`), so the
        chaser here is placed on the left island *within* the ring, which is
        what the exemption was always for: the fight the player is watching
        as they cross a bridge."""
        host = FakeHost()
        m = _master(host)
        ring = m.population.despawn_radius
        chaser = host.make_enemy("skull", 1000 + ring - 200, 2000, 1.0, 1.0)
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

    def test_the_world_cap_no_longer_counts_the_dormant(self):
        """Reversed on 2026-09-18. Dormant records used to come off
        `world_cap`, so a run that had banked records across several islands
        throttled live spawning everywhere -- which is precisely what the
        ring now produces, since its whole job is to turn distant bodies
        into records. A sleeping body is a ledger entry, not a claim on the
        field, and only live bodies are counted."""
        host = FakeHost()
        host.pursuing = set()
        m = _master(host)
        m.frozen = True                      # no companies; the point is the cap
        m.world_cap = 5
        _spawn(host, 2500, 4)
        host.elapsed += m.population.tick
        m.update(0.0)
        self.assertEqual(m.population.total_dormant, 4, "the ring slept them")
        self.assertEqual(host.live_count(), 0)
        # All five slots are still there: the four records claim none of them.
        made = [m.spawn_at("skull", pygame.Vector2(1000, 2000)) for _ in range(5)]
        self.assertTrue(all(e is not None for e in made), made)
        self.assertIsNone(m.spawn_at("skull", pygame.Vector2(1000, 2000)))
        self.assertIsNotNone(m.spawn_at("bear", pygame.Vector2(1000, 2000),
                                        owner="dev"))

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
        # G3: the first company is chosen and placed immediately, so a bare
        # `update` now seats one. These two tests are about the zone and
        # hibernation, so the director is frozen out of them -- `frozen`
        # stops companies and residents without stopping the zone tick.
        m.frozen = True
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
        m.frozen = True                 # see the note above
        _spawn(host, 2500, 2)
        for _ in range(3):
            host.elapsed += 1.0
            m.update(0.0)
        self.assertEqual(len(host.live), 2)                     # nothing sleeps
        self.assertEqual(m.zone(), {0: 1.0, 1: 1.0})


if __name__ == "__main__":
    unittest.main()
