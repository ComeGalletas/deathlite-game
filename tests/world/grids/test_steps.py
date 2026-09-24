"""`can_cross` / `can_step` / `diagonal_blocked` on hand-built grids.

Moved down from the generated-world sweeps in `tests/world/test_elevation.py`
(worldgen R4): the composition identity of a diagonal step and the corner the
endpoint rule exists to catch hold for a neighbourhood, not for a lucky
layout, so each is shown here on a drawing where every case is visible. The
world sweeps that remain there state the invariants over real islands.
"""
import unittest

from world.gen.height.graph import walk_links
from world.layout import GROUND, WALKABLE_KINDS
from world.rules.steps import can_cross, can_step, diagonal_blocked

from tests.world.grids import scenes

_ORTHO = ((1, 0), (-1, 0), (0, 1), (0, -1))
_DIAG = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def _tiles(ix):
    return [(c, r) for r in range(ix.rows) for c in range(ix.cols)]


class LevelChangeTests(unittest.TestCase):
    def test_ground_to_ground_across_a_drop_is_never_a_step(self):
        for name, drawing in scenes.SCENES.items():
            ix = scenes.index(drawing)
            drops = 0
            for a in _tiles(ix):
                if ix.kind_at(*a) != GROUND:
                    continue
                for dc, dr in _ORTHO:
                    b = (a[0] + dc, a[1] + dr)
                    if ix.kind_at(*b) != GROUND or ix.level_at(*b) == ix.level_at(*a):
                        continue
                    drops += 1
                    self.assertFalse(can_cross(ix, a, b), f"{name}: {a}->{b}")
            if name == "lateral":
                self.assertGreater(drops, 0, "the flank has no bare drop to refuse")

    def test_each_flight_joins_its_two_terraces(self):
        """The rule must not seal the route it guards: in every scene the
        flight is the one way from level 1 to level 0."""
        cases = {
            "wall_flight": ((2, 1), (2, 2), (2, 3)),     # terrace, flight, low
            "north_rim": ((2, 3), (2, 2), (2, 1)),
            "lateral": ((2, 2), (3, 2), (3, 1)),         # in from the flank, out north
        }
        for name, (top, flight, low) in cases.items():
            ix = scenes.index(scenes.SCENES[name])
            with self.subTest(scene=name):
                self.assertEqual(ix.level_at(*top), 1)
                self.assertEqual(ix.level_at(*low), 0)
                self.assertTrue(can_cross(ix, top, flight))
                self.assertTrue(can_cross(ix, flight, low))
                self.assertTrue(can_cross(ix, low, flight))

    def test_the_lateral_foot_opens_onto_both_terraces(self):
        ix = scenes.index(scenes.LATERAL)
        foot = (3, 3)
        self.assertTrue(can_cross(ix, (2, 3), foot))     # uphill flank
        self.assertTrue(can_cross(ix, foot, (4, 3)))     # downhill side
        self.assertTrue(can_cross(ix, foot, (3, 4)))     # south, low terrace


class DiagonalTests(unittest.TestCase):
    def test_a_diagonal_is_its_detours_minus_the_endpoint_rule(self):
        """`can_step` composes a diagonal from its right-angle detours, and
        then refuses it outright between two ground tiles of different
        levels -- on every tile pair of every scene."""
        for name, drawing in scenes.SCENES.items():
            ix = scenes.index(drawing)
            for a in _tiles(ix):
                if not ix.has_surface(*a):
                    continue
                for dc, dr in _DIAG:
                    b = (a[0] + dc, a[1] + dr)
                    if not ix.has_surface(*b):
                        continue
                    h, v = (a[0] + dc, a[1]), (a[0], a[1] + dr)
                    legs = ((can_cross(ix, a, h) and can_cross(ix, h, b))
                            or (can_cross(ix, a, v) and can_cross(ix, v, b)))
                    self.assertEqual(can_step(ix, a, b),
                                     legs and not diagonal_blocked(ix, a, b),
                                     f"{name}: {a}->{b}")

    def test_the_endpoint_rule_catches_the_corner_beside_a_lateral_head(self):
        """The case the rule exists for, drawn: the head opens west onto the
        plateau and north onto the low terrace, so the detour through it is
        open end to end, and only the endpoint rule stops a body gaining a
        level in one diagonal move."""
        ix = scenes.index(scenes.LATERAL)
        a, head, b = (2, 2), (3, 2), (3, 1)
        self.assertTrue(can_cross(ix, a, head) and can_cross(ix, head, b))
        self.assertTrue(diagonal_blocked(ix, a, b))
        self.assertFalse(can_step(ix, a, b))
        self.assertFalse(can_step(ix, b, a))

    def test_no_diagonal_changes_level_between_two_terraces(self):
        for name, drawing in scenes.SCENES.items():
            ix = scenes.index(drawing)
            for a in _tiles(ix):
                if ix.kind_at(*a) != GROUND:
                    continue
                for dc, dr in _DIAG:
                    b = (a[0] + dc, a[1] + dr)
                    if ix.kind_at(*b) == GROUND and ix.level_at(*b) != ix.level_at(*a):
                        self.assertFalse(can_step(ix, a, b), f"{name}: {a}->{b}")


class MirrorTests(unittest.TestCase):
    def test_can_cross_agrees_with_walk_links_on_every_scene(self):
        """The runtime rule and the generator's, cell for cell -- the pair
        `test_elevation.CanCrossTests` checks over real islands."""
        for name, drawing in scenes.SCENES.items():
            g = scenes.grid(drawing)
            ix = scenes.index(drawing)
            for pos, cell in g.items():
                if cell.kind not in WALKABLE_KINDS:
                    continue
                want = set(walk_links(g, pos))
                got = {(pos[0] + dc, pos[1] + dr) for dc, dr in _ORTHO
                       if can_cross(ix, pos, (pos[0] + dc, pos[1] + dr))}
                self.assertEqual(got, want, f"{name} at {pos}")


if __name__ == "__main__":
    unittest.main()
