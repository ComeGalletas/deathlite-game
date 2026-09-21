"""Elemental system M4: Frostburn, Overload and Superconduct
(design §5, journal `elemental_system_journal.md`).

Unit tier. Every reaction is reached the way the game reaches one -- prime
an enemy with one element, hit it with another through the real resolver --
so what is pinned is the behaviour a pair of infused weapons would produce.

The two rules that hold for every reaction, present and future, are checked
first: a secondary hit never leaves an aura, so reaction depth can never
exceed 1.
"""
import unittest

import pygame

from combat.elements import reactions, tracking
from combat.elements.ids import ElementId, ReactionId
from combat.elements.resolve import Outcome
from game.content import get_content
from tests.combat.fakes import FakeEnemy
from tests.combat.test_elements_base import build as build_bare
from tests.combat.test_elements_base import row, tweak

C = get_content()
FIRE, ICE, THUNDER, WIND = (ElementId.FIRE, ElementId.ICE,
                            ElementId.THUNDER, ElementId.WIND)

FROSTBURN_CFG = C.reactions["reactions"]["frostburn"]
OVERLOAD_CFG = C.reactions["reactions"]["overload"]
SUPERCONDUCT_CFG = C.reactions["reactions"]["superconduct"]
THUNDER_CFG = C.elements["elements"]["thunder"]


def build(enemies=(), **kw):
    """A resolver wired to the real reactions."""
    kw.setdefault("runner", reactions.run)
    return build_bare(enemies, **kw)


def react(resolver, target, first, second, *, damage=100.0, now=0.0,
          first_weapon="sword", second_weapon="rod"):
    """Prime `target` with `first`, then trigger with `second`."""
    resolver.apply(target, first, weapon_id=first_weapon, hit_damage=damage,
                   now=now)
    return resolver.apply(target, second, weapon_id=second_weapon,
                          hit_damage=damage, now=now)


def tough(x=0.0, y=0.0, hp=100000.0):
    return FakeEnemy(x, y, hp=hp)


# --- the rules every reaction obeys ------------------------------------------------

class UniversalRuleTests(unittest.TestCase):
    def test_every_pair_has_a_reaction_and_all_six_are_built(self):
        self.assertEqual([r.key for r in reactions.implemented()],
                         ["frostburn", "overload", "superconduct",
                          "firewind", "icewind", "thunderwind"])

    def test_a_reaction_runs_in_both_trigger_directions(self):
        for first, second in ((FIRE, THUNDER), (THUNDER, FIRE)):
            with self.subTest(first=first.key):
                crowd = [tough(), tough(40.0, 0.0)]
                r, world, _t = build(crowd)
                out = react(r, crowd[0], first, second)
                self.assertEqual(out, Outcome.REACTION)
                self.assertTrue(any(d[3] == tracking.OVERLOAD_WAVE
                                    for d in world.dealt))

    def test_a_secondary_hit_never_leaves_an_aura(self):
        """Which is what makes reaction depth exactly 1: nothing a reaction
        touches can hold an aura, so nothing it touches can react."""
        crowd = [tough(), tough(30.0, 0.0), tough(60.0, 0.0)]
        r, _w, _t = build(crowd)
        react(r, crowd[0], FIRE, THUNDER)
        for bystander in crowd[1:]:
            self.assertFalse(bystander.elemental.has_aura(0.0))

    def test_a_blast_cannot_set_off_a_second_reaction(self):
        crowd = [tough(), tough(30.0, 0.0)]
        r, _w, _t = build(crowd)
        # The bystander is primed and would react to anything elemental.
        r.apply(crowd[1], FIRE, weapon_id="sword", hit_damage=100.0, now=0.0)
        before = r.stats.reactions_total
        react(r, crowd[0], FIRE, THUNDER)
        self.assertEqual(r.stats.reactions_total, before + 1,
                         "only the triggering pair reacted")
        self.assertEqual(crowd[1].elemental.element(0.0), FIRE,
                         "the bystander keeps the aura it had")

    def test_every_reaction_locks_the_slot_it_consumed(self):
        cooldown = C.elements["global"]["reaction_aura_cooldown"]
        for first, second in ((FIRE, ICE), (FIRE, THUNDER), (ICE, THUNDER)):
            with self.subTest(pair=f"{first.key}+{second.key}"):
                e = tough()
                r, _w, _t = build([e])
                react(r, e, first, second)
                self.assertTrue(e.elemental.is_locked(cooldown - 0.01))

    def test_a_reaction_on_a_dead_carrier_writes_nothing_to_it(self):
        crowd = [tough(hp=1.0), tough(30.0, 0.0)]
        r, world, _t = build(crowd)
        r.apply(crowd[0], FIRE, weapon_id="sword", hit_damage=1.0, now=0.0)
        crowd[0].alive = False
        world.dealt.clear()
        out = r.apply(crowd[0], ICE, weapon_id="rod", hit_damage=100.0, now=0.0)
        self.assertEqual(out, Outcome.REACTION)
        self.assertNotIn("burn", crowd[0].status,
                         "Frostburn puts nothing on a corpse")


