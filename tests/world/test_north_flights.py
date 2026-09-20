"""North flights: the straight flight on a plateau's back.

A north face has no wall (`_raise_walls` only stones southward drops), so
the flight is the rim cell itself, one cell whatever the drop, with the low
ground north of it and its own terrace south::

    = = = = = =            = = = = = =
    # # # # # #     ->     # # # ^ # #
    # # # # # #            # # # # # #

The hand-built grids pin the site rule and the link rule; the shared worlds
check that the generator actually places them, that the runtime step rule
mirrors the generator on every one, and that both nav classes can climb
them. See `documentation/journals/north_stairs_journal.md`.
"""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from tests import worlds as W
from world.gen.height.flights import (_nstair_site, _cut, _cut_flights,
                                      _cut_north_flights)
from world.gen.height.graph import walk_links, check_grid, to_ascii
from world.layout import Cell, GROUND, CLIFF, VSTAIR, EWSTAIR
from world.pathfinding import NavField, _INF
from world.rules.steps import can_cross

SEEDS = (35, 7)


def _grid(rows, levels):
    """A grid from ASCII rows: `=` ground, `#` cliff (level 1 over 0), `.`
    void; `levels` gives each row's ground level."""
    grid = {}
    for r, line in enumerate(rows):
        for c, ch in enumerate(line.split()):
            if ch == "=":
                grid[(c, r)] = Cell(GROUND, level=levels[r])
            elif ch == "#":
                grid[(c, r)] = Cell(CLIFF, level=1, drop=1, row=0)
    return grid


def _plateau():
    """Three rows of level-0 back ground, then a level-1 terrace whose wall
    hangs over open water. The terrace is stranded -- its only possible way
    up is a north flight on its rim -- so `check_grid` complains until one
    is cut and is clean afterwards.

        = = = = = = =     0
        = = = = = = =     0
        = = = = = = =     0
        = = = = = = =     1   <- the rim, where a north flight may go
        = = = = = = =     1
        # # # # # # #     the wall, over the sea
    """
    rows = ["= = = = = = =", "= = = = = = =", "= = = = = = =",
            "= = = = = = =", "= = = = = = =", "# # # # # # #"]
    return _grid(rows, [0, 0, 0, 1, 1, 1])


class SiteRuleTests(unittest.TestCase):
    def test_a_rim_cell_with_room_to_land_qualifies(self):
        g = _plateau()
        self.assertEqual(_nstair_site(g, 3, 3), 1)

    def test_the_flight_takes_the_rim_cell_and_nothing_else(self):
        g = _plateau()
        self.assertTrue(any("unreachable" in s for s in check_grid(g)),
                        "the fixture's terrace should start stranded")
        before = dict(g)
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        cell = g[(3, 3)]
        self.assertEqual((cell.kind, cell.level, cell.drop, cell.row, cell.dir),
                         (VSTAIR, 1, 1, 0, "n"))
        changed = [p for p in g if g[p] != before[p]]
        self.assertEqual(changed, [(3, 3)])
        self.assertEqual(check_grid(g), [])
        self.assertIn("^", to_ascii(g))

    def test_the_cell_has_to_be_terrace_ground(self):
        g = _plateau()
        self.assertIsNone(_nstair_site(g, 3, 2), "level-0 ground is not a rim")
        self.assertIsNone(_nstair_site(g, 3, 5), "a wall cell is not a rim")
        self.assertIsNone(_nstair_site(g, 3, 4),
                          "a cell with its own terrace north is not the rim")

    def test_the_terrace_must_continue_south_and_on_both_flanks(self):
        for missing in ((2, 3), (4, 3), (3, 4)):
            g = _plateau()
            del g[missing]
            self.assertIsNone(_nstair_site(g, 3, 3), f"without {missing}")
        g = _plateau()
        g[(2, 3)] = Cell(GROUND, level=0)
        self.assertIsNone(_nstair_site(g, 3, 3), "a flank at the low level")

    def test_the_landing_needs_room_for_a_large_body(self):
        for missing in ((2, 2), (4, 2), (3, 1)):
            g = _plateau()
            del g[missing]
            self.assertIsNone(_nstair_site(g, 3, 3), f"without {missing}")

    def test_a_two_level_drop_qualifies_but_three_does_not(self):
        g = _plateau()
        for p, c in list(g.items()):
            if c.level == 1:
                g[p] = c._replace(level=2, drop=2 if c.kind == CLIFF else 0)
        self.assertEqual(_nstair_site(g, 3, 3), 2)
        for p, c in list(g.items()):
            if c.level == 2:
                g[p] = c._replace(level=3)
        self.assertIsNone(_nstair_site(g, 3, 3))

    def test_the_wall_pass_finds_nothing_and_the_north_pass_places_one(self):
        """The wall hangs over water, so `_cut_flights` has no site at all;
        the north pass has the whole rim to choose from -- one region, one
        cut."""
        g = _plateau()
        _cut_flights(g, random.Random(1), per_region=1, region=8, spacing=4)
        self.assertFalse([c for c in g.values() if c.kind in (VSTAIR, EWSTAIR)])
        _cut_north_flights(g, random.Random(1), per_region=1, region=8,
                           spacing=4)
        north = [p for p, c in g.items() if c.kind == VSTAIR and c.dir == "n"]
        self.assertEqual(len(north), 1)
        self.assertEqual(north[0][1], 3, "on the rim row")
        self.assertEqual(check_grid(g), [])

    def test_the_north_pass_draws_nothing_the_stream_sees(self):
        """`build_grid` restores the stream round the pass; the pass itself
        must therefore be the only thing that reads its own draws, which is
        the property this pins: two runs from equal states cut the same
        flight."""
        a, b = _plateau(), _plateau()
        _cut_north_flights(a, random.Random(7))
        _cut_north_flights(b, random.Random(7))
        self.assertEqual(a, b)

    def test_a_cut_that_would_sever_its_own_flank_is_rolled_back(self):
        """A rim cell may be the only thing joining a strip of terrace to the
        rest -- level 1 pinched between the low ground and a higher cap. A
        flight links only at its ends, so taking that cell strands the strip
        (and the prune would then delete the flight's own flank). The cut
        stands only if both flanks still reach the terrace another way."""
        g = _plateau()
        # a level-2 cap under the west half of the rim: cells (0..3, 4)
        for c in range(4):
            g[(c, 4)] = Cell(GROUND, level=2)
        self.assertEqual(_nstair_site(g, 4, 3), 1, "the site itself is fine")
        before = dict(g)
        self.assertFalse(_cut(g, 4, 3, VSTAIR, "rock", 1, "n"))
        self.assertEqual(g, before, "a rolled-back cut leaves no trace")
        # further east the strip is joined on both sides: the cut stands
        self.assertTrue(_cut(g, 5, 3, VSTAIR, "rock", 1, "n"))
        self.assertEqual(g[(5, 3)].dir, "n")

    def test_the_north_pass_joins_a_stranded_terrace_from_its_back(self):
        """With no regional quota at all, the join loop alone still reaches
        the stranded cap."""
        g = _plateau()
        _cut_north_flights(g, random.Random(1), per_region=0)
        north = [p for p, c in g.items() if c.kind == VSTAIR and c.dir == "n"]
        self.assertEqual(len(north), 1, "joined by the stranded-cap loop")
        self.assertEqual(check_grid(g), [])


