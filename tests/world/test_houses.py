"""Buildings (`TERRAIN_BUILDINGS`): a large `house` obstacle placed off-centre
in big rooms, plus a colour-matched village cluster in the roomiest rooms.
See world/procedural._scatter_houses."""
import itertools
import unittest

import pygame

from game import config
from world.map import GameMap
from world.procedural import (

    SPECIAL_KINDS, _HOUSE_RADIUS, _VILLAGE_MIN_ROOM_CELLS, _VILLAGE_RADIUS,
    _corridor_doorways, generate_world,
)

PX = config.TILE_PX


# LD-9: this module covers the **LD-8 world model** -- grown room shapes,
# corridors, cliff bands, one `floor` per room. `config.HEIGHTMAP_ROOMS`
# defaults on now and selects a different generator entirely, whose rooms are
# height maps with overlapping bounding rects and no cliff band. Pin the flag
# off here so this coverage keeps testing the path it was written for; the
# height-map path has its own in `tests/world/test_elevation.py`.
_SAVED_HEIGHTMAP = None


def _pin_heightmap_off():
    global _SAVED_HEIGHTMAP
    _SAVED_HEIGHTMAP = config.HEIGHTMAP_ROOMS
    config.HEIGHTMAP_ROOMS = False


def _restore_heightmap():
    config.HEIGHTMAP_ROOMS = _SAVED_HEIGHTMAP


def _houses(w):
    return [o for o in w.obstacles if o.kind == "house"]


def _room_of(w, o):
    for room in w.rooms:
        if room.rect.collidepoint(o.pos.x, o.pos.y):
            return room
    return None


class HousePlacementTests(unittest.TestCase):
    def test_houses_are_generated_somewhere(self):
        total = sum(len(_houses(generate_world(s))) for s in range(40))
        self.assertGreater(total, 20, "no houses across 40 seeds")

    def test_never_in_the_boss_room(self):
        for seed in range(40):
            w = generate_world(seed)
            boss = w.room(w.boss_id).rect
            self.assertFalse(
                any(boss.collidepoint(o.pos.x, o.pos.y) for o in _houses(w)),
                f"house in the boss room (seed {seed})")

    def test_only_in_rooms_big_enough(self):
        for seed in range(30):
            w = generate_world(seed)
            for o in _houses(w):
                room = _room_of(w, o)
                self.assertIsNotNone(room)
                rr = room.rect
                self.assertGreaterEqual(min(rr.width, rr.height), 6 * PX)
                self.assertGreaterEqual(len(room.cells), 60)

    def test_kept_off_the_room_centre(self):
        # never dead-centre: a house sits at >= 20% of the short side from the
        # bounding-box centre (special/start rooms keep even more clearance).
        for seed in range(30):
            w = generate_world(seed)
            for o in _houses(w):
                rr = _room_of(w, o).rect
                d = pygame.Vector2(rr.center).distance_to(o.pos)
                self.assertGreater(d, min(rr.width, rr.height) * 0.20,
                                   f"house too central (seed {seed})")

    def test_clear_of_every_corridor_doorway(self):
        for seed in range(25):
            w = generate_world(seed)
            hs = _houses(w)
            if not hs:
                continue
            doors = [d for slabs in _corridor_doorways(w.rooms, w.corridors).values()
                     for d in slabs]
            for o in hs:
                self.assertFalse(
                    any(d.collidepoint(o.pos.x, o.pos.y) for d in doors),
                    f"house on a doorway tile (seed {seed})")

    def test_deterministic(self):
        for seed in (3, 17, 44):
            a = [(round(o.pos.x, 3), round(o.pos.y, 3), o.variant)
                 for o in _houses(generate_world(seed))]
            b = [(round(o.pos.x, 3), round(o.pos.y, 3), o.variant)
                 for o in _houses(generate_world(seed))]
            self.assertEqual(a, b)

    def test_variant_encodes_colour_band_and_type(self):
        for seed in range(30):
            for o in _houses(generate_world(seed)):
                self.assertIn(o.variant, range(1, 16))


