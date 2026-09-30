"""ENT-019: the crowd bump at any frame rate (`journals/bump_frame_rate_journal.md`).

The bump pass shoves every overlapping pair once a frame, so before ENT-019 a
faster frame rate shoved harder a second. `physics.bump_scale(dt)` now sizes
a frame faster than 62 fps to shove at the same speed a game-second; a frame
of 1/62 s or longer is left exactly as it was (owner, ENT-019.D5).

* The factor's own rules, and `resolve(dt)` applying it, on stub bodies.
* The bench, `tools/benchmarks/bump_rate.py`: one packed crowd and two
  hand-built pairs stepped for the same game time at several rates, with the
  real `Enemy.update`. At 144 and 165 Hz they come apart as at 62 Hz, within
  the bounds below; the pass before ENT-019 (`B.unscaled()`) fails the same
  bounds, so they catch the bug. The bench is held to what its tables rely
  on: a trial is a pure function of its start, the pairs start where they
  are said to, and the series readers interpolate between frames.

The bit-for-bit pin at 62 fps and below is `test_bump_exact.py`'s.
"""
import unittest
from types import SimpleNamespace
from unittest import mock

from game import config
from game.states.playing.core import physics
from game.states.playing.core.physics import BumpResolver, bump_scale, tuned_dt
from tests.playing.test_bump import Body
from tools.benchmarks import bump_rate as B

# The tuned frame: 16 ms, the loop's millisecond frame at the 62 fps cap.
TUNED_DT = tuned_dt()
FAST = (75, 120, 144, 165, 240)          # Hz, shorter frames than the tuned one
# Every frame left as it was: the tuned one, exactly 1/62 s, the loop's 17
# and 18 ms frames at the cap, 60 Hz vsync, heavy scenes, the longest allowed.
SLOW_DTS = (TUNED_DT, 1 / 62, 0.017, 0.018, 1 / 60, 1 / 45, 1 / 30, config.MAX_DT)

# The bench's bounds at 144 and 165 Hz, as a share of the 62 Hz value.
# Measured with the fix (journal, "ENT-019.3: the pass after the fix"): the
# crowd's times 89-105 %, the pairs' distance and peak knock 93-99 %. Before
# it: 57-76 % and 133-167 %.
CROWD_BOUND = (0.85, 1.15)
PAIR_BOUND = (0.90, 1.10)


