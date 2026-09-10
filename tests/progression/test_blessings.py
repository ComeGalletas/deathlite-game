"""Six-weapon system P2 (design §21): the blessing catalog, applying levels,
gating on owned weapons, the weapon grants and their bundled level-I
blessing, and the offering weights."""
import random
import unittest

from combat.weapons import Weapon
from entities.player import Player
from game.content import get_content
from progression.blessings import (CATEGORIES, KINDS, RARITIES, Catalog,
                                   OfferingRules, apply_blessing, get_catalog,
                                   get_rules, grant_offers, roll_offering,
                                   valid_offers)
from progression.blessings.catalog import format_value, roman
from progression.blessings.offer import (blessing_offers, blessing_weight,
                                         bundle_candidates)

C = get_content()
CAT = get_catalog(C)
RULES = get_rules(C)


def hero(*wids):
    p = Player(0, 0)
    p.weapons = [Weapon(w, C.weapon(w)) for w in wids]
    return p


def weapon(p, wid):
    return next(w for w in p.weapons if w.weapon_id == wid)


class CatalogTests(unittest.TestCase):
    def test_every_entry_is_typed_and_five_levels_deep(self):
        for bid, b in CAT.by_id.items():
            self.assertIn(b.kind, KINDS, bid)
            self.assertIn(b.rarity, RARITIES, bid)
            self.assertIn(b.category, CATEGORIES, bid)
            self.assertEqual(b.max_level, 5, bid)
            for e in b.effects:
                self.assertEqual(len(e.levels), 5, bid)

    def test_weapon_blessings_name_real_weapons_and_stat_ones_none(self):
        for bid, b in CAT.by_id.items():
            if b.kind == "weapon":
                self.assertIn(b.weapon, C.weapons, bid)
            else:
                self.assertIsNone(b.weapon, bid)

    def test_every_weapon_and_summon_has_blessings(self):
        for wid in C.weapons:
            self.assertGreaterEqual(len(CAT.for_weapon(wid)), 3, wid)

    def test_the_stat_blessings_cover_the_design_list(self):
        stats = {e.stat for b in CAT.of_kind("stat") for e in b.effects}
        for s in ("max_hp", "move_speed", "xp_gain", "gold_gain", "melee_damage",
                  "ranged_damage", "block_chance", "evasion_chance", "crit_chance",
                  "block_strength"):
            self.assertIn(s, stats)

    def test_levels_are_monotone_in_the_direction_that_helps(self):
        for bid, b in CAT.by_id.items():
            for e in b.effects:
                lv = list(e.levels)
                if e.type == "weapon_bonus" and e.mode == "mult":
                    self.assertTrue(all(0.0 < v for v in lv), bid)
                    self.assertTrue(lv == sorted(lv) or lv == sorted(lv, reverse=True), bid)
                else:
                    self.assertEqual(lv, sorted(lv), bid)

    def test_descriptions_format_at_every_level(self):
        for b in CAT.by_id.values():
            for level in range(1, b.max_level + 1):
                text = b.describe(level)
                self.assertNotIn("{", text, b.id)
                self.assertTrue(b.title(level).endswith(roman(level)), b.id)

    def test_format_value(self):
        self.assertEqual(format_value(20, "flat"), "+20")
        self.assertEqual(format_value(0.25, "pct"), "+25%")
        self.assertEqual(format_value(0.84, "pct_drop"), "16%")
        self.assertEqual(format_value(0.3, "seconds"), "+0.3s")
        self.assertEqual(format_value(2.2, "mult"), "x2.2")

    def test_bad_data_raises(self):
        bad = {"x": {"name": "X", "kind": "weapon", "weapon": "axe", "category": "power",
                     "rarity": "common", "description": "", "effects": [
                         {"type": "weapon_bonus", "field": "damage", "levels": [1]}]}}
        with self.assertRaises(ValueError):
            Catalog(bad, C.weapons)
        bad["x"]["weapon"] = "sword"
        bad["x"]["rarity"] = "mythic"
        with self.assertRaises(ValueError):
            Catalog(bad, C.weapons)
        bad["x"]["rarity"] = "common"
        bad["x"]["effects"].append({"type": "weapon_bonus", "field": "area", "levels": [1, 2]})
        with self.assertRaises(ValueError):                    # ragged levels
            Catalog(bad, C.weapons)

    def test_rules_load(self):
        self.assertEqual(RULES.choices, 3)
        self.assertGreater(RULES.kind_weights["stat"], RULES.kind_weights["weapon"])
        self.assertEqual(RULES.kind_weights["grant"], RULES.kind_weights["stat"])
        self.assertLess(RULES.summon_factor, 1.0)
        self.assertEqual(RULES.falloff(1), 1.0)
        self.assertEqual(RULES.falloff(99), RULES.level_falloff[-1])


