"""Elemental system M5: FireWind, IceWind and ThunderWind
(design §5.1, §5.5, journal `elemental_system_journal.md`).

All three are the §4.4 Wind area with a different payload, so what is
pinned here is mostly the payload -- the area's own rules (follows its
enemy, sweeps at a low rate, one contact per body, bounded by
`max_targets`) are covered in `test_elements_base.py` and not repeated.

Since the owner's rework (2026-09-22) all three also pay their two-source
figure to the enemy they fired on -- which used to be excluded from its own
tornado and so took nothing at all -- and prime everything the tornado
touches with their own element, which can set off a further reaction.

The area outlives the hit that made it, so these tests advance it by hand
the way the run's update pass does.
"""
import unittest

from combat.elements import reactions, tracking
from combat.elements import profiles as prof
from combat.elements.ids import ElementId, ReactionId
from combat.elements.resolve import Outcome
from game.content import get_content
from tests.combat.fakes import FakeEnemy
from tests.combat.test_elements_base import build as build_bare
from tests.combat.test_elements_base import tweak
from tests.combat.test_reactions import pair_damage, react, tough

C = get_content()
FIRE, ICE, THUNDER, WIND = (ElementId.FIRE, ElementId.ICE,
                            ElementId.THUNDER, ElementId.WIND)

FIREWIND_CFG = C.reactions["reactions"]["firewind"]
ICEWIND_CFG = C.reactions["reactions"]["icewind"]
THUNDERWIND_CFG = C.reactions["reactions"]["thunderwind"]
ICE_CFG = C.elements["elements"]["ice"]
THUNDER_CFG = C.elements["elements"]["thunder"]


def build(enemies=(), **kw):
    kw.setdefault("runner", reactions.run)
    return build_bare(enemies, **kw)


def huddle(n=5, gap=25.0):
    """A knot of enemies close enough for one tornado to take all of them."""
    return [tough(i * gap, 0.0) for i in range(n)]


def sweep(world, now=0.0):
    """Run every seated area's first contact check, as the update pass does."""
    for area in world.areas:
        area.update(now, world)


# --- shared shape ------------------------------------------------------------------

class WindReactionShapeTests(unittest.TestCase):
    PAIRS = ((FIRE, WIND, ReactionId.FIREWIND, tracking.FIREWIND),
             (ICE, WIND, ReactionId.ICEWIND, tracking.ICEWIND),
             (THUNDER, WIND, ReactionId.THUNDERWIND, tracking.THUNDERWIND))

    def test_all_six_reactions_are_now_built(self):
        self.assertEqual(len(reactions.implemented()), 6)

    def test_each_seats_a_tornado_on_the_enemy_that_reacted(self):
        for prime, trigger, rid, effect in self.PAIRS:
            with self.subTest(reaction=rid.key):
                crowd = huddle()
                r, world, _t = build(crowd)
                out = react(r, crowd[0], prime, trigger)
                self.assertEqual(out, Outcome.REACTION)
                self.assertEqual(len(world.areas), 1)
                self.assertIs(world.areas[0].anchor, crowd[0])
                self.assertEqual(world.areas[0].effect, effect)

    def test_each_works_in_both_trigger_directions(self):
        """Priming with Wind seats a plain tornado of its own first, so what
        is asserted is the reaction's area, not the count."""
        for prime, trigger, rid, effect in self.PAIRS:
            for first, second in ((prime, trigger), (trigger, prime)):
                with self.subTest(reaction=rid.key, first=first.key):
                    crowd = huddle()
                    r, world, _t = build(crowd)
                    react(r, crowd[0], first, second)
                    self.assertEqual([a.effect for a in world.areas].count(effect), 1)

    def test_the_area_damages_and_shoves_what_it_touches(self):
        for prime, trigger, rid, effect in self.PAIRS:
            with self.subTest(reaction=rid.key):
                crowd = huddle()
                r, world, _t = build(crowd)
                react(r, crowd[0], prime, trigger)
                area_before = len(world.dealt)
                sweep(world)
                touched = [d[0] for d in world.dealt[area_before:]
                           if d[3] == effect]
                self.assertTrue(touched)
                self.assertNotIn(crowd[0], touched,
                                 "the anchor is paid directly, not by its own area")
                self.assertTrue(any(e._knock.length_squared() > 0.0
                                    for e in crowd[1:]))

    def test_the_enemy_it_fired_on_is_paid_too(self):
        """The rework's headline fix: before it, a Wind reaction's carrier
        took literally nothing, and with the incoming Wind hit suppressed
        triggering one on a lone enemy was a net loss."""
        for prime, trigger, rid, effect in self.PAIRS:
            with self.subTest(reaction=rid.key):
                crowd = huddle()
                r, world, _t = build(crowd)
                cfg = C.reactions["reactions"][rid.key]
                react(r, crowd[0], prime, trigger, damage=100.0)
                own = [d[1] for d in world.dealt
                       if d[0] is crowd[0] and d[3] == effect]
                self.assertEqual(len(own), 1)
                self.assertAlmostEqual(
                    own[0], pair_damage(cfg["damage"], 100.0, 100.0))

    def test_the_tornado_primes_everything_it_touches(self):
        """The aura spread the owner asked for: the tornado's own element,
        laid on each body it contacts."""
        want = {ReactionId.FIREWIND: FIRE, ReactionId.ICEWIND: ICE,
                ReactionId.THUNDERWIND: THUNDER}
        for prime, trigger, rid, effect in self.PAIRS:
            with self.subTest(reaction=rid.key):
                crowd = huddle()
                r, world, _t = build(crowd)
                react(r, crowd[0], prime, trigger)
                sweep(world)
                touched = [d[0] for d in world.dealt if d[3] == effect
                           and d[0] is not crowd[0]]
                self.assertTrue(touched)
                for e in touched:
                    self.assertEqual(e.elemental.element(0.0), want[rid])

    def test_a_bystanders_own_profile_decides_what_may_be_done_to_it(self):
        """Not the profile of whoever set the tornado off."""
        profiles, _ = prof.resolve(
            {"stubborn": {"elementProfile": {"knockback": {"enabled": False}}}})
        crowd = huddle()
        crowd[1].enemy_id = "stubborn"
        r, world, _t = build(crowd, )
        r.profiles = profiles
        react(r, crowd[0], FIRE, WIND)
        sweep(world)
        self.assertEqual(crowd[1].knocks, [])
        self.assertTrue(crowd[2].knocks, "its neighbour is shoved as usual")


