"""ENT-015: the boss pattern registry (`entities/ai/patterns.py`).

Pure: stand-in actor, perception and combat; the shipped patterns come from
`data/enemies/bosses.json`.
"""
import unittest

import pygame

from entities.ai import patterns
from entities.ai.blackboard import Blackboard
from entities.ai.machine import ATTACK_SLOT
from entities.ai.steering import Steering
from game.content import get_content


class _Combat:
    def __init__(self):
        self.calls = []

    def fire_projectile(self, **kw):
        self.calls.append(("shot", kw))

    def summon(self, enemy_id, pos, count):
        self.calls.append(("summon", enemy_id, count))

    def melee_hit(self, pos, radius, damage, duration):
        self.calls.append(("melee", radius, damage, duration))


class _Actor:
    def __init__(self):
        self.pos, self.vel = pygame.Vector2(100, 100), pygame.Vector2()
        self.bb, self.contact_damage = Blackboard(), 0.0


class _Per:
    player_pos = pygame.Vector2(300, 100)
    dt = 1 / 60


def _shipped():
    return [(bid, p) for bid, b in get_content().bosses.items()
            if isinstance(b, dict) for p in b.get("patterns", ())]


class BossPatternTests(unittest.TestCase):
    def test_every_shipped_pattern_is_registered_and_complete(self):
        """The data can only name patterns that exist, with every key they
        read -- the check the old `_fire_pattern` fall-through lacked."""
        shipped = _shipped()
        self.assertGreater(len(shipped), 0)
        for bid, p in shipped:
            with self.subTest(boss=bid, pattern=p.get("id")):
                self.assertEqual(patterns.problems(p), [])

    def test_an_unknown_or_incomplete_pattern_is_dropped_not_fatal(self):
        good = {"id": "sweep", "telegraph": 0.5, "duration": 0.3, "recover": 1.0,
                "sweep_radius": 100, "sweep_damage": 10}
        typo = dict(good, id="swep")
        short = {k: v for k, v in good.items() if k != "sweep_damage"}
        with self.assertLogs("entities.ai.patterns", level="WARNING") as logs:
            kept = patterns.valid_patterns("test", [typo, good, short])
        self.assertEqual(kept, [good])
        self.assertEqual(len(logs.output), 2)

    def test_the_barrage_is_an_even_ring_of_shots(self):
        p = {"bullets": 8, "bullet_speed": 190, "bullet_damage": 12}
        cmb = _Combat()
        patterns.get("radial_barrage").fire(_Actor(), _Per(), cmb, p)
        self.assertEqual(len(cmb.calls), 8)
        dirs = [kw["vel"].normalize() for _k, kw in cmb.calls]
        self.assertAlmostEqual(dirs[0].angle_to(dirs[1]), 45.0, places=3)
        self.assertTrue(all(kw["damage"] == 12 for _k, kw in cmb.calls))

    def test_the_charge_locks_at_the_player_and_dashes_along_it(self):
        a, p = _Actor(), {"charge_speed": 600, "charge_damage": 30}
        pat = patterns.get("charge")
        pat.fire(a, _Per(), _Combat(), p)
        self.assertEqual(a.bb.slot(ATTACK_SLOT)["dir"], pygame.Vector2(1, 0))
        acc = Steering()
        pat.active(a, _Per(), _Combat(), acc, p)
        self.assertEqual(acc.resolve(1.0), pygame.Vector2(600, 0))
        self.assertEqual(a.contact_damage, 30)

    def test_summon_and_sweep_hand_their_numbers_to_combat(self):
        cmb = _Combat()
        patterns.get("summon_brood").fire(_Actor(), _Per(), cmb,
                                          {"summon_id": "bumblebee", "summon_count": 8})
        patterns.get("sweep").fire(_Actor(), _Per(), cmb,
                                   {"sweep_radius": 150, "sweep_damage": 26, "duration": 0.35})
        self.assertEqual(cmb.calls, [("summon", "bumblebee", 8),
                                     ("melee", 150.0, 26.0, 0.35)])

    def test_patterns_without_an_active_hold_the_boss_still(self):
        for pid in ("radial_barrage", "summon_brood", "sweep"):
            self.assertIsNone(patterns.get(pid).active)


if __name__ == "__main__":
    unittest.main()
