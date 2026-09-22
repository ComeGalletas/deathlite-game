"""The reaction damage rework: two damage sources, the carrier floor, and
the aura cascade (owner, 2026-09-22; journal
`reaction_damage_rework_journal.md`).

`test_reactions.py` and `test_wind_reactions.py` pin what each reaction
does. This module pins the three rules the rework added *across* them, and
in particular the one that reverses a design invariant: a reaction may now
leave an aura on a body it reached, and that aura may start another
reaction.

The Wind areas outlive the hit that made them, so these tests advance them
by hand the way the run's update pass does.
"""
import unittest

from combat.elements import area as area_mod
from combat.elements import reactions, tracking
from combat.elements.ids import ElementId, ReactionId
from combat.elements.resolve import Outcome
from game.content import get_content
from tests.combat.test_elements_base import build as build_bare
from tests.combat.test_reactions import tough

C = get_content()
FIRE, ICE, THUNDER, WIND = (ElementId.FIRE, ElementId.ICE,
                            ElementId.THUNDER, ElementId.WIND)
FLOOR = C.elements["global"]["reaction_min_damage"]
COOLDOWN = C.elements["global"]["reaction_aura_cooldown"]


def build(enemies=(), **kw):
    kw.setdefault("runner", reactions.run)
    return build_bare(enemies, **kw)


def sweep(world, now=0.0):
    """One contact check on every seated area, as the update pass does."""
    for area in list(world.areas):
        area.update(now, world)


# --- the aura remembers what placed it ----------------------------------------

class AuraDamageTests(unittest.TestCase):
    """`ElementalState.source_damage` is the first of a reaction's two
    numbers; without it the rework has nothing to read."""

    def test_an_aura_records_the_hit_that_placed_it(self):
        e = tough()
        r, _w, _t = build([e])
        r.apply(e, FIRE, weapon_id="hammer", hit_damage=27.0, now=0.0)
        self.assertAlmostEqual(e.elemental.source_damage, 27.0)

    def test_a_refresh_keeps_the_heavier_of_the_two(self):
        """A fast cheap weapon re-priming an enemy must not be able to
        defuse a reaction the player set up with a slow expensive one."""
        e = tough()
        r, _w, _t = build([e])
        r.apply(e, FIRE, weapon_id="hammer", hit_damage=27.0, now=0.0)
        r.apply(e, FIRE, weapon_id="ring", hit_damage=6.0, now=0.1)
        self.assertAlmostEqual(e.elemental.source_damage, 27.0)

    def test_consuming_the_aura_clears_it(self):
        e = tough()
        r, _w, _t = build([e])
        r.apply(e, FIRE, weapon_id="hammer", hit_damage=27.0, now=0.0)
        r.apply(e, THUNDER, weapon_id="rod", hit_damage=6.0, now=0.0)
        self.assertEqual(e.elemental.source_damage, 0.0)

    def test_a_reaction_reads_the_aura_hit_not_only_the_trigger(self):
        """Overload is 50 % of the larger source plus 30 % of the smaller,
        so a Hammer-primed Overload triggered by a feeble hit is paid on the
        Hammer -- the failure the rework was for."""
        cfg = C.reactions["reactions"]["overload"]["damage"]
        e = tough()
        r, world, _t = build([e])
        r.apply(e, FIRE, weapon_id="hammer", hit_damage=27.0, now=0.0)
        r.apply(e, THUNDER, weapon_id="ring", hit_damage=6.0, now=0.0)
        direct = [d[1] for d in world.dealt if d[3] == tracking.OVERLOAD]
        self.assertEqual(len(direct), 1)
        self.assertAlmostEqual(direct[0], cfg["high"] * 27.0 + cfg["low"] * 6.0)

    def test_an_aura_with_no_damage_behind_it_falls_back_to_the_trigger(self):
        """Never paid as if one of the two halves were free."""
        cfg = C.reactions["reactions"]["overload"]["damage"]
        e = tough()
        r, world, _t = build([e])
        r.apply(e, FIRE, weapon_id="odd", hit_damage=0.0, now=0.0)
        r.apply(e, THUNDER, weapon_id="rod", hit_damage=40.0, now=0.0)
        direct = [d[1] for d in world.dealt if d[3] == tracking.OVERLOAD]
        self.assertAlmostEqual(direct[0], (cfg["high"] + cfg["low"]) * 40.0)


# --- the floor ------------------------------------------------------------------

class FloorTests(unittest.TestCase):
    def test_the_floor_is_the_carriers_alone(self):
        """Overload's shockwave carries the same figure as the carrier, so
        with two tiny hits the carrier is topped up and its neighbour is
        not -- which is what makes this observable at all."""
        centre, near = tough(), tough(30.0, 0.0)
        r, world, _t = build([centre, near])
        r.apply(centre, FIRE, weapon_id="w", hit_damage=1.0, now=0.0)
        r.apply(centre, THUNDER, weapon_id="w", hit_damage=1.0, now=0.0)
        own = next(d[1] for d in world.dealt if d[3] == tracking.OVERLOAD)
        wave = next(d[1] for d in world.dealt if d[3] == tracking.OVERLOAD_WAVE)
        self.assertAlmostEqual(own, FLOOR)
        self.assertLess(wave, FLOOR)

    def test_a_figure_already_above_the_floor_is_left_alone(self):
        cfg = C.reactions["reactions"]["overload"]["damage"]
        e = tough()
        r, world, _t = build([e])
        r.apply(e, FIRE, weapon_id="w", hit_damage=100.0, now=0.0)
        r.apply(e, THUNDER, weapon_id="w", hit_damage=100.0, now=0.0)
        own = next(d[1] for d in world.dealt if d[3] == tracking.OVERLOAD)
        self.assertAlmostEqual(own, (cfg["high"] + cfg["low"]) * 100.0)


