"""RND-010.6.3: the pieces of the elemental under-layer, timed in isolation
(`tools/benchmarks/under_leads.py`, `crowd_draw_journal.md`).

What is pinned:
* **the items:** the auras the probe times are the primed bodies the real
  pass draws, and every list is what its pass would iterate;
* **the pieces:** every one runs on its items in a real packed fight
  (seed 35), and timing them leaves the fight as it was;
* **the snapshots:** the fight is advanced between measured frames, not
  before the first;
* **the arithmetic and the printout** on made-up samples;
* **the command line**, and an end-to-end run.
"""
import contextlib
import io
import unittest
from typing import ClassVar
from unittest import mock

import pygame

from tests.devtools import (
    test_draw_layers as TDL,  # an alias: its classes are not collected twice
)
from tools.benchmarks import layer_probes as LP
from tools.benchmarks import under_leads as UL

SEED = 35


def _shot(samples, counts):
    passes = {"auras, whole": "auras", "aura: blit": "auras", "aura: blit, RLE copy": "candidates",
              "areas, whole": "areas", "ring: blit": "areas", "statuses, whole": "statuses"}
    over = {"auras, whole": "auras", "aura: blit": "auras", "aura: blit, RLE copy": "auras",
            "areas, whole": "areas", "ring: blit": "areas", "statuses, whole": "statuses"}
    return {"samples": samples, "pass": passes, "over": over,
            "counts": {"auras": 0, "statuses": 0, "chilled": 0, "burning": 0, "areas": 0, **counts}}


class ArithmeticTests(unittest.TestCase):
    # Two fight frames. The first: 100 auras, aura blit p50 6 (of 4, 6, 20),
    # whole p50 10; 2 tornadoes, ring blit 30, areas whole 50. The second:
    # 200 auras, blit p50 8, whole 12; no tornado (its area pieces unsampled).
    SHOTS: ClassVar[list] = [
        _shot({"auras, whole": [10.0, 30.0, 9.0], "aura: blit": [4.0, 6.0, 20.0],
               "aura: blit, RLE copy": [1.0], "areas, whole": [50.0], "ring: blit": [30.0],
               "statuses, whole": []},
              {"auras": 100, "areas": 2}),
        _shot({"auras, whole": [12.0], "aura: blit": [8.0], "aura: blit, RLE copy": [2.0],
               "areas, whole": [], "ring: blit": [], "statuses, whole": []},
              {"auras": 200, "areas": 0}),
    ]

    def test_the_means_over_the_snapshots(self):
        rows = UL.per_frame(self.SHOTS)
        # whole: (10 x 100 + 12 x 200) / 1000 = 3.4 ms over 2 frames -> 1.7 ms a
        # frame, 150 items a frame, 3400 / 300 = 11.33 us an item.
        us, n, ms = rows["auras, whole"]
        self.assertAlmostEqual(ms, 1.7)
        self.assertEqual(n, 150.0)
        self.assertAlmostEqual(us, 3400 / 300)
        # blit: (6 x 100 + 8 x 200) / 1000 = 2.2 -> 1.1 ms a frame.
        self.assertAlmostEqual(rows["aura: blit"][2], 1.1)
        # areas: only the first frame had any; the second counts as 0 ms.
        self.assertAlmostEqual(rows["areas, whole"][2], 0.05)
        self.assertEqual(rows["areas, whole"][1], 1.0)
        self.assertNotIn("statuses, whole", rows)                  # never sampled, no row

    def test_every_figure_of_the_printout(self):
        lines = UL.report(self.SHOTS).splitlines()
        self.assertEqual(lines[0], "  under leads, a mean over 2 fight frame(s): 150.0 auras, "
                                   "0.0 with a status (0.0 chilled, 0.0 burning), 1.0 tornadoes; "
                                   "3 rounds a frame")
        self.assertEqual(lines[1], "    candidate aura: blit, RLE copy      "
                                   "1.67 us an item  x  150.0  =  0.250 ms a frame")
        self.assertEqual(lines[2], "    auras, whole               11.33 us an item  x  150.0  "
                                   "=  1.700 ms a frame")
        self.assertEqual(lines[3], "      aura: blit                7.33 us an item  x  150.0  "
                                   "=  1.100 ms a frame    64.7 %")
        # The glue's "=" under the parts' "=".
        self.assertEqual(lines[4].index("="), lines[3].index("="))
        self.assertEqual(lines[4], "      (the glue)" + " " * 43 + "=  0.600 ms a frame")
        self.assertEqual(lines[5], "    statuses: nothing to draw")
        self.assertEqual(lines[6], "    areas, whole               50.00 us an item  x    1.0  "
                                   "=  0.050 ms a frame")
        self.assertEqual(lines[7], "      ring: blit               30.00 us an item  x    1.0  "
                                   "=  0.030 ms a frame    60.0 %")

    def test_the_command_line(self):
        a = UL.parse(["--live", "150", "--elapsed", "200"])
        self.assertEqual((a.seed, a.dormant, a.rounds, a.snapshots, a.gap), (SEED, 400, 50, 10, 30))
        for bad in (["--live", "1", "--elapsed", "0", "--rounds", "0"],
                    ["--live", "1", "--elapsed", "0", "--snapshots", "0"],
                    ["--live", "1", "--elapsed", "0", "--gap", "0"], ["--elapsed", "0"]):
            with self.subTest(argv=bad), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit):
                UL.parse(bad)


