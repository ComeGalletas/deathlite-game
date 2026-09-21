"""Elemental system M2: the aura slot, the lock, single-element hit
resolution, enemy profiles and the damage / application tracking
(design §3, journal `elemental_system_journal.md`).

Unit tier: hand-built fakes, no world and no Game. What an element or a
reaction *does* is M3 and M4; what this pins is the machinery around them --
which aura ends up on the slot, when a reaction fires, what gets locked, and
what is written down.

A recording `Element` stands in for the real four, so the hooks the resolver
drives (and the flags it drives them with) are asserted directly.
"""
import unittest

from combat.elements import profiles as prof
from combat.elements import tracking as track
from combat.elements.aura import ElementalState
from combat.elements.base import AuraEnd, Element
from combat.elements.ids import ElementId, ReactionId
from combat.elements.registry import ElementRegistry
from combat.elements.resolve import ElementalResolver, Outcome
from combat.elements.tracking import ElementTracking
from combat.status import StatusState
from game.content import get_content
from tests.combat.fakes import FakeEnemy

C = get_content()

FIRE, ICE, THUNDER, WIND = (ElementId.FIRE, ElementId.ICE,
                            ElementId.THUNDER, ElementId.WIND)


class Recorder(Element):
    """An element that writes down every hook it is given."""

    def __init__(self, element_id):
        super().__init__(element_id)
        self.landed = []
        self.applied = []
        self.ended = []

    def apply_initial_effect(self, target, ctx):
        self.landed.append(ctx)

    def on_applied(self, target, ctx):
        self.applied.append((ctx.bound, ctx.refreshed))

    def on_aura_ended(self, target, reason, ctx):
        self.ended.append(reason)


def registry(**over):
    """A registry whose four elements are `Recorder`s."""
    elements = {"global": dict(C.elements["global"], **over),
                "elements": C.elements["elements"]}
    return ElementRegistry(elements, C.reactions,
                           {e: Recorder for e in (FIRE, ICE, THUNDER, WIND)})


def resolver(profiles=None, tracking=None, runner=None, **over):
    reg = registry(**over)
    return ElementalResolver(reg, profiles=profiles,
                             tracking=tracking if tracking is not None else ElementTracking(),
                             reaction_runner=runner)


def enemy(**kw):
    return FakeEnemy(0.0, 0.0, **kw)


# --- the state object ------------------------------------------------------------

class ElementalStateTests(unittest.TestCase):
    def test_a_fresh_slot_is_empty_unlocked_and_holds_no_stacks(self):
        s = ElementalState()
        self.assertEqual(s.element(0.0), ElementId.NONE)
        self.assertFalse(s.has_aura(0.0))
        self.assertFalse(s.is_locked(0.0))
        self.assertEqual(s.ice_stacks, 0)

    def test_an_aura_expires_by_comparison_without_being_ticked(self):
        s = ElementalState()
        s.set_aura(FIRE, now=10.0, duration=4.0, weapon_id="sword")
        self.assertEqual(s.element(13.9), FIRE)
        self.assertAlmostEqual(s.remaining(13.0), 1.0)
        self.assertEqual(s.element(14.0), ElementId.NONE, "lapsed, with nothing ticked")
        self.assertEqual(s.remaining(14.0), 0.0)

    def test_a_refresh_never_shortens_and_re_attributes(self):
        s = ElementalState()
        s.set_aura(FIRE, now=0.0, duration=4.0, weapon_id="sword")
        s.refresh_aura(now=1.0, duration=1.0, weapon_id="bow")
        self.assertAlmostEqual(s.aura_expires_at, 4.0, msg="a shorter refresh is ignored")
        self.assertEqual(s.source_weapon, "bow")
        s.refresh_aura(now=3.0, duration=4.0, weapon_id="")
        self.assertAlmostEqual(s.aura_expires_at, 7.0)
        self.assertEqual(s.source_weapon, "bow", "an unnamed refresh keeps the owner")

    def test_consuming_empties_the_slot_and_reports_what_was_there(self):
        s = ElementalState()
        s.set_aura(ICE, now=0.0, duration=4.0)
        self.assertEqual(s.consume_aura(), ICE)
        self.assertFalse(s.has_aura(0.0))

    def test_a_lock_only_ever_extends(self):
        s = ElementalState()
        s.lock(now=0.0, seconds=4.0)
        s.lock(now=0.0, seconds=1.0)
        self.assertAlmostEqual(s.locked_until, 4.0, msg="the longer lock wins")
        self.assertTrue(s.is_locked(3.9))
        self.assertFalse(s.is_locked(4.0))

    def test_clear_returns_everything_to_a_fresh_slot(self):
        s = ElementalState()
        s.set_aura(FIRE, 0.0, 4.0, "sword")
        s.lock(0.0, 5.0)
        s.add_ice_stack(3)
        s.freeze_immune_until = 9.0
        s.clear()
        self.assertEqual(s.element(0.0), ElementId.NONE)
        self.assertFalse(s.is_locked(0.0))
        self.assertEqual(s.ice_stacks, 0)
        self.assertFalse(s.freeze_immune(0.0))


