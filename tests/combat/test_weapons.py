"""Milestone 2: weapon cooldown gating, auto-fire, projectile count / spread,
and the no-target fallback."""
import math
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import Weapon, FireContext
from game.content import get_content


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
    "projectile_speed": 400, "projectile_lifetime": 1.5, "spread_deg": 12,
    "area": 5, "weight": 0, "targeting_mode": "nearest", "pierce": 0,
    "special_effect": None, "category": "projectile", "tags": ["projectile"],
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
        from game.content import get_content
        for wid in ("ember_ring", "grave_totem"):
            w = Weapon(wid, get_content().weapon(wid))
            for _ in range(5):
                self.assertFalse(w.update(
                    0.1, make_context([FakeEnemy(80, 0)], [],
                                      spawn_summon=lambda **kw: None)))


class ProjectileSpreadDataTests(unittest.TestCase):
    """Every weapon that fans its shots must say how wide the fan is.

    A `<weapon>:projectiles` upgrade is generated for *every* owned weapon
    (`progression/upgrades._weapon_upgrades`), so any projectile weapon can be
    pushed past one shot in a real run. `Weapon._fire_projectiles` reads
    `spread_deg` with a hard subscript at that point -- deliberately, since a
    default in code would be per-weapon tuning living outside the data -- so a
    weapon missing the field crashes the run the moment the player takes its
    Multishot. `arcane_bolt` and `thunder_orb` both shipped without it.
    """

    def test_every_projectile_weapon_declares_a_spread(self):
        for wid, cfg in get_content().weapons.items():
            if cfg.get("category") != "projectile":
                continue
            self.assertIn("spread_deg", cfg, wid)
            self.assertGreater(float(cfg["spread_deg"]), 0.0, wid)

    def test_one_multishot_upgrade_does_not_crash_any_weapon(self):
        """The failure this guards is a KeyError deep in a firing path, so it is
        worth exercising rather than only asserting the data."""
        for wid, cfg in get_content().weapons.items():
            w = Weapon(wid, cfg)
            w.bonus["projectile_count"] += 1
            count = w._projectile_count()
            if count > 1 and cfg.get("category") == "projectile":
                math.radians(float(cfg["spread_deg"])) * (count - 1)


if __name__ == "__main__":
    unittest.main()
