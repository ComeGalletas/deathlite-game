"""Elemental system M1: ids, the config schema, JSON validation and baking,
the modifier layer and the registry (design §2, journal
`elemental_system_journal.md`).

Unit tier: hand-built data, no world, no Game. The shipped files are read
once through `get_content` to prove they load; every failure case is built
from a copy of them so the shipped data stays the one source of numbers.
"""
import copy
import unittest

from combat.elements import config as schema
from combat.elements.base import AuraEnd, Element
from combat.elements.ids import (
    ELEMENTS, REACTIONS, ElementId, ReactionId, element_from_key, reaction_from_key)
from combat.elements.registry import ElementRegistry, get_registry
from combat.elements.schema import (
    DamageSpec, ElementDataError, PairSpec, Section, deep_merge, dmg, f, i, pair)
from game.content import ContentError, get_content

C = get_content()


def elements_data():
    return copy.deepcopy(C.elements)


def reactions_data():
    return copy.deepcopy(C.reactions)


def registry(elements=None, reactions=None) -> ElementRegistry:
    return ElementRegistry(elements or elements_data(), reactions or reactions_data())


# --- ids ----------------------------------------------------------------------------

class IdTests(unittest.TestCase):
    def test_none_is_zero_and_the_four_elements_follow_in_order(self):
        self.assertEqual(int(ElementId.NONE), 0)
        self.assertEqual([int(e) for e in ELEMENTS], [1, 2, 3, 4])
        self.assertEqual([e.key for e in ELEMENTS], ["fire", "ice", "thunder", "wind"])

    def test_keys_round_trip(self):
        for e in ELEMENTS:
            self.assertIs(element_from_key(e.key), e)
        for r in REACTIONS:
            self.assertIs(reaction_from_key(r.key), r)
        with self.assertRaises(KeyError):
            element_from_key("none")

    def test_every_unordered_pair_has_exactly_one_reaction(self):
        pairs = {frozenset(p) for p in schema.REACTION_PAIRS.values()}
        self.assertEqual(len(pairs), 6)
        self.assertEqual(len(schema.REACTION_PAIRS), len(REACTIONS))
        for pair in pairs:
            self.assertEqual(len(pair), 2, "a reaction pairs two different elements")


# --- the schema language ------------------------------------------------------------

class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.s = Section("Demo", {
            "count": i(1), "rate": f(0.0, 1.0), "life": f(0.0, lo_open=True),
            "dmg": dmg(), "duo": pair(),
            "inner": Section("Inner", {"on": f(0.0)}),
        })
        self.ok = {"count": 2, "rate": 0.5, "life": 1.0, "dmg": {"frac": 0.3},
                   "duo": {"high": 0.5, "low": 0.2}, "inner": {"on": 1.0}}

    def test_a_valid_block_bakes_to_an_immutable_record(self):
        rec = self.s.bake(self.s.validate("demo", self.ok))
        self.assertEqual(rec.count, 2)
        self.assertEqual(rec.inner.on, 1.0)
        self.assertEqual(rec.dmg, DamageSpec(frac=0.3, flat=None))
        self.assertEqual(rec.duo, PairSpec(high=0.5, low=0.2))
        with self.assertRaises(AttributeError):
            rec.count = 5

    def test_unknown_key_missing_key_and_bad_types_raise(self):
        with self.assertRaisesRegex(ElementDataError, "unknown key"):
            self.s.validate("demo", {**self.ok, "bogus": 1})
        with self.assertRaisesRegex(ElementDataError, "missing"):
            self.s.validate("demo", {k: v for k, v in self.ok.items() if k != "rate"})
        with self.assertRaisesRegex(ElementDataError, "whole number"):
            self.s.validate("demo", {**self.ok, "count": 1.5})
        with self.assertRaisesRegex(ElementDataError, "expected a number"):
            self.s.validate("demo", {**self.ok, "rate": True})
        with self.assertRaisesRegex(ElementDataError, "expected an object"):
            self.s.validate("demo", {**self.ok, "inner": 3})

    def test_ranges_are_enforced_including_open_lower_bounds(self):
        with self.assertRaisesRegex(ElementDataError, "must be >= 1"):
            self.s.validate("demo", {**self.ok, "count": 0})
        with self.assertRaisesRegex(ElementDataError, "must be <= 1.0"):
            self.s.validate("demo", {**self.ok, "rate": 1.5})
        with self.assertRaisesRegex(ElementDataError, "must be > 0.0"):
            self.s.validate("demo", {**self.ok, "life": 0.0})

    def test_comment_keys_are_ignored(self):
        out = self.s.validate("demo", {**self.ok, "_note": "hello"})
        self.assertNotIn("_note", out)

    def test_partial_validation_allows_missing_but_not_unknown(self):
        self.assertEqual(self.s.validate("demo", {"count": 3}, partial=True), {"count": 3})
        with self.assertRaisesRegex(ElementDataError, "unknown key"):
            self.s.validate("demo", {"nope": 3}, partial=True)

    def test_damage_needs_exactly_one_of_frac_or_flat(self):
        for bad in ({}, {"frac": 0.1, "flat": 2}, {"pct": 1}, 3, {"frac": -1}):
            with self.subTest(bad=bad), self.assertRaises(ElementDataError):
                self.s.validate("demo", {**self.ok, "dmg": bad})
        rec = self.s.bake(self.s.validate("demo", {**self.ok, "dmg": {"flat": 12}}))
        self.assertEqual(rec.dmg.resolve(100.0), 12.0)
        rec = self.s.bake(self.s.validate("demo", self.ok))
        self.assertAlmostEqual(rec.dmg.resolve(100.0), 30.0)

    def test_leaf_paths_are_dotted_and_damage_and_pair_contribute_both(self):
        self.assertEqual(self.s.paths(), (
            "count", "rate", "life", "dmg.frac", "dmg.flat",
            "duo.high", "duo.low", "inner.on"))

    def test_deep_merge_replaces_a_damage_dict_whole(self):
        merged = deep_merge({"dmg": {"frac": 0.3}, "inner": {"on": 1.0, "x": 2}},
                            {"dmg": {"flat": 5}, "inner": {"on": 2.0}})
        self.assertEqual(merged, {"dmg": {"flat": 5}, "inner": {"on": 2.0, "x": 2}})


