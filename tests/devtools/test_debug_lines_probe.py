"""RND-010.5: the probe that times the F1 overlay's lines
(`tools/benchmarks/debug_lines.py`, `crowd_draw_journal.md`).

Pinned: the timing loop calls exactly what it says, `--rounds` times; the
printout's every figure; the command line; and an end-to-end run on a
small packed scene.
"""
import contextlib
import io
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.devtools import (
    test_draw_layers as TDL,  # an alias: its classes are not collected twice
)
from tools.benchmarks import debug_lines as DLn

SEED = 35
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "documentation" / "journals" / "data" / "rnd-010.5"
JOURNAL = ROOT / "documentation" / "journals" / "crowd_draw_journal.md"
PLAN = ROOT / "documentation" / "plans" / "crowd_performance_plan.md"
SCENES = {"live_150_elapsed_200": "150 packed, quiet",
          "live_150_elapsed_200_elements": "150 packed, infused",
          "live_250_elapsed_600": "250 packed, quiet",
          "live_250_elapsed_600_elements": "250 packed, infused"}
ESTIMATE = (0.2, 0.5)            # the plan's 4.1, ms a frame
SITTING_5_FIGHT_250 = 29.30      # RND-010.3 sitting 5, update and draw, ms (its lower end)
LINE = re.compile(r"  report_debug: ([\d.]+) us a call \(p90 ([\d.]+)\), ([\d.]+) ms a frame; "
                  r"of it active_auras ([\d.]+) us; (\d+) alive, (\d+) calls")


class MeasureTests(unittest.TestCase):
    def test_it_times_report_debug_and_active_auras_rounds_times_each(self):
        calls = {"report": 0, "auras": 0}
        run = SimpleNamespace(enemies=[1, 2, 3], stats={"time": 4.0})
        run.elements = SimpleNamespace(
            active_auras=lambda enemies, now: calls.__setitem__("auras", calls["auras"] + 1) or 0)
        ps = SimpleNamespace(run=run)
        ps.dev = SimpleNamespace(report_debug=lambda p: calls.__setitem__("report", calls["report"] + 1))
        result = DLn.measure(ps, rounds=5)
        self.assertEqual(calls, {"report": 5, "auras": 5})
        self.assertEqual((len(result["whole"]), len(result["auras"]), result["alive"]), (5, 5, 3))
        self.assertTrue(all(us >= 0.0 for us in result["whole"] + result["auras"]))


class ReportTests(unittest.TestCase):
    def test_it_uses_the_shared_percentile(self):
        # An even count tells it from statistics.median: [1, 2, 3, 4] has
        # p50 3 by stats.percentile, 2.5 by the median.
        result = {"whole": [4.0, 1.0, 3.0, 2.0], "auras": [1.0, 2.0, 3.0, 4.0], "alive": 1}
        self.assertIn("report_debug: 3.0 us a call (p90 4.0), 0.003 ms a frame; of it active_auras 3.0 us",
                      DLn.report(result))

    def test_every_figure(self):
        result = {"whole": [10.0, 30.0, 20.0, 40.0, 50.0], "auras": [7.0, 9.0, 8.0, 6.0, 5.0], "alive": 136}
        # stats.percentile on the sorted lists: p50 index round(0.5 * 4) = 2
        # -> 30, p90 index round(0.9 * 4) = 4 -> 50; 0.030 ms a frame; auras
        # p50 7.
        self.assertEqual(DLn.report(result),
                         "  report_debug: 30.0 us a call (p90 50.0), 0.030 ms a frame; of it "
                         "active_auras 7.0 us; 136 alive, 5 calls")

    def test_the_command_line(self):
        a = DLn.parse(["--live", "150", "--elapsed", "300"])
        self.assertEqual((a.seed, a.dormant, a.elements, a.rounds), (SEED, 400, False, 2000))
        self.assertTrue(DLn.parse(["--live", "1", "--elapsed", "0", "--elements"]).elements)
        for bad in (["--live", "1", "--elapsed", "0", "--rounds", "0"], ["--elapsed", "0"]):
            with self.subTest(argv=bad), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit):
                DLn.parse(bad)


