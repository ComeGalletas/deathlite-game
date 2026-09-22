"""What an element does when the hit that carried it kills the enemy.

The rule (owner, 2026-09-21): a dead carrier still fires everything that
reaches **other** enemies -- the chain jumps, the Wind area, the reaction
with its blast -- and **nothing is written to the body**. No aura, no
status, and its own share of the damage is dropped.

It matters because the loss scaled with the hero's damage. Measured against
the shipped numbers before the rule landed, a fully upgraded weapon one-shot
46 % of enemy types, and a fully upgraded Hammer on common enemies lost
100 % of its chain jumps, tornadoes and reactions. The elemental system
faded out exactly as a build came together, and kept working on elites, so
from the player's seat it read as random rather than as a rule.

Three places the question arises, all covered by the one rule:

1. **The weapon's base damage kills the target.** `apply_element` runs
   after `take_damage`, so the resolver is handed a corpse.
2. **The element's own damage kills the target.** The aliveness test for
   writing to the body is taken after the initial effect, so this case is
   the first one, one step later.
3. **A Thunder jump kills a node.** The node still arcs onward; the chain
   needs only where it was standing.

Nothing ever *targets* a corpse: `world.nearest` returns the living, so a
chain jumps from a body but never to one.
"""
import unittest

import pygame

from combat.elements import tracking
from combat.elements.ids import ElementId
from combat.elements.resolve import Outcome
from game.content import get_content
from game.states.playing.core.combat import CombatResolver
from tests.combat.fakes import FakeEnemy, fake_ps
from tests.combat.test_elements_base import build, row, tweak

C = get_content()
WIND_CFG = C.elements["elements"]["wind"]


def shoot(ps, enemy, element, damage, weapon_id="sword"):
    ps._spawn_projectile(
        pos=pygame.Vector2(enemy.pos), vel=pygame.Vector2(), damage=damage,
        radius=20.0, lifetime=0.1, pierce=0, src_weight=0.0,
        weapon_id=weapon_id, element=element)


# --- site 1: the weapon's base damage kills ------------------------------------

class KillingBlowTests(unittest.TestCase):
    def setUp(self):
        self.frail = FakeEnemy(0.0, 0.0, hp=10.0)
        self.ps = fake_ps([self.frail])
        self.combat = CombatResolver(self.ps)

    def test_nothing_is_written_to_the_body(self):
        shoot(self.ps, self.frail, ElementId.FIRE, damage=50.0)
        self.combat.projectile_hits()
        self.assertFalse(self.frail.alive)
        self.assertFalse(self.frail.elemental.has_aura(0.0))
        self.assertNotIn("burn", self.frail.status)

    def test_the_bodys_own_share_of_the_damage_is_dropped(self):
        shoot(self.ps, self.frail, ElementId.FIRE, damage=50.0)
        self.combat.projectile_hits()
        self.assertEqual(self.frail.damage_effects, [None],
                         "only the weapon's own hit landed")

    def test_a_lethal_hit_still_spawns_its_tornado(self):
        shoot(self.ps, self.frail, ElementId.WIND, damage=50.0, weapon_id="bow")
        self.combat.projectile_hits()
        self.assertEqual(len(self.ps.wind_areas), 1)
        self.assertIs(self.ps.wind_areas[0].anchor, self.frail,
                      "anchored to the corpse, so it stays where it fell")

    def test_a_lethal_hit_still_fires_its_chain(self):
        neighbours = [FakeEnemy(40.0, 0.0, hp=500.0),
                      FakeEnemy(80.0, 0.0, hp=500.0)]
        self.ps.enemies.extend(neighbours)
        shoot(self.ps, self.frail, ElementId.THUNDER, damage=50.0, weapon_id="rod")
        self.combat.projectile_hits()
        self.assertFalse(self.frail.alive)
        struck = [e for e in neighbours
                  if e.elemental.element(0.0) == ElementId.THUNDER]
        self.assertTrue(struck, "the chain outlives its origin")
        self.assertTrue(self.ps.element_fx, "and leaves an arc to draw")

    def test_a_lethal_hit_still_fires_the_reaction_the_target_had_earned(self):
        """The sharpest case, and the one that was worst before the rule:
        a primed enemy killed by the very hit that should set off its
        reaction. Measured at 0 of 300 reactions on an upgraded Sword."""
        fired = []
        self.ps.elements.reaction_runner = lambda t, v, c, ctx: fired.append(v.reaction)
        self.frail.hp = self.frail.max_hp = 500.0
        shoot(self.ps, self.frail, ElementId.FIRE, damage=10.0)
        self.combat.projectile_hits()
        self.assertEqual(self.frail.elemental.element(0.0), ElementId.FIRE)

        shoot(self.ps, self.frail, ElementId.THUNDER, damage=1000.0, weapon_id="rod")
        self.combat.projectile_hits()
        self.assertFalse(self.frail.alive)
        self.assertEqual([r.key for r in fired], ["overload"])

    def test_a_corpse_and_a_survivor_differ_only_in_what_is_written(self):
        tough = FakeEnemy(200.0, 0.0, hp=5000.0)
        self.ps.enemies.append(tough)
        shoot(self.ps, tough, ElementId.WIND, damage=50.0, weapon_id="bow")
        shoot(self.ps, self.frail, ElementId.WIND, damage=50.0, weapon_id="bow")
        self.combat.projectile_hits()
        self.assertEqual(len(self.ps.wind_areas), 2, "both tornadoes formed")
        self.assertEqual(tough.elemental.element(0.0), ElementId.WIND)
        self.assertFalse(self.frail.elemental.has_aura(0.0))


# --- site 2: the element's own damage kills -----------------------------------

