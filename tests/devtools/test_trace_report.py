"""SYS-010.3/.4: the frame-trace report's arithmetic (`frame_trace_journal.md`).

A synthetic trace, written as CSV row by row, built so every figure the
report prints is known in advance: which frames are in play (their update
was `PlayingState`'s), which are over the budget and why, the long ones and
what took most of each, the crowd buckets, and the worst seconds of each
run. A trace written by the real recorder reads back whole; rows that cannot
be read are skipped and counted; a file from an older recorder is refused
by name; the command with no argument finds the newest trace beside either
save.
"""
import contextlib
import csv
import io
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from systems import frame_trace as FT
from tools.benchmarks import trace_report as R

B = FT.BUDGET_MS


def _dir(case) -> Path:
    d = tempfile.mkdtemp()
    case.addCleanup(shutil.rmtree, d, True)
    return Path(d)


def _write(folder: Path, rows, name="frames-test.csv") -> Path:
    """`rows` of `(frame_ms, update, draw, present, wait, sample)` as a trace
    file, each row's `t` the sum of the periods before it. A sample of six
    is shown as its own state; one of seven names what it showed; one of
    eight says too whether the frame opened it."""
    path = folder / "traces" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    t = 0.0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(FT.COLUMNS)
        for frame, update, draw, present, wait, sample in rows:
            if len(sample) == 6:                            # shown as its own state
                sample = sample[:1] + sample
            if len(sample) == 7:                            # not opened this frame
                sample = sample[:2] + (0,) + sample[2:]
            state, shown, opened, live, view, parts, nums, clock = sample
            blank = lambda v: "" if v is None else v
            w.writerow([f"{t:.4f}", frame, update, draw, present, wait, state, shown, opened,
                        blank(live), blank(view), blank(parts), blank(nums), blank(clock)])
            t += frame / 1000.0
    return path


