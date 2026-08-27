"""Terrain Phase T1: data/terrain.json + Assets.tile() + decoration rigs.

Plumbing only — nothing draws terrain yet. Verifies the metadata is coherent
and the loader slices tiles / decoration strips correctly, degrading to None on
a missing sheet.
"""
import logging
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.assets import ASSETS_DIR, Assets, reset_assets
from game.content import get_content


def _display():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))


class TerrainMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        cls.t = get_content().terrain

    def test_core_fields_present(self):
        self.assertEqual(self.t["tile_px"], 64)
        self.assertEqual(self.t["grid"], [9, 6])
        for key in ("floor_sheet", "water_tile", "slots", "room_palettes", "rigs"):
            self.assertIn(key, self.t)

    def test_slot_indices_are_inside_the_grid(self):
        cols, rows = self.t["grid"]
        limit = cols * rows
        for name, val in self.t["slots"].items():
            for idx in (val if isinstance(val, list) else [val]):
                self.assertTrue(0 <= idx < limit, f"slot {name}={idx} out of 0..{limit - 1}")

    def test_referenced_sheets_exist(self):
        sheets = {self.t["floor_sheet"], self.t["water_tile"],
                  *self.t["room_palettes"].values()}
        for s in sheets:
            self.assertTrue((ASSETS_DIR / s).is_file(), f"missing {s}")

    def test_rig_files_and_strip_widths(self):
        rigs = self.t["rigs"]
        deco = [n for n in rigs if n.startswith("deco_")]
        self.assertGreaterEqual(len(deco), 13)          # 4 bush + 4 rock + 4 water rock + duck
        self.assertIn("terrain_foam", rigs)             # animated shoreline foam
        for name, rig in rigs.items():
            spec = rig["anims"]["loop"]
            self.assertTrue((ASSETS_DIR / spec["file"]).is_file(), spec["file"])
            surf = pygame.image.load(str(ASSETS_DIR / spec["file"]))
            fw = rig["frame"][0]
            self.assertEqual(surf.get_width(), fw * spec["frames"],
                             f"{name}: {surf.get_width()} != {fw}*{spec['frames']}")

    def test_decoration_registry_is_coherent(self):
        reg = self.t.get("decorations", [])
        self.assertTrue(reg, "no decoration registry")
        rigs = self.t["rigs"]
        ids = set()
        for e in reg:
            self.assertNotIn(e["id"], ids, f"duplicate decoration id {e['id']}")
            ids.add(e["id"])
            self.assertIn(e["placement"], ("room_interior", "void", "room_edge"))
            self.assertIn(e["rig"], rigs, f"{e['id']}: rig {e['rig']} not in rigs")
            self.assertGreater(float(e.get("scale", 1.0)), 0)
            if e["placement"] == "room_interior":
                lo, hi = e["per_room"]
                self.assertTrue(0 <= lo <= hi)

    def test_obstacle_decor_covers_every_obstacle_kind(self):
        from entities.obstacle import KINDS
        dec = self.t["obstacle_decor"]
        self.assertIsInstance(dec["size_boost"], (int, float))
        self.assertGreater(dec["size_boost"], 0)
        rigs = self.t["rigs"]
        for kind in KINDS:
            self.assertIn(kind, dec["rigs"], f"obstacle kind {kind!r} has no decor rigs")
            self.assertTrue(dec["rigs"][kind], f"{kind!r} decor rig list is empty")
            for rig in dec["rigs"][kind]:
                self.assertIn(rig, rigs, f"{rig} (obstacle_decor) missing from rigs")
                fp = rigs[rig].get("footprint")
                self.assertIsInstance(fp, int, f"{rig} needs an int footprint")
                self.assertGreater(fp, 0)


class AssetsTileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def setUp(self):
        reset_assets()
        self.a = Assets()
        self.sheet = get_content().terrain["floor_sheet"]

    def test_tile_returns_64px_cell(self):
        t = self.a.tile(self.sheet, 10)               # interior floor
        self.assertIsInstance(t, pygame.Surface)
        self.assertEqual(t.get_size(), (64, 64))

    def test_tile_scaled(self):
        t = self.a.tile(self.sheet, 0, size=(32, 32))
        self.assertEqual(t.get_size(), (32, 32))

    def test_tile_is_cached(self):
        self.assertIs(self.a.tile(self.sheet, 10), self.a.tile(self.sheet, 10))

    def test_distinct_indices_differ(self):
        a10 = pygame.image.tostring(self.a.tile(self.sheet, 10), "RGBA")
        a30 = pygame.image.tostring(self.a.tile(self.sheet, 30), "RGBA")
        self.assertNotEqual(a10, a30)

    def test_missing_sheet_returns_none(self):
        logging.disable(logging.CRITICAL)
        try:
            self.assertIsNone(self.a.tile("terrain/tileset/nope.png", 0))
        finally:
            logging.disable(logging.NOTSET)

    def test_out_of_range_index_returns_none(self):
        self.assertIsNone(self.a.tile(self.sheet, 999))

    def test_decoration_rigs_visible_via_frames(self):
        for name, rig in get_content().terrain["rigs"].items():
            n = rig["anims"]["loop"]["frames"]
            frs = self.a.frames(name, "loop")
            self.assertEqual(len(frs), n, name)
            self.assertEqual(frs[0].get_size(), tuple(rig["frame"]))

    def test_slot_helper_via_terrain(self):
        self.assertEqual(self.a.terrain["slots"]["interior"], 10)


class ObstacleDecorTests(unittest.TestCase):
    """Obstacles render as decoration sprites scaled to their collider; there is
    no decoration without an obstacle attached (T4, revised)."""

    @classmethod
    def setUpClass(cls):
        _display()

    def _map(self, seed=1234):
        from world.map import GameMap
        gm = GameMap(seed=seed)
        gm._build_tiles()
        self.assertTrue(gm._tiles_ok, "tileset assets absent -- cannot test decor")
        return gm

    def test_worldlayout_has_no_standalone_decoration_field(self):
        from world.procedural import WorldLayout, generate_world
        self.assertNotIn("decorations", WorldLayout.__dataclass_fields__)
        self.assertFalse(hasattr(generate_world(7), "decorations"))

    def test_every_obstacle_is_skinned_and_keys_are_obstacle_indices(self):
        gm = self._map()
        self.assertTrue(gm.obstacles)
        # all four obstacle kinds are mapped -> every obstacle gets a sprite
        self.assertEqual(len(gm._decos), len(gm.obstacles))
        self.assertTrue(set(gm._decos).issubset(range(len(gm.obstacles))))

    def test_sprite_width_matches_the_scaling_formula(self):
        gm = self._map()
        t = get_content().terrain
        boost = t["obstacle_decor"]["size_boost"]
        for i, (ax, ay, fps, frs) in gm._decos.items():
            o = gm.obstacles[i]
            rig = t["obstacle_decor"]["rigs"][o.kind][(o.variant - 1) % 4]
            meta = t["rigs"][rig]
            fw = meta["frame"][0]
            expected = max(1, round(fw * (2.0 * o.radius * boost) / meta["footprint"]))
            self.assertAlmostEqual(frs[0].get_width(), expected, delta=1,
                                   msg=f"{o.kind} r{o.radius} via {rig}")

    def test_bigger_collider_yields_a_bigger_sprite_in_the_same_family(self):
        gm = self._map()
        # rocks (r30) and pillars (r22) share the rock rigs: variant-for-variant
        # a rock's skin is wider than a pillar's.
        widths: dict[int, dict[str, int]] = {}
        for i, entry in gm._decos.items():
            o = gm.obstacles[i]
            if o.kind in ("rock", "pillar"):
                widths.setdefault(o.variant, {})[o.kind] = entry[3][0].get_width()
        compared = 0
        for d in widths.values():
            if "rock" in d and "pillar" in d:
                compared += 1
                self.assertGreater(d["rock"], d["pillar"])
        self.assertGreater(compared, 0, "no rock/pillar variant pair to compare")

    def test_deterministic(self):
        a, b = self._map(99), self._map(99)
        self.assertEqual([o.variant for o in a.obstacles],
                         [o.variant for o in b.obstacles])
        self.assertEqual({i: e[3][0].get_size() for i, e in a._decos.items()},
                         {i: e[3][0].get_size() for i, e in b._decos.items()})

    def test_obstacle_variants_in_range(self):
        from world.procedural import generate_world
        for seed in (1, 2, 3, 1234):
            self.assertTrue(all(o.variant in (1, 2, 3, 4)
                                for o in generate_world(seed).obstacles))

    def test_skinning_adds_no_collider_and_leaves_walkability_intact(self):
        import pygame as pg
        gm = self._map()
        self.assertIs(gm.obstacles, gm.layout.obstacles)          # same list, untouched
        o = gm.obstacles[0]
        self.assertFalse(gm.is_walkable(pg.Vector2(o.pos.x, o.pos.y)))

    def test_flag_off_falls_back_to_circles(self):
        from game import config
        from world.map import GameMap
        old = config.TERRAIN_DECORATIONS
        config.TERRAIN_DECORATIONS = False
        try:
            gm = GameMap(seed=1234)
            gm._build_tiles()
            self.assertEqual(gm._decos, {})
        finally:
            config.TERRAIN_DECORATIONS = old

    def test_build_headless(self):
        gm = self._map(42)
        self.assertGreater(len(gm._decos), 0)
        for ax, ay, fps, frs in gm._decos.values():
            self.assertGreater(len(frs), 0)


