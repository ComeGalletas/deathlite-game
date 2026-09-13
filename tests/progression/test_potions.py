"""CB-8: health potion drops from enemies.

The drop chance rises with the enemy's *base* HP and caps at 25 %; the enemy's
rarity band then picks the potion, with two hard exclusions -- a common enemy
never drops a rare potion, a rare enemy never drops a common one.
"""
import math
import random
import unittest

from game.content import get_content
from progression import potions as P

C = get_content()
T = C.potions
CURVE = T["drop_chance"]
ORDER = T["rarities"]

# Everything that can drop a potion. The training dummy is excluded everywhere:
# it is a dev-mode fixture, not part of the roster the tuning is fitted to.
ROSTER = [e for e in C.enemies if e != "training_dummy"]


def base_hp(enemy_id: str) -> float:
    return float(C.enemies[enemy_id]["hp"])


class TableMatchesTheRosterTests(unittest.TestCase):
    """Where the tuning table has to agree with `data/enemies/enemies.json`.

    Kept as its own class, and phrased to name the stale number, because these
    two ends are read by the chance, band and exclusion tests alike -- an HP
    rebalance that moves them used to scatter half a dozen opaque failures
    across three classes instead of one that says what actually went out of
    date.
    """

    def test_hp_min_and_hp_max_are_the_roster_ends(self):
        hps = [base_hp(e) for e in ROSTER]
        self.assertEqual(float(CURVE["hp_min"]), min(hps),
                         "drop_chance.hp_min is stale: the weakest enemy is now "
                         f"{min(ROSTER, key=base_hp)} at {min(hps):g}")
        self.assertEqual(float(CURVE["hp_max"]), max(hps),
                         "drop_chance.hp_max is stale: the strongest enemy is now "
                         f"{max(ROSTER, key=base_hp)} at {max(hps):g}")

    def test_no_enemy_sits_exactly_on_a_band_edge(self):
        """A threshold landing on an enemy's HP is a silent trap: shave one
        point off that enemy in a rebalance and it changes band, which breaks a
        hard exclusion rule with nothing pointing at the cause. Each bound
        belongs near the middle of the gap it divides.
        """
        edges = [(k, float(v)) for k, v in T["enemy_rarity_hp"].items()
                 if not k.startswith("_")]
        for eid in ROSTER:
            for name, edge in edges:
                self.assertNotEqual(
                    base_hp(eid), edge,
                    f"{eid} sits exactly on the '{name}' band edge ({edge:g}); "
                    "move the bound into the middle of its gap")


class TableTests(unittest.TestCase):
    def test_three_rarities_weakest_first(self):
        self.assertEqual(ORDER, ["common", "uncommon", "rare"])

    def test_the_heals_are_fifteen_twentyfive_and_fifty(self):
        self.assertEqual([P.heal_amount(r, T) for r in ORDER], [15.0, 25.0, 50.0])

    def test_each_rarity_maps_to_its_numbered_sprite(self):
        # "use the health potion numeric value name for the sprites rarity":
        # health_potion -> common, _2 -> uncommon, _3 -> rare.
        self.assertEqual(
            [P.sprite_rig(r, T) for r in ORDER],
            ["potion_health_common", "potion_health_uncommon", "potion_health_rare"])
        files = [C.sprites[P.sprite_rig(r, T)]["file"] for r in ORDER]
        self.assertEqual(files, ["items/potions/health_potion.png",
                                 "items/potions/health_potion_2.png",
                                 "items/potions/health_potion_3.png"])

    def test_rarer_potions_draw_larger(self):
        sizes = [C.sprites[P.sprite_rig(r, T)]["scale"][0] for r in ORDER]
        self.assertEqual(sizes, sorted(sizes))
        self.assertEqual(len(set(sizes)), len(sizes))


class ChanceTests(unittest.TestCase):
    def test_the_cap_is_twenty_five_percent(self):
        self.assertAlmostEqual(CURVE["cap"], 0.25)

    def test_the_strongest_enemy_sits_at_the_cap(self):
        # The enemy and the cap are both derived: a rebalance that crowns a new
        # strongest enemy is not this test's business, and `hp_max` going stale
        # is reported by TableMatchesTheRosterTests instead.
        self.assertAlmostEqual(P.drop_chance(base_hp(max(ROSTER, key=base_hp)), T),
                               float(CURVE["cap"]), places=6)

    def test_the_weakest_enemy_sits_at_the_floor(self):
        self.assertAlmostEqual(P.drop_chance(base_hp(min(ROSTER, key=base_hp)), T),
                               float(CURVE["floor"]), places=6)

    def test_the_chance_rises_with_hp(self):
        hps = sorted(base_hp(e) for e in ROSTER)
        chances = [P.drop_chance(hp, T) for hp in hps]
        self.assertEqual(chances, sorted(chances))
        self.assertLess(chances[0], chances[-1])

    def test_nothing_ever_exceeds_the_cap(self):
        # Including a boss-sized number, in case one is ever routed through.
        for hp in (0.001, 1, 5, 50, 390, 9990, 10 ** 6):
            self.assertLessEqual(P.drop_chance(hp, T), CURVE["cap"] + 1e-9, hp)
            self.assertGreaterEqual(P.drop_chance(hp, T), CURVE["floor"] - 1e-9, hp)

    def test_a_tougher_enemy_is_meaningfully_likelier(self):
        # The squared curve exists so the cap means something: the Warden must
        # be several times the Husk, not a few points above it.
        husk = P.drop_chance(base_hp("chaser"), T)
        warden = P.drop_chance(base_hp("brute"), T)
        self.assertGreater(warden, husk * 5.0)