# --- statuses ------------------------------------------------------------------

class StatusFrameworkTests(unittest.TestCase):
    def test_freeze_is_a_stun_family_row_so_it_stops_everything(self):
        st = StatusState()
        st.apply("freeze", 2.0, 1.0)
        self.assertTrue(st.is_stunned())
        self.assertEqual(st.speed_multiplier(), 0.0)
        self.assertIn("freeze", st)
        self.assertNotIn("stun", st, "it is its own row, not the Hammer's stun")

    def test_a_bound_status_ends_with_the_aura_and_an_unbound_one_does_not(self):
        st = StatusState()
        st.apply("burn", 4.0, 2.0, bound_to_aura=True)
        st.apply("bleed", 4.0, 1.0)
        self.assertEqual(st.end_bound(), ("burn",))
        self.assertNotIn("burn", st)
        self.assertIn("bleed", st, "a blessing's own status is untouched")

    def test_the_binding_follows_the_most_recent_application(self):
        st = StatusState()
        st.apply("burn", 4.0, 2.0, bound_to_aura=True)      # Fire's burn
        st.apply("burn", 4.0, 2.0, bound_to_aura=False)     # Scorch takes it over
        self.assertFalse(st.is_bound("burn"))
        self.assertEqual(st.end_bound(), ())
        self.assertIn("burn", st, "the blessing's burn outlives the aura")
        st.apply("burn", 4.0, 2.0, bound_to_aura=True)      # Fire takes it back
        self.assertTrue(st.is_bound("burn"))

    def test_apply_reports_the_stack_count(self):
        st = StatusState()
        self.assertEqual(st.apply("burn", 2.0, 1.0), 1)
        self.assertEqual(st.apply("burn", 2.0, 1.0), 2)
        self.assertEqual(st.apply("chill", 2.0, 0.2), 1)
        self.assertEqual(st.apply("chill", 2.0, 0.2), 1, "chill is refresh-only")

    def test_set_potency_can_lower_one_where_apply_cannot(self):
        st = StatusState()
        st.apply("chill", 2.0, 0.5)
        st.apply("chill", 2.0, 0.1)
        self.assertAlmostEqual(st.potency("chill"), 0.5, msg="apply only raises")
        st.set_potency("chill", 0.1)
        self.assertAlmostEqual(st.potency("chill"), 0.1)

    def test_a_tick_names_its_effect_only_when_the_entry_has_one(self):
        st = StatusState()
        st.apply("burn", 2.0, 3.0, source="sword")
        two_arg = []
        st.update(0.6, lambda amount, source: two_arg.append((amount, source)))
        self.assertEqual(two_arg, [(3.0, "sword")], "existing callbacks are unchanged")

        st = StatusState()
        st.apply("burn", 2.0, 3.0, source="sword", effect=track.BURN)
        three = []
        st.update(0.6, lambda amount, source, effect=None: three.append((amount, source, effect)))
        self.assertEqual(three, [(3.0, "sword", "burn")])

    def test_ending_a_status_outright(self):
        st = StatusState()
        st.apply("chill", 2.0, 0.2)
        self.assertTrue(st.end("chill"))
        self.assertFalse(st.end("chill"))