# --- FireWind -----------------------------------------------------------------------

class FireWindTests(unittest.TestCase):
    def setUp(self):
        self.crowd = huddle()
        self.r, self.world, self.tracked = build(self.crowd)

    def go(self, damage=100.0):
        react(self.r, self.crowd[0], FIRE, WIND, damage=damage)
        sweep(self.world)

    def test_it_leaves_everything_it_touches_burning(self):
        """The burn outlives `burn_duration` because the tornado also primes
        each body with Fire, and a Fire aura carries a burn of its own for
        the aura's life -- `StatusState.apply` keeps the longer of the two."""
        self.go()
        burning = [e for e in self.crowd[1:] if "burn" in e.status]
        self.assertTrue(burning)
        for e in burning:
            self.assertGreaterEqual(e.status.remaining("burn"),
                                    FIREWIND_CFG["burn_duration"])

    def test_the_burn_is_standalone_so_it_survives_the_aura_it_rode_in_with(self):
        """It is applied over the spread aura rather than under it, so the
        row belongs to FireWind: consuming that aura cannot end the burn."""
        keeper = self.crowd[1]
        self.go()
        self.assertIn("burn", keeper.status)
        self.assertFalse(keeper.status.is_bound("burn"))

    def test_it_reacts_with_an_aura_a_bystander_was_already_holding(self):
        """The cascade the owner chose (2026-09-22): the tornado's Fire
        meeting a bystander's Ice is a Frostburn on that bystander."""
        keeper = self.crowd[1]
        self.r.apply(keeper, ICE, weapon_id="rod", hit_damage=50.0, now=0.0)
        before = self.r.stats.reactions_total
        self.go()
        self.assertGreater(self.r.stats.reactions_total, before + 1,
                           "the tornado set off a second reaction")
        self.assertIn(tracking.FROSTBURN, keeper.damage_effects)

    def test_its_ticks_are_credited_to_firewind_not_to_the_spread_auras_burn(self):
        self.go()
        burning = next(e for e in self.crowd[1:] if "burn" in e.status)
        ticks = []
        burning.status.update(
            FIREWIND_CFG["burn_tick_interval"],
            lambda amount, source, effect=None: ticks.append(effect))
        self.assertEqual(ticks, [tracking.FIREWIND])

    def test_a_profile_can_refuse_the_burn_and_keep_the_damage(self):
        profiles, _ = prof.resolve(
            {"fireproof": {"elementProfile": {"burn": {"enabled": False}}}})
        self.crowd[1].enemy_id = "fireproof"
        self.r.profiles = profiles
        self.go()
        self.assertNotIn("burn", self.crowd[1].status)
        self.assertIn(tracking.FIREWIND, self.crowd[1].damage_effects)


