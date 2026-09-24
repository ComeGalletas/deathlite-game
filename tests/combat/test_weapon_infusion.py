"""Elemental system M6: a weapon's element and how often it lands
(design §6, journal `elemental_system_journal.md`).

The owner's decision of 2026-09-21 replaced the design's single
`elementInterval` counter with a per-weapon `element_application` block in
two modes, because "one firing = one attack" is false in this game: the
Ember Ring's orbiters and the summons re-hit on their own timers and never
fire an attack at all.

* **attack mode** counts attacks. One decision per attack, stamped on every
  projectile it spawns, so every pierce and every pellet of one volley
  agrees and nothing is re-checked per hit.
* **time mode** grants one application per window, claimed by the first hit
  that asks.

Every weapon carries one of the two, summons included.
"""
import unittest

import pygame

from combat.elements import tracking
from combat.elements.ids import ElementId
from combat.weapons import Weapon
from combat.weapons.core import ATTACK_MODE, ELEMENT_MODES, TIME_MODE
from game.content import get_content
from game.states.playing.core.combat import CombatResolver
from tests.combat.fakes import FakeEnemy, fake_ps

C = get_content()
FIRE, ICE = ElementId.FIRE, ElementId.ICE

ATTACK_WEAPONS = ("sword", "hammer", "daggers", "bow", "magic_rod", "bomb")
TIME_WEAPONS = ("ember_ring", "grave_totem", "spirit_wolf")


def weapon(wid, element=ElementId.NONE, **over):
    definition = dict(C.weapon(wid))
    if over:
        definition["element_application"] = {
            **definition["element_application"], **over}
    w = Weapon(wid, definition)
    w.element = element
    return w


def pattern(w, attacks=9) -> list[bool]:
    """Which of the next `attacks` attacks carry the element."""
    out = []
    for _ in range(attacks):
        w._begin_attack()
        out.append(bool(w.attack_element))
    return out


# --- the data -----------------------------------------------------------------

class DataTests(unittest.TestCase):
    def test_every_weapon_declares_how_it_applies_its_element(self):
        for wid, spec in C.weapons.items():
            with self.subTest(weapon=wid):
                block = spec.get("element_application")
                self.assertIsInstance(block, dict)
                self.assertIn(block["mode"], ELEMENT_MODES)

    def test_the_two_modes_carry_the_number_they_need(self):
        for wid, spec in C.weapons.items():
            with self.subTest(weapon=wid):
                block = spec["element_application"]
                if block["mode"] == ATTACK_MODE:
                    self.assertGreaterEqual(int(block["interval"]), 0)
                else:
                    self.assertGreater(float(block["window"]), 0.0)

    def test_the_re_hitting_weapons_are_the_time_mode_ones(self):
        """Orbiters and summons never fire an attack, so a counter has
        nothing to count."""
        for wid in TIME_WEAPONS:
            self.assertEqual(C.weapon(wid)["element_application"]["mode"],
                             TIME_MODE, wid)
        for wid in ATTACK_WEAPONS:
            self.assertEqual(C.weapon(wid)["element_application"]["mode"],
                             ATTACK_MODE, wid)

    def test_summons_can_be_infused(self):
        """The owner's correction: every weapon takes an element, summons
        included."""
        for wid in ("grave_totem", "spirit_wolf"):
            w = weapon(wid, FIRE)
            self.assertTrue(w.is_summon)
            self.assertTrue(w.infused)

    def test_a_weapon_missing_the_block_or_naming_a_bad_mode_is_refused(self):
        base = dict(C.weapon("sword"))
        for bad in ({}, {"mode": "sometimes", "interval": 0},
                    {"mode": "attack", "interval": -1},
                    {"mode": "time", "window": 0.0}):
            with self.subTest(bad=bad):
                broken = dict(base, element_application=bad)
                with self.assertRaises(ValueError):
                    Weapon("sword", broken)
        del base["element_application"]
        with self.assertRaises(ValueError):
            Weapon("sword", base)