# --- Frostburn ---------------------------------------------------------------------

class FrostburnTests(unittest.TestCase):
    def setUp(self):
        self.enemy = tough()
        self.r, self.world, self.tracked = build([self.enemy])

    def fire_then_ice(self, damage=100.0, now=0.0):
        return react(self.r, self.enemy, FIRE, ICE, damage=damage, now=now)

    def test_it_burns_and_slows_at_once(self):
        self.fire_then_ice()
        self.assertIn("burn", self.enemy.status)
        self.assertIn("chill", self.enemy.status)
        self.assertAlmostEqual(self.enemy.status.potency("chill"),
                               FROSTBURN_CFG["slow_percent"])

    def test_the_burn_is_stronger_than_plain_fires(self):
        self.fire_then_ice()
        frostburn = self.enemy.status.potency("burn")
        clean = tough()
        r2, _w, _t = build([clean])
        r2.apply(clean, FIRE, weapon_id="sword", hit_damage=100.0, now=0.0)
        self.assertGreater(frostburn, clean.status.potency("burn"))

    def test_its_ticks_are_credited_to_frostburn_not_to_burn(self):
        self.fire_then_ice()
        ticks = []
        self.enemy.status.update(
            FROSTBURN_CFG["tick_interval"],
            lambda amount, source, effect=None: ticks.append(effect))
        self.assertEqual(ticks, [tracking.FROSTBURN])

    def test_both_statuses_last_the_reactions_own_duration(self):
        self.fire_then_ice()
        for sid in ("burn", "chill"):
            self.assertAlmostEqual(self.enemy.status.remaining(sid),
                                   FROSTBURN_CFG["duration"])

    def test_neither_status_is_bound_to_an_aura(self):
        """The aura that earned them has just been consumed, so they are
        standalone and outlive it."""
        self.fire_then_ice()
        self.assertFalse(self.enemy.status.is_bound("burn"))
        self.assertFalse(self.enemy.status.is_bound("chill"))

    def test_it_holds_the_slot_for_as_long_as_it_lasts(self):
        self.fire_then_ice(now=0.0)
        own = FROSTBURN_CFG["lock_duration"]
        self.assertTrue(self.enemy.elemental.is_locked(own - 0.01))
        self.assertFalse(self.enemy.elemental.is_locked(own))

    def test_it_never_freezes(self):
        """Freezing counts Ice applications, and Frostburn does not touch
        that counter -- so this holds however long it runs."""
        for i in range(20):
            self.enemy.status.clear()
            self.enemy.elemental.clear()
            self.fire_then_ice(now=i * 10.0)
        self.assertNotIn("freeze", self.enemy.status)
        self.assertEqual(self.enemy.elemental.ice_stacks, 0)

    def test_it_reaches_no_one_else(self):
        bystander = tough(30.0, 0.0)
        self.r, self.world, _t = build([self.enemy, bystander])
        self.fire_then_ice()
        self.assertEqual(bystander.status.active_ids(), ())

    def test_a_profile_can_switch_its_halves_off_independently(self):
        from combat.elements import profiles as prof
        profiles, _ = prof.resolve(
            {"skull": {"elementProfile": {"slow": {"enabled": False}}}})
        self.r.profiles = profiles
        self.fire_then_ice()
        self.assertIn("burn", self.enemy.status)
        self.assertNotIn("chill", self.enemy.status)