# --- the five resolution steps -----------------------------------------------------

class ResolutionTests(unittest.TestCase):
    def test_an_empty_slot_takes_the_aura_and_lands_the_element(self):
        r = resolver()
        e = enemy()
        self.assertEqual(r.apply(e, FIRE, weapon_id="sword", hit_damage=10.0, now=1.0),
                         Outcome.APPLIED)
        self.assertEqual(e.elemental.element(1.0), FIRE)
        self.assertEqual(e.elemental.source_weapon, "sword")
        fire = r.registry.element(FIRE)
        self.assertEqual(len(fire.landed), 1)
        self.assertEqual(fire.applied, [(True, False)], "bound, not a refresh")

    def test_the_same_element_again_refreshes_rather_than_reacting(self):
        r = resolver()
        e = enemy()
        r.apply(e, FIRE, now=0.0)
        out = r.apply(e, FIRE, now=1.0)
        self.assertEqual(out, Outcome.REFRESHED)
        duration = r.registry.config(FIRE).aura.duration
        self.assertAlmostEqual(e.elemental.aura_expires_at, 1.0 + duration)
        self.assertEqual(r.registry.element(FIRE).applied, [(True, False), (True, True)])

    def test_an_expired_aura_is_a_fresh_application_not_a_reaction(self):
        r = resolver()
        e = enemy()
        r.apply(e, FIRE, now=0.0)
        late = r.registry.config(FIRE).aura.duration + 1.0
        self.assertEqual(r.apply(e, ICE, now=late), Outcome.APPLIED)
        self.assertEqual(e.elemental.element(late), ICE)

    def test_a_different_element_consumes_the_aura_and_reacts(self):
        seen = []
        r = resolver(runner=lambda t, v, c, ctx: seen.append((v.reaction, v.incoming)))
        e = enemy()
        r.apply(e, FIRE, weapon_id="sword", now=0.0)
        out = r.apply(e, ICE, weapon_id="bow", hit_damage=10.0, now=1.0)
        self.assertEqual(out, Outcome.REACTION)
        self.assertEqual(seen, [(ReactionId.FROSTBURN, ICE)])
        self.assertFalse(e.elemental.has_aura(1.0), "the incoming element leaves none")

    def test_the_incoming_element_deals_no_initial_effect_on_a_reaction(self):
        r = resolver(runner=lambda *a: None)
        e = enemy()
        r.apply(e, FIRE, now=0.0)
        before = len(r.registry.element(ICE).landed)
        r.apply(e, ICE, now=1.0)
        self.assertEqual(len(r.registry.element(ICE).landed), before,
                         "the reaction replaces it entirely")

    def test_the_consumed_elements_aura_ended_hook_fires_with_the_reason(self):
        r = resolver(runner=lambda *a: None)
        e = enemy()
        r.apply(e, FIRE, now=0.0)
        r.apply(e, ICE, now=1.0)
        self.assertEqual(r.registry.element(FIRE).ended, [AuraEnd.CONSUMED])

    def test_a_consumed_aura_takes_its_bound_statuses_with_it(self):
        r = resolver(runner=lambda *a: None)
        e = enemy()
        r.apply(e, FIRE, now=0.0)
        e.status.apply("burn", 9.0, 2.0, bound_to_aura=True)
        e.status.apply("bleed", 9.0, 1.0)
        r.apply(e, ICE, now=1.0)
        self.assertNotIn("burn", e.status, "the resolver owns the binding contract")
        self.assertIn("bleed", e.status)

    def test_no_element_is_nothing_at_all(self):
        r = resolver()
        e = enemy()
        self.assertEqual(r.apply(e, ElementId.NONE, now=0.0), Outcome.NONE)
        self.assertFalse(e.elemental.has_aura(0.0))

    def test_a_dead_target_resolves_outward_but_takes_nothing(self):
        """The death rule (2026-09-21). Its own module covers what the
        element still sends outward; here, that the body stays clean and
        the outcome says so."""
        r = resolver()
        e = enemy()
        e.alive = False
        self.assertEqual(r.apply(e, FIRE, now=0.0), Outcome.OUTWARD)
        self.assertFalse(e.elemental.has_aura(0.0))
        self.assertNotIn("burn", e.status)
        self.assertEqual(r.stats.corpse_hits, 1)


