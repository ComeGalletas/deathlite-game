"""RND-010.2: the probes on the layer tool's own error
(`tools/benchmarks/layer_probes.py`, `crowd_draw_journal.md`).

What is pinned:
* **the printouts:** every figure of `bias` and `nested`, on made-up data
  where no column can stand in for another;
* **the rotation:** bare, every timer, all but the nested, the root alone,
  in turn, the first bare; the young garbage collected after every frame
  with no timer on; the timer taken off whatever frame the run stops on;
* **the probes on a real packed run** (seed 35): the frame counts of each
  kind, what each kind's timer wraps, and every attribute as it was after;
* **the command line.**
"""
import contextlib
import io
import unittest
from unittest import mock

from game import config
from tests.devtools import (
    test_draw_layers as TDL,  # an alias: its classes are not collected twice
)
from tools.benchmarks import draw_layers as DL
from tools.benchmarks import layer_probes as LP
from tools.benchmarks import spawn_stress as S

SEED = 35


class FormatTests(unittest.TestCase):
    def test_every_figure_of_the_bias_printout(self):
        # Plain [1, 3, 5]: p50 3; bare [2, 4, 6]: p50 4; per block
        # [-0.5, -0.25, 0, 0.5, 1.0]: p50 0, two of five slower (a tie
        # is not slower).
        text = LP.format_bias({"plain": [5.0, 1.0, 3.0], "bare": [4.0, 2.0, 6.0],
                               "diffs": [0.5, -0.25, 1.0, 0.0, -0.5]})
        self.assertEqual(text.splitlines(), [
            "  bias: 5 blocks; draw p50 plain 3.00 ms (3 frames), bare 4.00 ms (3 frames)",
            ("  per block, bare minus plain p50: p50 +0.00 ms, from -0.50 to +1.00; "
            "bare slower in 2 of 5")])

    def test_bias_pairs_each_block_bare_minus_plain_in_abba_order(self):
        # Block 1, plain first: plain [1, 1, 1], layered [3, 99, 3, 99]
        # (bare 0 and 2): +2. Block 2, layered first: bare [4, 4], plain
        # [5, 5, 5]: -1. The order alternates so a drift inside a block
        # falls on each side alike.
        alt = DL.Alternate(DL.LayerTimer(), ps=None)
        alt.bare, alt.timed = [0, 2], [1, 3]
        plains = iter([[1.0] * 3, [5.0] * 3])
        layered = iter([[3.0, 99.0, 3.0, 99.0], [4.0, 99.0, 4.0, 99.0]])
        order = []

        def run(ps, n, render):
            order.append(("plain", n))
            return None, next(plains), None

        def layered_run(ps, n):
            order.append(("layered", n))
            return None, next(layered), None, alt

        with mock.patch.object(S, "run", run), mock.patch.object(S, "layered_run", layered_run):
            result = LP.bias(object(), blocks=2, plain=3, layered=4)
        self.assertEqual(order, [("plain", 3), ("layered", 4), ("layered", 4), ("plain", 3)])
        self.assertEqual(result, {"plain": [1.0, 1.0, 1.0, 5.0, 5.0, 5.0],
                                  "bare": [3.0, 3.0, 4.0, 4.0], "diffs": [2.0, -1.0]})

    def test_nested_groups_the_draws_and_sums_the_enemies_rows(self):
        class _Rotate:
            def __init__(self, ps):
                self.kinds = ["bare", "all", "no_nested", "root", "bare"]
                self.timers = {
                    "all": mock.Mock(frames=[{"enemies": 1.0, "enemies/shade": 0.5,
                                              "enemies/marks": 0.25, "world": 0.2, "ground": 9.0}],
                                     **{"calls_per_frame.side_effect": {"enemies": 7.5}.get}),
                    "no_nested": mock.Mock(frames=[{"enemies": 1.25, "ground": 9.0}]),
                    "root": mock.Mock(frames=[{"draw": 12.0}])}

            def close(self):
                pass

        with mock.patch.object(LP, "Rotate", _Rotate), \
                mock.patch.object(S, "run", lambda ps, n, render, after_draw: (
                    None, [10.0, 15.0, 13.0, 11.0, 10.5], None)):
            result = LP.nested(object(), 5)
        self.assertEqual(result["draw"], {"bare": [10.0, 10.5], "all": [15.0],
                                          "no_nested": [13.0], "root": [11.0]})
        self.assertEqual(result["all_enemies"], [1.75])           # its nested rows in, ground out
        self.assertEqual(result["all_world"], [0.2])
        self.assertEqual(result["no_nested_enemies"], [1.25])
        self.assertEqual(result["no_nested_world"], [0.0])        # absent counts 0
        self.assertEqual(result["enemies_calls"], 7.5)            # the probe's own count

    def test_every_figure_of_the_nested_printout(self):
        text = LP.format_nested({
            "draw": {"bare": [10.0, 11.0, 12.0], "all": [14.0, 15.0, 16.0],
                     "no_nested": [13.0, 14.0, 12.0], "root": [11.5, 11.5, 11.5]},
            "all_enemies": [5.0, 6.0, 7.0], "all_world": [1.0, 2.0, 3.0],
            "no_nested_enemies": [4.0, 4.5, 5.0], "no_nested_world": [0.5, 1.0, 1.5],
            "enemies_calls": 4.0})
        self.assertEqual(text.splitlines(), [
            ("  nested: whole draw p50 by kind (3 frames each): bare 11.00, all timers 15.00, "
            "all but the nested 13.00, root alone 11.50 ms"),
            "    all timers           enemies with its nested rows p50 6.00 ms, world 2.00 ms",
            "    all but the nested   enemies with its nested rows p50 4.50 ms, world 1.00 ms",
            "  the nested wrappers add +2.00 ms to the whole draw, every timer +4.00 ms, at p50",
            # 6.00 - 4.50 = 1.50 ms over 4 enemies a frame: 375 us each.
            ("  and +1.50 ms to enemies with its nested rows: 4.0 enemies drawn a frame, "
             "+375.00 us an enemy")])


