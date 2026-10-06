"""RND-010.3: the results' figures come out of the raw sittings
(`documentation/journals/data/rnd-010.3/derived.py`, `crowd_draw_journal.md`).

What is pinned: the script runs on the committed outputs, and prints the
figures the journal's results lean on, so a raw file edited or a parser
gone wrong shows here rather than in a stale journal; and every output
file in the folder is one the README accounts for.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "documentation" / "journals" / "data" / "rnd-010.3"


class DerivedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run = subprocess.run([sys.executable, str(DATA / "derived.py")], capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=120, check=False)
        cls.code, cls.out, cls.err = run.returncode, run.stdout, run.stderr

    def test_it_runs(self):
        self.assertEqual(self.code, 0, self.err)

    def test_the_figures_the_results_lean_on(self):
        for figure in (
            "bare     quiet   9.02 /   8.86  fight  12.13 /  12.07  added  +3.16 (from +3.05 to +3.27)",
            "bare     quiet  10.69 /  10.58  fight  17.51 /  17.45  added  +6.85 (from +6.76 to +6.93)",
            "flat/elemental         quiet  0.11 /  0.11  fight  2.81 /  2.82  added +2.71",
            "enemies                quiet  2.97 /  2.94  fight  5.07 /  5.07  added +2.12",
            "mean diff median -1.27, interval -1.56 to -0.74 -> faster; p90 19.61 -> 18.08; p99 28.87 -> 23.31",
            "emptied 26 times in 600 frames (about every 23)",
            "predicted 1.85 ms a frame (the emptying 0.003 of it), its worst frame 11.52 ms",
            "LRU  1536: 0.31 a frame, worst 3, held at most 80.6 MB; predicts 1.83 ms a frame saved",
            "LRU  1024: 2.07 a frame, worst 11, held at most 55.5 MB; predicts 1.68 ms a frame saved",
            "n=200 sprite only        p50 1.86 ms, less the fill 0.37: 7.45 us a sprite",
            "the lambda and the forwarder alone: 0.03 ms",
        ):
            with self.subTest(figure=figure):
                self.assertIn(figure, self.out)

    def test_a_row_a_run_did_not_print_is_named(self):
        self.assertIn("no row in quiet a (never called there, counted 0): death_fx, death_fx/shade", self.out)


class ReadmeTests(unittest.TestCase):
    def test_every_output_file_is_accounted_for(self):
        readme = (DATA / "README.md").read_text(encoding="utf-8")
        named = set(re.findall(r"`(r\d_[a-z_]+?(?:_\d+[ab]?)?\.txt)`", readme))
        globs = re.findall(r"`(r\d)_\*`|`(r\d_[a-z]+)_\*`", readme)
        prefixes = {a or b for a, b in globs}
        for f in sorted(DATA.glob("r*.txt")):
            with self.subTest(file=f.name):
                self.assertTrue(f.name in named                       # by name in the table
                                or any(f.name.startswith(p + "_") for p in prefixes)   # by `rN_*`
                                or re.fullmatch(r"r\d_meta\.txt", f.name),          # `rN_meta.txt`
                                f"{f.name} is not in the README's table")


if __name__ == "__main__":
    unittest.main()