# --- attack mode ------------------------------------------------------------------

class AttackModeTests(unittest.TestCase):
    def test_interval_zero_carries_every_attack(self):
        self.assertEqual(pattern(weapon("sword", FIRE, interval=0)), [True] * 9)

    def test_interval_one_carries_every_other_attack(self):
        self.assertEqual(pattern(weapon("sword", FIRE, interval=1)),
                         [True, False] * 4 + [True])

    def test_interval_n_carries_one_attack_in_n_plus_one(self):
        self.assertEqual(pattern(weapon("sword", FIRE, interval=2)),
                         [True, False, False] * 3)

    def test_the_first_attack_always_carries(self):
        for interval in (0, 1, 5, 20):
            with self.subTest(interval=interval):
                self.assertTrue(pattern(weapon("sword", FIRE, interval=interval),
                                        attacks=1)[0])

    def test_an_uninfused_weapon_carries_nothing(self):
        self.assertEqual(pattern(weapon("sword")), [False] * 9)

    def test_a_blessing_can_shorten_the_interval(self):
        w = weapon("daggers", FIRE)
        self.assertEqual(w.element_interval, 2)
        w.bonus["element_interval"] = -2
        self.assertEqual(w.element_interval, 0)
        self.assertEqual(pattern(w), [True] * 9)

    def test_the_interval_never_goes_below_zero(self):
        w = weapon("sword", FIRE, interval=0)
        w.bonus["element_interval"] = -10
        self.assertEqual(w.element_interval, 0)

    def test_a_time_mode_weapon_stamps_nothing(self):
        w = weapon("ember_ring", FIRE)
        self.assertEqual(pattern(w), [False] * 9,
                         "its hits are gated at the hit site instead")


# --- time mode ---------------------------------------------------------------------

class TimeModeTests(unittest.TestCase):
    def test_one_application_per_window(self):
        w = weapon("ember_ring", FIRE, window=1.0)
        taken = [w.take_element_window(t)
                 for t in (0.0, 0.3, 0.6, 0.9, 1.0, 1.4, 2.0)]
        self.assertEqual(taken, [True, False, False, False, True, False, True])

    def test_the_first_hit_after_the_window_claims_it(self):
        """Not every hit inside the window -- the owner's confirmed
        reading."""
        w = weapon("ember_ring", FIRE, window=1.0)
        self.assertTrue(w.take_element_window(0.0))
        self.assertEqual([w.take_element_window(0.0 + i * 0.05)
                          for i in range(1, 6)], [False] * 5)

    def test_an_uninfused_weapon_never_claims(self):
        w = weapon("ember_ring")
        self.assertFalse(w.take_element_window(99.0))

    def test_an_attack_mode_weapon_never_claims(self):
        w = weapon("sword", FIRE)
        self.assertFalse(w.take_element_window(99.0))

    def test_a_blessing_can_shorten_the_window(self):
        w = weapon("ember_ring", FIRE, window=2.0)
        w.bonus["element_window_mult"] = 0.5
        self.assertAlmostEqual(w.element_window, 1.0)
        self.assertTrue(w.take_element_window(0.0))
        self.assertTrue(w.take_element_window(1.0))


# --- one element per weapon ----------------------------------------------------------

class InfusionTests(unittest.TestCase):
    def test_a_weapon_holds_one_element_and_a_new_one_replaces_it(self):
        w = weapon("sword")
        self.assertFalse(w.infused)
        w.element = FIRE
        self.assertEqual(w.element, FIRE)
        w.element = ICE
        self.assertEqual(w.element, ICE, "the data type enforces the one-element rule")

    def test_two_weapons_hold_their_elements_apart(self):
        a, b = weapon("sword", FIRE), weapon("bow", ICE)
        self.assertEqual((a.element, b.element), (FIRE, ICE))


# --- through the hit site --------------------------------------------------------------