# --- Overload -----------------------------------------------------------------------

class OverloadTests(unittest.TestCase):
    def setUp(self):
        self.centre = tough()
        self.near = [tough(30.0, 0.0), tough(0.0, 40.0)]
        self.far = tough(5000.0, 0.0)
        self.r, self.world, self.tracked = build(
            [self.centre, *self.near, self.far])

    def go(self, damage=100.0):
        return react(self.r, self.centre, FIRE, THUNDER, damage=damage)

    def test_the_target_takes_the_direct_damage(self):
        self.go(damage=100.0)
        direct = [d for d in self.world.dealt if d[3] == tracking.OVERLOAD]
        self.assertEqual(len(direct), 1)
        self.assertIs(direct[0][0], self.centre)
        self.assertAlmostEqual(direct[0][1],
                               100.0 * OVERLOAD_CFG["damage"]["frac"])

    def test_the_shockwave_reaches_the_neighbours_but_not_the_target(self):
        self.go()
        hit = {id(d[0]) for d in self.world.dealt
               if d[3] == tracking.OVERLOAD_WAVE}
        self.assertEqual(hit, {id(e) for e in self.near})

    def test_the_shockwave_shoves_outward(self):
        self.go()
        self.assertGreater(self.near[0]._knock.x, 0.0)
        self.assertGreater(self.near[1]._knock.y, 0.0)

    def test_nothing_outside_the_radius_is_touched(self):
        self.go()
        self.assertEqual(self.far.damage_effects, [])
        self.assertEqual(self.far.knocks, [])

    def test_the_shove_is_clamped_so_stacked_blasts_cannot_fling_a_body(self):
        cap = OVERLOAD_CFG["max_knockback_speed"]
        for _ in range(6):
            self.centre.elemental.clear()
            self.go()
        self.assertLessEqual(self.near[0]._knock.length(), cap + 1e-6)

    def test_the_blast_leaves_no_aura_on_anyone(self):
        self.go()
        for e in (self.centre, *self.near):
            self.assertFalse(e.elemental.has_aura(0.0))

    def test_max_targets_bounds_the_blast(self):
        crowd = [tough()] + [tough(10.0 + i * 5.0, 0.0) for i in range(8)]
        r, world, _t = build(crowd, reactions=self._with(max_targets=2))
        react(r, crowd[0], FIRE, THUNDER)
        wave = [d for d in world.dealt if d[3] == tracking.OVERLOAD_WAVE]
        self.assertEqual(len(wave), 2)

    def test_a_profile_can_take_the_shove_away_and_keep_the_damage(self):
        from combat.elements import profiles as prof
        profiles, _ = prof.resolve(
            {"skull": {"elementProfile": {"overload": {"knockback_multiplier": 0.0}}}})
        self.r.profiles = profiles
        self.go()
        self.assertEqual(self.near[0].knocks, [])
        self.assertTrue([d for d in self.world.dealt
                         if d[3] == tracking.OVERLOAD_WAVE])

    @staticmethod
    def _with(**over):
        import copy
        data = copy.deepcopy(C.reactions)
        data["reactions"]["overload"].update(over)
        return data


# --- Superconduct -----------------------------------------------------------------

