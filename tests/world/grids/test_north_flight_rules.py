"""North flights on hand-built grids: the site rule and the link rule.

Moved from `tests/world/test_north_flights.py` (worldgen R4) so they run in
the `unit` tier; the generated-world checks stay there. A north face has no
wall, so the flight is the rim cell itself, one cell whatever the drop, with
the low ground north of it and its own terrace south::

    = = = = = =            = = = = = =
    # # # # # #     ->     # # # ^ # #
    # # # # # #            # # # # # #
"""
import random
import unittest

from world.gen.height.flights import (_nstair_site, _cut, _cut_flights,
                                      _cut_north_flights)
from world.gen.height.graph import walk_links, check_grid, to_ascii
from world.layout import Cell, GROUND, CLIFF, VSTAIR, EWSTAIR


def _grid(rows, levels):
    """A grid from ASCII rows: `=` ground, `#` cliff (level 1 over 0), `.`
    void; `levels` gives each row's ground level."""
    grid = {}
    for r, line in enumerate(rows):
        for c, ch in enumerate(line.split()):
            if ch == "=":
                grid[(c, r)] = Cell(GROUND, level=levels[r])
            elif ch == "#":
                grid[(c, r)] = Cell(CLIFF, level=1, drop=1, row=0)
    return grid


def _plateau():
    """Three rows of level-0 back ground, then a level-1 terrace whose wall
    hangs over open water. The terrace is stranded -- its only possible way
    up is a north flight on its rim -- so `check_grid` complains until one
    is cut and is clean afterwards.

        = = = = = = =     0
        = = = = = = =     0
        = = = = = = =     0
        = = = = = = =     1   <- the rim, where a north flight may go
        = = = = = = =     1
        # # # # # # #     the wall, over the sea
    """
    rows = ["= = = = = = =", "= = = = = = =", "= = = = = = =",
            "= = = = = = =", "= = = = = = =", "# # # # # # #"]
    return _grid(rows, [0, 0, 0, 1, 1, 1])


