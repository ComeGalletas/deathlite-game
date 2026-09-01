"""LD-9: the per-island biome pool.

The height-map worlds used to read a fixed `floor -> sheet` map, so every island
on every seed wore the same tileset at the same height. Now the tilesets are
listed in `data/terrain.json` as `heightmap_biome_pool`, with no floor attached,
and each island draws its terraces from that list.

The brief's rule was *at least three tilemaps per island, no two adjacent floors
share one*. Level 0 supplies the first of the three for free -- it keeps the
room-kind palette, because it is the only terrace that meets the sea and so the
only one that needs a shoreline block with real surf in it -- and the pool
covers the raised terraces above it.
"""
import json
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.assets import ASSETS_DIR, get_assets
from world.gen import generate_world
from world.layout import GROUND
from world.terrain.biome import floor_palette
from world.terrain.sheets import TileSheets

POOL = ["a.png", "b.png", "c.png"]
# `b` shares a material with the ground the islands rise from, the way
# `tilemap_7`'s grass shares one with the level-0 kind palettes.
FAMILY = {"base.png": "grass", "a.png": "rock", "b.png": "grass",
          "c.png": "sand"}.get


class PoolDataTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join("data", "terrain.json"), encoding="utf-8") as fh:
            self.t = json.load(fh)

    def test_the_pool_is_declared_and_has_room_to_vary(self):
        pool = self.t.get("heightmap_biome_pool")
        self.assertTrue(pool, "no biome pool declared")
        self.assertGreaterEqual(len(pool), 2,
                                "a pool of one cannot satisfy the adjacency rule")
        self.assertEqual(len(set(pool)), len(pool), "duplicate sheet in the pool")

    def test_every_pool_sheet_is_a_real_file(self):
        for rel in self.t["heightmap_biome_pool"]:
            self.assertTrue(os.path.exists(os.path.join(ASSETS_DIR, rel)), rel)

    def test_no_pool_sheet_claims_a_shoreline(self):
        """Only level 0 meets the sea, and level 0 is never drawn from the pool.
        A pool sheet claiming surf would render a beach in the middle of a
        terrace."""
        flags = self.t.get("sheet_flags", {})
        for rel in self.t["heightmap_biome_pool"]:
            self.assertFalse(flags.get(rel, {}).get("shoreline", True),
                             f"{rel} is not flagged shoreline: false")

    def test_the_old_fixed_floor_map_is_gone(self):
        """It is superseded; leaving it would be two sources for one answer."""
        self.assertNotIn("heightmap_floor_sheets", self.t)

    def test_every_sheet_that_can_touch_a_terrace_declares_its_material(self):
        """An undeclared sheet is its own family, so it would be allowed to sit
        on top of a sheet it is indistinguishable from."""
        fams = self.t.get("sheet_biomes", {})
        for rel in (list(self.t["heightmap_biome_pool"])
                    + list(self.t["room_palettes"].values())):
            self.assertIn(rel, fams, f"{rel} has no declared biome")

    def test_the_pool_offers_a_material_the_ground_does_not(self):
        """Level 0 is always a kind palette. If the pool held only that
        material there would be no legal choice for level 1."""
        fams = self.t["sheet_biomes"]
        ground = {fams[r] for r in self.t["room_palettes"].values()}
        pool = {fams[r] for r in self.t["heightmap_biome_pool"]}
        self.assertTrue(pool - ground, "no pool material differs from the ground")