class ThroughTheHitSiteTests(unittest.TestCase):
    """What the two modes look like from the enemy's side."""

    def setUp(self):
        self.enemy = FakeEnemy(0.0, 0.0, hp=1000000.0)
        self.ps = fake_ps([self.enemy])
        self.combat = CombatResolver(self.ps)

    def hold(self, w):
        self.ps.player.weapons.append(w)
        return w

    def shot(self, weapon_id, element=ElementId.NONE, damage=20.0, pierce=0):
        return self.ps._spawn_projectile(
            pos=pygame.Vector2(self.enemy.pos), vel=pygame.Vector2(),
            damage=damage, radius=20.0, lifetime=0.1, pierce=pierce,
            src_weight=0.0, weapon_id=weapon_id, element=element)

    def applications(self):
        return sum(self.ps.ledger.elements.applications.values())

    def test_an_attack_modes_stamp_is_what_the_hit_site_reads(self):
        self.hold(weapon("sword", FIRE))
        self.shot("sword", FIRE)
        self.combat.projectile_hits()
        self.assertEqual(self.applications(), 1)

    def test_an_unstamped_shot_from_an_attack_mode_weapon_stays_plain(self):
        """A crater tick or a Powder Keg burst names the weapon but is not
        one of its attacks, so it carries nothing."""
        self.hold(weapon("hammer", FIRE))
        self.shot("hammer")
        self.combat.projectile_hits()
        self.assertEqual(self.applications(), 0)

    def test_a_time_mode_weapon_is_gated_at_the_hit_site(self):
        self.hold(weapon("ember_ring", FIRE, window=1.0))
        for _ in range(4):
            self.shot("ember_ring")
            self.combat.projectile_hits()
        self.assertEqual(self.applications(), 1,
                         "four hits in the same instant, one application")

    def test_a_time_mode_weapon_applies_again_after_its_window(self):
        self.hold(weapon("ember_ring", FIRE, window=1.0))
        for now in (0.0, 1.0, 2.0):
            self.ps.stats["time"] = now
            self.shot("ember_ring")
            self.combat.projectile_hits()
        self.assertEqual(self.applications(), 3)

    def test_a_summons_bolt_carries_its_weapons_element(self):
        """The summon spawns the bolt itself and never sees the weapon, so
        the hit site looks it up by id."""
        self.hold(weapon("spirit_wolf", ICE, window=1.0))
        self.shot("spirit_wolf")
        self.combat.projectile_hits()
        self.assertEqual(self.ps.ledger.elements.applications,
                         {("spirit_wolf", "ice"): 1})

    def test_a_projectile_from_no_held_weapon_carries_nothing(self):
        """The Pinball buff's ball names a weapon the hero does not hold."""
        self.shot("pinball")
        self.combat.projectile_hits()
        self.assertEqual(self.applications(), 0)

    def test_every_pierce_of_one_attack_shares_its_decision(self):
        crowd = [FakeEnemy(i * 5.0, 0.0, hp=1000000.0) for i in range(4)]
        self.ps = fake_ps(crowd)
        self.combat = CombatResolver(self.ps)
        self.hold(weapon("bow", FIRE))
        self.shot("bow", FIRE, pierce=9)
        self.combat.projectile_hits()
        self.assertEqual(self.applications(), len(crowd),
                         "one decision, applied to everything the shot hit")


# --- the whole chain, from firing a weapon to an aura --------------------------------

class FiringTests(unittest.TestCase):
    def test_firing_an_infused_weapon_stamps_its_projectiles(self):
        """End to end: the weapon fires itself, and the spread reaches the
        projectile without anything in between being told about elements."""
        from tests.combat.test_weapon_fire import make_context

        target = FakeEnemy(60.0, 0.0)
        w = weapon("bow", FIRE, interval=1)
        spawned: list[dict] = []
        stamped = []
        for _ in range(4):
            w._cd = 0.0
            spawned.clear()
            w.update(0.0, make_context([target], spawned))
            self.assertTrue(spawned, "the weapon fired")
            stamped.append(all(bool(kw.get("element")) for kw in spawned))
        self.assertEqual(stamped, [True, False, True, False])


