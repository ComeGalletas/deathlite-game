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

from game import config
from game.assets import ASSETS_DIR, Assets, reset_assets
from game.content import get_content


# The pinned-seed render checks here validate the terrain renderer against the
# flat base layout; LD-2 verticality shifts the RNG stream and adds cliff /
# stair passes, and has its own coverage in tests/world/test_verticality.py.
_SAVED_VERT = None


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


def setUpModule():
    _pin_heightmap_off()
    global _SAVED_VERT
    _SAVED_VERT = config.WORLD_VERTICALITY
    config.WORLD_VERTICALITY = False


def tearDownModule():
    _restore_heightmap()
    config.WORLD_VERTICALITY = _SAVED_VERT


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

    def test_foam_has_three_distinct_animation_routines(self):
        routines = self.t["foam_routines"]
        self.assertGreaterEqual(len(routines), 3)
        self.assertGreaterEqual(len({float(r["fps"]) for r in routines}), 3)

    def test_trees_have_three_distinct_animation_routines(self):
        """Same reason as the foam: one clock for every instance makes a whole
        forest breathe in step, which reads as one object rather than many."""
        routines = self.t["tree_routines"]
        self.assertGreaterEqual(len(routines), 3)
        self.assertGreaterEqual(len({float(r["fps"]) for r in routines}), 3)
        self.assertGreaterEqual(len({int(r["phase"]) for r in routines}), 3)

    def test_slot_indices_are_inside_the_grid(self):
        cols, rows = self.t["grid"]
        limit = cols * rows

        def _indices(v):
            if isinstance(v, dict):                     # e.g. slots.cliff
                for inner in v.values():
                    yield from _indices(inner)
            elif isinstance(v, list):
                yield from v
            else:
                yield v

        for name, val in self.t["slots"].items():
            for idx in _indices(val):
                self.assertTrue(0 <= idx < limit, f"slot {name}={idx} out of 0..{limit - 1}")

    def test_cliff_slots_are_a_full_left_mid_right_single_autotile(self):
        cliff = self.t["slots"]["cliff"]
        self.assertEqual(set(cliff), {"top", "body", "bottom"})
        for row, edges in cliff.items():
            self.assertEqual(set(edges), {"left", "mid", "right", "single"}, row)

    def test_floor_sheets_are_real_files(self):
        for path in self.t.get("floor_sheets", {}).values():
            self.assertTrue((ASSETS_DIR / path).is_file(), f"missing {path}")

    def test_vstair_overlay_sprite_is_a_real_srcalpha_file(self):
        vs = self.t.get("vstair", {})
        self.assertIn("sheet", vs)
        p = ASSETS_DIR / vs["sheet"]
        self.assertTrue(p.is_file(), f"missing {vs['sheet']}")
        surf = pygame.image.load(str(p))
        w, h = surf.get_size()
        self.assertTrue(64 <= w <= 512 and 64 <= h <= 512, (w, h))
        # the prep script keys the backdrop out -> real transparency
        self.assertLess(surf.convert_alpha().get_at((0, 0))[3], 40)

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
            self.assertIn(e["placement"],
                          ("room_interior", "void", "room_edge", "shore", "lake"))
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

    def test_foam_anchors_stay_on_ground_edges_or_void_cliff_feet(self):
        from game import config
        gm = self._map()
        px = config.TILE_PX
        self.assertTrue(gm._shore)
        for x, y in gm._shore:
            cx, cy = x + px / 2, y + px / 2
            self.assertTrue(gm._point_ok(cx, cy), "foam anchor is not under ground")
            self.assertTrue(any(not gm._point_ok(cx + dx, cy + dy)
                                for dx, dy in ((px, 0), (-px, 0), (0, px), (0, -px))),
                            "foam ground tile no longer borders empty sea")
        for x, y, _f in gm._cliff_foam:
            self.assertFalse(gm._point_ok(x + px / 2, y + px / 2),
                             "void-facing cliff foam is on walkable ground")

    def test_every_sea_facing_ground_room_tile_has_foam(self):
        from game import config
        gm = self._map()
        px = config.TILE_PX
        expected = set()
        for room in gm.layout.rooms:
            if room.floor != 0:
                continue
            for col, row in room.cells:
                x, y = room.rect.x + col * px, room.rect.y + row * px
                if any(not gm._point_ok(x + px / 2 + dx, y + px / 2 + dy)
                       for dx, dy in ((px, 0), (-px, 0), (0, px), (0, -px))):
                    expected.add((x, y))
        self.assertTrue(expected)
        self.assertTrue(expected.issubset(set(gm._shore)))

    def test_every_obstacle_is_skinned_and_keys_are_obstacle_indices(self):
        gm = self._map()
        self.assertTrue(gm.obstacles)
        # every obstacle kind is mapped -> every obstacle gets a sprite
        self.assertEqual(len(gm._decos), len(gm.obstacles))
        self.assertTrue(set(gm._decos).issubset(range(len(gm.obstacles))))

    def test_sprite_width_matches_the_scaling_formula(self):
        gm = self._map()
        t = get_content().terrain
        boost = t["obstacle_decor"]["size_boost"]
        render_radius = t["obstacle_decor"].get("render_radius", {})
        for i, (ax, ay, fps, frs, phase) in gm._decos.items():
            o = gm.obstacles[i]
            choices = t["obstacle_decor"]["rigs"][o.kind]
            rig = choices[(o.variant - 1) % len(choices)]
            meta = t["rigs"][rig]
            fw = meta["frame"][0]
            draw_r = render_radius.get(o.kind, o.radius)
            expected = max(1, round(fw * (2.0 * draw_r * boost) / meta["footprint"]))
            self.assertAlmostEqual(frs[0].get_width(), expected, delta=1,
                                   msg=f"{o.kind} r{o.radius} draw_r{draw_r} via {rig}")

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
        # Small obstacles carry a 1..4 cosmetic variant; a `house` encodes its
        # colour band + type as 1..15 (see world/procedural._scatter_houses).
        from world.procedural import generate_world
        for seed in (1, 2, 3, 1234):
            for o in generate_world(seed).obstacles:
                hi = 15 if o.kind == "house" else 4
                self.assertIn(o.variant, range(1, hi + 1),
                              msg=f"{o.kind} variant {o.variant}")

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
        for ax, ay, fps, frs, phase in gm._decos.values():
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
        surfs = list(gm._room_surfs.values()) + [s for _r, s, _f in gm._corr_surfs]
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

    def test_zoom_does_not_invent_partial_alpha_at_tile_edges(self):
        from world.map import GameMap

        source = pygame.Surface((2, 2), pygame.SRCALPHA)
        source.set_at((0, 0), (80, 120, 90, 255))
        gm = GameMap.__new__(GameMap)
        gm._render_zoom = 1.5
        gm._blit_cache = {}

        scaled = gm.renderer._z_surf(source)
        alphas = {scaled.get_at((x, y)).a
                  for y in range(scaled.get_height())
                  for x in range(scaled.get_width())}
        self.assertLessEqual(alphas, {0, 255})

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
        gm.renderer._draw_tiled(rec, cam)

        foam_set = set(map(id, gm._foam))
        room_set = set(map(id, gm._room_surfs.values()))
        first_foam = next((i for i, s in enumerate(rec.calls) if id(s) in foam_set), None)
        first_room = next((i for i, s in enumerate(rec.calls) if id(s) in room_set), None)
        self.assertIsNotNone(first_foam, "no foam blit")
        self.assertIsNotNone(first_room, "no room blit")
        self.assertLess(first_foam, first_room)

    def test_foam_locations_use_three_desynchronized_routines(self):
        gm = self._map()
        anchors = gm._shore + [(x, y) for x, y, _f in gm._cliff_foam]
        buckets = {gm._foam_routine_index(x, y, len(gm._foam_routines))
                   for x, y in anchors}
        self.assertTrue({0, 1, 2}.issubset(buckets))

        by_bucket = {
            bucket: next(p for p in anchors
                         if gm._foam_routine_index(*p, len(gm._foam_routines)) == bucket)
            for bucket in (0, 1, 2)
        }
        frames = {id(gm._foam_frame_at(*by_bucket[bucket], seconds=0.0))
                  for bucket in (0, 1, 2)}
        self.assertEqual(len(frames), 3, "foam routines start on the same frame")


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
        self.assertEqual(bs("h", 0, 5), "h_left")
        self.assertEqual(bs("h", 4, 5), "h_right")
        self.assertEqual(bs("h", 2, 5), "h_mid")
        self.assertEqual(bs("v", 0, 5), "v_top")
        self.assertEqual(bs("v", 4, 5), "v_bot")
        self.assertEqual(bs("v", 2, 5), "v_mid")
        self.assertEqual(bs("h", 0, 1), "h_mid")           # degenerate single cell

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

    def test_corridors_bake_srcalpha_without_seeding_the_shore(self):
        from world.map import GameMap
        gm = GameMap(seed=1234)
        gm._build_tiles()
        self.assertTrue(gm._tiles_ok and gm._corr_surfs)
        for _r, s, _f in gm._corr_surfs:
            self.assertTrue(s.get_flags() & pygame.SRCALPHA)
        px = get_content().terrain["tile_px"]
        ground_cells = {
            (room.rect.x + col * px, room.rect.y + row * px)
            for room in gm.layout.rooms if room.floor == 0
            for col, row in room.cells
        }
        self.assertTrue(set(gm._shore).issubset(ground_cells),
                        "a corridor-only cell seeded shoreline foam")

    def test_corridor_carries_bridge_edge_properties(self):
        from world.procedural import generate_world
        for seed in (1, 7, 99, 1234):
            w = generate_world(seed)
            for c in w.corridors:
                self.assertIn(c.axis, ("h", "v"))
                self.assertEqual((c.end_low, c.end_high),
                                 ("west", "east") if c.axis == "h"
                                 else ("north", "south"))
                self.assertEqual({c.room_low, c.room_high}, {c.a, c.b})
                lo, hi = w.room(c.room_low).rect, w.room(c.room_high).rect
                if c.axis == "h":
                    self.assertLess(lo.centerx, hi.centerx)
                else:
                    self.assertLess(lo.centery, hi.centery)

    def test_bridge_bakes_the_matching_end_cap_at_each_mouth(self):
        from game.assets import Assets, reset_assets
        from world.map import GameMap
        reset_assets()
        a = Assets()
        b = self.t["bridge"]
        bcols = b["grid"][0]
        want = {name: pygame.image.tostring(a.tile(b["sheet"], idx, cols=bcols), "RGBA")
                for name, idx in b["slots"].items()}
        px = self.t["tile_px"]

        gm = GameMap(seed=1234)
        gm._build_tiles()
        self.assertTrue(gm._corr_surfs)
        checked_h = checked_v = 0
        for c, (rect, surf, _f) in zip(gm.layout.corridors, gm._corr_surfs):
            if c.axis == "h":
                first = surf.subsurface((0, 0, px, px))
                last = surf.subsurface((surf.get_width() - px, 0, px, px))
                lo_name, hi_name = "h_left", "h_right"
                checked_h += 1
            else:
                first = surf.subsurface((0, 0, px, px))
                last = surf.subsurface((0, surf.get_height() - px, px, px))
                lo_name, hi_name = "v_top", "v_bot"
                checked_v += 1
            self.assertEqual(pygame.image.tostring(first, "RGBA"), want[lo_name],
                             f"corridor {c.a}-{c.b}: wrong low-end cap")
            self.assertEqual(pygame.image.tostring(last, "RGBA"), want[hi_name],
                             f"corridor {c.a}-{c.b}: wrong high-end cap")
        self.assertTrue(checked_h and checked_v, "need both axes in the sample")

    def test_bridge_surface_overlaps_one_tile_into_each_room(self):
        from world.map import GameMap
        px = self.t["tile_px"]
        gm = GameMap(seed=1234)
        gm._build_tiles()
        for c, (rect, _surf, _f) in zip(gm.layout.corridors, gm._corr_surfs):
            lo = gm.layout.room(c.room_low).rect
            hi = gm.layout.room(c.room_high).rect
            if c.axis == "h":
                # ends reach ~one tile past each room edge, not the room centres
                self.assertLess(rect.left, lo.right)
                self.assertGreaterEqual(rect.left, lo.right - 2 * px)
                self.assertGreater(rect.right, hi.left)
                self.assertLessEqual(rect.right, hi.left + 2 * px)
                self.assertLess(rect.width, c.rect.width)
            else:
                self.assertLess(rect.top, lo.bottom)
                self.assertGreaterEqual(rect.top, lo.bottom - 2 * px)
                self.assertGreater(rect.bottom, hi.top)
                self.assertLessEqual(rect.bottom, hi.top + 2 * px)
                self.assertLess(rect.height, c.rect.height)


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
            room = gm.layout.room(rid)
            r = room.rect
            cx, cy = room.center                          # centroid for shaped rooms
            clear = min(r.width, r.height) * 0.22
            for _frs, _ax, _ay, _fps, x, y in inst:
                self.assertTrue(r.collidepoint(x, y), "clutter outside its room")
                cell = (int((x - r.left) // px), int((y - r.top) // px))
                self.assertIn(cell, room.cells, "clutter on a bitten-out cell")
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

    def test_min_gap_lets_small_flora_cluster_but_not_bushes(self):
        # `min_gap` on an entry lowers the in-room separation (mushrooms/flowers
        # form patches); an entry without it keeps the 40 px default (bushes).
        import math
        t = get_content().terrain
        bush = t["rigs"]["deco_bush_1"]
        bush_size = (round(bush["frame"][0] * 0.75), round(bush["frame"][1] * 0.75))
        clustered = False
        for seed in (1, 7, 42, 99, 1234):
            gm = self._map(seed)
            for inst in gm._room_decor.values():
                pts = [(x, y) for *_r, x, y in inst]
                for i in range(len(pts)):
                    for j in range(i + 1, len(pts)):
                        if math.dist(pts[i], pts[j]) < 38:
                            clustered = True
                bushes = [(x, y) for frs, _ax, _ay, _fps, x, y in inst
                          if frs[0].get_size() == bush_size]
                for i in range(len(bushes)):
                    for j in range(i + 1, len(bushes)):
                        self.assertGreaterEqual(math.dist(bushes[i], bushes[j]), 39,
                                                f"bushes bunched (seed {seed})")
        self.assertTrue(clustered, "no decoration cluster formed anywhere")

    def test_foam_draws_before_void_scenery(self):
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
        gm.renderer._draw_tiled(rec, cam)
        void_ids = {id(f) for _f in gm._void_decor for f in _f[0]}
        foam_ids = set(map(id, gm._foam))
        first_void = next((k for k, s in enumerate(rec.calls) if s in void_ids), None)
        first_foam = next((k for k, s in enumerate(rec.calls) if s in foam_ids), None)
        self.assertIsNotNone(first_void, "void scenery never blitted")
        self.assertIsNotNone(first_foam, "foam never blitted")
        self.assertLess(first_foam, first_void)


class TreeSkinShadowSeamTests(unittest.TestCase):
    """T9 / B3: real animated tree sprites skin the `tree` obstacle; only trees
    cast a depth-sorted round shade; foam is dropped at the bridge/room doorway
    seam."""

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
        """Every rig the `tree` obstacle draws from has to exist, animate, and
        be laid out as a **horizontal strip**.

        This used to pin the exact four names and demand exactly eight frames
        each, which said nothing about whether they were usable and refused a
        fifth tree for having six frames. The strip geometry is the real
        constraint: `Assets.frames` slices `frames` cells of `frame[0]` px
        across, so a sheet whose width is not that product silently yields
        blank or clipped frames. `tree_sheet.png` arrived as a 4x3 *grid* and
        would have done exactly that.
        """
        rigs = self.t["obstacle_decor"]["rigs"]
        self.assertGreaterEqual(len(rigs["tree"]), 4)
        self.assertNotIn("shrub", rigs)     # bushes are decoration now, not an obstacle
        for name in rigs["tree"]:
            rig = self.t["rigs"][name]
            loop = rig["anims"]["loop"]
            path = ASSETS_DIR / loop["file"]
            self.assertTrue(path.is_file(), name)
            self.assertGreater(loop["frames"], 1, f"{name} does not animate")
            sheet = pygame.image.load(str(path))
            self.assertEqual(sheet.get_width(), rig["frame"][0] * loop["frames"],
                             f"{name}: sheet is not a strip of "
                             f"{loop['frames']} x {rig['frame'][0]} px")
            self.assertEqual(sheet.get_height(), rig["frame"][1], name)
            self.assertGreater(int(rig["footprint"]), 0)

    def test_a_grove_does_not_sway_in_lock_step(self):
        """The trees of one world have to be spread over the declared routines
        -- if they all landed on one, the whole forest would still animate as a
        single object, which is what this exists to prevent."""
        gm = self._map(7)
        declared = {(float(r["fps"]), int(r["phase"]))
                    for r in get_content().terrain["tree_routines"]}
        got = {(e[2], e[4]) for i, e in gm._decos.items()
               if gm.obstacles[i].kind == "tree" and len(e[3]) > 1}
        self.assertTrue(got <= declared,
                        f"a tree is swaying on an undeclared routine: "
                        f"{got - declared}")
        self.assertEqual(got, declared, "some routine went unused")

    def test_a_tree_keeps_its_routine_across_a_rebake(self):
        """It is bucketed on where the tree stands, not on anything the bake
        makes up, so the same seed animates identically twice running."""
        a, b = self._map(7), self._map(7)
        self.assertEqual({i: (e[2], e[4]) for i, e in a._decos.items()},
                         {i: (e[2], e[4]) for i, e in b._decos.items()})

    def test_only_trees_take_a_routine(self):
        """A rock has one frame and nothing to offset; giving it a phase would
        index off the end of its own list."""
        gm = self._map(7)
        for i, e in gm._decos.items():
            if gm.obstacles[i].kind != "tree" or len(e[3]) <= 1:
                self.assertEqual(e[4], 0, gm.obstacles[i].kind)

    def test_tree_skin_is_animated_and_scaled_to_the_collider(self):
        gm = self._map(7)
        seen = 0
        for i, (ax, ay, fps, frs, phase) in gm._decos.items():
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

    def test_only_trees_cast_a_shade_and_no_under_skin_shadow(self):
        gm = self._map()
        self.assertFalse(hasattr(gm, "_obst_shadow"),
                         "the per-obstacle contact shadow was removed")
        self.assertTrue(gm._tree_shadows)
        tree_idx = {i for i, o in enumerate(gm.obstacles)
                    if o.kind == "tree" and i in gm._decos}
        self.assertEqual(set(gm._tree_shadows), tree_idx)
        padding = int(self.t["obstacle_decor"]["tree_shadow"]["radius_padding"])
        radius_scale = float(self.t["obstacle_decor"]["tree_shadow"]["radius_scale"])
        render_radius = self.t["obstacle_decor"].get("render_radius", {})
        for i, (wx, wy, r, surf) in gm._tree_shadows.items():
            self.assertIsInstance(surf, pygame.Surface)
            self.assertTrue(surf.get_flags() & pygame.SRCALPHA)
            self.assertEqual(surf.get_size(), (2 * r, 2 * r))
            draw_r = float(render_radius.get("tree", gm.obstacles[i].radius))
            self.assertEqual(r, round(draw_r * radius_scale) + padding)
            self.assertLess(surf.get_at((r, r))[3], 200)

    def test_shade_flag_off_keeps_skins_but_drops_the_shade(self):
        from game import config
        old = config.TERRAIN_SHADOWS
        config.TERRAIN_SHADOWS = False
        try:
            gm = self._map()
            self.assertTrue(gm._decos)
            self.assertEqual(gm._tree_shadows, {})
        finally:
            config.TERRAIN_SHADOWS = old

    def test_draw_obstacles_blits_only_skins_no_shadow(self):
        from systems.camera import Camera
        gm = self._map()
        i = next(i for i, o in enumerate(gm.obstacles)
                 if o.kind == "tree" and i in gm._decos)
        cam = Camera(gm.width, gm.height)
        cam.snap_to(gm.obstacles[i].pos)

        class _Recorder:
            def __init__(self): self.calls = []
            def blit(self, src, *a, **k): self.calls.append(id(src))
            def fill(self, *a, **k): pass

        rec = _Recorder()
        gm.renderer._draw_obstacles(rec, cam)
        skin_ids = {id(f) for e in gm._decos.values() for f in e[3]}
        self.assertTrue(rec.calls)
        self.assertTrue(all(c in skin_ids for c in rec.calls),
                        "_draw_obstacles blitted something other than a skin frame")

    def test_obstacle_skin_is_seated_below_the_collider_by_the_drop(self):
        from game import config
        from systems.camera import Camera
        gm = self._map()
        # a kind driven by the global drop, not a per-kind `sprite_drop` override
        # (houses pin their own value, so toggling the config would do nothing).
        i, o = next((i, o) for i, o in enumerate(gm.obstacles)
                    if i in gm._decos and o.kind not in gm._sprite_drop)
        ax, ay, _fps, _frs, _phase = gm._decos[i]
        cam = Camera(gm.width, gm.height)
        cam.snap_to(o.pos)

        class _Rec:
            def __init__(self): self.calls = []
            def blit(self, src, dest, *a, **k): self.calls.append(dest[1])
            def fill(self, *a, **k): pass

        old = config.SPRITE_ANCHOR_DROP
        try:
            config.SPRITE_ANCHOR_DROP = 0.0
            r0 = _Rec(); gm.renderer._draw_one_obstacle(r0, cam, i, o)
            config.SPRITE_ANCHOR_DROP = 0.7
            r1 = _Rec(); gm.renderer._draw_one_obstacle(r1, cam, i, o)
        finally:
            config.SPRITE_ANCHOR_DROP = old
        self.assertAlmostEqual(r1.calls[0] - r0.calls[0],
                               round(0.7 * o.radius * gm._render_zoom), delta=1)

    def test_tree_shade_compatibility_painter_blits_visible_shades(self):
        from systems.camera import Camera
        gm = self._map()
        first = next(iter(gm._tree_shadows.values()))
        cam = Camera(gm.width, gm.height)
        cam.snap_to(pygame.Vector2(first[0], first[1]))

        class _Recorder:
            def __init__(self): self.calls = []
            def blit(self, src, *a, **k): self.calls.append(id(src))
            def fill(self, *a, **k): pass

        rec = _Recorder()
        gm.renderer.draw_tree_shadows(rec, cam)
        shade_ids = {id(s) for _x, _y, _r, s in gm._tree_shadows.values()}
        self.assertTrue(any(c in shade_ids for c in rec.calls),
                        "no tree shade blitted for an in-view tree")

    def test_character_shade_is_masked_to_the_sprite_alpha(self):
        from types import SimpleNamespace
        from world.map import GameMap

        shade = pygame.Surface((4, 4), pygame.SRCALPHA)
        shade.fill((12, 18, 22, 128))
        frame = pygame.Surface((4, 4), pygame.SRCALPHA)
        frame.set_at((1, 1), (240, 240, 240, 255))

        gm = GameMap.__new__(GameMap)
        gm._tree_shadows = {0: (2, 2, 2, shade)}
        gm._render_zoom = 1.0
        gm._blit_cache = {}
        camera = SimpleNamespace(pos=pygame.Vector2())

        shaded = gm.renderer.shade_character_frame(frame, (0, 0), camera, character_y=2)
        self.assertLess(shaded.get_at((1, 1)).r, frame.get_at((1, 1)).r)
        self.assertEqual(shaded.get_at((0, 0)).a, 0,
                         "shade leaked outside the character silhouette")

        above_tree = gm.renderer.shade_character_frame(frame, (0, 0), camera, character_y=1)
        self.assertIs(above_tree, frame,
                  "character would be darkened twice by both shadow paths")

    def test_foam_remains_on_ground_room_edges_next_to_corridors(self):
        gm = self._map(1234)
        px = self.t["tile_px"]
        corr = [rect for rect, _s, _f in gm._corr_surfs]
        rooms = [r.rect for r in gm.layout.rooms]
        seen = False
        for sx, sy in gm._shore:
            c = pygame.Rect(sx, sy, px, px)
            on_bridge = any(c.colliderect(h.inflate(px, px)) for h in corr)
            in_room = any(c.colliderect(h) for h in rooms)
            seen |= on_bridge and in_room
        self.assertTrue(seen, "no ground shoreline foam remains near a corridor")

    def test_ground_only_shoreline_has_open_edges(self):
        gm = self._map(1234)
        self.assertGreater(len(gm._shore), 100)


if __name__ == "__main__":
    unittest.main()
