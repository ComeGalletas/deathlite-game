"""RND-010.3: the results' figures come out of the raw sittings
(`documentation/journals/data/rnd-010.3/derived.py`, `crowd_draw_journal.md`).

What is pinned:
* `derived.py` runs on the committed outputs and prints the figures the
  journal's results lean on, so a raw file edited or a parser gone wrong
  shows here rather than in a stale journal;
* the journal quotes those same figures (a figure retyped by hand and
  wrong fails here);
* the folder holds exactly the files the README accounts for, no more.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "documentation" / "journals" / "data" / "rnd-010.3"
JOURNAL = ROOT / "documentation" / "journals" / "crowd_draw_journal.md"

# (what derived.py prints, what the journal's results say), the journal's
# side matched with its whitespace collapsed and its minus signs as "-".
FIGURES = (
    ("bare     quiet   9.02 /   8.86  fight  12.13 /  12.07  added  +3.16 (from +3.05 to +3.27)",
     "+3.16 (+3.05 to +3.27)"),
    ("bare     quiet  10.69 /  10.58  fight  17.51 /  17.45  added  +6.85 (from +6.76 to +6.93)",
     "+6.85 (+6.76 to +6.93)"),
    ("flat/elemental         quiet  0.11 /  0.11  fight  2.81 /  2.82  added +2.71", "+2.71 ms"),
    ("enemies                quiet  2.97 /  2.94  fight  5.07 /  5.07  added +2.12", "+2.12 ms"),
    ("mean diff median -1.27, interval -1.56 to -0.74 -> faster; p90 19.61 -> 18.08; p99 28.87 -> 23.31",
     "-1.27, -1.56 to -0.74 ms: **faster**"),
    ("the mean falls by 1.28 ms", "pooled, 1.28 ms"),
    ("the gap is 0.27 to 1.09 ms; against the pooled 1.28, 0.55 ms", "the gap is 0.27 to 1.09 ms"),
    ("emptied 26 times in 600 frames (about every 23)", "emptied 26 times in 600 frames, about every 23"),
    ("today's cap holds 0.31 of the distinct frames", "Today's cap holds 0.31 of them"),
    ("predicted 1.85 ms a frame (the emptying 0.003 of it), its worst frame 11.52 ms",
     "1.85 ms a frame, with a worst frame of 11.5 ms"),
    ("LRU  1536: 0.31 a frame, worst 3, held at most 80.6 MB; predicts 1.83 ms a frame saved", "80.6 MB"),
    ("LRU  1024: 2.07 a frame, worst 11, held at most 55.5 MB; predicts 1.68 ms a frame saved",
     "predicts 1.68 ms saved"),
    ("pig_rider's, 467x367, 0.69 MB a copy", "0.69 MB (pig_rider, 467x367)"),
    ("a cap of   512 full of them:   351.0 MB", "351 MB"),
    ("a cap of  1536 full of them:  1053.0 MB", "1,053 MB"),
    ("250: sittings 1 and 2's fights' bare draw over sitting 5's, every pairing: +0.80 to +2.97 ms",
     "0.6 to 3.0 ms more than sitting 5's"),
    ("n=200 sprite only        p50 1.86 ms, less the fill 0.37: 7.45 us a sprite", "0.37 ms"),
    ("the lambda and the forwarder alone: 0.05 ms",
     "lambda and the forwarder together cost 0.03 ms at 150 and 0.05 at 250"),
)

FILES = {"README.md", "derived.py"} | {f"sitting{n}.sh" for n in range(1, 6)} | {
    f"r{n}_meta.txt" for n in range(1, 6)} | {
    *(f"r1_{k}_{c}.txt" for k in ("leads", "variants", "fight") for c in (150, 250)),
    "r1_gc.txt", "r1_blit_floor.txt",
    *(f"r2_{k}_{c}.txt" for k in ("caches", "wash_lru", "fight") for c in (150, 250)),
    *(f"r3_quiet_{c}{r}.txt" for c in (150, 250) for r in "ab"),
    *(f"r3_caches_{c}.txt" for c in (150, 250)),
    *(f"r4_{k}_{c}{r}.txt" for k in ("quiet", "fight") for c in (150, 250) for r in "ab"),
    *(f"r5_{k}_{c}{r}.txt" for k in ("quiet", "fight") for c in (150, 250) for r in "ab"),
    *(f"r5_{k}_{c}.txt" for k in ("caches", "wash_lru") for c in (150, 250)),
    "r5_blit_floor.txt",
}


class DerivedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run = subprocess.run([sys.executable, str(DATA / "derived.py")], capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=120, check=False)
        cls.code, cls.out, cls.err = run.returncode, run.stdout, run.stderr
        results = JOURNAL.read_text(encoding="utf-8").split("## RND-010.3: Results", 1)[1]
        results = results.split("\n## ", 1)[0]
        cls.journal = " ".join(results.replace("−", "-").split())

    def test_it_runs(self):
        self.assertEqual(self.code, 0, self.err)

    def test_the_figures_come_out_and_the_journal_quotes_them(self):
        for printed, quoted in FIGURES:
            with self.subTest(figure=printed):
                self.assertIn(printed, self.out)
                self.assertIn(quoted, self.journal)

    def test_a_row_a_run_did_not_print_is_named(self):
        self.assertIn("no row in quiet a (never called there, counted 0): death_fx, death_fx/shade", self.out)


class ReadmeTests(unittest.TestCase):
    def test_the_folder_holds_exactly_the_sittings(self):
        self.assertEqual({p.name for p in DATA.iterdir() if p.is_file()}, FILES)

    def test_the_readme_accounts_for_every_output(self):
        readme = (DATA / "README.md").read_text(encoding="utf-8")
        for name in sorted(FILES - {"README.md"}):
            with self.subTest(file=name):
                stem = re.match(r"(r\d_[a-z_]+?)_\d", name)
                self.assertTrue(name in readme
                                or re.fullmatch(r"r\d_meta\.txt|sitting\d\.sh", name)
                                or (stem and (stem.group(1) + "_*" in readme or name[:2] + "_*" in readme)),
                                f"{name} is not in the README")


if __name__ == "__main__":
    unittest.main()
