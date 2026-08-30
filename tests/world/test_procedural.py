"""Milestone 8: procedural world generation (spec 5.2 / 5.4 / 8:
"Procedural generation determinism")."""
import unittest

from world.procedural import SPECIAL_KINDS, _four_connected, generate_world


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

    def test_corridor_lanes_vary_and_fit_the_shared_room_edge(self):
        from game import config
        non_centre_lane = False
        for seed in (1, 7, 42, 99, 1234):
            world = generate_world(seed)
            for c in world.corridors:
                first, second = world.room(c.a).rect, world.room(c.b).rect
                if c.axis == "h":
                    lo, hi = max(first.top, second.top), min(first.bottom, second.bottom)
                    self.assertTrue(lo <= c.lane - config.TILE_PX // 2)
                    self.assertTrue(c.lane + config.TILE_PX // 2 <= hi)
                    non_centre_lane |= c.lane != first.centery
                else:
                    lo, hi = max(first.left, second.left), min(first.right, second.right)
                    self.assertTrue(lo <= c.lane - config.TILE_PX // 2)
                    self.assertTrue(c.lane + config.TILE_PX // 2 <= hi)
                    non_centre_lane |= c.lane != first.centerx
        self.assertTrue(non_centre_lane, "all corridors still use room-centre lanes")

    def test_snapped_layout_still_connected_and_non_overlapping(self):
        w = generate_world(2024)
        self.assertTrue(w.is_connected())
        for i, r in enumerate(w.rooms):
            for other in w.rooms[i + 1:]:
                self.assertFalse(r.rect.colliderect(other.rect))


class IrregularRoomTests(unittest.TestCase):
    """W1: rooms carry a tile-cell mask (`Room.cells`); combat rooms get 2-3-cell
    corner bites, `start` / `boss` stay rectangular. Renderer + walkability still
    read the bounding rect at this milestone."""

    SEEDS = (1, 7, 42, 99, 1234, 2024)

    def _rooms(self, seed):
        return generate_world(seed).rooms

    def test_every_room_has_a_valid_cell_mask(self):
        from game import config
        for seed in self.SEEDS:
            for r in self._rooms(seed):
                w, h = r.tile_dims
                self.assertTrue(r.cells, f"seed {seed} room {r.id} empty mask")
                self.assertTrue(all(0 <= c[0] < w and 0 <= c[1] < h for c in r.cells))
                self.assertTrue(_four_connected(set(r.cells)))
                self.assertGreaterEqual(len(r.cells), 9)
                self.assertLessEqual(len(r.cells), config.ROOM_SIZE_MAX_CELLS)

    def test_bounding_box_matches_the_mask(self):
        for seed in self.SEEDS:
            for r in self._rooms(seed):
                w, h = r.tile_dims
                self.assertEqual(max(c[0] for c in r.cells), w - 1)
                self.assertEqual(max(c[1] for c in r.cells), h - 1)
                self.assertEqual(min(c[0] for c in r.cells), 0)
                self.assertEqual(min(c[1] for c in r.cells), 0)

    def test_start_and_boss_stay_rectangular(self):
        for seed in self.SEEDS:
            w = generate_world(seed)
            for rid in (w.start_id, w.boss_id):
                r = w.room(rid)
                cw, ch = r.tile_dims
                self.assertEqual(len(r.cells), cw * ch)

    def test_room_centre_is_an_occupied_cell(self):
        from game import config
        px = config.TILE_PX
        for seed in self.SEEDS:
            for r in self._rooms(seed):
                c = r.center
                col = int((c.x - r.rect.left) // px)
                row = int((c.y - r.rect.top) // px)
                self.assertIn((col, row), r.cells,
                              f"seed {seed} room {r.id} centre in the void")

    def test_some_rooms_are_actually_shaped(self):
        shaped = 0
        for seed in self.SEEDS:
            for r in self._rooms(seed):
                w, h = r.tile_dims
                if len(r.cells) < w * h:
                    shaped += 1
        self.assertGreater(shaped, 0, "no room ever got a corner bite")

    def test_deterministic_masks(self):
        a = [sorted(r.cells) for r in generate_world(555).rooms]
        b = [sorted(r.cells) for r in generate_world(555).rooms]
        self.assertEqual(a, b)

    def test_flag_off_gives_plain_rectangles(self):
        from game import config
        old = config.IRREGULAR_ROOMS
        config.IRREGULAR_ROOMS = False
        try:
            for r in generate_world(42).rooms:
                w, h = r.tile_dims
                self.assertEqual(len(r.cells), w * h)
        finally:
            config.IRREGULAR_ROOMS = old

    def test_size_band_wider_than_the_legacy_range(self):
        # irregular mode should reach both smaller and larger rooms than the old
        # 0.55-0.86 band (chunk 720 -> ~396..619 px).
        widths = [r.rect.width for seed in range(40)
                  for r in generate_world(seed).rooms]
        self.assertLess(min(widths), 396)
        self.assertGreater(max(widths), 619)


if __name__ == "__main__":
    unittest.main()