class ElementKillsCarrierTests(unittest.TestCase):
    def test_a_lethal_wind_hit_still_leaves_its_tornado(self):
        enemy = FakeEnemy(0.0, 0.0, hp=5.0)
        resolver, world, _t = build([enemy])
        lethal = 5.0 / WIND_CFG["hit"]["damage"]["frac"] + 1.0
        resolver.apply(enemy, ElementId.WIND, weapon_id="bow",
                       hit_damage=lethal, now=0.0)
        self.assertFalse(enemy.alive)
        self.assertEqual(len(world.areas), 1)

    def test_a_lethal_fire_hit_writes_no_burn_to_the_corpse(self):
        """The aliveness test is taken after the initial effect, so an
        element that finished the enemy itself writes nothing either."""
        enemy = FakeEnemy(0.0, 0.0, hp=5.0)
        resolver, _w, _t = build([enemy])
        resolver.apply(enemy, ElementId.FIRE, weapon_id="sword",
                       hit_damage=1000.0, now=0.0)
        self.assertFalse(enemy.alive)
        self.assertNotIn("burn", enemy.status)
        self.assertFalse(enemy.elemental.has_aura(0.0))


# --- site 3: a jump kills a node -----------------------------------------------

class ChainNodeDiesTests(unittest.TestCase):
    def chain_of(self, hp_of_second):
        data = tweak(**{"thunder.chain.jumps": 3,
                        "thunder.chain.targets_per_jump": 1,
                        "thunder.chain.max_range": 60.0,
                        "thunder.chain.falloff": 1.0})
        line = row(n=4, gap=40.0)
        for e in line:
            e.hp = e.max_hp = 5000.0
        line[1].hp = line[1].max_hp = hp_of_second
        resolver, world, _t = build(line, elements=data)
        resolver.apply(line[0], ElementId.THUNDER, weapon_id="rod",
                       hit_damage=100.0, now=0.0)
        return line, {id(d[0]) for d in world.dealt}

    def test_the_chain_arcs_on_past_the_node_its_jump_killed(self):
        line, struck = self.chain_of(hp_of_second=1.0)
        self.assertFalse(line[1].alive)
        self.assertIn(id(line[1]), struck, "it took the jump that killed it")
        self.assertIn(id(line[2]), struck, "and the arc carried on from it")
        self.assertIn(id(line[3]), struck)

    def test_a_corpse_is_never_itself_a_jump_target(self):
        line, _struck = self.chain_of(hp_of_second=1.0)
        data = tweak(**{"thunder.chain.jumps": 1,
                        "thunder.chain.targets_per_jump": 3,
                        "thunder.chain.max_range": 200.0})
        line[1].alive = False
        resolver, world, _t = build(line, elements=data)
        world.dealt.clear()
        resolver.apply(line[0], ElementId.THUNDER, weapon_id="rod",
                       hit_damage=100.0, now=1.0)
        self.assertNotIn(id(line[1]), {id(d[0]) for d in world.dealt})

    def test_the_same_chain_runs_to_the_end_when_nothing_dies(self):
        line, struck = self.chain_of(hp_of_second=5000.0)
        self.assertEqual(len(struck), 4)


# --- what the books say -----------------------------------------------------------

class TrackingTests(unittest.TestCase):
    def setUp(self):
        self.frail = FakeEnemy(0.0, 0.0, hp=10.0)
        self.ps = fake_ps([self.frail])
        self.combat = CombatResolver(self.ps)

    def test_a_hit_on_a_corpse_still_counts_as_an_application(self):
        """It did something -- that is the whole point of the rule -- so the
        run summary counts it."""
        shoot(self.ps, self.frail, ElementId.FIRE, damage=50.0)
        self.combat.projectile_hits()
        self.assertEqual(self.ps.ledger.elements.applications,
                         {("sword", "fire"): 1})

    def test_no_damage_is_filed_against_the_body(self):
        shoot(self.ps, self.frail, ElementId.FIRE, damage=50.0)
        self.combat.projectile_hits()
        self.assertNotIn(("sword", tracking.FIRE_HIT),
                         self.ps.ledger.elements.damage)

    def test_the_resolver_counts_corpse_hits_for_the_overlay(self):
        shoot(self.ps, self.frail, ElementId.FIRE, damage=50.0)
        self.combat.projectile_hits()
        stats = self.ps.elements.stats
        self.assertEqual(stats.corpse_hits, 1)
        self.assertEqual(stats.by_outcome.get(Outcome.OUTWARD), 1)


# --- the deferred-reaction path -----------------------------------------------------

class DeferredReactionTests(unittest.TestCase):
    def test_a_reaction_still_fires_if_its_target_died_while_it_waited(self):
        ran = []
        enemy = FakeEnemy(0.0, 0.0, hp=5000.0)
        resolver, _w, _t = build(
            [enemy], runner=lambda t, v, c, ctx: ran.append(v.reaction))
        resolver.registry.global_cfg = resolver.registry.global_cfg._replace(
            max_reactions_per_frame=0)
        resolver.begin_frame(0.0)
        resolver.apply(enemy, ElementId.FIRE, weapon_id="sword",
                       hit_damage=10.0, now=0.0)
        resolver.apply(enemy, ElementId.THUNDER, weapon_id="rod",
                       hit_damage=10.0, now=0.0)
        self.assertEqual(resolver.pending, 1)

        enemy.alive = False
        resolver.registry.global_cfg = resolver.registry.global_cfg._replace(
            max_reactions_per_frame=8)
        resolver.begin_frame(0.02)
        self.assertEqual([r.key for r in ran], ["overload"])


if __name__ == "__main__":
    unittest.main()
