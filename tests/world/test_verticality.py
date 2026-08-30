"""LD-1: layered verticality + LD-2 tile-meta / elevation tilesets
(journals/level_design_journal.md). The feature is gated on
`config.WORLD_VERTICALITY`; every test that flips it restores it in `finally`.
"""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from world.procedural import Stair, WorldLayout, generate_world
from world.pathfinding import NavField, _point_in_corridor, _point_on_floor
from world.map import GameMap

_SEEDS = tuple(range(40))

# interior grass tone per elevation sheet (data/terrain.json floor_sheets)
_SHEET_TONE = {0: (151, 181, 83), 1: (131, 173, 87),
               2: (96, 169, 99), 3: (86, 152, 139)}


def _display():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))


def _grass_tone(surf):
    tot = [0, 0, 0]
    n = 0
    for y in range(6, surf.get_height() - 6, 5):
        for x in range(6, surf.get_width() - 6, 5):
            p = surf.get_at((x, y))
            if p[3] > 220 and p[1] >= p[0] and p[1] >= p[2]:
                tot[0] += p[0]; tot[1] += p[1]; tot[2] += p[2]; n += 1
    return tuple(v // max(1, n) for v in tot)


def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


class _Vertical:
    """Mixin: run the body with WORLD_VERTICALITY on, CLIFF_CARVE off."""
    def setUp(self):
        self._v, self._c = config.WORLD_VERTICALITY, config.CLIFF_CARVE
        config.WORLD_VERTICALITY = True
        config.CLIFF_CARVE = False

    def tearDown(self):
        config.WORLD_VERTICALITY = self._v
        config.CLIFF_CARVE = self._c


class DataModelTests(unittest.TestCase):
    def setUp(self):
        self._v = config.WORLD_VERTICALITY
        config.WORLD_VERTICALITY = False

    def tearDown(self):
        config.WORLD_VERTICALITY = self._v

    def test_room_floor_defaults_to_zero_and_layout_has_no_stairs(self):
        w = generate_world(7)                       # flag forced off in setUp
        self.assertTrue(all(r.floor == 0 for r in w.rooms))
        self.assertEqual(w.stairs, [])

    def test_walkable_rects_includes_stairs(self):
        s = Stair(0, 1, pygame.Rect(0, 0, 64, 128), "v", 1, 1)
        w = WorldLayout(0, [], [], pygame.Rect(0, 0, 1, 1), 0, 0, [], [s])
        self.assertIn(s.rect, w.walkable_rects())


class FlagOffUnchangedTests(unittest.TestCase):
    def test_flag_off_flat_world_is_deterministic(self):
        """Variable corridor lanes intentionally revise the base layout;
        verticality-off worlds must still be reproducible and contain no stairs."""
        saved = config.WORLD_VERTICALITY
        config.WORLD_VERTICALITY = False
        try:
            for s in (0, 1, 7, 42, 99, 1234, 2024):
                first, second = generate_world(s), generate_world(s)
                self.assertEqual(_layout_sig(first), _layout_sig(second),
                                 f"flat world is not deterministic for seed {s}")
                self.assertTrue(all(room.floor == 0 for room in first.rooms))
                self.assertEqual(first.stairs, [])
        finally:
            config.WORLD_VERTICALITY = saved

    def test_flag_off_is_a_flat_world(self):
        saved = config.WORLD_VERTICALITY
        config.WORLD_VERTICALITY = False
        try:
            for s in _SEEDS:
                w = generate_world(s)
                self.assertTrue(all(r.floor == 0 for r in w.rooms), f"seed {s}")
                self.assertEqual(w.stairs, [], f"seed {s}")
        finally:
            config.WORLD_VERTICALITY = saved


class GenerationTests(_Vertical, unittest.TestCase):
    def test_deterministic(self):
        for s in (3, 17, 42):
            self.assertEqual(_vert_sig(generate_world(s)), _vert_sig(generate_world(s)))

    def test_floors_span_zero_to_three_across_seeds(self):
        seen = set()
        for s in _SEEDS:
            seen |= {r.floor for r in generate_world(s).rooms}
        self.assertLessEqual(seen, {0, 1, 2, 3})
        self.assertTrue({1, 2} <= seen, "no raised rooms at all across 40 seeds")

    def test_start_stays_on_the_ground(self):
        for s in _SEEDS:
            w = generate_world(s)
            self.assertEqual(w.room(w.start_id).floor, 0)

    def test_no_tree_edge_spans_more_than_two_floors(self):
        for s in _SEEDS:
            w = generate_world(s)
            for r in w.rooms:
                for nb in r.neighbors:
                    self.assertLessEqual(abs(r.floor - w.room(nb).floor), 2,
                                         f"seed {s}: rooms {r.id}/{nb}")

    def test_floor_three_is_a_tiny_interior_pocket(self):
        for s in _SEEDS:
            w = generate_world(s)
            f3 = [r for r in w.rooms if r.floor == 3]
            self.assertLessEqual(len(f3), 2, f"seed {s}")
            for r in f3:                            # every neighbour is 2 or 3
                self.assertTrue(all(w.room(nb).floor >= 2 for nb in r.neighbors),
                                f"seed {s}: floor-3 room {r.id} touches lower ground")

    def test_cross_floor_edges_are_stairs_same_floor_stay_corridors(self):
        for s in _SEEDS:
            w = generate_world(s)
            for c in w.corridors:
                self.assertEqual(w.room(c.a).floor, w.room(c.b).floor,
                                 f"seed {s}: corridor {c.a}-{c.b} spans floors")
            linked = {frozenset((c.a, c.b)) for c in w.corridors}
            linked |= {frozenset((st.low_room, st.high_room)) for st in w.stairs}
            edges = {frozenset((r.id, nb)) for r in w.rooms for nb in r.neighbors}
            self.assertEqual(linked, edges, f"seed {s}: a tree edge lost its link")

    def test_stair_tags_are_sane(self):
        for s in _SEEDS:
            w = generate_world(s)
            for st in w.stairs:
                self.assertIn(st.width_tiles, (1, 2))
                self.assertIn(st.d_floor, (1, 2))
                lo, hi = w.room(st.low_room).floor, w.room(st.high_room).floor
                self.assertLess(lo, hi)
                self.assertEqual(hi - lo, st.d_floor)

    def test_stair_widths_are_a_mix_not_all_one_value(self):
        widths = {st.width_tiles for s in _SEEDS for st in generate_world(s).stairs}
        self.assertEqual(widths, {1, 2})

    def test_every_room_still_connected(self):
        for s in _SEEDS:
            self.assertTrue(generate_world(s).is_connected(), f"seed {s}")

    def test_no_obstacle_sits_on_a_stair(self):
        for s in _SEEDS:
            w = generate_world(s)
            for st in w.stairs:
                for o in w.obstacles:
                    self.assertFalse(st.rect.collidepoint(o.pos.x, o.pos.y),
                                     f"seed {s}: {o.kind} on stair "
                                     f"{st.low_room}->{st.high_room}")


class CollisionTests(_Vertical, unittest.TestCase):
    def test_stair_centre_is_walkable(self):
        for s in _SEEDS:
            gm = GameMap(seed=s)
            for st in gm.layout.stairs:
                self.assertTrue(gm._point_ok(st.rect.centerx, st.rect.centery),
                                f"seed {s}")

    def test_collision_and_nav_floor_tests_agree(self):
        for s in (1, 8, 19, 26, 37):
            gm = GameMap(seed=s)
            b = gm.layout.bounds
            rng = random.Random(s)
            for _ in range(800):
                x = rng.uniform(b.left, b.right)
                y = rng.uniform(b.top, b.bottom)
                self.assertEqual(gm._point_ok(x, y),
                                 _point_on_floor(gm.layout, x, y),
                                 f"seed {s} at ({x:.0f},{y:.0f})")


class NavTests(_Vertical, unittest.TestCase):
    def test_a_stair_cell_gets_corridor_leniency(self):
        w = generate_world(7)
        st = w.stairs[0]
        self.assertTrue(_point_in_corridor(w, st.rect.centerx, st.rect.centery))

    def test_flow_field_routes_across_floors_to_every_raised_room(self):
        px = config.TILE_PX
        for s in _SEEDS:
            w = generate_world(s)
            nf = NavField(w)
            sc = w.room(w.start_id).center
            nf.rebuild((sc.x, sc.y))
            for r in w.rooms:
                if r.floor == 0:
                    continue
                cells = sorted(r.cells)
                reached = sum(
                    1 for (cc, rr) in cells
                    if nf.cost(pygame.Vector2(r.rect.left + cc * px + 32,
                                              r.rect.top + rr * px + 32), 14.0) < 1e9
                    or nf.cost(pygame.Vector2(r.rect.left + cc * px + 32,
                                              r.rect.top + rr * px + 32), 30.0) < 1e9)
                self.assertGreater(reached / len(cells), 0.6,
                                   f"seed {s}: raised room {r.id} barely reachable")

    def test_boss_seek_uses_nav_when_available_else_beelines(self):
        from types import SimpleNamespace
        from entities.boss import Boss
        from game.content import get_content
        bid = next(iter(get_content().bosses))
        b = Boss(bid, get_content().boss(bid), 0, 0)

        nav_ctx = SimpleNamespace(nav_dir=lambda p, r: pygame.Vector2(0, 1),
                                  player_pos=pygame.Vector2(500, 0))
        self.assertEqual(b._seek(nav_ctx), pygame.Vector2(0, 1))     # follows the field

        beeline_ctx = SimpleNamespace(nav_dir=lambda p, r: pygame.Vector2(),
                                      player_pos=pygame.Vector2(500, 0))
        self.assertEqual(b._seek(beeline_ctx), pygame.Vector2(1, 0)) # straight-line fallback


class TileMetaTests(_Vertical, unittest.TestCase):
    def test_every_room_cell_has_meta(self):
        for s in _SEEDS:
            w = generate_world(s)
            for r in w.rooms:
                self.assertEqual(set(r.tile_meta), set(r.cells),
                                 f"seed {s} room {r.id}")
                for m in r.tile_meta.values():
                    self.assertEqual((m.room_id, m.surface, m.floor),
                                     (r.id, "room", r.floor))

    def test_tile_at_matches_room_floor_and_falls_through_to_none(self):
        for s in _SEEDS:
            w = generate_world(s)
            for r in w.rooms:
                c = r.center
                m = w.tile_at(c.x, c.y)
                self.assertIsNotNone(m, f"seed {s} room {r.id} centre")
                self.assertEqual(m.floor, r.floor)
            # LD-4: a staircase unit's *approach* tiles deliberately reach into
            # the rooms, and `tile_at` resolves rooms first, so pick a stair
            # tile that actually sits in the gap between them.
            outside = [st for st in w.stairs
                       if not any(rm.rect.collidepoint(st.rect.centerx,
                                                       st.rect.centery)
                                  for rm in w.rooms)]
            if outside:
                st = outside[0]
                self.assertEqual(
                    w.tile_at(st.rect.centerx, st.rect.centery).surface, "stair")
            b = w.bounds
            self.assertIsNone(w.tile_at(b.right + 100, b.bottom + 100))

    def test_deterministic(self):
        for s in (3, 17, 42):
            a, b = generate_world(s), generate_world(s)
            self.assertEqual([sorted(r.tile_meta.items()) for r in a.rooms],
                             [sorted(r.tile_meta.items()) for r in b.rooms])

    def test_raised_south_rim_is_a_seamless_left_to_right_run(self):
        # The face tile is chosen by what abuts the cliff on each side: a side
        # is a rounded run-end (`left` / `right` / `single`) only where it faces
        # the void, and a solid `mid` edge wherever the neighbouring column has
        # floor at the rim row -- whether that is the next rim cell in the run
        # or the plateau's own land wrapping south past the drop-off.
        seen = end_against_land = False
        for s in _SEEDS:
            w = generate_world(s)
            for r in w.rooms:
                if r.floor == 0:
                    continue
                self.assertTrue(all(not m.foam for m in r.tile_meta.values()),
                                f"seed {s} room {r.id}: a raised cell foams")
                for (c, row), m in r.tile_meta.items():
                    if m.cliff != "top":
                        continue
                    left_solid = (c - 1, row) in r.cells
                    right_solid = (c + 1, row) in r.cells
                    want = ("mid" if left_solid and right_solid else
                            "left" if right_solid else
                            "right" if left_solid else "single")
                    self.assertEqual(m.cliff_var, want,
                                     f"seed {s} r{r.id} ({c},{row})")
                    seen = True
                    # a rim cell butting solid land (a neighbour that is floor
                    # but not itself a rim) must still resolve to `mid`, not a
                    # void-facing cap
                    def _rim(cc):
                        return (cc, row) in r.cells and (cc, row + 1) not in r.cells
                    if want == "mid" and not (_rim(c - 1) and _rim(c + 1)):
                        end_against_land = True
        self.assertTrue(seen, "no raised south rim across the seed range")
        self.assertTrue(end_against_land,
                        "no rim cell butting solid land across the seed range")

    def test_flag_off_meta_is_flat(self):
        saved = config.WORLD_VERTICALITY
        config.WORLD_VERTICALITY = False
        try:
            for s in _SEEDS[:10]:
                w = generate_world(s)
                for r in w.rooms:
                    for m in r.tile_meta.values():
                        self.assertEqual(
                            (m.floor, m.foam, m.cliff, m.cliff_var, m.lip),
                            (0, True, "", "", ""))
        finally:
            config.WORLD_VERTICALITY = saved


class ElevationSheetTests(_Vertical, unittest.TestCase):
    """LD-2 E1: raised rooms bake in their elevation grass sheet and never
    register a shoreline / foam cell."""

    @classmethod
    def setUpClass(cls):
        _display()

    def _built_map(self, seed):
        gm = GameMap(seed=seed)
        gm._render_zoom = 1.0
        gm._build_tiles()
        self.assertTrue(gm._tiles_ok, "tileset assets absent")
        return gm

    def test_a_raised_room_bakes_its_elevation_grass(self):
        got = {}
        for s in _SEEDS:
            if set(got) >= {1, 2, 3}:
                break
            gm = self._built_map(s)
            for r in gm.layout.rooms:
                if r.floor in (1, 2, 3) and r.floor not in got:
                    got[r.floor] = _grass_tone(gm._room_surfs[r.id])
        self.assertTrue({1, 2, 3} <= set(got), f"floors sampled: {sorted(got)}")
        for f, tone in got.items():
            self.assertLess(_dist(tone, _SHEET_TONE[f]),
                            _dist(tone, _SHEET_TONE[0]),
                            f"floor {f} baked grass {tone} not its own sheet")

    def test_no_shore_cell_inside_a_raised_room(self):
        for s in _SEEDS[:20]:
            gm = self._built_map(s)
            raised = [r.rect for r in gm.layout.rooms if r.floor > 0]
            for sx, sy in gm._shore:
                for rr in raised:
                    self.assertFalse(rr.collidepoint(sx + 1, sy + 1),
                                     f"seed {s}: foam inside a plateau at ({sx},{sy})")

    def test_cliff_face_starts_below_the_rim_cell(self):
        # E10: the rim cell is the room's own `slots.raised` south-edge tile
        # (grass + strand fringe), so the baked face surface must be entirely
        # transparent over that cell and only start one row below it.
        # LD-3: except where a ramp run starts -- there the run's first piece
        # deliberately puts its top tile on the rim row.
        px = config.TILE_PX
        checked = 0
        for s in _SEEDS:
            gm = self._built_map(s)
            for r in gm.layout.rooms:
                rim = [(c, ro) for (c, ro), m in r.tile_meta.items()
                       if m.cliff == "top" and not m.ramp]
                surf = next((sf for b, sf, _fl in gm._cliff_surfs
                             if b.x == r.rect.x and b.y == r.rect.y), None)
                if not rim or surf is None:
                    continue
                for c, ro in rim:
                    for dy in (4, px // 2, px - 6):
                        self.assertLessEqual(
                            surf.get_at((c * px + px // 2, ro * px + dy))[3], 8,
                            f"seed {s}: cliff face paints over its own rim cell")
                    checked += 1
                if checked:
                    break
            if checked:
                break
        self.assertGreater(checked, 0, "no cliff rim cell sampled")

    def test_raised_room_uses_the_non_foam_autotile_block(self):
        # E10: a raised room's tiles come from `slots.raised` -- the sheet's
        # second 16-tile block, fringed with cliff grass instead of white surf
        # -- selected straight from `TileMeta` (lip + cliff). Corners included,
        # so nothing is rotated or cropped to fake one.
        from game.assets import get_assets
        px = config.TILE_PX
        seen = set()
        for s in _SEEDS:
            gm = self._built_map(s)
            t = get_assets().terrain
            raised = {k: int(v) for k, v in t["slots"]["raised"].items()}
            self.assertEqual(len(raised), 16, "`slots.raised` is not a full block")
            for r in gm.layout.rooms:
                if r.floor <= 0:
                    continue
                surf = gm._room_surfs[r.id]
                sheet = t["floor_sheets"][str(r.floor)]
                for (c, ro), m in r.tile_meta.items():
                    # LD-3: a cell a ramp run starts at drops its south side so
                    # the plateau's grass flows off into the run instead of an
                    # `s` edge tile fringing across the top of it.
                    south = bool(m.cliff) and not m.ramp
                    sides = "".join(d for d in "nswe"
                                    if (d == "s" and south)
                                    or (d != "s" and d in m.lip))
                    want = get_assets().tile(sheet, raised[sides])
                    for dx, dy in ((3, 3), (px // 2, px // 2), (px - 4, px - 4)):
                        self.assertEqual(
                            surf.get_at((c * px + dx, ro * px + dy)),
                            want.get_at((dx, dy)),
                            f"seed {s} room {r.id} cell ({c},{ro}) sides "
                            f"'{sides}': not the `slots.raised` tile")
                    seen.add(sides)
            if len(seen) >= 8:
                break
        # corners are the point of E10 -- assert real ones were exercised
        self.assertTrue({"nw", "ne"} & seen, f"no north corner sampled: {seen}")
        self.assertTrue({"sw", "se"} & seen, f"no south corner sampled: {seen}")

    def test_ground_rooms_still_seed_the_shore(self):
        gm = self._built_map(7)
        self.assertGreater(len(gm._shore), 50)
        ground = [r.rect for r in gm.layout.rooms if r.floor == 0]
        self.assertTrue(any(rr.collidepoint(sx + 1, sy + 1)
                            for sx, sy in gm._shore for rr in ground),
                        "no foam on any ground room edge")

    def test_cliff_face_bakes_with_no_transparent_seam(self):
        # E7: widening every face tile so adjacent columns' solid cores overlap
        # means the seam between two same-row rim columns has no fully-
        # transparent hairline. Sampled at the first body row across each pair
        # of adjacent rim columns that both drop the full face into the void
        # (E8 can shorten or drop a column's face where it lands on ground).
        px = config.TILE_PX
        checked = 0
        for s in _SEEDS[:20]:
            gm = self._built_map(s)
            lay = gm.layout
            for r in lay.rooms:
                if r.floor <= 0:
                    continue
                surf = next((sf for b, sf, _fl in gm._cliff_surfs
                             if b.x == r.rect.x and b.y == r.rect.y), None)
                if surf is None:
                    continue
                face_h = max(1, min(r.floor, 2) * int(config.CLIFF_TILES))
                rim = {(c, ro): m.cliff_var
                       for (c, ro), m in r.tile_meta.items() if m.cliff == "top"}

                def full_void(c, ro):
                    cx = r.rect.x + c * px + px // 2
                    return all(lay.tile_at(cx, r.rect.y + (ro + k) * px + px // 2)
                               is None for k in range(1, face_h + 2))

                for (c, ro), var in rim.items():
                    if var not in ("left", "mid") or (c + 1, ro) not in rim:
                        continue                       # need a right rim neighbour
                    if not (full_void(c, ro) and full_void(c + 1, ro)):
                        continue
                    y = (ro + 1) * px + px // 2         # middle of the first body row
                    seam = (c + 1) * px
                    band = [surf.get_at((x, y))[3]
                            for x in range(seam - 10, seam + 11)]
                    self.assertTrue(min(band) > 100,
                                    f"seed {s}: void hairline at a cliff column seam")
                    checked += 1
        self.assertGreater(checked, 0, "no adjacent void rim columns sampled")

    def test_cliff_face_is_opaque_straight_under_the_rim(self):
        # E10: with the rim cell now carrying the room's own south-edge tile,
        # the face must butt right up under it -- no transparent gap between
        # the grass strand fringe and the first stone row.
        px = config.TILE_PX
        checked = 0
        for s in _SEEDS:
            gm = self._built_map(s)
            lay = gm.layout
            for r in gm.layout.rooms:
                if r.floor <= 0:
                    continue
                surf = next((sf for b, sf, _fl in gm._cliff_surfs
                             if b.x == r.rect.x and b.y == r.rect.y), None)
                if surf is None:
                    continue
                face_h = max(1, min(r.floor, 2) * int(config.CLIFF_TILES))
                for (c, ro), m in r.tile_meta.items():
                    if m.cliff != "top":
                        continue
                    xs = (r.rect.x + c * px + 2, r.rect.x + c * px + px // 2,
                          r.rect.x + (c + 1) * px - 3)
                    if any(lay.tile_at(x, r.rect.y + (ro + 1) * px + px // 2)
                           is not None for x in xs):
                        continue           # grounded -- no face drawn here
                    for dy in (1, 6, px // 2):
                        self.assertGreater(
                            surf.get_at((c * px + px // 2,
                                         (ro + 1) * px + dy))[3], 200,
                            f"seed {s}: gap between the rim tile and the face")
                    checked += 1
                    break
                if checked:
                    break
            if checked >= 3:
                break
        self.assertGreater(checked, 0, "no void cliff column sampled")

    def test_cliff_foot_foams_over_void_and_grounds_over_a_tile(self):
        # E8: a cliff column whose foot drops into open water gets a
        # `_cliff_foam` point at its base. LD-7a: a column with a lower room
        # floor **directly south of the drawn foot cell** goes plain -- no foam
        # -- and instead gets an underlay grass tile. A column grounded on a
        # bridge / stair, or hanging over a dry span, also skips the foam.
        px = config.TILE_PX
        void_feet = grounded_feet = on_ground_feet = 0
        for s in _SEEDS:
            gm = self._built_map(s)
            lay = gm.layout
            foam = {(int(x), int(y)) for x, y in gm._cliff_foam}
            dry = [c.rect.inflate(px, px) for c in lay.corridors] \
                + [st.rect.inflate(px, px) for st in lay.stairs]
            for r in lay.rooms:
                if r.floor <= 0:
                    continue
                face_h = max(1, min(r.floor, 2) * int(config.CLIFF_TILES))
                for (c, ro), m in r.tile_meta.items():
                    if m.cliff != "top":
                        continue
                    # E8a grounding: whole width covered within face_h+1
                    xs = (r.rect.x + c * px + 2,
                          r.rect.x + c * px + px // 2,
                          r.rect.x + (c + 1) * px - 3)
                    gk = next((k for k in range(1, face_h + 2)
                               if all(lay.tile_at(x, r.rect.y + (ro + k) * px
                                                  + px // 2) is not None
                                      for x in xs)), None)
                    draw_h = min(face_h, gk - 1) if gk else face_h
                    foot_row = ro + draw_h
                    # LD-7a: room floor directly south of the drawn foot cell
                    below = lay.tile_at(r.rect.x + c * px + px // 2,
                                        r.rect.y + (foot_row + 1) * px + px // 2)
                    on_ground = (below is not None and below.surface == "room"
                                 and below.floor < r.floor)
                    foot = (r.rect.x + c * px, r.rect.y + foot_row * px)
                    over_span = any(d.collidepoint(foot[0] + px // 2,
                                                   foot[1] + px // 2) for d in dry)
                    if gk is not None and not on_ground:
                        self.assertNotIn(foot, foam,
                                         f"seed {s}: grounded cliff foot foams")
                        grounded_feet += 1
                    elif on_ground:
                        self.assertNotIn(foot, foam,
                                         f"seed {s}: on-ground cliff foot foams")
                        on_ground_feet += 1
                    elif over_span:
                        self.assertNotIn(foot, foam,
                                         f"seed {s}: sky-gap cliff foot foams")
                    else:
                        self.assertIn(foot, foam,
                                      f"seed {s}: void cliff foot seeded no foam")
                        void_feet += 1
        self.assertGreater(void_feet, 0, "no void cliff feet sampled")
        self.assertGreater(on_ground_feet, 0, "no on-ground cliff feet sampled")

    def test_cliff_foot_underlay_sits_at_the_cliff_cell_over_lower_ground(self):
        # LD-7a: `_cliff_underlay` is one lower-room grass tile drawn at a
        # cliff-foot cell that has a lower room floor **directly south of it**.
        # So the tile is opaque grass, the cell one row south is a lower room
        # floor, and the same cell carries a drop-shadow anchor.
        px = config.TILE_PX
        seen = 0
        for s in _SEEDS:
            gm = self._built_map(s)
            shadow = {(int(x), int(y)) for x, y in gm._cliff_shadow}
            for rect, tile in gm._cliff_underlay:
                p = tile.get_at((px // 2, px // 2))
                self.assertGreater(p[3], 200, f"seed {s}: underlay tile transparent")
                self.assertGreaterEqual(p[1], p[0], f"seed {s}: underlay not grass")
                self.assertGreaterEqual(p[1], p[2], f"seed {s}: underlay not grass")
                south = gm.layout.tile_at(rect.x + px // 2, rect.y + px + px // 2)
                self.assertIsNotNone(south, f"seed {s}: no ground south of underlay")
                self.assertEqual(south.surface, "room",
                                 f"seed {s}: underlay's south neighbour is not a room")
                self.assertIn((rect.x, rect.y), shadow,
                              f"seed {s}: underlay cell has no shadow anchor")
                seen += 1
        self.assertGreater(seen, 0, "no cliff-foot underlay across the seeds")

    def test_cliff_faces_paint_below_rooms_and_ramp_units_above(self):
        # LD-7 order: LD-7a cliff-foot underlay tiles -> cliff faces -> room
        # floors -> lifted staircase units. The underlay is the only terrain
        # drawn before the cliff faces; the cliff faces are before every room
        # floor; the ramp units are after the room floors.
        gm = next((g for g in (self._built_map(s) for s in _SEEDS)
                   if g._cliff_surfs and g._ramp_surfs and g._cliff_underlay),
                  None)
        self.assertIsNotNone(gm, "no seed with a cliff, a ramp unit and an underlay")

        class _FullView:
            """A camera whose visible rect covers the whole world (no culling)."""
            def __init__(self, w, h):
                self.pos = pygame.Vector2(0, 0)
                self.zoom = 1.0
                self._r = pygame.Rect(-w, -h, 3 * w, 3 * h)
            def visible_rect(self): return self._r

        class _Rec:
            def __init__(self): self.ids = []
            def blit(self, src, *a, **k): self.ids.append(id(src))
            def fill(self, *a, **k): pass
            def get_size(self): return (2400, 1800)

        rec = _Rec()
        gm._render_zoom = 1.0
        gm._draw_tiled(rec, _FullView(gm.width, gm.height))
        pos = {}
        for i, sid in enumerate(rec.ids):
            pos.setdefault(sid, i)                # first blit of each surface
        first_under = min(pos[id(t)] for _r, t in gm._cliff_underlay if id(t) in pos)
        first_cliff = min(pos[id(s)] for _b, s, _f in gm._cliff_surfs if id(s) in pos)
        last_cliff = max(pos[id(s)] for _b, s, _f in gm._cliff_surfs if id(s) in pos)
        first_room = min(pos[id(s)] for s in gm._room_surfs.values() if id(s) in pos)
        first_ramp = min(pos[id(s)] for _b, s, _f in gm._ramp_surfs if id(s) in pos)
        self.assertLess(first_under, first_cliff, "underlay painted after a cliff face")
        self.assertLess(last_cliff, first_room, "a cliff painted after a room floor")
        self.assertLess(first_room, first_ramp, "a ramp unit painted under a room floor")

    def test_a_partly_covered_rim_column_keeps_its_full_face(self):
        # E8a: corridor / stair rects are tile-sized but not aligned to a
        # room's column grid, so a bridge can cover only part of a rim column.
        # E8's single centre probe then dropped the whole face and the
        # uncovered half showed the void. Every rim column must be opaque all
        # the way down to wherever it is *fully* covered.
        px = config.TILE_PX
        checked = partial = 0
        for s in _SEEDS[:25]:
            gm = self._built_map(s)
            lay = gm.layout
            for r in lay.rooms:
                if r.floor <= 0:
                    continue
                surf = next((sf for b, sf, _fl in gm._cliff_surfs
                             if b.x == r.rect.x and b.y == r.rect.y), None)
                if surf is None:
                    continue
                face_h = max(1, min(r.floor, 2) * int(config.CLIFF_TILES))
                for (c, ro), m in r.tile_meta.items():
                    if m.cliff != "top":
                        continue
                    xs = (r.rect.x + c * px + 2,
                          r.rect.x + c * px + px // 2,
                          r.rect.x + (c + 1) * px - 3)
                    # first step where the column is *fully* covered
                    full = next((k for k in range(1, face_h + 2)
                                 if all(lay.tile_at(x, r.rect.y + (ro + k) * px
                                                    + px // 2) is not None
                                        for x in xs)), None)
                    # ... and where any single probe first hits something
                    any_k = next((k for k in range(1, face_h + 2)
                                  if any(lay.tile_at(x, r.rect.y + (ro + k) * px
                                                     + px // 2) is not None
                                         for x in xs)), None)
                    if full == any_k or any_k is None or any_k > face_h:
                        continue        # not partial, or below the face itself
                    partial += 1
                    # the column must still be painted at the row where only
                    # part of it was covered -- sample the uncovered probe
                    k = any_k
                    # LD-6: tiles are drawn at native size, so a `left` /
                    # `single` variant's own left edge (and `right` / `single`
                    # right edge) is *meant* to be transparent -- the run's
                    # void-facing outer edge. Only the interior probe is a
                    # genuine "did the half-covered column get painted" check.
                    edge_ok = {
                        xs[0]: m.cliff_var not in ("left", "single"),
                        xs[1]: True,
                        xs[2]: m.cliff_var not in ("right", "single"),
                    }
                    for x in xs:
                        if lay.tile_at(x, r.rect.y + (ro + k) * px + px // 2):
                            continue                # that half is covered
                        if not edge_ok[x]:
                            continue
                        sx = x - r.rect.x
                        sy = (ro + k) * px + px // 2
                        self.assertGreater(
                            surf.get_at((sx, sy))[3], 100,
                            f"seed {s} room {r.id} col {c}: void strip under a "
                            f"partly covered rim column")
                        checked += 1
        self.assertGreater(partial, 0, "no partly covered rim columns in sample")
        self.assertGreater(checked, 0, "no uncovered probe sampled")

    def test_corridors_never_seed_shoreline_foam(self):
        # Bridges overlap one tile into rooms, so a room-edge anchor can be
        # inside a bridge's blit rect. The ownership rule is the source of
        # truth: every normal shore anchor must be a ground-room cell.
        for s in _SEEDS[:25]:
            gm = self._built_map(s)
            ground_cells = {
                (room.rect.x + col * config.TILE_PX,
                 room.rect.y + row * config.TILE_PX)
                for room in gm.layout.rooms if room.floor == 0
                for col, row in room.cells
            }
            self.assertTrue(set(gm._shore).issubset(ground_cells),
                            f"seed {s}: a corridor seeded shoreline foam")

    def test_nw_rim_of_a_raised_room_is_darkened(self):
        for s in _SEEDS:
            gm = self._built_map(s)
            for r in gm.layout.rooms:
                if r.floor == 0:
                    continue
                surf = gm._room_surfs[r.id]
                lip_cells = [(c, ro) for (c, ro), m in r.tile_meta.items() if m.lip]
                plain = [(c, ro) for (c, ro), m in r.tile_meta.items()
                         if not m.lip and not m.cliff]
                if not lip_cells or not plain:
                    continue
                px = config.TILE_PX
                pc, pr = plain[0]
                base = sum(surf.get_at((pc * px + px // 2, pr * px + px // 2))[:3])
                # a lip cell's rim pixel (1 px inside the exposed side) is darker
                lc, lr = lip_cells[0]
                m = r.tile_meta[(lc, lr)]
                ox = 2 if "w" in m.lip else px - 3 if "e" in m.lip else px // 2
                oy = 2 if "n" in m.lip else px // 2
                rim = sum(surf.get_at((lc * px + ox, lr * px + oy))[:3])
                self.assertLess(rim, base, f"seed {s} room {r.id}: lip not darkened")
                return
        self.fail("no raised room with both a lip cell and a plain cell")


def _layout_sig(w):
    return ([(r.id, tuple(r.rect), r.kind, r.floor, tuple(sorted(r.neighbors)),
             tuple(sorted(r.cells))) for r in w.rooms],
            [(c.a, c.b, tuple(c.rect), c.axis) for c in w.corridors],
            [(o.kind, round(o.pos.x, 3), round(o.pos.y, 3)) for o in w.obstacles],
            len(w.stairs))


def _vert_sig(w):
    return (_layout_sig(w),
            [(st.low_room, st.high_room, tuple(st.rect), st.axis,
              st.width_tiles, st.d_floor) for st in w.stairs])


if __name__ == "__main__":
    unittest.main()


class RampTests(_Vertical, unittest.TestCase):
    """LD-4: a cross-floor link is a **staircase unit** -- 3 tiles wide, 2 band
    rows deep -- cut into the cliff band, instead of LD-3's diagonal run of
    one-tile-per-descent pieces::

        row rim   :  = = = = = = = =     plateau surface
        band row 0:  # # # # > = # #     stair top    + top landing at c+d
        band row 1:  # # # = > # # #     bottom landing at c-d + stair bottom
        row below :  = = = = = = = =     low room surface

    Gated on `config.RAMP_STAIRS`. One-floor changes only (decision 2, option c).
    """

    def setUp(self):
        super().setUp()
        self._r = config.RAMP_STAIRS
        config.RAMP_STAIRS = True

    def tearDown(self):
        config.RAMP_STAIRS = self._r
        super().tearDown()

    @staticmethod
    def _units(w):
        """`{(high, low, direction): {part: rect}}`, parts named
        `top_approach` / `top` / `stair` / `bot` / `bot_approach`."""
        px = config.TILE_PX
        grouped = {}
        for st in w.stairs:
            if st.ramp:
                grouped.setdefault((st.high_room, st.low_room, st.ramp), []).append(st)
        named = {}
        for key, parts in grouped.items():
            y0 = w.room(key[0]).rect.bottom
            m = {}
            for st in parts:
                r = st.rect
                if r.height == 2 * px and r.top == y0:
                    m["stair"] = r
                elif r.top == y0 - 2 * px:
                    m["top_approach"] = r
                elif r.top == y0 and r.height == px:
                    m["top"] = r
                elif r.top == y0 + px and r.height == px:
                    m["bot"] = r
                elif r.top == y0 + 2 * px:
                    m["bot_approach"] = r
            named[key] = m
        return named

    def test_flag_off_plans_no_units(self):
        config.RAMP_STAIRS = False
        for s in _SEEDS:
            w = generate_world(s)
            self.assertEqual([st for st in w.stairs if st.ramp], [],
                             f"seed {s}: staircase tile with the flag off")
            self.assertEqual(
                [m for r in w.rooms for m in r.tile_meta.values() if m.ramp], [],
                f"seed {s}: staircase metadata with the flag off")

    def test_some_seeds_actually_get_a_unit(self):
        n = sum(1 for s in _SEEDS if self._units(generate_world(s)))
        self.assertGreater(n, 3, f"only {n}/{len(_SEEDS)} seeds got a staircase")

    def test_a_unit_has_all_five_tiles_in_the_right_places(self):
        px = config.TILE_PX
        checked = 0
        for s in _SEEDS:
            w = generate_world(s)
            for (hi_id, lo_id, d), m in self._units(w).items():
                self.assertEqual(set(m), {"top_approach", "top", "stair",
                                          "bot", "bot_approach"},
                                 f"seed {s}: unit is missing tiles")
                dd = 1 if d == "w" else -1
                stair = m["stair"]
                self.assertEqual(stair.height, 2 * px,
                                 f"seed {s}: the stair is not 2 tiles tall")
                self.assertEqual(m["top"].x, stair.x + dd * px,
                                 f"seed {s}: top landing on the wrong side")
                self.assertEqual(m["bot"].x, stair.x - dd * px,
                                 f"seed {s}: bottom landing on the wrong side")
                self.assertEqual(m["top_approach"].x, m["top"].x)
                self.assertEqual(m["bot_approach"].x, m["bot"].x)
                checked += 1
        self.assertGreater(checked, 0, "no staircase sampled")

    def test_a_unit_is_flush_between_its_rooms_and_spans_one_floor(self):
        px = config.TILE_PX
        for s in _SEEDS:
            w = generate_world(s)
            for (hi_id, lo_id, _d), m in self._units(w).items():
                hi, lo = w.room(hi_id), w.room(lo_id)
                self.assertEqual(hi.floor - lo.floor, 1,
                                 f"seed {s}: unit spans more than one floor")
                self.assertEqual(lo.rect.top,
                                 hi.rect.bottom + int(config.CLIFF_TILES) * px,
                                 f"seed {s}: rooms not snapped flush")
                self.assertEqual(m["stair"].top, hi.rect.bottom)
                self.assertEqual(m["stair"].bottom, lo.rect.top)

    def test_the_unit_chain_is_orthogonal_end_to_end(self):
        """Plateau -> top approach -> top landing -> stair -> bottom landing ->
        bottom approach -> low room, every link sharing a full edge. The flow
        field refuses a diagonal step unless both orthogonal neighbours are
        open, which is what broke LD-3's diagonal run."""
        for s in _SEEDS:
            w = generate_world(s)
            for key, m in self._units(w).items():
                chain = [m["top_approach"], m["top"], m["stair"],
                         m["bot"], m["bot_approach"]]
                for a, b in zip(chain, chain[1:]):
                    sx = min(a.right, b.right) - max(a.left, b.left)
                    sy = min(a.bottom, b.bottom) - max(a.top, b.top)
                    touching = ((sx > 0 and (a.bottom == b.top or b.bottom == a.top))
                                or (sy > 0 and (a.right == b.left or b.right == a.left)))
                    self.assertTrue(touching,
                                    f"seed {s}: unit chain breaks between "
                                    f"{tuple(a)} and {tuple(b)}")

    def test_the_approaches_reach_two_tiles_into_each_room(self):
        """Not cosmetic: without them the lenient cells stop at the room edge,
        where clearance is under the large nav class's 22 px, so only the small
        class could reach the unit."""
        px = config.TILE_PX
        for s in _SEEDS:
            w = generate_world(s)
            for (hi_id, lo_id, _d), m in self._units(w).items():
                hi, lo = w.room(hi_id), w.room(lo_id)
                self.assertEqual(m["top_approach"].height, 2 * px)
                self.assertEqual(m["top_approach"].bottom, hi.rect.bottom)
                self.assertEqual(m["bot_approach"].height, 2 * px)
                self.assertEqual(m["bot_approach"].top, lo.rect.top)
                rows_n = hi.rect.height // px
                for c in range((m["top_approach"].x - hi.rect.left) // px,
                               (m["top_approach"].right - 1 - hi.rect.left) // px + 1):
                    for row in (rows_n - 1, rows_n - 2):
                        self.assertIn((c, row), hi.cells,
                                      f"seed {s}: top approach is off the plateau")
                for c in range((m["bot_approach"].x - lo.rect.left) // px,
                               (m["bot_approach"].right - 1 - lo.rect.left) // px + 1):
                    for row in (0, 1):
                        self.assertIn((c, row), lo.cells,
                                      f"seed {s}: bottom approach is off the low room")

    def test_both_nav_classes_traverse_every_unit(self):
        checked = 0
        for s in _SEEDS[:25]:
            w = generate_world(s)
            tiles = [st for st in w.stairs if st.ramp]
            if not tiles:
                continue
            nf = NavField(w, w.obstacles)
            sc = w.room(w.start_id).center
            nf.rebuild((sc.x, sc.y))
            for st in tiles:
                c = pygame.Vector2(st.rect.centerx, st.rect.centery)
                for radius in (14.0, 30.0):
                    self.assertLess(nf.cost(c, radius), 1e9,
                                    f"seed {s}: unit tile unreachable at r={radius}")
                checked += 1
        self.assertGreater(checked, 0, "no unit tile sampled")

    def test_no_obstacle_sits_on_a_unit(self):
        for s in _SEEDS:
            w = generate_world(s)
            for st in w.stairs:
                if not st.ramp:
                    continue
                for o in w.obstacles:
                    self.assertFalse(st.rect.collidepoint(o.pos.x, o.pos.y),
                                     f"seed {s}: {o.kind} on a staircase tile")

    def test_metadata_tags_the_stair_column(self):
        px = config.TILE_PX
        for s in _SEEDS:
            w = generate_world(s)
            units = self._units(w)
            tags = [(r.id, c, ro, m.ramp)
                    for r in w.rooms for (c, ro), m in r.tile_meta.items() if m.ramp]
            self.assertEqual(len(tags), len(units),
                             f"seed {s}: {len(tags)} tags for {len(units)} units")
            for rid, c, ro, d in tags:
                hi = w.room(rid)
                self.assertEqual(hi.tile_meta[(c, ro)].cliff, "top",
                                 f"seed {s}: tag is not on a south-rim cell")
                m = next(v for k, v in units.items() if k[0] == rid and k[2] == d)
                self.assertEqual(m["stair"].x, hi.rect.left + c * px,
                                 f"seed {s}: tag column is not the stair column")

    def test_layout_stays_connected_and_deterministic(self):
        for s in _SEEDS:
            a, b = generate_world(s), generate_world(s)
            self.assertTrue(a.is_connected(), f"seed {s}: layout disconnected")
            self.assertEqual(
                [(st.ramp, tuple(st.rect), st.high_room, st.low_room) for st in a.stairs],
                [(st.ramp, tuple(st.rect), st.high_room, st.low_room) for st in b.stairs],
                f"seed {s}: staircase planning is not deterministic")

    def test_the_unit_renders_its_three_parts(self):
        """Cliff-behind (`mid`, opaque) across both band rows of all three unit
        columns stays baked in the cliff surface so no part of the cut shows the
        sea; LD-7: the walkable landings + stair piece are lifted into
        `_ramp_surfs` and each landing samples as grass there."""
        px = config.TILE_PX
        checked = 0
        for s in _SEEDS:
            gm = GameMap(seed=s)
            gm._render_zoom = 1.0
            gm._build_tiles()
            if not gm._tiles_ok:
                continue
            for r in gm.layout.rooms:
                tag = [(c, ro, m.ramp) for (c, ro), m in r.tile_meta.items() if m.ramp]
                if not tag:
                    continue
                surf = next((sf for b, sf, _fl in gm._cliff_surfs
                             if b.x == r.rect.x and b.y == r.rect.y), None)
                if surf is None:
                    continue
                c0, ro0, d = tag[0]
                dd = 1 if d == "w" else -1
                # cliff-behind: opaque across every unit tile in the cliff surface
                for col, band in ((c0, 0), (c0, 1), (c0 + dd, 0), (c0 + dd, 1),
                                  (c0 - dd, 0), (c0 - dd, 1)):
                    y = (ro0 + 1 + band) * px + px // 2
                    self.assertGreater(
                        surf.get_at((col * px + px // 2, y))[3], 200,
                        f"seed {s}: unit tile ({col},{band}) shows the void")
                # LD-7: landings live in the lifted ramp surface, not the cliff
                rblit, rsurf = next(
                    ((b, sf) for b, sf, _fl in gm._ramp_surfs
                     if b.x == r.rect.x + (c0 - 1) * px
                     and b.y == r.rect.y + (ro0 + 1) * px), (None, None))
                self.assertIsNotNone(rsurf, f"seed {s}: unit not lifted to _ramp_surfs")
                land_hi = rsurf.get_at((r.rect.x + (c0 + dd) * px + px // 2 - rblit.x,
                                        r.rect.y + (ro0 + 1) * px + px // 2 - rblit.y))
                land_lo = rsurf.get_at((r.rect.x + (c0 - dd) * px + px // 2 - rblit.x,
                                        r.rect.y + (ro0 + 2) * px + px // 2 - rblit.y))
                for p in (land_hi, land_lo):
                    self.assertGreater(p[3], 200, f"seed {s}: landing is transparent")
                    self.assertGreater(p[1], p[2] + 15,
                                       f"seed {s}: landing is not grass")
                checked += 1
        self.assertGreater(checked, 0, "no unit rendered")


class StructAnnexTests(_Vertical, unittest.TestCase):
    """LD-5: structure tiles (plank-stair strips, staircase-unit landings) get
    an owning room and are folded into that room's autotiled shape."""

    def setUp(self):
        super().setUp()
        self._r, self._a = config.RAMP_STAIRS, config.STRUCT_ANNEX
        config.RAMP_STAIRS = True

    def tearDown(self):
        config.RAMP_STAIRS = self._r
        config.STRUCT_ANNEX = self._a
        super().tearDown()

    def test_flag_off_leaves_annex_empty_and_meta_unchanged(self):
        config.STRUCT_ANNEX = False
        for s in _SEEDS:
            w = generate_world(s)
            for r in w.rooms:
                self.assertEqual(r.annex, frozenset(),
                                 f"seed {s} room {r.id}: annex set with flag off")

    def test_flag_on_folds_the_top_landing_into_the_plateau(self):
        """The rim cell directly above a staircase unit's top landing stops
        being a south rim -- so the plateau's grass runs flat down to the
        landing instead of a cliff fringe cutting across."""
        config.STRUCT_ANNEX = True
        px = config.TILE_PX
        checked = 0
        for s in _SEEDS:
            w = generate_world(s)
            for st in w.stairs:
                hi = w.room(st.high_room)
                if (not st.ramp or st.rect.height != 2 * px
                        or st.rect.top != hi.rect.bottom):
                    continue                      # only the 1x2 stair piece
                                                  # (approaches are 2-tall too)
                d = 1 if st.ramp == "w" else -1
                col = (st.rect.x - hi.rect.left) // px
                top_col = col + d
                rows_n = hi.rect.height // px
                self.assertIn((top_col, rows_n), hi.annex,
                              f"seed {s}: top landing not annexed to the plateau")
                rim = hi.tile_meta.get((top_col, rows_n - 1))
                if rim is not None:
                    self.assertEqual(rim.cliff, "",
                                     f"seed {s}: rim cell above the landing is "
                                     f"still a cliff top")
                checked += 1
        self.assertGreater(checked, 0, "no staircase unit sampled")

    def test_flag_on_is_deterministic(self):
        config.STRUCT_ANNEX = True
        for s in (3, 17, 29):
            a, b = generate_world(s), generate_world(s)
            self.assertEqual([sorted(r.annex) for r in a.rooms],
                             [sorted(r.annex) for r in b.rooms])


class PlankStairRenderTests(_Vertical, unittest.TestCase):
    """LD-5: a non-ramp `Stair` renders as a plank bridge (1 or 2 wide), not a
    bare grass strip in one sheet."""

    @classmethod
    def setUpClass(cls):
        _display()

    def test_wide_stairs_are_roughly_one_in_seven(self):
        wide = narrow = 0
        for s in range(80):
            for st in generate_world(s).stairs:
                if st.ramp:
                    continue
                if st.width_tiles == 2:
                    wide += 1
                else:
                    narrow += 1
        self.assertGreater(wide, 0, "no wide stairs at all")
        ratio = narrow / wide
        self.assertTrue(3 < ratio < 14,
                        f"wide-stair rate off target: 1 per {ratio:.1f} narrow")

    def test_a_non_ramp_stair_bakes_plank_tiles_not_bare_grass(self):
        px = config.TILE_PX
        checked = 0
        for s in range(30):
            gm = GameMap(seed=s)
            gm._render_zoom = 1.0
            gm._build_tiles()
            if not gm._tiles_ok:
                continue
            for st in gm.layout.stairs:
                if st.ramp:
                    continue
                surf = next((sf for b, sf, _fl in gm._stair_surfs
                             if b.colliderect(st.rect.inflate(px, px))), None)
                if surf is None:
                    continue
                # a plank tile has strong wood browns; bare grass does not
                brown = 0
                for x in range(0, surf.get_width(), 6):
                    for y in range(0, surf.get_height(), 6):
                        p = surf.get_at((x, y))
                        if p[3] > 200 and p[0] > 120 and p[0] > p[2] + 25 \
                                and p[1] < p[0]:
                            brown += 1
                self.assertGreater(brown, 4,
                                   f"seed {s}: stair strip has no plank pixels")
                checked += 1
                break
        self.assertGreater(checked, 0, "no plank stair rendered")


class CliffFootAndSeamTests(_Vertical, unittest.TestCase):
    """LD-6: a cliff foot that lands on lower ground gets a static drop shadow
    (not foam); cliff tiles are drawn at native size so a run end keeps its
    transparent outer edge and the inter-column seam is closed by a mid patch."""

    @classmethod
    def setUpClass(cls):
        _display()

    def _built(self, s):
        gm = GameMap(seed=s)
        gm._render_zoom = 1.0
        gm._build_tiles()
        return gm

    def test_shadow_only_where_a_cliff_foot_lands_on_a_lower_room(self):
        px = config.TILE_PX
        checked_on = checked_sea = 0
        for s in _SEEDS:
            gm = self._built(s)
            if not gm._tiles_ok:
                continue
            for wx, wy in gm._cliff_shadow:
                # LD-7a: the shadow anchor is the cliff *foot* cell (in the
                # band); the lower room it belongs to is one tile south of it.
                m = gm.layout.tile_at(wx + px // 2, wy + px + px // 2)
                self.assertIsNotNone(m, f"seed {s}: shadow with only void below")
                self.assertEqual(m.surface, "room",
                                 f"seed {s}: shadow not over a room floor")
                checked_on += 1
            # a cliff foot over open sea contributes foam, never a shadow, at
            # the same spot
            foam = {(x, y) for x, y in gm._cliff_foam}
            shadow = {(x, y) for x, y in gm._cliff_shadow}
            self.assertEqual(foam & shadow, set(),
                             f"seed {s}: a foot is both foam and shadow")
            checked_sea += len(foam)
        self.assertGreater(checked_on, 0, "no cliff-foot shadow sampled")
        self.assertGreater(checked_sea, 0, "no cliff-foot foam sampled")

    def test_cliff_foot_shadow_does_not_suppress_ground_shoreline_foam(self):
        px = config.TILE_PX
        for s in _SEEDS:
            gm = self._built(s)
            if not gm._tiles_ok:
                continue
            shore = set(gm._shore)
            for room in gm.layout.rooms:
                if room.floor != 0:
                    continue
                for col, row in room.cells:
                    # LD-7a: a cell with a cliff band flush overhead has its
                    # north side closed and deliberately does not foam.
                    if (room.id, col, row) in gm._cliff_capped:
                        continue
                    sx = room.rect.x + col * px
                    sy = room.rect.y + row * px
                    if any(not gm._point_ok(sx + px / 2 + dx, sy + px / 2 + dy)
                           for dx, dy in ((px, 0), (-px, 0), (0, px), (0, -px))):
                        self.assertIn((sx, sy), shore,
                                      f"seed {s}: missing sea-facing ground foam")

    def test_interior_seam_between_two_mid_columns_is_opaque(self):
        px = config.TILE_PX
        checked = 0
        for s in _SEEDS:
            gm = self._built(s)
            if not gm._tiles_ok:
                continue
            for r in gm.layout.rooms:
                surf = next((sf for b, sf, _fl in gm._cliff_surfs
                             if b.x == r.rect.x and b.y == r.rect.y), None)
                if surf is None:
                    continue
                rim = {(c, ro): m.cliff_var
                       for (c, ro), m in r.tile_meta.items() if m.cliff == "top"}
                ramp_c = {c for (c, ro), m in r.tile_meta.items() if m.ramp}
                # LD-4 unit columns (stair + its two landings) are their own
                # sub-render; this checks the plain face only.
                unit_c = set()
                for cc in ramp_c:
                    unit_c |= {cc - 1, cc, cc + 1}
                face_h = max(1, min(r.floor, 2) * int(config.CLIFF_TILES))

                def full_void(cc, ro):
                    cx = r.rect.x + cc * px + px // 2
                    return all(gm.layout.tile_at(
                        cx, r.rect.y + (ro + k) * px + px // 2) is None
                        for k in range(1, face_h + 2))

                for (c, ro), var in rim.items():
                    if (c + 1, ro) not in rim:
                        continue
                    if var != "mid" or rim[(c + 1, ro)] != "mid":
                        continue
                    if c in unit_c or (c + 1) in unit_c:
                        continue
                    if not (full_void(c, ro) and full_void(c + 1, ro)):
                        continue        # a grounded column has a short/no face
                    y = (ro + 1) * px + px // 2
                    band = [surf.get_at((c * px + px + dx, y))[3]
                            for dx in range(-6, 7)]
                    self.assertGreater(min(band), 120,
                                       f"seed {s}: void hairline at a cliff seam")
                    checked += 1
        self.assertGreater(checked, 0, "no interior cliff seam sampled")