class RotateTests(unittest.TestCase):
    def test_the_kinds_in_turn_collected_with_no_timer_on(self):
        ps = object()
        rotate = LP.Rotate(ps)
        events = mock.Mock()
        for kind in ("all", "no_nested", "root"):
            timer = getattr(events, kind)
            timer.install.return_value = timer
            rotate.timers[kind] = timer
        with mock.patch.object(LP.gc, "collect", events.collect):
            for _ in range(5):
                rotate()
            rotate.close()
        self.assertEqual(rotate.kinds, ["bare", "all", "no_nested", "root", "bare"])
        c = mock.call
        self.assertEqual(events.mock_calls, [
            c.collect(0), c.all.install(ps),
            c.all.frame(), c.all.uninstall(), c.collect(0), c.no_nested.install(ps),
            c.no_nested.frame(), c.no_nested.uninstall(), c.collect(0), c.root.install(ps),
            c.root.frame(), c.root.uninstall(), c.collect(0),
            c.collect(0), c.all.install(ps),
            c.all.uninstall()])                            # close: off where the run stopped

    def test_what_each_kind_leaves_unwrapped(self):
        rotate = LP.Rotate(object())
        self.assertEqual(rotate.timers["all"].skip, frozenset())
        self.assertEqual(rotate.timers["no_nested"].skip, {"shade", "hpbar", "marks"})
        self.assertEqual(rotate.timers["root"].skip | {"draw"}, {label for label, *_ in DL.LAYERS})
        self.assertNotIn("draw", rotate.timers["root"].skip)


class PackedSceneTests(unittest.TestCase):
    def test_the_harness_pack_up_to_the_timing(self):
        # As `spawn_stress.main --pack`: built with the default LOD (the
        # boss held back by default), the shortfall said, 60 drawn frames,
        # then packed with nothing primed.
        calls = mock.Mock()
        ps = mock.Mock()
        calls.build.return_value = ("game", ps)
        calls.display_line.return_value = "display"
        calls.shortfall.return_value = "short"
        with mock.patch.multiple(S, build=calls.build, display_line=calls.display_line,
                                 shortfall=calls.shortfall, run=calls.run,
                                 cascade_setup=calls.cascade_setup), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(LP.packed_scene(7, 150, 400, 300.0, "s.json"), ("game", ps))
        c = mock.call
        self.assertEqual(calls.mock_calls, [
            c.build(7, 150, 400, 300.0, config.ENEMY_LOD_SKIP, save_path="s.json"),
            c.display_line(ps), c.shortfall(ps, 150, 300.0),
            c.run(ps, 60, render=True), c.cascade_setup(ps, prime=False)])
        self.assertEqual(out.getvalue(), "display\nshort\n")


