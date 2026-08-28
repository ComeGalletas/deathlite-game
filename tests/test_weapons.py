"""Milestone 2: weapon cooldown gating, auto-fire, projectile count / spread,
and the no-target fallback."""
import unittest

import pygame

from combat.weapons import Weapon, FireContext


class FakeEnemy:
    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)


def make_context(enemies, sink, **over):
    base = dict(
        origin=pygame.Vector2(0, 0), enemies=enemies,
        damage_multiplier=1.0, attack_speed_multiplier=1.0,
        projectile_speed_multiplier=1.0, area_multiplier=1.0,
        fallback_dir=pygame.Vector2(1, 0),
        spawn_projectile=lambda **kw: sink.append(kw),
    )
    base.update(over)
    return FireContext(**base)


BOLT = {
    "name": "Test Bolt", "damage": 10, "cooldown": 1.0, "projectile_count": 1,
    "projectile_speed": 400, "projectile_lifetime": 1.5, "area": 5,
    "knockback": 0, "targeting_mode": "nearest", "pierce": 0, "tags": ["projectile"],
}


class WeaponTests(unittest.TestCase):
    def test_fires_immediately_then_respects_cooldown(self):
        shots = []
        w = Weapon("bolt", dict(BOLT))
        w.update(0.016, make_context([FakeEnemy(100, 0)], shots))
        self.assertEqual(len(shots), 1)
        w.update(0.5, make_context([FakeEnemy(100, 0)], shots))  # still cooling
        self.assertEqual(len(shots), 1)
        w.update(0.6, make_context([FakeEnemy(100, 0)], shots))  # 1.1s elapsed
        self.assertEqual(len(shots), 2)

    def test_attack_speed_shortens_cooldown(self):
        shots = []
        w = Weapon("bolt", dict(BOLT))
        ctx = make_context([FakeEnemy(50, 0)], shots, attack_speed_multiplier=2.0)
        w.update(0.016, ctx)
        w.update(0.55, make_context([FakeEnemy(50, 0)], shots,
                                    attack_speed_multiplier=2.0))
        self.assertEqual(len(shots), 2)  # cooldown halved to 0.5s

    def test_projectile_count_bonus_produces_spread(self):
        shots = []
        d = dict(BOLT)
        w = Weapon("bolt", d)
        w.bonus["projectile_count"] = 2  # -> 3 projectiles
        w.update(0.016, make_context([FakeEnemy(0, 100)], shots))
        self.assertEqual(len(shots), 3)
        # Velocities differ (arc), but all point roughly downward toward target.
        vels = {(round(s["vel"].x, 2), round(s["vel"].y, 2)) for s in shots}
        self.assertEqual(len(vels), 3)

    def test_no_enemy_no_fallback_does_not_fire_or_burn_cooldown(self):
        shots = []
        w = Weapon("bolt", dict(BOLT))
        w.update(0.016, make_context([], shots, fallback_dir=pygame.Vector2(0, 0)))
        self.assertEqual(shots, [])
        # Should retry quickly rather than wait a full second.
        w.update(0.2, make_context([FakeEnemy(10, 0)], shots))
        self.assertEqual(len(shots), 1)

    def test_damage_multiplier_flows_into_projectile(self):
        shots = []
        w = Weapon("bolt", dict(BOLT))
        w.update(0.016, make_context([FakeEnemy(100, 0)], shots,
                                     damage_multiplier=3.0))
        self.assertEqual(shots[0]["damage"], 30.0)

    def test_update_reports_the_fire_beat(self):
        shots = []
        w = Weapon("bolt", dict(BOLT))
        self.assertTrue(w.update(0.016, make_context([FakeEnemy(100, 0)], shots)))
        self.assertFalse(w.update(0.5, make_context([FakeEnemy(100, 0)], shots)))   # cooling
        self.assertTrue(w.update(0.6, make_context([FakeEnemy(100, 0)], shots)))    # ready again
        # no target -> not a fire beat
        self.assertFalse(w.update(0.016, make_context([], shots,
                                                      fallback_dir=pygame.Vector2(0, 0))))

    def test_orbit_and_summon_never_report_a_fire_beat(self):
        for effect in ("orbit", "summon"):
            w = Weapon("w", dict(BOLT, special_effect=effect))
            for _ in range(5):
                self.assertFalse(w.update(0.1, make_context([FakeEnemy(80, 0)], [])))


if __name__ == "__main__":
    unittest.main()