class BumpScaleTests(unittest.TestCase):
    def test_the_tuned_frame_is_the_loops_frame_at_the_cap(self):
        # `clock.tick` counts whole ms: a 62 fps cap is 16 ms frames.
        self.assertEqual(TUNED_DT, 16 / 1000)
        self.assertEqual(TUNED_DT, (1000 // config.BUMP_REFERENCE_FPS) / 1000)

    def test_every_shorter_loop_frame_shoves_less_and_meets_1_at_the_tuned_one(self):
        shares = [bump_scale(ms / 1000) for ms in range(1, 16)]
        self.assertTrue(all(0.0 < s < 1.0 for s in shares), shares)
        self.assertEqual(shares, sorted(shares))
        self.assertAlmostEqual(bump_scale(TUNED_DT - 1e-9), 1.0, places=6)

    def test_a_frame_of_no_time_or_a_nonsense_one_shoves_nothing(self):
        for dt in (0.0, -0.01, float("nan")):
            with self.subTest(dt=dt):
                self.assertEqual(bump_scale(dt), 0.0)

    def test_a_tuned_or_slower_frame_is_exactly_the_tuned_shove(self):
        for dt in SLOW_DTS:
            with self.subTest(fps=round(1 / dt, 2)):
                self.assertEqual(bump_scale(dt), 1.0)

    def test_a_faster_frame_shoves_less_and_less(self):
        shares = [bump_scale(1.0 / hz) for hz in FAST]
        self.assertTrue(all(0.0 < s < 1.0 for s in shares), shares)
        self.assertEqual(shares, sorted(shares, reverse=True))

    def test_a_held_overlap_is_shoved_at_the_same_speed_at_any_faster_rate(self):
        # A pair held at one overlap is handed the same shove every frame,
        # and its knock decays between frames: it settles where the decay
        # takes away what a frame adds. That speed is the shove's size a
        # second, and it must be the tuned rate's at every faster rate.
        def settled(dt):
            give = config.BUMP_GAIN * 10.0 * bump_scale(dt)
            keep = config.BUMP_DECAY ** dt
            knock = 0.0
            for _ in range(round(20 / dt)):
                knock = knock * keep + give
            return knock
        tuned = settled(TUNED_DT)
        for dt in [1.0 / hz for hz in FAST] + [ms / 1000 for ms in (4, 7, 11, 15)]:
            with self.subTest(fps=round(1 / dt, 2)):
                self.assertAlmostEqual(settled(dt) / tuned, 1.0, places=9)

    def test_the_reference_is_not_the_loop_cap(self):
        # The web profile sets `FPS` to 60; the bump keeps its tuning.
        want = bump_scale(1 / 144)
        for fps in (60, 144):
            with self.subTest(fps=fps), mock.patch.object(config, "FPS", fps):
                self.assertEqual(tuned_dt(), TUNED_DT)
                self.assertEqual(bump_scale(TUNED_DT), 1.0)
                self.assertEqual(bump_scale(1 / 144), want)

    def test_a_knock_that_never_decays_scales_with_the_frame(self):
        with mock.patch.object(config, "BUMP_DECAY", 1.0):
            self.assertAlmostEqual(bump_scale(TUNED_DT / 2), 0.5)
            self.assertEqual(bump_scale(TUNED_DT), 1.0)


class ResolveTests(unittest.TestCase):
    """`resolve(dt)` on stub bodies: an enemy pair, and the hero with a bug."""

    def _knocks(self, dt):
        a, b = Body(0, 0, 14, 7), Body(12, 0, 14, 7)
        hero = Body(100, 0, 12, 40)
        bug = Body(110, 0, 8, 3)
        ps = SimpleNamespace(enemies=[a, b, bug], boss=None, player=hero,
                             elements=None, stats={"time": 0.0})
        BumpResolver(ps).resolve(dt)
        return [(k.x, k.y) for k in (a._knock, b._knock, bug._knock, hero._knock)]

    def test_a_faster_frame_shoves_its_share_of_the_tuned_one(self):
        tuned = self._knocks(TUNED_DT)
        self.assertTrue(all(k != (0.0, 0.0) for k in tuned), tuned)
        for hz in FAST:
            share = bump_scale(1.0 / hz)
            with self.subTest(hz=hz):
                for got, want in zip(self._knocks(1.0 / hz), tuned):
                    self.assertAlmostEqual(got[0], want[0] * share, places=9)
                    self.assertAlmostEqual(got[1], want[1] * share, places=9)

    def test_a_slower_frame_shoves_the_tuned_amount_bit_for_bit(self):
        tuned = self._knocks(TUNED_DT)
        for dt in SLOW_DTS:
            with self.subTest(fps=round(1 / dt, 2)):
                self.assertEqual(self._knocks(dt), tuned)

    def test_the_pass_reads_the_factor_every_frame(self):
        # Patched, as the bench's `unscaled` patches it: the pass looks the
        # factor up by name each call, so the bench's `--unscaled` table is
        # the pass before ENT-019.
        with mock.patch.object(physics, "bump_scale", lambda _dt: 1.0):
            self.assertEqual(self._knocks(1 / 144), self._knocks(TUNED_DT))


class SeriesReaderTests(unittest.TestCase):
    """`at` and `time_to`: the rates do not share frame times, so both read
    between frames."""

    SERIES = [(0.0, 100.0), (0.1, 60.0), (0.2, 20.0), (0.3, 20.0)]

    def test_at_reads_between_frames(self):
        self.assertAlmostEqual(B.at(self.SERIES, 0.05), 80.0)
        self.assertAlmostEqual(B.at(self.SERIES, 0.1), 60.0)
        self.assertAlmostEqual(B.at(self.SERIES, 0.15), 40.0)

    def test_at_past_the_end_is_the_last_value(self):
        self.assertEqual(B.at(self.SERIES, 9.0), 20.0)

    def test_time_to_interpolates_the_crossing(self):
        self.assertAlmostEqual(B.time_to(self.SERIES, 0.5), 0.125)
        self.assertAlmostEqual(B.time_to(self.SERIES, 0.6), 0.1)

    def test_time_to_a_level_never_reached_is_none(self):
        self.assertIsNone(B.time_to(self.SERIES, 0.1))


class CommandLineTests(unittest.TestCase):
    def test_defaults(self):
        a = B.parse([])
        self.assertEqual(a.rates, list(B.RATES))
        self.assertEqual((a.seed, a.live, a.pack, a.seconds), (B.SEED, B.LIVE, B.PACK, 2.0))
        self.assertFalse(a.markdown)
        self.assertFalse(a.unscaled)

    def test_a_rate_or_a_duration_of_zero_is_refused(self):
        for argv in (["--rates", "0"], ["--seconds", "0"], ["--rates", "30", "-62"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit):
                B.parse(argv)

    def test_unscaled_puts_the_factor_back(self):
        real = physics.bump_scale
        with B.unscaled():
            self.assertEqual(physics.bump_scale(1 / 144), 1.0)
        self.assertIs(physics.bump_scale, real)


class BenchTests(unittest.TestCase):
    """One booted run (seed 35), shared by every test here."""

    @classmethod
    def setUpClass(cls):
        cls.bench = B.Bench()

    # --- the rate itself ----------------------------------------------
    def _misses(self, rates=(144, 165)) -> list:
        """Every measure at `rates` outside its bound of the 62 Hz value."""
        bench, out = self.bench, []
        ref = bench.crowd_trial(62, 1.0)
        for hz in rates:
            s = bench.crowd_trial(hz, 1.0)
            for f in B.FRACTIONS:
                share = B.time_to(s, f) / B.time_to(ref, f)
                if not CROWD_BOUND[0] <= share <= CROWD_BOUND[1]:
                    out.append(f"crowd t{int(f * 100)} at {hz} Hz: {share:.0%}")
        for kind in ("equal", "lopsided"):
            rs, rpeak = bench.pair_trial(kind, 62, 1.0)
            for hz in rates:
                s, peak = bench.pair_trial(kind, hz, 1.0)
                for what, share in (("distance", s[-1][1] / rs[-1][1]),
                                    ("peak knock", peak / rpeak)):
                    if not PAIR_BOUND[0] <= share <= PAIR_BOUND[1]:
                        out.append(f"{kind} {what} at {hz} Hz: {share:.0%}")
        return out

    def test_a_fast_display_separates_as_62_fps_does(self):
        self.assertEqual(self._misses(), [])

    def test_the_pass_before_the_fix_fails_the_same_bounds(self):
        # The test above has teeth: the old pass shoved a pair a third
        # further at 144 Hz and halved a crowd's overlap in 61 % of the time.
        with B.unscaled():
            misses = self._misses()
        self.assertGreaterEqual(len(misses), 8, misses)

    def test_at_62_fps_and_below_the_crowd_moves_exactly_as_before(self):
        # End to end through the real `Enemy.update`: the factor is 1.0 on
        # the loop's 16 ms frame and every slower one (ENT-019.D5). Both
        # sides share the new `_bump`; the shove itself is pinned against
        # the old one by `test_bump_exact.py`.
        bench = self.bench
        for hz in (62.5, 62, 60, 30):
            with self.subTest(hz=hz):
                now = bench.crowd_trial(hz, 0.5)
                with B.unscaled():
                    before = bench.crowd_trial(hz, 0.5)
                self.assertEqual(now, before)

    # --- the bench -------------------------------------------------------
    def test_the_crowd_is_packed_and_overlapping(self):
        bench = self.bench
        self.assertEqual(len(bench.crowd), B.LIVE)
        s = bench.crowd_trial(62, 0.0)
        self.assertEqual(len(s), 1)
        self.assertGreater(s[0][1], 1000.0, "the packed crowd barely overlaps")

    def test_a_trial_is_a_pure_function_of_its_start(self):
        # Every rate is compared from one start, so a trial must leave
        # nothing behind that changes the next one.
        bench = self.bench
        first = bench.crowd_trial(62, 0.4)
        bench.crowd_trial(30, 0.4)
        bench.pair_trial("lopsided", 144, 0.3)
        self.assertEqual(bench.crowd_trial(62, 0.4), first)

    def test_the_crowd_separates(self):
        s = self.bench.crowd_trial(62, 1.0)
        self.assertLess(s[-1][1], 0.1 * s[0][1], s[-1])

    def test_each_pair_starts_its_depth_inside_its_push_radius(self):
        frac = config.CROWD_PUSH_RADIUS_FRAC
        for kind in ("equal", "lopsided"):
            a, b = self.bench.pair(kind)
            with self.subTest(kind=kind):
                s, _peak = self.bench.pair_trial(kind, 62, 0.0)
                self.assertAlmostEqual(s[0][1], frac * (a.radius + b.radius) - B.PAIR_DEPTH)

    def test_the_pairs_are_what_they_say(self):
        a, b = self.bench.pair("equal")
        self.assertEqual((a.enemy_id, a.weight), (b.enemy_id, b.weight))
        heavy, light = self.bench.pair("lopsided")
        weights = [e.weight for e in self.bench.crowd]
        self.assertEqual((heavy.weight, light.weight), (max(weights), min(weights)))
        self.assertGreater(heavy.weight, 4 * light.weight)

    def test_a_pair_trial_puts_the_field_back(self):
        bench = self.bench
        before = list(bench.ps.run.enemies)
        bench.pair_trial("equal", 62, 0.2)
        self.assertEqual(bench.ps.run.enemies, before)
        self.assertEqual([tuple(e.pos) for e in bench.crowd],
                         [tuple(p) for p in bench.start])

    def test_the_journal_tables_read_against_the_62_hz_row(self):
        text = B.markdown(self.bench, (30, 62), 0.3)
        rows = [l for l in text.splitlines() if l.startswith("| 62 Hz")]
        self.assertEqual(len(rows), 2, text)               # the crowd, the pairs
        self.assertEqual(rows[0].count("(100 %)"), len(B.FRACTIONS), text)
        self.assertEqual(rows[1].count("(100 %)"), 4, text)
        self.assertEqual(sum(1 for l in text.splitlines() if l.startswith("| 30 Hz")), 2)

    def test_the_pairs_separate_past_their_push_radius(self):
        frac = config.CROWD_PUSH_RADIUS_FRAC
        for kind in ("equal", "lopsided"):
            a, b = self.bench.pair(kind)
            with self.subTest(kind=kind):
                s, peak = self.bench.pair_trial(kind, 62, 1.0)
                self.assertGreater(s[-1][1], frac * (a.radius + b.radius))
                self.assertGreater(peak, 0.0)


if __name__ == "__main__":
    unittest.main()
