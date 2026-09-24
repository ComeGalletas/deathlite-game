"""Treasure chests are seated at generation (CB-9,
`documentation/journals/combat_balance_journal.md`).

What is pinned: the owner's counting rules -- at most 5 chests an island,
averaging 2-3, at most one `rare` and one `epic` on any one island; that a
chest only ever stands on a resource anchor the spawn-point stage already
vetted; that village islands carry none (the HI-1 sanctuary rule); that the
stage draws nothing from the world's RNG, so islands, bridges and obstacles
digest identically with it on or off; and that one seed always seats the same
chests.
"""
import collections
import hashlib
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests import worlds as W
from tools.verification import world_digest as digest
from world.gen.chests import (island_chest_count, island_chest_rarities,
                              place_chests)
from world.gen.tuning import (VILLAGE_KIND, _CHEST_CAPS, _CHEST_COUNT_WEIGHTS,
                              _CHEST_RARITIES)
from world.gen import generate_world

# A wider sweep than the four pinned seeds, for the statistical claims only.
SWEEP = tuple(range(200, 240))


def _per_island(layout) -> dict:
    out = collections.defaultdict(list)
    for chest in layout.chests:
        out[chest.room_id].append(chest.rarity)
    return out


def _geometry_digest(layout) -> str:
    """Everything this stage must not move: islands, bridges, obstacles,
    spawn points and the anchors themselves."""
    h = hashlib.sha256()
    digest._feed(h, (layout.rooms, layout.corridors, layout.obstacles,
                     layout.spawn_points, layout.resource_points,
                     layout.bounds, layout.start_id, layout.boss_id))
    return h.hexdigest()


class CountingRuleTests(unittest.TestCase):
    """The owner's brief, read back off real worlds."""

    def test_never_more_than_five_on_an_island(self):
        for seed in W.SEEDS:
            for room_id, tiers in _per_island(W.layout(seed)).items():
                with self.subTest(seed=seed, room=room_id):
                    self.assertLessEqual(len(tiers), 5)

    def test_at_most_one_rare_and_one_epic_on_an_island(self):
        for seed in W.SEEDS:
            for room_id, tiers in _per_island(W.layout(seed)).items():
                counts = collections.Counter(tiers)
                for rarity, cap in _CHEST_CAPS.items():
                    with self.subTest(seed=seed, room=room_id, rarity=rarity):
                        self.assertLessEqual(counts.get(rarity, 0), cap)

    def test_an_island_that_has_chests_has_at_least_one(self):
        # No `0` weight, so "has anchors" and "has a chest" are the same thing.
        self.assertNotIn(0, _CHEST_COUNT_WEIGHTS)
        for seed in W.SEEDS:
            for tiers in _per_island(W.layout(seed)).values():
                self.assertGreaterEqual(len(tiers), 1)

    def test_the_average_island_carries_two_to_three(self):
        totals, islands = 0, 0
        for seed in SWEEP:
            layout = generate_world(seed)
            per = _per_island(layout)
            totals += sum(len(v) for v in per.values())
            islands += len(per)
        mean = totals / islands
        self.assertGreaterEqual(mean, 2.0, f"mean {mean:.2f} per island")
        self.assertLessEqual(mean, 3.0, f"mean {mean:.2f} per island")