class LinkRuleTests(unittest.TestCase):
    def test_down_is_north_and_up_is_south(self):
        g = _plateau()
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        self.assertEqual(set(walk_links(g, (3, 3))), {(3, 2), (3, 4)})
        self.assertIn((3, 3), walk_links(g, (3, 2)))
        self.assertIn((3, 3), walk_links(g, (3, 4)))
        # the flanks are the same terrace but a flight links only at its ends
        self.assertNotIn((3, 3), walk_links(g, (2, 3)))
        self.assertNotIn((3, 3), walk_links(g, (4, 3)))

    def test_check_grid_names_a_flight_leading_nowhere(self):
        g = _plateau()
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        g[(3, 2)] = Cell(GROUND, level=1)
        self.assertTrue(any("no low landing" in s for s in check_grid(g)))
        g = _plateau()
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        g[(3, 4)] = Cell(GROUND, level=0)
        self.assertTrue(any("no terrace to the south" in s
                            for s in check_grid(g)))

    def test_ascii_shows_the_orientation(self):
        g = _plateau()
        _cut(g, 3, 3, VSTAIR, "rock", 1, "n")
        lines = to_ascii(g).splitlines()
        self.assertEqual(lines[3].split()[3], "^")
        self.assertEqual(set(lines[5].split()), {"#"})


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
            for cls, clearance in (("small", 16.0), ("large", 22.0)):
                ff = nf.fields[cls]
                checked = 0
                for room, (c, r), _cell in _north_flights(layout):
                    at = _abs_tiles(room)
                    for frm, to in (((c, r - 1), (c, r + 1)),
                                    ((c, r + 1), (c, r - 1))):
                        ff.rebuild(_centre(ix, at(frm)), min_clearance=clearance)
                        self.assertTrue(
                            any(ff.cost_at(p) < _INF
                                for p in quarters(ix, at(to))),
                            f"seed {seed} {cls}: the north flight at {(c, r)} "
                            f"is sealed from {frm}")
                    checked += 1
                self.assertGreater(checked, 5)


