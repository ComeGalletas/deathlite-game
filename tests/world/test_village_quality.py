"""What the human island and its village come out as, over a sweep.

The rest of the village tests read three or four pinned seeds and assert that
*every* village satisfies each rule. That is the right shape for a rule the
pass really does guarantee -- a hall on the heal's x, a pen, no two circles
overlapping -- and the wrong shape for one the island's geography can refuse.
When the island lost a quarter of its ground (`size` 0.56 -> 0.51) two such
"every village" assertions turned out to have been passing on four seeds by
luck: the heal's full company of two was already failing elsewhere at 0.56,
and a village on the tightest island now gets one or two houses instead of
three or four. Asserting them per village pins the seeds, not the generator.

So this module measures instead. It reads fifteen shared worlds -- the pinned
seeds plus the twelve the repair tests already build, so the sweep is nearly
free -- and splits what it finds in two: the rules that hold for every village
of the sample, and the *rates* for the ones the ground can refuse. A rate is
what the pass actually promises, and it moves when the generator regresses
while surviving a seed whose island happens to be awkward.

The numbers in the assertions are the measured ones with headroom, and the
measurement at the time of writing is in each test's docstring. When a
deliberate change moves them, move the numbers and say so in
`documentation/journals/human_island_journal.md`.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game import config
from tests import worlds as W
from world.gen.tuning import VILLAGE_KIND, _V_HEAL_COMPANY, _V_HOUSES
from world.layout import GROUND

# The pinned seeds plus the repair suite's twelve: fifteen worlds, twenty-three
# villages, and every one of them already built by another module in a full run.
SEEDS = sorted({*range(1, 13), *W.SEEDS})


def _sample():
    """`(seed, room, village)` for every village island of the sweep, plus
    the smallest volcanic island of that world (`None` when it has none)."""
    out = []
    for seed in SEEDS:
        w = W.layout(seed)
        rooms = {r.id: r for r in w.rooms if r.kind == VILLAGE_KIND}
        volcanic = [len(r.cells) for r in w.rooms if r.topography == "volcanic"]
        for v in w.villages:
            out.append((seed, rooms[v.room_id], v, min(volcanic) if volcanic else None))
    return out


def _kinds(village):
    return [k for k, _x, _y in village.buildings]


class IslandSizeTests(unittest.TestCase):
    """The island the village stands on."""

    def test_the_island_is_flat_lakeless_and_a_fifth_of_a_volcanic_one(self):
        """Measured over the sweep: 145 to 222 walkable tiles, 0.16 to 0.26 of
        the smallest volcanic island in the same world. The band below is wide
        enough for the seeds this does not read and tight enough that a `size`
        change cannot pass unnoticed -- which is the point, since `size` is the
        one knob that decides all of this."""
        for seed, room, _v, volcanic in _sample():
            with self.subTest(seed=seed, room=room.id):
                self.assertGreaterEqual(len(room.cells), 110, "island too small")
                self.assertLessEqual(len(room.cells), 280, "island too large")
                self.assertEqual({c.level for c in room.grid.values()
                                  if c.kind == GROUND}, {0}, "not flat")
                if volcanic is not None:
                    self.assertLessEqual(len(room.cells) / volcanic, 0.35,
                                         "not a small island any more")

    def test_no_island_is_pinched_past_use(self):
        """The village needs a body, not a ribbon: at least a third of the
        rect's tiles are walkable. Measured 0.41 to 0.57 over the sweep."""
        for seed, room, _v, _volcanic in _sample():
            cols, rows = room.tile_dims
            with self.subTest(seed=seed, room=room.id):
                self.assertGreaterEqual(len(room.cells) / (cols * rows), 0.33,
                                        f"{room.tile_dims} rect, {len(room.cells)} cells")


class VillageAlwaysTests(unittest.TestCase):
    """What every village gets, however tight its island."""

    def test_every_village_has_its_core(self):
        """A forge near the middle, the heal due north of it on its x, a town
        hall, a sheep pen, a military building by a bridge, and at least one
        house. Measured 23 of 23 on every count, the forge at most 4.5 tiles
        off the island's centre."""
        px = config.TILE_PX
        for seed, room, v, _volcanic in _sample():
            with self.subTest(seed=seed, room=room.id):
                kinds = _kinds(v)
                self.assertLessEqual(v.forge.distance_to(room.center), 6 * px,
                                     "the forge wandered off the middle")
                self.assertLess(v.heal.y, v.forge.y, "the heal is not north")
                self.assertLess(abs(v.heal.x - v.forge.x), px, "the heal is off the axis")
                self.assertIn("monastery", kinds, "no town hall")
                self.assertIsNotNone(v.pen, "no sheep pen")
                self.assertTrue(any(k in ("barracks", "tower", "archery") for k in kinds),
                                "no military building")
                self.assertGreaterEqual(kinds.count("house"), 1, "no houses")
                self.assertGreaterEqual(v.company, 1, "the heal stands alone")


class VillageRateTests(unittest.TestCase):
    """What the ground can refuse, as a rate over the sweep."""

    def test_most_villages_get_their_full_row_of_houses(self):
        """`_V_HOUSES` is 3-5 (the owner's row, 2026-09-12); the tightest
        islands still seat only one or two. Measured 20 of 23 villages at
        three or more (0.87), the sweep at 1 to 5, and 16 of 23 at four or
        five -- houses may crowd now, so the row closes up rather than
        stopping at the ring's slots."""
        counts = [_kinds(v).count("house") for _seed, _room, v, _vol in _sample()]
        full = sum(1 for n in counts if n >= _V_HOUSES[0])
        self.assertGreaterEqual(full, 0.75 * len(counts),
                                f"only {full} of {len(counts)} villages seated "
                                f"{_V_HOUSES[0]} houses: {sorted(counts)}")

    def test_most_heals_get_the_full_company(self):
        """Two buildings besides the forge and the hall within reach of the
        heal. Measured 20 of 23 (0.87) -- six of them with three or four,
        since the crowding row gathers round the square; the other three
        have one, which `VillageAlwaysTests` pins as the floor."""
        counts = [v.company for _seed, _room, v, _vol in _sample()]
        full = sum(1 for n in counts if n >= _V_HEAL_COMPANY)
        self.assertGreaterEqual(full, 0.75 * len(counts),
                                f"only {full} of {len(counts)} heals kept the "
                                f"full company: {sorted(counts)}")


if __name__ == "__main__":
    unittest.main()
