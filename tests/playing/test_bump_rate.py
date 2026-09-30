"""ENT-019: the crowd bump at any frame rate (`journals/bump_frame_rate_journal.md`).

The bench, `tools/benchmarks/bump_rate.py`, steps one packed crowd and two
hand-built pairs for the same game time at several frame rates. These tests
hold the bench itself to what its tables rely on: a trial is a pure function
of its start, the crowd and the pairs start where they are said to, and the
series readers interpolate between frames correctly.
"""
import unittest

from game import config
from tools.benchmarks import bump_rate as B


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

    def test_a_rate_or_a_duration_of_zero_is_refused(self):
        for argv in (["--rates", "0"], ["--seconds", "0"], ["--rates", "30", "-62"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit):
                B.parse(argv)


class BenchTests(unittest.TestCase):
    """One booted run (seed 35), shared by every test here."""

    @classmethod
    def setUpClass(cls):
        cls.bench = B.Bench()

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
