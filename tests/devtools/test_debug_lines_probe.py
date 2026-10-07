"""RND-010.5: the probe that times the F1 overlay's lines
(`tools/benchmarks/debug_lines.py`, `crowd_draw_journal.md`).

Pinned: the timing loop calls exactly what it says, `--rounds` times; the
printout's every figure; the command line; and an end-to-end run on a
small packed scene.
"""
import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest import mock

from tests.devtools import (
    test_draw_layers as TDL,  # an alias: its classes are not collected twice
)
from tools.benchmarks import debug_lines as DLn

SEED = 35


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
    def test_every_figure(self):
        result = {"whole": [10.0, 30.0, 20.0, 40.0, 50.0], "auras": [7.0, 9.0, 8.0, 6.0, 5.0], "alive": 136}
        # median 30, p90 index int(0.9 * 4) = 3 of the sorted list -> 40,
        # 0.030 ms a frame, auras median 7.
        self.assertEqual(DLn.report(result),
                         "  report_debug: 30.0 us a call (p90 40.0), 0.030 ms a frame; of it "
                         "active_auras 7.0 us; 136 alive, 5 calls")

    def test_the_command_line(self):
        a = DLn.parse(["--live", "150", "--elapsed", "300"])
        self.assertEqual((a.seed, a.dormant, a.elements, a.rounds), (SEED, 400, False, 2000))
        self.assertTrue(DLn.parse(["--live", "1", "--elapsed", "0", "--elements"]).elements)
        for bad in (["--live", "1", "--elapsed", "0", "--rounds", "0"], ["--elapsed", "0"]):
            with self.subTest(argv=bad), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit):
                DLn.parse(bad)


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