class PainterTests(unittest.TestCase):
    def test_the_stairs_sit_on_the_seam_and_cast_no_shadow(self):
        """No shadow blob on the low ground north of a north flight; the
        stairs centred on the seam, half on each tile, each half on its own
        floor's band, grass and rock alike. Where the sprite is opaque the
        baked pixel *is* the sprite's pixel: the foot half on the landing's
        lower half, the top half on the rim's upper half. Outside the
        sprite the rim is plateau ground and the landing is low ground,
        both opaque."""
        from world.terrain.grid_paint import _shadow_casts
        W.display()
        px = config.TILE_PX

        def baked(gm, level, wx, wy):
            hit = [(rect, surf) for rect, surf, lvl in gm._grid_surfs
                   if lvl == level and rect.collidepoint(wx, wy)]
            self.assertTrue(hit, f"no band {level} at {(wx, wy)}")
            rect, surf = hit[0]
            return tuple(surf.get_at((wx - rect.x, wy - rect.y)))

        def opaque_point(half):
            """The most opaque pixel down the half's middle column. The
            smoothscaled art is a hair short of opaque everywhere, so the
            baked pixel is a blend and is compared with a small tolerance."""
            x = half.get_width() // 2
            y = max(range(half.get_height()), key=lambda yy: half.get_at((x, yy)).a)
            self.assertGreaterEqual(half.get_at((x, y)).a, 240)
            return x, y

        def close(got, want):
            return all(abs(a - b) <= 8 for a, b in zip(got[:3], want[:3]))

        for seed in SEEDS:
            gm = W.baked(seed)
            foot, top = gm._sheets.vstair_seam(1)
            self.assertEqual(foot.get_size(), (px, px // 2))
            self.assertEqual(top.get_size(), (px, px // 2))
            tx, ty = opaque_point(top)
            fx, fy = opaque_point(foot)
            seen = 0
            styles = set()
            sheets = gm._sheets
            piece = sheets.ramp_slots.get("n") or sheets.ramp_slots.get("s")
            for room, (c, r), cell in _north_flights(gm.layout):
                self.assertEqual(_shadow_casts(room.grid, c, r, cell, 0, 0, px),
                                 [])
                low = cell.level - cell.drop
                x0 = room.rect.x + c * px
                y0 = room.rect.y + r * px
                sx = px // 2
                # NS-7: one thing or the other, never both.
                channel = sheets.cell(sheets.sheet_for(cell.level, room.kind, room),
                                      piece[-1])
                if cell.tag == "rock":
                    # the rim's upper half carries the top half of the sprite
                    self.assertTrue(close(baked(gm, cell.level, x0 + tx, y0 + ty),
                                          tuple(top.get_at((tx, ty)))),
                                    f"seed {seed}: no top step on the rim at {(c, r)}")
                    # the landing's lower half carries the foot half
                    self.assertTrue(close(baked(gm, low, x0 + fx, y0 - px // 2 + fy),
                                          tuple(foot.get_at((fx, fy)))),
                                    f"seed {seed}: no foot on the landing at {(c, r)}")
                    # and below the stone the rim is plain plateau ground,
                    # not the channel: no side lip where the channel has one
                    self.assertNotEqual(baked(gm, cell.level, x0 + 2, y0 + 3 * px // 4),
                                        tuple(channel.get_at((2, 3 * px // 4))),
                                        f"seed {seed}: channel under the stone at {(c, r)}")
                    self.assertEqual(baked(gm, cell.level, x0 + sx, y0 + 3 * px // 4)[3],
                                     255)
                else:
                    # a grass flight: plain plateau grass on the rim cell's
                    # lower half, and the channel straddling the seam --
                    # its lower half on the rim's upper half (plateau band),
                    # its upper half on the landing's lower half (low band)
                    plain = sheets.cell(sheets.sheet_for(cell.level, room.kind, room),
                                        sheets.interior)
                    self.assertEqual(baked(gm, cell.level, x0 + sx, y0 + 3 * px // 4),
                                     tuple(plain.get_at((sx, 3 * px // 4))),
                                     f"seed {seed}: rim under the channel is not plain "
                                     f"grass at {(c, r)}")
                    # the lip: the first opaque pixel in from the tile's
                    # left edge on that row (the margin outside it is clear)
                    def lip(row):
                        return next(xx for xx in range(px // 2)
                                    if channel.get_at((xx, row)).a == 255)
                    lx = lip(px // 2 + px // 4)
                    self.assertEqual(baked(gm, cell.level, x0 + lx, y0 + px // 4),
                                     tuple(channel.get_at((lx, px // 2 + px // 4))),
                                     f"seed {seed}: no channel lip on the rim at {(c, r)}")
                    lx = lip(px // 4)
                    self.assertEqual(baked(gm, low, x0 + lx, y0 - px // 4),
                                     tuple(channel.get_at((lx, px // 4))),
                                     f"seed {seed}: no channel lip on the landing at {(c, r)}")
                    self.assertEqual(baked(gm, cell.level, x0 + tx, y0 + ty),
                                     tuple(channel.get_at((tx, px // 2 + ty))),
                                     f"seed {seed}: stone on a grass flight at {(c, r)}")
                # and the landing beyond the sprite is opaque ground
                self.assertEqual(baked(gm, low, x0 + sx, y0 - px + px // 4)[3],
                                 255)
                styles.add(cell.tag)
                seen += 1
            self.assertGreater(seen, 5)
            self.assertEqual(styles, {"grass", "rock"}, f"seed {seed}")

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
