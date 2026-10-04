"""RND-010.3.2: the crowd performance plan's two appendix probes under
`tools/benchmarks/` (`crowd_draw_journal.md`).

What is pinned:
* **blit_floor:** the command line, the seeded crowd, one time per frame,
  the printed line on made-up times, and a whole run's rows;
* **gc_probe:** the collection hook records each collection's frame and
  generation and always comes off; the frozen mode puts the collector's
  thresholds and freeze back; a real run (seed 35) is timed frame by frame;
  the printed line; the command line.
"""
import contextlib
import gc
import io
import unittest

from tests.devtools import (
    test_draw_layers as TDL,  # an alias: its classes are not collected twice
)
from tools.benchmarks import blit_floor as BF
from tools.benchmarks import gc_probe as GP

SEED = 35


class BlitFloorTests(unittest.TestCase):
    def test_the_command_line(self):
        a = BF.parse([])
        self.assertEqual((a.sizes, a.counts, a.frames), ([(1600, 900), (2560, 1080)], [100, 200, 300], 120))
        b = BF.parse(["--sizes", "640x360", "--counts", "5,7", "--frames", "2"])
        self.assertEqual((b.sizes, b.counts, b.frames), ([(640, 360)], [5, 7], 2))
        for bad in (["--sizes", "640"], ["--counts", "x"], ["--frames", "0"], ["--counts", "0"]):
            with self.subTest(argv=bad), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit):
                BF.parse(bad)

    def test_the_crowd_is_seeded_and_on_the_surface(self):
        a, b = BF.positions(50, 640, 360), BF.positions(50, 640, 360)
        self.assertEqual(a, b)
        self.assertTrue(all(0 <= x < 640 and 0 <= y < 360 for x, y in a))

    def test_every_figure_of_a_line(self):
        # Sorted [1, 2, 3, 4, 9]: p50 index 2 = 3, p90 index round(3.6) = 4 -> 9.
        self.assertEqual(BF.line(640, 360, 7, True, [9.0, 1.0, 4.0, 2.0, 3.0]),
                         "640x360  n=  7  sprite+shadow+bar   p50   3.00  p90   9.00 ms")
        self.assertIn("sprite only", BF.line(640, 360, 7, False, [1.0]))

    def test_a_run_prints_both_rows_for_each_size_and_count(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(BF.main(["--sizes", "320x180", "--counts", "3,4", "--frames", "2"]), 0)
        lines = out.getvalue().splitlines()
        self.assertEqual([ln.split("  p50")[0] for ln in lines], [
            "320x180  n=  3  sprite only       ", "320x180  n=  3  sprite+shadow+bar ",
            "320x180  n=  4  sprite only       ", "320x180  n=  4  sprite+shadow+bar "])

    def test_one_time_per_frame(self):
        import pygame
        pygame.init()
        screen = pygame.display.set_mode((320, 180))
        sprite, shadow, bar = BF.props()
        self.assertEqual(sprite.get_size(), (BF.SPRITE_PX, BF.SPRITE_PX))
        times = BF.frame_times(screen, sprite, shadow, bar, BF.positions(5, 320, 180), 4, True)
        self.assertEqual(len(times), 4)
        self.assertTrue(all(t >= 0 for t in times))


class CollectorTests(unittest.TestCase):
    def test_each_collection_is_recorded_with_its_frame_and_generation(self):
        before = list(gc.callbacks)
        with GP.collections() as (events, at):
            at[0] = 7
            gc.collect(1)
        self.assertEqual(gc.callbacks, before)                 # the hook came off
        self.assertEqual([(f, g) for f, g, _ms in events], [(7, 1)])
        self.assertGreaterEqual(events[0][2], 0.0)

    def test_the_hook_comes_off_on_a_raise(self):
        before = list(gc.callbacks)
        with self.assertRaises(RuntimeError), GP.collections():
            raise RuntimeError("a frame fell over")
        self.assertEqual(gc.callbacks, before)

    def test_frozen_puts_the_collector_back(self):
        before = gc.get_threshold()
        with GP.frozen():
            self.assertEqual(gc.get_threshold(), GP.FROZEN_THRESHOLDS)
            self.assertGreater(gc.get_freeze_count(), 0)
        self.assertEqual(gc.get_threshold(), before)
        self.assertEqual(gc.get_freeze_count(), 0)
        with self.assertRaises(RuntimeError), GP.frozen():
            raise RuntimeError("a run fell over")
        self.assertEqual((gc.get_threshold(), gc.get_freeze_count()), (before, 0))

    def test_every_figure_of_the_report(self):
        result = {"times": [5.0, 1.0, 3.0], "counts": [4, 1, 0], "ms": [0.44, 0.06, 0.0]}
        # Sorted [1, 3, 5]: p50 3, p99 index round(1.98) = 2 -> 5, max 5.
        self.assertEqual(GP.report("default collector", 20, result),
                         "default collector: live 20  p50 3.00  p99 5.00  max 5.00 ms  |  "
                         "collections gen0/1/2 [4, 1, 0], summed ms [0.4, 0.1, 0.0]")

    def test_the_command_line(self):
        a = GP.parse([])
        self.assertEqual((a.seed, a.live, a.elapsed, a.frames, a.pack), (SEED, 200, 400.0, 600, False))
        for bad in (["--frames", "0"], ["--live", "0"]):
            with self.subTest(argv=bad), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit):
                GP.parse(bad)


class GcRunTests(unittest.TestCase):
    """Real runs, seed 35, a small crowd."""

    def test_a_run_is_timed_frame_by_frame_and_the_hero_put_back(self):
        args = GP.parse(["--live", "20", "--elapsed", "300", "--frames", "5"])
        with contextlib.redirect_stdout(io.StringIO()):
            ps = GP.scene(args, TDL._fresh_save())
        home = ps.player.pos.copy()
        result = GP.measure(ps, 5, warm=2)
        self.assertEqual(len(result["times"]), 5)
        self.assertEqual(len(result["counts"]), 3)
        self.assertEqual(ps.player.pos, home)

    def test_main_reports_both_modes(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            GP.main(["--live", "20", "--elapsed", "300", "--frames", "3"], save_path=TDL._fresh_save())
        lines = out.getvalue().splitlines()
        self.assertEqual([ln.split(":")[0] for ln in lines],
                         ["default collector", "frozen, thresholds (700, 10, 1000)"])


if __name__ == "__main__":
    unittest.main()