class SceneTests(unittest.TestCase):
    """One packed scene, seed 35, 30 alive, shared; every test leaves its
    attributes as it found them."""

    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            cls.game, cls.ps = LP.packed_scene(SEED, 30, 0, 300.0, TDL._fresh_save())
        cls.printed = out.getvalue()
        cls.clean = TDL.WiringTests._attributes(cls.ps)

    def tearDown(self):
        self.assertEqual(TDL.WiringTests._attributes(self.ps), self.clean)

    def test_the_scene_prints_the_display_and_holds_the_boss(self):
        self.assertIn("boss held back", self.printed)
        self.assertEqual(self.printed.count("\n"), 1)          # the display line, no shortfall

    def test_bias_pairs_plain_and_layered_blocks(self):
        result = LP.bias(self.ps, blocks=2, plain=3, layered=4)
        self.assertEqual(len(result["plain"]), 6)
        self.assertEqual(len(result["bare"]), 4)               # frames 0 and 2 of each layered block
        self.assertEqual(len(result["diffs"]), 2)

    def test_nested_counts_each_kind(self):
        result = LP.nested(self.ps, 9)
        self.assertEqual({k: len(v) for k, v in result["draw"].items()},
                         {"bare": 3, "all": 2, "no_nested": 2, "root": 2})
        self.assertEqual(len(result["all_enemies"]), 2)
        self.assertTrue(all(v > 0 for v in result["all_enemies"]))
        self.assertGreater(result["enemies_calls"], 0)

    def test_each_kind_wraps_what_it_says(self):
        rotate = LP.Rotate(self.ps)
        try:
            S.run(self.ps, 4, render=True, after_draw=rotate)
        finally:
            rotate.close()
        self.assertIn("enemies/shade", rotate.timers["all"].frames[0])
        self.assertIn("enemies", rotate.timers["no_nested"].frames[0])
        self.assertFalse(any(k.startswith("enemies/") for k in rotate.timers["no_nested"].frames[0]))
        self.assertEqual(set(rotate.timers["root"].frames[0]), {"draw"})


class MainTests(unittest.TestCase):
    def test_nested_end_to_end(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = LP.main(["nested", "--seed", str(SEED), "--live", "30", "--elapsed", "300", "--dormant", "0",
                            "--frames", "4"], save_path=TDL._fresh_save())
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("  nested: whole draw p50 by kind (1 frames each)", text)
        self.assertTrue(text.rstrip().endswith("  boss at the end: held back"))

    def test_bias_end_to_end(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            LP.main(["bias", "--seed", str(SEED), "--live", "30", "--elapsed", "300", "--dormant", "0",
                     "--blocks", "2", "--plain", "2", "--layered", "2"], save_path=TDL._fresh_save())
        self.assertIn("  bias: 2 blocks; draw p50 plain", out.getvalue())


class CommandLineTests(unittest.TestCase):
    def _refused(self, argv):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            LP.parse(argv)
        self.assertEqual(cm.exception.code, 2)

    def test_defaults(self):
        a = LP.parse(["bias", "--live", "150", "--elapsed", "300"])
        self.assertEqual((a.seed, a.dormant, a.blocks, a.plain, a.layered), (SEED, 400, 16, 40, 80))
        b = LP.parse(["nested", "--live", "250", "--elapsed", "600"])
        self.assertEqual((b.dormant, b.frames), (400, 400))

    def test_refusals(self):
        self._refused([])
        self._refused(["bias", "--elapsed", "300"])                    # no --live
        self._refused(["bias", "--live", "150", "--elapsed", "300", "--layered", "1"])
        self._refused(["bias", "--live", "150", "--elapsed", "300", "--blocks", "0"])
        self._refused(["bias", "--live", "150", "--elapsed", "300", "--blocks", "3"])  # odd: no ABBA
        self._refused(["bias", "--live", "150", "--elapsed", "300", "--plain", "0"])
        self._refused(["nested", "--live", "150", "--elapsed", "300", "--frames", "3"])


if __name__ == "__main__":
    unittest.main()
