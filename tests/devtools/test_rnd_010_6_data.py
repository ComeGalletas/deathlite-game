"""RND-010.6: the results' figures come out of the four sittings and the
headless counts (`documentation/journals/data/rnd-010.6/derived.py`,
`crowd_draw_journal.md`).

What is pinned: `derived.py` runs on the committed outputs and prints the
figures in `FIGURES`; the journal's RND-010.6 results carry the quoted
text beside each, the plan's row 4.5 the ones in `PLAN_FIGURES`, and the
cache's docstring the counts its cap rests on; the folder holds exactly
the sittings' files.
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "documentation" / "journals" / "data" / "rnd-010.6"
JOURNAL = ROOT / "documentation" / "journals" / "crowd_draw_journal.md"
PLAN = ROOT / "documentation" / "plans" / "crowd_performance_plan.md"
RLE = ROOT / "game" / "states" / "playing" / "visual" / "elements" / "rle.py"

# (what derived.py prints, what the journal's results say), the journal's
# side matched with its whitespace collapsed.
FIGURES = (
    # The split, sitting 1.
    ("elemental/auras        0.82 / 0.79", "| `elemental/auras` | 0.82 / 0.79 | 2.35 / 2.33 |"),
    ("elemental/auras        2.35 / 2.33", "| `elemental/auras` | 0.82 / 0.79 | 2.35 / 2.33 |"),
    ("elemental/areas        0.45 / 0.40", "| `elemental/areas` | 0.45 / 0.40 | 0.47 / 0.46 |"),
    ("elemental/areas        0.47 / 0.46", "| `elemental/areas` | 0.45 / 0.40 | 0.47 / 0.46 |"),
    ("elemental/statuses     0.36 / 0.31", "| `elemental/statuses` | 0.36 / 0.31 | 0.31 / 0.31 |"),
    ("elemental/statuses     0.31 / 0.31", "| `elemental/statuses` | 0.36 / 0.31 | 0.31 / 0.31 |"),
    ("elemental/particles    0.10 / 0.09", "| `elemental/particles` | 0.10 / 0.09 | 0.28 / 0.27 |"),
    ("elemental/particles    0.28 / 0.27", "| `elemental/particles` | 0.10 / 0.09 | 0.28 / 0.27 |"),
    ("the under-layer, summed 1.76 / 1.62", "| the under-layer, summed | 1.76 / 1.62 | 3.44 / 3.41 |"),
    ("the under-layer, summed 3.44 / 3.41", "| the under-layer, summed | 1.76 / 1.62 | 3.44 / 3.41 |"),
    # The leads, sitting 1.
    ("150: 51.6 auras", "51.6 drawn at 150 and 183.7 at 250"),
    ("250: 183.7 auras", "51.6 drawn at 150 and 183.7 at 250"),
    ("aura blit 0.640, its RLE copy 0.063, predicted saving 0.577",
     "the blit 0.640 and 2.077 ms, its RLE copy 0.063 and 0.235 ms, a predicted saving of 0.577 and 1.842 ms"),
    ("aura blit 2.077, its RLE copy 0.235, predicted saving 1.842", "a predicted saving of 0.577 and 1.842 ms"),
    ("aura lookups (state, world_to_screen, size, frame) 0.100", "frame) 0.100 and 0.289 ms"),
    ("aura lookups (state, world_to_screen, size, frame) 0.289", "whose lookups total 0.289 ms at 250"),
    ("chill surface + polygons 0.146", "0.146 ms at 150, 0.032 at 250"),
    ("chill surface + polygons 0.032", "0.146 ms at 150, 0.032 at 250"),
    ("ring surface + circle 0.104", "surface and circle, what `ring_cached` removes: 0.104 and 0.153 ms"),
    ("ring surface + circle 0.153", "0.104 and 0.153 ms"),
    # The variants.
    ("s3 150 aura_rle         p50 -0.42 (-1.19 to +0.20) not resolved; mean -0.37 (-1.18 to -0.04) resolved",
     "-0.42 (-1.19 to +0.20), not resolved; the mean -0.37 (-1.18 to -0.04), resolved"),
    ("s3 250 aura_rle         p50 -1.14 (-1.71 to -0.26) resolved; mean -0.95 (-1.79 to -0.46) resolved",
     "-1.14 (-1.71 to -0.26), resolved; the mean -0.95 (-1.79 to -0.46)"),
    ("s3 150 shape_cached     p50 -0.03 (-0.56 to +0.23) not resolved", "-0.03 (-0.56 to +0.23), not resolved"),
    ("s3 250 shape_cached     p50 +0.15 (-1.01 to +0.65) not resolved", "+0.15 (-1.01 to +0.65), not resolved"),
    ("s3 150 ring_cached      p50 +0.03 (-0.37 to +0.24) not resolved", "+0.03 (-0.37 to +0.24), not resolved"),
    ("s3 250 ring_cached      p50 +0.10 (-1.12 to +0.36) not resolved", "+0.10 (-1.12 to +0.36), not resolved"),
    ("s1 150 aura_lookup_once p50 -0.09 (-0.89 to +0.48) not resolved", "-0.09 (-0.89 to +0.48), not resolved"),
    ("s1 250 aura_lookup_once p50 +0.04 (-0.26 to +0.38) not resolved", "+0.04 (-0.26 to +0.38), not resolved"),
    # Before and after, sitting 4: the fight.
    ("bare      before  15.61 /  16.36  after  14.54 /  14.51  change  -1.46 (-1.85 to -1.07)",
     "| bare draw | -1.46 (-1.85 to -1.07) | -1.26 (-1.95 to -0.56) | -2.46 (-2.77 to -2.16) |"),
    ("change  -1.26 (-1.95 to -0.56)", "| bare draw | -1.46 (-1.85 to -1.07) | -1.26 (-1.95 to -0.56) |"),
    ("change  -2.46 (-2.77 to -2.16)", "| -1.26 (-1.95 to -0.56) | -2.46 (-2.77 to -2.16) |"),
    ("under-layer before   1.94 /   2.07  after   1.37 /   1.29  change  -0.67 (-0.78 to -0.57)",
     "| -0.67 (-0.78 to -0.57) | -1.20 (-1.25 to -1.15) | -1.66 (-1.70 to -1.63) |"),
    ("under-layer before   3.22 /   3.31  after   2.06 /   2.07  change  -1.20 (-1.25 to -1.15)",
     "| the under-layer's rows | -0.67 (-0.78 to -0.57) | -1.20 (-1.25 to -1.15) |"),
    ("under-layer before   3.62 /   3.61  after   1.92 /   1.98  change  -1.66 (-1.70 to -1.63)",
     "At 250 they fall from 3.62 / 3.61 to 1.92 / 1.98 ms"),
    ("change  -2.86 (-3.18 to -2.53)",
     "| draw p90 | -2.86 (-3.18 to -2.53) | -1.84 (-2.77 to -0.92) | -3.30 (-4.38 to -2.22) |"),
    ("change  -1.84 (-2.77 to -0.92)", "| -2.86 (-3.18 to -2.53) | -1.84 (-2.77 to -0.92) |"),
    ("change  -3.30 (-4.38 to -2.22)", "| -1.84 (-2.77 to -0.92) | -3.30 (-4.38 to -2.22) |"),
    ("frame     before  24.78 /  26.18  after  22.84 /  23.09  change  -2.52 (-3.34 to -1.69)",
     "| update + draw | -2.52 (-3.34 to -1.69) | -1.21 (-2.51 to +0.09) | -3.24 (-4.18 to -2.29) |"),
    ("change  -1.21 (-2.51 to +0.09)", "| -2.52 (-3.34 to -1.69) | -1.21 (-2.51 to +0.09) |"),
    ("change  -3.24 (-4.18 to -2.29)", "| -1.21 (-2.51 to +0.09) | -3.24 (-4.18 to -2.29) |"),
    ("update    before   9.11 /   9.49  after   8.64 /   8.76  change  -0.60",
     "the fight's update, which the change does not touch, moved -0.60, -0.14 and -0.34 ms"),
    ("update    before  10.59 /  11.53  after  10.86 /  10.97  change  -0.14", "moved -0.60, -0.14 and -0.34 ms"),
    ("update    before  14.17 /  14.18  after  13.57 /  14.11  change  -0.34", "moved -0.60, -0.14 and -0.34 ms"),
    ("the bare draw's change beyond the under-layer's: -0.79",
     "by 0.79 ms at 150 and 0.80 at 250 (-1.46 against -0.67, -2.46 against -1.66; 0.06 at 200)"),
    ("the bare draw's change beyond the under-layer's: -0.80", "0.80 at 250"),
    ("the bare draw's change beyond the under-layer's: -0.06", "0.06 at 200"),
    # The quiet control.
    ("under-layer before   0.09 /   0.10  after   0.10 /   0.10  change  +0.01",
     "the same rows move +0.01 to +0.02 ms"),
    ("under-layer before   0.10 /   0.10  after   0.11 /   0.12  change  +0.02",
     "the same rows move +0.01 to +0.02 ms"),
    ("under-layer before   0.12 /   0.12  after   0.13 /   0.13  change  +0.01",
     "the same rows move +0.01 to +0.02 ms"),
    ("bare      before  10.34 /  10.51  after  10.96 /  10.73  change  +0.42 (+0.22 to +0.62)",
     "at 200 its bare draw +0.42 (+0.22 to +0.62)"),
    ("draw p90  before  11.58 /  12.39  after  12.70 /  13.25  change  +0.99 (+0.31 to +1.67)",
     "its draw p90 +0.99 (+0.31 to +1.67)"),
    ("frame     before  20.34 /  20.53  after  21.45 /  20.95  change  +0.76 (+0.42 to +1.11)",
     "its update + draw +0.76 (+0.42 to +1.11)"),
    ("update    before  10.06 /  10.10  after  10.52 /  10.39  change  +0.38", "its update, untouched, +0.38 ms"),
    ("sitting 4's load at its steps: cpu 6 to 74 %, gpu 0 to 20 %", "(CPU load 6 to 74 % at the steps, GPU 0 to 20 %"),
    ("sitting 4's draw p99s: fight 30.20 to 84.08 ms, quiet 18.99 to 49.31 ms",
     "run from 30.20 to 84.08 ms in the fight and from 18.99 to 49.31 ms in the quiet runs"),
    ("reactions/transient    0.05 / 0.05", "at 0.05 / 0.05 ms at 150 and 0.07 / 0.07 at 250"),
    ("reactions/transient    0.07 / 0.07", "0.07 / 0.07 at 250: too small to pursue"),
    ("the two caches' parts, each count: 0.03 to 0.15 ms", "remove 0.03 to 0.15 ms each in the leads"),
    # The cache.
    ("150: 342 distinct aura frames", "asks for 342 distinct aura frames at 150 and 456 at 250"),
    ("250: 456 distinct aura frames", "456 at 250, so the cap is over twice the larger"),
    ("380 copies, 18.8 MB as pixels", "leaves 380 copies at 150 and 443 at 250, 18.8 and 23.6 MB"),
    ("443 copies, 23.6 MB as pixels", "18.8 and 23.6 MB as pixels, at the headless zoom of 1.5"),
    ("largest 116 kB, cap 1024 x largest = 118.4 MB", "the largest copy, 116 kB there, so 118.4 MB as pixels"),
    ("150: resident memory +16.6 MB as plain copies, +17.3 MB once encoded",
     "raises its resident memory by 16.6 and 19.3 MB, and +17.3 and +20.3 MB once each is encoded"),
    ("250: resident memory +19.3 MB as plain copies, +20.3 MB once encoded", "+17.3 and +20.3 MB once"),
)
PLAN_FIGURES = (
    ("aura blit 2.077, its RLE copy 0.235", "the aura's blit (2.077 ms at 250 in the fight), which an RLE copy"),
    ("its RLE copy 0.235", "cuts to 0.235"),
    ("change  -0.67 (-0.78 to -0.57)", "the under-layer's rows -0.67 / -1.20 / -1.66 ms"),
    ("the two caches' parts, each count: 0.03 to 0.15 ms", "the caches named here remove 0.03 to 0.15 ms each"),
)
# Outside the results: the sequence table's row and the cache's docstring.
JOURNAL_FIGURES = (
    ("change  -1.66 (-1.70 to -1.63)", "the aura's RLE blit, -1.66 ms on the under-layer at 250 in the fight"),
)
RLE_FIGURES = (
    ("change  -1.66 (-1.70 to -1.63)", "the under-layer's rows fell by 1.66 ms"),
    ("150: 342 distinct aura frames", "asks for 342 distinct aura frames at 150 and 456 at 250"),
    ("250: 456 distinct aura frames", "asks for 342 distinct aura frames at 150 and 456 at 250"),
)
SITTING_4 = {f"s4_{kind}_{n}_{side}_{r}.txt" for kind in ("fight", "quiet") for n in (150, 200, 250)
             for side in ("before", "after") for r in "ab"}
FILES = {"README.md", "derived.py", "counts.sh", "aura_keys.py", "rle_bytes.py", "rle_memory.py",
         "keys_150.txt", "keys_250.txt", "bytes_150.txt", "bytes_250.txt", "memory_150.txt", "memory_250.txt",
         "sitting1.sh", "sitting2.sh", "sitting3.sh", "sitting4.sh",
         "s1_meta.txt", "s2_meta.txt", "s3_meta.txt", "s4_meta.txt",
         "s1_layers_150_a.txt", "s1_layers_150_b.txt", "s1_layers_250_a.txt", "s1_layers_250_b.txt",
         "s1_leads_150.txt", "s1_leads_250.txt", "s1_variants_150.txt", "s1_variants_250.txt",
         "s2_aura_rle_150.txt", "s2_aura_rle_250.txt", "s3_variants_150.txt", "s3_variants_250.txt"} | SITTING_4


def _flat(text: str) -> str:
    return " ".join(text.replace("−", "-").split())


class DerivedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run = subprocess.run([sys.executable, str(DATA / "derived.py")], capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=120, check=False)
        cls.code, cls.out, cls.err = run.returncode, run.stdout, run.stderr
        results = JOURNAL.read_text(encoding="utf-8").split("## RND-010.6: Results", 1)[1]
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

    def test_the_sequence_row_and_the_cache_quote_it_too(self):
        journal = _flat(JOURNAL.read_text(encoding="utf-8"))
        doc = _flat(RLE.read_text(encoding="utf-8"))
        for printed, quoted in JOURNAL_FIGURES:
            with self.subTest(journal=quoted):
                self.assertIn(printed, self.out)
                self.assertIn(_flat(quoted), journal)
        for printed, quoted in RLE_FIGURES:
            with self.subTest(rle=quoted):
                self.assertIn(printed, self.out)
                self.assertIn(_flat(quoted), doc)


class FolderTests(unittest.TestCase):
    def test_the_folder_holds_exactly_the_sittings(self):
        self.assertEqual({p.name for p in DATA.iterdir() if p.is_file()}, FILES)


if __name__ == "__main__":
    unittest.main()
