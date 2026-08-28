"""Irregular rooms (worldgen W1-W4): the tile-cell mask drives walkability
(W2), rendering (W3) and scatter (W4)."""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from world.map import GameMap
from world.procedural import _four_connected, generate_world


def _display():
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))


def _shaped_room(seed_range=range(60)):
    """First (seed, room) whose mask has a corner bitten out."""
    for seed in seed_range:
        for r in generate_world(seed).rooms:
            w, h = r.tile_dims
            if len(r.cells) < w * h:
                return seed, r
    raise AssertionError("no shaped room found")


def _world_pt(room, col, row):
    px = config.TILE_PX
    return pygame.Vector2(room.rect.left + (col + 0.5) * px,
                          room.rect.top + (row + 0.5) * px)


class WalkabilityMaskTests(unittest.TestCase):
    def test_a_bitten_out_cell_is_not_walkable_but_a_floor_cell_is(self):
        seed, room = _shaped_room()
        gm = GameMap(seed=seed)
        w, h = room.tile_dims
        void = [(c, r) for c in range(w) for r in range(h) if (c, r) not in room.cells]
        self.assertTrue(void)
        for col, row in void:
            p = _world_pt(room, col, row)
            self.assertFalse(gm._point_ok(p.x, p.y),
                             f"void cell {(col, row)} reads walkable")
        for col, row in sorted(room.cells):
            p = _world_pt(room, col, row)
            self.assertTrue(gm._point_ok(p.x, p.y),
                            f"floor cell {(col, row)} reads blocked")

    def test_shaped_room_floor_is_one_connected_component(self):
        seed, room = _shaped_room()
        gm = GameMap(seed=seed)
        # flood fill over the *walkable* cells (via _point_ok) from one corner
        floor = {(c, r) for (c, r) in room.cells}
        start = min(floor)
        seen, stack = {start}, [start]
        while stack:
            c, r = stack.pop()
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (c + dc, r + dr)
                if nb in floor and nb not in seen:
                    p = _world_pt(room, *nb)
                    if gm._point_ok(p.x, p.y):
                        seen.add(nb)
                        stack.append(nb)
        self.assertEqual(seen, floor, "shaped room floor split into pieces")

    def test_random_point_in_room_always_lands_on_the_floor(self):
        seed, _ = _shaped_room()
        gm = GameMap(seed=seed)
        rng = random.Random(0)
        for room in gm.layout.rooms:
            for _ in range(40):
                p = gm.random_point_in_room(room, rng)
                self.assertIn(gm.room_cell(room, p.x, p.y), room.cells)

    def test_corridors_remain_walkable(self):
        gm = GameMap(seed=42)
        for c in gm.layout.corridors:
            self.assertTrue(gm.is_walkable(pygame.Vector2(c.rect.center)))

    def test_no_obstacle_sits_in_a_bitten_out_cell(self):
        px = config.TILE_PX
        for seed in (1, 7, 42, 99, 1234):
            w = generate_world(seed)
            rooms = {r.id: r for r in w.rooms}
            for o in w.obstacles:
                for r in w.rooms:
                    if r.rect.collidepoint(o.pos.x, o.pos.y):
                        cell = (int((o.pos.x - r.rect.left) // px),
                                int((o.pos.y - r.rect.top) // px))
                        self.assertIn(cell, r.cells,
                                      f"seed {seed}: {o.kind} in a void cell of room {r.id}")
                        break

    def test_flag_off_walkability_is_the_full_rectangle(self):
        old = config.IRREGULAR_ROOMS
        config.IRREGULAR_ROOMS = False
        try:
            gm = GameMap(seed=42)
            room = gm.layout.rooms[3]
            w, h = room.tile_dims
            for col in range(w):
                for row in range(h):
                    p = _world_pt(room, col, row)
                    self.assertTrue(gm._point_ok(p.x, p.y))
        finally:
            config.IRREGULAR_ROOMS = old


class ScatterMaskTests(unittest.TestCase):
    """W4: obstacle + decor scatter pick from the cell mask; count scales with
    a room's area; doorways stay clear; the biggest room fits the bounds."""

    def test_every_obstacle_sits_on_a_floor_cell(self):
        px = config.TILE_PX
        for seed in (3, 11, 42, 63, 777):
            w = generate_world(seed)
            for o in w.obstacles:
                for r in w.rooms:
                    if r.rect.collidepoint(o.pos.x, o.pos.y):
                        cell = (int((o.pos.x - r.rect.left) // px),
                                int((o.pos.y - r.rect.top) // px))
                        self.assertIn(cell, r.cells)
                        break

    def test_obstacle_count_scales_with_room_area(self):
        # over many seeds, bigger combat rooms average more obstacles
        small, big = [], []
        for seed in range(50):
            w = generate_world(seed)
            for r in w.rooms:
                if r.kind != "combat":
                    continue
                n = sum(1 for o in w.obstacles if r.rect.collidepoint(o.pos.x, o.pos.y))
                (big if len(r.cells) >= 70 else small).append(n)
        self.assertGreater(sum(big) / len(big), sum(small) / len(small))

    def test_doorway_tiles_stay_clear_with_shaped_rooms(self):
        from world.procedural import _corridor_doorways
        px = config.TILE_PX
        for seed in (1, 7, 42, 63, 99, 1234):
            w = generate_world(seed)
            slabs = _corridor_doorways(w.rooms, w.corridors)
            tiles = [d.inflate(-2 * px, -2 * px)
                     for lst in slabs.values() for d in lst]
            for o in w.obstacles:
                for t in tiles:
                    if t.width > 0 and t.collidepoint(o.pos.x, o.pos.y):
                        self.fail(f"seed {seed}: {o.kind} on a doorway tile")

    def test_largest_room_is_within_bounds(self):
        for seed in range(40):
            w = generate_world(seed)
            biggest = max(w.rooms, key=lambda r: r.rect.width * r.rect.height)
            self.assertTrue(w.bounds.contains(biggest.rect))
            self.assertLessEqual(len(max(w.rooms, key=lambda r: len(r.cells)).cells),
                                 config.ROOM_SIZE_MAX_CELLS)

    def test_decor_clutter_only_on_fully_interior_cells(self):
        _display()
        seed, _ = _shaped_room()
        gm = GameMap(seed=seed)
        gm._build_tiles()
        self.assertTrue(gm._tiles_ok, "tileset absent -- cannot check clutter")
        ortho = ((1, 0), (-1, 0), (0, 1), (0, -1))
        for rid, inst in gm._room_decor.items():
            room = gm.layout.room(rid)
            for *_rest, x, y in inst:
                col, row = gm.room_cell(room, x, y)
                self.assertTrue(
                    all((col + dc, row + dr) in room.cells for dc, dr in ortho),
                    f"room {rid} clutter cell {(col, row)} is on an edge")


def _floor_rects(room):
    px = config.TILE_PX
    return [pygame.Rect(room.rect.left + c * px, room.rect.top + r * px, px, px)
            for c, r in room.cells]


def _grown_room(seed_range=range(120)):
    """First (seed, room) whose bbox is bigger than a single chunk on some axis
    -> it grew into a neighbour chunk (W5)."""
    for seed in seed_range:
        for r in generate_world(seed).rooms:
            if max(r.rect.width, r.rect.height) > config.CHUNK_SIZE:
                return seed, r
    raise AssertionError("no multi-chunk room found")


class MultiChunkRoomTests(unittest.TestCase):
    SEEDS = tuple(range(60))

    def test_a_multichunk_room_exists(self):
        seed, room = _grown_room()
        self.assertGreater(max(room.rect.width, room.rect.height), config.CHUNK_SIZE)

    def test_growth_respects_the_cell_cap(self):
        for seed in self.SEEDS:
            for r in generate_world(seed).rooms:
                self.assertLessEqual(len(r.cells), config.ROOM_SIZE_MAX_CELLS)
                self.assertTrue(_four_connected(set(r.cells)))

    def test_grown_room_is_fully_walkable(self):
        seed, room = _grown_room()
        gm = GameMap(seed=seed)
        room = gm.layout.rooms[room.id]
        for col, row in sorted(room.cells):
            p = _world_pt(room, col, row)
            self.assertTrue(gm._point_ok(p.x, p.y), f"floor cell {(col, row)} blocked")

    def test_all_rooms_within_bounds_and_world_connected(self):
        for seed in self.SEEDS:
            w = generate_world(seed)
            self.assertTrue(w.is_connected())
            for r in w.rooms:
                self.assertTrue(w.bounds.contains(r.rect))

    def test_no_two_rooms_share_a_floor_tile(self):
        for seed in self.SEEDS:
            w = generate_world(seed)
            for i, a in enumerate(w.rooms):
                arects = _floor_rects(a)
                for b in w.rooms[i + 1:]:
                    for br in _floor_rects(b):
                        self.assertEqual(br.collidelist(arects), -1,
                                         f"seed {seed}: rooms {a.id}/{b.id} overlap a tile")

    def test_corridors_still_bridge_both_rooms(self):
        for seed in self.SEEDS:
            w = generate_world(seed)
            for c in w.corridors:
                ra, rb = w.room(c.a).rect, w.room(c.b).rect
                self.assertTrue(c.rect.colliderect(ra) and c.rect.colliderect(rb),
                                f"seed {seed}: corridor {c.a}-{c.b} lost a room")

    def test_deterministic_with_growth(self):
        seed, _ = _grown_room()
        a = [sorted(r.cells) for r in generate_world(seed).rooms]
        b = [sorted(r.cells) for r in generate_world(seed).rooms]
        self.assertEqual(a, b)

    def test_flag_off_keeps_every_room_in_its_chunk(self):
        old = config.IRREGULAR_ROOMS
        config.IRREGULAR_ROOMS = False
        try:
            for seed in range(30):
                for r in generate_world(seed).rooms:
                    self.assertLessEqual(max(r.rect.width, r.rect.height),
                                         config.CHUNK_SIZE)
        finally:
            config.IRREGULAR_ROOMS = old


if __name__ == "__main__":
    unittest.main()
