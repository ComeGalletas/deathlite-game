"""`_foot_stone_frees` on hand-built grids, where every case is visible.

Moved from `tests/world/test_elevation.py`, where it was the model for
worldgen R4 but ran in the `world` tier by path. The generated-world half --
every real flight foot opens onto what replaced its stone -- stays there as
`FootStoneTests`.
"""
import unittest

from world.gen.height.walls import _foot_stone_frees
from world.layout import CLIFF, GROUND, Cell


class FootStoneRuleTests(unittest.TestCase):
    """`_foot_stone_frees` on hand-built grids, where every case is visible."""

    def _grid(self, below):
        """A foot at (0, 0) arriving on level 0, with `below` laid out south
        of it as a list of cells starting at (0, 1)."""
        return {(0, i + 1): cell for i, cell in enumerate(below)}

    def test_bare_ground_under_the_foot_is_fine(self):
        g = self._grid([Cell(GROUND, level=0)])
        self.assertTrue(_foot_stone_frees(g, (0, 0), 0))

    def test_nothing_at_all_under_the_foot_is_fine(self):
        self.assertTrue(_foot_stone_frees({}, (0, 0), 0))

    def test_stone_bottoming_out_on_the_landing_floor_can_be_freed(self):
        g = self._grid([Cell(CLIFF, level=1, drop=1, row=0),
                        Cell(GROUND, level=0)])
        self.assertTrue(_foot_stone_frees(g, (0, 0), 0))

    def test_stone_over_higher_ground_cannot(self):
        """The four sites this rejects: lifting the stone here would leave a
        bare level change instead of a wall you can see."""
        g = self._grid([Cell(CLIFF, level=1, drop=1, row=0),
                        Cell(GROUND, level=1)])
        self.assertFalse(_foot_stone_frees(g, (0, 0), 0))

    def test_stone_over_open_water_cannot(self):
        g = self._grid([Cell(CLIFF, level=1, drop=1, row=0)])
        self.assertFalse(_foot_stone_frees(g, (0, 0), 0))

    def test_a_two_cell_face_is_taken_as_a_whole(self):
        g = self._grid([Cell(CLIFF, level=2, drop=2, row=0),
                        Cell(CLIFF, level=2, drop=2, row=1),
                        Cell(GROUND, level=0)])
        self.assertTrue(_foot_stone_frees(g, (0, 0), 0))
        self.assertFalse(_foot_stone_frees(g, (0, 0), 1))


if __name__ == "__main__":
    unittest.main()