# --- the shipped data ------------------------------------------------------------------

class ShippedDataTests(unittest.TestCase):
    def test_elements_json_covers_the_four_elements_and_the_global_block(self):
        self.assertEqual(set(C.elements["elements"]), {e.key for e in ELEMENTS})
        g = C.elements["global"]
        self.assertGreaterEqual(g["reaction_aura_cooldown"], 0.0)
        self.assertGreaterEqual(g["max_reactions_per_frame"], 1)

    def test_reactions_json_covers_the_six_reactions(self):
        self.assertEqual(set(C.reactions["reactions"]), {r.key for r in REACTIONS})

    def test_frostburn_ships_with_an_extended_lock_and_the_others_do_not(self):
        r = C.reactions["reactions"]
        self.assertTrue(r["frostburn"]["lock_aura_slot"])
        self.assertGreater(r["frostburn"]["lock_duration"], 0.0)
        for rid in REACTIONS:
            if rid is not ReactionId.FROSTBURN:
                self.assertFalse(r[rid.key]["lock_aura_slot"], rid.key)

    def test_the_whole_registry_bakes_from_the_shipped_files(self):
        reg = get_registry(C)
        self.assertIs(get_registry(C), reg, "one registry per content object")
        for eid in ELEMENTS:
            cfg = reg.config(eid)
            self.assertGreater(cfg.aura.duration, 0.0)
        for rid in REACTIONS:
            a, b = schema.REACTION_PAIRS[rid]
            self.assertEqual(reg.reaction_config(rid, a), reg.reaction_config(rid, b),
                             f"{rid.key}: identical in both directions with no override")


# --- validation of element data ----------------------------------------------------