class TheLookFollowsTheInfusionTests(unittest.TestCase):
    """`infusion` is not `element`, and M13 needs both.

    `attack_element` is the element this attack *applies*, which is the
    right rule for damage and the wrong one for paint. M13 first painted
    from it and the screenshot showed what that means: the Ember Ring, the
    Grave Totem and the Spirit Wolf are the three time-mode weapons, whose
    spawns are stamped with nothing at all, so all three came out in their
    plain colours at every element. The Daggers, at `interval: 2`, were
    drawn plain on two swings in three.

    So every spawn also carries `infusion` -- what the weapon is -- and the
    painters read that. Nothing about damage changed; `element` still says
    what lands.
    """

    def spawns(self, wid, element, attacks=4, **over):
        from tests.combat.test_weapon_fire import make_context

        target = FakeEnemy(60.0, 0.0)
        w = weapon(wid, element, **over)
        out = []
        for _ in range(attacks):
            w._cd = 0.0
            spawned: list[dict] = []
            w.update(0.0, make_context([target], spawned))
            self.assertTrue(spawned, f"{wid} fired")
            out.append(spawned[0])
        return out

    def test_an_attack_mode_weapon_looks_infused_on_every_attack(self):
        """The Daggers apply on one swing in three and look infused on all
        three -- which swing spends the element is a balance detail, not
        something to read off the sprite."""
        kws = self.spawns("bow", FIRE, interval=2)
        self.assertEqual([bool(k.get("element")) for k in kws],
                         [True, False, False, True])
        self.assertEqual([k.get("infusion") for k in kws], [FIRE] * 4)

    def test_a_time_mode_weapon_looks_infused_although_it_stamps_nothing(self):
        """The regression this class exists for. `attack_element` is
        documented as NONE for these, so painting from it left every
        orbiter and both summons plain."""
        for wid in TIME_WEAPONS:
            with self.subTest(weapon=wid):
                w = weapon(wid, ICE)
                w._begin_attack()
                self.assertEqual(w.attack_element, ElementId.NONE)
                self.assertEqual(w.element, ICE)

    def test_an_orbiter_carries_the_infusion(self):
        from tests.combat.test_weapon_fire import make_context

        target = FakeEnemy(20.0, 0.0)
        w = weapon("ember_ring", ICE)
        spawned: list[dict] = []
        w.update(0.0, make_context([target], spawned))
        self.assertTrue(spawned, "the ring formed")
        for kw in spawned:
            self.assertEqual(kw.get("element"), ElementId.NONE)
            self.assertEqual(kw.get("infusion"), ICE)

    def test_an_uninfused_weapon_carries_no_infusion(self):
        for kw in self.spawns("bow", ElementId.NONE):
            self.assertFalse(kw.get("infusion"))

    def test_a_pooled_projectile_does_not_inherit_the_last_infusion(self):
        """`acquire()` does not clear fields; `reset` does, and it has to
        set this one even when the caller passes nothing."""
        from entities.projectile import Projectile

        p = Projectile()
        p.infusion = FIRE
        p.reset(pos=pygame.Vector2(), vel=pygame.Vector2(), damage=1.0,
                radius=1.0, lifetime=1.0)
        self.assertEqual(p.infusion, ElementId.NONE)

    def test_a_pooled_summon_does_not_inherit_the_last_infusion(self):
        from entities.summon import Summon

        s = Summon()
        s.infusion = FIRE
        s.reset(kind="totem", pos=pygame.Vector2(), damage=1.0, lifetime=1.0,
                color=(1, 1, 1), tags=())
        self.assertEqual(s.infusion, ElementId.NONE)


if __name__ == "__main__":
    unittest.main()
