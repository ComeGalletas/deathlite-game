"""What a treasure chest contains (CB-9), and the blessing-rarity filter it
needs from the offering.

The four contents rules from the owner's brief, read straight off
`data/chests.json`: every tier pays gold in its own range; every tier drops
exactly **one** potion and a richer tier buys a *better* one, never more;
common chests never carry a blessing, uncommon ones sometimes do, rare and
epic always do; and each of those two draws from its own pair of blessing
rarities, weighted toward the poorer one.
"""
import random
import unittest

from game.content import get_content
from progression import chests as chest_rules
from progression.blessings import roll_offering, valid_offers
from progression.blessings.offer import blessing_offers

C = get_content()
T = C.chests
TIERS = ("common", "uncommon", "rare", "epic")


class TableShapeTests(unittest.TestCase):
    def test_the_four_tiers_are_the_authored_order(self):
        self.assertEqual(chest_rules.rarities(T), TIERS)

    def test_every_tier_names_its_own_sprite(self):
        rigs = {chest_rules.sprite_rig(t, T) for t in TIERS}
        self.assertEqual(len(rigs), len(TIERS))
        for tier in TIERS:
            self.assertIn(tier, chest_rules.sprite_rig(tier, T))

    def test_every_sprite_rig_is_loadable(self):
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIn(chest_rules.sprite_rig(tier, T), C.sprites)


class GoldTests(unittest.TestCase):
    def test_common_starts_at_the_briefs_ten_to_twenty_five(self):
        self.assertEqual(T["chests"]["common"]["gold"], [10, 25])

    def test_gold_rises_with_the_tier(self):
        lows = [T["chests"][t]["gold"][0] for t in TIERS]
        highs = [T["chests"][t]["gold"][1] for t in TIERS]
        self.assertEqual(lows, sorted(lows))
        self.assertEqual(highs, sorted(highs))
        self.assertEqual(len(set(lows)), len(lows), "each tier pays more than the last")

    def test_a_roll_lands_inside_its_range(self):
        rng = random.Random(11)
        for tier in TIERS:
            lo, hi = T["chests"][tier]["gold"]
            for _ in range(200):
                self.assertTrue(lo <= chest_rules.gold(tier, T, rng) <= hi)

    def test_a_roll_uses_the_whole_range(self):
        rng = random.Random(12)
        seen = {chest_rules.gold("common", T, rng) for _ in range(400)}
        self.assertEqual(min(seen), 10)
        self.assertEqual(max(seen), 25)


class PotionTests(unittest.TestCase):
    """The owner's rule: one potion per chest, the rarity is what climbs."""

    def test_a_tier_names_one_potion_rarity_not_a_count(self):
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIsInstance(T["chests"][tier]["potion"], str)

    def test_each_potion_rarity_exists_in_the_cb8_table(self):
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIn(chest_rules.potion_rarity(tier, T),
                              C.potions["rarities"])

    def test_the_potion_rarity_never_drops_as_the_tier_rises(self):
        order = C.potions["rarities"]
        got = [order.index(chest_rules.potion_rarity(t, T)) for t in TIERS]
        self.assertEqual(got, sorted(got))

    def test_an_epic_chest_drops_a_rare_potion(self):
        # The brief spells this out; there is no epic potion to drop.
        self.assertEqual(chest_rules.potion_rarity("epic", T), "rare")
        self.assertEqual(chest_rules.potion_rarity("rare", T), "rare")

    def test_the_poorer_tiers_match_their_own_rarity(self):
        self.assertEqual(chest_rules.potion_rarity("common", T), "common")
        self.assertEqual(chest_rules.potion_rarity("uncommon", T), "uncommon")