# --- the lock -----------------------------------------------------------------

class LockTests(unittest.TestCase):
    def test_every_reaction_starts_the_global_cooldown(self):
        cooldown = 2.0
        r = resolver(runner=lambda *a: None, reaction_aura_cooldown=cooldown)
        e = enemy()
        r.apply(e, FIRE, now=0.0)
        r.apply(e, THUNDER, now=1.0)        # Overload: no lock of its own
        self.assertTrue(e.elemental.is_locked(1.0 + cooldown - 0.01))
        self.assertFalse(e.elemental.is_locked(1.0 + cooldown))

    def test_frostburn_holds_the_slot_longer_than_the_global_cooldown(self):
        r = resolver(runner=lambda *a: None, reaction_aura_cooldown=0.5)
        e = enemy()
        r.apply(e, FIRE, now=0.0)
        r.apply(e, ICE, now=0.0)
        own = C.reactions["reactions"]["frostburn"]["lock_duration"]
        self.assertGreater(own, 0.5, "the shipped data is what makes this a real case")
        self.assertAlmostEqual(e.elemental.locked_until, own)

    def test_a_hit_on_a_locked_slot_lands_but_leaves_nothing(self):
        r = resolver(runner=lambda *a: None)
        e = enemy()
        r.apply(e, FIRE, now=0.0)
        r.apply(e, ICE, now=0.0)                       # locks the slot
        out = r.apply(e, THUNDER, weapon_id="rod", hit_damage=5.0, now=0.1)
        self.assertEqual(out, Outcome.LOCKED)
        self.assertFalse(e.elemental.has_aura(0.1))
        thunder = r.registry.element(THUNDER)
        self.assertEqual(len(thunder.landed), 1, "the element still lands")
        self.assertEqual(thunder.applied, [(False, False)], "its statuses are standalone")

    def test_the_slot_takes_an_aura_again_once_the_lock_lapses(self):
        r = resolver(runner=lambda *a: None, reaction_aura_cooldown=1.0)
        e = enemy()
        r.apply(e, FIRE, now=0.0)
        r.apply(e, THUNDER, now=0.0)
        self.assertEqual(r.apply(e, WIND, now=1.0), Outcome.APPLIED)


# --- the per-frame reaction budget ---------------------------------------------------