class ElementValidationTests(unittest.TestCase):
    def test_a_missing_element_or_an_extra_one_fails(self):
        d = elements_data()
        del d["elements"]["wind"]
        with self.assertRaisesRegex(ElementDataError, "covers"):
            schema.check_elements(d)
        d = elements_data()
        d["elements"]["earth"] = d["elements"]["fire"]
        with self.assertRaisesRegex(ElementDataError, "covers"):
            schema.check_elements(d)

    def test_bad_values_name_their_path(self):
        d = elements_data()
        d["elements"]["thunder"]["chain"]["jumps"] = -1
        with self.assertRaisesRegex(ElementDataError, r"thunder\.chain\.jumps"):
            schema.check_elements(d)
        d = elements_data()
        d["elements"]["ice"]["slow"]["max_percent"] = 1.2
        with self.assertRaisesRegex(ElementDataError, r"ice\.slow\.max_percent"):
            schema.check_elements(d)
        d = elements_data()
        d["elements"]["fire"]["aura"]["duration"] = 0
        with self.assertRaisesRegex(ElementDataError, r"fire\.aura\.duration"):
            schema.check_elements(d)

    def test_an_unknown_key_anywhere_fails(self):
        d = elements_data()
        d["elements"]["fire"]["burn"]["stacks"] = 3
        with self.assertRaisesRegex(ElementDataError, "unknown key"):
            schema.check_elements(d)
        d = elements_data()
        d["global"]["tornado_speed"] = 3
        with self.assertRaisesRegex(ElementDataError, "unknown key"):
            schema.check_elements(d)

    def test_content_turns_the_error_into_a_content_error(self):
        from game import content as content_module
        d = elements_data()
        d["global"].pop("reaction_aura_cooldown")
        with self.assertRaises(ContentError):
            content_module._check_elements(d)
        r = reactions_data()
        r["reactions"]["overload"]["knockback"] = -5
        with self.assertRaises(ContentError):
            content_module._check_reactions(r)


# --- validation of reaction data -----------------------------------------------------

class ReactionValidationTests(unittest.TestCase):
    def test_a_missing_reaction_fails(self):
        r = reactions_data()
        del r["reactions"]["icewind"]
        with self.assertRaisesRegex(ElementDataError, "covers"):
            schema.check_reactions(r)

    def test_an_override_may_only_name_the_pairs_elements(self):
        r = reactions_data()
        r["reactions"]["overload"]["triggered_by"] = {"ice": {"knockback": 1.0}}
        with self.assertRaisesRegex(ElementDataError, "not one of"):
            schema.check_reactions(r)

    def test_an_override_may_only_touch_existing_keys(self):
        r = reactions_data()
        r["reactions"]["overload"]["triggered_by"] = {"fire": {"radius": 1.0}}
        with self.assertRaisesRegex(ElementDataError, "unknown key"):
            schema.check_reactions(r)

    def test_an_override_value_is_range_checked(self):
        r = reactions_data()
        r["reactions"]["frostburn"]["triggered_by"] = {"ice": {"slow_percent": 2.0}}
        with self.assertRaisesRegex(ElementDataError, r"triggered_by\.ice\.slow_percent"):
            schema.check_reactions(r)

    def test_a_valid_override_is_kept_and_a_comment_trigger_is_ignored(self):
        r = reactions_data()
        r["reactions"]["overload"]["triggered_by"] = {
            "fire": {"damage": {"high": 0.9, "low": 0.2}},
            "_why": "fire hits harder"}
        out = schema.check_reactions(r)
        self.assertEqual(out["reactions"]["overload"]["triggered_by"],
                         {"fire": {"damage": {"high": 0.9, "low": 0.2}}})


class PairFieldTests(unittest.TestCase):
    """The two-source damage value the owner's 2026-09-22 rework introduced."""

    def setUp(self):
        self.s = Section("Demo", {"duo": pair()})

    def bake(self, high, low):
        return self.s.bake(self.s.validate(
            "demo", {"duo": {"high": high, "low": low}})).duo

    def test_it_pays_high_of_the_larger_and_low_of_the_smaller(self):
        spec = self.bake(0.5, 0.3)
        self.assertAlmostEqual(spec.resolve(100.0, 20.0), 0.5 * 100 + 0.3 * 20)

    def test_it_is_symmetric_in_its_two_arguments(self):
        """Which hit placed the aura and which triggered the reaction is
        bookkeeping; it must not change the figure."""
        spec = self.bake(0.5, 0.3)
        self.assertAlmostEqual(spec.resolve(100.0, 20.0),
                               spec.resolve(20.0, 100.0))

    def test_equal_coefficients_pay_the_same_share_of_both(self):
        """Which is how the Wind three are expressed: 30 % of each."""
        spec = self.bake(0.3, 0.3)
        self.assertAlmostEqual(spec.resolve(27.0, 6.0), 0.3 * (27.0 + 6.0))

    def test_both_halves_are_required_and_must_be_numbers_at_or_above_zero(self):
        for bad in ({"high": 0.5}, {"low": 0.5}, {}, {"high": 0.5, "low": -1},
                    {"high": 0.5, "low": True}, {"high": 0.5, "low": 0.2, "mid": 1}):
            with self.subTest(block=bad):
                with self.assertRaises(ElementDataError):
                    self.s.validate("demo", {"duo": bad})

    def test_a_modifier_can_address_either_coefficient(self):
        self.assertEqual(self.s.paths(), ("duo.high", "duo.low"))
        baked = self.s.bake(self.s.validate("demo", {"duo": {"high": 0.5, "low": 0.3}}),
                            lambda path, v: v * 2 if path == "duo.high" else v)
        self.assertEqual(baked.duo, PairSpec(1.0, 0.3))

    def test_every_shipped_reaction_declares_its_damage_as_a_pair(self):
        for rid in schema.REACTIONS:
            with self.subTest(reaction=rid.key):
                cfg = registry().reaction_config(
                    rid, schema.REACTION_PAIRS[rid][1])
                self.assertIsInstance(cfg.damage, PairSpec)


