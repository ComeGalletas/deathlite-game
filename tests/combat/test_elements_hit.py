"""Elemental system M3: the hit-site hook (design §6.2).

Everything above this file drives the resolver directly. This one goes
through `CombatResolver.projectile_hits`, the single pass every hero damage
path in the game ends in, to pin the three things that matter about the
seam itself: an infused projectile resolves its element, a plain one does
not, and the element's values are a fraction of the weapon damage that hit
actually dealt.
"""
import unittest

import pygame

from combat.elements import tracking
from combat.elements.ids import ElementId
from game.content import get_content
from game.states.playing.core.combat import CombatResolver
from tests.combat.fakes import FakeEnemy, fake_ps

C = get_content()
FIRE_CFG = C.elements["elements"]["fire"]


def shoot(ps, enemy, element=ElementId.NONE, damage=50.0, weapon_id="sword"):
    """A stationary hit on `enemy`, the way a melee cone lands one."""
    proj = ps._spawn_projectile(
        pos=pygame.Vector2(enemy.pos), vel=pygame.Vector2(), damage=damage,
        radius=20.0, lifetime=0.1, pierce=0, src_weight=0.0,
        weapon_id=weapon_id, element=element)
    return proj


class HookTests(unittest.TestCase):
    def setUp(self):
        # Tough on purpose: an enemy the weapon hit itself kills takes
        # no aura, which would muddy the tests below; the death rule
        # has its own module.
        self.enemy = FakeEnemy(0.0, 0.0, hp=10000.0)
        self.ps = fake_ps([self.enemy])
        self.combat = CombatResolver(self.ps)

    def test_an_enemy_the_hit_kills_takes_no_aura_but_still_resolves(self):
        """The death rule, at the seam: nothing is written to a body the
        hit killed, but the element still runs for what it sends
        outward (`test_elements_death_order.py`)."""
        frail = FakeEnemy(200.0, 0.0, hp=5.0)
        self.ps.enemies.append(frail)
        shoot(self.ps, frail, ElementId.WIND, damage=50.0, weapon_id="bow")
        self.combat.projectile_hits()
        self.assertFalse(frail.alive)
        self.assertFalse(frail.elemental.has_aura(0.0))
        self.assertEqual(len(self.ps.wind_areas), 1,
                         "the tornado it earned still forms")

    def test_a_plain_hit_leaves_no_aura(self):
        shoot(self.ps, self.enemy)
        self.combat.projectile_hits()
        self.assertLess(self.enemy.hp, self.enemy.max_hp, "it still hurt")
        self.assertFalse(self.enemy.elemental.has_aura(0.0))

    def test_an_infused_hit_resolves_its_element(self):
        shoot(self.ps, self.enemy, ElementId.FIRE)
        self.combat.projectile_hits()
        self.assertEqual(self.enemy.elemental.element(0.0), ElementId.FIRE)
        self.assertIn("burn", self.enemy.status)
        self.assertEqual(self.enemy.elemental.source_weapon, "sword")

    def test_the_element_scales_with_the_damage_the_hit_dealt(self):
        shoot(self.ps, self.enemy, ElementId.FIRE, damage=200.0)
        self.combat.projectile_hits()
        expected = 200.0 * FIRE_CFG["hit"]["damage"]["frac"]
        self.assertIn(tracking.FIRE_HIT, self.enemy.damage_effects)
        index = self.enemy.damage_effects.index(tracking.FIRE_HIT)
        self.assertAlmostEqual(self.enemy.hp,
                               self.enemy.max_hp - 200.0 - expected, places=4)
        self.assertEqual(self.enemy.damage_sources[index], "sword")

    def test_the_dev_no_damage_toggle_silences_elements_too(self):
        self.ps.dev_mode = True
        self.ps._dev_no_damage = True
        self.combat.run.dev_mode = True
        shoot(self.ps, self.enemy, ElementId.FIRE)
        self.combat.projectile_hits()
        self.assertFalse(self.enemy.elemental.has_aura(0.0))
        self.assertNotIn("burn", self.enemy.status)

    def test_elemental_damage_reaches_the_run_total_and_the_ledger(self):
        shoot(self.ps, self.enemy, ElementId.FIRE, damage=100.0)
        self.combat.projectile_hits()
        books = self.ps.ledger.elements
        self.assertGreater(books.damage[("sword", tracking.FIRE_HIT)], 0.0)
        self.assertAlmostEqual(self.ps.stats["damage_dealt"],
                               self.ps.ledger.total, places=4)

    def test_a_second_element_reacts_through_the_same_seam(self):
        fired = []
        self.ps.elements.reaction_runner = lambda t, v, c, ctx: fired.append(v.reaction)
        shoot(self.ps, self.enemy, ElementId.FIRE)
        self.combat.projectile_hits()
        shoot(self.ps, self.enemy, ElementId.THUNDER, weapon_id="rod")
        self.combat.projectile_hits()
        self.assertEqual([r.key for r in fired], ["overload"])
        self.assertTrue(self.enemy.elemental.is_locked(0.0))

    def test_a_wind_hit_seats_an_area_on_the_run(self):
        shoot(self.ps, self.enemy, ElementId.WIND)
        self.combat.projectile_hits()
        self.assertEqual(len(self.ps.wind_areas), 1)
        self.assertIs(self.ps.wind_areas[0].anchor, self.enemy)

    def test_a_thunder_hit_chains_to_the_neighbours(self):
        others = [FakeEnemy(40.0, 0.0), FakeEnemy(80.0, 0.0)]
        self.ps.enemies.extend(others)
        shoot(self.ps, self.enemy, ElementId.THUNDER, weapon_id="rod")
        self.combat.projectile_hits()
        struck = [e for e in others
                  if e.elemental.element(0.0) == ElementId.THUNDER]
        self.assertTrue(struck, "the chain reached past the enemy that was hit")
        self.assertTrue(self.ps.element_fx, "and left an arc to draw")


if __name__ == "__main__":
    unittest.main()