class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.ran = []
        self.r = resolver(runner=lambda t, v, c, ctx: self.ran.append(v.reaction),
                          max_reactions_per_frame=1)

    def _primed(self, n):
        out = []
        for _ in range(n):
            e = enemy()
            self.r.apply(e, FIRE, now=0.0)
            out.append(e)
        return out

    def test_reactions_past_the_budget_are_deferred_not_dropped(self):
        a, b = self._primed(2)
        self.r.begin_frame(0.0)
        self.assertEqual(self.r.apply(a, THUNDER, now=0.0), Outcome.REACTION)
        self.assertEqual(self.r.apply(b, THUNDER, now=0.0), Outcome.DEFERRED)
        self.assertEqual(len(self.ran), 1)
        self.assertEqual(self.r.pending, 1)

        self.r.begin_frame(0.02)
        self.assertEqual(len(self.ran), 2, "the next frame runs it")
        self.assertEqual(self.r.pending, 0)

    def test_a_deferred_reaction_has_already_consumed_its_aura_and_locked(self):
        a, b = self._primed(2)
        self.r.begin_frame(0.0)
        self.r.apply(a, THUNDER, now=0.0)
        self.r.apply(b, THUNDER, now=0.0)
        self.assertFalse(b.elemental.has_aura(0.0), "it can never fire twice")
        self.assertTrue(b.elemental.is_locked(0.0))

    def test_an_enemy_that_dies_while_waiting_still_gets_its_reaction(self):
        """The death rule: the blast was owed to the enemies around it,
        and the reaction reads only its position."""
        a, b = self._primed(2)
        self.r.begin_frame(0.0)
        self.r.apply(a, THUNDER, now=0.0)
        self.r.apply(b, THUNDER, now=0.0)
        b.alive = False
        self.r.begin_frame(0.02)
        self.assertEqual(len(self.ran), 2)
        self.assertEqual(self.r.pending, 0)

    def test_a_backlog_drains_one_frame_at_a_time(self):
        enemies = self._primed(4)
        self.r.begin_frame(0.0)
        for e in enemies:
            self.r.apply(e, THUNDER, now=0.0)
        self.assertEqual(len(self.ran), 1)
        for frame in range(1, 4):
            self.r.begin_frame(frame * 0.02)
            self.assertEqual(len(self.ran), frame + 1)
        self.assertEqual(self.r.pending, 0)


# --- enemy profiles -------------------------------------------------------------------

class ProfileParsingTests(unittest.TestCase):
    def parse(self, block):
        return prof.resolve({"boss": {"elementProfile": block}}, kind="boss")

    def test_no_overrides_means_every_type_shares_the_default(self):
        profiles, notes = prof.resolve(C.enemies, kind="enemy")
        self.assertEqual(notes, [], "the shipped data carries no profiles yet")
        self.assertTrue(all(p is prof.DEFAULT for p in profiles.values()))
        self.assertIn("skull", profiles)

    def test_a_value_override_replaces_the_data_value(self):
        profiles, notes = self.parse({"ice": {"freeze.stacks_required": 12}})
        self.assertEqual(notes, [])
        reg = registry()
        self.assertEqual(reg.config(ICE, profiles["boss"]).freeze.stacks_required, 12)
        self.assertNotEqual(reg.config(ICE).freeze.stacks_required, 12)

    def test_a_damage_multiplier_scales_every_damage_value_of_that_element(self):
        profiles, _ = self.parse({"damage_multiplier": {"fire": 0.5}})
        reg = registry()
        base, tough = reg.config(FIRE), reg.config(FIRE, profiles["boss"])
        self.assertAlmostEqual(tough.hit.damage.frac, base.hit.damage.frac * 0.5)
        self.assertAlmostEqual(tough.burn.tick.frac, base.burn.tick.frac * 0.5)
        self.assertEqual(tough.aura.duration, base.aura.duration, "only damage")

    def test_a_knockback_multiplier_scales_only_knockback(self):
        profiles, _ = self.parse({"overload": {"knockback_multiplier": 0.0}})
        reg = registry()
        cfg = reg.reaction_config(ReactionId.OVERLOAD, FIRE, profiles["boss"])
        self.assertEqual(cfg.knockback, 0.0)
        self.assertEqual(cfg.shockwave_radius,
                         reg.reaction_config(ReactionId.OVERLOAD, FIRE).shockwave_radius)

    def test_an_effect_toggle_reads_back(self):
        profiles, notes = self.parse({"freeze": {"enabled": False}})
        self.assertEqual(notes, [])
        p = profiles["boss"]
        self.assertFalse(p.enabled("freeze"))
        self.assertTrue(p.enabled("slow"))
        self.assertTrue(p.aura_enabled)

    def test_bad_entries_are_skipped_with_a_note_and_never_raise(self):
        cases = [
            ({"earth": {"x": 1}}, "not an element"),
            ({"ice": {"freeze.nonsense": 1}}, "is not a value of ice"),
            ({"ice": {"freeze.stacks_required": "many"}}, "not a number"),
            ({"freeze": {"enabled": "no"}}, "not true/false"),
            ({"freeze": {}}, "needs"),
            ({"damage_multiplier": {"fire": -1}}, "not a multiplier"),
            ({"damage_multiplier": {"nope": 1}}, "not an element or reaction"),
            ({"ice": 5}, "not an object"),
        ]
        for block, needle in cases:
            with self.subTest(block=block):
                profiles, notes = self.parse(block)
                self.assertTrue(any(needle in n for n in notes), notes)
                self.assertTrue(profiles["boss"].is_default
                                or not profiles["boss"].touches("ice"))

    def test_a_good_entry_survives_a_bad_one_beside_it(self):
        profiles, notes = self.parse(
            {"ice": {"freeze.stacks_required": 9, "freeze.bogus": 1}})
        self.assertEqual(len(notes), 1)
        self.assertEqual(registry().config(ICE, profiles["boss"]).freeze.stacks_required, 9)

    def test_a_profile_that_says_nothing_usable_is_the_shared_default(self):
        profiles, _ = self.parse({"earth": {"x": 1}})
        self.assertIs(profiles["boss"], prof.DEFAULT)

    def test_comment_keys_are_ignored(self):
        profiles, notes = self.parse({"_why": "tanky", "ice": {"_note": "x",
                                                               "freeze.duration": 1.0}})
        self.assertEqual(notes, [])
        self.assertEqual(registry().config(ICE, profiles["boss"]).freeze.duration, 1.0)


