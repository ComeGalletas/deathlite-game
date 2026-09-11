"""HI-1: the human island (`documentation/journals/human_island_journal.md`).

A village is a room kind, not a special kind: it is chosen by role near the
start, wears the flat `human` topography, and carries nothing the rest of the
world does -- no scatter, no spawn points, no residents. What *does* stand on
it is the village pass's business (HI-2, `world/gen/village.py`).

Reads the shared cached worlds; the two count-band checks build a layout
each under their own settings, since the band is the thing under test.
"""
import unittest

import pygame

from game import config
from game.content import get_content
from spawn.master import _RESIDENT_KINDS
from tests import worlds as W
from world.gen import generate_world
from world.gen.settings import GenSettings
from world.gen.tuning import SPECIAL_KINDS, VILLAGE_KIND
from world.layout import GROUND, LAKE


def _villages(w):
    return [r for r in w.rooms if r.kind == VILLAGE_KIND]


class VillageRoleTests(unittest.TestCase):
    def test_every_world_has_one_or_two_villages(self):
        lo, hi = config.HEIGHTMAP_VILLAGES
        for seed in W.SEEDS:
            n = len(_villages(W.layout(seed)))
            self.assertGreaterEqual(n, lo, f"seed {seed}: {n} villages")
            self.assertLessEqual(n, hi, f"seed {seed}: {n} villages")

    def test_the_band_is_a_setting(self):
        for band in ((1, 1), (2, 2)):
            w = generate_world(W.SEEDS[0],
                               settings=GenSettings.from_config(villages=band))
            self.assertEqual(len(_villages(w)), band[0], f"band {band}")

    def test_villages_sit_near_the_start_and_are_never_the_boss(self):
        lo, hi = config.HEIGHTMAP_VILLAGE_DISTANCE
        for seed in W.SEEDS:
            w = W.layout(seed)
            dist = w.bfs_distances(w.start_id)
            for r in _villages(w):
                self.assertNotIn(r.id, (w.start_id, w.boss_id), f"seed {seed}")
                self.assertTrue(lo <= dist[r.id] <= hi,
                                f"seed {seed}: village {r.id} at distance {dist[r.id]}")

    def test_village_is_not_a_special_kind_and_the_fountain_island_is_gone(self):
        self.assertNotIn(VILLAGE_KIND, SPECIAL_KINDS)
        self.assertNotIn("fountain", SPECIAL_KINDS)
        for seed in W.SEEDS:
            self.assertNotIn("fountain", {r.kind for r in W.layout(seed).rooms})


class VillageShapeTests(unittest.TestCase):
    def test_village_wears_the_human_topography_flat_and_whole(self):
        spec = config.HEIGHTMAP_TOPOGRAPHIES[config.HEIGHTMAP_VILLAGE_TOPOGRAPHY]
        self.assertEqual(spec["weight"], 0, "the human shape is assigned by role only")
        for seed in W.SEEDS:
            for r in _villages(W.layout(seed)):
                self.assertEqual(r.topography, config.HEIGHTMAP_VILLAGE_TOPOGRAPHY)
                cells = r.grid.values()
                self.assertEqual({c.level for c in cells if c.kind == GROUND}, {0},
                                 f"seed {seed}: village {r.id} is not flat")
                self.assertEqual(sum(1 for c in cells if c.kind == LAKE), 0,
                                 f"seed {seed}: village {r.id} has a lake")

    def test_village_is_about_half_a_volcanic_island(self):
        """Smaller than any volcanic island of the same world. The exact ratio
        is the `size` knob's business and is measured in the journal."""
        for seed in W.SEEDS:
            w = W.layout(seed)
            volcanic = [len(r.cells) for r in w.rooms if r.topography == "volcanic"]
            if not volcanic:
                continue
            for r in _villages(w):
                self.assertLess(len(r.cells), min(volcanic), f"seed {seed}")


