"""The village tidy pass's rules (`world/gen/village_tidy.py`) on a stand-in
site: every branch the generated villages rarely reach -- a prop that fits
nowhere and goes, a key building that never gives way, two houses allowed
to crowd, a military building moved beside its bridge, a pen that has to be
laid again, a heal whose company is already there or cannot be fetched.

The stand-in keeps the site's interface (`placed`, `add`, `remove`,
`art_of`, `fits`, `ring`, `snap`, ...) and nothing else: painted boxes are
squares of a size per kind, and `fits` / `ring` answer what each test says.
`tests/world/test_village_tidy.py` checks the pass on the generated worlds.
"""
import math
import unittest
from types import SimpleNamespace

import pygame

from world.gen import village_tidy as T
from world.gen.tuning import _V_CLUSTER_MAX, _V_HEAL_COMPANY, _V_HEAL_NEAR

PX = 64
ART = {"forge": 120, "monastery": 120, "house": 100, "barracks": 100, "tower": 80,
       "archery": 90, "tree": 60, "rock": 30, "fence": 20}


class Site:
    def __init__(self, fits=lambda kind, x, y: True, ring_spot=None):
        self.placed = []
        self.boxes = []                 # the protected heal box(es)
        self.art_tol = 6.0
        self.px = PX
        self.forge = (0.0, 0.0)
        self.mouth_dirs = []
        self.pen = None
        self._fits = fits
        self._ring_spot = ring_spot
        self.ring_calls = []

    def add(self, kind, x, y, variant=1, skin=True):
        o = SimpleNamespace(kind=kind, pos=pygame.Vector2(x, y), variant=variant, skin=skin)
        self.placed.append(o)
        return o

    def remove(self, o):
        self.placed.remove(o)

    def art_of(self, o):
        s = ART[o.kind]
        return pygame.Rect(round(o.pos.x - s / 2), round(o.pos.y - s / 2), s, s)

    def art_ok(self, kind, x, y, skip=None):
        s = ART[kind]
        me = pygame.Rect(round(x - s / 2), round(y - s / 2), s, s)
        return not any(T.clips(me, self.art_of(o), self.art_tol)
                       for o in self.placed if o is not skip and o.kind != "fence")

    def fits(self, kind, x, y, lane=True):
        return self._fits(kind, x, y)

    def snap(self, x, y):
        return (math.floor(x / PX) * PX + PX / 2, math.floor(y / PX) * PX + PX / 2)

    def on_axis(self, angle):
        return False

    def ring(self, kind, d_range, a0, spread, ok=None):
        self.ring_calls.append((kind, d_range))
        if self._ring_spot is None:
            return None
        return self._ring_spot if ok is None or ok(*self._ring_spot) else None

    def kinds(self):
        return sorted(o.kind for o in self.placed)


class ClipTests(unittest.TestCase):
    def test_overlap_beyond_the_tolerance_both_ways_is_a_clip(self):
        a = pygame.Rect(0, 0, 100, 100)
        self.assertTrue(T.clips(a, pygame.Rect(90, 90, 100, 100), 6))
        self.assertFalse(T.clips(a, pygame.Rect(95, 0, 100, 100), 6), "5 px one way")
        self.assertFalse(T.clips(a, pygame.Rect(200, 0, 10, 10), 6))