class ProfileBehaviourTests(unittest.TestCase):
    def test_an_aura_toggle_makes_the_type_immune_to_reactions(self):
        profiles, _ = prof.resolve(
            {"tank": {"elementProfile": {"aura": {"enabled": False}}}})
        ran = []
        r = resolver(profiles=profiles, runner=lambda *a: ran.append(a))
        e = enemy(enemy_id="tank")
        self.assertEqual(r.apply(e, FIRE, now=0.0), Outcome.LOCKED)
        self.assertEqual(r.apply(e, ICE, now=0.0), Outcome.LOCKED)
        self.assertEqual(ran, [], "it never reacts")
        self.assertFalse(e.elemental.has_aura(0.0))
        self.assertEqual(len(r.registry.element(FIRE).landed), 1,
                         "but the element still damages it")

    def test_an_unlisted_type_still_gets_the_default_profile(self):
        r = resolver(profiles={"tank": prof.ElementProfile("t", disabled=("aura",))})
        e = enemy(enemy_id="skull")
        self.assertEqual(r.apply(e, FIRE, now=0.0), Outcome.APPLIED)

    def test_profile_and_buff_compose_with_the_buff_first(self):
        profiles, _ = prof.resolve(
            {"tank": {"elementProfile": {"damage_multiplier": {"fire": 0.5}}}})
        reg = registry()
        reg.modifiers(FIRE).add("hit.damage.frac", source="blessing", mult=4.0)
        base = C.elements["elements"]["fire"]["hit"]["damage"]["frac"]
        self.assertAlmostEqual(reg.config(FIRE, profiles["tank"]).hit.damage.frac,
                               base * 4.0 * 0.5)


# --- tracking ---------------------------------------------------------------------

