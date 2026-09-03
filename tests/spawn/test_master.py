"""`spawn/master.py` against a stub host (spawn master S3): packs land
together on one vetted point, the cap holds for every entry point, debt
is kept and retried, templates roll, modifiers scale the cadence, the
event fires, and a world with no points falls back."""
import random
import unittest

import pygame

from game import config
from game.content import get_content
from spawn import ENEMY_SPAWNED, SpawnMaster
from spawn.budget import SpawnDirector
from tests.spawn.fakehost import FakeHost


def _master(host, seed: int = 3, duration: float = 600.0) -> SpawnMaster:
    director = SpawnDirector(run_duration=duration, rng=random.Random(seed))
    return SpawnMaster(host, director)


def _run(master, host, seconds: float, dt: float = 1 / 30) -> None:
    t = 0.0
    while t < seconds:
        master.update(dt)
        t += dt
        host.elapsed = t


class PackTests(unittest.TestCase):
    def test_the_director_pack_lands_together_on_a_point(self):
        host = FakeHost()
        m = _master(host)
        host.elapsed = 400.0                        # late: packs of 2-4
        m.update(1.0)                               # one tick past the timer
        self.assertTrue(host.live)
        points = {(p.x, p.y) for p in host.layout.spawn_points}
        leader = host.live[0]
        self.assertIn((leader.pos.x, leader.pos.y), points)
        reach = 2 * (26.0 + 26.0 + m.placement.ring_gap) * 1.6
        for e in host.live[1:]:
            self.assertLess((e.pos - leader.pos).length(), reach)
            self.assertNotIn((e.pos.x, e.pos.y), points)      # followers ring, not stack
        self.assertEqual(m.spawned, len(host.live))

    def test_every_spawn_is_off_screen_and_off_the_player(self):
        host = FakeHost()
        m = _master(host)
        _run(m, host, 60.0)
        self.assertGreater(len(host.live), 10)
        pad = m.placement.view_pad
        padded = host.view.inflate(2 * pad, 2 * pad)
        for e in host.live:
            self.assertFalse(padded.collidepoint(e.pos.x, e.pos.y))

    def test_stat_multipliers_come_from_the_director(self):
        host = FakeHost()
        m = _master(host)
        host.elapsed = 300.0
        e = m.spawn_at("chaser", pygame.Vector2(50, 50))
        hp, spd = m.director.stat_multipliers(300.0)
        self.assertEqual((e.hp_mult, e.spd_mult), (hp, spd))

    def test_the_event_names_enemy_owner_and_room(self):
        host = FakeHost()
        m = _master(host)
        m.spawn_at("chaser")
        ev, payload = host.events[-1]
        self.assertEqual(ev, ENEMY_SPAWNED)
        self.assertEqual(payload["enemy_id"], "chaser")
        self.assertEqual(payload["owner"], "direct")
        self.assertIn(payload["room"], (0, 1))
        m.spawn_at("chaser", pygame.Vector2(10, 10), owner="summon")
        self.assertEqual(host.events[-1][1]["owner"], "summon")
        self.assertIsNone(host.events[-1][1]["room"])


class CapTests(unittest.TestCase):
    def test_every_entry_point_stops_at_the_cap(self):
        host = FakeHost()
        m = _master(host)
        cap = m.director.enemy_count_cap(0.0)
        for _ in range(cap):
            host.make_enemy("chaser", 5, 5, 1.0, 1.0)
        self.assertIsNone(m.spawn_at("chaser"))
        self.assertIsNone(m.spawn_at("chaser", pygame.Vector2(1, 1)))
        self.assertEqual(m.spawn_group("husk_pack"), [])
        _run(m, host, 5.0)
        self.assertEqual(len(host.live), cap)

    def test_scripted_owners_are_always_seated(self):
        host = FakeHost()
        m = _master(host)
        cap = m.director.enemy_count_cap(0.0)
        for _ in range(cap):
            host.make_enemy("chaser", 5, 5, 1.0, 1.0)
        self.assertIsNone(m.spawn_at("elite", pygame.Vector2(1, 1)))          # direct: refused
        self.assertIsNone(m.spawn_at("elite", pygame.Vector2(1, 1), owner="summon"))
        arena = m.spawn_at("elite", pygame.Vector2(1, 1), owner="arena")     # scripted: seated
        self.assertIsNotNone(arena)
        self.assertEqual(len(host.live), cap + 1)
        pack = m.spawn_group("warband", at=pygame.Vector2(500, 500), owner="arena")
        self.assertGreaterEqual(len(pack), 3)                                # whole pack lands
        self.assertEqual(get_content().spawn_tables.owners["cap_exempt"], ["arena", "dev"])
        self.assertIsNotNone(m.spawn_at("chaser", pygame.Vector2(1, 1), owner="dev"))

    def test_a_pack_spawns_short_rather_than_over_the_cap(self):
        host = FakeHost()
        m = _master(host)
        cap = m.director.enemy_count_cap(0.0)
        for _ in range(cap - 1):
            host.make_enemy("chaser", 5, 5, 1.0, 1.0)
        made = m.spawn_group("swarm")                # 1 + 4..6 wanted
        self.assertEqual(len(made), 1)
        self.assertEqual(len(host.live), cap)