# --- directional variants ------------------------------------------------------------------

class VariantTests(unittest.TestCase):
    def test_an_override_applies_only_in_its_direction(self):
        r = reactions_data()
        r["reactions"]["overload"]["triggered_by"] = {
            "fire": {"damage": {"high": 0.9, "low": 0.2}},
            "thunder": {"shockwave_radius": 150}}
        reg = registry(reactions=schema.check_reactions(r))
        by_fire = reg.reaction_config(ReactionId.OVERLOAD, ElementId.FIRE)
        by_thunder = reg.reaction_config(ReactionId.OVERLOAD, ElementId.THUNDER)
        base = C.reactions["reactions"]["overload"]
        self.assertEqual(by_fire.damage, PairSpec(0.9, 0.2))
        self.assertEqual(by_thunder.damage,
                         PairSpec(base["damage"]["high"], base["damage"]["low"]))
        self.assertEqual(by_thunder.shockwave_radius, 150.0)
        self.assertEqual(by_fire.shockwave_radius, base["shockwave_radius"])

    def test_a_pair_override_replaces_both_halves_rather_than_blending(self):
        """`deep_merge` recurses into sub-objects, which would otherwise
        leave an override that named one coefficient carrying the base's
        other one -- a half-applied tuning value."""
        r = reactions_data()
        r["reactions"]["overload"]["triggered_by"] = {
            "fire": {"damage": {"high": 0.9, "low": 0.0}}}
        reg = registry(reactions=schema.check_reactions(r))
        self.assertEqual(reg.reaction_config(ReactionId.OVERLOAD, ElementId.FIRE).damage,
                         PairSpec(0.9, 0.0))

    def test_a_pair_override_must_name_both_coefficients(self):
        r = reactions_data()
        r["reactions"]["overload"]["triggered_by"] = {"fire": {"damage": {"high": 0.9}}}
        with self.assertRaises(ElementDataError):
            schema.check_reactions(r)

    def test_the_table_is_symmetric_in_type_and_empty_on_the_diagonal(self):
        reg = registry()
        for rid, (a, b) in schema.REACTION_PAIRS.items():
            self.assertEqual(reg.reaction(a, b).reaction, rid)
            self.assertEqual(reg.reaction(b, a).reaction, rid)
            self.assertEqual(reg.reaction(a, b).incoming, b)
            self.assertEqual(reg.reaction(b, a).incoming, a)
        for e in ElementId:
            self.assertIsNone(reg.reaction(e, e))
            self.assertIsNone(reg.reaction(ElementId.NONE, e))
            self.assertIsNone(reg.reaction(e, ElementId.NONE))

    def test_asking_for_a_variant_the_pair_cannot_trigger_raises(self):
        with self.assertRaises(KeyError):
            registry().reaction_config(ReactionId.OVERLOAD, ElementId.ICE)


# --- modifiers ----------------------------------------------------------------------------