class TerrainSurfaceAlphaTests(unittest.TestCase):
    """T6: baked room / corridor surfaces carry per-pixel alpha so the autotile
    edge tiles' transparent water side survives the bake (no black ring), and
    foam is composited *behind* the terrain."""

    @classmethod
    def setUpClass(cls):
        _display()

    def _map(self, seed=1234):
        from world.map import GameMap
        gm = GameMap(seed=seed)
        gm._build_tiles()
        self.assertTrue(gm._tiles_ok, "tileset assets absent")
        return gm

    def test_room_and_corridor_bakes_are_srcalpha_32bit(self):
        gm = self._map()
        surfs = list(gm._room_surfs.values()) + [s for _, s in gm._corr_surfs]
        self.assertTrue(surfs)
        for s in surfs:
            self.assertTrue(s.get_flags() & pygame.SRCALPHA, "not SRCALPHA")
            self.assertEqual(s.get_bitsize(), 32)

    def test_water_buffer_stays_opaque(self):
        gm = self._map()
        self.assertIsNotNone(gm._water_buf)
        self.assertFalse(gm._water_buf.get_flags() & pygame.SRCALPHA)

    def test_autotile_edge_transparency_survives_the_bake(self):
        gm = self._map()
        # Every room's (0,0) cell is corner_nw and its top row is edge_n -- both
        # transparent on the water side. With an opaque .convert() bake these
        # would all be alpha 255 (black-filled).
        bled = 0
        for surf in gm._room_surfs.values():
            w = surf.get_width()
            bled += sum(1 for x in range(0, w, 4) if surf.get_at((x, 0))[3] < 255)
        self.assertGreater(bled, 0, "top edge of every room baked fully opaque")

    def test_draw_tiled_blits_foam_before_the_room_surfaces(self):
        from systems.camera import Camera
        gm = self._map()
        self.assertTrue(gm._foam, "foam frames not loaded")
        cam = Camera(gm.width, gm.height)
        cam.snap_to(gm.center)

        class _Recorder:                         # blit() is read-only on a real Surface
            def __init__(self): self.calls = []
            def blit(self, src, *a, **k): self.calls.append(src)
            def fill(self, *a, **k): pass

        rec = _Recorder()
        gm._draw_tiled(rec, cam)

        foam_set = set(map(id, gm._foam))
        room_set = set(map(id, gm._room_surfs.values()))
        first_foam = next((i for i, s in enumerate(rec.calls) if id(s) in foam_set), None)
        first_room = next((i for i, s in enumerate(rec.calls) if id(s) in room_set), None)
        self.assertIsNotNone(first_foam, "no foam blit")
        self.assertIsNotNone(first_room, "no room blit")
        self.assertLess(first_foam, first_room)


