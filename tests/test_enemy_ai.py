"""Milestone 4: enemy variant behaviors (spec 3.3 / 8)."""
import random
import unittest

import pygame

from entities.enemy import Enemy
from entities.enemy_ai import BEHAVIORS, EnemyContext
from game.content import get_content


def ctx(dt=1 / 30, player=(0, 0), **cb):
    calls = {"fired": [], "summoned": [], "exploded": []}
    base = dict(
        dt=dt, player_pos=pygame.Vector2(*player), player=object(),
        rng=random.Random(0),
        fire_projectile=lambda **kw: calls["fired"].append(kw),
        summon=lambda eid, pos, n: calls["summoned"].append((eid, n)),
        explosion=lambda pos, r, d: calls["exploded"].append((r, d)),
    )
    base.update(cb)
    return EnemyContext(**base), calls


def make(enemy_id, x=200, y=0):
    return Enemy(enemy_id, get_content().enemy(enemy_id), x, y)


class ShieldTests(unittest.TestCase):
    def test_shield_absorbs_before_hp(self):
        e = make("shielded")
        shield = e.shield_hp
        hp = e.hp
        e.take_damage(shield - 5)
        self.assertAlmostEqual(e.shield_hp, 5)
        self.assertEqual(e.hp, hp)  # nothing bled through

    def test_overkill_spills_into_hp(self):
        e = make("shielded")
        e.take_damage(e.shield_hp + 10)
        self.assertEqual(e.shield_hp, 0)
        self.assertAlmostEqual(e.hp, e.max_hp - 10)


class BehaviorTests(unittest.TestCase):
    def test_chaser_moves_toward_player(self):
        e = make("chaser")
        c, _ = ctx(player=(0, 0))
        e.update(c)
        self.assertLess(e.pos.x, 200)  # moved left toward origin

    def test_ranged_enemy_fires_projectile(self):
        e = make("ranged")
        e.pos = pygame.Vector2(150, 0)  # inside firing range
        fired = []
        for _ in range(200):
            c, calls = ctx(dt=1 / 30, player=(0, 0),
                           fire_projectile=lambda **kw: fired.append(kw))
            e.update(c)
        self.assertTrue(fired)
        self.assertIn("damage", fired[0])

    def test_exploder_dies_when_it_reaches_player(self):
        e = make("exploder")
        e.pos = pygame.Vector2(10, 0)
        c, _ = ctx(player=(0, 0))
        e.update(c)
        self.assertFalse(e.alive)

    def test_summoner_spawns_brood_on_interval(self):
        e = make("summoner")
        summoned = []
        for _ in range(300):
            c, _ = ctx(dt=1 / 30, player=(0, 0),
                       summon=lambda eid, pos, n: summoned.append((eid, n)))
            e.update(c)
        self.assertTrue(summoned)
        self.assertEqual(summoned[0][0], "swarm")

    def test_brute_telegraphs_then_slams(self):
        e = make("brute")
        e.pos = pygame.Vector2(40, 0)  # within slam_range
        exploded = []
        saw_telegraph = False
        for _ in range(400):
            c, _ = ctx(dt=1 / 30, player=(0, 0),
                       explosion=lambda pos, r, d: exploded.append((r, d)))
            e.update(c)
            if e.telegraphing:
                saw_telegraph = True
        self.assertTrue(saw_telegraph, "brute never entered telegraph")
        self.assertTrue(exploded, "brute never landed a slam")


