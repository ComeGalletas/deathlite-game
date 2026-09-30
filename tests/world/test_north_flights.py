"""North flights: the straight flight on a plateau's back.

A north face has no wall (`_raise_walls` only stones southward drops), so
the flight is the rim cell itself, one cell whatever the drop, with the low
ground north of it and its own terrace south::

    = = = = = =            = = = = = =
    # # # # # #     ->     # # # ^ # #
    # # # # # #            # # # # # #

The site rule and the link rule are pinned on hand-built grids in
`tests/world/grids/test_north_flight_rules.py` (the `unit` tier, worldgen
R4); the shared worlds here check that the generator actually places them,
that the runtime step rule mirrors the generator on every one, and that both
nav classes can climb them. See
`documentation/journals/north_stairs_journal.md`.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from tests import worlds as W
from world.gen.height.graph import walk_links
from world.gen.spawnpoints import body_radii  # the large body the world is certified for (ENT-021)
from world.layout import GROUND, VSTAIR
from world.nav.field import NavField, _INF
from world.rules.steps import can_cross, can_step

SEEDS = (35, 7)


def _abs_tiles(room):
    px = config.TILE_PX
    c0 = int(room.rect.left) // px
    r0 = int(room.rect.top) // px
    return lambda p: (c0 + p[0], r0 + p[1])


def _centre(ix, tile):
    px = ix.px
    return pygame.Vector2(ix.origin[0] + tile[0] * px + px / 2,
                          ix.origin[1] + tile[1] * px + px / 2)


def _north_flights(layout):
    for room in layout.rooms:
        for pos, cell in room.grid.items():
            if cell.kind == VSTAIR and cell.dir == "n":
                yield room, pos, cell


class GeneratedTests(unittest.TestCase):
    def test_the_generator_places_them(self):
        for seed in SEEDS:
            n = sum(1 for _ in _north_flights(W.layout(seed)))
            self.assertGreater(n, 5, f"seed {seed}: no north flights")

    def test_every_one_sits_on_a_back_rim(self):
        """The invariant, read off the shipped grid: low ground north, its own
        terrace south and on both flanks, one cell, row 0."""
        for seed in SEEDS:
            for room, (c, r), cell in _north_flights(W.layout(seed)):
                g = room.grid
                self.assertEqual(cell.row, 0)
                north = g.get((c, r - 1))
                self.assertEqual((north.kind, north.level),
                                 (GROUND, cell.level - cell.drop),
                                 f"seed {seed} room {room.id} at {(c, r)}")
                for p in ((c, r + 1), (c - 1, r), (c + 1, r)):
                    nb = g.get(p)
                    self.assertEqual((nb.kind, nb.level), (GROUND, cell.level),
                                     f"seed {seed} room {room.id} at {(c, r)}")

    def test_tile_meta_says_it_descends_north(self):
        for seed in SEEDS:
            for room, pos, _cell in _north_flights(W.layout(seed)):
                self.assertEqual(room.tile_meta[pos].ramp, "n")

    def test_the_runtime_rule_mirrors_the_generator(self):
        for seed in SEEDS:
            gm = W.game_map(seed)
            ix = gm._levels
            for room, pos, _cell in _north_flights(gm.layout):
                at = _abs_tiles(room)
                a = at(pos)
                want = {at(p) for p in walk_links(room.grid, pos)}
                got = {(a[0] + dc, a[1] + dr)
                       for dc, dr in ((-1, 0), (1, 0), (0, -1), (0, 1))
                       if can_cross(ix, a, (a[0] + dc, a[1] + dr))}
                self.assertEqual(got, want, f"seed {seed} at {pos}")
                self.assertTrue(can_cross(ix, (a[0], a[1] - 1), a))
                self.assertTrue(can_cross(ix, (a[0], a[1] + 1), a))

    def test_a_body_walks_through_the_door_sideways(self):
        """WLD-014: a north flight has no walls at its flanks. On every one,
        a body walks from each flank onto the flight and back, and from the
        flank down through the flight to the landing -- while the frontier
        beside the door stays shut: no step from a flank straight to the
        low ground north of it, nor diagonally to the landing."""
        for seed in SEEDS:
            gm = W.game_map(seed)
            ix = gm._levels
            for room, pos, _cell in _north_flights(gm.layout):
                at = _abs_tiles(room)
                a = at(pos)
                where = f"seed {seed} at {pos}"
                landing = (a[0], a[1] - 1)
                for dc in (-1, 1):
                    flank = (a[0] + dc, a[1])
                    north = (flank[0], flank[1] - 1)
                    self.assertTrue(can_cross(ix, flank, a), where)
                    self.assertTrue(can_cross(ix, a, flank), where)
                    self.assertTrue(gm.path_ok(_centre(ix, flank), _centre(ix, a)),
                                    where)
                    self.assertTrue(gm.path_ok(_centre(ix, a), _centre(ix, flank)),
                                    where)
                    self.assertTrue(gm.is_walkable(_centre(ix, a), 16.0,
                                                   frm=_centre(ix, flank)),
                                    f"{where}: a small body is refused the door "
                                    f"from its {'west' if dc < 0 else 'east'} flank")
                    self.assertFalse(can_step(ix, flank, north), where)
                    self.assertFalse(can_step(ix, flank, landing), where)
                    self.assertFalse(can_step(ix, landing, flank), where)

    def test_both_nav_classes_can_climb_one(self):
        """From the low landing, the field reaches the terrace tile south of
        the flight, and back the other way.

        Sampled at the tile's four quarter points, not its centre alone: the
        large class walks a 48 px lattice against 64 px tiles, so a tile's
        centre lands in one nav cell that may straddle the tile below it --
        and a tree standing diagonally off the landing can take that one
        cell's clearance under the radius while the tile itself is still
        plainly walkable through its other cells."""
        px = config.TILE_PX

        def quarters(ix, tile):
            centre = _centre(ix, tile)
            return [centre + pygame.Vector2(dx, dy)
                    for dx in (-px / 4, px / 4) for dy in (-px / 4, px / 4)]

        for seed in SEEDS:
            gm = W.game_map(seed)
            layout, ix = gm.layout, gm._levels
            nf = NavField(layout, layout.obstacles)
            for cls, clearance in (("small", 16.0), ("large", body_radii()[1])):
                ff = nf.fields[cls]
                checked = 0
                for room, (c, r), _cell in _north_flights(layout):
                    at = _abs_tiles(room)
                    # up and down, and in from either flank (WLD-014)
                    for frm, to in (((c, r - 1), (c, r + 1)),
                                    ((c, r + 1), (c, r - 1)),
                                    ((c - 1, r), (c, r - 1)),
                                    ((c + 1, r), (c, r - 1))):
                        ff.rebuild(_centre(ix, at(frm)), min_clearance=clearance)
                        self.assertTrue(
                            any(ff.cost_at(p) < _INF
                                for p in quarters(ix, at(to))),
                            f"seed {seed} {cls}: the north flight at {(c, r)} "
                            f"is sealed from {frm}")
                    checked += 1
                self.assertGreater(checked, 5)


def _band_px(surfs, level, wx, wy):
    """The baked pixel of `level`'s band at world `(wx, wy)`, or `None` when
    no band of that level covers the point."""
    for rect, surf, lvl in surfs:
        if lvl == level and rect.collidepoint(wx, wy):
            return tuple(surf.get_at((wx - rect.x, wy - rect.y)))
    return None


def _band_tile(surfs, level, wx, wy, px):
    """`level`'s band cut to the `px` tile whose top-left is world
    `(wx, wy)`, as RGBA bytes, or `None` when no band covers the whole tile."""
    tile = pygame.Rect(wx, wy, px, px)
    for rect, surf, lvl in surfs:
        if lvl == level and rect.contains(tile):
            sub = surf.subsurface(tile.move(-rect.x, -rect.y))
            return pygame.image.tobytes(sub, "RGBA")
    return None


def _expected_landing(sheets, sheet, tag, drop):
    """What a north flight's landing should show, cut here from the source
    art rather than asked of the painter's own helpers: the flipped stone's
    north half for "rock"; for "grass" the channel's low end, its foot
    piece -- the upper half of it for one level, the whole tile for two."""
    if tag == "rock":
        spr = sheets.vstair_sprite(drop, north=True)
        w, h = spr.get_size()
        return spr.subsurface(pygame.Rect(0, 0, w, h // 2)).copy()
    piece = sheets.ramp_slots.get("n") or sheets.ramp_slots.get("s")
    tile = sheets.cell(sheet, piece[-1])
    if drop > 1:
        return tile
    w, h = tile.get_size()
    return tile.subsurface(pygame.Rect(0, 0, w, h // 2)).copy()


class PainterTests(unittest.TestCase):
    """WLD-014: a north flight is a door in the frontier between two floors.
    Its rim cell is plain plateau grass, lip-free, whatever the tag, and the
    connection -- the channel for "grass", the flipped stone for "rock" --
    shows only as its landing half, on the landing's lower half, on the low
    floor's band. Nothing of it lies on the rim."""

    def _landing_matches(self, surfs, level, x0, y0, half, tol):
        """Every pixel the landing half paints opaque is the baked pixel of
        `level`'s band at the landing's lower half. `tol` covers the
        smoothscaled stone, which is a hair short of opaque everywhere, so
        the baked pixel is a blend; the channel tile is exact."""
        w, h = half.get_size()
        checked = 0
        for yy in range(h):
            for xx in range(w):
                want = half.get_at((xx, yy))
                if want.a < 240:
                    continue
                got = _band_px(surfs, level, x0 + xx, y0 - h + yy)
                if got is None or any(abs(a - b) > tol
                                      for a, b in zip(got[:3], tuple(want)[:3])):
                    return False
                checked += 1
        self.assertGreater(checked, w * h // 4, "the half is mostly clear")
        return True

    def test_the_door_shows_on_the_landing_only_and_casts_no_shadow(self):
        from world.terrain.grid_paint import _shadow_casts
        W.display()
        px = config.TILE_PX
        for seed in SEEDS:
            gm = W.baked(seed)
            sheets, surfs = gm._sheets, gm._grid_surfs
            styles, seen = set(), 0
            for room, (c, r), cell in _north_flights(gm.layout):
                where = f"seed {seed} room {room.id} at {(c, r)} ({cell.tag})"
                self.assertEqual(_shadow_casts(room.grid, c, r, cell, 0, 0, px),
                                 [], where)
                low = cell.level - cell.drop
                x0 = room.rect.x + c * px
                y0 = room.rect.y + r * px
                sheet = sheets.sheet_for(cell.level, room.kind, room)
                # The rim tile is the plain interior tile, byte for byte: no
                # lip across the door and no stair or channel on it.
                plain = pygame.image.tobytes(sheets.cell(sheet, sheets.interior),
                                             "RGBA")
                self.assertEqual(_band_tile(surfs, cell.level, x0, y0, px), plain,
                                 f"{where}: the rim is not open plateau grass")
                # The landing's lower half carries the landing half.
                half = _expected_landing(sheets, sheet, cell.tag, cell.drop)
                tol = 8 if cell.tag == "rock" else 0
                self.assertEqual(half.get_size(), (px, px // 2))
                self.assertTrue(self._landing_matches(surfs, low, x0, y0, half, tol),
                                f"{where}: the landing half is not on the landing")
                # ...and on the low band only: the plateau's band is clear
                # over the landing.
                over = _band_px(surfs, cell.level, x0 + px // 2, y0 - px // 4)
                self.assertTrue(over is None or over[3] == 0,
                                f"{where}: the plateau band paints the landing")
                # The landing's upper half, beyond the door, is opaque ground.
                self.assertEqual(_band_px(surfs, low, x0 + px // 2,
                                          y0 - px + px // 4)[3], 255, where)
                styles.add(cell.tag)
                seen += 1
            self.assertGreater(seen, 5)
            self.assertEqual(styles, {"grass", "rock"}, f"seed {seed}")

    def test_the_flanking_rim_keeps_its_lip(self):
        """The lip breaks at the door and nowhere else: the rim cells either
        side of a north flight are still the autotiled north-lip tile, not
        the plain interior tile the door is."""
        W.display()
        px = config.TILE_PX
        for seed in SEEDS:
            gm = W.baked(seed)
            sheets, surfs = gm._sheets, gm._grid_surfs
            for room, (c, r), cell in _north_flights(gm.layout):
                sheet = sheets.sheet_for(cell.level, room.kind, room)
                plain = pygame.image.tobytes(sheets.cell(sheet, sheets.interior),
                                             "RGBA")
                for dc in (-1, 1):
                    # ground by the site rule, so never a second door
                    self.assertEqual(room.grid[(c + dc, r)].kind, GROUND)
                    got = _band_tile(surfs, cell.level,
                                     room.rect.x + (c + dc) * px,
                                     room.rect.y + r * px, px)
                    self.assertNotEqual(got, plain,
                                        f"seed {seed} at {(c + dc, r)}: the "
                                        f"flank lost its lip")

    def test_a_two_level_door_fills_the_whole_landing(self):
        """D2, on a real two-level geometry. The generator places no
        two-level north flight today (NS-5 measured every one as a
        one-level drop), so the island is built by hand: level-0 ground,
        then a level-2 terrace with its wall, the door on its back rim.
        For both tags the rim is plain grass and the landing -- ground at
        level 0 -- shows a whole tile of the connection, on its own band
        and in the composited frame, which is the same picture the
        unbanded painter makes."""
        from types import SimpleNamespace
        from world.gen.height.graph import check_grid
        from world.layout import CLIFF, Cell
        from world.terrain.grid_paint import paint_room_grid, paint_room_levels
        W.display()
        px = config.TILE_PX
        sheets = W.baked(SEEDS[0])._sheets
        for tag in ("rock", "grass"):
            g = {}
            for c in range(7):
                for r in range(3):
                    g[(c, r)] = Cell(GROUND, level=0)
                for r in range(3, 7):
                    g[(c, r)] = Cell(GROUND, level=2)
                g[(c, 7)] = Cell(CLIFF, level=2, drop=2, row=0)
                g[(c, 8)] = Cell(CLIFF, level=2, drop=2, row=1)
            g[(3, 3)] = Cell(VSTAIR, level=2, drop=2, row=0, tag=tag, dir="n")
            self.assertEqual(check_grid(g), [], tag)
            rect = pygame.Rect(0, 0, 7 * px, 9 * px)
            room = SimpleNamespace(id=0, rect=rect, grid=g, kind="",
                                   topography=None)
            bands = paint_room_levels(None, sheets, None, room)
            frame = pygame.Surface(rect.size, pygame.SRCALPHA)
            for brect, surf, _lvl in sorted(bands, key=lambda t: t[2]):
                frame.blit(surf, brect.topleft)
            flat_rect, flat = paint_room_grid(None, sheets, None, room)
            flat_frame = pygame.Surface(rect.size, pygame.SRCALPHA)
            flat_frame.blit(flat, flat_rect.topleft)
            self.assertEqual(pygame.image.tobytes(frame, "RGBA"),
                             pygame.image.tobytes(flat_frame, "RGBA"), tag)

            sheet = sheets.sheet_for(2, "", room)
            x0, y0 = 3 * px, 3 * px
            self.assertEqual(_band_tile(bands, 2, x0, y0, px),
                             pygame.image.tobytes(sheets.cell(sheet, sheets.interior),
                                                  "RGBA"), f"{tag}: rim")
            half = _expected_landing(sheets, sheet, tag, 2)
            self.assertEqual(half.get_size(), (px, px), tag)
            tol = 8 if tag == "rock" else 0
            self.assertTrue(self._landing_matches(bands, 0, x0, y0, half, tol),
                            f"{tag}: not a whole tile on the landing's band")
            self.assertTrue(self._landing_matches([(rect, frame, 0)], 0, x0, y0,
                                                  half, tol),
                            f"{tag}: hidden in the composited frame")

    def test_south_flights_are_still_painted_as_flights(self):
        """The regression the north branch caused once: every wall-cut
        flight fell through to the east/west branch and came out as a bare
        cliff face. A south flight's head is the grass channel piece with,
        when "rock", the stone flight over it -- composed here as the
        painter composes it and compared pixel for pixel at the centre.
        Both styles must be seen per seed, or the test proves nothing."""
        W.display()
        px = config.TILE_PX
        for seed in SEEDS:
            gm = W.baked(seed)
            sheets = gm._sheets
            styles = set()
            for room in gm.layout.rooms:
                for (c, r), cell in room.grid.items():
                    if cell.kind != VSTAIR or cell.dir != "s" or cell.row != 0:
                        continue
                    sheet = sheets.sheet_for(cell.level, room.kind, room)
                    piece = sheets.ramp_slots.get("s")
                    idx = piece[0] if cell.drop > 1 else piece[-1]
                    tile = sheets.cell(sheet, idx).copy()
                    if cell.tag == "rock":
                        tile.blit(sheets.vstair_sprite(cell.drop), (0, 0))
                    want = tuple(tile.get_at((px // 2, px // 2)))
                    wx = room.rect.x + c * px + px // 2
                    wy = room.rect.y + r * px + px // 2
                    # the flight stands on the terrace below it, so it is
                    # painted on that terrace's band
                    hit = [(rect, surf) for rect, surf, lvl in gm._grid_surfs
                           if lvl == cell.level - cell.drop
                           and rect.collidepoint(wx, wy)]
                    self.assertTrue(hit, f"seed {seed}: no band under {(c, r)}")
                    rect, surf = hit[0]
                    got = tuple(surf.get_at((wx - rect.x, wy - rect.y)))
                    self.assertEqual(got, want, f"seed {seed}: south {cell.tag} "
                                     f"flight at {(c, r)} is not painted as a "
                                     f"flight")
                    styles.add(cell.tag)
            self.assertEqual(styles, {"grass", "rock"}, f"seed {seed}")

    def test_the_north_sprite_is_the_south_one_upside_down(self):
        """Derived at load, so it stays in step with the authored file: the
        foot line -- the darkest row of the south sprite, at its bottom --
        is the top row of the north one."""
        W.display()
        sheets = W.baked(SEEDS[0])._sheets
        south = sheets.vstair_sprite(1)
        north = sheets.vstair_sprite(1, north=True)
        self.assertIsNotNone(south)
        self.assertEqual(north.get_size(), south.get_size())
        w, h = south.get_size()
        for y in (0, h // 3, h - 1):
            for x in (w // 4, w // 2, 3 * w // 4):
                self.assertEqual(tuple(north.get_at((x, y))),
                                 tuple(south.get_at((x, h - 1 - y))))
        self.assertIs(north, sheets.vstair_sprite(1, north=True), "cached")


if __name__ == "__main__":
    unittest.main()
