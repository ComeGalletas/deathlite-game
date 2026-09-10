"""Six-weapon system P3: Forge cards in the offering (design §7, §12, §13):
only for a weapon with enough blessing levels, at Forge rarity, gone once
the weapon is forged; post-Forge blessings appear only after that Forge."""
import random
import unittest

from combat.weapons import Weapon
from entities.player import Player
from game.content import get_content
from progression.blessings import (Catalog, apply_blessing, forge_offers,
                                   get_catalog, get_rules, roll_offering,
                                   valid_offers)

C = get_content()
CAT = get_catalog(C)
RULES = get_rules(C)


def hero(*wids, levels=0):
    p = Player(0, 0)
    p.weapons = [Weapon(w, C.weapon(w)) for w in wids]
    for w in p.weapons:
        w.level = 1 + levels
    return p


def ids(p, **kw):
    return {u.id for u in valid_offers(p, C, random.Random(0), **kw)}


class ForgeCardTests(unittest.TestCase):
    def test_no_forge_cards_without_two_blessing_levels(self):
        self.assertFalse(any(i.startswith("forge:") for i in ids(hero("sword", levels=1))))
        got = {i for i in ids(hero("sword", levels=2)) if i.startswith("forge:")}
        self.assertEqual(got, {"forge:whirlwind", "forge:greatsword"})

    def test_real_blessings_count_toward_eligibility(self):
        p = hero("bow")
        apply_blessing(p, CAT.get("bow_rapid_draw"))
        self.assertFalse(forge_offers(p, C))
        apply_blessing(p, CAT.get("bow_piercing_arrow"))
        self.assertEqual({u.id for u in forge_offers(p, C)}, {"forge:multishot", "forge:ballista"})

    def test_forge_cards_carry_forge_kind_and_rarity_and_weight(self):
        u = next(u for u in forge_offers(hero("hammer", levels=2), C) if u.id == "forge:earthshaker")
        self.assertEqual((u.kind, u.rarity, u.weapon), ("forge", "forge", "hammer"))
        self.assertAlmostEqual(u.weight, RULES.kind_weights["forge"] * RULES.rarity_weights["forge"])
        self.assertIn("Earthshaker", u.title)
        self.assertIn("Area control", u.description)

    def test_forge_cards_are_rarer_than_any_blessing(self):
        p = hero("hammer", levels=2)
        offers = valid_offers(p, C, random.Random(0))
        forge_w = max(u.weight for u in offers if u.kind == "forge")
        common_w = min(u.weight for u in offers if u.kind == "stat" and u.rarity == "common")
        self.assertLess(forge_w, common_w)

    def test_shrines_never_offer_a_forge(self):
        self.assertFalse(any(i.startswith("forge:")
                             for i in ids(hero("sword", levels=2), kinds=("stat", "weapon"))))

    def test_taking_the_card_forges_the_weapon_and_ends_the_choice(self):
        p = hero("sword", levels=2)
        card = next(u for u in forge_offers(p, C) if u.id == "forge:whirlwind")
        card.apply(p)
        self.assertEqual(p.weapons[0].forge, "whirlwind")
        self.assertEqual(p.weapons[0].name, "Whirlwind")
        self.assertFalse(any(i.startswith("forge:") for i in ids(p)))

    def test_summons_never_get_forge_cards(self):
        self.assertFalse(forge_offers(hero("spirit_wolf", levels=5), C))

    def test_forge_cards_do_show_up_in_rolls(self):
        p = hero("sword", "bow", "bomb", levels=2)
        seen = 0
        for seed in range(400):
            seen += any(u.kind == "forge" for u in roll_offering(p, C, random.Random(seed)))
        self.assertGreater(seen, 5)
        self.assertLess(seen, 200, "forge cards are meant to be rare")


class PostForgeTests(unittest.TestCase):
    def test_thirteen_post_forge_blessings_one_per_forge_at_least(self):
        post = [b for b in CAT.by_id.values() if b.requires_forge]
        self.assertEqual(len(post), 13)
        self.assertEqual({b.requires_forge for b in post},
                         {"whirlwind", "greatsword", "earthshaker", "meteor_hammer",
                          "twin_daggers", "fan_of_blades", "multishot", "ballista",
                          "arcane_storm", "arcane_lance", "cluster_bomb", "minefield"})

    def test_hidden_until_the_forge_and_only_for_that_forge(self):
        p = hero("daggers", levels=2)
        self.assertNotIn("twin_daggers_dual_wield", ids(p))
        card = next(u for u in forge_offers(p, C) if u.id == "forge:twin_daggers")
        card.apply(p)
        now = ids(p)
        self.assertIn("twin_daggers_dual_wield", now)
        self.assertIn("twin_daggers_cross_cut", now)
        self.assertNotIn("fan_of_blades_more_blades", now)

    def test_a_post_forge_blessing_applies_like_any_other(self):
        p = hero("daggers", levels=2)
        next(u for u in forge_offers(p, C) if u.id == "forge:twin_daggers").apply(p)
        apply_blessing(p, CAT.get("twin_daggers_cross_cut"))
        self.assertEqual(p.weapons[0].bonus["twin_offset_deg"], 4)

    def test_catalog_rejects_a_post_forge_blessing_on_the_wrong_weapon(self):
        bad = {"x": {"name": "X", "kind": "weapon", "weapon": "bow", "category": "power",
                     "rarity": "common", "description": "d",
                     "requires": {"forge": "whirlwind"},
                     "effects": [{"type": "weapon_bonus", "field": "damage",
                                  "levels": [1, 2, 3, 4, 5]}]}}
        with self.assertRaises(ValueError):
            Catalog(bad, C.weapons, C.forges)
        bad["x"]["requires"]["forge"] = "no_such_forge"
        with self.assertRaises(ValueError):
            Catalog(bad, C.weapons, C.forges)


if __name__ == "__main__":
    unittest.main()