class PlacementTests(unittest.TestCase):
    def test_every_chest_stands_on_a_resource_anchor(self):
        for seed in W.SEEDS:
            layout = W.layout(seed)
            anchors = {(p.room_id, round(p.x, 3), round(p.y, 3))
                       for p in layout.resource_points}
            for chest in layout.chests:
                with self.subTest(seed=seed, chest=chest):
                    self.assertIn(
                        (chest.room_id, round(chest.x, 3), round(chest.y, 3)),
                        anchors)

    def test_a_chest_never_shares_an_anchor(self):
        for seed in W.SEEDS:
            seen = {(c.room_id, c.x, c.y) for c in W.layout(seed).chests}
            self.assertEqual(len(seen), len(W.layout(seed).chests))

    def test_a_chest_carries_its_anchors_floor(self):
        for seed in W.SEEDS:
            layout = W.layout(seed)
            floors = {(p.room_id, p.x, p.y): p.floor
                      for p in layout.resource_points}
            for chest in layout.chests:
                with self.subTest(seed=seed, chest=chest):
                    self.assertEqual(chest.floor,
                                     floors[(chest.room_id, chest.x, chest.y)])

    def test_villages_carry_none(self):
        """HI-1's sanctuary rule, inherited: `place_points` gives a village
        island no anchors, so nothing here has to special-case it."""
        found = 0
        for seed in W.SEEDS:
            layout = W.layout(seed)
            villages = {r.id for r in layout.rooms if r.kind == VILLAGE_KIND}
            self.assertTrue(villages, f"seed {seed} has no village to check")
            found += len(villages)
            for chest in layout.chests:
                self.assertNotIn(chest.room_id, villages)
        self.assertGreater(found, 0)

    def test_the_tiers_a_world_seats_are_ordered_per_island(self):
        """Recorded poorest first, so the list reads in the authored order."""
        for seed in W.SEEDS:
            for tiers in _per_island(W.layout(seed)).values():
                order = [_CHEST_RARITIES.index(t) for t in tiers]
                self.assertEqual(order, sorted(order))


class PurityTests(unittest.TestCase):
    """One fresh build per seed, shared by the class (TST-005.2): the three
    tests used to build ten worlds between them. The second build the
    determinism test needs is the suite's shared cache (`tests/worlds`),
    which is built independently through `GameMap`."""

    @classmethod
    def setUpClass(cls):
        cls.fresh = {seed: generate_world(seed) for seed in W.SEEDS}

    def test_the_stage_takes_nothing_from_the_worlds_rng(self):
        """Re-running the stage on a finished layout cannot move anything
        above it: its RNG is private, keyed by seed and island. (It re-runs
        on the shared fresh builds; passing means it changed nothing, so the
        other tests still see the worlds as generated.)"""
        for seed, layout in self.fresh.items():
            before = _geometry_digest(layout)
            first = list(layout.chests)
            place_chests(layout)
            with self.subTest(seed=seed):
                self.assertEqual(_geometry_digest(layout), before)
                self.assertEqual(list(layout.chests), first)

    def test_one_seed_seats_one_set_of_chests(self):
        for seed, layout in self.fresh.items():
            with self.subTest(seed=seed):
                self.assertEqual(layout.chests, W.layout(seed).chests)

    def test_different_seeds_seat_different_chests(self):
        sets = {tuple(layout.chests) for layout in self.fresh.values()}
        self.assertEqual(len(sets), len(W.SEEDS))


class DrawTests(unittest.TestCase):
    """The two pure draws, away from any world."""

    def test_the_count_never_exceeds_the_anchors_available(self):
        rng = random.Random(1)
        for available in range(0, 8):
            for _ in range(50):
                self.assertLessEqual(island_chest_count(rng, available), available)

    def test_no_anchors_means_no_chests(self):
        self.assertEqual(island_chest_count(random.Random(1), 0), 0)

    def test_the_count_stays_inside_the_weight_table(self):
        rng = random.Random(2)
        seen = {island_chest_count(rng, 99) for _ in range(500)}
        self.assertEqual(seen, set(_CHEST_COUNT_WEIGHTS))

    def test_a_capped_tier_falls_back_to_common(self):
        """Five chests on one island can never be five epics, however the
        weights fall: the surplus becomes `common`."""
        for seed in range(50):
            tiers = island_chest_rarities(random.Random(seed), 5)
            counts = collections.Counter(tiers)
            self.assertEqual(len(tiers), 5)
            for rarity, cap in _CHEST_CAPS.items():
                self.assertLessEqual(counts.get(rarity, 0), cap)

    def test_every_tier_can_be_drawn(self):
        rng = random.Random(4)
        seen = set()
        for _ in range(400):
            seen.update(island_chest_rarities(rng, 3))
        self.assertEqual(seen, set(_CHEST_RARITIES))


if __name__ == "__main__":
    unittest.main()