class ModifierTests(unittest.TestCase):
    def test_config_is_cached_until_a_modifier_changes(self):
        reg = registry()
        first = reg.config(ElementId.THUNDER)
        self.assertIs(reg.config(ElementId.THUNDER), first)
        reg.modifiers(ElementId.THUNDER).add("chain.jumps", source="test", flat=1)
        second = reg.config(ElementId.THUNDER)
        self.assertIsNot(second, first)
        self.assertIs(reg.config(ElementId.THUNDER), second, "rebaked once, then cached")

    def test_flat_then_mult_and_ints_stay_ints(self):
        reg = registry()
        base = reg.config(ElementId.THUNDER).chain
        mods = reg.modifiers(ElementId.THUNDER)
        mods.add("chain.jumps", source="a", flat=2)
        mods.add("chain.jumps", source="b", mult=2.0)
        mods.add("chain.max_range", source="a", mult=1.5)
        cfg = reg.config(ElementId.THUNDER).chain
        self.assertEqual(cfg.jumps, (base.jumps + 2) * 2)
        self.assertIsInstance(cfg.jumps, int)
        self.assertAlmostEqual(cfg.max_range, base.max_range * 1.5)
        self.assertEqual(cfg.targets_per_jump, base.targets_per_jump, "untouched leaf")

    def test_a_damage_leaf_is_modifiable(self):
        reg = registry()
        reg.modifiers(ElementId.FIRE).add("hit.damage.frac", source="t", mult=2.0)
        self.assertAlmostEqual(reg.config(ElementId.FIRE).hit.damage.frac,
                               C.elements["elements"]["fire"]["hit"]["damage"]["frac"] * 2)

    def test_removing_a_source_restores_the_data_values(self):
        reg = registry()
        base = reg.config(ElementId.ICE)
        mods = reg.modifiers(ElementId.ICE)
        mods.add("freeze.stacks_required", source="boss", flat=7)
        self.assertNotEqual(reg.config(ElementId.ICE).freeze.stacks_required,
                            base.freeze.stacks_required)
        self.assertTrue(mods.remove_source("boss"))
        self.assertFalse(mods.remove_source("boss"))
        self.assertEqual(reg.config(ElementId.ICE), base)

    def test_a_modified_value_is_clamped_to_its_range(self):
        reg = registry()
        mods = reg.modifiers(ElementId.ICE)
        mods.add("slow.max_percent", source="t", flat=5.0)
        mods.add("freeze.stacks_required", source="t", flat=-100)
        cfg = reg.config(ElementId.ICE)
        self.assertEqual(cfg.slow.max_percent, 1.0)
        self.assertEqual(cfg.freeze.stacks_required, 1)

    def test_an_unknown_path_or_a_nameless_source_is_refused(self):
        mods = registry().modifiers(ElementId.WIND)
        with self.assertRaises(KeyError):
            mods.add("area.tornadoes", source="t", flat=1)
        with self.assertRaises(ValueError):
            mods.add("area.radius", source="", flat=1)

    def test_reaction_modifiers_reach_both_variants(self):
        reg = registry()
        mods = reg.reaction_modifiers(ReactionId.SUPERCONDUCT)
        mods.add("bonus_jumps", source="t", flat=1)
        base = C.reactions["reactions"]["superconduct"]["bonus_jumps"]
        for trig in (ElementId.ICE, ElementId.THUNDER):
            self.assertEqual(reg.reaction_config(ReactionId.SUPERCONDUCT, trig).bonus_jumps,
                             base + 1)
        self.assertEqual(mods.describe(), {"bonus_jumps": (1.0, 1.0)})

    def test_clear_modifiers_resets_everything(self):
        reg = registry()
        reg.modifiers(ElementId.FIRE).add("aura.duration", source="t", mult=3.0)
        reg.reaction_modifiers(ReactionId.OVERLOAD).add("knockback", source="t", flat=9)
        reg.clear_modifiers()
        self.assertEqual(reg.config(ElementId.FIRE).aura.duration,
                         C.elements["elements"]["fire"]["aura"]["duration"])
        self.assertEqual(reg.reaction_config(ReactionId.OVERLOAD, ElementId.FIRE).knockback,
                         C.reactions["reactions"]["overload"]["knockback"])


# --- the registry's elements ------------------------------------------------------------

class RegistryElementTests(unittest.TestCase):
    def test_placeholders_fill_every_slot_until_the_real_elements_land(self):
        reg = registry()
        self.assertEqual([e.id for e in reg.elements], list(ELEMENTS))
        for e in reg.elements:
            self.assertIsInstance(e, Element)
        with self.assertRaises(KeyError):
            reg.element(ElementId.NONE)

    def test_a_registered_class_replaces_the_placeholder(self):
        class Ember(Element):
            ID = ElementId.FIRE

        reg = ElementRegistry(elements_data(), reactions_data(), {ElementId.FIRE: Ember})
        self.assertIsInstance(reg.element(ElementId.FIRE), Ember)
        self.assertEqual(reg.element(ElementId.FIRE).key, "fire")
        self.assertNotIsInstance(reg.element(ElementId.ICE), Ember)

    def test_the_default_hooks_are_no_ops(self):
        e = Element(ElementId.WIND)
        e.apply_initial_effect(None, None)
        e.on_applied(None, None)
        e.on_aura_ended(None, AuraEnd.CONSUMED, None)


if __name__ == "__main__":
    unittest.main()