class PathChaseTests(unittest.TestCase):
    """M4: flow-field chaser -- inert when disabled, follows `nav_dir` when on,
    plus neighbour separation and an unstick nudge."""

    def test_disabled_is_exactly_chase(self):
        from entities.enemy_ai import chase, path_chase
        a, b = make("chaser"), make("chaser")
        c, _ = ctx(player=(0, 0))                     # nav_enabled defaults False
        path_chase(a, c)
        chase(b, c)
        self.assertAlmostEqual(a.vel.x, b.vel.x, places=5)
        self.assertAlmostEqual(a.vel.y, b.vel.y, places=5)

    def test_follows_the_field_direction_when_enabled(self):
        from entities.enemy_ai import path_chase
        e = make("chaser")                            # sits at (200, 0)
        c, _ = ctx(player=(200, 0), nav_enabled=True,
                   nav_dir=lambda pos, r: pygame.Vector2(0, -1))
        path_chase(e, c)
        self.assertLess(e.vel.y, -e.speed * 0.9)      # steered up, not at the player

    def test_falls_back_to_straight_when_the_field_is_silent(self):
        from entities.enemy_ai import path_chase
        e = make("chaser")
        c, _ = ctx(player=(0, 0), nav_enabled=True,
                   nav_dir=lambda pos, r: pygame.Vector2())
        path_chase(e, c)
        self.assertLess(e.vel.x, 0)                   # toward the origin (player)
        self.assertAlmostEqual(e.vel.length(), e.speed, places=3)

    def test_separation_pushes_a_crowded_enemy_off_line(self):
        from entities.enemy_ai import path_chase
        a = make("chaser"); a.pos = pygame.Vector2(0, 0)
        b = make("chaser"); b.pos = pygame.Vector2(5, 0)     # almost on top of A
        c, _ = ctx(player=(0, 500), nav_enabled=True,
                   nav_dir=lambda pos, r: pygame.Vector2(),
                   neighbors=lambda pos, r: [a, b])
        path_chase(a, c)
        self.assertLess(a.vel.x, -1.0)               # shoved away from B (+x)
        self.assertGreater(a.vel.y, 0.0)             # still heading toward the player

    def _pin_tick(self, e):
        from entities.enemy_ai import path_chase
        c, _ = ctx(dt=0.1, player=(0, 0), nav_enabled=True,
                   nav_dir=lambda pos, r: pygame.Vector2())
        path_chase(e, c)

    def test_unstick_nudge_fires_within_half_a_second_of_being_pinned(self):
        e = make("chaser")
        for _ in range(3):                            # ~0.2 s pinned -- not yet
            self._pin_tick(e)
        self.assertLessEqual(e.ai.get("nudge_t", 0.0), 0.0)
        for _ in range(3):                            # now across the 0.4 s mark
            self._pin_tick(e)
        self.assertGreater(e.ai.get("nudge_t", 0.0), 0.0)

    def test_no_nudge_while_the_enemy_keeps_making_progress(self):
        from entities.enemy_ai import path_chase
        e = make("chaser")                            # far from the player, closing
        for _ in range(15):                           # 1.5 s of genuine movement
            c, _ = ctx(dt=0.1, player=(0, -3000), nav_enabled=True,
                       nav_dir=lambda pos, r: pygame.Vector2())
            path_chase(e, c)
            e.pos += e.vel * 0.1                      # integrate the step ourselves
        self.assertLessEqual(e.ai.get("nudge_t", 0.0), 0.0)

    def test_obstacle_avoid_veers_a_chaser_off_a_prop_in_its_path(self):
        from types import SimpleNamespace
        from entities.enemy_ai import path_chase
        e = make("chaser")
        e.pos = pygame.Vector2(0, 0)
        prop = SimpleNamespace(pos=pygame.Vector2(40, 12), radius=25)
        c, _ = ctx(player=(400, 0), nav_enabled=True,
                   nav_dir=lambda pos, r: pygame.Vector2(1, 0),
                   obstacles_near=lambda pos, rad:
                       [prop] if pos.distance_to(prop.pos) < rad else [])
        path_chase(e, c)
        self.assertGreater(e.vel.x, 0)          # still heading toward the player
        self.assertLess(e.vel.y, 0)             # but shoved clear of the prop at +y

    def test_obstacle_avoid_does_nothing_when_the_path_is_clear(self):
        from types import SimpleNamespace
        from entities.enemy_ai import path_chase
        far = SimpleNamespace(pos=pygame.Vector2(600, 600), radius=25)
        e = make("chaser"); e.pos = pygame.Vector2(0, 0)
        c, _ = ctx(player=(400, 0), nav_enabled=True,
                   nav_dir=lambda pos, r: pygame.Vector2(1, 0),
                   obstacles_near=lambda pos, rad:
                       [far] if pos.distance_to(far.pos) < rad else [])
        path_chase(e, c)
        self.assertAlmostEqual(e.vel.y, 0.0, places=3)
        self.assertAlmostEqual(e.vel.length(), e.speed, places=3)

    def test_deterministic_including_the_nudge(self):
        from entities.enemy_ai import path_chase

        def run():
            e = make("chaser")
            vs = []
            for _ in range(15):
                c, _ = ctx(dt=0.1, player=(0, 0), rng=random.Random(7),
                           nav_enabled=True,
                           nav_dir=lambda pos, r: pygame.Vector2())
                path_chase(e, c)
                vs.append((round(e.vel.x, 6), round(e.vel.y, 6)))
            return vs

        self.assertEqual(run(), run())


