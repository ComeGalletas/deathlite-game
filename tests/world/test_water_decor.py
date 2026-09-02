"""Water scenery: the open sea, the shoreline ring and the inland lakes.

The three passes in `world/terrain/decor/scatter_water.py` all feed `_void_decor`, and
all three only exist on the height-map world, so this module pins that flag on.

The bug most of this suite is about: the sea scatter used to stop after 240
instances while scanning north to south, which made the cap a *horizon* rather
than a density limit -- on a 19,136 x 7,680 world it ran out a quarter of the
way down and every island below the first row sat in an empty sea.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.content import get_content
from world.layout import GROUND, CLIFF, VSTAIR, EWSTAIR
from world.map import GameMap
from world.terrain.decor import scatter_water as W

SEEDS = (35, 7, 1234)
_SAVED = None
_MAPS: dict = {}


def setUpModule():
    global _SAVED
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    _SAVED = config.HEIGHTMAP_ROOMS
    config.HEIGHTMAP_ROOMS = True


def tearDownModule():
    config.HEIGHTMAP_ROOMS = _SAVED


def _map(seed: int) -> GameMap:
    if seed not in _MAPS:
        gm = GameMap(seed=seed)
        gm._build_tiles()
        _MAPS[seed] = gm
    return _MAPS[seed]


def _blobs(cells):
    """Connected components of a cell set -- one pond, not every pond on the
    island lumped together."""
    todo, out = set(cells), []
    while todo:
        start = todo.pop()
        comp, stack = {start}, [start]
        while stack:
            c = stack.pop()
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (c[0] + d[0], c[1] + d[1])
                if q in todo:
                    todo.discard(q)
                    comp.add(q)
                    stack.append(q)
        out.append(comp)
    return out


def _tile_of(room, x, y):
    px = config.TILE_PX
    return (int((x - room.rect.x) // px), int((y - room.rect.y) // px))


class CoverageTests(unittest.TestCase):
    def test_scenery_reaches_every_band_of_the_world(self):
        """The regression for the 240-instance horizon. Ten horizontal bands,
        and effectively all of them populated -- not just the northern quarter."""
        for seed in SEEDS:
            gm = _map(seed)
            b = gm.layout.bounds
            bands = {int((y - b.y) / b.height * 10)
                     for _f, _ax, _ay, _fps, _x, y in gm._void_decor}
            self.assertGreaterEqual(
                len(bands), 9,
                f"seed {seed}: water scenery only reaches bands {sorted(bands)}")

    def test_the_southern_half_is_not_empty(self):
        for seed in SEEDS:
            gm = _map(seed)
            mid = gm.layout.bounds.centery
            south = sum(1 for i in gm._void_decor if i[5] > mid)
            self.assertGreater(south, 50,
                               f"seed {seed}: only {south} props south of centre")


class LakeTests(unittest.TestCase):
    def test_lake_cells_are_found_at_all(self):
        found = sum(len(W._lake_cells(r))
                    for seed in SEEDS for r in _map(seed).layout.rooms)
        self.assertGreater(found, 50, "no inland water in any sample world")

    def test_most_ponds_get_scenery(self):
        """Per pond, not per island: an island can hold several, and averaging
        their centres lands on the grass between them."""
        total = with_props = 0
        for seed in SEEDS:
            gm = _map(seed)
            for room in gm.layout.rooms:
                tiles = {_tile_of(room, i[4], i[5]) for i in gm._void_decor}
                for comp in _blobs(W._lake_cells(room)):
                    total += 1
                    if tiles & comp:
                        with_props += 1
        self.assertGreater(total, 5, "too few ponds to draw a conclusion")
        # Not all of them: a three-tile pond legitimately rolls empty sometimes.
        self.assertGreater(with_props / total, 0.6,
                           f"only {with_props}/{total} ponds have scenery")


class PlacementTests(unittest.TestCase):
    def test_no_water_prop_stands_on_land(self):
        """Neither on a walkable point nor on any *painted* tile -- island
        bounding boxes overlap, so a tile absent from one room's grid can be
        ground in another's."""
        for seed in SEEDS:
            gm = _map(seed)
            for _f, _ax, _ay, _fps, x, y in gm._void_decor:
                self.assertFalse(gm._point_ok(x, y),
                                 f"seed {seed}: water prop on walkable ground")
                for r in gm.layout.rooms:
                    if not r.grid or not r.rect.collidepoint(x, y):
                        continue
                    c = r.grid.get(_tile_of(r, x, y))
                    if c is not None:
                        self.assertNotIn(
                            c.kind, (GROUND, CLIFF, VSTAIR, EWSTAIR),
                            f"seed {seed}: water prop on a {c.kind} tile")

    def test_every_placement_kind_actually_places_something(self):
        """A registry entry nobody reaches is the failure mode this whole
        change was about -- deco_16..deco_18 sat unreachable for months."""
        gm = _map(SEEDS[0])
        lake_tiles = {(r.id, p) for r in gm.layout.rooms for p in W._lake_cells(r)}
        ring_tiles = {(r.id, p) for r in gm.layout.rooms for p in W._water_ring(r)}
        in_lake = in_ring = 0
        for _f, _ax, _ay, _fps, x, y in gm._void_decor:
            for r in gm.layout.rooms:
                if not r.grid or not r.rect.collidepoint(x, y):
                    continue
                key = (r.id, _tile_of(r, x, y))
                if key in lake_tiles:
                    in_lake += 1
                elif key in ring_tiles:
                    in_ring += 1
        self.assertGreater(in_lake, 0, "the lake pass placed nothing")
        self.assertGreater(in_ring, 0, "the shore pass placed nothing")
        self.assertGreater(len(gm._void_decor), in_lake + in_ring,
                           "the open-sea pass placed nothing")

    def test_is_deterministic_per_seed(self):
        a, b = GameMap(seed=99), GameMap(seed=99)
        a._build_tiles()
        b._build_tiles()
        self.assertEqual([i[4:] for i in a._void_decor],
                         [i[4:] for i in b._void_decor])

    def test_stays_under_the_area_derived_ceiling(self):
        for seed in SEEDS:
            gm = _map(seed)
            b = gm.layout.bounds
            cap = max(240, int(W._MAX_PER_MP * b.width * b.height / 1_000_000))
            self.assertLessEqual(len(gm._void_decor), cap)


class RegistryTests(unittest.TestCase):
    def test_every_water_entry_resolves_to_real_frames(self):
        gm = _map(SEEDS[0])
        self.assertTrue(gm._void_decor)
        for frs, _ax, _ay, fps, _x, _y in gm._void_decor:
            self.assertTrue(frs and all(isinstance(f, pygame.Surface) for f in frs))
            self.assertGreaterEqual(fps, 0.0)

    def test_no_cloud_rig_is_left_unused(self):
        """All eight cloud rigs are authored now; four used to be declared and
        never reached by any entry."""
        terrain = get_content().terrain
        declared = {r for r in terrain["rigs"] if r.startswith("deco_cloud_")}
        used = {e["rig"] for e in terrain["decorations"]}
        self.assertEqual(declared - used, set())


if __name__ == "__main__":
    unittest.main()