# --- IceWind -------------------------------------------------------------------------

class IceWindTests(unittest.TestCase):
    def setUp(self):
        self.crowd = huddle()
        self.r, self.world, self.tracked = build(self.crowd)
        self.per_contact = ICEWIND_CFG["stacks_per_contact"]

    def go(self, damage=100.0, now=0.0):
        react(self.r, self.crowd[0], ICE, WIND, damage=damage, now=now)
        sweep(self.world, now)

    def test_it_pours_its_stacks_into_what_it_touches(self):
        """`stacks_per_contact` from the payload plus one from the Ice aura
        the tornado now spreads, whose own application is a stack."""
        self.go()
        want = self.per_contact + 1
        touched = [e for e in self.crowd[1:] if e.elemental.ice_stacks]
        self.assertTrue(touched)
        for e in touched:
            self.assertEqual(e.elemental.ice_stacks, want)
            self.assertAlmostEqual(
                e.status.potency("chill"),
                ICE_CFG["slow"]["percent_per_stack"] * want)

    def test_the_slow_is_standalone_and_rides_the_aura_it_came_with(self):
        """Applied over the spread aura, so the row is IceWind's: it is not
        bound, and it lasts at least the reaction's own `slow_duration`."""
        self.go()
        chilled = next(e for e in self.crowd[1:] if "chill" in e.status)
        self.assertGreaterEqual(chilled.status.remaining("chill"),
                                ICEWIND_CFG["slow_duration"])
        self.assertFalse(chilled.status.is_bound("chill"))

    def test_its_stacks_can_freeze(self):
        """Design open item 7: the stacks go through Ice's own model, so
        enough of them freeze exactly as Ice's do."""
        data = tweak(**{"ice.freeze.stacks_required": self.per_contact + 1})
        self.crowd = huddle()
        self.r, self.world, _t = build(self.crowd, elements=data)
        self.go()
        frozen = [e for e in self.crowd[1:] if "freeze" in e.status]
        self.assertTrue(frozen)
        self.assertTrue(frozen[0].status.is_stunned())

    def test_it_stops_short_of_freezing_when_the_threshold_is_higher(self):
        data = tweak(**{"ice.freeze.stacks_required": self.per_contact + 4})
        self.crowd = huddle()
        self.r, self.world, _t = build(self.crowd, elements=data)
        self.go()
        for e in self.crowd[1:]:
            self.assertNotIn("freeze", e.status)

    def test_each_body_keeps_its_own_freeze_threshold(self):
        """A tornado sweeps commons and elites together, so the threshold
        has to be read per body rather than off whoever reacted."""
        profiles, _ = prof.resolve(
            {"tank": {"elementProfile": {"ice": {"freeze.stacks_required": 99}}}})
        data = tweak(**{"ice.freeze.stacks_required": self.per_contact + 1})
        self.crowd = huddle()
        self.crowd[1].enemy_id = "tank"
        self.r, self.world, _t = build(self.crowd, elements=data)
        self.r.profiles = profiles
        self.go()
        self.assertNotIn("freeze", self.crowd[1].status)
        self.assertIn("freeze", self.crowd[2].status)


# --- ThunderWind ----------------------------------------------------------------------

