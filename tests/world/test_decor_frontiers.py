"""Decoration placement respects terrace frontiers (height-map worlds).

The rules under test are all bake-time and all live on the `config.HEIGHTMAP_ROOMS`
path, so this module pins that flag **on** -- the two older decor suites
(`tests/rendering/test_terrain.py`, `tests/world/test_room_shapes.py`) pin it
off to keep describing the flat LD-8 world, and neither can see a level change.

What is actually at stake: an island's terraces bake into a *single* ground
surface, which is composited before any sprite is drawn. A prop standing below
a terrace therefore paints over that terrace's tiles however the depth layer
sorts it. Sorting cannot fix that; only not standing there can, which is why
these are placement tests rather than render tests.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.content import get_content
from world.map import GameMap
from world import frontier as F

SEEDS = (35, 7, 1234)

_SAVED = None


def setUpModule():
    global _SAVED
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    _SAVED = config.HEIGHTMAP_ROOMS
    config.HEIGHTMAP_ROOMS = True


def tearDownModule():
    config.HEIGHTMAP_ROOMS = _SAVED


_MAPS: dict = {}


def _map(seed: int) -> GameMap:
    if seed not in _MAPS:
        gm = GameMap(seed=seed)
        gm._build_tiles()
        _MAPS[seed] = gm
    return _MAPS[seed]


def _placed(gm):
    """`(room, frames, anchor_x, anchor_y, x, y)` for every grid-room prop."""
    for rid, inst in gm._room_decor.items():
        room = gm.layout.room(rid)
        if not room.grid:
            continue
        for frs, ax, ay, _fps, x, y in inst:
            yield room, frs, ax, ay, x, y


class FrontierTests(unittest.TestCase):
    def setUp(self):
        gm = _map(SEEDS[0])
        self.assertTrue(gm._tiles_ok, "tileset assets absent")

    def test_something_is_still_placed(self):
        # The rules reject placements; they must not starve the scatter. The
        # 6-try budget is only adequate because the eligible area shrinks by
        # about a fifth, not by most of itself.
        for seed in SEEDS:
            total = sum(len(v) for v in _map(seed)._room_decor.values())
            self.assertGreater(total, 150, f"seed {seed} scatter collapsed")

    def test_no_prop_stands_against_a_level_change(self):
        """Every prop's four orthogonal neighbours are floor of its own terrace."""
        for seed in SEEDS:
            gm = _map(seed)
            px = config.TILE_PX
            for room, _frs, _ax, _ay, x, y in _placed(gm):
                col, row = gm.room_cell(room, x, y)
                level = F.cell_level(room, (col, row))
                self.assertIsNotNone(level, "prop off the floor entirely")
                for dc, dr in F.ORTHO:
                    self.assertEqual(
                        F.cell_level(room, (col + dc, row + dr)), level,
                        f"seed {seed} room {room.id}: prop at cell "
                        f"{(col, row)} touches another terrace")

    def test_no_prop_art_reaches_onto_a_higher_terrace(self):
        """The uphill keep-back: nothing within a rig's own north / east / west
        reach may be a terrace above the one it stands on."""
        px = config.TILE_PX
        keepback = float(get_content().terrain["decor_placement"]["uphill_keepback"])
        for seed in SEEDS:
            gm = _map(seed)
            for room, frs, ax, ay, x, y in _placed(gm):
                level = F.tile_level(room, x, y, px)
                east = frs[0].get_width() - ax
                self.assertTrue(
                    F.uphill_clear(room, x, y, level, ay * keepback,
                                    ax * keepback, east * keepback, px),
                    f"seed {seed} room {room.id}: prop art at {(x, y)} "
                    f"reaches onto a higher terrace")

    def test_every_prop_keeps_the_edge_inset_off_a_frontier(self):
        """The sub-tile margin, diagonals included -- what stops a prop reading
        as glued to the boundary line between two tilesets."""
        px = config.TILE_PX
        inset = float(get_content().terrain["decor_placement"]["edge_inset"])
        self.assertGreaterEqual(inset, 5)
        for seed in SEEDS:
            gm = _map(seed)
            for room, _frs, _ax, _ay, x, y in _placed(gm):
                level = F.tile_level(room, x, y, px)
                self.assertTrue(
                    F.frontier_clear(room, x, y, level, inset, px),
                    f"seed {seed} room {room.id}: prop at {(x, y)} sits "
                    f"within {inset}px of a frontier")