# --- the cascade ------------------------------------------------------------------

class CascadeTests(unittest.TestCase):
    """A spread aura meeting a different one starts another reaction. This
    reverses design §5.3 and §5.4 and is deliberate."""

    def test_a_tornado_sets_off_a_reaction_on_a_primed_bystander(self):
        carrier, bystander = tough(), tough(30.0, 0.0)
        r, world, _t = build([carrier, bystander])
        # The bystander is holding Ice; the tornado will bring Fire.
        r.apply(bystander, ICE, weapon_id="rod", hit_damage=20.0, now=0.0)
        r.apply(carrier, WIND, weapon_id="sword", hit_damage=40.0, now=0.0)
        out = r.apply(carrier, FIRE, weapon_id="sword", hit_damage=40.0, now=0.0)
        self.assertEqual(out, Outcome.REACTION)
        before = r.stats.reactions_total
        sweep(world)
        self.assertEqual(r.stats.reactions_total, before + 1)
        self.assertIn(tracking.FROSTBURN, bystander.damage_effects)

    def test_superconducts_spread_sets_off_reactions_it_meets(self):
        line = [tough(), tough(40.0, 0.0), tough(80.0, 0.0)]
        r, _w, _t = build(line)
        for e in line[1:]:
            r.apply(e, FIRE, weapon_id="rod", hit_damage=20.0, now=0.0)
        r.apply(line[0], ICE, weapon_id="sword", hit_damage=40.0, now=0.0)
        before = r.stats.reactions_total
        r.apply(line[0], THUNDER, weapon_id="sword", hit_damage=40.0, now=0.0)
        # The Superconduct itself, plus a Frostburn on each primed body its
        # Ice reached.
        self.assertEqual(r.stats.reactions_total, before + 3)
        for e in line[1:]:
            self.assertIn(tracking.FROSTBURN, e.damage_effects)

    def test_a_spread_aura_carries_the_damage_that_body_just_took(self):
        """So a cascade decays: each generation is paid from the last one's
        figure rather than from the original weapon hit."""
        carrier, bystander = tough(), tough(30.0, 0.0)
        r, world, _t = build([carrier, bystander])
        r.apply(carrier, WIND, weapon_id="sword", hit_damage=100.0, now=0.0)
        r.apply(carrier, FIRE, weapon_id="sword", hit_damage=100.0, now=0.0)
        area = next(a for a in world.areas if a.effect == tracking.FIREWIND)
        sweep(world)
        self.assertAlmostEqual(bystander.elemental.source_damage, area.damage)
        self.assertLess(bystander.elemental.source_damage, 100.0,
                        "the cascade decays rather than holding full value")

    def test_a_body_that_just_reacted_takes_no_spread_aura(self):
        """The per-enemy lock is one of the two brakes on an uncapped
        cascade, so it has to keep working through the spread path."""
        carrier, bystander = tough(), tough(30.0, 0.0)
        r, world, _t = build([carrier, bystander])
        r.apply(bystander, ICE, weapon_id="rod", hit_damage=20.0, now=0.0)
        r.apply(bystander, FIRE, weapon_id="rod", hit_damage=20.0, now=0.0)
        self.assertTrue(bystander.elemental.is_locked(0.0))
        r.apply(carrier, WIND, weapon_id="sword", hit_damage=40.0, now=0.0)
        r.apply(carrier, FIRE, weapon_id="sword", hit_damage=40.0, now=0.0)
        sweep(world)
        self.assertFalse(bystander.elemental.has_aura(0.0),
                         "a locked slot refuses the tornado's aura")

    def test_the_frame_budget_bounds_a_cascade_and_defers_the_rest(self):
        """The other brake: nothing is dropped, but a frame can only run so
        many, which is also what caps the recursion depth."""
        cap = C.elements["global"]["max_reactions_per_frame"]
        # Packed tight enough that the tornado's own `max_targets` contacts
        # land inside one frame and outnumber the budget.
        crowd = [tough(i * 8.0, 0.0) for i in range(cap + 6)]
        r, world, _t = build(crowd)
        for e in crowd[1:]:
            r.apply(e, ICE, weapon_id="rod", hit_damage=20.0, now=0.0)
        r.begin_frame(0.0)
        r.apply(crowd[0], WIND, weapon_id="sword", hit_damage=40.0, now=0.0)
        r.apply(crowd[0], FIRE, weapon_id="sword", hit_damage=40.0, now=0.0)
        sweep(world)
        self.assertLessEqual(r.stats.reactions_this_frame, cap)
        self.assertGreater(r.pending, 0, "the overflow is held, not dropped")

    def test_overload_and_frostburn_stay_terminal(self):
        """Only the Wind three and Superconduct spread; the other two must
        not, or every pair would cascade."""
        for prime, trigger in ((FIRE, THUNDER), (FIRE, ICE)):
            with self.subTest(pair=f"{prime.key}+{trigger.key}"):
                carrier, bystander = tough(), tough(30.0, 0.0)
                r, world, _t = build([carrier, bystander])
                r.apply(carrier, prime, weapon_id="sword", hit_damage=40.0, now=0.0)
                r.apply(carrier, trigger, weapon_id="rod", hit_damage=40.0, now=0.0)
                sweep(world)
                self.assertFalse(bystander.elemental.has_aura(0.0))