class ThunderWindTests(unittest.TestCase):
    def setUp(self):
        self.crowd = huddle(n=9, gap=20.0)
        self.r, self.world, self.tracked = build(self.crowd)

    def go(self, damage=100.0):
        react(self.r, self.crowd[0], THUNDER, WIND, damage=damage)

    def test_the_strike_lands_on_the_closest_bodies(self):
        self.go()
        struck = [d[0] for d in self.world.dealt
                  if d[3] == tracking.THUNDER_STRIKE]
        self.assertTrue(struck)
        self.assertNotIn(self.crowd[0], struck, "it strikes *through* the anchor")
        # Nearest-first, so the closest neighbour is always among them.
        self.assertIn(self.crowd[1], struck)

    def test_it_is_a_flat_burst_not_a_chain(self):
        """Every strike arc starts at the reacting enemy; a jump tree's
        would start at whichever node it walked from."""
        self.go()
        origins = {tuple(a[0]) for a in self.world.arcs}
        self.assertEqual(origins, {tuple(self.crowd[0].pos)})

    def test_every_body_it_strikes_takes_the_same_damage(self):
        self.go(damage=100.0)
        amounts = {round(d[1], 6) for d in self.world.dealt
                   if d[3] == tracking.THUNDER_STRIKE}
        self.assertEqual(len(amounts), 1, "no falloff: this is one burst")
        self.assertAlmostEqual(amounts.pop(),
                               100.0 * THUNDERWIND_CFG["strike_damage"]["frac"])

    def test_the_strike_leaves_no_aura(self):
        """With Thunder's own chain switched off, anything the bystanders
        hold afterwards could only have come from the strike."""
        data = tweak(**{"thunder.chain.jumps": 0})
        crowd = huddle(n=9, gap=20.0)
        r, _w, _t = build(crowd, elements=data)
        react(r, crowd[0], THUNDER, WIND)
        for e in crowd[1:]:
            self.assertFalse(e.elemental.has_aura(0.0))

    def test_it_never_reaches_fewer_bodies_than_base_thunder_would(self):
        from combat.elements.reactions.thunderwind import ThunderWind

        for per_jump, jumps in ((1, 1), (3, 2), (5, 4)):
            with self.subTest(per_jump=per_jump, jumps=jumps):
                data = tweak(**{"thunder.chain.targets_per_jump": per_jump,
                                "thunder.chain.jumps": jumps})
                r, _w, _t = build(self.crowd, elements=data)
                ctx = self._context(r)
                config = r.registry.reaction_config(ReactionId.THUNDERWIND,
                                                    WIND, ctx.profile)
                self.assertGreaterEqual(ThunderWind.targets(config, ctx),
                                        per_jump * (jumps + 1))

    def test_a_buff_to_thunders_reach_widens_the_burst(self):
        from combat.elements.reactions.thunderwind import ThunderWind

        data = tweak(**{"thunder.chain.targets_per_jump": 4,
                        "thunder.chain.jumps": 2})
        r, _w, _t = build(self.crowd, elements=data)
        ctx = self._context(r)
        config = r.registry.reaction_config(ReactionId.THUNDERWIND, WIND,
                                            ctx.profile)
        before = ThunderWind.targets(config, ctx)
        r.registry.modifiers(THUNDER).add("chain.jumps", source="blessing", flat=4)
        self.assertGreater(ThunderWind.targets(config, ctx), before)

    def test_the_range_bounds_it(self):
        import copy
        data = copy.deepcopy(C.reactions)
        data["reactions"]["thunderwind"]["strike_range"] = 30.0
        crowd = huddle(n=6, gap=25.0)
        r, world, _t = build(crowd, reactions=data)
        react(r, crowd[0], THUNDER, WIND)
        struck = {id(d[0]) for d in world.dealt
                  if d[3] == tracking.THUNDER_STRIKE}
        self.assertEqual(struck, {id(crowd[1])}, "only the one inside 30 px")

    def _context(self, resolver):
        from combat.elements.resolve import HitContext

        profile = resolver.profile_for(self.crowd[0])
        return HitContext(
            target=self.crowd[0], element=WIND, now=0.0, weapon_id="bow",
            hit_damage=100.0, config=resolver.registry.config(WIND, profile),
            profile=profile, registry=resolver.registry, resolver=resolver)


# --- through the hit site ---------------------------------------------------------------

class ThroughTheHitSiteTests(unittest.TestCase):
    def test_two_infused_hits_produce_a_tornado_that_burns_a_bystander(self):
        import pygame

        from game.states.playing.core.combat import CombatResolver
        from combat.elements import area as wind_area
        from tests.combat.fakes import fake_ps

        centre = FakeEnemy(0.0, 0.0, hp=100000.0)
        bystander = FakeEnemy(25.0, 0.0, hp=100000.0)
        ps = fake_ps([centre, bystander])
        combat = CombatResolver(ps)

        for element, weapon in ((ElementId.FIRE, "sword"),
                                (ElementId.WIND, "bow")):
            ps._spawn_projectile(
                pos=pygame.Vector2(centre.pos), vel=pygame.Vector2(),
                damage=40.0, radius=20.0, lifetime=0.1, pierce=0,
                src_weight=0.0, weapon_id=weapon, element=element)
            combat.projectile_hits()

        self.assertEqual(len(ps.wind_areas), 1)
        ps.wind_areas = wind_area.update_all(ps.wind_areas, 0.0,
                                             ps.elements.world)
        self.assertIn("burn", bystander.status)
        books = ps.ledger.elements
        self.assertEqual(books.reactions, {("bow", "firewind"): 1})
        self.assertGreater(books.damage[("bow", tracking.FIREWIND)], 0.0)
        self.assertAlmostEqual(ps.stats["damage_dealt"], ps.ledger.total,
                               places=4)


if __name__ == "__main__":
    unittest.main()