class HouseColliderTests(unittest.TestCase):
    def _map_with_house(self):
        for seed in range(40):
            gm = GameMap(seed=seed)
            house = next((o for o in gm.obstacles if o.kind == "house"), None)
            if house is not None:
                return gm, house
        self.fail("no seed produced a house")

    def test_blocks_standing_but_not_well_outside_its_footprint(self):
        gm, house = self._map_with_house()
        self.assertFalse(gm.is_walkable(pygame.Vector2(house.pos), 0))
        # nothing of *this* house reaches 3 radii out (other obstacles might)
        for ang in (0, 90, 180, 270):
            p = pygame.Vector2(house.pos) + pygame.Vector2(3 * _HOUSE_RADIUS, 0).rotate(ang)
            self.assertGreater(p.distance_to(house.pos), _HOUSE_RADIUS)

    def test_blocks_projectiles(self):
        gm, house = self._map_with_house()
        hit = gm.blocking_obstacle_hit(pygame.Vector2(house.pos), 4)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.kind, "house")


class VillageClusterTests(unittest.TestCase):
    def _a_village(self):
        for seed in range(120):
            w = generate_world(seed)
            for room in w.rooms:
                inside = [o for o in _houses(w)
                          if room.rect.collidepoint(o.pos.x, o.pos.y)]
                if len(inside) >= 2:
                    return seed, room, inside
        self.fail("no village across 120 seeds")

    def test_a_village_exists_only_in_a_roomy_room(self):
        _seed, room, inside = self._a_village()
        self.assertGreaterEqual(len(room.cells), _VILLAGE_MIN_ROOM_CELLS)
        self.assertLessEqual(len(inside), 4)

    def test_one_colour_band_distinct_types_spaced_and_grouped(self):
        _seed, _room, inside = self._a_village()
        bands = {(o.variant - 1) // 3 for o in inside}
        self.assertEqual(len(bands), 1, "village mixes colour bands")
        types = {(o.variant - 1) % 3 for o in inside}
        self.assertGreaterEqual(len(types), min(len(inside), 3),
                                "village houses are not varied types")
        for a, b in itertools.combinations(inside, 2):
            self.assertGreaterEqual(a.pos.distance_to(b.pos), 2 * _HOUSE_RADIUS)
        anchor = inside[0].pos
        for o in inside[1:]:
            self.assertLessEqual(anchor.distance_to(o.pos),
                                 _VILLAGE_RADIUS[1] * PX + 1)


class FlagOffTests(unittest.TestCase):
    def setUp(self):
        self._old = config.TERRAIN_BUILDINGS

    def tearDown(self):
        config.TERRAIN_BUILDINGS = self._old

    def test_flag_off_produces_no_houses_and_stays_deterministic(self):
        config.TERRAIN_BUILDINGS = False
        for seed in (0, 4, 43):
            a = generate_world(seed).obstacles
            b = generate_world(seed).obstacles
            self.assertFalse(any(o.kind == "house" for o in a))
            self.assertEqual([(o.kind, tuple(o.pos)) for o in a],
                             [(o.kind, tuple(o.pos)) for o in b])

    def test_special_room_centres_still_clear_with_the_flag_on_or_off(self):
        for flag in (False, True):
            config.TERRAIN_BUILDINGS = flag
            for seed in (5, 9, 42):
                w = generate_world(seed)
                for room in w.rooms:
                    if room.kind not in SPECIAL_KINDS:
                        continue
                    cx, cy = room.rect.center
                    clear = min(room.rect.width, room.rect.height) * 0.2
                    for o in w.obstacles:
                        self.assertGreaterEqual(
                            (o.pos.x - cx) ** 2 + (o.pos.y - cy) ** 2, clear ** 2,
                            f"obstacle mid-{room.kind} (seed {seed}, flag {flag})")


if __name__ == "__main__":
    unittest.main()


def setUpModule():
    _pin_heightmap_off()


def tearDownModule():
    _restore_heightmap()
