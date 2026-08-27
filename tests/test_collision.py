"""Milestone 2: spatial grid broad-phase + circle overlap."""
import unittest

import pygame

from systems.collision import SpatialGrid, circles_overlap


class Ent:
    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)


class CircleOverlapTests(unittest.TestCase):
    def test_touching_counts_as_overlap(self):
        self.assertTrue(circles_overlap(0, 0, 5, 10, 0, 5))

    def test_far_apart_no_overlap(self):
        self.assertFalse(circles_overlap(0, 0, 5, 100, 0, 5))


class SpatialGridTests(unittest.TestCase):
    def test_query_returns_nearby_excludes_far(self):
        grid = SpatialGrid(cell_size=64)
        near = Ent(100, 100)
        far = Ent(2000, 2000)
        grid.rebuild([near, far])
        found = grid.query_circle(110, 110, 20)
        self.assertIn(near, found)
        self.assertNotIn(far, found)

    def test_query_radius_spans_multiple_cells(self):
        grid = SpatialGrid(cell_size=32)
        ents = [Ent(x, 0) for x in range(0, 200, 20)]
        grid.rebuild(ents)
        found = grid.query_circle(100, 0, 80)
        # Every entity within 80px (plus one cell of broad-phase slack) present.
        for e in ents:
            if abs(e.pos.x - 100) <= 80:
                self.assertIn(e, found)

    def test_rebuild_clears_previous(self):
        grid = SpatialGrid(cell_size=64)
        grid.rebuild([Ent(0, 0)])
        grid.rebuild([Ent(500, 500)])
        self.assertEqual(grid.query_circle(0, 0, 10), [])


if __name__ == "__main__":
    unittest.main()
