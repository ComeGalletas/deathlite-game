"""`spawn/watchdog.py` and `SpawnMaster.recycle` (spawn master S5): what
counts as stuck or off the floor, the on-screen hold, and what a recycle
keeps, moves and gives up on."""
import random
import unittest

import pygame

from game.content import get_content
from spawn import ENEMY_RECYCLED, SpawnMaster, Watchdog
from spawn.budget import SpawnDirector
from tests.spawn.fakehost import BRIDGE, FakeHost


def _dog() -> Watchdog:
    return Watchdog(get_content().spawn_tables.watchdog)


def _master(host, seed: int = 3) -> SpawnMaster:
    m = SpawnMaster(host, SpawnDirector(run_duration=600.0, rng=random.Random(seed)))
    m.use_locality = False
    return m


def _sample(dog, host, times: int) -> list:
    """Advance the clock a sample interval at a time, collecting verdicts."""
    out = []
    for _ in range(times):
        host.elapsed += dog.sample_interval
        out.extend(dog.update(host, host.elapsed))
    return out


def _off_screen(host, x=300.0, y=300.0):
    """An enemy on island 0, well outside the view (centred at 1000, 2000)."""
    return host.make_enemy("chaser", x, y, 1.0, 1.0, "director")


class VerdictTests(unittest.TestCase):
    def test_a_moving_enemy_is_never_flagged(self):
        host, dog = FakeHost(), _dog()
        e = _off_screen(host)
        e.moving = True
        verdicts = []
        for _ in range(dog.window + 2):
            e.pos.x += e.radius * 2            # real headway each sample
            verdicts.extend(_sample(dog, host, 1))
        self.assertEqual(verdicts, [])

    def test_an_enemy_that_wants_to_move_but_cannot_is_stuck(self):
        host, dog = FakeHost(), _dog()
        e = _off_screen(host)
        e.moving = True
        early = _sample(dog, host, dog.window)          # first window fills, plus stagger
        late = _sample(dog, host, 2)
        v = (early + late)
        self.assertTrue(v, "no verdict after the window filled")
        self.assertEqual((v[0].enemy, v[0].reason, v[0].poof), (e, "stuck", False))

    def test_standing_still_on_purpose_is_not_stuck(self):
        host, dog = FakeHost(), _dog()
        e = _off_screen(host)
        e.moving = False
        self.assertEqual(_sample(dog, host, dog.window + 3), [])

    def test_an_idle_wanderer_is_not_stuck(self):
        host, dog = FakeHost(), _dog()
        e = _off_screen(host)
        e.moving = True
        host.pursuing = set()                                    # not chasing anyone
        self.assertEqual(_sample(dog, host, dog.window + 3), [])

    def test_an_attacking_enemy_is_never_flagged(self):
        host, dog = FakeHost(), _dog()
        e = _off_screen(host)
        e.moving, e.attacking = True, True
        self.assertEqual(_sample(dog, host, dog.window + 3), [])

    def test_in_contact_range_of_the_player_is_not_stuck(self):
        host, dog = FakeHost(), _dog()
        host.view = pygame.Rect(0, 0, 10, 10)                 # nothing on screen
        e = host.make_enemy("chaser", host.player.x + 20, host.player.y, 1.0, 1.0, "director")
        e.moving = True
        self.assertEqual(_sample(dog, host, dog.window + 3), [])

    def test_off_floor_and_off_world_are_immediate(self):
        host, dog = FakeHost(), _dog()
        wall = _off_screen(host, 300, 300)
        host.blocked = [(pygame.Vector2(300, 300), 50.0)]
        lost = _off_screen(host, -500, -500)
        v = _sample(dog, host, 2)
        reasons = {id(x.enemy): x.reason for x in v}
        self.assertEqual(reasons, {id(wall): "off_floor", id(lost): "off_world"})

    def test_a_bridge_is_floor(self):
        host, dog = FakeHost(), _dog()
        host.blocked = [(pygame.Vector2(BRIDGE.center), 30.0)]   # the fake floor test says no
        e = host.make_enemy("chaser", *BRIDGE.center, 1.0, 1.0, "director")
        self.assertEqual(_sample(dog, host, 2), [])

    def test_a_visible_verdict_is_held_then_poofs(self):
        host, dog = FakeHost(), _dog()
        e = host.make_enemy("chaser", host.player.x + 300, host.player.y, 1.0, 1.0, "director")
        host.blocked = [(pygame.Vector2(e.pos), 50.0)]           # embedded, on screen
        held = _sample(dog, host, 2)
        self.assertEqual(held, [])
        self.assertEqual(dog.flagged, 1)
        v = _sample(dog, host, int(dog.on_screen_wait / dog.sample_interval) + 1)
        self.assertEqual(len(v), 1)
        self.assertTrue(v[0].poof)
        self.assertEqual(v[0].reason, "off_floor")

    def test_leaving_the_view_releases_the_hold_without_a_poof(self):
        host, dog = FakeHost(), _dog()
        e = host.make_enemy("chaser", host.player.x + 300, host.player.y, 1.0, 1.0, "director")
        host.blocked = [(pygame.Vector2(e.pos), 50.0)]
        _sample(dog, host, 2)
        host.view.center = (3000, 3000)                          # camera moved away
        v = _sample(dog, host, 1)
        self.assertEqual(len(v), 1)
        self.assertFalse(v[0].poof)

    def test_tracks_are_pruned_with_the_dead(self):
        host, dog = FakeHost(), _dog()
        e = _off_screen(host)
        _sample(dog, host, 2)
        self.assertIn(id(e), dog._tracks)
        host.live.remove(e)
        _sample(dog, host, 1)
        self.assertNotIn(id(e), dog._tracks)


