"""`world/gen/graph.py` on hand-built island chains: BFS distances, which
island is a village, what every island is, and what shape it takes.

Stand-in settings (a namespace with the fields the stage reads) keep the
numbers visible in each test and independent of the shipped tuning, which
the generated-world tests (`tests/world/test_village.py`, `test_layout.py`)
read from the data.
"""
import random
import unittest
from types import SimpleNamespace

import pygame

from world.gen import graph
from world.gen.tuning import SPECIAL_KINDS, VILLAGE_KIND
from world.layout import Room


def _chain(n):
    """`n` islands in a line, 0 - 1 - 2 - ... - n-1."""
    rooms = []
    for i in range(n):
        nb = [j for j in (i - 1, i + 1) if 0 <= j < n]
        rooms.append(Room(id=i, cell=(i, 0), rect=pygame.Rect(i * 64, 0, 64, 64),
                          kind="combat", neighbors=nb))
    return rooms


def _settings(**over):
    s = dict(villages=(1, 1), village_distance=(1, 2),
             topographies={"small": {"weight": 1}, "volcanic": {"weight": 3},
                           "retired": {"weight": 0}, "unweighted": {}},
             boss_topography="boss", village_topography="flat")
    s.update(over)
    return SimpleNamespace(**s)


class DistanceTests(unittest.TestCase):
    def test_distances_are_hops_along_the_chain(self):
        rooms = _chain(5)
        self.assertEqual(graph._distances(rooms, 0), {0: 0, 1: 1, 2: 2, 3: 3, 4: 4})
        self.assertEqual(graph._distances(rooms, 2), {0: 2, 1: 1, 2: 0, 3: 1, 4: 2})

    def test_an_unlinked_island_is_left_out(self):
        rooms = _chain(3)
        rooms[2].neighbors = []
        rooms[1].neighbors = [0]
        self.assertEqual(graph._distances(rooms, 0), {0: 0, 1: 1})


class VillagePickTests(unittest.TestCase):
    def test_villages_come_from_the_distance_band_never_start_or_boss(self):
        rooms = _chain(6)
        dist = graph._distances(rooms, 0)
        s = _settings(villages=(2, 2), village_distance=(2, 3))
        for seed in range(20):
            got = graph._pick_villages(rooms, random.Random(seed), 0, 5, dist, s)
            self.assertEqual(len(got), 2)
            self.assertLessEqual(set(got), {2, 3})
            self.assertEqual(got, sorted(got))

    def test_the_count_is_capped_by_the_candidates(self):
        rooms = _chain(4)
        dist = graph._distances(rooms, 0)
        got = graph._pick_villages(rooms, random.Random(1), 0, 3, dist,
                                   _settings(villages=(3, 3), village_distance=(1, 1)))
        self.assertEqual(got, [1])

    def test_an_empty_band_falls_back_to_any_island_not_none(self):
        """The forge has to exist somewhere: with nothing in the band, any
        island that is neither start nor boss will do."""
        rooms = _chain(4)
        dist = graph._distances(rooms, 0)
        got = graph._pick_villages(rooms, random.Random(1), 0, 3, dist,
                                   _settings(villages=(1, 1), village_distance=(7, 9)))
        self.assertEqual(len(got), 1)
        self.assertIn(got[0], (1, 2))


class KindTests(unittest.TestCase):
    def test_start_boss_village_and_the_rest_combat(self):
        rooms = _chain(5)
        dist = graph._distances(rooms, 0)
        graph._assign_kinds(rooms, random.Random(3), 0, 4, dist,
                            _settings(villages=(1, 1), village_distance=(2, 2)))
        kinds = [r.kind for r in rooms]
        self.assertEqual(kinds[0], "start")
        self.assertEqual(kinds[4], "boss")
        self.assertEqual(kinds[2], VILLAGE_KIND)
        # The specials are parked (SPECIAL_KINDS is empty), so the rest fight.
        self.assertEqual(SPECIAL_KINDS, ())
        self.assertEqual({kinds[1], kinds[3]}, {"combat"})


class TopographyTests(unittest.TestCase):
    def test_the_boss_and_the_villages_are_fixed_the_rest_are_drawn(self):
        rooms = _chain(40)
        rooms[5].kind = VILLAGE_KIND
        graph.assign_topography(rooms, random.Random(9), 39, _settings())
        self.assertEqual(rooms[39].topography, "boss")
        self.assertEqual(rooms[5].topography, "flat")
        drawn = [r.topography for r in rooms if r.id not in (5, 39)]
        self.assertLessEqual(set(drawn), {"small", "volcanic"},
                             "a zero or missing weight is never drawn")
        self.assertGreater(drawn.count("volcanic"), drawn.count("small"),
                           "drawn by weight, 3 to 1")

    def test_the_draw_is_the_rng_s(self):
        a, b = _chain(12), _chain(12)
        graph.assign_topography(a, random.Random(4), 11, _settings())
        graph.assign_topography(b, random.Random(4), 11, _settings())
        self.assertEqual([r.topography for r in a], [r.topography for r in b])


if __name__ == "__main__":
    unittest.main()
