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
from world.gen.height.graph import walk_links, check_grid, reachable, to_ascii
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

    def test_a_rim_cell_that_is_the_only_join_keeps_its_strip_joined(self):
        """A rim cell may be the only thing joining a strip of terrace to the
        rest -- level 1 pinched between the low ground and a higher cap.
        While a flight linked only at its ends, taking that cell stranded
        the strip, and the cut was rolled back (NS-4). A north flight is a
        door now (WLD-014): it joins the strip through its west flank, so the
        cut stands and the strip stays on the terrace."""
        g = _plateau()
        # a level-2 cap under the west half of the rim: cells (0..3, 4)
        for c in range(4):
            g[(c, 4)] = Cell(GROUND, level=2)
        self.assertEqual(_nstair_site(g, 4, 3), 1, "the site itself is fine")
        # the strip's only way to the rest of its terrace is (4, 3)
        self.assertTrue(all(g[(c, 4)].level == 2 for c in range(4)))
        _cut(g, 4, 3, VSTAIR, "rock", 1, "n")
        self.assertEqual(g[(4, 3)].dir, "n")
        joined = reachable(g, (4, 4))
        for c in range(4):
            self.assertIn((c, 3), joined, f"the strip lost ({c}, 3)")

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
        self.assertIn((3, 2), walk_links(g, (3, 3)))
        self.assertIn((3, 4), walk_links(g, (3, 3)))
        self.assertIn((3, 3), walk_links(g, (3, 2)))
        self.assertIn((3, 3), walk_links(g, (3, 4)))

    def test_the_door_has_no_walls_at_its_flanks(self):
        """WLD-014: the plateau ground either side of a north flight is its
        own terrace, and the flight joins it both ways. The four edges are
        the whole of what it links."""
        g = _plateau()
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        self.assertEqual(set(walk_links(g, (3, 3))),
                         {(3, 2), (3, 4), (2, 3), (4, 3)})
        self.assertIn((3, 3), walk_links(g, (2, 3)))
        self.assertIn((3, 3), walk_links(g, (4, 3)))

    def test_the_frontier_stays_shut_beside_the_door(self):
        """The only walls left are the frontier between the floors: a flank
        does not reach the low ground north of it, and the landing does not
        reach the flanks. Changing floors still means crossing the flight."""
        g = _plateau()
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        for flank in ((2, 3), (4, 3)):
            links = walk_links(g, flank)
            self.assertNotIn((flank[0], 2), links, f"{flank} reaches the low ground")
        self.assertEqual({p for p in walk_links(g, (3, 2)) if g[p].level == 1},
                         {(3, 3)}, "the landing reaches the terrace only "
                                   "through the flight")

    def test_a_flank_at_another_level_does_not_link(self):
        """The site rule keeps both flanks at the flight's level, but the
        link rule states its own condition rather than trusting that: ground
        at the low level beside the flight is the frontier, not a door."""
        g = _plateau()
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        g[(2, 3)] = Cell(GROUND, level=0)
        self.assertNotIn((2, 3), walk_links(g, (3, 3)))
        self.assertNotIn((3, 3), walk_links(g, (2, 3)))

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
