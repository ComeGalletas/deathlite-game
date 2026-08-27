"""Milestone 7: seeded item generation, rarity distribution, serialisation
(spec 4.4 / 4.5 / 8: "Item generation", "Rarity probabilities")."""
import random
import unittest
from collections import Counter

from game.content import get_content
from progression.items import (RARITIES, Item, generate_item, roll_rarity)


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.content = get_content()

    def test_same_seed_same_item(self):
        a = generate_item(self.content, seed=4242, item_level=5)
        b = generate_item(self.content, seed=4242, item_level=5)
        self.assertEqual(a.to_dict(), b.to_dict())

    def test_different_seeds_differ(self):
        items = {generate_item(self.content, seed=s).to_dict()["item_id"]
                 for s in range(30)}
        self.assertGreater(len(items), 1)

    def test_affix_count_matches_rarity(self):
        want = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4}
        seen = {}
        for s in range(4000):
            it = generate_item(self.content, seed=s, luck=5)
            seen.setdefault(it.rarity, len(it.affixes))
        for rarity, count in seen.items():
            self.assertLessEqual(count, want[rarity])

    def test_legendary_has_unique_effect(self):
        it = None
        for s in range(20000):
            cand = generate_item(self.content, seed=s, luck=8)
            if cand.rarity == "legendary":
                it = cand
                break
        self.assertIsNotNone(it, "no legendary rolled in 20k tries")
        self.assertIsNotNone(it.unique_effect)

    def test_affixes_never_duplicate_a_stat(self):
        for s in range(2000):
            it = generate_item(self.content, seed=s, luck=6)
            keys = [it.base_stat] + [a.stat or a.tag for a in it.affixes]
            self.assertEqual(len(keys), len(set(keys)))

    def test_roundtrips_through_dict(self):
        it = generate_item(self.content, seed=99, item_level=7, luck=4)
        again = Item.from_dict(it.to_dict())
        self.assertEqual(again.to_dict(), it.to_dict())

    def test_tag_affixes_produce_tag_effects(self):
        # Force a slot/seed known to carry a tag affix eventually.
        found = False
        for s in range(3000):
            it = generate_item(self.content, seed=s, luck=8, slot="weapon")
            if it.tag_effects():
                found = True
                tag, val = it.tag_effects()[0]
                self.assertIn(tag, ("fire", "frost", "lightning", "area", "elite"))
                self.assertGreater(val, 0)
                break
        self.assertTrue(found)


class RarityTests(unittest.TestCase):
    def test_distribution_is_ordered_common_to_legendary(self):
        rng = random.Random(1)
        counts = Counter(roll_rarity(rng) for _ in range(20000))
        ordered = [counts[r] for r in RARITIES]
        self.assertEqual(ordered, sorted(ordered, reverse=True))
        self.assertGreater(counts["common"], counts["legendary"] * 10)

    def test_luck_shifts_weight_upward(self):
        rng_a = random.Random(2)
        rng_b = random.Random(2)
        low = Counter(roll_rarity(rng_a, luck=0) for _ in range(20000))
        high = Counter(roll_rarity(rng_b, luck=10) for _ in range(20000))
        self.assertGreater(high["rare"] + high["epic"] + high["legendary"],
                           low["rare"] + low["epic"] + low["legendary"])


if __name__ == "__main__":
    unittest.main()