class SceneTests(unittest.TestCase):
    """One packed fight, seed 35, 60 alive, shared: every enemy primed."""

    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            cls.game, cls.ps = LP.packed_scene(SEED, 60, 0, 300.0, TDL._fresh_save(), elements=True)
        cls.surface = pygame.display.get_surface()

    def test_the_auras_are_the_bodies_the_pass_draws(self):
        from game.states.playing.visual.elements import layers
        run = self.ps.run
        drawn = []
        real = layers._aura

        def counted(surface, cam, body, profile, style):
            drawn.append(body)

        lists = UL.items(self.ps)
        with mock.patch.object(layers, "_aura", counted):
            n = layers.draw_auras(self.surface, run, run.element_visuals.profiles, run.stats["time"])
        self.assertIs(layers._aura, real)
        self.assertGreater(n, 0)
        self.assertEqual(lists["auras"], drawn)
        self.assertEqual(lists["areas"], [a for a in run.wind_areas
                                          if a.remaining(run.stats["time"]) > 0.0])

    def test_every_piece_runs_on_its_items_and_leaves_the_fight_as_it_was(self):
        lists = UL.items(self.ps)
        table = UL.pieces(self.ps, self.surface)
        self.assertEqual({p for p, _o, _f in table.values()},
                         {"auras", "statuses", "areas", "candidates"})
        before = UL.items(self.ps)
        clock = self.ps.run.stats["time"]
        for name, (_pass, over, fn) in table.items():
            with self.subTest(piece=name):
                its = lists[over]
                if name.endswith(", whole"):
                    fn(its)
                else:
                    for it in its:
                        fn(it)
        self.assertEqual(UL.items(self.ps), before)
        self.assertEqual(self.ps.run.stats["time"], clock)

    def test_the_fight_advances_between_snapshots_only(self):
        steps = []
        shots = UL.measure(self.ps, 2, snapshots=3, gap=7, advance=lambda p, n: steps.append(n))
        self.assertEqual(steps, [7, 7])
        self.assertEqual(len(shots), 3)
        for shot in shots:
            self.assertEqual(len(shot["samples"]["auras, whole"]), 2)       # one per round


class MainTests(unittest.TestCase):
    def test_end_to_end(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = UL.main(["--seed", str(SEED), "--live", "40", "--elapsed", "300", "--dormant", "0",
                            "--rounds", "2", "--snapshots", "2", "--gap", "2"],
                           save_path=TDL._fresh_save())
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("  under leads, a mean over 2 fight frame(s): ", text)
        self.assertRegex(text, r"    auras, whole +[\d.]+ us an item")
        self.assertIn("    candidate aura: blit, RLE copy", text)


if __name__ == "__main__":
    unittest.main()
