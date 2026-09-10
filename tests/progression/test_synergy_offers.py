"""Six-weapon system P4: synergy cards are offered only when both weapons
of the pair are owned (design §5.4, §10), and apply as effects on the
benefiting weapon."""
import random
import unittest

from combat.weapons import Weapon
from entities.player import Player
from game.content import get_content
from progression.blessings import apply_blessing, get_catalog, valid_offers

C = get_content()
CAT = get_catalog(C)
PAIRS = {
    "daggers_blood_in_the_water": ("daggers", "sword"),
    "bow_linebreaker": ("bow", "hammer"),
    "bomb_demolition": ("bomb", "hammer"),
    "daggers_marked_prey": ("daggers", "magic_rod"),
    "sword_crowd_cleaner": ("sword", "bomb"),
    "bow_crossfire": ("bow", "magic_rod"),
}


def hero(*wids):
    p = Player(0, 0)
    p.weapons = [Weapon(w, C.weapon(w)) for w in wids]
    return p


def ids(p):
    return {u.id for u in valid_offers(p, C, random.Random(0))}


class SynergyOfferTests(unittest.TestCase):
    def test_the_six_pairs_of_the_design(self):
        for bid, (owner, partner) in PAIRS.items():
            b = CAT.get(bid)
            self.assertEqual(b.weapon, owner, bid)
            self.assertEqual(b.requires_weapons, (partner,), bid)
            self.assertEqual(b.category, "synergy", bid)
            self.assertEqual(b.rarity, "rare", bid)

    def test_needs_both_weapons(self):
        for bid, (owner, partner) in PAIRS.items():
            self.assertNotIn(bid, ids(hero(owner)), bid)
            self.assertNotIn(bid, ids(hero(partner)), bid)
            self.assertIn(bid, ids(hero(owner, partner)), bid)

    def test_a_synergy_card_applies_to_the_owning_weapon(self):
        p = hero("daggers", "sword")
        apply_blessing(p, CAT.get("daggers_blood_in_the_water"))
        daggers = p.weapon_by_id("daggers")
        self.assertAlmostEqual(daggers.effects["syn_after_sword"], 0.25)
        self.assertEqual(p.weapon_by_id("sword").effects, {})

    def test_hunters_mark_needs_only_the_bow(self):
        self.assertIn("bow_hunters_mark", ids(hero("bow")))
        self.assertNotIn("bow_hunters_mark", ids(hero("sword")))

    def test_the_catalog_rejects_an_unknown_partner(self):
        from progression.blessings import Catalog
        bad = {"x": {"name": "X", "kind": "weapon", "weapon": "bow", "category": "synergy",
                     "rarity": "rare", "description": "d", "requires": {"weapons": ["axe"]},
                     "effects": [{"type": "weapon_effect", "key": "syn_after_axe",
                                  "levels": [1, 2, 3, 4, 5]}]}}
        with self.assertRaises(ValueError):
            Catalog(bad, C.weapons, C.forges)


if __name__ == "__main__":
    unittest.main()
