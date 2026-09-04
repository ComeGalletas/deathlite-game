"""Spawn points and resource anchors are decided at generation (spawn
master S1, `documentation/spawn_master_design.md`).

What is pinned: every point passes the geometry it was promised to pass,
read back through the same helpers the scatter and the collider use rather
than through the stage's own code; the per-floor count follows the
`SPAWN_POINTS_PER_FLOOR` knob; the stage draws nothing from the world's RNG
(the islands, bridges and obstacles digest the same with a different count);
and the validator notices a point that has gone astray.
"""
import hashlib
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config
from spawn import PointIndex
from tests import worlds as W
from world import digest
from world.gen.scatter import _blocks, _corridor_doorways, _flight_keepouts
from world.gen.spawnpoints import body_radii
from world.gen.tuning import (_GRID_BOSS_CLEAR_RADIUS, _RESOURCE_KINDS,
                              _RESOURCE_OFF_SPAWN_TILES,
                              _RESOURCE_POINTS_PER_ISLAND,
                              _SPAWN_MIN_SPACING_TILES, _SPAWN_OBSTACLE_GAP,
                              _SPAWN_START_CLEAR_TILES)
from world.gen.validate import validate
from world.layout import GROUND
from world.rules import inset as terrain_inset

PX = config.TILE_PX
SMALL, LARGE = body_radii()


