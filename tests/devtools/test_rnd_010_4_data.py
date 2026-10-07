"""RND-010.4: the results' figures come out of the before/after sitting
(`documentation/journals/data/rnd-010.4/derived.py`, `crowd_draw_journal.md`).

What is pinned: `derived.py` runs on the committed outputs and prints the
figures in `FIGURES`; the journal's RND-010.4 results carry the quoted
text beside each, and the plan's row 4.13 the ones in `PLAN_FIGURES`; the
folder holds exactly the sitting's files.
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "documentation" / "journals" / "data" / "rnd-010.4"
JOURNAL = ROOT / "documentation" / "journals" / "crowd_draw_journal.md"
PLAN = ROOT / "documentation" / "plans" / "crowd_performance_plan.md"

# (what derived.py prints, what the journal's results say), the journal's
# side matched with its whitespace collapsed and its minus signs as "-".
FIGURES = (
    ("bare      before  17.93 /  18.27  after  16.16 /  16.24  change  -1.90 (-2.11 to -1.69)",
     "| 250: bare draw | 17.93 / 18.27 | 16.16 / 16.24 | -1.90 (-2.11 to -1.69) |"),
    ("layer enemies              before   5.31 /   5.40  after   3.72 /   3.72  change  -1.64 (-1.68 to -1.59)",
     "| 250: `enemies` row | 5.31 / 5.40 | 3.72 / 3.72 | -1.64 (-1.68 to -1.59) |"),
    ("frame     before  30.30 /  30.64  after  28.66 /  28.73  change  -1.77 (-1.98 to -1.57)",
     "| 250: update + draw | 30.30 / 30.64 | 28.66 / 28.73 | -1.77 (-1.98 to -1.57) |"),
    ("draw p90  before  22.07 /  23.65  after  18.89 /  18.43  change  -4.20 (-5.22 to -3.18)",
     "| 250: draw p90 | 22.07 / 23.65 | 18.89 / 18.43 | -4.20 (-5.22 to -3.18) |"),
    ("draw p99  before  32.36 /  33.14  after  29.95 /  30.17  change  -2.69 (-3.19 to -2.19)",
     "| 250: draw p99 | 32.36 / 33.14 | 29.95 / 30.17 | -2.69 (-3.19 to -2.19) |"),
    ("bare      before  16.23 /  15.89  after  15.42 /  14.99  change  -0.86 (-1.24 to -0.47)",
     "| 200: bare draw | 16.23 / 15.89 | 15.42 / 14.99 | -0.86 (-1.24 to -0.47) |"),
    ("layer enemies              before   3.99 /   3.83  after   3.14 /   3.07  change  -0.81 (-0.92 to -0.69)",
     "| 200: `enemies` row | 3.99 / 3.83 | 3.14 / 3.07 | -0.81 (-0.92 to -0.69) |"),
    ("bare      before  14.43 /  15.09  after  14.55 /  15.85  change  +0.44 (-0.54 to +1.42)",
     "| 150: bare draw | 14.43 / 15.09 | 14.55 / 15.85 | +0.44 (-0.54 to +1.42): not resolved |"),
    ("update    before   8.72 /   8.74  after   8.90 /   9.43  change  +0.43 (+0.16 to +0.71)",
     "The update rose there too (+0.16 to +0.71 ms)"),
    ("the game's cap 1536", "now prints the game's cap as 1536"),
)
PLAN_FIGURES = (
    ("change  -1.90 (-2.11 to -1.69)", "bare draw -1.90 ms, the `enemies` row -1.64 ms, draw p90 -4.20 ms"),
)
FILES = {"README.md", "derived.py", "sitting1.sh", "s1_meta.txt", "s1_caches_250_after.txt"} | {
    f"s1_{kind}_{n}_{side}_{r}.txt" for kind in ("fight", "quiet") for n in (150, 200, 250)
    for side in ("before", "after") for r in "ab"}


def _flat(text: str) -> str:
    return " ".join(text.replace("−", "-").split())


class DerivedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run = subprocess.run([sys.executable, str(DATA / "derived.py")], capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=120, check=False)
        cls.code, cls.out, cls.err = run.returncode, run.stdout, run.stderr
        results = JOURNAL.read_text(encoding="utf-8").split("## RND-010.4: Results", 1)[1]
        cls.journal = _flat(results.split("\n## ", 1)[0])
        cls.plan = _flat(PLAN.read_text(encoding="utf-8"))

    def test_it_runs(self):
        self.assertEqual(self.code, 0, self.err)

    def test_the_journal_quotes_what_it_prints(self):
        for printed, quoted in FIGURES:
            with self.subTest(figure=quoted):
                self.assertIn(printed, self.out)
                self.assertIn(quoted, self.journal)

    def test_the_plan_quotes_it_too(self):
        for printed, quoted in PLAN_FIGURES:
            with self.subTest(figure=quoted):
                self.assertIn(printed, self.out)
                self.assertIn(quoted, self.plan)


class FolderTests(unittest.TestCase):
    def test_the_folder_holds_exactly_the_sitting(self):
        self.assertEqual({p.name for p in DATA.iterdir() if p.is_file()}, FILES)


if __name__ == "__main__":
    unittest.main()
