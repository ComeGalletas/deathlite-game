"""RND-010.3.4: throwaway variants of the draw, checked pixel-identical and
timed against it (`tools/benchmarks/draw_variants.py`, `crowd_draw_journal.md`).

What is pinned:
* **exactness:** every variant draws a seed-35 packed frame byte for byte
  as the draw does; `rig_frame_cached` returns the very frame object the
  original does for every drawn enemy across a sweep of animation times;
* **the check itself:** a variant that changes a pixel is caught, and a
  scene that moves between draws is refused rather than compared;
* **undo:** nothing a variant patched is left behind;
* **the timing:** ABBA order, the hero on its anchor, the variant on only
  in its own parts;
* **the printout and the command line.**
"""
import contextlib
import io
import unittest
from unittest import mock

import pygame

from tests.devtools import (
    test_draw_layers as TDL,  # an alias: its classes are not collected twice
)
from tools.benchmarks import draw_leads as DLe
from tools.benchmarks import draw_variants as DV
from tools.benchmarks import layer_probes as LP

SEED = 35


class FormatTests(unittest.TestCase):
    def test_every_figure_of_the_printout(self):
        result = {"off": [5.0, 1.0, 3.0], "on": [4.0, 2.0, 2.5],
                  "diffs": [float(i) - 8 for i in range(16)]}
        # off p50 3, on p50 2.5; diffs -8 .. +7: p50 index round(7.5) = 8 -> 0, the
        # 4th smallest -5 and the 4th largest +4.
        self.assertEqual(DV.format_timed("x", result).splitlines(), [
            ("  x: draw p50 off 3.00 ms, on 2.50 ms (3 frames each); per block, on minus off p50: "
             "p50 +0.00 ms, from -8.00 to +7.00"),
            ("    the median saving lies in -5.00 to +4.00 ms (97.9 % sign-test interval; "
             "negative is faster)")])
        short = DV.format_timed("x", {"off": [1.0], "on": [1.0], "diffs": [0.0, 0.1]})
        self.assertTrue(short.endswith("    too few blocks for a sign-test interval on the median"))

    def test_the_command_line(self):
        a = DV.parse(["--live", "150", "--elapsed", "300"])
        self.assertEqual((a.seed, a.dormant, a.variants, a.blocks, a.frames),
                         (SEED, 400, list(DV.VARIANTS), 16, 40))
        self.assertEqual(DV.parse(["--live", "1", "--elapsed", "0", "--variants",
                                   "world_bucketed"]).variants, ["world_bucketed"])
        for bad in (["--live", "1", "--elapsed", "0", "--variants", "nope"],
                    ["--live", "1", "--elapsed", "0", "--variants", ","],
                    ["--live", "1", "--elapsed", "0", "--blocks", "3"],
                    ["--live", "1", "--elapsed", "0", "--frames", "0"]):
            with self.subTest(argv=bad), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit):
                DV.parse(bad)


class TimingTests(unittest.TestCase):
    def test_abba_on_its_anchor_the_variant_on_only_in_its_parts(self):
        ps = mock.Mock()
        ps.player.pos = pygame.Vector2(10.0, 20.0)
        state = {"on": False}
        log = []

        def variant(ps_):
            state["on"] = True
            return lambda: state.update(on=False)

        def run(ps_, n, render):
            log.append((state["on"], tuple(ps_.player.pos)))
            ps_.player.pos += (5.0, 5.0)                   # the jitter leaves it elsewhere
            return None, [2.0 if state["on"] else 3.0] * n, None

        with mock.patch.dict(DV.VARIANTS, {"probe": variant}), mock.patch.object(DV.S, "run", run):
            result = DV.timed(ps, "probe", blocks=2, frames=3)
        home = (10.0, 20.0)
        self.assertEqual(log, [(False, home), (True, home), (True, home), (False, home)])
        self.assertFalse(state["on"])
        self.assertEqual(tuple(ps.player.pos), home)
        self.assertEqual(result["diffs"], [-1.0, -1.0])
        self.assertEqual((len(result["off"]), len(result["on"])), (6, 6))