class BridgeCorridorTests(unittest.TestCase):
    """T7: corridors render from Bridge_All.png (its own grid), directional."""

    @classmethod
    def setUpClass(cls):
        _display()
        cls.t = get_content().terrain

    def test_bridge_block_is_coherent(self):
        b = self.t["bridge"]
        self.assertTrue((ASSETS_DIR / b["sheet"]).is_file(), b["sheet"])
        limit = b["grid"][0] * b["grid"][1]
        for name, idx in b["slots"].items():
            self.assertTrue(0 <= idx < limit, f"{name}={idx} outside {limit}")
        for req in ("h_left", "h_mid", "h_right", "v_top", "v_mid", "v_bot"):
            self.assertIn(req, b["slots"])

    def test_bridge_slot_helper_picks_end_caps_and_mid(self):
        from world.map import GameMap
        bs = GameMap._bridge_slot
        self.assertEqual(bs(True, 0, 0, 1, 5), "h_left")
        self.assertEqual(bs(True, 0, 4, 1, 5), "h_right")
        self.assertEqual(bs(True, 0, 2, 1, 5), "h_mid")
        self.assertEqual(bs(False, 0, 0, 5, 1), "v_top")
        self.assertEqual(bs(False, 4, 0, 5, 1), "v_bot")
        self.assertEqual(bs(False, 2, 0, 5, 1), "v_mid")

    def test_tile_slices_bridge_sheet_with_its_own_grid(self):
        from game.assets import Assets, reset_assets
        reset_assets()
        a = Assets()
        b = self.t["bridge"]
        bcols = b["grid"][0]
        for idx in b["slots"].values():
            surf = a.tile(b["sheet"], idx, cols=bcols)
            self.assertIsInstance(surf, pygame.Surface, f"bridge idx {idx}")
            self.assertEqual(surf.get_size(), (self.t["tile_px"], self.t["tile_px"]))
        # v_top (index 3) with the wrong (floor) grid width falls off the sheet
        logging.disable(logging.CRITICAL)
        try:
            self.assertIsNone(a.tile(b["sheet"], b["slots"]["v_top"]))  # cols defaults to 9
        finally:
            logging.disable(logging.NOTSET)

    def test_corridors_bake_srcalpha_and_seed_the_shore(self):
        from world.map import GameMap
        gm = GameMap(seed=1234)
        gm._build_tiles()
        self.assertTrue(gm._tiles_ok and gm._corr_surfs)
        for _, s in gm._corr_surfs:
            self.assertTrue(s.get_flags() & pygame.SRCALPHA)
        # Some mid-bridge cell survives into the shore list (plank-gap foam);
        # the T9 doorway-seam filter only strips the room/bridge junction.
        in_a_corridor = [p for p in gm._shore
                         if any(rect.collidepoint(p[0] + 1, p[1] + 1)
                                for rect, _ in gm._corr_surfs)]
        self.assertTrue(in_a_corridor, "no corridor cell seeded the shore")


