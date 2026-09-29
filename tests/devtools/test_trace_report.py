"""SYS-010.3: the frame-trace report's arithmetic (`frame_trace_journal.md`).

A synthetic trace, written through the real recorder, built so every figure
the report prints is known in advance: which frames are in play, which are
over the budget and why, the long ones, the crowd buckets, the worst
seconds, and the frame just after a state change whose period carries a
load and is left out of the period figures.
"""
import contextlib
import io
import os
import tempfile
import time
import unittest
from pathlib import Path

from systems import frame_trace as FT
from tools.benchmarks import trace_report as R

B = FT.BUDGET_MS


def _write(rows):
    path = Path(tempfile.mkdtemp()) / "traces" / "frames-test.csv"
    tr = FT.FrameTrace(path)
    for frame, update, draw, present, sample in rows:
        tr.record(frame, update, draw, present, sample)
    tr.close()
    return path


def _play(live, run_time):
    return ("PlayingState", live, live // 2, 10, 3, run_time)


MENU = ("MenuState", None, None, None, None, None)
PAUSE = ("PausedState", 30, 15, 10, 3, 5.5)

ROWS = [
    (16.7, 0.5, 3.0, 13.0, MENU),
    (16.7, 0.5, 3.0, 13.0, MENU),
    (3000.0, 4.0, 6.0, 6.0, _play(10, 0.0)),        # the first frame of the run: carries the load
    (16.7, 4.0, 6.0, 6.0, _play(10, 0.1)),          # 10 ms of work
    (16.7, 5.0, 7.0, 4.0, _play(30, 1.2)),          # 12
    (33.3, 12.0, 6.0, 15.0, _play(60, 1.4)),        # 18: over, update-bound, long
    (33.3, 5.0, 13.0, 15.0, _play(120, 1.6)),       # 18: over, draw-bound, long
    (16.7, 6.0, 8.0, 2.0, _play(160, 2.1)),         # 14
    (33.3, 9.0, 9.0, 15.0, _play(160, 2.3)),        # 18: over, a tie counts update-bound, long
    (16.7, 0.1, 5.0, 11.0, PAUSE),                  # paused: not in play
]


class SummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = _write(ROWS)
        cls.rows = R.load(cls.path)
        cls.s = R.summarise(cls.rows)

    def test_the_rows_round_trip(self):
        self.assertEqual(len(self.rows), len(ROWS))
        self.assertIsNone(self.rows[0]["live"])
        self.assertEqual(self.rows[5]["update_ms"], 12.0)

    def test_in_play_and_the_other_states(self):
        s = self.s
        self.assertEqual(s["play"], 7)
        self.assertEqual(s["states"], {"PlayingState": 7, "MenuState": 2, "PausedState": 1})
        self.assertEqual(s["transitions"], 1)

    def test_over_budget_and_why(self):
        s = self.s
        self.assertEqual(s["over"], 3)
        self.assertEqual((s["update_bound"], s["draw_bound"]), (2, 1))

    def test_long_frames_leave_the_transition_out(self):
        self.assertEqual(self.s["long"], 3)
        self.assertEqual(self.s["spread"]["frame_ms"][3], 33.3)      # not the load's 3000

    def test_the_spreads(self):
        # Work in play: 10, 10, 12, 18, 18, 14, 18 -> sorted 10 10 12 14 18 18 18.
        self.assertEqual(self.s["work"], (14.0, 18.0, 18.0, 18.0))
        self.assertEqual(self.s["spread"]["update_ms"][3], 12.0)

    def test_the_crowd_buckets(self):
        got = {(c["lo"], c["hi"]): (c["frames"], c["over"]) for c in self.s["crowds"]}
        self.assertEqual(got, {(0, 24): (2, 0), (25, 49): (1, 0), (50, 99): (1, 1),
                               (100, 149): (1, 1), (150, None): (2, 1)})

    def test_the_worst_seconds(self):
        worst = [(sec, v["over"], v["worst"], v["live"]) for sec, v in self.s["worst_seconds"]]
        self.assertEqual(worst, [(1, 2, 18.0, 120), (2, 1, 18.0, 160)])

    def test_the_budget_is_the_one_constant(self):
        from tools.benchmarks import spawn_stress
        self.assertIs(R.BUDGET_MS, FT.BUDGET_MS)
        self.assertIs(spawn_stress.BUDGET_MS, FT.BUDGET_MS)

    def test_the_printout_carries_the_answer(self):
        text = R.format(self.s)
        self.assertIn("in play (PlayingState): 7 frames", text)
        self.assertIn("work (update + draw) over budget: 3 (42.9 %)", text)
        self.assertIn("long frames (period over 1.5 x budget, a missed refresh): 3 (50.0 %", text)
        self.assertIn("update-bound 2, draw-bound 1", text)


class CommandLineTests(unittest.TestCase):
    def test_a_named_trace_is_reported(self):
        path = _write(ROWS)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(R.main([str(path)]), 0)
        self.assertIn("in play (PlayingState): 7 frames", out.getvalue())

    def test_the_newest_trace_beside_the_save(self):
        d = Path(tempfile.mkdtemp())
        folder = d / "traces"
        folder.mkdir()
        old, new = folder / "frames-a.csv", folder / "frames-b.csv"
        old.write_text("x")
        new.write_text("x")
        os.utime(old, (time.time() - 100, time.time() - 100))
        self.assertEqual(R.newest(d / "save.json"), new)
        self.assertIsNone(R.newest(Path(tempfile.mkdtemp()) / "save.json"))

    def test_a_trace_with_no_play_says_so(self):
        text = R.format(R.summarise(R.load(_write([(16.7, 0.5, 3.0, 13.0, MENU)] * 3))))
        self.assertIn("no frames in play", text)


if __name__ == "__main__":
    unittest.main()