def _rows() -> dict:
    """Each kept output's figures, by file stem: p50, p90, ms, auras, alive."""
    out = {}
    for stem in SCENES:
        med, p90, ms, auras, alive, _ = LINE.search((DATA / f"{stem}.txt").read_text(encoding="utf-8")).groups()
        out[stem] = {"p50": float(med), "p90": float(p90), "ms": ms, "auras": float(auras), "alive": alive}
    return out


class JournalTests(unittest.TestCase):
    """The RND-010.5 results, and every figure the journal and the plan
    quote from them, are the kept outputs."""

    def test_every_quoted_figure_is_derived_from_the_files(self):
        rows = _rows()
        ms = sorted(float(r["ms"]) for r in rows.values())
        lo, hi = f"{ms[0]:.3f}", f"{ms[-1]:.3f}"
        rest = sorted(r["p50"] - r["auras"] for r in rows.values())
        q150, i250 = rows["live_150_elapsed_200"], rows["live_250_elapsed_600_elements"]
        self.assertEqual((lo, hi), (q150["ms"], i250["ms"]), "the range runs 150 quiet to 250 infused")
        share = (f"{round(100 * ms[0] / ESTIMATE[1])} to {round(100 * ms[-1] / ESTIMATE[0])} %")
        journal = JOURNAL.read_text(encoding="utf-8")
        plan = PLAN.read_text(encoding="utf-8")
        for text in (f"{lo} to {hi} ms a frame, {share} of the plan's estimate",
                     f"{lo} to {hi} ms a frame, the whole of",
                     f"the measured cost is {share} of that",
                     (f"({q150['auras']:.1f} of {q150['p50']:.1f} µs at 150 quiet, "
                      f"{i250['auras']:.1f} of {i250['p50']:.1f} µs at 250\n  infused)"),
                     f"f-strings are the remaining {rest[0]:.1f} to {rest[-1]:.1f} µs",
                     f"so {hi} ms is {100 * ms[-1] / SITTING_5_FIGHT_250:.2f} %"):
            with self.subTest(journal=text):
                self.assertIn(text, journal)
        for text in (f"**Measured** in RND-010.5: {lo} to {hi} ms a\n  frame at 150 to 250 packed",
                     f"{lo} ms at 150 packed quiet to {hi} ms at 250 infused",
                     f"4.1 is {lo} to {hi} ms"):
            with self.subTest(plan=text):
                self.assertIn(text, plan)

    def test_every_row_is_its_file(self):
        journal = JOURNAL.read_text(encoding="utf-8")
        results = journal.split("## RND-010.5: Results", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(sorted(p.stem for p in DATA.glob("*.txt")), sorted(SCENES))
        for stem, scene in SCENES.items():
            text = (DATA / f"{stem}.txt").read_text(encoding="utf-8")
            with self.subTest(file=stem):
                flags = stem.replace("_", " ").replace("live", "--live").replace("elapsed", "--elapsed")
                self.assertEqual(text.splitlines()[0],
                                 "python -m tools.benchmarks.debug_lines --seed 35 "
                                 + flags.replace("elements", "--elements"))
                med, p90, ms, auras, alive, calls = LINE.search(text).groups()
                self.assertEqual(calls, "2000")
                self.assertIn(f"| {scene} | {alive} | {med} µs (p90 {p90}) | {ms} ms | {auras} µs |",
                              results)


class MainTests(unittest.TestCase):
    def test_end_to_end(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = DLn.main(["--seed", str(SEED), "--live", "30", "--elapsed", "300", "--dormant", "0",
                             "--rounds", "3"], save_path=TDL._fresh_save())
        self.assertEqual(code, 0)
        self.assertRegex(out.getvalue(), r"  report_debug: [\d.]+ us a call .* alive, 3 calls")

    def test_elements_asks_for_the_fight(self):
        asked = []

        def packed(*a, elements=False):
            asked.append(elements)
            raise RuntimeError("built")

        for argv, want in ((["--elements"], True), ([], False)):
            with self.subTest(argv=argv), mock.patch.object(DLn.LP, "packed_scene", packed), \
                    self.assertRaisesRegex(RuntimeError, "built"):
                DLn.main(["--live", "30", "--elapsed", "300", *argv])
        self.assertEqual(asked, [True, False])


if __name__ == "__main__":
    unittest.main()
