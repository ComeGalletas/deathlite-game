"""The shape every generated world has: the structural contract of
`WorldLayout` on the shared cached seeds.

These are the invariants `test_procedural.py` used to pin for the flat
generator -- room count, reachability, roles, bounds, tile alignment --
restated for the height-map world, which is the only one now. Determinism
is `test_digest.py`'s job.
"""
import unittest

from game import config
from tests import worlds as W
from world.gen.rooms import _four_connected
from world.procedural import SPECIAL_KINDS


class StructureTests(unittest.TestCase):
    def test_requested_room_count(self):
        for seed in W.SEEDS:
            self.assertEqual(len(W.layout(seed).rooms),
                             config.HEIGHTMAP_ROOM_COUNT, f"seed {seed}")

    def test_every_room_reachable_from_start(self):
        for seed in W.SEEDS:
            self.assertTrue(W.layout(seed).is_connected(), f"seed {seed}")

    def test_start_and_boss_are_distinct_and_boss_is_farthest(self):
        for seed in W.SEEDS:
            w = W.layout(seed)
            self.assertNotEqual(w.start_id, w.boss_id)
            dist = w.bfs_distances(w.start_id)
            self.assertEqual(dist[w.boss_id], max(dist.values()), f"seed {seed}")
            self.assertEqual(w.room(w.start_id).kind, "start")
            self.assertEqual(w.room(w.boss_id).kind, "boss")

    def test_special_rooms_present(self):
        for seed in W.SEEDS:
            kinds = {r.kind for r in W.layout(seed).rooms}
            self.assertTrue(set(SPECIAL_KINDS) & kinds,
                            f"seed {seed}: no special locations placed")

    def test_all_geometry_within_bounds(self):
        for seed in W.SEEDS:
            w = W.layout(seed)
            b = w.bounds
            self.assertEqual((b.x, b.y), (0, 0))
            for r in w.rooms:
                self.assertTrue(b.contains(r.rect), f"seed {seed} room {r.id}")
            for c in w.corridors:
                self.assertTrue(b.contains(c.rect), f"seed {seed} bridge")

    def test_corridors_bridge_their_two_rooms(self):
        for seed in W.SEEDS:
            w = W.layout(seed)
            for c in w.corridors:
                ra, rb = w.room(c.a).rect, w.room(c.b).rect
                self.assertTrue(c.rect.colliderect(ra) and c.rect.colliderect(rb),
                                f"seed {seed}: bridge {c.a}-{c.b} misses a room")


class ValidateTests(unittest.TestCase):
    """`world/gen/validate.py` reads every promise back off a finished world."""

    def test_every_cached_world_is_sound(self):
        from world.gen.validate import validate
        for seed in W.SEEDS:
            self.assertEqual(validate(W.layout(seed)), [], f"seed {seed}")

    def test_it_notices_a_broken_promise(self):
        from world.gen.validate import validate
        gm = W.fresh(W.SEEDS[0])
        gm.layout.rooms[0].rect.x += 3                # off the lattice
        gm.layout.obstacles[0].pos.x = -500.0         # into the sea
        bad = validate(gm.layout)
        self.assertTrue(any("off the tile lattice" in b for b in bad), bad)
        self.assertTrue(any("off the floor" in b for b in bad), bad)


class SettingsTests(unittest.TestCase):
    """A world is generated under one `GenSettings` throughout, and a test
    can hand one in instead of mutating `game.config`."""

    def test_a_settings_override_replaces_the_global_mutation(self):
        from world.gen.settings import GenSettings
        from world.procedural import generate_world
        seed = W.SEEDS[0]
        by_flag = W.layout(seed, HEIGHTMAP_UNSEAL=False)
        by_settings = generate_world(
            seed, settings=GenSettings.from_config(unseal=False))
        self.assertEqual([(o.kind, tuple(o.pos)) for o in by_flag.obstacles],
                         [(o.kind, tuple(o.pos)) for o in by_settings.obstacles])

    def test_unknown_settings_are_refused(self):
        from world.gen.settings import GenSettings
        with self.assertRaises(TypeError):
            GenSettings.from_config(HEIGHTMAP_UNSEAL=False)


class GridAlignmentTests(unittest.TestCase):
    """Room rects sit on the world tile lattice and are tile-sized, so a
    room-relative `(col, row)` maps to one absolute tile (`LevelIndex`
    depends on it) and a bridge lands square on a tile at both ends."""

    def test_room_rects_are_tile_aligned_and_tile_sized(self):
        px = config.TILE_PX
        for seed in W.SEEDS:
            for r in W.layout(seed).rooms:
                self.assertEqual((r.rect.x % px, r.rect.y % px), (0, 0),
                                 f"seed {seed} room {r.id} off the lattice")
                self.assertEqual((r.rect.width % px, r.rect.height % px), (0, 0),
                                 f"seed {seed} room {r.id}")

    def test_corridors_are_one_tile_wide(self):
        px = config.TILE_PX
        for seed in W.SEEDS:
            for c in W.layout(seed).corridors:
                self.assertEqual(min(c.rect.width, c.rect.height), px,
                                 f"seed {seed}")


class FloorMaskTests(unittest.TestCase):
    """`Room.cells` is the walkable subset of the height map: inside the
    rect, one piece, and the room's centre stands on it."""

    def test_every_cell_is_inside_the_rect_and_walkable_in_the_grid(self):
        from world.layout import WALKABLE_KINDS
        for seed in W.SEEDS:
            for r in W.layout(seed).rooms:
                w, h = r.tile_dims
                self.assertTrue(r.cells, f"seed {seed} room {r.id}: empty")
                for c in r.cells:
                    self.assertTrue(0 <= c[0] < w and 0 <= c[1] < h)
                    self.assertIn(r.grid[c].kind, WALKABLE_KINDS)

    def test_the_floor_is_one_piece(self):
        for seed in W.SEEDS:
            for r in W.layout(seed).rooms:
                self.assertTrue(_four_connected(set(r.cells)),
                                f"seed {seed} room {r.id} is in pieces")

    def test_room_centre_is_an_occupied_cell(self):
        px = config.TILE_PX
        for seed in W.SEEDS:
            for r in W.layout(seed).rooms:
                c = r.center
                cell = (int((c.x - r.rect.left) // px),
                        int((c.y - r.rect.top) // px))
                self.assertIn(cell, r.cells,
                              f"seed {seed} room {r.id} centre in the void")

    def test_random_point_in_room_always_lands_on_the_floor(self):
        import random
        rng = random.Random(1)
        for seed in W.SEEDS:
            gm = W.game_map(seed)
            for r in gm.layout.rooms:
                for _ in range(40):
                    p = gm.random_point_in_room(r, rng)
                    self.assertTrue(gm._point_ok(p.x, p.y),
                                    f"seed {seed} room {r.id}: {p} is off the floor")


if __name__ == "__main__":
    unittest.main()
