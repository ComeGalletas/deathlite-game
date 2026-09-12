"""ui/bars: the HUD bar 3-slice, the exact-length fill, and the level gem.

The claims that matter are geometric, so the assertions sample pixels against
the sheet itself rather than trusting a size: a cap must be the artist's cap,
a fill must stop where the fraction says, and the frameless XP bar must sit at
the same horizontal inset as the framed HP bar so the two line up in the HUD.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.assets import Assets, reset_assets
from ui import bars
from ui.bars import slices

FRAME = "bar_hex_frame_silver"
HP_FILL = "bar_hex_fill_red"
XP_FILL = "bar_hex_fill_blue"
EMPTY = "bar_hex_empty"
WIDTH = 104


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def setUp(self):
        reset_assets()
        bars.clear_cache()
        self.assets = Assets()

    # --- shared geometry helpers ---------------------------------
    def well(self):
        return tuple(self.assets.rig(FRAME)["well"])

    def track(self, width=WIDTH):
        ww = self.well()[2]
        return width - (self.assets.image(FRAME).get_width() - ww)

    def fill_end(self, surf, fill_rig, y):
        """Rightmost x on row `y` carrying a colour only the fill uses, or -1."""
        src = self.assets.image(fill_rig)
        mid = src.get_height() // 2
        colours = {tuple(src.get_at((x, mid)))
                   for x in range(2, src.get_width() - 2)}
        found = -1
        for x in range(surf.get_width()):
            if tuple(surf.get_at((x, y))) in colours:
                found = x
        return found


class SliceTests(_Base):
    """`slices.hslice`: a 48-px cell rebuilt at any length."""

    def test_rebuilds_to_the_asked_width_at_the_native_height(self):
        src = self.assets.image(FRAME)
        out = slices.hslice(self.assets, FRAME, 200)
        self.assertEqual(out.get_size(), (200, src.get_height()))

    def test_caps_are_copied_pixel_for_pixel(self):
        # Housing and fill alike: the ends on screen are the artist's ends.
        # For the fill this is what keeps the hex terminus authored at every
        # length instead of becoming a blunt vertical cut.
        for rig in (FRAME, HP_FILL, XP_FILL, EMPTY):
            src = self.assets.image(rig)
            left, right = slices.caps(self.assets, rig)
            out = slices.hslice(self.assets, rig, 200)
            for y in range(src.get_height()):
                for x in range(left):
                    self.assertEqual(out.get_at((x, y)), src.get_at((x, y)),
                                     f"{rig} left cap differs at {x},{y}")
                for x in range(right):
                    self.assertEqual(out.get_at((200 - right + x, y)),
                                     src.get_at((src.get_width() - right + x, y)),
                                     f"{rig} right cap differs at {x},{y}")

    def test_the_middle_band_is_the_sheet_column_repeated(self):
        # The whole point of the 3-slice: the sheet's middle is one column wide
        # in effect, so stretching it cannot introduce a colour of its own.
        src = self.assets.image(FRAME)
        left, right = slices.caps(self.assets, FRAME)
        out = slices.hslice(self.assets, FRAME, 200)
        column = [src.get_at((left, y)) for y in range(src.get_height())]
        for x in range(left, 200 - right):
            self.assertEqual([out.get_at((x, y)) for y in range(out.get_height())],
                             column, f"middle differs at x={x}")

    def test_width_under_the_two_caps_is_clamped_not_crashed(self):
        left, right = slices.caps(self.assets, FRAME)
        self.assertEqual(slices.hslice(self.assets, FRAME, 1).get_width(),
                         left + right)

    def test_missing_rig_is_none(self):
        self.assertIsNone(slices.hslice(self.assets, "no_such_rig", 100))

    def test_the_same_request_is_served_from_cache(self):
        self.assertIs(slices.hslice(self.assets, FRAME, 120),
                      slices.hslice(self.assets, FRAME, 120))


class BarTests(_Base):
    """`bars.bar`: housing + trough + a fill cut to the exact fraction."""

    def bar(self, fraction, **kw):
        kw.setdefault("framed", True)
        return bars.bar(self.assets, frame=FRAME, fill=HP_FILL, empty=EMPTY,
                        width=WIDTH, fraction=fraction, **kw)

    def hp_end(self, surf):
        wy = self.well()[1]
        return self.fill_end(surf, HP_FILL,
                             wy + self.assets.image(HP_FILL).get_height() // 2)

    def test_framed_bar_is_the_housing_size(self):
        housing = self.assets.image(FRAME)
        self.assertEqual(self.bar(0.5).get_size(),
                         (WIDTH, housing.get_height()))

    def test_frameless_bar_is_only_as_tall_as_the_fill(self):
        self.assertEqual(self.bar(0.5, framed=False).get_size(),
                         (WIDTH, self.well()[3]))

    def test_scale_multiplies_both_axes(self):
        plain, big = self.bar(0.5), self.bar(0.5, scale=3)
        self.assertEqual(big.get_size(),
                         (plain.get_width() * 3, plain.get_height() * 3))

    def test_the_fill_tracks_the_fraction(self):
        ends = [self.hp_end(self.bar(f)) for f in (0.25, 0.5, 0.75, 1.0)]
        self.assertEqual(ends, sorted(ends), "more HP drew less bar")
        wx, track = self.well()[0], self.track()
        self.assertAlmostEqual(ends[1], wx + track // 2, delta=3)
        self.assertGreaterEqual(ends[3], wx + track - 3)

    def test_the_bar_seats_the_authored_fill_slice_in_the_well(self):
        # The sheet's six pre-rendered steps exist for their right cap, and
        # cutting the 100 % sprite to an arbitrary length carries that cap
        # along. So the bar must contain exactly the slice -- hex point
        # included -- laid at the well, not an edge of our own making.
        wx, wy, _, _ = self.well()
        checked = 0
        for fraction in (0.37, 0.61, 0.88):
            want = slices.hslice(self.assets, HP_FILL,
                                 round(self.track() * fraction))
            out = self.bar(fraction)
            for y in range(want.get_height()):
                for x in range(want.get_width()):
                    ink = want.get_at((x, y))
                    # The hex point tapers: where the slice is transparent the
                    # trough behind it shows through, which is intended.
                    if ink[3] == 0:
                        continue
                    self.assertEqual(out.get_at((wx + x, wy + y)), ink,
                                     f"fill differs at {x},{y} (f={fraction})")
                    checked += 1
        self.assertGreater(checked, 0, "the fill was never actually compared")

    def test_an_empty_bar_draws_no_fill_colour(self):
        self.assertEqual(self.hp_end(self.bar(0.0)), -1)

    def test_a_sliver_too_short_for_its_caps_draws_nothing(self):
        # One pixel of a 4-px-capped hex fill would have to be widened to be
        # drawn at all, which would show health an almost-dead hero lacks.
        self.assertEqual(self.hp_end(self.bar(0.5 / self.track())), -1)

    def test_fraction_is_clamped_both_ways(self):
        self.assertEqual(self.hp_end(self.bar(-5.0)), self.hp_end(self.bar(0.0)))
        self.assertEqual(self.hp_end(self.bar(5.0)), self.hp_end(self.bar(1.0)))

    def test_the_trough_spans_the_whole_track_behind_an_empty_bar(self):
        wx, wy, _, wh = self.well()
        out = self.bar(0.0)
        row = wy + wh // 2
        for x in range(wx + 2, wx + self.track() - 2):
            self.assertGreater(out.get_at((x, row))[3], 0,
                               f"hole in the empty trough at x={x}")

    def test_the_xp_bar_lines_up_under_the_hp_bar(self):
        # The frameless bar keeps the housing's inset; that is the only reason
        # the two bars agree on where their track starts and ends.
        wy = self.well()[1]
        hp = self.bar(1.0)
        xp = bars.bar(self.assets, frame=FRAME, fill=XP_FILL, empty=EMPTY,
                      width=WIDTH, fraction=1.0, framed=False)
        hp_row = wy + self.assets.image(HP_FILL).get_height() // 2
        xp_row = self.assets.image(XP_FILL).get_height() // 2
        self.assertEqual(self.fill_end(hp, HP_FILL, hp_row),
                         self.fill_end(xp, XP_FILL, xp_row))

    def test_missing_rig_is_none(self):
        self.assertIsNone(bars.bar(self.assets, frame="no_such_rig",
                                   fill=HP_FILL, empty=EMPTY, width=WIDTH,
                                   fraction=0.5))

    def test_the_same_request_is_served_from_cache(self):
        self.assertIs(self.bar(0.5), self.bar(0.5))


class MedallionTests(_Base):
    """`bars.medallion`: the gem seated in its socket ring."""

    def gem(self, size=64):
        return bars.medallion(self.assets, socket=config.HUD_GEM_SOCKET,
                              core=config.HUD_GEM_CORE, size=size)

    def test_it_is_square_at_the_asked_size(self):
        self.assertEqual(self.gem(64).get_size(), (64, 64))

    def test_the_ring_goes_over_the_gem(self):
        # Order is the trick: ring pixels must survive compositing, or the
        # thing reads as a blob rather than a stone set into metal.
        ring = self.assets.image(config.HUD_GEM_SOCKET)
        out = self.gem(ring.get_width())
        kept = sum(1 for y in range(ring.get_height())
                   for x in range(ring.get_width())
                   if ring.get_at((x, y))[3] == 255
                   and out.get_at((x, y)) == ring.get_at((x, y)))
        self.assertGreater(kept, 200)

    def test_the_gem_fills_the_rings_hollow(self):
        ring = self.assets.image(config.HUD_GEM_SOCKET)
        out = self.gem(ring.get_width())
        cx, cy = ring.get_width() // 2, ring.get_height() // 2
        self.assertEqual(ring.get_at((cx, cy))[3], 0)      # the socket is hollow
        self.assertGreater(out.get_at((cx, cy))[3], 0)     # the gem fills it

    def test_missing_rig_is_none(self):
        self.assertIsNone(bars.medallion(self.assets, socket="no_such_rig",
                                         core=config.HUD_GEM_CORE, size=64))


class RigDataTests(_Base):
    """`data/ui_sprites.json`: the sheet coordinates the bars are cut from."""

    def test_every_bar_rig_declares_its_caps(self):
        for rig in (FRAME, HP_FILL, XP_FILL, EMPTY, "bar_hex_frame_grey",
                    "bar_hex_frame_copper", "bar_hex_fill_yellow",
                    "bar_hex_fill_green"):
            left, right = slices.caps(self.assets, rig)
            self.assertGreater(left + right, 0, f"{rig} has no caps")

    def test_the_well_matches_the_fill_it_holds(self):
        # The housing's trough and the fill sprite have to be the same size,
        # or the fill would rattle around inside the frame.
        wx, _, ww, wh = self.well()
        fill = self.assets.image(HP_FILL)
        self.assertEqual((ww, wh), fill.get_size())
        housing = self.assets.image(FRAME)
        self.assertEqual(wx, housing.get_width() - ww - wx,
                         "the fill is not centred in its housing")