class ProtectedTests(unittest.TestCase):
    def test_a_prop_over_the_heal_goes_and_a_key_building_stays(self):
        site = Site()
        site.boxes = [pygame.Rect(-50, -50, 100, 100)]
        site.add("forge", 0, 0)
        site.add("tree", 10, 10)
        site.add("rock", 400, 400)                    # nowhere near: stays
        site.add("tree", 20, 20, skin=False)          # a collider-only prop: not judged
        report = {"moved": [], "removed": [], "company": 0}
        T._clear_protected(site, [], report)
        self.assertEqual([r[0] for r in report["removed"]], ["tree"])
        self.assertIn("forge", site.kinds())
        self.assertIn("rock", site.kinds())

    def test_a_house_over_the_heal_is_moved_round_the_ring(self):
        site = Site(ring_spot=(300.0, 0.0))
        site.boxes = [pygame.Rect(-50, -50, 100, 100)]
        site.add("house", 0, 30, variant=3)
        report = {"moved": [], "removed": [], "company": 0}
        T._clear_protected(site, [], report)
        self.assertEqual(report["moved"], [("house", 0.0, 30.0, 300.0, 0.0)])
        moved = [o for o in site.placed if o.kind == "house"][0]
        self.assertEqual(moved.variant, 3, "the house keeps its look")
        self.assertEqual(site.ring_calls[0][0], "house")

    def test_a_house_that_fits_nowhere_goes(self):
        site = Site(ring_spot=None)
        site.boxes = [pygame.Rect(-50, -50, 100, 100)]
        site.add("house", 0, 30)
        report = {"moved": [], "removed": [], "company": 0}
        T._clear_protected(site, [], report)
        self.assertEqual(report["removed"], [("house", 0.0, 30.0)])
        self.assertEqual(site.placed, [])


class UnclipTests(unittest.TestCase):
    def test_the_later_building_gives_way_and_a_key_one_never_does(self):
        site = Site(ring_spot=None)                   # nowhere to move to: it goes
        site.add("tower", 30, 0)                      # placed first
        site.add("forge", 0, 0)                       # key, placed later
        report = {"moved": [], "removed": [], "company": 0}
        T._unclip_buildings(site, [], report)
        self.assertEqual(site.kinds(), ["forge"])
        self.assertEqual(report["removed"][0][0], "tower")

    def test_two_houses_may_crowd(self):
        site = Site()
        site.add("house", 0, 0)
        site.add("house", 20, 0)
        report = {"moved": [], "removed": [], "company": 0}
        T._unclip_buildings(site, [], report)
        self.assertEqual(site.kinds(), ["house", "house"])
        self.assertEqual(report, {"moved": [], "removed": [], "company": 0})

    def test_a_military_building_moves_beside_its_bridge(self):
        mouth = (pygame.Vector2(0, 640), pygame.Vector2(0, -1))    # the road runs north
        site = Site()
        site.mouth_dirs = [mouth]
        site.add("forge", 0, 0)
        site.add("barracks", 20, 0)
        report = {"moved": [], "removed": [], "company": 0}
        T._unclip_buildings(site, [mouth], report)
        self.assertEqual(site.kinds(), ["barracks", "forge"])
        kind, *_old, x, y = report["moved"][0]
        self.assertEqual(kind, "barracks")
        self.assertLessEqual(pygame.Vector2(x, y).distance_to(mouth[0]), 8 * PX)


class MilitarySpotTests(unittest.TestCase):
    def test_the_spot_nearest_the_old_one_that_fits(self):
        m, d = pygame.Vector2(0, 0), pygame.Vector2(1, 0)          # road runs east
        site = Site(fits=lambda k, x, y: y > 0)                    # only the south side
        spot = T.military_spot(site, "tower", (400.0, 300.0), [(m, d)])
        self.assertIsNotNone(spot)
        self.assertGreater(spot[1], 0)
        self.assertLessEqual(pygame.Vector2(spot).distance_to(m), 8 * PX)

    def test_none_when_nothing_beside_any_road_fits(self):
        site = Site(fits=lambda k, x, y: False)
        self.assertIsNone(T.military_spot(site, "tower", (0.0, 0.0),
                                          [(pygame.Vector2(), pygame.Vector2(1, 0))]))