class DecorationScatterTests(unittest.TestCase):
    """T8: seeded non-colliding scenery -- interior clutter + void water
    scenery -- data-driven from terrain.json "decorations", gated by
    config.TERRAIN_DECOR, with no effect on walkability."""

    @classmethod
    def setUpClass(cls):
        _display()

    def _map(self, seed=1234):
        from world.map import GameMap
        gm = GameMap(seed=seed)
        gm._build_tiles()
        self.assertTrue(gm._tiles_ok, "tileset assets absent")
        return gm

    def test_scatter_is_deterministic_per_seed(self):
        a, b = self._map(99), self._map(99)
        pa = {rid: [i[4:] for i in inst] for rid, inst in a._room_decor.items()}
        pb = {rid: [i[4:] for i in inst] for rid, inst in b._room_decor.items()}
        self.assertEqual(pa, pb)
        self.assertEqual([i[4:] for i in a._void_decor],
                         [i[4:] for i in b._void_decor])

    def test_something_is_placed(self):
        gm = self._map(7)
        self.assertTrue(gm._room_decor, "no interior clutter placed anywhere")
        self.assertTrue(gm._void_decor, "no void scenery placed")

    def test_room_clutter_lands_on_interior_cells_clear_of_the_centre(self):
        gm = self._map(1234)
        px = 64
        for rid, inst in gm._room_decor.items():
            r = gm.layout.room(rid).rect
            cx, cy = r.center
            clear = min(r.width, r.height) * 0.22
            for _frs, _ax, _ay, _fps, x, y in inst:
                self.assertTrue(r.collidepoint(x, y), "clutter outside its room")
                self.assertGreaterEqual(x, r.x + px)      # not on the perimeter col
                self.assertLess(x, r.right - px)
                self.assertGreaterEqual(y, r.y + px)      # not on the perimeter row
                self.assertLess(y, r.bottom - px)
                self.assertGreater((x - cx) ** 2 + (y - cy) ** 2, clear ** 2)

    def test_void_scenery_is_off_every_room_and_corridor(self):
        gm = self._map(1234)
        self.assertTrue(gm._void_decor)
        for _frs, _ax, _ay, _fps, x, y in gm._void_decor:
            self.assertFalse(gm._point_ok(x, y), "void deco on walkable ground")

    def test_scatter_does_not_touch_walkability_or_obstacles(self):
        from game import config
        gm_on = self._map(1234)
        old = config.TERRAIN_DECOR
        config.TERRAIN_DECOR = False
        try:
            gm_off = self._map(1234)
        finally:
            config.TERRAIN_DECOR = old
        self.assertIs(gm_on.obstacles, gm_on.layout.obstacles)
        self.assertEqual(len(gm_on.obstacles), len(gm_off.obstacles))
        b = gm_on.layout.bounds
        for i in range(0, b.width, 137):
            for j in range(0, b.height, 149):
                p = pygame.Vector2(b.x + i, b.y + j)
                self.assertEqual(gm_on.is_walkable(p), gm_off.is_walkable(p))

    def test_flag_off_yields_no_scatter(self):
        from game import config
        old = config.TERRAIN_DECOR
        config.TERRAIN_DECOR = False
        try:
            gm = self._map(1234)
            self.assertEqual(gm._room_decor, {})
            self.assertEqual(gm._void_decor, [])
        finally:
            config.TERRAIN_DECOR = old

    def test_every_instance_resolves_to_real_frames(self):
        gm = self._map(42)
        allinst = list(gm._void_decor)
        for inst in gm._room_decor.values():
            allinst += inst
        self.assertTrue(allinst)
        for frs, ax, ay, fps, x, y in allinst:
            self.assertTrue(frs and all(isinstance(f, pygame.Surface) for f in frs))
            self.assertGreaterEqual(fps, 0.0)

    def test_void_scenery_draws_before_the_foam(self):
        from systems.camera import Camera
        gm = self._map(1234)
        self.assertTrue(gm._void_decor and gm._foam)
        cam = Camera(gm.width, gm.height)
        cam.snap_to(pygame.Vector2(gm._void_decor[0][4], gm._void_decor[0][5]))

        class _Recorder:
            def __init__(self): self.calls = []
            def blit(self, src, *a, **k): self.calls.append(id(src))
            def fill(self, *a, **k): pass

        rec = _Recorder()
        gm._draw_tiled(rec, cam)
        void_ids = {id(f) for _f in gm._void_decor for f in _f[0]}
        foam_ids = set(map(id, gm._foam))
        first_void = next((k for k, s in enumerate(rec.calls) if s in void_ids), None)
        first_foam = next((k for k, s in enumerate(rec.calls) if s in foam_ids), None)
        self.assertIsNotNone(first_void, "void scenery never blitted")
        self.assertIsNotNone(first_foam, "foam never blitted")
        self.assertLess(first_void, first_foam)