class ApplyTests(unittest.TestCase):
    def test_stat_blessing_totals_follow_the_level_table(self):
        p = hero("sword")
        b = CAT.get("vitality")
        base = p.stats["max_hp"]
        for level in range(1, 6):
            self.assertEqual(apply_blessing(p, b), level)
            self.assertAlmostEqual(p.stats["max_hp"], base + b.effects[0].value_at(level))
        self.assertEqual(p.blessings["vitality"], 5)
        with self.assertRaises(ValueError):
            apply_blessing(p, b)

    def test_max_hp_blessing_heals_by_the_gain(self):
        p = hero("sword")
        p.hp = 50
        apply_blessing(p, CAT.get("vitality"))
        self.assertEqual(p.hp, 70)

    def test_pct_stat_blessing(self):
        p = hero("sword")
        base = p.stats["move_speed"]
        b = CAT.get("fleet_foot")
        apply_blessing(p, b); apply_blessing(p, b)
        self.assertAlmostEqual(p.stats["move_speed"], base * (1 + b.effects[0].value_at(2)))

    def test_weapon_add_bonus_totals_follow_the_table(self):
        p = hero("sword")
        b = CAT.get("sword_sharpened_edge")
        for level in range(1, 6):
            apply_blessing(p, b)
            self.assertAlmostEqual(weapon(p, "sword").bonus["damage"],
                                   b.effects[0].value_at(level))
        self.assertEqual(weapon(p, "sword").level, 6)

    def test_weapon_mult_bonus_totals_follow_the_table(self):
        p = hero("daggers")
        b = CAT.get("daggers_quick_hands")
        for level in range(1, 6):
            apply_blessing(p, b)
            self.assertAlmostEqual(weapon(p, "daggers").bonus["cooldown_mult"],
                                   b.effects[0].value_at(level))

    def test_multi_effect_blessing_touches_every_field(self):
        p = hero("sword")
        apply_blessing(p, CAT.get("sword_heavy_blade"))
        w = weapon(p, "sword")
        self.assertGreater(w.bonus["damage"], 0)
        self.assertGreater(w.bonus["weight"], 0)
        self.assertAlmostEqual(w.bonus["cooldown_mult"], 1.15)
        apply_blessing(p, CAT.get("sword_heavy_blade"))
        self.assertAlmostEqual(w.bonus["cooldown_mult"], 1.15, msg="a fixed tradeoff, not compounding")

    def test_weapon_effect_sets_a_total(self):
        p = hero("hammer")
        b = CAT.get("hammer_executioner")
        apply_blessing(p, b); apply_blessing(p, b)
        fx = weapon(p, "hammer").effects
        self.assertAlmostEqual(fx["executioner_mult"], b.effects[0].value_at(2))
        self.assertAlmostEqual(fx["executioner_threshold"], 0.35)

    def test_a_weapon_blessing_needs_the_weapon(self):
        with self.assertRaises(ValueError):
            apply_blessing(hero("sword"), CAT.get("bow_rapid_draw"))

    def test_apply_rebuilds_the_combat_aggregate(self):
        from progression.blessings import rebuild
        p = hero("sword")
        rebuild(p)
        before = p.blessing_fx
        apply_blessing(p, CAT.get("vitality"))
        self.assertIsNot(p.blessing_fx, before)


class GatingTests(unittest.TestCase):
    def _ids(self, p, **kw):
        return {u.id for u in valid_offers(p, C, random.Random(0), **kw)}

    def test_no_hammer_blessing_without_the_hammer(self):
        ids = self._ids(hero("sword"))
        self.assertFalse({b.id for b in CAT.for_weapon("hammer")} & ids)
        plain = {b.id for b in CAT.for_weapon("sword")
                 if b.requires_forge is None and not b.requires_weapons}
        self.assertTrue(plain <= ids)
        self.assertFalse({b.id for b in CAT.for_weapon("sword") if b.requires_forge} & ids)

    def test_every_stat_blessing_is_always_offered(self):
        ids = self._ids(hero("bow"))
        self.assertTrue({b.id for b in CAT.of_kind("stat")} <= ids)

    def test_a_maxed_blessing_disappears(self):
        p = hero("sword")
        for _ in range(5):
            apply_blessing(p, CAT.get("vitality"))
        self.assertNotIn("vitality", self._ids(p))

    def test_kinds_filter_keeps_shrines_off_the_grants(self):
        ids = self._ids(hero("sword"), kinds=("stat", "weapon"))
        self.assertFalse(any(i.startswith("grant:") for i in ids))
        self.assertIn("vitality", ids)

    def test_offer_carries_level_rarity_and_text(self):
        p = hero("sword")
        apply_blessing(p, CAT.get("sword_sharpened_edge"))
        u = next(u for u in valid_offers(p, C, random.Random(0)) if u.id == "sword_sharpened_edge")
        self.assertEqual(u.level, 2)
        self.assertEqual(u.title, "Sharpened Edge II")
        self.assertEqual(u.rarity, "common")
        self.assertEqual(u.kind, "weapon")
        self.assertEqual(u.weapon, "sword")
        self.assertIn("+6", u.description)
        self.assertIn("Sword", u.tags)