class PenTests(unittest.TestCase):
    def test_a_clean_pen_or_no_pen_is_left_alone(self):
        site = Site()
        report = {"moved": [], "removed": [], "company": 0}
        T._repen(site, pygame.Vector2(0, 1), report)                 # no posts at all
        site.add("fence", 500, 500)
        T._repen(site, pygame.Vector2(0, 1), report)                 # posts in the clear
        self.assertEqual(report["moved"], [])
        self.assertEqual(site.kinds(), ["fence"])

    def test_a_post_under_a_building_lays_the_whole_pen_again(self):
        from unittest import mock
        site = Site()
        site.add("house", 0, 0)
        site.add("fence", 10, 10)
        site.add("fence", 600, 600)
        report = {"moved": [], "removed": [], "company": 0}
        with mock.patch("world.gen.village._place_pen", return_value="new pen") as place:
            T._repen(site, pygame.Vector2(0, 1), report)
        place.assert_called_once()
        self.assertEqual(site.kinds(), ["house"], "every post of the old ring came out")
        self.assertEqual(site.pen, "new pen")
        self.assertEqual(report["moved"], [("pen",)])


class HealCompanyTests(unittest.TestCase):
    HEAL = (0.0, 0.0)

    def test_company_already_there_is_counted_and_nothing_moves(self):
        site = Site()
        site.add("house", 2 * PX, 0)
        site.add("tower", -2 * PX, 0)
        site.add("forge", 0, -PX)                      # key: not company
        report = {"moved": [], "removed": [], "company": 0}
        self.assertEqual(T._flank_heal(site, self.HEAL, report), 2)
        self.assertEqual(report["moved"], [])

    def test_a_spare_house_is_pulled_onto_the_flank(self):
        self.assertEqual(_V_HEAL_COMPANY, 2)
        site = Site(fits=lambda k, x, y: True)
        site.add("forge", 0, -PX)
        site.add("house", 2.5 * PX, 0)                 # company already, east
        spare = site.add("house", 0, 5 * PX)           # outside the heal's reach
        report = {"moved": [], "removed": [], "company": 0}
        got = T._flank_heal(site, self.HEAL, report)
        self.assertEqual(got, 2)
        self.assertEqual(len(report["moved"]), 1)
        moved = [o for o in site.placed if o.kind == "house" and o is not spare]
        self.assertTrue(any(o.pos.x < 0 for o in moved), "the emptier (west) side first")

    def test_a_house_that_cannot_move_is_put_back_and_the_count_stays_short(self):
        site = Site(fits=lambda k, x, y: False)
        site.add("house", 0, 8 * PX, variant=2)
        report = {"moved": [], "removed": [], "company": 0}
        self.assertEqual(T._flank_heal(site, self.HEAL, report), 0)
        (house,) = site.placed
        self.assertEqual((house.pos.x, house.pos.y, house.variant), (0, 8 * PX, 2))

    def test_the_flank_spot_stays_inside_the_heal_s_reach(self):
        site = Site()
        spot = T.flank_spot(site, self.HEAL, +1)
        self.assertIsNotNone(spot)
        self.assertGreater(spot[0], 0)
        self.assertLessEqual(pygame.Vector2(spot).length(), _V_HEAL_NEAR * PX)
        self.assertIsNone(T.flank_spot(site, self.HEAL, -1, ok=lambda x, y: False))

    def test_the_cluster_holds_only_while_every_house_has_a_neighbour(self):
        site = Site()
        site.add("forge", 0, 0)
        site.add("house", 2 * PX, 0)
        self.assertTrue(T._cluster_holds(site, (-2 * PX, 0)))
        far = (_V_CLUSTER_MAX + 3) * PX
        self.assertFalse(T._cluster_holds(site, (far, far)))


class TidyTests(unittest.TestCase):
    def test_the_report_carries_every_stage(self):
        site = Site(ring_spot=None)
        site.boxes = [pygame.Rect(-50, -50, 100, 100)]
        site.add("tree", 0, 0)
        report = T.tidy(site, (0.0, 0.0), [], pygame.Vector2(0, 1))
        self.assertEqual(set(report), {"moved", "removed", "company"})
        self.assertEqual(report["removed"], [("tree", 0.0, 0.0)])
        self.assertEqual(report["company"], 0)


if __name__ == "__main__":
    unittest.main()
