"""RND-010.3: the results' figures come out of the raw sittings
(`documentation/journals/data/rnd-010.3/derived.py`, `crowd_draw_journal.md`).

What is pinned, and no more:
* `derived.py` runs on the committed outputs and prints the figures in
  `FIGURES`, so a raw file edited or a parser gone wrong shows here;
* for each of those, the journal's results carry the quoted text beside
  it, so those figures, if retyped by hand and wrong, fail here. The
  tables and the plan's annotations are not pinned figure by figure;
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
    (("flat/elemental         quiet  0.08 /  0.08  fight  1.44 /  1.44  added +1.36",
      "flat/elemental         quiet  0.11 /  0.11  fight  2.81 /  2.82  added +2.71"),
     "| `flat/elemental` (auras, status marks, areas, motes under the bodies) | +1.36 ms | +2.71 ms |"),
    (("enemies                quiet  1.89 /  1.86  fight  2.32 /  2.34  added +0.46",
      "enemies                quiet  2.97 /  2.94  fight  5.07 /  5.07  added +2.12"),
     "| `enemies` (an enemy's own draw) | +0.46 ms | +2.12 ms |"),
    ("mean diff median -1.27, interval -1.56 to -0.74 -> faster; p90 19.61 -> 18.08; p99 28.87 -> 23.31",
     "-1.27, -1.56 to -0.74 ms: **faster**"),
    ("the mean falls by 1.28 ms", "pooled, 1.28 ms"),
    ("the gap is 0.27 to 1.09 ms; against the pooled 1.28, 0.55 ms", "the gap is 0.27 to 1.09 ms"),
    ("emptied 26 times in 600 frames (about every 23)", "emptied 26 times in 600 frames, about every 23"),
    ("today's cap holds 0.31 of the distinct frames", "Today's cap holds 0.31 of them"),
    ("predicted 1.85 ms a frame (the emptying 0.003 of it), its worst frame 11.52 ms",
     "1.85 ms a frame, with a worst frame of 11.5 ms"),
    ("LRU  1536: 0.31 a frame, worst 3, held at most 80.6 MB; predicts 1.83 ms a frame saved",
     "| wash, LRU 1536 | 0.31 | 3 | 80.6 MB |"),
    ("LRU  1024: 2.07 a frame, worst 11, held at most 55.5 MB; predicts 1.68 ms a frame saved",
     "predicts 1.68 ms saved"),
    (("the largest frame is bear's, 203x173, 0.14 MB a copy; full caps: 512 -> 71.9 MB, "
      "1024 -> 143.8 MB, 1536 -> 215.8 MB"), "0.14 MB (bear, 203x173; bosses are never washed)"),
    ("1536 -> 215.8 MB", "1536 up to 215.8 MB"),
    (("the largest frame is pig_rider's, 467x367, 0.69 MB a copy; full caps: 128 -> 87.8 MB, "
      "256 -> 175.5 MB"), "a full 256 could hold up to 175.5 MB"),
    (("150: sittings 1 and 2's fights' bare draw over sitting 5's, every pairing: +0.63 to +1.90 ms",
      "250: sittings 1 and 2's fights' bare draw over sitting 5's, every pairing: +0.80 to +2.97 ms"),
     "0.6 to 3.0 ms more than sitting 5's"),
    ("n=200 sprite only        p50 1.86 ms, less the fill 0.37: 7.45 us a sprite",
     "the fill alone takes 0.37 ms"),
    ("the lambda and the forwarder alone: 0.05 ms",
     "lambda and the forwarder together cost 0.03 ms at 150 and 0.05 at 250"),
    (("150: sitting 1's fights' bare draw over sitting 5's, every pairing: +1.84 to +1.90 ms",
      "250: sitting 1's fights' bare draw over sitting 5's, every pairing: +2.91 to +2.97 ms"),
     "1.8 to 1.9 ms more at 150 than sitting 5's (2.9 to 3.0 at 250)"),
    ("the replay predicts today's wash cache at 0.28 ms a frame and the LRU of 1536 to save 0.24",
     "0.28 ms a frame for today's cache, and at 0.24 ms saved by the LRU of 1536"),
    ("the fight's bare draw less terrain 46 us an enemy: 0.17 to 0.37 ms", "are worth 0.17 to 0.37 ms"),
    (("n=300 sprite only        p50 2.46 ms, less the fill 0.37: 6.97 us a sprite",
      "n=100 sprite only        p50 1.23 ms, less the fill 0.37: 8.60 us a sprite"),
     "6.97 to 8.60 µs a blit"),
    ("= 175.5 MB, whatever the caps above", "up to 175.5 MB (128 x 2 x 0.69 MB)"),
    (("against the median per-block mean saving 0.30 (-0.11 to 1.04) the gap is -0.80 to 0.35 ms; "
      "against the pooled 0.58, -0.34 ms"), "the pooled mean saving is 0.58 ms"),
    ("against the pooled 0.58", "The median's interval there (-0.11 to +1.04)"),
    (("update   quiet   7.88 /   7.82  fight   7.51 /   7.60  added  -0.29 (from -0.37 to -0.22)",
      "update   quiet  12.27 /  12.30  fight  12.12 /  12.09  added  -0.18 (from -0.21 to -0.15)"),
     "The update falls a little in every pair (-0.37 to -0.15 ms)"),
    ("the fight ends with 25 fewer alive", "25 fewer at the end at 150"),
    ("(16 in all, while timed)", "at least 16 and 22 arrived later"),
    ("enemies/shade: quiet 0.38 / 0.37, fight 0.43 / 0.43; enemies/hpbar fight 0.58 / 0.58",
     ("`enemies/shade` row is 0.38 / 0.61 ms quiet and 0.43 / 0.67 ms in the fight, against the "
      "fight's bars at 0.58 / 0.56 ms")),
)

# D2's figures: what derived.py prints, and what the decision says.
D2_FIGURES = (
    ("held at most 28.2 MB;", "held at most 28.2 MB"),
    ("held at most 80.6 MB; predicts 1.83 ms a frame saved", "held at most 80.6 MB"),
    ("held at most 55.5 MB; predicts 1.68 ms a frame saved", "1024 held 55.5 MB, for a predicted 1.68 ms"),
    ("512 -> 71.9 MB, 1024 -> 143.8 MB, 1536 -> 215.8 MB",
     "today's 512 could hold up to 71.9 MB, 1024 up to 143.8 MB and 1536 up to 215.8 MB"),
    ("256 -> 175.5 MB", "a tint cap of 256 could hold up to 175.5 MB"),
    ("= 175.5 MB, whatever the caps above", "up to 175.5 MB whatever the caps"),
)

# The same for a few of the plan's RND-010.3 annotations.
PLAN_FIGURES = (
    ("sitting 5, every run at both counts: ground 3.33 to 3.41 ms", "`ground` at 3.33 to 3.41 ms"),
    ("sitting 5, every run at both counts: water 1.00 to 1.08 ms", "`water` at 1.00 to 1.08 ms"),
    ("mean diff median -1.27, interval -1.56 to -0.74",
     "the blocks' median mean saving is 1.27 ms (97.9 % interval 0.74 to 1.56"),
    ("1536 -> 215.8 MB", "so 1536 could hold 215.8 MB"),
)
PLAN = ROOT / "documentation" / "plans" / "crowd_performance_plan.md"

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
            with self.subTest(figure=quoted):
                for line in (printed if isinstance(printed, tuple) else (printed,)):
                    self.assertIn(line, self.out)
                self.assertIn(quoted, self.journal)

    def test_d2_quotes_them(self):
        journal = JOURNAL.read_text(encoding="utf-8")
        d2 = journal.split("**RND-010.D2", 1)[1].split("\n- **", 1)[0].split("\n## ", 1)[0]
        d2 = " ".join(d2.split())
        for printed, quoted in D2_FIGURES:
            with self.subTest(figure=quoted):
                self.assertIn(printed, self.out)
                self.assertIn(quoted, d2)

    def test_the_plan_quotes_them_too(self):
        plan = " ".join(PLAN.read_text(encoding="utf-8").replace("−", "-").split())
        for printed, quoted in PLAN_FIGURES:
            with self.subTest(figure=quoted):
                self.assertIn(printed, self.out)
                self.assertIn(quoted, plan)

    def test_the_prediction_and_the_bound_recomputed_apart(self):
        # The saving the LRU of 1536 predicts at 250, from the raw caches
        # file, and the wash cap's bound, from the rig data: worked here
        # without derived.py's code, then found in its output.
        import json
        t = (DATA / "r5_caches_250.txt").read_text(encoding="utf-8")
        wash = t.split("  wash: ", 1)[1].split("  tint: ", 1)[0]
        today = float(re.search(r"cap\s+512: emptied when full\s+([\d.]+)", wash).group(1))
        clears = int(re.search(r"cap\s+512: .*?emptied\s+(\d+) times", wash).group(1))
        lru = float(re.search(r"cap\s+1536: .*?LRU\s+([\d.]+)", wash).group(1))
        miss = float(re.search(r"a miss ([\d.]+) us", wash).group(1))
        empty = float(re.search(r"emptying a cache of 512: ([\d.]+) ms", wash).group(1))
        frames = 900 - 300
        saved = (today - lru) * miss / 1000 + clears * empty / frames
        self.assertIn(f"held at most 80.6 MB; predicts {saved:.2f} ms a frame saved", self.out)
        rigs = json.loads((ROOT / "data" / "enemies" / "enemy_sprites.json").read_text(encoding="utf-8"))
        worn = {e["sprite"] for e in json.loads((ROOT / "data" / "enemies" / "enemies.json")
                                                .read_text(encoding="utf-8")).values() if e.get("sprite")}
        self.assertEqual([r for r in sorted(worn) if not rigs.get(r, {}).get("scale")], [])  # none skipped
        display = (DATA / "r5_fight_250a.txt").read_text(encoding="utf-8")
        zoom = float(re.search(r"zoom ([\d.]+)", display).group(1))
        size = lambda table, r: round(table[r]["scale"][0] * zoom) * round(table[r]["scale"][1] * zoom) * 4
        biggest = max(size(rigs, r) for r in worn)
        self.assertIn(f"1536 -> {1536 * biggest / 1e6:.1f} MB", self.out)
        # The tint cache and the ghost cache: enemies, bosses and every hero rig.
        bosses = {b["sprite"] for b in json.loads((ROOT / "data" / "enemies" / "bosses.json")
                                                  .read_text(encoding="utf-8")).values() if b.get("sprite")}
        heroes = json.loads((ROOT / "data" / "heroes" / "character_sprites.json").read_text(encoding="utf-8"))
        largest = max([size(rigs, r) for r in worn | bosses]
                      + [size(heroes, r) for r in heroes if heroes[r].get("scale")])
        self.assertIn(f"256 -> {256 * largest / 1e6:.1f} MB", self.out)
        self.assertIn(f"= {128 * 2 * largest / 1e6:.1f} MB, whatever the caps above", self.out)

    def test_a_row_a_run_did_not_print_is_named(self):
        self.assertIn("no row in quiet a (never called there, counted 0): death_fx, death_fx/shade", self.out)


def _callers(name: str) -> set:
    """`(file, function)` for every reference to `name` (a bare name or an
    attribute, called or not, so an alias such as `w = fx.washed` counts)
    anywhere under `game/`, by the innermost function holding it, or
    `<module>` outside any. The definition itself is not a reference."""
    import ast

    found = set()

    def visit(node, where, rel):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                visit(child, child.name, rel)
                continue
            if name in (getattr(child, "attr", None), getattr(child, "id", None)) \
                    and isinstance(child, ast.Attribute | ast.Name):
                found.add((rel, where))
            visit(child, where, rel)

    for path in sorted((ROOT / "game").rglob("*.py")):
        visit(ast.parse(path.read_text(encoding="utf-8")), "<module>", path.relative_to(ROOT).as_posix())
    return found


class CodeTests(unittest.TestCase):
    """The premises D2's bounds rest on: which frames reach which cache."""

    RENDERING = "game/states/playing/visual/rendering.py"

    def test_washed_has_one_caller_the_enemy_sprite(self):
        # Only a regular enemy's frame is ever washed, never a boss's or
        # the hero's: the wash bound runs over enemies.json's rigs alone.
        self.assertEqual(_callers("washed"), {(self.RENDERING, "enemy_sprite")})

    def test_hit_tinted_takes_enemies_the_boss_and_the_hero(self):
        # The tint bound runs over enemy, boss and hero rigs: no other caller.
        # `PlayingState._hit_tinted` is a class-level alias of it, which
        # nothing in the game calls (the tests do).
        state = "game/states/playing/core/state.py"
        self.assertEqual(_callers("hit_tinted"), {(self.RENDERING, "enemy_sprite"),
                                                  (self.RENDERING, "boss"), (self.RENDERING, "player"),
                                                  (state, "<module>")})
        self.assertEqual(_callers("_hit_tinted"), {(state, "<module>")})


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