class SuperconductTests(unittest.TestCase):
    def setUp(self):
        self.line = row(n=8, gap=40.0)
        for e in self.line:
            e.hp = e.max_hp = 100000.0
        self.r, self.world, self.tracked = build(self.line)

    def go(self, damage=100.0):
        return react(self.r, self.line[0], ICE, THUNDER, damage=damage)

    def test_the_target_takes_the_direct_damage(self):
        self.go(damage=100.0)
        direct = [d for d in self.world.dealt if d[3] == tracking.SUPERCONDUCT]
        self.assertEqual(len(direct), 1)
        self.assertAlmostEqual(direct[0][1],
                               100.0 * SUPERCONDUCT_CFG["damage"]["frac"])

    def test_the_spread_slows_without_damaging(self):
        self.go()
        spread = [e for e in self.line[1:] if "chill" in e.status]
        self.assertTrue(spread)
        for e in spread:
            self.assertEqual(e.damage_effects, [], "slow only, no damage")
            self.assertAlmostEqual(e.status.potency("chill"),
                                   SUPERCONDUCT_CFG["slow_percent"])

    def test_the_spread_leaves_no_aura(self):
        self.go()
        for e in self.line[1:]:
            self.assertFalse(e.elemental.has_aura(0.0))

    def test_the_spread_adds_no_freeze_stacks(self):
        self.go()
        for e in self.line[1:]:
            self.assertEqual(e.elemental.ice_stacks, 0)
            self.assertNotIn("freeze", e.status)

    def test_it_always_reaches_further_than_base_thunder(self):
        """Defined against Thunder's live config, so no edit to the data can
        make Superconduct the shorter of the pair."""
        from combat.elements.reactions.superconduct import Superconduct

        for thunder_jumps in (0, 1, 4):
            with self.subTest(thunder_jumps=thunder_jumps):
                data = tweak(**{"thunder.chain.jumps": thunder_jumps})
                r, _w, _t = build(self.line, elements=data)
                ctx = self._context(r)
                config = r.registry.reaction_config(ReactionId.SUPERCONDUCT,
                                                    THUNDER, ctx.profile)
                self.assertGreater(Superconduct.jumps(config, ctx), thunder_jumps)

    def test_a_buff_to_thunders_chain_lengthens_it_too(self):
        from combat.elements.reactions.superconduct import Superconduct

        ctx = self._context(self.r)
        config = self.r.registry.reaction_config(ReactionId.SUPERCONDUCT,
                                                 THUNDER, ctx.profile)
        before = Superconduct.jumps(config, ctx)
        self.r.registry.modifiers(THUNDER).add("chain.jumps", source="blessing",
                                               flat=3)
        self.assertEqual(Superconduct.jumps(config, ctx), before + 3)

    def test_max_targets_bounds_the_spread(self):
        import copy
        data = copy.deepcopy(C.reactions)
        data["reactions"]["superconduct"].update(max_targets=2, max_range=500.0)
        r, _w, _t = build(self.line, reactions=data)
        react(r, self.line[0], ICE, THUNDER)
        slowed = [e for e in self.line[1:] if "chill" in e.status]
        self.assertEqual(len(slowed), 2)

    def test_it_leaves_arcs_for_the_placeholder_visual(self):
        self.go()
        self.assertTrue(self.world.arcs)

    def _context(self, resolver):
        """A `HitContext` the way the resolver builds one, for the helpers
        that read Thunder's config off it."""
        from combat.elements.resolve import HitContext

        profile = resolver.profile_for(self.line[0])
        return HitContext(
            target=self.line[0], element=THUNDER, now=0.0, weapon_id="rod",
            hit_damage=100.0, config=resolver.registry.config(THUNDER, profile),
            profile=profile, registry=resolver.registry, resolver=resolver)


# --- through the hit site ------------------------------------------------------------

class ThroughTheHitSiteTests(unittest.TestCase):
    """One end-to-end pass, so the wiring from a weapon hit to a reaction's
    blast is covered as well as the reaction itself."""

    def test_two_infused_hits_produce_an_overload_that_damages_a_bystander(self):
        from game.states.playing.core.combat import CombatResolver
        from tests.combat.fakes import fake_ps

        centre = FakeEnemy(0.0, 0.0, hp=100000.0)
        bystander = FakeEnemy(30.0, 0.0, hp=100000.0)
        ps = fake_ps([centre, bystander])
        combat = CombatResolver(ps)

        for element, weapon in ((ElementId.FIRE, "sword"),
                                (ElementId.THUNDER, "rod")):
            ps._spawn_projectile(
                pos=pygame.Vector2(centre.pos), vel=pygame.Vector2(),
                damage=40.0, radius=20.0, lifetime=0.1, pierce=0,
                src_weight=0.0, weapon_id=weapon, element=element)
            combat.projectile_hits()

        books = ps.ledger.elements
        self.assertEqual(books.reactions, {("rod", "overload"): 1})
        self.assertGreater(books.damage[("rod", tracking.OVERLOAD_WAVE)], 0.0)
        self.assertIn(tracking.OVERLOAD_WAVE, bystander.damage_effects)
        self.assertAlmostEqual(ps.stats["damage_dealt"], ps.ledger.total,
                               places=4)


if __name__ == "__main__":
    unittest.main()
