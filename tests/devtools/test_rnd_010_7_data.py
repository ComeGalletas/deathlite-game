"""RND-010.7: the results' figures come out of the headless sitting and the
walk's shapes (`documentation/journals/data/rnd-010.7/derived.py`,
`crowd_draw_journal.md`).

What is pinned: `derived.py` runs on the committed outputs and prints the
figures in `FIGURES`; the journal's RND-010.7 results carry the quoted text
beside each, and the plan's row 4.4 the ones in `PLAN_FIGURES`; the folder
holds exactly the sitting's files.
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "documentation" / "journals" / "data" / "rnd-010.7"
JOURNAL = ROOT / "documentation" / "journals" / "crowd_draw_journal.md"
PLAN = ROOT / "documentation" / "plans" / "crowd_performance_plan.md"

FIGURES = (
    ("shade walk, us a call  before 1.80 / 1.78  after 2.11 / 2.19  change +0.36 (+0.31 to +0.41)",
     "| the walk (`draw_leads`), µs a call | 1.80 / 1.78 → 2.11 / 2.19, +0.36 (+0.31 to +0.41) |"),
    ("shade walk, us a call  before 1.67 / 1.69  after 2.16 / 2.07  change +0.44 (+0.38 to +0.49)",
     "1.67 / 1.69 → 2.16 / 2.07, +0.44 (+0.38 to +0.49) |"),
    ("enemies/shade p50 ms   before 0.36 / 0.37  after 0.44 / 0.44  change +0.08 (+0.07 to +0.08)",
     "| `enemies/shade` row, p50 ms | 0.36 / 0.37 → 0.44 / 0.44, +0.08 (+0.07 to +0.08) |"),
    ("enemies/shade p50 ms   before 0.57 / 0.56  after 0.67 / 0.67  change +0.11 (+0.10 to +0.11)",
     "0.57 / 0.56 → 0.67 / 0.67, +0.11 (+0.10 to +0.11) |"),
    ("136 drawn, 2 of them shaded", "2 of 136 drawn bodies at 150 and 2 of 226 at 250 are shaded"),
    ("226 drawn, 2 of them shaded", "2 of 226 at 250 are shaded"),
    (("150: 134 unshaded of 136 drawn; 51 with every index cell empty, 83 touching an occupied one; "
     "the 64 px grid returns early for 84"),
     "of the 134 unshaded at 150, 51 touch only empty cells and 83 an occupied one"),
    (("250: 224 unshaded of 226 drawn; 83 with every index cell empty, 141 touching an occupied one; "
     "the 64 px grid returns early for 143"),
     "of the 224 at 250, 83 and 141"),
    ("the 64 px grid returns early for 84", "returns early for 84 of the 134 at 150 and 143 of the 224 at 250"),
    ("before    1.42 / 1.41 us a call", "| the walk | 1.42 / 1.41 | 1.41 / 1.41 |"),
    ("before    1.41 / 1.41 us a call", "| the walk | 1.42 / 1.41 | 1.41 / 1.41 |"),
    ("any_skip  2.24 / 2.26 us a call", "| the skip as built | 2.24 / 2.26 | 2.25 / 2.26 |"),
    ("any_skip  2.25 / 2.26 us a call", "| the skip as built | 2.24 / 2.26 | 2.25 / 2.26 |"),
    ("one_cell  1.86 / 1.84 us a call", "| a one-cell fast path | 1.86 / 1.84 | 1.88 / 1.87 |"),
    ("one_cell  1.88 / 1.87 us a call", "| a one-cell fast path | 1.86 / 1.84 | 1.88 / 1.87 |"),
    ("fine      1.30 / 1.29 us a call", "| an exact skip on a 64 px occupancy grid | 1.30 / 1.29 | 1.29 / 1.29 |"),
    ("fine      1.29 / 1.29 us a call", "| an exact skip on a 64 px occupancy grid | 1.30 / 1.29 | 1.29 / 1.29 |"),
    ("bare      0.58 / 0.57 us a call", "| the call and the cell arithmetic alone | 0.58 / 0.57 | 0.56 / 0.57 |"),
    ("bare      0.56 / 0.57 us a call", "| the call and the cell arithmetic alone | 0.58 / 0.57 | 0.56 / 0.57 |"),
    ("room above the floor 0.113 / 0.112 ms a frame; the fine skip saves 0.016 / 0.014 ms a frame",
     "Above it lies 0.113 / 0.112 ms a frame at 150 and 0.190 / 0.186 at 250"),
    ("room above the floor 0.190 / 0.186 ms a frame; the fine skip saves 0.028 / 0.027 ms a frame",
     "It saves 0.016 / 0.014 ms a frame at 150 and 0.028 / 0.027 at 250"),
    ("the unshaded alone, after: 1.81 / 1.84 us a call",
     "The same skip reads 1.81 / 1.84 µs in sitting 1's `draw_leads` subset at 150, against 2.24 / 2.26 here"),
    ("the fine skip saves 0.016 / 0.014", "It saves 0.014 to 0.028 ms a frame, inside what a sitting resolves"),
)
PLAN_FIGURES = (
    ("change +0.36 (+0.31 to +0.41)", "+0.36 / +0.44 µs a call, `enemies/shade` +0.08 / +0.11 ms at 150 / 250"),
    ("83 with every index cell empty, 141 touching an occupied one",
     "83 of 134 and 141 of 224 unshaded bodies still touch an occupied cell"),
    ("the fine skip saves 0.028 / 0.027", "saves 0.014 to 0.028 ms a frame and is not built (RND-010.7.D1)"),
)
FILES = {"README.md", "derived.py", "sitting1.sh", "s1_meta.txt", "shapes.sh", "walk_shapes.py",
         "shapes_150_a.txt", "shapes_150_b.txt", "shapes_250_a.txt", "shapes_250_b.txt"} | {
    f"s1_{tool}_{n}_{side}_{r}.txt" for tool in ("leads", "layers") for n in (150, 250)
    for side in ("before", "after") for r in "ab"}


def _flat(text: str) -> str:
    return " ".join(text.replace("−", "-").split())


class DerivedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run = subprocess.run([sys.executable, str(DATA / "derived.py")], capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=120, check=False, encoding="utf-8")
        cls.code, cls.out, cls.err = run.returncode, run.stdout, run.stderr
        results = JOURNAL.read_text(encoding="utf-8").split("## RND-010.7: Results", 1)[1]
        cls.journal = _flat(results.split("\n## ", 1)[0])
        cls.plan = _flat(PLAN.read_text(encoding="utf-8"))

    def test_it_runs(self):
        self.assertEqual(self.code, 0, self.err)

    def test_the_journal_quotes_what_it_prints(self):
        for printed, quoted in FIGURES:
            with self.subTest(figure=quoted):
                self.assertIn(printed, self.out)
                self.assertIn(_flat(quoted), self.journal)

    def test_the_plan_quotes_it_too(self):
        for printed, quoted in PLAN_FIGURES:
            with self.subTest(figure=quoted):
                self.assertIn(printed, self.out)
                self.assertIn(_flat(quoted), self.plan)


class FolderTests(unittest.TestCase):
    def test_the_folder_holds_exactly_the_sitting(self):
        self.assertEqual({p.name for p in DATA.iterdir() if p.is_file()}, FILES)


if __name__ == "__main__":
    unittest.main()