class PaletteRuleTests(unittest.TestCase):
    def test_adjacent_levels_never_share_a_sheet(self):
        for seed in range(40):
            for rid in range(6):
                pal = floor_palette(seed, rid, (1, 2, 3), POOL, base="base.png")
                got = [pal[k] for k in sorted(pal)]
                for a, b in zip(got, got[1:]):
                    self.assertNotEqual(a, b, f"seed {seed} room {rid}: {got}")

    def test_adjacent_levels_never_share_a_material(self):
        """The rule that matters. Two different files of the same material read
        as one continuous surface with a cliff line drawn through it."""
        for seed in range(40):
            for rid in range(6):
                pal = floor_palette(seed, rid, (1, 2), POOL, base="base.png",
                                    family=FAMILY)
                got = [FAMILY(pal[k]) for k in sorted(pal)]
                self.assertNotEqual(FAMILY("base.png"), got[0],
                                    f"seed {seed} room {rid}: {got}")
                for a, b in zip(got, got[1:]):
                    self.assertNotEqual(a, b, f"seed {seed} room {rid}: {got}")

    def test_the_lowest_terrace_differs_from_the_ground_it_rises_from(self):
        for seed in range(40):
            pal = floor_palette(seed, 0, (1, 2), POOL, base=POOL[0])
            self.assertNotEqual(pal[1], POOL[0])

    def test_it_is_stable_for_the_same_seed_and_room(self):
        a = floor_palette(7, 3, (1, 2), POOL, base="base.png")
        b = floor_palette(7, 3, (1, 2), POOL, base="base.png")
        self.assertEqual(a, b)

    def test_rooms_of_one_world_do_not_all_look_alike(self):
        seen = {tuple(sorted(floor_palette(11, rid, (1, 2), POOL,
                                           base="base.png").items()))
                for rid in range(12)}
        self.assertGreater(len(seen), 1, "every island drew the same palette")

    def test_a_pool_of_one_degrades_instead_of_failing(self):
        """Nothing else is available, so the repeat is the only answer; it must
        not raise or loop."""
        pal = floor_palette(0, 0, (1, 2), ["only.png"], base="base.png")
        self.assertEqual(pal, {1: "only.png", 2: "only.png"})

    def test_an_empty_pool_yields_no_palette(self):
        self.assertEqual(floor_palette(0, 0, (1, 2), [], base="b.png"), {})

    def test_it_does_not_touch_the_shared_rng(self):
        """The world's own stream must not shift because something asked for a
        palette, or the same seed would generate two different worlds."""
        import random
        random.seed(99)
        before = [random.random() for _ in range(5)]
        random.seed(99)
        floor_palette(1, 1, (1, 2), POOL, base="base.png")
        self.assertEqual(before, [random.random() for _ in range(5)])


class BakedWorldTests(unittest.TestCase):
    """The painters have to agree with the palette, not just the module."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls._saved = config.HEIGHTMAP_ROOMS
        config.HEIGHTMAP_ROOMS = True

    @classmethod
    def tearDownClass(cls):
        config.HEIGHTMAP_ROOMS = cls._saved

    def _sheets(self, seed):
        layout = generate_world(seed)
        return layout, TileSheets(get_assets(), layout.seed)

    def test_every_raised_level_of_every_island_gets_a_pool_sheet(self):
        layout, sheets = self._sheets(21)
        if not sheets.ok:
            self.skipTest("tileset missing")
        raised = 0
        for room in layout.rooms:
            if not room.grid:
                continue
            for level in {c.level for c in room.grid.values()
                          if c.kind == GROUND and c.level > 0}:
                self.assertIn(sheets.sheet_for(level, room.kind, room),
                              sheets.biome_pool)
                raised += 1
        self.assertGreater(raised, 0, "no raised terrace in this world to check")

    def test_level_zero_keeps_its_kind_palette(self):
        layout, sheets = self._sheets(21)
        if not sheets.ok:
            self.skipTest("tileset missing")
        for room in layout.rooms:
            got = sheets.sheet_for(0, room.kind, room)
            self.assertNotIn(got, sheets.biome_pool)
            self.assertEqual(got, sheets.palettes.get(room.kind,
                                                      sheets.floor_sheet))

    def test_two_islands_of_one_world_differ(self):
        layout, sheets = self._sheets(21)
        if not sheets.ok:
            self.skipTest("tileset missing")
        pals = {tuple(sorted(sheets.biome_palette(r).items()))
                for r in layout.rooms if r.grid and r.floor >= 0}
        self.assertGreater(len(pals), 1)

    def test_no_terrace_wears_the_material_of_the_terrace_below_it(self):
        """End to end on the real data: `tilemap_7` is grass and every level 0
        is grass, so `tilemap_7` must never land on level 1."""
        layout, sheets = self._sheets(21)
        if not sheets.ok:
            self.skipTest("tileset missing")
        checked = 0
        for room in layout.rooms:
            if not room.grid:
                continue
            below = sheets.biome_of(sheets.sheet_for(0, room.kind, room))
            for level in sorted({c.level for c in room.grid.values()
                                 if c.kind == GROUND and c.level > 0}):
                fam = sheets.biome_of(sheets.sheet_for(level, room.kind, room))
                self.assertNotEqual(fam, below,
                                    f"room {room.id} level {level} is {fam} "
                                    f"on top of {fam}")
                below = fam
                checked += 1
        self.assertGreater(checked, 0)

    def test_a_room_without_the_pool_falls_back_rather_than_guessing(self):
        """`sheet_for` with no room cannot know which island was meant, so it
        must not return a pool sheet."""
        layout, sheets = self._sheets(21)
        if not sheets.ok:
            self.skipTest("tileset missing")
        self.assertNotIn(sheets.sheet_for(2, "default"), sheets.biome_pool)


if __name__ == "__main__":
    unittest.main()
