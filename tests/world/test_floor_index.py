"""ENT-018.3: the floor rule's per-square index gives exactly the full
scan's answers (`enemy_update_journal.md`).

`FloorIndex` narrows `room_of` and `in_corridor` to the islands and bridges
whose bounds reach a point's square, in layout order. Pinned against the
unindexed rule, answer for answer (`room_of` by identity):

* dense samples of the four pinned worlds, and every island and bridge
  edge and every square boundary, at and a hair either side;
* the keying: a bridge is tested through `Rect.collidepoint`, which
  truncates toward zero, so -0.5 lies on a bridge that starts at 0; an
  island's bounds compare as floats, so it does not; nan and inf;
* the collider's own lookups (`GameMap`) against the rule without the
  index.
"""
import math
import unittest
from types import SimpleNamespace

import pygame

from tests import worlds as W
from world.rules import floor as floor_rules


def _answers(layout, x, y, index=None):
    return (floor_rules.room_of(layout, x, y, index),
            floor_rules.in_corridor(layout, x, y, index),
            floor_rules.point_on_floor(layout, x, y, index),
            floor_rules.inset_at(layout, x, y, index))


def _edge_points(layout, square):
    """Every island and bridge edge and every square boundary the world
    spans, at and a hair either side, crossed with a spread of the other
    coordinate."""
    b = layout.bounds
    xs, ys = set(), set()
    for item in [*layout.rooms, *layout.corridors]:
        r = item.rect
        xs.update((r.left, r.right, r.centerx))
        ys.update((r.top, r.bottom, r.centery))
    xs.update(range(-square, b.right + square, square))
    ys.update(range(-square, b.bottom + square, square))
    near = (-0.5, -1e-9, 0.0, 1e-9, 0.5)
    out = []
    for x in sorted(xs):
        for y in sorted(ys)[::11]:
            out.extend((x + d, y) for d in near)
    for y in sorted(ys):
        for x in sorted(xs)[::11]:
            out.extend((x, y + d) for d in near)
    return out


class PinnedWorldTests(unittest.TestCase):
    def test_every_answer_is_the_full_scans(self):
        for seed in W.SEEDS:
            layout = W.layout(seed)
            index = floor_rules.FloorIndex(layout)
            b = layout.bounds
            points = [(x + 0.37, y + 0.61)
                      for x in range(b.left - 64, b.right + 64, 53)
                      for y in range(b.top - 64, b.bottom + 64, 53)]
            points += _edge_points(layout, floor_rules.FloorIndex.SQUARE)
            on_floor = on_bridge = 0
            with self.subTest(seed=seed):
                for x, y in points:
                    want = _answers(layout, x, y)
                    got = _answers(layout, x, y, index)
                    if got[0] is not want[0] or got[1:] != want[1:]:
                        self.fail(f"seed {seed} at ({x}, {y}): {got} != {want}")
                    on_floor += want[2]
                    on_bridge += want[1]
                # The samples mean something only if they reach floor and
                # bridges as well as the void.
                self.assertGreater(on_floor, len(points) // 10)
                self.assertGreater(on_bridge, 50)


class KeyingTests(unittest.TestCase):
    """A small layout drawn by hand: an island and a bridge at the origin's
    edges, and one well into negative coordinates."""

    def setUp(self):
        island = SimpleNamespace(rect=pygame.Rect(-300, -300, 256, 256),
                                 cells={(c, r) for c in range(4) for r in range(4)},
                                 levels=None)
        self.layout = SimpleNamespace(
            rooms=[island],
            corridors=[SimpleNamespace(rect=pygame.Rect(0, 0, 64, 32)),
                       SimpleNamespace(rect=pygame.Rect(-520, -40, 60, 30))])
        self.index = floor_rules.FloorIndex(self.layout)

    def _same(self, x, y):
        want = (floor_rules.room_of(self.layout, x, y),
                floor_rules.in_corridor(self.layout, x, y))
        got = (floor_rules.room_of(self.layout, x, y, self.index),
               floor_rules.in_corridor(self.layout, x, y, self.index))
        self.assertIs(got[0], want[0], (x, y))
        self.assertEqual(got[1], want[1], (x, y))
        return want

    def test_a_bridge_truncates_toward_zero(self):
        # `collidepoint` reads -0.5 as 0: on the bridge that starts at 0.
        self.assertTrue(self._same(-0.5, 5.0)[1])
        self.assertTrue(self._same(5.0, -0.99)[1])
        self.assertFalse(self._same(-1.0, 5.0)[1])
        # And -520.5 as -520: on the bridge that starts there.
        self.assertTrue(self._same(-520.5, -30.0)[1])
        self.assertFalse(self._same(-460.5, -30.0)[1])

    def test_an_island_compares_as_floats(self):
        self.assertIsNotNone(self._same(-300.0, -300.0)[0])
        self.assertIsNone(self._same(-300.5, -290.0)[0])
        self.assertIsNotNone(self._same(-44.5, -44.5)[0])
        self.assertIsNone(self._same(-44.0, -100.0)[0])

    def test_nan_and_inf_answer_as_the_full_scan(self):
        for x, y in ((math.nan, 5.0), (5.0, math.nan), (math.inf, 5.0), (-math.inf, -math.inf)):
            with self.subTest(x=x, y=y):
                self._same(x, y)


class ColliderTests(unittest.TestCase):
    """`GameMap`'s lookups, which now pass the index, against the rule
    without it."""

    def test_the_collider_answers_as_the_rule(self):
        gm = W.game_map(35)
        layout = gm.layout
        b = layout.bounds
        for x in range(b.left, b.right, 29):
            for y in range(b.top, b.bottom, 29):
                x_, y_ = x + 0.5, y + 0.25
                self.assertEqual(gm._point_ok(x_, y_),
                                 floor_rules.point_on_floor(layout, x_, y_))
                self.assertEqual(gm.on_bridge(x_, y_), floor_rules.in_corridor(layout, x_, y_))
                self.assertIs(gm._room_of(x_, y_), floor_rules.room_of(layout, x_, y_))
                self.assertEqual(gm.inset_at(x_, y_), float(floor_rules.inset_at(layout, x_, y_)))

    def test_every_collider_lookup_carries_the_index(self):
        # The saving itself: an answer is the same without the index, so
        # only this can see the collider stop passing it.
        from unittest import mock

        gm = W.game_map(35)
        c = gm.layout.rooms[0].rect.center
        seen = []

        def spy(name):
            real = getattr(floor_rules, name)

            def call(layout, x, y, index=None):
                seen.append((name, index))
                return real(layout, x, y, index)
            return call

        with mock.patch.object(floor_rules, "point_on_floor", spy("point_on_floor")), \
                mock.patch.object(floor_rules, "in_corridor", spy("in_corridor")), \
                mock.patch.object(floor_rules, "room_of", spy("room_of")), \
                mock.patch.object(floor_rules, "inset_at", spy("inset_at")):
            gm._point_ok(*c)
            gm.on_bridge(*c)
            gm._room_of(*c)
            gm.inset_at(*c)
        self.assertEqual({n for n, _i in seen},
                         {"point_on_floor", "in_corridor", "room_of", "inset_at"})
        self.assertTrue(all(i is gm._floor_index() for _n, i in seen), seen)

    def test_another_layout_gets_its_own_index(self):
        gm = W.fresh(7)
        first = gm._floor_index()
        self.assertIs(gm._floor_index(), first)
        gm.layout = W.layout(35)
        self.assertIsNot(gm._floor_index(), first)
        self.assertIs(gm._floor_index()._layout, gm.layout)


if __name__ == "__main__":
    unittest.main()