class BlessingTests(unittest.TestCase):
    def _sample(self, tier, n=4000, seed=5):
        rng = random.Random(seed)
        return [chest_rules.blessing_rarity(tier, T, rng) for _ in range(n)]

    def test_a_common_chest_never_carries_one(self):
        self.assertNotIn("blessing", T["chests"]["common"])
        self.assertEqual(set(self._sample("common")), {None})

    def test_an_uncommon_chest_sometimes_carries_a_common_one(self):
        got = self._sample("uncommon")
        self.assertEqual(set(got), {None, "common"})
        rate = 1.0 - got.count(None) / len(got)
        self.assertAlmostEqual(rate, 0.35, delta=0.05)

    def test_a_rare_chest_always_carries_one(self):
        got = self._sample("rare")
        self.assertNotIn(None, got)
        self.assertEqual(set(got), {"common", "uncommon"})

    def test_a_rare_chest_leans_common(self):
        got = self._sample("rare")
        self.assertGreater(got.count("common"), got.count("uncommon"))
        self.assertAlmostEqual(got.count("common") / len(got), 0.65, delta=0.05)

    def test_an_epic_chest_always_carries_one(self):
        got = self._sample("epic")
        self.assertNotIn(None, got)
        self.assertEqual(set(got), {"uncommon", "rare"})

    def test_an_epic_chest_leans_uncommon(self):
        got = self._sample("epic")
        self.assertGreater(got.count("uncommon"), got.count("rare"))
        self.assertAlmostEqual(got.count("uncommon") / len(got), 0.65, delta=0.05)

    def test_no_tier_offers_a_blessing_richer_than_its_own(self):
        """An uncommon chest cannot hand out a rare blessing, and so on."""
        order = list(TIERS)
        for tier in TIERS:
            spec = T["chests"][tier].get("blessing")
            if spec is None:
                continue
            for rarity in spec["weights"]:
                with self.subTest(tier=tier, rarity=rarity):
                    self.assertLess(order.index(rarity), order.index(tier))


class _Hero:
    """A hero with nothing owned and nothing levelled: every stat blessing is
    valid, and no weapon blessing is."""
    def __init__(self):
        self.weapons = []
        self.blessings = {}
        self.stats = {}


class OfferingFilterTests(unittest.TestCase):
    """The one API addition CB-9 needed from the blessing package."""

    def test_unfiltered_still_returns_every_rarity(self):
        got = {u.rarity for u in blessing_offers(_Hero(), C, kinds=("stat",))}
        self.assertIn("common", got)
        self.assertIn("uncommon", got)

    def test_a_filter_returns_only_that_rarity(self):
        for rarity in ("common", "uncommon"):
            with self.subTest(rarity=rarity):
                got = blessing_offers(_Hero(), C, kinds=("stat", "weapon"),
                                      rarities=(rarity,))
                self.assertTrue(got, f"no {rarity} blessing is offerable")
                self.assertEqual({u.rarity for u in got}, {rarity})

    def test_every_rare_blessing_is_a_weapon_blessing(self):
        """Why `Chests._grant_blessing` falls back rather than paying nothing:
        an epic chest can roll `rare`, and the catalog has no rare *stat*
        blessing, so a hero with no eligible weapon has none to be given."""
        rares = [b for b in C.blessings.values()
                 if isinstance(b, dict) and b.get("rarity") == "rare"]
        self.assertTrue(rares)
        self.assertEqual({b["kind"] for b in rares}, {"weapon"})
        self.assertEqual(
            blessing_offers(_Hero(), C, kinds=("stat", "weapon"),
                            rarities=("rare",)),
            [], "a weaponless hero has no rare blessing to be handed")

    def test_the_filter_narrows_rather_than_widens(self):
        hero = _Hero()
        everything = blessing_offers(hero, C, kinds=("stat", "weapon"))
        commons = blessing_offers(hero, C, kinds=("stat", "weapon"),
                                  rarities=("common",))
        self.assertLess(len(commons), len(everything))
        self.assertTrue({u.id for u in commons} <= {u.id for u in everything})

    def test_valid_offers_drops_grants_that_do_not_match(self):
        """A weapon grant carries a fixed `common` rarity of its own, so asking
        for rare cards must not smuggle one in."""
        got = valid_offers(_Hero(), C, random.Random(1), rarities=("rare",))
        self.assertTrue(all(u.rarity == "rare" for u in got))

    def test_roll_offering_honours_the_filter(self):
        rng = random.Random(9)
        for _ in range(40):
            picked = roll_offering(_Hero(), C, rng, 1, kinds=("stat", "weapon"),
                                   rarities=("uncommon",))
            self.assertEqual([u.rarity for u in picked], ["uncommon"])

    def test_an_impossible_filter_returns_nothing_rather_than_raising(self):
        self.assertEqual(
            roll_offering(_Hero(), C, random.Random(1), 1,
                          kinds=("stat",), rarities=("not_a_rarity",)),
            [])


if __name__ == "__main__":
    unittest.main()