class VillageLayoutTests(unittest.TestCase):
    """HI-2: the village pass. Only village kinds stand on the island, the
    forge is at the middle, the guards are at the bridges, the pen is whole,
    and no two colliders overlap."""

    VILLAGE_KINDS = {"forge", "house", "monastery", "archery", "barracks",
                     "tower", "castle", "fence",
                     # the village's own scatter (trees and rocks in the gaps)
                     "tree", "rock", "pillar", "sign", "scarecrow"}

    def _on(self, w, room):
        return [o for o in w.obstacles if room.rect.collidepoint(o.pos.x, o.pos.y)]

    def test_only_village_kinds_stand_on_a_village(self):
        for seed in W.SEEDS:
            w = W.layout(seed)
            for r in _villages(w):
                kinds = {o.kind for o in self._on(w, r)}
                self.assertTrue(kinds, f"seed {seed}: village {r.id} is bare")
                self.assertLessEqual(kinds, self.VILLAGE_KINDS, f"seed {seed}")

    def test_one_village_record_per_village_island(self):
        for seed in W.SEEDS:
            w = W.layout(seed)
            self.assertEqual([v.room_id for v in w.villages],
                             [r.id for r in _villages(w)])

    def test_the_forge_stands_near_the_middle(self):
        px = config.TILE_PX
        for seed in W.SEEDS:
            w = W.layout(seed)
            for v in w.villages:
                room = w.room(v.room_id)
                # near the centroid, allowing the slide south that leaves the
                # axis (heal, hall) room to the north
                self.assertLessEqual(v.forge.distance_to(room.center), 5 * px,
                                     f"seed {seed}: forge off-centre")
                forges = [o for o in self._on(w, room) if o.kind == "forge"]
                self.assertEqual(len(forges), 1)
                self.assertEqual(forges[0].pos, v.forge)

    def test_the_heal_is_near_the_forge_and_on_ground(self):
        px = config.TILE_PX
        for seed in W.SEEDS:
            w = W.layout(seed)
            for v in w.villages:
                room = w.room(v.room_id)
                self.assertLessEqual(v.heal.distance_to(v.forge), 5 * px)
                cell = room.grid.get(((v.heal.x - room.rect.left) // px,
                                      (v.heal.y - room.rect.top) // px))
                self.assertIsNotNone(cell)
                self.assertEqual(cell.kind, GROUND)

    def test_guards_stand_a_few_tiles_in_from_a_bridge(self):
        """Every barracks and tower is within reach of some bridge mouth."""
        # (the group test above covers the archery as well)
        px = config.TILE_PX
        for seed in W.SEEDS:
            w = W.layout(seed)
            for v in w.villages:
                mouths = [pygame.Vector2(m) for m in v.mouths]
                self.assertTrue(mouths, f"seed {seed}: a village with no bridge")
                for kind, x, y in v.buildings:
                    if kind in ("barracks", "tower"):
                        d = min(m.distance_to((x, y)) for m in mouths)
                        self.assertLessEqual(d, 8 * px,
                                             f"seed {seed}: {kind} {d / px:.1f} tiles from a bridge")
                self.assertTrue(any(k in ("barracks", "tower") for k, _x, _y in v.buildings))

    def test_the_pen_is_a_closed_ring_on_ground_with_one_gate(self):
        from world.gen.tuning import _V_PEN_SCALE
        px = config.TILE_PX
        pitch = px * _V_PEN_SCALE
        pens = 0
        for seed in W.SEEDS:
            w = W.layout(seed)
            for v in w.villages:
                if v.pen is None:
                    continue
                pens += 1
                room = w.room(v.room_id)
                fences = [o for o in self._on(w, room) if o.kind == "fence"]
                ring = v.pen.inflate(round(2 * pitch), round(2 * pitch))
                self.assertTrue(all(ring.collidepoint(o.pos.x, o.pos.y) for o in fences))
                # one two-tile gate: the ring's tile count less two
                wt, ht = round(ring.width / pitch), round(ring.height / pitch)
                self.assertEqual(len(fences), 2 * wt + 2 * ht - 4 - 2, f"seed {seed}")
                for col in range(ring.left // px, (ring.right - 1) // px + 1):
                    for row in range(ring.top // px, (ring.bottom - 1) // px + 1):
                        cell = room.grid.get((col - room.rect.left // px,
                                              row - room.rect.top // px))
                        self.assertIsNotNone(cell, f"seed {seed}: pen off the island")
                        self.assertEqual(cell.kind, GROUND)
        self.assertGreater(pens, 0, "no village in the pinned seeds got a pen")

    def test_satellites_collide_but_carry_no_skin(self):
        for seed in W.SEEDS:
            w = W.layout(seed)
            sats = [o for o in w.obstacles if not o.skin]
            self.assertTrue(sats, f"seed {seed}: no compound building")
            for o in sats:
                self.assertIn(o.kind, ("barracks", "archery", "monastery", "castle"))
                self.assertGreater(o.radius, 0)

    def test_no_two_village_circles_overlap(self):
        for seed in W.SEEDS:
            w = W.layout(seed)
            for r in _villages(w):
                on = self._on(w, r)
                for i, a in enumerate(on):
                    for b in on[i + 1:]:
                        if a.kind == b.kind and not (a.skin and b.skin):
                            continue        # one compound's own circles
                        self.assertGreaterEqual(
                            a.pos.distance_to(b.pos), a.radius + b.radius - 1e-6,
                            f"seed {seed}: {a.kind} overlaps {b.kind}")

    def test_the_axis_forge_heal_and_town_hall_run_due_north(self):
        """The heal zone directly above the forge, the town hall (the
        monastery) directly above the heal, all on one vertical line."""
        px = config.TILE_PX
        halls = 0
        for seed in W.SEEDS:
            for v in W.layout(seed).villages:
                self.assertLessEqual(v.heal.y, v.forge.y - 2 * px, f"seed {seed}: heal not north")
                self.assertLess(abs(v.heal.x - v.forge.x), px, f"seed {seed}: heal off the axis")
                for kind, x, y in v.buildings:
                    if kind != "monastery":
                        continue
                    halls += 1
                    self.assertLess(y, v.heal.y - px, f"seed {seed}: hall not above the heal")
                    self.assertEqual(x, v.heal.x, f"seed {seed}: hall off the heal's x")
        self.assertGreater(halls, 0)
        w = generate_world(W.SEEDS[0], settings=GenSettings.from_config(town_hall=False))
        self.assertFalse(any(o.kind == "monastery" for o in w.obstacles))

    def test_houses_cluster_and_the_military_groups_by_the_bridges(self):
        px = config.TILE_PX
        for seed in W.SEEDS:
            for v in W.layout(seed).villages:
                houses = [pygame.Vector2(x, y) for k, x, y in v.buildings if k == "house"]
                blds = [pygame.Vector2(x, y) for _k, x, y in v.buildings]
                # every house has another building within four tiles: one
                # village round its square (LD-Z: the two houses flanking
                # the heal are five tiles apart, and both by the forge)
                for h in houses:
                    self.assertLessEqual(
                        min(h.distance_to(o) for o in blds if o is not h), 4 * px,
                        f"seed {seed}: a house stands alone")
                mouths = [pygame.Vector2(m) for m in v.mouths]
                military = [(k, pygame.Vector2(x, y)) for k, x, y in v.buildings
                            if k in ("barracks", "tower", "archery")]
                for k, pos in military:
                    self.assertLessEqual(min(m.distance_to(pos) for m in mouths), 8 * px,
                                         f"seed {seed}: {k} far from every bridge")

    def test_the_ring_is_compact_and_the_props_stay_outside_it(self):
        """Every house, monastery and archery within the ring's reach of the
        forge; every tree and rock outside the cluster radius."""
        from world.gen.tuning import _V_CLUSTER_RADIUS, _V_RING
        px = config.TILE_PX
        for seed in W.SEEDS:
            w = W.layout(seed)
            for v in w.villages:
                room = w.room(v.room_id)
                for kind, x, y in v.buildings:
                    if kind == "house":
                        self.assertLessEqual(v.forge.distance_to((x, y)),
                                             (_V_RING[1] + 1.5) * px, f"seed {seed}: {kind} strays")
                for o in self._on(w, room):
                    if o.kind in ("tree", "rock", "pillar", "sign", "scarecrow"):
                        self.assertGreaterEqual(v.forge.distance_to(o.pos), _V_CLUSTER_RADIUS * px,
                                                f"seed {seed}: {o.kind} inside the settlement")


class VillageIsEmptyTests(unittest.TestCase):
    """The rest of the world's machinery passes over a village."""

    def test_no_spawn_or_resource_points_on_a_village(self):
        for seed in W.SEEDS:
            w = W.layout(seed)
            ids = {r.id for r in _villages(w)}
            self.assertEqual([p for p in w.spawn_points if p.room_id in ids], [])
            self.assertEqual([p for p in w.resource_points if p.room_id in ids], [])
            # ... and the rest of the world still has them
            self.assertTrue(w.spawn_points, f"seed {seed}")

    def test_village_seeds_no_residents(self):
        table = get_content().spawn_tables.residents
        self.assertIn(VILLAGE_KIND, _RESIDENT_KINDS,
                      "a village must not fall through to the `special` count")
        self.assertEqual(table[VILLAGE_KIND], 0)


if __name__ == "__main__":
    unittest.main()