class TrackingTests(unittest.TestCase):
    def test_an_application_is_counted_however_the_hit_resolves(self):
        t = ElementTracking()
        r = resolver(tracking=t, runner=lambda *a: None)
        e = enemy()
        r.apply(e, FIRE, weapon_id="sword", now=0.0)     # applied
        r.apply(e, FIRE, weapon_id="sword", now=0.1)     # refreshed
        r.apply(e, ICE, weapon_id="bow", now=0.2)        # reaction
        r.apply(e, WIND, weapon_id="rod", now=0.3)       # locked
        self.assertEqual(t.applications[("sword", "fire")], 2)
        self.assertEqual(t.applications[("bow", "ice")], 1)
        self.assertEqual(t.applications[("rod", "wind")], 1)

    def test_a_reaction_is_credited_to_the_weapon_that_triggered_it(self):
        t = ElementTracking()
        r = resolver(tracking=t, runner=lambda *a: None)
        e = enemy()
        r.apply(e, FIRE, weapon_id="sword", now=0.0)
        r.apply(e, THUNDER, weapon_id="rod", now=0.1)
        self.assertEqual(t.reactions, {("rod", "overload"): 1},
                         "the incoming element's weapon owns the reaction")

    def test_damage_is_filed_under_the_effect_and_the_weapon(self):
        t = ElementTracking()
        t.record_damage(30.0, "rod", track.OVERLOAD)
        t.record_damage(12.0, "sword", track.OVERLOAD)
        t.record_damage(5.0, "sword", track.BURN)
        self.assertEqual(t.damage_by_effect(), {"overload": 42.0, "burn": 5.0})
        self.assertEqual(t.damage_by_weapon(), {"rod": 30.0, "sword": 17.0})
        self.assertEqual(t.total_damage, 47.0)

    def test_effect_rows_are_biggest_first_and_named_for_the_screen(self):
        t = ElementTracking()
        t.record_damage(5.0, "sword", track.BURN)
        t.record_damage(30.0, "rod", track.OVERLOAD)
        rows = t.effect_rows()
        self.assertEqual([r["id"] for r in rows], ["overload", "burn"])
        self.assertEqual(rows[0]["name"], "Overload")
        self.assertEqual(rows[0]["by_weapon"], {"rod": 30.0})

    def test_unnamed_sources_land_in_the_other_bucket_and_zero_is_ignored(self):
        t = ElementTracking()
        t.record_damage(4.0, "", track.BURN)
        t.record_damage(0.0, "sword", track.BURN)
        t.record_damage(4.0, "sword", "")
        self.assertEqual(t.damage, {("other", "burn"): 4.0})

    def test_the_ledger_files_a_second_dimension_without_moving_the_first(self):
        from game.states.playing.core.run_ledger import RunLedger
        ledger = RunLedger()
        ledger.record(10.0, "sword")
        ledger.record(6.0, "sword", track.BURN)
        self.assertEqual(ledger.damage["sword"], 16.0, "the weapon row is whole")
        self.assertEqual(ledger.total, 16.0, "...so the smoke test's pin holds")
        self.assertEqual(ledger.elements.damage, {("sword", "burn"): 6.0})

    def test_the_snapshot_is_plain_data(self):
        t = ElementTracking()
        t.record_damage(3.0, "sword", track.BURN)
        t.record_application("sword", FIRE)
        snap = t.snapshot()
        self.assertEqual(snap["total"], 3.0)
        self.assertEqual(snap["applications"], [{"weapon": "sword", "element": "fire",
                                                 "count": 1}])
        self.assertEqual(t.counts_for("sword"), {"fire": 1})


# --- counters the dev overlay reads --------------------------------------------------

class StatsTests(unittest.TestCase):
    def test_the_resolver_counts_what_it_did(self):
        r = resolver(runner=lambda *a: None)
        e = enemy()
        r.apply(e, FIRE, now=0.0)
        r.apply(e, ICE, now=0.0)
        r.apply(e, WIND, now=0.0)          # locked by Frostburn
        self.assertEqual(r.stats.applications, 3)
        self.assertEqual(r.stats.reactions_total, 1)
        self.assertEqual(r.stats.locked_hits, 1)
        self.assertEqual(r.stats.by_outcome[Outcome.APPLIED], 1)

    def test_active_auras_counts_only_live_ones(self):
        r = resolver()
        held, lapsed = enemy(), enemy()
        r.apply(held, FIRE, now=0.0)
        r.apply(lapsed, FIRE, now=0.0)
        self.assertEqual(r.active_auras([held, lapsed], 0.5), 2)
        late = r.registry.config(FIRE).aura.duration + 1.0
        self.assertEqual(r.active_auras([held, lapsed], late), 0)


if __name__ == "__main__":
    unittest.main()