def _cell(room, p):
    return room.grid.get((int((p.x - room.rect.x) // PX),
                          int((p.y - room.rect.y) // PX)))


def _radius(p) -> float:
    return LARGE if p.clearance == "large" else SMALL


def _geometry_digest(layout) -> str:
    """Everything the stage must not move: islands, bridges, obstacles."""
    h = hashlib.sha256()
    digest._feed(h, (layout.rooms, layout.corridors, layout.obstacles,
                     layout.bounds, layout.start_id, layout.boss_id))
    return h.hexdigest()


class SpawnPointGeometryTests(unittest.TestCase):
    def _each(self):
        for seed in W.SEEDS:
            lay = W.layout(seed)
            for p in lay.spawn_points:
                yield seed, lay, lay.room(p.room_id), p

    def test_every_point_is_on_plain_ground_of_its_floor(self):
        for seed, lay, room, p in self._each():
            cell = _cell(room, p)
            self.assertIsNotNone(cell, f"seed {seed}: {p} off the island")
            self.assertEqual(cell.kind, GROUND, f"seed {seed}: {p} not on ground")
            self.assertEqual(cell.level, p.floor, f"seed {seed}: {p} floor")

    def test_every_point_keeps_the_terrace_margin_for_its_class(self):
        body = terrain_inset.body_inset()
        for seed, lay, room, p in self._each():
            margin = LARGE + body if p.clearance == "large" else body
            self.assertTrue(terrain_inset.world_clear(room, p.x, p.y, margin),
                            f"seed {seed}: {p} straddles a rim")

    def test_no_obstacle_reaches_a_point(self):
        for seed, lay, room, p in self._each():
            r = _radius(p)
            for o in lay.obstacles:
                reach = r + float(o.radius) + _SPAWN_OBSTACLE_GAP
                self.assertGreaterEqual(
                    (p.x - o.pos.x) ** 2 + (p.y - o.pos.y) ** 2, reach * reach,
                    f"seed {seed}: {p} on a {o.kind}")

    def test_points_stay_off_bridge_mouths_and_flights(self):
        for seed in W.SEEDS:
            lay = W.layout(seed)
            doors = [d for slabs in _corridor_doorways(lay.rooms, lay.corridors).values()
                     for d in slabs]
            keepouts = _flight_keepouts(lay.rooms)
            for p in lay.spawn_points:
                self.assertFalse(_blocks(doors, p.x, p.y, _radius(p)),
                                 f"seed {seed}: {p} in a bridge mouth")
                self.assertFalse(any(k.collidepoint(p.x, p.y) for k in keepouts),
                                 f"seed {seed}: {p} on a flight")

    def test_the_widest_body_can_stand_on_a_large_point(self):
        for seed in W.SEEDS:
            grid = W.nav(seed).grids["large"]
            for p in W.layout(seed).spawn_points:
                if p.clearance == "large":
                    self.assertTrue(grid.passable_world(p.x, p.y, LARGE),
                                    f"seed {seed}: {p} not passable")

    def test_points_on_one_floor_keep_their_spacing(self):
        gap_sq = (_SPAWN_MIN_SPACING_TILES * PX) ** 2
        for seed in W.SEEDS:
            idx = PointIndex(W.layout(seed))
            for key, pts in idx.by_floor.items():
                for i, a in enumerate(pts):
                    for b in pts[i + 1:]:
                        self.assertGreaterEqual(
                            (a.x - b.x) ** 2 + (a.y - b.y) ** 2, gap_sq,
                            f"seed {seed}: {key} has two points too close")

    def test_the_start_island_keeps_the_hero_calm(self):
        keep_sq = (_SPAWN_START_CLEAR_TILES * PX) ** 2
        for seed in W.SEEDS:
            lay = W.layout(seed)
            c = lay.room(lay.start_id).center
            for p in PointIndex(lay).by_room.get(lay.start_id, ()):
                self.assertGreaterEqual((p.x - c.x) ** 2 + (p.y - c.y) ** 2, keep_sq)

    def test_the_boss_island_is_tagged_and_keeps_its_arena(self):
        for seed in W.SEEDS:
            lay = W.layout(seed)
            boss = lay.room(lay.boss_id)
            for p in lay.spawn_points:
                self.assertEqual("boss" in p.tags, p.room_id == lay.boss_id,
                                 f"seed {seed}: {p}")
                if p.room_id == lay.boss_id:
                    for cx, cy in ((boss.center.x, boss.center.y),
                                   (boss.rect.centerx, boss.rect.centery)):
                        self.assertGreaterEqual(
                            (p.x - cx) ** 2 + (p.y - cy) ** 2,
                            _GRID_BOSS_CLEAR_RADIUS ** 2, f"seed {seed}: {p} in the arena")

    def test_upper_tag_means_above_sea_level(self):
        for seed, lay, room, p in self._each():
            self.assertEqual("upper" in p.tags, p.floor > 0, f"seed {seed}: {p}")


class SpawnPointCountTests(unittest.TestCase):
    def test_no_floor_exceeds_the_knob_and_the_shore_terrace_meets_it(self):
        target = config.SPAWN_POINTS_PER_FLOOR
        for seed in W.SEEDS:
            idx = PointIndex(W.layout(seed))
            for (rid, floor), pts in idx.by_floor.items():
                self.assertLessEqual(len(pts), target, f"seed {seed}: island {rid} floor {floor}")
            for room in W.layout(seed).rooms:
                self.assertEqual(len(idx.by_floor.get((room.id, 0), ())), target,
                                 f"seed {seed}: island {room.id} shore terrace short")

    def test_every_island_and_terrace_has_points(self):
        for seed in W.SEEDS:
            lay = W.layout(seed)
            idx = PointIndex(lay)
            for room in lay.rooms:
                levels = {c.level for c in room.grid.values() if c.kind == GROUND}
                for level in levels:
                    self.assertTrue(idx.by_floor.get((room.id, level)),
                                    f"seed {seed}: island {room.id} floor {level} empty")

    def test_the_knob_changes_the_count_and_nothing_else(self):
        """A different count per floor leaves every island, bridge and
        obstacle where it was: the stage draws nothing from the world's
        RNG."""
        seed = W.SEEDS[0]
        base = W.layout(seed)
        fewer = W.layout(seed, SPAWN_POINTS_PER_FLOOR=4)
        self.assertEqual(_geometry_digest(base), _geometry_digest(fewer))
        self.assertNotEqual(digest.layout_digest(base), digest.layout_digest(fewer))
        for pts in PointIndex(fewer).by_floor.values():
            self.assertLessEqual(len(pts), 4)
        self.assertLess(len(fewer.spawn_points), len(base.spawn_points))

    def test_generation_is_deterministic(self):
        seed = W.SEEDS[1]
        self.assertEqual(W.layout(seed).spawn_points, W.fresh(seed).layout.spawn_points)
        self.assertEqual(W.layout(seed).resource_points,
                         W.fresh(seed).layout.resource_points)


class ResourcePointTests(unittest.TestCase):
    def test_anchors_stand_on_ground_off_the_spawn_points(self):
        off_sq = (_RESOURCE_OFF_SPAWN_TILES * PX) ** 2
        for seed in W.SEEDS:
            lay = W.layout(seed)
            idx = PointIndex(lay)
            for rid, pts in idx.resource_by_room.items():
                self.assertLessEqual(len(pts), _RESOURCE_POINTS_PER_ISLAND)
                self.assertTrue(pts, f"seed {seed}: island {rid} has no anchors")
                for p in pts:
                    cell = _cell(lay.room(rid), p)
                    self.assertIsNotNone(cell)
                    self.assertEqual(cell.kind, GROUND)
                    self.assertEqual(cell.level, p.floor)
                    self.assertIn(p.kind, _RESOURCE_KINDS)
                    for s in idx.by_room.get(rid, ()):
                        self.assertGreaterEqual((p.x - s.x) ** 2 + (p.y - s.y) ** 2, off_sq,
                                                f"seed {seed}: anchor on a spawn pad")


class IndexAndValidatorTests(unittest.TestCase):
    def test_the_index_groups_by_island_and_floor(self):
        lay = W.layout(W.SEEDS[0])
        idx = PointIndex(lay)
        self.assertEqual(len(idx), len(lay.spawn_points))
        self.assertEqual(sum(len(v) for v in idx.by_room.values()), len(idx))
        self.assertEqual(sum(len(v) for v in idx.by_floor.values()), len(idx))
        self.assertEqual(idx.rooms(), sorted(r.id for r in lay.rooms))
        two = idx.in_rooms([lay.start_id, lay.boss_id])
        self.assertEqual({p.room_id for p in two}, {lay.start_id, lay.boss_id})

    def test_the_validator_notices_a_stray_point(self):
        gm = W.fresh(W.SEEDS[0])
        lay = gm.layout
        self.assertEqual(validate(lay), [])
        lay.spawn_points[0] = lay.spawn_points[0]._replace(x=-500.0)
        lay.resource_points[0] = lay.resource_points[0]._replace(floor=99)
        bad = validate(lay)
        self.assertTrue(any("spawn point 0" in b for b in bad), bad)
        self.assertTrue(any("resource point 0" in b and "floor 99" in b for b in bad), bad)


if __name__ == "__main__":
    unittest.main()