class GrantTests(unittest.TestCase):
    def test_grants_for_every_unowned_weapon_while_slots_are_open(self):
        ids = {u.id for u in grant_offers(hero("sword"), C, random.Random(0))}
        self.assertEqual(ids, {f"grant:{w}" for w in C.weapons if w != "sword"})

    def test_three_weapons_stop_weapon_grants_but_not_the_summon(self):
        ids = {u.id for u in grant_offers(hero("sword", "bow", "bomb"), C, random.Random(0))}
        self.assertEqual(ids, {"grant:ember_ring", "grant:grave_totem", "grant:spirit_wolf"})

    def test_a_summon_fills_only_the_summon_slot(self):
        ids = {u.id for u in grant_offers(hero("sword", "spirit_wolf"), C, random.Random(0))}
        self.assertIn("grant:hammer", ids)
        self.assertNotIn("grant:grave_totem", ids)

    def test_a_grant_adds_the_weapon_and_exactly_one_level_one_blessing(self):
        p = hero("sword")
        g = next(u for u in grant_offers(p, C, random.Random(1)) if u.id == "grant:bow")
        self.assertIsNotNone(g.bundle)
        self.assertIn(CAT.get(g.bundle).name + " I", g.description)   # named on the card
        before = dict(p.blessings)
        g.apply(p)
        self.assertIn("bow", {w.weapon_id for w in p.weapons})
        gained = {k: v for k, v in p.blessings.items() if before.get(k, 0) != v}
        self.assertEqual(len(gained), 1)
        self.assertEqual(list(gained.values()), [1])
        self.assertEqual(list(gained), [g.bundle])

    def test_bundle_candidates_are_level_zero_and_valid_after_the_grant(self):
        p = hero("sword")
        apply_blessing(p, CAT.get("vitality"))
        pool = bundle_candidates(p, C, "bow")
        ids = {b.id for b in pool}
        self.assertNotIn("vitality", ids)                     # already level I
        self.assertIn("bow_rapid_draw", ids)                  # the new weapon's own
        self.assertIn("sword_sharpened_edge", ids)            # an owned weapon's
        self.assertNotIn("hammer_crushing_blow", ids)         # still unowned
        self.assertIn("fleet_foot", ids)

    def test_the_bundle_is_the_rngs_pick(self):
        p = hero("sword")
        a = next(u for u in grant_offers(p, C, random.Random(7)) if u.id == "grant:bow").bundle
        b = next(u for u in grant_offers(p, C, random.Random(7)) if u.id == "grant:bow").bundle
        self.assertEqual(a, b)


class WeightTests(unittest.TestCase):
    def _w(self, bid, level=1):
        return blessing_weight(CAT.get(bid), level, CAT, RULES)

    def test_stat_outweighs_weapon_at_equal_rarity_and_level(self):
        self.assertGreater(self._w("vitality"), self._w("sword_sharpened_edge"))

    def test_a_grant_shares_the_stat_weight_while_slots_are_open(self):
        g = next(u for u in grant_offers(hero("sword"), C, random.Random(0)) if u.id == "grant:bow")
        self.assertAlmostEqual(g.weight, self._w("vitality"))

    def test_higher_levels_weigh_less(self):
        ws = [self._w("vitality", lv) for lv in range(1, 6)]
        self.assertEqual(ws, sorted(ws, reverse=True))
        self.assertLess(ws[-1], ws[0])

    def test_summons_weigh_less_than_weapons_and_their_grant_too(self):
        self.assertLess(self._w("spirit_wolf_savage_bite"), self._w("sword_sharpened_edge"))
        offers = {u.id: u for u in grant_offers(hero("sword"), C, random.Random(0))}
        self.assertLess(offers["grant:spirit_wolf"].weight, offers["grant:bow"].weight)

    def test_rarity_multiplies(self):
        self.assertGreater(self._w("sword_sharpened_edge"), self._w("sword_critical_edge"))
        self.assertGreater(self._w("sword_critical_edge"), self._w("sword_heavy_blade"))

    def test_stat_blessings_land_in_nearly_every_offering(self):
        p = hero("sword", "bow", "bomb")                      # slots full: no grants
        hits = 0
        n = 300
        for seed in range(n):
            offer = roll_offering(p, C, random.Random(seed))
            hits += any(u.kind == "stat" for u in offer)
        self.assertGreater(hits / n, 0.9)


class RollTests(unittest.TestCase):
    def test_three_distinct_cards(self):
        offer = roll_offering(hero("sword"), C, random.Random(1))
        self.assertEqual(len(offer), 3)
        self.assertEqual(len({u.id for u in offer}), 3)

    def test_deterministic_for_a_seed(self):
        a = [u.id for u in roll_offering(hero("sword"), C, random.Random(5))]
        b = [u.id for u in roll_offering(hero("sword"), C, random.Random(5))]
        self.assertEqual(a, b)

    def test_default_count_is_the_datas_choices(self):
        self.assertEqual(len(roll_offering(hero("sword"), C, random.Random(2))), RULES.choices)

    def test_blessing_offers_alone_carry_no_grants(self):
        self.assertFalse(any(u.kind == "grant" for u in blessing_offers(hero("sword"), C)))


if __name__ == "__main__":
    unittest.main()
