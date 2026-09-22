"""Elemental system M4: Frostburn, Overload and Superconduct
(design §5, journal `elemental_system_journal.md`).

Unit tier. Every reaction is reached the way the game reaches one -- prime
an enemy with one element, hit it with another through the real resolver --
so what is pinned is the behaviour a pair of infused weapons would produce.

The rules that hold for every reaction are checked first. Since the owner's
rework (2026-09-22) "a secondary hit never leaves an aura" is **not** one of
them: the Wind three and Superconduct prime what they reach, and a spread
aura meeting a different one starts another reaction on purpose. What is
pinned instead is that Overload and Frostburn stay terminal, that a reaction
is paid from **both** interacting hits, and that its damage on its own
carrier never falls below the global floor.
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
          first_weapon="sword", second_weapon="rod", second_damage=None):
    """Prime `target` with `first`, then trigger with `second`.

    `second_damage` gives the triggering hit a size of its own, which is how
    a test tells the two source values apart: since the rework a reaction is
    paid `high x max + low x min` of the pair, and two equal hits cannot show
    which coefficient went where."""
    resolver.apply(target, first, weapon_id=first_weapon, hit_damage=damage,
                   now=now)
    return resolver.apply(target, second, weapon_id=second_weapon,
                          hit_damage=damage if second_damage is None
                          else second_damage, now=now)


def pair_damage(cfg_damage, first: float, second: float) -> float:
    """What the data says a reaction pays for two hits of these sizes."""
    return (cfg_damage["high"] * max(first, second)
            + cfg_damage["low"] * min(first, second))


def reaction_damage(world) -> float:
    """Everything a world recorded that a **reaction** dealt, leaving out
    the priming element's own hit -- which differs between two runs that
    swap the sizes of the pair, and would otherwise drown the figure under
    test."""
    from combat.elements.ids import ReactionId
    return sum(d[1] for d in world.dealt
               if isinstance(tracking.source_of(d[3]), ReactionId))


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

    def test_overload_leaves_no_aura_on_what_it_reaches(self):
        """Overload and Frostburn spread nothing, so they stay terminal --
        the cascade the rework opened is the Wind three and Superconduct."""
        crowd = [tough(), tough(30.0, 0.0), tough(60.0, 0.0)]
        r, _w, _t = build(crowd)
        react(r, crowd[0], FIRE, THUNDER)
        for bystander in crowd[1:]:
            self.assertFalse(bystander.elemental.has_aura(0.0))

    def test_a_blast_cannot_set_off_a_second_reaction(self):
        """Still true of Overload: its shockwave damages and shoves, and
        leaves nothing behind that another hit could react with."""
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

    def test_every_reaction_reads_both_hits_that_met_on_the_body(self):
        """The heart of the rework: the aura's own hit is one of the two
        numbers, so a heavy primer pays even when a feeble hit triggers."""
        for first, second in ((FIRE, THUNDER), (ICE, THUNDER)):
            with self.subTest(pair=f"{first.key}+{second.key}"):
                heavy, feeble = [tough(), tough()], [tough(), tough()]
                r1, w1, _t = build([heavy[0]])
                react(r1, heavy[0], first, second, damage=100.0,
                      second_damage=5.0)
                r2, w2, _t = build([feeble[0]])
                react(r2, feeble[0], first, second, damage=5.0,
                      second_damage=5.0)
                self.assertGreater(reaction_damage(w1), reaction_damage(w2))

    def test_the_order_of_the_two_hits_does_not_change_the_figure(self):
        """`high x max + low x min` is symmetric, so which weapon happened to
        fire second cannot change what the reaction is worth."""
        a, b = tough(), tough()
        r1, w1, _t = build([a])
        react(r1, a, FIRE, THUNDER, damage=80.0, second_damage=20.0)
        r2, w2, _t = build([b])
        react(r2, b, FIRE, THUNDER, damage=20.0, second_damage=80.0)
        self.assertAlmostEqual(reaction_damage(w1), reaction_damage(w2))

    def test_a_reaction_never_pays_its_carrier_less_than_the_floor(self):
        floor = C.elements["global"]["reaction_min_damage"]
        for first, second in ((FIRE, ICE), (FIRE, THUNDER), (ICE, THUNDER),
                              (FIRE, WIND), (ICE, WIND), (THUNDER, WIND)):
            with self.subTest(pair=f"{first.key}+{second.key}"):
                e = tough()
                r, world, _t = build([e])
                react(r, e, first, second, damage=0.5, second_damage=0.5)
                own = [d[1] for d in world.dealt if d[0] is e
                       and isinstance(tracking.source_of(d[3]), ReactionId)]
                self.assertTrue(own, f"{first.key}+{second.key} paid nothing")
                self.assertAlmostEqual(max(own), floor)

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

    def test_the_slow_lasts_the_reactions_own_duration(self):
        self.fire_then_ice()
        self.assertAlmostEqual(self.enemy.status.remaining("chill"),
                               FROSTBURN_CFG["duration"])

    def test_the_burn_lasts_exactly_long_enough_to_pay_out_its_ticks(self):
        """Derived from `ticks x tick_interval` rather than carrying a
        duration of its own, so the two can never drift apart."""
        self.fire_then_ice()
        self.assertAlmostEqual(
            self.enemy.status.remaining("burn"),
            FROSTBURN_CFG["ticks"] * FROSTBURN_CFG["tick_interval"])

    def test_it_lands_an_immediate_hit_as_well_as_the_burn(self):
        """The half the rework added: 70 % of the smaller source hit and
        20 % of the larger, paid at once."""
        self.r, self.world, _t = build([self.enemy])
        self.fire_then_ice(damage=100.0)
        direct = [d for d in self.world.dealt if d[3] == tracking.FROSTBURN]
        self.assertEqual(len(direct), 1)
        self.assertAlmostEqual(
            direct[0][1], pair_damage(FROSTBURN_CFG["damage"], 100.0, 100.0))

    def test_the_burn_pays_out_the_figure_the_data_names(self):
        """`tick` is what the whole burn is worth, so raising `ticks`
        redistributes it instead of multiplying it."""
        self.fire_then_ice(damage=100.0)
        per_tick = self.enemy.status.potency("burn")
        self.assertAlmostEqual(
            per_tick * FROSTBURN_CFG["ticks"],
            pair_damage(FROSTBURN_CFG["tick"], 100.0, 100.0))

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
                               pair_damage(OVERLOAD_CFG["damage"], 100.0, 100.0))

    def test_the_shockwave_pays_what_the_carrier_paid(self):
        """Since the rework there is one figure, not a carrier value and a
        weaker wave value (owner, 2026-09-22)."""
        self.go(damage=100.0)
        wave = [d[1] for d in self.world.dealt
                if d[3] == tracking.OVERLOAD_WAVE]
        self.assertTrue(wave)
        for amount in wave:
            self.assertAlmostEqual(
                amount, pair_damage(OVERLOAD_CFG["damage"], 100.0, 100.0))

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
        direct = [d for d in self.world.dealt
                  if d[3] == tracking.SUPERCONDUCT and d[0] is self.line[0]]
        self.assertEqual(len(direct), 1)
        self.assertAlmostEqual(
            direct[0][1], pair_damage(SUPERCONDUCT_CFG["damage"], 100.0, 100.0))

    def test_the_spread_damages_everything_it_reaches(self):
        """It used to carry a slow and nothing else, so its arcs flew out to
        bodies that took nothing (owner's rework, 2026-09-22)."""
        self.go(damage=100.0)
        want = pair_damage(SUPERCONDUCT_CFG["damage"], 100.0, 100.0)
        reached = [e for e in self.line[1:] if "chill" in e.status]
        self.assertTrue(reached)
        for e in reached:
            paid = [d[1] for d in self.world.dealt
                    if d[0] is e and d[3] == tracking.SUPERCONDUCT]
            self.assertEqual(len(paid), 1)
            self.assertAlmostEqual(paid[0], want)

    def test_the_spread_primes_what_it_reaches_with_ice(self):
        self.go()
        reached = [e for e in self.line[1:] if "chill" in e.status]
        self.assertTrue(reached)
        for e in reached:
            self.assertEqual(e.elemental.element(0.0), ICE)

    def test_the_spread_pours_in_the_stacks_the_data_names(self):
        """Counted, not added blind: laying the aura runs Ice's own
        `on_applied`, which is worth a stack by itself."""
        self.go()
        reached = [e for e in self.line[1:] if "chill" in e.status]
        self.assertTrue(reached)
        for e in reached:
            self.assertEqual(e.elemental.ice_stacks,
                             SUPERCONDUCT_CFG["ice_stacks"])

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


# --- the reaction label (M11 C) ------------------------------------------------------

class ReactionLabelTests(unittest.TestCase):
    """One label per reaction, on the body it fired on."""

    def _fire(self, reaction, bystanders=0):
        """Prime a body with the reaction's pair and trigger it."""
        from combat.elements.config import REACTION_PAIRS

        first, second = REACTION_PAIRS[reaction]
        target = tough()
        others = [tough(x=20.0 * (i + 1)) for i in range(bystanders)]
        resolver, world, _tracked = build([target, *others])
        react(resolver, target, first, second)
        return world, target

    def test_every_reaction_asks_for_its_name(self):
        for reaction in ReactionId:
            with self.subTest(reaction=reaction.key):
                world, target = self._fire(reaction)
                self.assertEqual(len(world.labels), 1,
                                 "exactly one label per reaction")
                pos, got = world.labels[0]
                self.assertIs(got, reaction)
                self.assertEqual(tuple(pos), tuple(target.pos),
                                 "the label belongs to the body that reacted")

    def test_one_element_on_its_own_says_nothing(self):
        target = tough()
        resolver, world, _tracked = build([target])
        resolver.apply(target, ElementId.FIRE, weapon_id="sword",
                       hit_damage=100.0, now=0.0)
        self.assertEqual(world.labels, [])

    def test_a_bystander_a_reaction_only_touches_stays_silent(self):
        """Superconduct's jumps and Overload's shockwave reach other bodies
        without reacting on them. "Every enemy that gets a reaction
        triggered" means the body whose aura was consumed, not everything
        the blast happened to touch."""
        world, target = self._fire(ReactionId.OVERLOAD, bystanders=3)
        self.assertEqual(len(world.labels), 1)
        self.assertEqual(tuple(world.labels[0][0]), tuple(target.pos))


if __name__ == "__main__":
    unittest.main()

