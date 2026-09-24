"""`world/gen/validate.py` on a hand-built two-island world: sound as built,
and each promise broken on its own names itself.

The generated-world side -- every cached world validates clean, and a
corrupted one is caught -- is `tests/world/test_layout.py::ValidateTests`.
Generated worlds never break most of these promises, so only a world drawn
by hand reaches the sentences that report them.
"""
import copy
import unittest
from types import SimpleNamespace

import pygame

from game import config
from world.gen.validate import validate
from world.layout import (CLIFF, GROUND, VSTAIR, Cell, Corridor, ResourcePoint,
                          Room, SpawnPoint, WorldLayout)

PX = config.TILE_PX


def _island(rid, col0, levels=(0,)):
    """A 4 x 4 island at tile column `col0`: ground on every cell, or with a
    raised terrace on its top-left 2 x 2 held up by a cliff row when
    `levels` has two entries."""
    grid = {(c, r): Cell(GROUND, level=0) for c in range(4) for r in range(4)}
    if len(levels) > 1:
        for c in range(2):
            grid[(c, 0)] = Cell(GROUND, level=1)
            grid[(c, 1)] = Cell(CLIFF, level=1, drop=1, row=0)
    cells = frozenset(p for p, c in grid.items() if c.kind == GROUND)
    room = Room(id=rid, cell=(rid, 0), rect=pygame.Rect(col0 * PX, 0, 4 * PX, 4 * PX),
                kind="combat", neighbors=[1 - rid], grid=grid, cells=cells,
                tile_meta={p: None for p in cells}, topography="small",
                palette={lv: "sheet" for lv in levels})
    return room


def _world():
    a, b = _island(0, 0), _island(1, 6)
    bridge = Corridor(a=0, b=1, rect=pygame.Rect(2 * PX, PX, 6 * PX, PX))
    lay = WorldLayout(seed=0, rooms=[a, b], corridors=[bridge],
                      bounds=pygame.Rect(0, 0, 10 * PX, 4 * PX), start_id=0, boss_id=1)
    centre = (0.5 + 2) * PX
    lay.spawn_points = [SpawnPoint(room_id=0, floor=0, x=centre, y=centre)]
    lay.resource_points = [ResourcePoint(room_id=1, floor=0, x=6 * PX + centre, y=centre)]
    lay.obstacles = [SimpleNamespace(kind="rock", pos=pygame.Vector2(centre, centre))]
    return lay


def _says(test, lay, phrase):
    bad = validate(lay)
    test.assertTrue(any(phrase in b for b in bad), f"{phrase!r} not in {bad}")


class SoundWorldTests(unittest.TestCase):
    def test_the_hand_built_world_is_sound(self):
        self.assertEqual(validate(_world()), [])


class RoomPromiseTests(unittest.TestCase):
    def test_a_rect_off_the_lattice_or_not_tile_sized(self):
        lay = _world()
        lay.rooms[0].rect.x += 3
        _says(self, lay, "off the tile lattice")
        lay = _world()
        lay.rooms[0].rect.width += 5
        _says(self, lay, "is not tile-sized")

    def test_an_island_with_no_height_map(self):
        lay = _world()
        lay.rooms[1].grid = {}
        _says(self, lay, "island 1: no height map")

    def test_cells_that_are_not_the_walkable_grid(self):
        lay = _world()
        lay.rooms[0].cells = lay.rooms[0].cells - {(0, 0)}
        _says(self, lay, "`cells` is not the walkable subset")

    def test_grid_cells_outside_the_rect(self):
        lay = _world()
        lay.rooms[0].grid[(9, 9)] = Cell(CLIFF, level=1, drop=1)
        _says(self, lay, "grid cells outside the rect")

    def test_the_grid_rules_are_read_through(self):
        """`check_grid`'s complaints come back prefixed with the island."""
        lay = _world()
        lay.rooms[0].grid[(3, 3)] = Cell(GROUND, level=1)     # a stranded terrace
        lay.rooms[0].palette[1] = "sheet"
        bad = [b for b in validate(lay) if b.startswith("island 0: ")]
        self.assertTrue(bad, "check_grid found nothing to say")

    def test_no_topography(self):
        lay = _world()
        lay.rooms[1].topography = ""
        _says(self, lay, "island 1: no topography")

    def test_a_terrace_without_a_palette_sheet(self):
        lay = _world()
        lay.rooms[0].palette = {}
        _says(self, lay, "have no palette sheet")

    def test_tile_meta_that_does_not_cover_the_floor(self):
        lay = _world()
        lay.rooms[0].tile_meta.pop((1, 1))
        _says(self, lay, "tile meta does not cover exactly the floor")

    def test_terraces_without_an_inset_field(self):
        lay = _world()
        room = _island(0, 0, levels=(0, 1))
        lay.rooms[0] = room
        bad = validate(lay)
        self.assertIn("island 0: terraces but no inset field", bad)
        room.inset = object()
        self.assertNotIn("island 0: terraces but no inset field", validate(lay))


class WorldPromiseTests(unittest.TestCase):
    def test_a_bridge_that_misses_an_island_or_is_not_one_tile_wide(self):
        lay = _world()
        lay.corridors[0].rect = pygame.Rect(2 * PX, PX, 2 * PX, PX)
        _says(self, lay, "bridge 0-1 does not reach both islands")
        lay = _world()
        lay.corridors[0].rect.height = 2 * PX
        _says(self, lay, "bridge 0-1 is not one tile wide")

    def test_an_unreachable_island(self):
        lay = _world()
        for r in lay.rooms:
            r.neighbors = []
        _says(self, lay, "an island is unreachable from the start")

    def test_bounds_off_the_origin(self):
        lay = _world()
        lay.bounds.x = PX
        _says(self, lay, "not the origin")

    def test_an_obstacle_off_the_floor(self):
        lay = _world()
        lay.obstacles[0].pos.update(5 * PX, 3.5 * PX)          # the sea between
        _says(self, lay, "obstacle 0 (rock) stands off the floor")

    def test_points_off_their_island_off_plain_ground_or_on_the_wrong_floor(self):
        lay = _world()
        p = lay.spawn_points[0]
        lay.spawn_points = [p._replace(room_id=1)]
        _says(self, lay, "spawn point 0 is not on island 1's floor")

        lay = _world()
        lay.rooms[0].grid[(2, 2)] = Cell(VSTAIR, level=1, drop=1)  # floor, not ground
        _says(self, lay, "spawn point 0 is not on plain ground")

        lay = _world()
        lay.resource_points = [lay.resource_points[0]._replace(floor=1)]
        _says(self, lay, "resource point 0 says floor 1, stands on 0")

    def test_every_broken_promise_is_listed_not_just_the_first(self):
        lay = copy.deepcopy(_world())
        lay.rooms[1].topography = ""
        lay.bounds.x = PX
        self.assertGreaterEqual(len(validate(lay)), 2)


if __name__ == "__main__":
    unittest.main()