class EnemyRarityTests(unittest.TestCase):
    def _bands(self):
        got = {}
        for eid in ROSTER:
            got.setdefault(P.enemy_rarity(base_hp(eid), T), []).append(eid)
        return got

    def test_every_enemy_lands_in_exactly_one_known_band(self):
        got = self._bands()
        self.assertEqual(sorted(e for v in got.values() for e in v), sorted(ROSTER))
        self.assertLessEqual(set(got), set(ORDER))

    def test_the_bands_do_not_interleave_on_hp(self):
        """The property the thresholds exist to produce: sort the roster by HP
        and the band index never goes backwards. Asserted without naming an
        enemy or a count, so adding one to the roster is not a test change.
        """
        seen = [ORDER.index(P.enemy_rarity(base_hp(e), T))
                for e in sorted(ROSTER, key=base_hp)]
        self.assertEqual(seen, sorted(seen))

    def test_the_rare_band_is_exactly_the_elite_enemies(self):
        """The design rule. The HP thresholds are only how it is expressed, so
        this is what must hold after any rebalance -- if it breaks, the bounds
        need moving, not this test.
        """
        for eid in ROSTER:
            rare = P.enemy_rarity(base_hp(eid), T) == "rare"
            self.assertEqual(rare, bool(C.enemies[eid].get("is_elite")), eid)

    def test_the_bands_are_read_off_the_thresholds(self):
        bands = T["enemy_rarity_hp"]
        self.assertEqual(P.enemy_rarity(bands["uncommon"] - 1, T), "common")
        self.assertEqual(P.enemy_rarity(bands["uncommon"], T), "uncommon")
        self.assertEqual(P.enemy_rarity(bands["rare"] - 1, T), "uncommon")
        self.assertEqual(P.enemy_rarity(bands["rare"], T), "rare")


class ExclusionTests(unittest.TestCase):
    """The two rules the request states outright."""

    def _seen(self, enemy_id, rolls=6000):
        rng = random.Random(4242)
        hp = base_hp(enemy_id)
        return {P.roll_rarity(hp, T, rng) for _ in range(rolls)}

    def test_no_enemy_ever_rolls_a_rarity_its_band_forbids(self):
        """Both exclusions at once, with the forbidden set read per enemy off
        the weights table -- so the roster and the weights can each change
        without this test naming either. It subsumes the two hand-listed
        cases (common enemies never rare, rare enemies never common), which
        went stale whenever an enemy moved band.
        """
        for eid in ROSTER:
            weights = T["rarity_weights"][P.enemy_rarity(base_hp(eid), T)]
            forbidden = {r for r in ORDER if float(weights[r]) == 0.0}
            self.assertEqual(self._seen(eid) & forbidden, set(), eid)

    def test_the_zero_weights_are_the_two_exclusions(self):
        w = T["rarity_weights"]
        self.assertEqual(float(w["common"]["rare"]), 0.0)
        self.assertEqual(float(w["rare"]["common"]), 0.0)

    def test_uncommon_enemies_can_drop_all_three(self):
        self.assertEqual(self._seen("tank"), set(ORDER))

    def test_a_roll_only_ever_returns_a_weighted_rarity(self):
        rng = random.Random(1)
        for eid in C.enemies:
            if eid == "training_dummy":
                continue
            weights = T["rarity_weights"][P.enemy_rarity(base_hp(eid), T)]
            allowed = {r for r in ORDER if float(weights[r]) > 0.0}
            for _ in range(200):
                self.assertIn(P.roll_rarity(base_hp(eid), T, rng), allowed, eid)


class RollTests(unittest.TestCase):
    def test_roll_returns_none_when_the_chance_misses(self):
        class Rng:
            def random(self):
                return 0.999
        self.assertIsNone(P.roll(base_hp("swarm"), T, Rng()))

    def test_roll_returns_a_rarity_when_the_chance_hits(self):
        class Rng:
            def __init__(self):
                self._n = 0

            def random(self):
                self._n += 1
                return 0.0 if self._n == 1 else 0.5
        self.assertIn(P.roll(base_hp("brute"), T, Rng()), ORDER)

    def test_the_observed_rate_matches_the_curve_at_both_ends(self):
        """`roll` honours `drop_chance` -- the contract -- rather than
        restating a tuning value, so a re-tune moves both sides together.

        The tolerance is 5 sigma for the binomial at this n rather than a flat
        literal: it stays honest if the chance moves, and it is loose enough
        that a passing build never flakes (5 sigma is about 1 in 3.5 million,
        and the seed is fixed anyway).
        """
        n = 20000
        for eid in (max(ROSTER, key=base_hp), min(ROSTER, key=base_hp)):
            hp = base_hp(eid)
            want = P.drop_chance(hp, T)
            rng = random.Random(2026)
            hits = sum(P.roll(hp, T, rng) is not None for _ in range(n))
            sigma = math.sqrt(want * (1.0 - want) / n)
            self.assertAlmostEqual(hits / n, want, delta=5.0 * sigma, msg=eid)


if __name__ == "__main__":
    unittest.main()