class TreeSkinShadowSeamTests(unittest.TestCase):
    """T9: real animated tree sprites skin the `tree` obstacle, a soft contact
    shadow sits under every skinned obstacle, and foam is dropped at the
    bridge/room doorway seam."""

    @classmethod
    def setUpClass(cls):
        _display()
        cls.t = get_content().terrain

    def _map(self, seed=1234):
        from world.map import GameMap
        gm = GameMap(seed=seed)
        gm._build_tiles()
        self.assertTrue(gm._tiles_ok, "tileset assets absent")
        return gm

    def test_tree_kind_maps_to_tree_rigs(self):
        rigs = self.t["obstacle_decor"]["rigs"]
        self.assertEqual(rigs["tree"],
                         ["deco_tree_1", "deco_tree_2", "deco_tree_3", "deco_tree_4"])
        self.assertEqual(rigs["shrub"][0], "deco_bush_1")     # shrubs keep bushes
        for name in rigs["tree"]:
            rig = self.t["rigs"][name]
            self.assertTrue((ASSETS_DIR / rig["anims"]["loop"]["file"]).is_file())
            self.assertEqual(rig["anims"]["loop"]["frames"], 8)
            self.assertGreater(int(rig["footprint"]), 0)

    def test_tree_skin_is_animated_and_scaled_to_the_collider(self):
        gm = self._map(7)
        seen = 0
        for i, (ax, ay, fps, frs) in gm._decos.items():
            if gm.obstacles[i].kind != "tree":
                continue
            seen += 1
            self.assertEqual(len(frs), 8)
            self.assertGreater(fps, 0.0)
        self.assertGreater(seen, 0, "no tree obstacle skinned")

    def test_tree_obstacle_still_blocks_movement(self):
        import pygame as pg
        gm = self._map(7)
        trees = [o for o in gm.obstacles if o.kind == "tree"]
        self.assertTrue(trees)
        self.assertFalse(gm.is_walkable(pg.Vector2(trees[0].pos.x, trees[0].pos.y)))

    def test_shadow_under_every_skinned_obstacle_and_squashed(self):
        gm = self._map()
        self.assertTrue(gm._obst_shadow)
        self.assertEqual(set(gm._obst_shadow), set(gm._decos))
        for surf in gm._obst_shadow.values():
            self.assertIsInstance(surf, pygame.Surface)
            self.assertGreater(surf.get_width(), surf.get_height())   # oblique squash

    def test_shadow_flag_off_keeps_skins_but_drops_shadows(self):
        from game import config
        old = config.TERRAIN_SHADOWS
        config.TERRAIN_SHADOWS = False
        try:
            gm = self._map()
            self.assertTrue(gm._decos)
            self.assertEqual(gm._obst_shadow, {})
        finally:
            config.TERRAIN_SHADOWS = old

    def test_shadow_is_drawn_before_the_skin(self):
        from systems.camera import Camera
        gm = self._map()
        i = next(iter(gm._obst_shadow))
        o = gm.obstacles[i]
        cam = Camera(gm.width, gm.height)
        cam.snap_to(o.pos)

        class _Recorder:
            def __init__(self): self.calls = []
            def blit(self, src, *a, **k): self.calls.append(id(src))
            def fill(self, *a, **k): pass

        rec = _Recorder()
        gm._draw_obstacles(rec, cam)
        shadow_i = rec.calls.index(id(gm._obst_shadow[i]))
        skin_ids = {id(f) for f in gm._decos[i][3]}
        skin_i = next(k for k, s in enumerate(rec.calls) if s in skin_ids)
        self.assertLess(shadow_i, skin_i)

    def test_no_foam_cell_straddles_a_bridge_and_a_room(self):
        gm = self._map(1234)
        px = self.t["tile_px"]
        corr = [rect for rect, _ in gm._corr_surfs]
        rooms = [r.rect for r in gm.layout.rooms]
        for sx, sy in gm._shore:
            c = pygame.Rect(sx, sy, px, px)
            on_bridge = any(c.colliderect(h.inflate(px, px)) for h in corr)
            in_room = any(c.colliderect(h) for h in rooms)
            self.assertFalse(on_bridge and in_room,
                             f"doorway-seam foam left at ({sx}, {sy})")

    def test_seam_filter_keeps_open_room_edges(self):
        # A world still has plenty of shoreline after the seam trim.
        gm = self._map(1234)
        self.assertGreater(len(gm._shore), 100)


if __name__ == "__main__":
    unittest.main()