class RecycleTests(unittest.TestCase):
    def test_a_recycle_keeps_hp_and_lands_on_a_point_of_the_same_island(self):
        host = FakeHost()
        m = _master(host)
        e = _off_screen(host)
        e.hp, e.shield_hp = 3.0, 1.5
        m.recycle(e, "stuck", poof=False)
        self.assertNotIn(e, host.live)
        self.assertEqual(len(host.live), 1)
        w = host.live[0]
        self.assertEqual((w.hp, w.shield_hp, w.enemy_id, w.owner), (3.0, 1.5, "chaser", "director"))
        self.assertEqual(w.recycles, 1)
        pts = {(p.x, p.y) for p in m.index.by_room[0]}
        self.assertIn((w.pos.x, w.pos.y), pts)
        self.assertEqual(m.recycled, 1)
        ev, payload = host.events[-1]
        self.assertEqual((ev, payload["enemy_id"], payload["reason"]), (ENEMY_RECYCLED, "chaser", "stuck"))
        self.assertEqual(host.poofs, [])

    def test_a_poof_is_fired_where_the_body_was(self):
        host = FakeHost()
        m = _master(host)
        e = _off_screen(host, 700, 700)
        m.recycle(e, "off_floor", poof=True)
        self.assertEqual(host.poofs, [(700.0, 700.0)])

    def test_the_third_recycle_removes_the_body(self):
        host = FakeHost()
        m = _master(host)
        e = _off_screen(host)
        for _ in range(m.watchdog.max_recycles):
            m.recycle(host.live[0], "stuck", poof=False)
            self.assertEqual(len(host.live), 1)
        m.recycle(host.live[0], "stuck", poof=False)
        self.assertEqual(host.live, [])
        self.assertEqual(m.population.total_dormant, 0)
        self.assertEqual(m.discarded, 1)

    def test_an_exempt_owner_is_moved_as_the_same_object(self):
        host = FakeHost()
        m = _master(host)
        e = _off_screen(host)
        e.owner = "arena"
        m.recycle(e, "stuck", poof=False)
        self.assertIn(e, host.live)                              # identity kept
        self.assertEqual(len(host.live), 1)
        self.assertNotEqual((e.pos.x, e.pos.y), (300.0, 300.0))

    def test_nowhere_to_land_keeps_the_record_dormant(self):
        host = FakeHost()
        m = _master(host)
        e = _off_screen(host)
        host.blocked = [(pygame.Vector2(1000, 2000), 5000.0)]    # island 0 all wall
        m.recycle(e, "off_floor", poof=False)
        self.assertEqual(host.live, [])
        self.assertEqual(m.population.dormant_in(0), 1)

    def test_the_master_runs_the_watchdog_each_tick(self):
        host = FakeHost()
        m = _master(host)
        m.frozen = True                                          # no director noise
        e = _off_screen(host)
        e.moving = True
        for _ in range(int((m.watchdog.window + 3) * m.watchdog.sample_interval / 0.1)):
            host.elapsed += 0.1
            m.update(0.1)
        self.assertNotIn(e, host.live)
        self.assertEqual(m.recycled, 1)


if __name__ == "__main__":
    unittest.main()
