"""The weapon fire path: cooldown gating and auto-fire, projectile count and
spread, the no-target fallback, and the reach ring that gates it all.

A weapon only fires while an enemy sits inside its reach ring; with the ring
empty the hero (and the Ember Ring's orbiters) drop to idle and the weapon
polls (`self._cd = 0.1`). Melee sizes the ring from the tip of its own cone
(`_area`); every other category reads an explicit `reach` field. Both scale
with `area_multiplier` and `bonus["area"]`, so any area-growing blessing
widens the ring too.

Regrouped by subject in TST-004.5 from `test_weapons.py` (Milestone 2) and
`test_weapons_reach.py` (CB-2); the roster and data checks those modules
also held are in `test_weapon_roster.py`.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import FireContext, Weapon
from game.content import get_content
from tests.combat.fakes import FakeProj, FakeTarget


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
    "special_effect": None, "category": "projectile", "class": "ranged",
    "tags": ["projectile"],
    # Required taxonomy since M6: how the weapon paces its element.
    "element_application": {"mode": "attack", "interval": 0},
}


class WeaponTests(unittest.TestCase):
    def test_fires_immediately_then_respects_cooldown(self):
        shots = []
        w = Weapon("bolt", dict(BOLT))
        w.update(0.016, make_context([FakeTarget(100, 0)], shots))
        self.assertEqual(len(shots), 1)
        w.update(0.5, make_context([FakeTarget(100, 0)], shots))  # still cooling
        self.assertEqual(len(shots), 1)
        w.update(0.6, make_context([FakeTarget(100, 0)], shots))  # 1.1s elapsed
        self.assertEqual(len(shots), 2)

    def test_attack_speed_shortens_cooldown(self):
        shots = []
        w = Weapon("bolt", dict(BOLT))
        ctx = make_context([FakeTarget(50, 0)], shots, attack_speed_multiplier=2.0)
        w.update(0.016, ctx)
        w.update(0.55, make_context([FakeTarget(50, 0)], shots,
                                    attack_speed_multiplier=2.0))
        self.assertEqual(len(shots), 2)  # cooldown halved to 0.5s

    def test_projectile_count_bonus_produces_spread(self):
        shots = []
        d = dict(BOLT)
        w = Weapon("bolt", d)
        w.bonus["projectile_count"] = 2  # -> 3 projectiles
        w.update(0.016, make_context([FakeTarget(0, 100)], shots))
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
        w.update(0.2, make_context([FakeTarget(10, 0)], shots))
        self.assertEqual(len(shots), 1)

    def test_damage_multiplier_flows_into_projectile(self):
        shots = []
        w = Weapon("bolt", dict(BOLT))
        w.update(0.016, make_context([FakeTarget(100, 0)], shots,
                                     damage_multiplier=3.0))
        self.assertEqual(shots[0]["damage"], 30.0)

    def test_update_reports_the_fire_beat(self):
        shots = []
        w = Weapon("bolt", dict(BOLT))
        self.assertTrue(w.update(0.016, make_context([FakeTarget(100, 0)], shots)))
        self.assertFalse(w.update(0.5, make_context([FakeTarget(100, 0)], shots)))   # cooling
        self.assertTrue(w.update(0.6, make_context([FakeTarget(100, 0)], shots)))    # ready again
        # no target -> not a fire beat
        self.assertFalse(w.update(0.016, make_context([], shots,
                                                      fallback_dir=pygame.Vector2(0, 0))))

    def test_orbit_and_summon_never_report_a_fire_beat(self):
        from game.content import get_content
        for wid in ("ember_ring", "grave_totem"):
            w = Weapon(wid, get_content().weapon(wid))
            for _ in range(5):
                self.assertFalse(w.update(
                    0.1, make_context([FakeTarget(80, 0)], [],
                                      spawn_summon=lambda **kw: None)))


def ctx(enemies, sink, *, area=1.0, origin=(0, 0), anchor=None):
    o = pygame.Vector2(*origin)
    return FireContext(
        origin=o, enemies=list(enemies),
        damage_multiplier=1.0, attack_speed_multiplier=1.0,
        projectile_speed_multiplier=1.0, area_multiplier=area,
        fallback_dir=pygame.Vector2(1, 0),
        spawn_projectile=lambda **kw: (sink.append(FakeProj(**kw)), sink[-1])[1],
        anchor=anchor if anchor is not None else o)


def w(wid):
    return Weapon(wid, get_content().weapon(wid))


class ReachTests(unittest.TestCase):
    def test_melee_reach_tracks_the_cone_tip(self):
        s = w("sword")                       # no `reach` field: the cone tip
        area = get_content().weapon("sword")["area"]
        self.assertEqual(s._reach(1.0), s._area(1.0))
        self.assertEqual(s._reach(1.7), s._area(1.7))
        s.bonus["area"] = 20.0
        self.assertEqual(s._reach(1.0), s._area(1.0))
        self.assertEqual(s._reach(2.0), (area + 20) * 2.0)

    def test_projectile_reach_is_field_plus_area_bonus_times_mult(self):
        f = w("bow")                               # reach 460
        self.assertEqual(f._reach(1.0), 460.0)
        self.assertEqual(f._reach(1.5), 690.0)
        f.bonus["area"] = 50.0
        self.assertEqual(f._reach(1.0), 510.0)
        self.assertEqual(f._reach(2.0), 1020.0)

    def test_a_non_melee_def_without_a_reach_field_is_unbounded(self):
        d = dict(get_content().weapon("bow"))
        d.pop("reach", None)
        self.assertEqual(Weapon("x", d)._reach(1.0), float("inf"))

    def test_summon_weapons_never_gate_their_own_fire(self):
        # their `update` branches to `_maintain_summons` before `_fire`; `_reach`
        # is `inf` so even if it were reached it would not gate.
        for wid in ("grave_totem", "spirit_wolf"):
            self.assertEqual(w(wid)._reach(1.0), float("inf"), wid)


class MeleeGateTests(unittest.TestCase):
    def test_fires_just_inside_the_ring_not_just_outside(self):
        s = w("sword")
        reach = s._reach(1.0)                      # == the sword's area
        shots = []
        self.assertFalse(s.update(0.016, ctx([FakeTarget(reach + 1, 0)], shots)))
        self.assertEqual(shots, [])
        s._cd = 0.0
        self.assertTrue(s.update(0.016, ctx([FakeTarget(reach - 1, 0)], shots)))
        self.assertEqual(len(shots), 1)

    def test_cooldown_stays_small_while_gated(self):
        s = w("sword")
        s.update(0.016, ctx([FakeTarget(999, 0)], []))
        self.assertLessEqual(s._cd, 0.11)          # polling, not the full 1.0s cooldown


class ProjectileGateTests(unittest.TestCase):
    def test_out_of_ring_enemy_does_not_trigger(self):
        f = w("bow")
        shots = []
        self.assertFalse(f.update(0.016, ctx([FakeTarget(1000, 0)], shots)))
        self.assertEqual(shots, [])

    def test_random_targeting_only_picks_from_inside_the_ring(self):
        # `random` mode would otherwise sometimes aim at a foe outside the ring;
        # `_fire` filters the candidate list first.
        d = dict(get_content().weapon("bow"))
        d["targeting_mode"] = "random"
        d["projectile_count"] = 1
        rnd = Weapon("rnd", d)
        inside, outside = FakeTarget(0, 120), FakeTarget(0, -3000)
        for _ in range(50):
            rnd._cd = 0.0
            shots = []
            rnd.update(0.016, ctx([inside, outside], shots))
            self.assertTrue(shots)
            self.assertGreater(shots[0].vel.y, 0.0)   # always toward the in-ring foe


class AreaScalingTests(unittest.TestCase):
    def test_area_multiplier_widens_the_ring_enough_to_trigger(self):
        s = w("sword")
        e = FakeTarget(s._reach(1.0) + 8, 0)        # just outside at x1.0, inside at x1.5
        self.assertFalse(s.update(0.016, ctx([e], [])))
        s._cd = 0.0
        shots = []
        self.assertTrue(s.update(0.016, ctx([e], shots, area=1.5)))
        self.assertEqual(len(shots), 1)

    def test_area_bonus_also_widens_the_ring(self):
        f = w("bow")
        e = FakeTarget(490, 0)                      # outside reach 460
        self.assertFalse(f.update(0.016, ctx([e], [])))
        f._cd = 0.0
        f.bonus["area"] = 50.0                     # reach -> 510
        shots = []
        self.assertTrue(f.update(0.016, ctx([e], shots)))
        self.assertTrue(shots)


class OrbitGateTests(unittest.TestCase):
    def test_no_orbiters_while_the_ring_is_empty(self):
        made = []
        w("ember_ring").update(0.016, ctx([], made))
        self.assertEqual(made, [])

    def test_orbiters_form_when_a_foe_enters_and_drop_when_it_leaves(self):
        ring = w("ember_ring")
        live = []
        c = ctx([FakeTarget(100, 0)], live)         # inside reach 140
        ring.update(0.016, c)
        self.assertEqual(len([o for o in live if o.active]), ring._projectile_count())
        c.enemies = [FakeTarget(500, 0)]            # foe leaves -> hero lowers the ring
        ring.update(0.016, c)
        self.assertEqual([o for o in live if o.active], [])


class RegressionTests(unittest.TestCase):
    """A foe well inside reach -> CB-2 must not change cadence or aim."""

    def test_rod_cadence_and_aim_unchanged(self):
        b = w("magic_rod")                         # cooldown 0.85, reach 400
        e = FakeTarget(80, 0)
        shots = []
        self.assertTrue(b.update(0.016, ctx([e], shots)))     # fires at once
        self.assertFalse(b.update(0.5, ctx([e], shots)))      # still cooling
        self.assertTrue(b.update(0.6, ctx([e], shots)))       # ready again (~1.1s)
        self.assertEqual(len(shots), 2)
        for s in shots:
            self.assertAlmostEqual(s.vel.normalize().x, 1.0, places=3)

    def test_bow_fan_all_head_toward_the_target(self):
        f = w("bow")
        f.bonus["projectile_count"] += 2                      # a three-arrow fan
        shots = []
        f.update(0.016, ctx([FakeTarget(0, 200)], shots))      # target on +y
        self.assertEqual(len(shots), 3)
        self.assertTrue(all(s.vel.y > 0 for s in shots))


class BodyReachTests(unittest.TestCase):
    """CR2: the reach gate counts the enemy's body, like the hit test does --
    a tank whose edge is in a short swing's arc is in reach even when its
    centre is not."""

    class _Body:
        def __init__(self, x, y, radius):
            self.pos = pygame.Vector2(x, y)
            self.radius = radius

    def test_a_big_body_inside_the_arc_counts(self):
        s = w("sword")
        reach = s._reach(1.0)
        tank = self._Body(reach + 10, 0, 18)           # centre 10 px out, body 8 px in
        shots = []
        self.assertTrue(s.update(0.016, ctx([tank], shots)))
        self.assertEqual(len(shots), 1)

    def test_a_body_wholly_outside_still_does_not(self):
        s = w("sword")
        reach = s._reach(1.0)
        far = self._Body(reach + 25, 0, 18)            # edge 7 px out
        self.assertFalse(s.update(0.016, ctx([far], [])))

    def test_a_stand_in_with_no_radius_counts_its_centre(self):
        s = w("sword")
        reach = s._reach(1.0)
        self.assertFalse(s.update(0.016, ctx([FakeTarget(reach + 1, 0)], [])))


if __name__ == "__main__":
    unittest.main()
