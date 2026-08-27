"""Milestone 8: procedural world generation (spec 5.2 / 5.4 / 8:
"Procedural generation determinism")."""
import unittest

from world.procedural import SPECIAL_KINDS, generate_world


class DeterminismTests(unittest.TestCase):
    def test_same_seed_same_layout(self):
        a = generate_world(1234)
        b = generate_world(1234)
        self.assertEqual([(r.id, tuple(r.rect), r.kind, tuple(sorted(r.neighbors)))
                          for r in a.rooms],
                         [(r.id, tuple(r.rect), r.kind, tuple(sorted(r.neighbors)))
                          for r in b.rooms])
        self.assertEqual([(c.a, c.b, tuple(c.rect)) for c in a.corridors],
                         [(c.a, c.b, tuple(c.rect)) for c in b.corridors])

    def test_different_seeds_differ(self):
        shapes = {tuple(tuple(r.rect) for r in generate_world(s).rooms)
                  for s in range(20)}
        self.assertGreater(len(shapes), 1)


class StructureTests(unittest.TestCase):
    def setUp(self):
        self.w = generate_world(99)

    def test_requested_room_count(self):
        from game import config
        self.assertEqual(len(self.w.rooms), config.WORLD_ROOM_COUNT)

    def test_every_room_reachable_from_start(self):
        self.assertTrue(self.w.is_connected(),
                        "a critical room is unreachable (spec 5.4)")

    def test_start_and_boss_are_distinct_and_boss_is_farthest(self):
        self.assertNotEqual(self.w.start_id, self.w.boss_id)
        dist = self.w.bfs_distances(self.w.start_id)
        self.assertEqual(dist[self.w.boss_id], max(dist.values()))
        self.assertEqual(self.w.room(self.w.start_id).kind, "start")
        self.assertEqual(self.w.room(self.w.boss_id).kind, "boss")

    def test_special_rooms_present(self):
        kinds = {r.kind for r in self.w.rooms}
        self.assertTrue(set(SPECIAL_KINDS) & kinds, "no special locations placed")

    def test_all_geometry_within_bounds_and_nonoverlapping(self):
        b = self.w.bounds
        self.assertEqual((b.x, b.y), (0, 0))
        for r in self.w.rooms:
            self.assertTrue(b.contains(r.rect))
        for i, r in enumerate(self.w.rooms):
            for other in self.w.rooms[i + 1:]:
                self.assertFalse(r.rect.colliderect(other.rect),
                                 "room floors overlap")

    def test_corridors_bridge_their_two_rooms(self):
        for c in self.w.corridors:
            ra = self.w.room(c.a).rect
            rb = self.w.room(c.b).rect
            self.assertTrue(c.rect.colliderect(ra) and c.rect.colliderect(rb))


class GridAlignmentTests(unittest.TestCase):
    """T7: room rects and corridor widths snap to config.TILE_PX so the tiled
    renderer covers each cell exactly."""

    def test_room_dims_are_tile_multiples(self):
        from game import config
        for seed in (1, 7, 99, 1234):
            for r in generate_world(seed).rooms:
                self.assertEqual(r.rect.width % config.TILE_PX, 0, f"seed {seed}")
                self.assertEqual(r.rect.height % config.TILE_PX, 0, f"seed {seed}")
                self.assertGreaterEqual(min(r.rect.width, r.rect.height),
                                        3 * config.TILE_PX)

    def test_corridors_are_one_tile_wide(self):
        from game import config
        for seed in (1, 7, 99, 1234):
            for c in generate_world(seed).corridors:
                self.assertEqual(min(c.rect.width, c.rect.height), config.TILE_PX)

    def test_snapped_layout_still_connected_and_non_overlapping(self):
        w = generate_world(2024)
        self.assertTrue(w.is_connected())
        for i, r in enumerate(w.rooms):
            for other in w.rooms[i + 1:]:
                self.assertFalse(r.rect.colliderect(other.rect))


if __name__ == "__main__":
    unittest.main()