class SiteRuleTests(unittest.TestCase):
    def test_a_rim_cell_with_room_to_land_qualifies(self):
        g = _plateau()
        self.assertEqual(_nstair_site(g, 3, 3), 1)

    def test_the_flight_takes_the_rim_cell_and_nothing_else(self):
        g = _plateau()
        self.assertTrue(any("unreachable" in s for s in check_grid(g)),
                        "the fixture's terrace should start stranded")
        before = dict(g)
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        cell = g[(3, 3)]
        self.assertEqual((cell.kind, cell.level, cell.drop, cell.row, cell.dir),
                         (VSTAIR, 1, 1, 0, "n"))
        changed = [p for p in g if g[p] != before[p]]
        self.assertEqual(changed, [(3, 3)])
        self.assertEqual(check_grid(g), [])
        self.assertIn("^", to_ascii(g))

    def test_the_cell_has_to_be_terrace_ground(self):
        g = _plateau()
        self.assertIsNone(_nstair_site(g, 3, 2), "level-0 ground is not a rim")
        self.assertIsNone(_nstair_site(g, 3, 5), "a wall cell is not a rim")
        self.assertIsNone(_nstair_site(g, 3, 4),
                          "a cell with its own terrace north is not the rim")

    def test_the_terrace_must_continue_south_and_on_both_flanks(self):
        for missing in ((2, 3), (4, 3), (3, 4)):
            g = _plateau()
            del g[missing]
            self.assertIsNone(_nstair_site(g, 3, 3), f"without {missing}")
        g = _plateau()
        g[(2, 3)] = Cell(GROUND, level=0)
        self.assertIsNone(_nstair_site(g, 3, 3), "a flank at the low level")

    def test_the_landing_needs_room_for_a_large_body(self):
        for missing in ((2, 2), (4, 2), (3, 1)):
            g = _plateau()
            del g[missing]
            self.assertIsNone(_nstair_site(g, 3, 3), f"without {missing}")

    def test_a_two_level_drop_qualifies_but_three_does_not(self):
        g = _plateau()
        for p, c in list(g.items()):
            if c.level == 1:
                g[p] = c._replace(level=2, drop=2 if c.kind == CLIFF else 0)
        self.assertEqual(_nstair_site(g, 3, 3), 2)
        for p, c in list(g.items()):
            if c.level == 2:
                g[p] = c._replace(level=3)
        self.assertIsNone(_nstair_site(g, 3, 3))

    def test_the_wall_pass_finds_nothing_and_the_north_pass_places_one(self):
        """The wall hangs over water, so `_cut_flights` has no site at all;
        the north pass has the whole rim to choose from -- one region, one
        cut."""
        g = _plateau()
        _cut_flights(g, random.Random(1), per_region=1, region=8, spacing=4)
        self.assertFalse([c for c in g.values() if c.kind in (VSTAIR, EWSTAIR)])
        _cut_north_flights(g, random.Random(1), per_region=1, region=8,
                           spacing=4)
        north = [p for p, c in g.items() if c.kind == VSTAIR and c.dir == "n"]
        self.assertEqual(len(north), 1)
        self.assertEqual(north[0][1], 3, "on the rim row")
        self.assertEqual(check_grid(g), [])

    def test_the_north_pass_draws_nothing_the_stream_sees(self):
        """`build_grid` restores the stream round the pass; the pass itself
        must therefore be the only thing that reads its own draws, which is
        the property this pins: two runs from equal states cut the same
        flight."""
        a, b = _plateau(), _plateau()
        _cut_north_flights(a, random.Random(7))
        _cut_north_flights(b, random.Random(7))
        self.assertEqual(a, b)

    def test_a_cut_that_would_sever_its_own_flank_is_rolled_back(self):
        """A rim cell may be the only thing joining a strip of terrace to the
        rest -- level 1 pinched between the low ground and a higher cap. A
        flight links only at its ends, so taking that cell strands the strip
        (and the prune would then delete the flight's own flank). The cut
        stands only if both flanks still reach the terrace another way."""
        g = _plateau()
        # a level-2 cap under the west half of the rim: cells (0..3, 4)
        for c in range(4):
            g[(c, 4)] = Cell(GROUND, level=2)
        self.assertEqual(_nstair_site(g, 4, 3), 1, "the site itself is fine")
        before = dict(g)
        self.assertFalse(_cut(g, 4, 3, VSTAIR, "rock", 1, "n"))
        self.assertEqual(g, before, "a rolled-back cut leaves no trace")
        # further east the strip is joined on both sides: the cut stands
        self.assertTrue(_cut(g, 5, 3, VSTAIR, "rock", 1, "n"))
        self.assertEqual(g[(5, 3)].dir, "n")

    def test_the_north_pass_joins_a_stranded_terrace_from_its_back(self):
        """With no regional quota at all, the join loop alone still reaches
        the stranded cap."""
        g = _plateau()
        _cut_north_flights(g, random.Random(1), per_region=0)
        north = [p for p, c in g.items() if c.kind == VSTAIR and c.dir == "n"]
        self.assertEqual(len(north), 1, "joined by the stranded-cap loop")
        self.assertEqual(check_grid(g), [])


class LinkRuleTests(unittest.TestCase):
    def test_down_is_north_and_up_is_south(self):
        g = _plateau()
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        self.assertEqual(set(walk_links(g, (3, 3))), {(3, 2), (3, 4)})
        self.assertIn((3, 3), walk_links(g, (3, 2)))
        self.assertIn((3, 3), walk_links(g, (3, 4)))
        # the flanks are the same terrace but a flight links only at its ends
        self.assertNotIn((3, 3), walk_links(g, (2, 3)))
        self.assertNotIn((3, 3), walk_links(g, (4, 3)))

    def test_check_grid_names_a_flight_leading_nowhere(self):
        g = _plateau()
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        g[(3, 2)] = Cell(GROUND, level=1)
        self.assertTrue(any("no low landing" in s for s in check_grid(g)))
        g = _plateau()
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        g[(3, 4)] = Cell(GROUND, level=0)
        self.assertTrue(any("no terrace to the south" in s
                            for s in check_grid(g)))

    def test_ascii_shows_the_orientation(self):
        g = _plateau()
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        lines = to_ascii(g).splitlines()
        self.assertEqual(lines[3].split()[3], "^")
        self.assertEqual(set(lines[5].split()), {"#"})


if __name__ == "__main__":
    unittest.main()
