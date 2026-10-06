"""RND-010.3.3: the pieces of an enemy's draw, timed in isolation
(`tools/benchmarks/draw_leads.py`, `crowd_draw_journal.md`).

What is pinned:
* **the enemies:** the ones the probe times are exactly those the real
  draw runs `one_enemy`'s body for (in view, out of the spawn burst);
* **the pieces:** every one runs on every drawn enemy of a real packed
  scene (seed 35); the `world_to_screen` count matches a real pass and
  leaves the camera as it was;
* **the timing:** one sample per round per piece, the pieces' order
  rotated each round, each kind of piece run over its own enemies;
* **the arithmetic and the printout** on made-up samples;
* **the command line.**
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
from tools.benchmarks import draw_leads as DL
from tools.benchmarks import layer_probes as LP

SEED = 35


class ArithmeticTests(unittest.TestCase):
    RESULT: ClassVar[dict] = {
        # Skewed so the p50 is not the mean (whole: p50 11, mean 17; blit:
        # p50 6, mean 10; world_to_screen: p50 0.2, mean 0.4), and the parts
        # listed smallest first, so the printout's order is its own sort.
        "samples": {"ghost copy": [3.0], "world_to_screen": [0.9, 0.1, 0.2],
                    "one_enemy, whole": [30.0, 10.0, 11.0], "sprite blit": [4.0, 20.0, 6.0],
                    "scene: cull test": [0.5], "rig_frame": []},
        "per": {"one_enemy, whole": "enemy", "sprite blit": "enemy", "world_to_screen": "call",
                "ghost copy": "shaded", "scene: cull test": "live", "rig_frame": "enemy"},
        "enemies": 100, "shaded": 10, "live": 120, "w2s": 2.0}

    def test_calls_a_frame_by_kind(self):
        rows = DL.per_frame(self.RESULT)
        self.assertEqual(rows["one_enemy, whole"], (11.0, 100, 1.1))
        self.assertEqual(rows["sprite blit"], (6.0, 100, 0.6))
        self.assertAlmostEqual(rows["world_to_screen"][0], 0.2)
        self.assertEqual(rows["world_to_screen"][1], 200.0)          # 100 enemies x 2 calls
        self.assertEqual(rows["ghost copy"], (3.0, 10, 0.03))        # the shaded only
        self.assertEqual(rows["scene: cull test"], (0.5, 120, 0.06))  # every live enemy
        self.assertNotIn("rig_frame", rows)                          # no samples, no row

    def test_every_figure_of_the_printout(self):
        lines = DL.report(self.RESULT).splitlines()
        self.assertEqual(lines[0], "  draw leads: 120 alive, 100 drawn, 10 of them shaded, "
                                   "2.0 world_to_screen calls an enemy; 3 rounds")
        self.assertEqual(lines[1], "    one_enemy, whole           11.00 us a call  x  100.0  =   1.10 ms a frame")
        # The parts by ms a frame, largest first, with their share of the whole.
        self.assertEqual(lines[2], "    sprite blit                 6.00 us a call  x  100.0  =   0.60 ms a "
                                   "frame    54.5 % of the whole")
        self.assertTrue(lines[3].startswith("    world_to_screen             0.20 us a call  x  200.0  =   0.04"))
        self.assertTrue(lines[4].startswith("    ghost copy                  3.00 us a call  x   10.0  =   0.03"))
        # 1.10 - (0.60 + 0.04 + 0.03) = 0.43
        self.assertEqual(lines[5], "    (the glue between them)                              =   0.43 ms a frame")
        self.assertEqual(lines[6], "    scene: cull test            0.50 us a call  x  120.0  =   0.06 ms a frame")

    def test_the_command_line(self):
        a = DL.parse(["--live", "150", "--elapsed", "300"])
        self.assertEqual((a.seed, a.dormant, a.rounds), (SEED, 400, 200))
        for bad in ([], ["--live", "150", "--elapsed", "300", "--rounds", "0"]):
            with self.subTest(argv=bad), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit):
                DL.parse(bad)


class RotationTests(unittest.TestCase):
    def test_one_sample_a_round_and_the_order_rotated(self):
        order = []
        names = ("a", "b", "c")

        def table(ps, surface):
            return {n: ((lambda e, n=n: order.append(n)), "enemy") for n in names}

        ps = mock.Mock()
        ps.run.enemies = []
        with mock.patch.object(DL, "pieces", table), \
                mock.patch.object(DL, "drawn_enemies", lambda ps: ["e"]), \
                mock.patch.object(DL, "_shaded", lambda ps, e: False), \
                mock.patch.object(DL, "world_to_screen_calls", lambda ps, s: 2.0):
            result = DL.measure(ps, rounds=3)
        self.assertEqual(order, ["a", "b", "c", "b", "c", "a", "c", "a", "b"])
        self.assertEqual({n: len(v) for n, v in result["samples"].items()}, {"a": 3, "b": 3, "c": 3})


class SceneTests(unittest.TestCase):
    """One packed scene, seed 35, 40 alive, shared."""

    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            cls.game, cls.ps = LP.packed_scene(SEED, 40, 0, 300.0, TDL._fresh_save())
        cls.surface = pygame.display.get_surface()

    def test_an_enemy_still_in_its_spawn_burst_is_left_out(self):
        # The scene's bursts are over; one is put back on an enemy for the
        # test (index -1 is before any reveal frame).
        from types import SimpleNamespace
        e = DL.drawn_enemies(self.ps)[0]
        had = vars(e).get("_spawn_fx")
        e._spawn_fx = SimpleNamespace(finished=False, index=-1)
        try:
            self.assertNotIn(e, DL.drawn_enemies(self.ps))
        finally:
            e._spawn_fx = had
        self.assertIn(e, DL.drawn_enemies(self.ps))

    def test_the_enemies_are_those_the_draw_paints(self):
        ren = self.ps.renderer
        painted = []
        real = ren.spawn_veiled

        def veiled(e):
            out = real(e)
            if not out:
                painted.append(e)
            return out

        ren.spawn_veiled = veiled                 # one_enemy asks this first
        try:
            self.ps.draw(self.surface)
        finally:
            del ren.spawn_veiled
        self.assertEqual({id(e) for e in painted if e in self.ps.run.enemies},
                         {id(e) for e in DL.drawn_enemies(self.ps)})
        self.assertGreater(len(painted), 0)

    def test_every_piece_runs_on_every_drawn_enemy(self):
        table = DL.pieces(self.ps, self.surface)
        for name, (fn, _per) in table.items():
            with self.subTest(piece=name):
                for e in DL.drawn_enemies(self.ps):
                    fn(e)

    def test_world_to_screen_is_counted_and_the_camera_left_alone(self):
        cam = self.ps.run.camera
        calls = DL.world_to_screen_calls(self.ps, self.surface)
        self.assertNotIn("world_to_screen", vars(cam))
        # No fight here: one_enemy's own and blit_rig's, nothing hurt or marked.
        self.assertEqual(calls, 2.0)

    def test_a_short_measure(self):
        result = DL.measure(self.ps, rounds=2)
        self.assertEqual(result["enemies"], len(DL.drawn_enemies(self.ps)))
        self.assertEqual(result["live"], len(self.ps.run.enemies))
        for name, vals in result["samples"].items():
            per = result["per"][name]
            with self.subTest(piece=name):
                self.assertEqual(len(vals), 0 if per == "shaded" and not result["shaded"] else 2)


class MainTests(unittest.TestCase):
    def test_end_to_end(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = DL.main(["--seed", str(SEED), "--live", "30", "--elapsed", "300", "--dormant", "0",
                            "--rounds", "2"], save_path=TDL._fresh_save())
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("  draw leads: ", text)
        self.assertIn("    one_enemy, whole", text)
        self.assertTrue(text.rstrip().endswith("  boss at the end: held back"))


if __name__ == "__main__":
    unittest.main()