class SpecialMoverNavTests(unittest.TestCase):
    """M5: FSM / special enemies route their *approach* through the flow field
    (chase + recover), but telegraph / charge / blink / retreat stay straight."""

    _UP = staticmethod(lambda pos, r: pygame.Vector2(0, -1))

    def test_approach_helper(self):
        from entities.enemy_ai import _approach
        e = make("charger")                          # at (200, 0), player at (0, 0)
        off, _ = ctx(player=(0, 0))                  # nav disabled
        self.assertLess(_approach(e, off).x, 0)      # -> straight toward player
        silent, _ = ctx(player=(0, 0), nav_enabled=True,
                        nav_dir=lambda pos, r: pygame.Vector2())
        self.assertLess(_approach(e, silent).x, 0)   # silent field -> straight
        on, _ = ctx(player=(0, 0), nav_enabled=True, nav_dir=self._UP)
        self.assertEqual(_approach(e, on), pygame.Vector2(0, -1))

    def test_charger_chase_phase_follows_the_field(self):
        e = make("charger")
        c, _ = ctx(player=(0, 0), nav_enabled=True, nav_dir=self._UP)
        BEHAVIORS["fsm_charger"](e, c)
        self.assertEqual(e.ai.get("fs", "chase"), "chase")
        self.assertLess(e.vel.y, -e.speed * 0.9)     # up, per the field
        self.assertLess(abs(e.vel.x), e.speed * 0.2)

    def test_charge_dash_ignores_the_field(self):
        e = make("charger")
        e.ai["fs"] = "attack"
        e.ai["ft"] = 1.0
        e.ai["dir"] = pygame.Vector2(1, 0)           # locked in at telegraph end
        c, _ = ctx(player=(0, 0), nav_enabled=True, nav_dir=self._UP)
        BEHAVIORS["fsm_charger"](e, c)
        self.assertGreater(e.vel.x, 0)               # still dashing +x, not up
        self.assertAlmostEqual(e.vel.y, 0.0, places=3)

    def test_kite_shoot_closes_in_via_field_but_retreats_straight(self):
        far = make("ranged", x=900)                  # dist >> prefer_distance
        c, _ = ctx(player=(0, 0), nav_enabled=True, nav_dir=self._UP)
        BEHAVIORS["kite_shoot"](far, c)
        self.assertLess(far.vel.y, -far.speed * 0.9)  # closing in, per the field

        near = make("ranged", x=40)                   # inside prefer_distance
        c2, _ = ctx(player=(0, 0), nav_enabled=True, nav_dir=self._UP)
        BEHAVIORS["kite_shoot"](near, c2)
        self.assertGreater(near.vel.x, 0)             # backs off +x, field ignored

    def test_summoner_and_exploder_and_brute_approach_via_field(self):
        for eid in ("summoner", "exploder", "brute"):
            e = make(eid, x=700)                      # far enough to be "approach"
            c, _ = ctx(player=(0, 0), nav_enabled=True, nav_dir=self._UP)
            BEHAVIORS[eid](e, c)
            self.assertLess(e.vel.y, 0, f"{eid} ignored the field")
            self.assertLess(abs(e.vel.x), abs(e.vel.y), f"{eid} not field-aligned")

    def test_disabled_keeps_the_straight_line(self):
        for eid in ("summoner", "exploder", "brute", "charger", "warlock"):
            e = make(eid, x=700)
            c, _ = ctx(player=(0, 0))                 # nav disabled
            BEHAVIORS[e.behavior](e, c)
            self.assertLess(e.vel.x, 0, f"{eid} not heading toward the player")
            self.assertAlmostEqual(e.vel.y, 0.0, places=3, msg=eid)


if __name__ == "__main__":
    unittest.main()