class SceneTests(unittest.TestCase):
    """One packed scene, seed 35, 40 alive, shared."""

    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            cls.game, cls.ps = LP.packed_scene(SEED, 40, 0, 300.0, TDL._fresh_save())
        cls.surface = pygame.display.get_surface()

    def _patched_state(self):
        from game.states.playing.visual import scene
        return (dict(vars(self.ps)).keys(), dict(vars(self.ps.renderer)).keys(), scene.draw_world)

    def test_every_variant_draws_the_same_frame(self):
        for name in DV.VARIANTS:
            with self.subTest(variant=name):
                before = self._patched_state()
                self.assertTrue(DV.identical(self.ps, name, self.surface))
                self.assertEqual(self._patched_state(), before)       # undone

    def test_a_variant_that_changes_a_pixel_is_caught(self):
        def blot(ps):
            real = ps.renderer.one_enemy

            def one_enemy(surface, e):
                real(surface, e)
                surface.set_at((0, 0), (255, 0, 255, 255))
            ps.renderer.one_enemy = one_enemy
            return lambda: delattr(ps.renderer, "one_enemy")

        with mock.patch.dict(DV.VARIANTS, {"blot": blot}):
            self.assertFalse(DV.identical(self.ps, "blot", self.surface))
        self.assertNotIn("one_enemy", vars(self.ps.renderer))

    def test_a_scene_that_moves_is_refused(self):
        frames = iter([b"a", b"a", b"b"])
        with mock.patch.object(DV, "picture", lambda ps, s: next(frames)), \
                self.assertRaisesRegex(RuntimeError, "moved"):
            DV.identical(self.ps, "forwarder_bypassed", self.surface)
        self.assertNotIn("_draw_one_enemy", vars(self.ps))
        self.assertIsNone(self.ps.game_map.renderer.clock)          # the clock put back

    def test_rig_frame_cached_returns_the_same_frame_object(self):
        ren, z = self.ps.renderer, self.ps.camera.zoom
        enemies = DLe.drawn_enemies(self.ps)
        undo = DV.VARIANTS["rig_frame_cached"](self.ps)
        try:
            cached = ren.rig_frame
        finally:
            undo()
        original = ren.rig_frame
        assets = self.ps.game.assets
        checked, one_shots = 0, 0
        for e in {e.anim.rig: e for e in enemies}.values():       # one enemy per rig
            t, name = e.anim.t, e.anim.anim
            try:
                # Every animation of the rig, not only what it plays now:
                # loops wrap and one-shots clamp, both over 0 to 3.9 s.
                for anim_name, spec in assets.meta[e.anim.rig]["anims"].items():
                    e.anim.anim = anim_name
                    one_shots += not spec.get("loop", False)
                    for step in range(40):
                        e.anim.t = step * 0.1
                        for face in (-1, 1):
                            a, b = original(e.anim, face, z), cached(e.anim, face, z)
                            self.assertIs(a[0], b[0])
                            self.assertEqual(a[1], b[1])
                            checked += 1
            finally:
                e.anim.t, e.anim.anim = t, name
        self.assertGreater(checked, 0)
        self.assertGreater(one_shots, 0)

    def test_world_bucketed_paints_in_the_original_order_even_on_ties(self):
        # Scenery and actors tied on level and depth: the original's lists
        # and stable sort paint the scenery's first; so must the variant.
        from game.states.playing.visual import elements as element_fx
        from game.states.playing.visual import scene

        def run(draw_world):
            painted = []
            item = lambda tag: (lambda s: painted.append(tag))
            r = mock.Mock()
            r.banded_scenery.return_value = [(1, 5.0, item("tree")), (0, 2.0, item("rock")),
                                             (1, 3.0, item("bush"))]
            r.ground_levels.return_value = [0, 1, 2]
            ps = mock.Mock()
            ps.game_map.renderer = r
            with mock.patch.object(scene, "actor_items", lambda ps_: [
                        (1, 5.0, item("enemy")), (0, 2.0, item("hero")), (2, 1.0, item("bat"))]), \
                    mock.patch.object(scene, "draw_flat_effects", lambda *a: painted.append("flat")), \
                    mock.patch.object(element_fx, "bands", lambda run: None):
                draw_world(ps, None)
            return painted

        original = scene.draw_world
        expected = run(original)
        undo = DV.VARIANTS["world_bucketed"](self.ps)
        try:
            got = run(scene.draw_world)
        finally:
            undo()
        self.assertIs(scene.draw_world, original)
        self.assertEqual(expected, ["flat", "rock", "hero", "flat", "bush", "tree", "enemy",
                                    "flat", "bat"])
        self.assertEqual(got, expected)


class MainTests(unittest.TestCase):
    def test_end_to_end(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = DV.main(["--seed", str(SEED), "--live", "30", "--elapsed", "300", "--dormant", "0",
                            "--blocks", "2", "--frames", "2"], save_path=TDL._fresh_save())
        self.assertEqual(code, 0)
        text = out.getvalue()
        for name in DV.VARIANTS:
            with self.subTest(variant=name):
                self.assertIn(f"  {name}: draw p50 off", text)
        self.assertTrue(text.rstrip().endswith("  boss at the end: held back"))

    def test_a_differing_variant_is_reported_and_not_timed(self):
        with mock.patch.object(DV, "identical", lambda ps, name, s: name != "world_bucketed"), \
                mock.patch.object(DV, "timed", lambda ps, name, b, f: {
                    "off": [1.0], "on": [1.0], "diffs": [0.0, 0.0]}), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            DV.main(["--seed", str(SEED), "--live", "30", "--elapsed", "300", "--dormant", "0"],
                    save_path=TDL._fresh_save())
        text = out.getvalue()
        self.assertIn("  world_bucketed: the frame differs with it on; not timed", text)
        self.assertNotIn("  world_bucketed: draw p50", text)
        self.assertIn("  rig_frame_cached: draw p50", text)


if __name__ == "__main__":
    unittest.main()