class ObstacleKeepBackTests(unittest.TestCase):
    """Trees, rocks and houses come from `world/gen/scatter.py`, a different
    placement path, and carry the same rule. Trees are what it is really for:
    a canopy is 256 px tall and reaches some four tiles north of its trunk."""

    def _home(self, gm, o, px):
        """The grid room an obstacle stands on. Island bounding boxes overlap,
        so membership has to be by cell, not by rect."""
        for r in gm.layout.rooms:
            if (r.grid and r.rect.collidepoint(o.pos.x, o.pos.y)
                    and F.tile_level(r, o.pos.x, o.pos.y, px) is not None):
                return r
        return None

    def test_no_obstacle_art_reaches_onto_a_higher_terrace(self):
        px = config.TILE_PX
        for seed in SEEDS:
            gm = _map(seed)
            checked = 0
            for i, o in enumerate(gm.obstacles):
                entry = gm._decos.get(i)
                if entry is None:
                    continue
                ax, ay, _fps, frs, _phase = entry
                room = self._home(gm, o, px)
                if room is None:
                    continue
                checked += 1
                level = F.tile_level(room, o.pos.x, o.pos.y, px)
                self.assertTrue(
                    F.uphill_clear(room, o.pos.x, o.pos.y, level,
                                   ay, ax, frs[0].get_width() - ax, px),
                    f"seed {seed}: {o.kind} at "
                    f"({o.pos.x:.0f}, {o.pos.y:.0f}) overhangs a terrace")
            self.assertGreater(checked, 100, f"seed {seed} scatter collapsed")

    def test_per_kind_reach_covers_every_rig_a_kind_can_wear(self):
        """The scatter places before `variant` is drawn, so it uses a per-kind
        worst case. That case must actually bound every rig -- including the
        per-biome tree lists, which are chosen from the terrace, not the kind."""
        terrain = get_content().terrain
        reach = F.obstacle_reach(terrain)
        conf = terrain["obstacle_decor"]
        boost = float(conf["size_boost"])
        for kind, names in conf["rigs"].items():
            extra = [r for spec in terrain["biomes"].values()
                     for r in spec.get("trees", []) if kind == "tree"]
            radius = float(conf.get("render_radius", {}).get(
                kind, terrain["obstacles"][kind]["radius"]))
            for rig in list(names) + extra:
                meta = terrain["rigs"][rig]
                fw, fh = meta["frame"]
                ax, ay = meta["anchor"]
                scale = F.rig_scale(meta, radius, boost)
                north, west, east = reach[kind]
                self.assertGreaterEqual(north, ay * scale - 1e-6, f"{kind}/{rig}")
                self.assertGreaterEqual(west, ax * scale - 1e-6, f"{kind}/{rig}")
                self.assertGreaterEqual(east, (fw - ax) * scale - 1e-6,
                                        f"{kind}/{rig}")


class UphillGeometryTests(unittest.TestCase):
    def test_a_wide_box_cannot_straddle_a_narrow_higher_strip(self):
        """Why `uphill_clear` scans the swept tile range instead of sampling
        its rim: a one-tile-wide terrace strip sits between the left and right
        edges of a wide sprite, and rim samples miss it entirely."""
        class _Cell:
            def __init__(self, level):
                self.level = level

        class _Room:
            rect = pygame.Rect(0, 0, 640, 640)
            # a single level-1 column at col 5, level 0 either side
            grid = {(c, r): _Cell(1 if c == 5 else 0)
                    for c in range(10) for r in range(10)}
            cells = frozenset(grid)

        px = 64
        # anchored at col 5's neighbour, art spanning cols 4..6
        x, y = 4 * px + 32, 6 * px + 32
        self.assertFalse(
            F.uphill_clear(_Room(), x, y, 0, north=96, west=64, east=128, px=px))


class DepthLayerTests(unittest.TestCase):
    def test_interior_clutter_is_in_the_depth_sorted_layer(self):
        """Clutter used to be painted flat, straight after the ground and
        before every character, so a scarecrow could never occlude the hero."""
        from systems.camera import Camera
        gm = _map(SEEDS[0])
        cam = Camera(gm.width, gm.height)
        cam.snap_to(gm.center)
        cull = cam.visible_rect().inflate(320, 320)
        want = {round(y) for inst in gm._room_decor.values()
                for *_r, x, y in inst if cull.collidepoint(x, y)}
        got = {round(depth) for depth, _fn in gm.renderer.scenery_drawables(cam)}
        self.assertTrue(want, "no clutter in view -- test proves nothing")
        self.assertTrue(want.issubset(got),
                        "interior clutter is missing from the depth layer")

    def test_no_flat_clutter_painter_survives(self):
        """The unsorted painter is gone; nothing may draw clutter after the
        characters again by calling it."""
        gm = _map(SEEDS[0])
        self.assertFalse(hasattr(gm.renderer, "draw_room_clutter"))


class LegacyPathTests(unittest.TestCase):
    def test_interior_cells_falls_back_to_membership_without_a_grid(self):
        """A legacy room has no levels to compare, and keeps the plain
        `in room.cells` test it always used."""
        class _FakeRoom:
            grid: dict = {}
            cells = frozenset({(c, r) for c in range(4) for r in range(4)})

        got = F.interior_cells(_FakeRoom())
        self.assertEqual(got, [(1, 1), (1, 2), (2, 1), (2, 2)])

    def test_interior_cells_is_none_for_a_room_with_no_cells(self):
        class _Bare:
            grid: dict = {}
            cells = frozenset()

        self.assertIsNone(F.interior_cells(_Bare()))


if __name__ == "__main__":
    unittest.main()
