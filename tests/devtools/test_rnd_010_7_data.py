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
    (("150: 134 unshaded; before 1.44, any_skip 2.30, one_cell 1.91, bare 0.61; room above the floor 0.83 us, "
     "0.11 ms a frame"),
     "the walk is 1.44 µs a call at 150 and 1.45 at 250, against a floor of 0.61 and 0.59"),
    (("250: 224 unshaded; before 1.45, any_skip 2.32, one_cell 1.93, bare 0.59; room above the floor 0.86 us, "
     "0.19 ms a frame"),
     "The room above the floor is 0.11 ms a frame at 150 and 0.19 at 250"),
    ("any_skip 2.30", "the skip as built is 2.30 and 2.32 µs, a one-cell fast path 1.91 and 1.93"),
)
PLAN_FIGURES = (
    ("change +0.36 (+0.31 to +0.41)", "+0.36 / +0.44 µs a call, `enemies/shade` +0.08 / +0.11 ms at 150 / 250"),
    ("room above the floor 0.83 us, 0.11 ms a frame", "the most any skip could save is 0.11 / 0.19 ms"),
)
FILES = {"README.md", "derived.py", "sitting1.sh", "s1_meta.txt", "shapes.sh", "walk_shapes.py",
         "shapes_150.txt", "shapes_250.txt"} | {
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