class DebtTests(unittest.TestCase):
    def test_an_unseatable_pack_is_kept_and_retried(self):
        host = FakeHost()
        host.view = pygame.Rect(-100, -100, 4200, 4200)     # everything on screen
        m = _master(host)
        host.elapsed = 100.0
        m.update(2.0)
        self.assertEqual(host.live, [])
        self.assertEqual(m.debt, 1)
        self.assertEqual(m.deferred, 1)
        host.view = pygame.Rect(0, 0, 1000, 600)
        host.view.center = (1000, 2000)
        m.update(0.0)                               # the retry seats it
        self.assertEqual(m.debt, 0)
        self.assertTrue(host.live)

    def test_debt_is_capped(self):
        host = FakeHost()
        host.view = pygame.Rect(-100, -100, 4200, 4200)
        m = _master(host)
        host.elapsed = 500.0
        for _ in range(200):
            m.update(1.0)
        self.assertLessEqual(m.debt, 20)


class GroupAndModifierTests(unittest.TestCase):
    def test_a_template_rolls_its_followers_in_span(self):
        host = FakeHost()
        m = _master(host)
        made = m.spawn_group("warband")
        ids = [e.enemy_id for e in made]
        self.assertEqual(ids[0], "elite")
        self.assertIn(ids.count("chaser"), (2, 3))
        self.assertIn(ids.count("ranged"), (0, 1))
        self.assertEqual(host.events[-1][1]["owner"], "group")

    def test_a_template_at_a_position_lands_there(self):
        host = FakeHost()
        m = _master(host)
        made = m.spawn_group("husk_pack", at=pygame.Vector2(300, 300), owner="arena")
        self.assertEqual((made[0].pos.x, made[0].pos.y), (300.0, 300.0))
        self.assertTrue(all(e is not None for e in made))
        self.assertEqual(host.events[-1][1]["owner"], "arena")

    def test_a_group_that_prefers_upper_lands_upper(self):
        def floor_of(x, y):
            return 1 if y < 2000 else 0
        from tests.spawn.fakehost import ROOM0, ROOM1, grid_points
        pts = grid_points(0, ROOM0, floor_of=floor_of) + grid_points(1, ROOM1, floor_of=floor_of)
        pts = [p._replace(tags=frozenset({"upper"}) if p.floor == 1 else frozenset()) for p in pts]
        host = FakeHost(points=pts)
        host.player = pygame.Vector2(1000, 3000)          # on floor 0, view far from floor 1
        host.view.center = (1000, 3000)
        m = _master(host)
        # with the weighting only, both floors are possible; make it certain
        m.placement.prefer_weight = 1e9
        made = m.spawn_group("artillery")
        self.assertLess(made[0].pos.y, 2000)

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
        fast.set_modifier("test", 2.0)
        n_slow = spawned_in(slow, slow_host, 30.0)
        n_fast = spawned_in(fast, fast_host, 30.0)
        self.assertGreater(n_fast, n_slow * 1.6)


class FallbackTests(unittest.TestCase):
    def test_a_world_with_no_points_places_through_the_fallback(self):
        host = FakeHost(points=[])
        host.fallback = pygame.Vector2(123, 456)
        m = _master(host)
        e = m.spawn_at("chaser")
        self.assertEqual((e.pos.x, e.pos.y), (123.0, 456.0))
        host.elapsed = 100.0
        m.update(2.0)
        self.assertGreater(len(host.live), 1)
        self.assertEqual(m.debt, 0)

    def test_no_points_and_no_fallback_spawns_nothing(self):
        host = FakeHost(points=[])
        m = _master(host)
        self.assertIsNone(m.spawn_at("chaser"))
        self.assertEqual(host.live, [])

    def test_the_zone_is_the_players_island_and_its_neighbours(self):
        host = FakeHost()
        m = _master(host)
        self.assertEqual(m.zone(), {0: 1.0, 1: 1.0})
        host.player = pygame.Vector2(-50, -50)              # off every island
        self.assertEqual(m.zone(), {0: 1.0, 1: 1.0})        # every island with points


if __name__ == "__main__":
    unittest.main()