def _play(live, run_time):
    return ("PlayingState", live, live // 2, 10, 3, run_time)


def _run(case, rows):
    return R.summarise(R.load(_write(_dir(case), rows))[0])


MENU = ("MenuState", None, None, None, None, None)
LOAD = ("LoadingState", "PlayingState", 1, 10, 5, 10, 3, 0.0)   # finished the load: shows the run
PAUSE = ("PausedState", 30, 15, 10, 3, 5.5)

ROWS = [
    (16.7, 0.5, 3.0, 13.0, 0.1, MENU),
    (16.7, 0.5, 3.0, 13.0, 0.1, MENU),
    (3000.0, 40.0, 6.0, 6.0, 0.1, LOAD),            # the loading screen's last update: not play
    (16.7, 4.0, 6.0, 6.0, 0.6, _play(24, 0.1)),     # 10 ms of work; the first bucket's top edge
    (16.7, 5.0, 7.0, 4.0, 0.6, _play(25, 1.2)),     # 12; the second bucket's bottom edge
    (33.3, 12.0, 6.0, 11.0, 0.2, _play(60, 1.4)),   # 18: over, update-bound; long, the update most
    (33.3, 5.0, 13.0, 10.0, 0.2, _play(120, 1.6)),  # 18: over, draw-bound; long, the draw most
    (16.7, 6.0, 8.0, 2.0, 0.6, _play(160, 2.1)),    # 14
    (33.3, 9.0, 9.0, 15.0, 0.2, _play(160, 2.3)),   # 18: over, a tie counts update-bound; long, the present
    (16.7, 0.1, 5.0, 11.0, 0.5, PAUSE),             # paused: not in play
    (16.7, 0.1, 5.0, 11.0, 0.5, PAUSE),
]


class SummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.rows, cls.skipped = R.load(_write(Path(cls.tmp), ROWS))
        cls.s = R.summarise(cls.rows)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def test_the_rows_round_trip(self):
        self.assertEqual((len(self.rows), self.skipped), (len(ROWS), 0))
        self.assertIsNone(self.rows[0]["live"])
        self.assertEqual(self.rows[5]["update_ms"], 12.0)
        self.assertEqual(self.rows[3]["t"], 3.0334)
        self.assertAlmostEqual(self.rows[5]["other_ms"], 4.1)       # 33.3 - 12 - 6 - 11 - 0.2

    def test_in_play_is_the_rows_whose_update_was_play(self):
        s = self.s
        self.assertEqual(s["play"], 6)
        self.assertEqual(s["states"], {"PlayingState": 6, "MenuState": 2, "PausedState": 2,
                                       "LoadingState": 1})

    def test_over_budget_and_why(self):
        s = self.s
        self.assertEqual(s["over"], 3)                                 # not the load's 46
        self.assertEqual((s["update_bound"], s["draw_bound"]), (2, 1))
        self.assertEqual(s["over_all"], 4)                             # every frame: it counts there

    def test_long_frames_and_what_took_most_of_each(self):
        s = self.s
        self.assertEqual((s["long"], s["long_over"]), (3, 3))
        self.assertEqual(s["causes"], {"update_ms": 1, "draw_ms": 1, "present_ms": 1})

    def test_the_loading_frame_is_in_no_play_figure(self):
        self.assertEqual(self.s["spread"]["frame_ms"][3], 33.3)        # not the load's 3000
        self.assertEqual(self.s["spread"]["update_ms"][3], 12.0)       # not the load's 40

    def test_the_spreads(self):
        # Work in play: 10, 12, 18, 18, 14, 18 -> sorted 10 12 14 18 18 18.
        self.assertEqual(self.s["work"], (14.0, 18.0, 18.0, 18.0))
        self.assertEqual(self.s["spread"]["wait_ms"], (0.2, 0.6, 0.6, 0.6))   # .2 .2 .2 .6 .6 .6
        self.assertAlmostEqual(self.s["spread"]["other_ms"][3], 5.1)

    def test_the_crowd_buckets(self):
        got = {(c["lo"], c["hi"]): (c["frames"], c["over"], c["in_view"], c["particles"])
               for c in self.s["crowds"]}
        self.assertEqual(got, {(0, 24): (1, 0, 12, 10), (25, 49): (1, 0, 12, 10),
                               (50, 99): (1, 1, 30, 10), (100, 149): (1, 1, 60, 10),
                               (150, None): (2, 1, 80, 10)})

    def test_the_worst_seconds(self):
        worst = [(key, v["over"], v["worst"], v["live"]) for key, v in self.s["worst_seconds"]]
        self.assertEqual(worst, [((1, 1), 2, 18.0, 120), ((1, 2), 1, 18.0, 160)])
        self.assertEqual(self.s["runs"], 1)

    def test_the_budget_is_the_one_constant(self):
        from tools.benchmarks import spawn_stress
        self.assertIs(R.BUDGET_MS, FT.BUDGET_MS)
        self.assertIs(spawn_stress.BUDGET_MS, FT.BUDGET_MS)

    def test_the_printout_carries_the_answer(self):
        text = R.format(self.s)
        self.assertIn("every frame: work over budget 4 (36.4 %)", text)
        self.assertIn("in play (PlayingState): 6 frames\n", text)
        self.assertIn("work (update + draw) over budget: 3 (50.0 %); update-bound 2, draw-bound 1", text)
        self.assertIn("long frames (period over 1.5 x budget): 3 (50.0 %); "
                      "3 with work over budget", text)
        self.assertIn("what took most of each: update 1, draw 1, present 1, wait 0, other 0", text)
        self.assertIn("    wait     0.20 / 0.60 / 0.60 / 0.60", text)
        self.assertIn("    150+           2  14.00 / 18.00  1 (50.0 %)  80  10", text)
        self.assertIn("worst seconds (1 run(s), run clock)", text)
        self.assertIn("run 1     1 s     2   18.00 ms   120", text)


class OpenedOverlayTests(unittest.TestCase):
    def test_a_play_frame_that_opened_an_overlay_is_counted_apart(self):
        # The frame that opens the level-up cards draws their first frame
        # (22 ms); the end banner's wait phase updates the run, and only its
        # first frame, which opened it, is counted apart.
        lvl = ("PlayingState", "LevelUpState", 1, 20, 10, 10, 3, 1.3)
        banner = ("PlayingState", "EndBannerState", 1, 20, 10, 10, 3, 1.4)
        waiting = ("PlayingState", "EndBannerState", 0, 20, 10, 10, 3, 1.4)
        s = _run(self, [
            (16.7, 4.0, 6.0, 1.0, 5.0, _play(20, 1.1)),
            (40.0, 7.0, 30.0, 1.0, 0.2, lvl),               # opened the cards: over budget
            (16.7, 0.1, 5.0, 1.0, 9.0, ("LevelUpState", 20, 10, 10, 3, 1.3)),
            (16.7, 4.0, 6.0, 1.0, 5.0, _play(20, 1.3)),     # picked: play again
            (30.0, 5.0, 20.0, 1.0, 0.2, banner),            # opened the banner: over budget
            (16.7, 4.0, 6.0, 1.0, 5.0, waiting),            # the wait phase: play
            (16.7, 4.0, 6.0, 1.0, 5.0, waiting),
        ])
        self.assertEqual(s["play"], 4)
        self.assertEqual(s["opened"], {"LevelUpState": 1, "EndBannerState": 1})
        self.assertEqual((s["opened_over"], s["over"]), (2, 0))
        self.assertEqual(s["worst_seconds"], [])            # neither is a play second
        text = R.format(s)
        self.assertIn("counted apart: 2 play frame(s) that opened an overlay (LevelUpState 1, "
                      "EndBannerState 1); their draw is the overlay's first; work over budget 2, "
                      "update-bound 0, draw-bound 2", text)

    def test_a_chained_level_up_is_counted_apart_though_the_cards_were_up(self):
        # The pick pops the cards and the same frame's update opens the
        # next: shown as the frame before, yet opened (the recorder
        # compares the states as objects).
        cards = ("LevelUpState", 20, 10, 10, 3, 1.3)
        s = _run(self, [
            (40.0, 7.0, 30.0, 1.0, 0.2, ("PlayingState", "LevelUpState", 1, 20, 10, 10, 3, 1.3)),
            (16.7, 0.1, 5.0, 1.0, 9.0, cards),
            (40.0, 7.0, 30.0, 1.0, 0.2, ("PlayingState", "LevelUpState", 1, 20, 10, 10, 3, 1.3)),
            (16.7, 0.1, 5.0, 1.0, 9.0, cards),
            (16.7, 4.0, 6.0, 1.0, 5.0, _play(20, 1.4)),
        ])
        self.assertEqual((s["play"], s["over"]), (1, 0))
        self.assertEqual((s["opened"], s["opened_over"]), ({"LevelUpState": 2}, 2))

    def test_an_opening_frame_over_budget_by_its_update_says_so(self):
        # A death hitch in the update, not the banner's first draw.
        s = _run(self, [
            (40.0, 30.0, 6.0, 1.0, 0.2, ("PlayingState", "EndBannerState", 1, 20, 10, 10, 3, 1.3)),
        ])
        self.assertIn("work over budget 1, update-bound 1, draw-bound 0", R.format(_run(self, [
            (16.7, 4.0, 6.0, 1.0, 5.0, _play(20, 1.2)),
            (40.0, 30.0, 6.0, 1.0, 0.2, ("PlayingState", "EndBannerState", 1, 20, 10, 10, 3, 1.3)),
        ])))
        self.assertEqual(s["opened_update_bound"], 1)

    def test_a_trace_that_opens_no_overlay_says_nothing_of_it(self):
        self.assertNotIn("opened an overlay", R.format(_run(self, ROWS)))


class CauseTests(unittest.TestCase):
    def test_each_part_can_take_a_long_frame(self):
        s = _run(self, [
            (16.7, 3.0, 4.0, 1.0, 8.6, _play(10, 0.1)),     # not long
            (33.3, 3.0, 4.0, 1.0, 25.2, _play(10, 0.2)),    # the tick's wait
            (33.3, 3.0, 4.0, 24.0, 2.2, _play(10, 0.3)),    # the present
            (33.3, 20.0, 4.0, 1.0, 0.2, _play(10, 0.4)),    # the update; work over budget
            (33.3, 4.0, 20.0, 1.0, 0.2, _play(10, 0.5)),    # the draw; work over budget
            (33.3, 3.0, 3.0, 1.0, 1.0, _play(10, 0.6)),     # the rest of the period: 25.3
            (33.3, 10.0, 10.0, 10.0, 3.3, _play(10, 0.7)),  # a tie: the update; work over budget
        ])
        self.assertEqual((s["long"], s["long_over"]), (6, 3))
        self.assertEqual(s["causes"], {"update_ms": 2, "draw_ms": 1, "present_ms": 1,
                                       "wait_ms": 1, "other_ms": 1})

    def test_long_frames_the_wait_took_are_named_as_the_os_timer(self):
        text = R.format(_run(self, [(33.3, 3.0, 4.0, 1.0, 25.2, _play(10, 0.2))]))
        self.assertIn("the frame cap's sleep overshooting, not the game's work", text)
        text = R.format(_run(self, [(33.3, 20.0, 4.0, 1.0, 0.2, _play(10, 0.2))]))
        self.assertNotIn("overshooting", text)

    def test_no_long_frames_prints_no_causes(self):
        text = R.format(_run(self, [(16.7, 3.0, 4.0, 1.0, 8.6, _play(10, 0.1))]))
        self.assertIn("long frames (period over 1.5 x budget): 0 (0.0 %)", text)
        self.assertNotIn("what took most", text)


class RunTests(unittest.TestCase):
    def test_two_runs_seconds_never_merge(self):
        # Both runs are over budget in their second 1; the loading frame's
        # run clock starting again is what tells them apart.
        s = _run(self, [
            (16.7, 1.0, 1.0, 1.0, 0.0, _play(10, 0.0)),
            (20.0, 10.0, 9.0, 1.0, 0.0, _play(30, 1.2)),    # run 1, second 1: over
            (500.0, 30.0, 5.0, 1.0, 0.0, ("LoadingState", 5, 2, 0, 0, 0.0)),  # run 2 built
            (20.0, 10.0, 9.0, 1.0, 0.0, _play(40, 1.3)),    # run 2, second 1: over
            (20.0, 10.0, 9.0, 1.0, 0.0, _play(50, 1.5)),    # run 2, second 1: over
        ])
        worst = [(key, v["over"], v["live"]) for key, v in s["worst_seconds"]]
        self.assertEqual(worst, [((2, 1), 2, 50), ((1, 1), 1, 30)])
        self.assertEqual(s["runs"], 2)

    def test_the_menus_between_two_runs_part_them(self):
        # The run clock does not go back here; the frames outside any run do.
        s = _run(self, [
            (20.0, 10.0, 9.0, 1.0, 0.0, _play(30, 1.2)),    # run 1, second 1: over
            (16.7, 1.0, 1.0, 1.0, 0.0, MENU),
            (20.0, 10.0, 9.0, 1.0, 0.0, _play(40, 1.4)),    # run 2, second 1: over
        ])
        self.assertEqual([key for key, _v in s["worst_seconds"]], [(1, 1), (2, 1)])
        self.assertEqual(s["runs"], 2)

    def test_a_clock_that_goes_back_starts_a_run(self):
        s = _run(self, [
            (20.0, 10.0, 9.0, 1.0, 0.0, _play(30, 1.2)),    # run 1, second 1: over
            (20.0, 10.0, 9.0, 1.0, 0.0, _play(30, 0.2)),    # run 2, second 0: over
            (20.0, 10.0, 9.0, 1.0, 0.0, _play(30, 1.1)),    # run 2, second 1: over
        ])
        self.assertEqual([key for key, _v in s["worst_seconds"]], [(1, 1), (2, 0), (2, 1)])
        self.assertEqual(s["runs"], 2)

    def test_a_trace_outside_any_run_has_none(self):
        s = _run(self, [(16.7, 1.0, 1.0, 1.0, 0.0, MENU)] * 2)
        self.assertEqual((s["runs"], s["worst_seconds"]), (0, []))


class UnreadableRowTests(unittest.TestCase):
    def test_rows_that_cannot_be_read_are_skipped_and_counted(self):
        path = _write(_dir(self), ROWS[3:5])
        with open(path, "a", newline="", encoding="utf-8") as f:
            P = "PlayingState,PlayingState,0"
            f.write(f"0.1,nan,1,1,1,0,{P},1,1,1,1,1\n")      # not finite
            f.write(f"0.1,16,1,1,1,,{P},1,1,1,1,1\n")        # a blank time
            f.write(f"0.1,16,1,1,1,0,{P},many,1,1,1,1\n")    # a count that is not one
            f.write(f"0.1,16,1,1,1,0,{P},1,1,1,1,inf\n")     # not finite
            f.write(f"0.1,16,1,1,1,0,{P},1,1,1,1,1,9\n")     # a field too many
            f.write(f"0.1,16,1,1,1,0,{P},40\n")              # cut off in the crowd
            f.write("0.2,16,1,1\n")                          # cut off in the times
            f.write(f"0.1,16,1,1,1,0,{P},5,,3,1,1\n")       # a crowd half written
            f.write(f"0.1,16,1,1,1,0,{P},5,2,,1,1\n")       # a crowd half written
            f.write(f"0.1,16,1,1,1,0,{P},,5,3,1,1\n")       # half written, alive blank
            f.write(f"0.1,16,-1,1,1,0,{P},1,1,1,1,1\n")     # a negative time
            f.write(f"0.1,16,1,1,1,0,{P},-5,1,1,1,1\n")     # a negative count
            f.write(f"0.1,\"16,1,1,1,0,{P},1,1,1,1,1\n")    # a stray quote: this row only
            f.write(f"0.1,16,1,1,1,0,{P[:-2]},2,1,1,1,1,1\n")   # opened not 0 or 1
            f.write(f"0.1,2,5,3,1,10,{P},1,1,1,1,1\n")      # parts over the period
            f.write(f"0.1,16,1,1,1,0,{P},10.5,5,1,1,1\n")   # a count that is not whole
            f.write(f"0.1,16,1,1,1,0,{P},5,6,1,1,1\n")      # more in view than alive
            f.write(f"0.3,16.7,4,6,1,0,{P},24,12,10,3,1.5\n")   # read: the quote spoiled nothing more
        rows, skipped = R.load(path)
        self.assertEqual((len(rows), skipped), (3, 17))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(R.main([str(path)]), 0)
        self.assertIn("17 row(s) could not be read and were skipped", out.getvalue())
        self.assertIn("in play (PlayingState): 3 frames", out.getvalue())

    def test_a_trace_with_no_frames_says_so(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(R.main([str(_write(_dir(self), []))]), 0)
        self.assertIn("no readable frames", out.getvalue())

    def test_a_trace_from_an_older_recorder_is_refused_by_name(self):
        path = _dir(self) / "frames-old.csv"
        old = [c for c in FT.COLUMNS if c not in ("wait_ms", "shown", "opened")]
        path.write_text(",".join(old) + "\n" + ",".join("1" for _ in old) + "\n", encoding="utf-8")
        with self.assertRaises(R.NotATrace):
            R.load(path)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            R.main([str(path)])
        self.assertIn("its header has no wait_ms, shown, opened (a trace from an older recorder?)",
                      err.getvalue())

    def test_a_file_that_is_not_utf8_csv_is_refused_by_name(self):
        folder = _dir(self)
        good = _write(folder, ROWS).read_text(encoding="utf-8")
        cases = {
            "latin.csv": good.encode("utf-8") + "0.1,16,1,1,1,0,Caf\u00e9,x\n".encode("latin-1"),
            "utf16.csv": good.encode("utf-16"),
            "big.csv": good.encode("utf-8") + b"0.1," + b"9" * 200_000 + b"\n",
        }
        for name, data in cases.items():
            with self.subTest(file=name):
                path = folder / name
                path.write_bytes(data)
                with self.assertRaises(R.NotATrace):
                    R.load(path)
                err = io.StringIO()
                with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
                    R.main([str(path)])
                self.assertIn("cannot be read as a CSV trace", err.getvalue())

    def test_an_empty_file_is_refused_as_empty(self):
        for text in ("", "\n\n\n", "  \r\n \n"):
            with self.subTest(text=text):
                path = _dir(self) / "frames-empty.csv"
                path.write_text(text, encoding="utf-8", newline="")
                err = io.StringIO()
                with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
                    R.main([str(path)])
                self.assertIn("the file is empty", err.getvalue())

    def test_a_file_whose_first_line_is_blank_is_not_a_trace(self):
        path = _write(_dir(self), ROWS)
        path.write_text("\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
        with self.assertRaisesRegex(R.NotATrace, "its first line is not a header"):
            R.load(path)

    def test_a_header_an_editor_gave_a_bom_still_reads(self):
        path = _write(_dir(self), ROWS)
        path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
        rows, skipped = R.load(path)
        self.assertEqual((len(rows), skipped), (len(ROWS), 0))

    def test_the_recorders_file_reads_back_whole(self):
        # The contract between the writer and the reader: every row the
        # recorder writes, menu blanks included, is one the report reads.
        path = _dir(self) / "traces" / "frames-rec.csv"
        tr = FT.FrameTrace(path)
        now = time.perf_counter()
        for i, sample in enumerate((s[0], s[0], 0) + s[1:] for s in (MENU, _play(12, 0.5), PAUSE)):
            tr.record(now + i * 0.016, 0.5, 1.0, 2.0, 3.0, sample)
        tr.close(now + 0.048)                    # the made-up frames' own clock
        rows, skipped = R.load(path)
        self.assertEqual((len(rows), skipped), (3, 0))
        self.assertEqual([r["state"] for r in rows], ["MenuState", "PlayingState", "PausedState"])
        self.assertEqual([r["shown"] for r in rows], ["MenuState", "PlayingState", "PausedState"])
        self.assertIsNone(rows[0]["run_time"])
        self.assertEqual(rows[1]["live"], 12.0)


class CommandLineTests(unittest.TestCase):
    def _main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = R.main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_a_named_trace_is_reported(self):
        path = _write(_dir(self), ROWS)
        code, out, _ = self._main([str(path)])
        self.assertEqual(code, 0)
        self.assertIn(f"trace: {path}", out)
        self.assertIn("in play (PlayingState): 6 frames", out)

    def test_no_argument_reads_the_newest_beside_either_save(self):
        # The source tree's save and the packaged game's: the newest of both,
        # whichever holds it.
        from game import save
        a, b = _dir(self), _dir(self)
        old = _write(a, ROWS, "frames-a.csv")
        new = _write(b, ROWS, "frames-b.csv")
        os.utime(old, (time.time() - 100, time.time() - 100))
        for first, second in ((a, b), (b, a)):
            with self.subTest(default=first.name), \
                    mock.patch.object(save, "DEFAULT_PATH", first / "save.json"), \
                    mock.patch.object(save, "user_save_path", lambda s=second: s / "save.json"):
                code, out, _ = self._main([])
                self.assertEqual(code, 0)
                self.assertIn(f"trace: {new}", out)

    def test_no_argument_and_no_trace_says_how_to_make_one(self):
        from game import save
        a, b = _dir(self), _dir(self)
        with mock.patch.object(save, "DEFAULT_PATH", a / "save.json"), \
                mock.patch.object(save, "user_save_path", lambda: b / "save.json"):
            code, _, err = self._main([])
        self.assertEqual(code, 2)
        self.assertIn("play with `python main.py --trace`", err)

    def test_a_missing_file_is_named_not_a_traceback(self):
        code, _, err = self._main([str(_dir(self) / "nope.csv")])
        self.assertEqual(code, 2)
        self.assertIn("no such trace:", err)

    def test_newest_picks_across_both_saves(self):
        a, b = _dir(self), _dir(self)
        old = _write(a, [], "frames-a.csv")
        new = _write(b, [], "frames-b.csv")
        os.utime(old, (time.time() - 100, time.time() - 100))
        self.assertEqual(R.newest(a / "save.json", b / "save.json"), new)
        self.assertEqual(R.newest(a / "save.json"), old)
        self.assertIsNone(R.newest(_dir(self) / "save.json"))

    def test_a_trace_with_no_play_says_so(self):
        text = R.format(_run(self, [(16.7, 0.5, 3.0, 13.0, 0.0, MENU)] * 3))
        self.assertIn("no frames in play", text)


if __name__ == "__main__":
    unittest.main()
