"""RND-010.2: the draw timed layer by layer (`crowd_draw_journal.md`).

What is pinned:
* **the accounting:** each layer's time excludes the layers it calls, a
  nested layer is named under its caller (`enemies/shade`), the root and
  the world are left out of names, and a frame's parts add up to its whole;
  a layer that raises still closes its accounting;
* **the wiring:** on a real packed fight (seed 35) every layer's entry
  point is found, the picture is byte-identical with and without the
  timers, `uninstall` leaves every attribute as it was, the core layers are
  seen, the enemies' calls are the enemies drawn (that the parts add up
  to the whole is pinned on a made-up clock, never the wall clock);
* **alternation:** the timers on every other frame, the first bare, on a
  real run through `spawn_stress.layered_run`; the headline and the
  timers' cost read the bare frames only; `main --layers` prints it all;
* **the crowd:** the harness says when the director's cap, or the live cap
  behind it, refused part of the crowd asked for, and keeps the boss out
  of a late run clock unless `--boss` asks for it;
* **the villagers and huts:** their draw functions are timed on a real
  frame with them in view;
* **the command line:** `--layers` implies `--render`, needs two frames,
  and is refused with `--profile` and with `--bump`.
"""
import contextlib
import io
import unittest
from unittest import mock

import pygame

from game import config
from game.states.playing.visual.elements import layers as element_layers
from tools.benchmarks import draw_layers as DL
from tools.benchmarks import spawn_stress as S

SEED = 35


def _fresh_save() -> str:
    """A save of defaults, so the owner's own `save.json` (window size,
    tutorials) cannot reach a test. Its folder is removed at exit."""
    import atexit
    import os
    import shutil
    import tempfile

    from game import save as save_mod

    folder = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, folder, True)
    path = os.path.join(folder, "save.json")
    save_mod.save(save_mod.SaveData(), path)
    return path


# Every layer the tool times, pinned: a row dropped from `LAYERS` is a row
# the reports lose without a word.
EXPECTED_LAYERS = (
    "draw", "world", "water", "ground", "scenery", "villagers", "huts", "elemental_sort",
    "flat", "player_shots", "elemental", "enemies", "boss", "player", "summons", "death_fx",
    "spawn_fx", "shade", "hpbar", "marks", "ghost", "projectiles", "particles", "numbers",
    "reactions", "key_marker", "hints", "hud", "feedback")


class _Clock:
    """A `perf_counter` that returns the programmed seconds in turn."""

    def __init__(self, *ticks):
        self._ticks = iter(ticks)

    def __call__(self):
        return next(self._ticks)


def _picture(ps) -> bytes:
    """A frame of `ps`, with the aura shed (random) held still."""
    s = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    with mock.patch.object(element_layers, "_shed", lambda *a: None):
        ps.draw(s)
    return pygame.image.tobytes(s, "RGBA")


class LayerSetTests(unittest.TestCase):
    def test_the_layers_are_the_pinned_set(self):
        self.assertEqual(tuple(label for label, _where, _attr in DL.LAYERS), EXPECTED_LAYERS)
        self.assertEqual(DL.ITEMS, frozenset({"scenery", "villagers", "huts"}))

    def test_the_groups_are_the_journals(self):
        # The terrain and the crowd's part as `crowd_draw_journal.md`
        # defines them; a row dropped here would shift every group figure.
        self.assertEqual(DL.GROUPS, (
            ("terrain", ("ground", "water", "scenery", "scenery_list")),
            ("crowd", ("enemies", "enemies/shade", "ghost", "world"))))


class AccountingTests(unittest.TestCase):
    def _timer(self, *ticks):
        timer = DL.LayerTimer()
        return timer, mock.patch.object(DL.time, "perf_counter", _Clock(*ticks))

    def test_nested_layers_are_exclusive_and_named_under_their_caller(self):
        # draw [0, 10] > world [1, 9] > enemies [2, 8] > shade [3, 5]
        timer, clock = self._timer(0.0, 0.001, 0.002, 0.003, 0.005, 0.008, 0.009, 0.010)
        with clock:
            shade = timer._wrap("shade", lambda: None)
            enemies = timer._wrap("enemies", shade)
            world = timer._wrap("world", enemies)
            draw = timer._wrap("draw", world)
            draw()
        f = timer.frame()
        self.assertEqual(set(f), {"draw", "world", "enemies", "enemies/shade"})
        self.assertAlmostEqual(f["enemies/shade"], 2.0)
        self.assertAlmostEqual(f["enemies"], 4.0)            # 6 less the shade's 2
        self.assertAlmostEqual(f["world"], 2.0)              # 8 less the enemies' 6
        self.assertAlmostEqual(f["draw"], 2.0)               # 10 less the world's 8
        self.assertAlmostEqual(sum(f.values()), 10.0)        # the parts are the whole

    def test_a_layer_three_deep_is_named_under_its_caller_only(self):
        # draw > flat > elemental > particles reads `elemental/particles`.
        timer, clock = self._timer(0.0, 0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007)
        with clock:
            particles = timer._wrap("particles", lambda: None)
            elemental = timer._wrap("elemental", particles)
            flat = timer._wrap("flat", elemental)
            timer._wrap("draw", flat)()
        self.assertEqual(set(timer.frame()), {"draw", "flat", "flat/elemental", "elemental/particles"})

    def test_a_layer_called_straight_from_the_draw_keeps_its_own_name(self):
        timer, clock = self._timer(0.0, 0.001, 0.003, 0.004)
        with clock:
            shots = timer._wrap("projectiles", lambda: None)
            timer._wrap("draw", shots)()
        self.assertEqual(set(timer.frame()), {"draw", "projectiles"})

    def test_a_nested_layer_that_raises_inside_a_caught_block_is_still_counted(self):
        # The caller catches it and the frame goes on: the raise is part of
        # the frame, and its time is kept.
        timer, clock = self._timer(0.0, 0.001, 0.002, 0.003)

        def boom():
            raise ValueError("a painter fell over")

        def caller():
            with contextlib.suppress(ValueError):
                timer._wrap("enemies", boom)()

        with clock:
            timer._wrap("draw", caller)()
        f = timer.frame()                                     # nothing left open
        self.assertAlmostEqual(f["enemies"], 1.0)
        self.assertAlmostEqual(f["draw"], 2.0)

    def test_frame_inside_a_draw_is_refused(self):
        timer = DL.LayerTimer()
        with self.assertRaises(RuntimeError):
            timer._wrap("draw", timer.frame)()

    def test_the_summary_and_the_calls(self):
        timer = DL.LayerTimer()
        timer.frames = [{"a": 1.0, "b": 3.0}, {"a": 3.0}]
        timer.calls = [{"a": 2, "b": 1}, {"a": 4}]
        rows = {k: (p50, mean) for k, p50, _p90, mean in timer.summary()}
        self.assertEqual(rows["a"], (1.0, 2.0))               # index round(0.5) = 0, half to even
        self.assertEqual(rows["b"], (0.0, 1.5))               # absent from a frame counts 0
        self.assertEqual([k for k, *_ in timer.summary()], ["a", "b"])
        self.assertEqual(timer.totals(), [4.0, 3.0])
        self.assertEqual(timer.calls_per_frame("a"), 3.0)
        text = DL.format_layers(timer, bare=[2.0, 2.5])
        self.assertIn("draw by layer, exclusive ms over 2 timed frames", text)
        # Timed p50 3.0 (totals [3, 4]) against bare 2.0: +1.00 ms over
        # 3.5 calls a frame (2 of `a`, 1.5 of `b`).
        self.assertIn("the 2 frames between, drawn without the timers: draw p50 2.00 ms; "
                      "the timers add +1.00 ms at p50, 3.5 timed calls a frame, 285.71 us a call "
                      "in place", text)

    def test_every_row_and_column_of_the_printout(self):
        # Three frames, two layers; the bare frames [4, 5, 6] (p50 5).
        timer = DL.LayerTimer()
        timer.frames = [{"a": 1.0, "b": 2.0}, {"a": 3.0, "b": 2.0}, {"a": 7.0}]
        timer.calls = [{"a": 1, "b": 2}, {"a": 3, "b": 2}, {"a": 5}]
        lines = DL.format_layers(timer, bare=[6.0, 4.0, 5.0]).splitlines()
        # a: sorted [1, 3, 7]: p50 3, p90 7 (index round(1.8) = 2), mean
        # 11/3 = 3.67; share of the mean draw (totals [3, 5, 7], mean 5):
        # 73.3 %; calls 3 a frame. b: [0, 2, 2]: p50 2, p90 2, mean 4/3 =
        # 1.33, 26.7 %, calls 4/3 = 1.3.
        self.assertEqual(lines[1], "    a                        3.00 /   7.00 /   3.67    73.3 %       3.0")
        self.assertEqual(lines[2], "    b                        2.00 /   2.00 /   1.33    26.7 %       1.3")
        # Totals sorted [3, 5, 7]: p50 5, p90 7, mean 5: three different
        # columns, so none can stand in for another.
        self.assertEqual(lines[3], "    (all layers)             5.00 /   7.00 /   5.00")
        # No terrain or crowd rows here: the groups read zero (lines 4 to 6).
        self.assertEqual(lines[6], "    (crowd / terrain)       0.000 /  0.000            each frame's ratio")
        # Timed p50 5 against bare p50 5: +0.00 ms over 4.33 calls a frame.
        self.assertEqual(lines[7], "  the 3 frames between, drawn without the timers: draw p50 5.00 ms; "
                                   "the timers add +0.00 ms at p50, 4.3 timed calls a frame, 0.00 us a call "
                                   "in place")

    def test_the_groups_are_each_frames_sum_not_a_sum_of_p50s(self):
        # Terrain per frame: 1 + 1 = 2, 3.5, 2 + 2 = 4: p50 3.5, p90 4, mean
        # 3.17 (the rows' p50s would sum to 2). Crowd: 2 + 1 = 3, 1 + 1 = 2,
        # 5: p50 3, p90 5, mean 3.33 (the rows' p50s: 2). Each frame's
        # ratio: 1.5, 0.571, 1.25: p50 1.25, p90 1.5.
        timer = DL.LayerTimer()
        timer.frames = [{"ground": 1.0, "water": 1.0, "enemies": 2.0, "world": 1.0},
                        {"ground": 3.5, "enemies": 1.0, "enemies/shade": 1.0},
                        {"ground": 2.0, "scenery": 2.0, "enemies": 5.0}]
        timer.calls = [{}, {}, {}]
        self.assertEqual(DL.format_layers(timer).splitlines()[-3:], [
            "    (terrain)                3.50 /   4.00 /   3.17   each frame's sum",
            "    (crowd)                  3.00 /   5.00 /   3.33   each frame's sum",
            "    (crowd / terrain)       1.250 /  1.500            each frame's ratio"])

    def test_no_timed_frames_is_said_plainly(self):
        self.assertEqual(DL.format_layers(DL.LayerTimer(), bare=[1.0]),
                         "  draw by layer: no timed frames (--layers needs --frames 2 or more)")

    def test_an_items_entry_point_times_each_draw_function_it_returns(self):
        # The list is built [0, 0.5] ms; then draw [1, 5] > villager [2, 4].
        timer, clock = self._timer(0.0, 0.0005, 0.001, 0.002, 0.004, 0.005)
        drawn = []

        def items(view):
            return [(0, 1.0, lambda s: drawn.append(s))]

        with clock:
            listed = timer._wrap_items("villagers", items)("view")
            fn = listed[0][2]
            timer._wrap("draw", lambda: fn("surface"))()
        self.assertEqual(drawn, ["surface"])
        self.assertEqual(listed[0][:2], (0, 1.0))
        f = timer.frame()
        self.assertEqual(set(f), {"draw", "villagers", "villagers_list"})
        self.assertAlmostEqual(f["villagers_list"], 0.5)      # the list's own row
        self.assertAlmostEqual(f["villagers"], 2.0)
        self.assertAlmostEqual(f["draw"], 2.0)

    def test_a_draw_that_raises_leaves_no_partial_frame(self):
        timer, clock = self._timer(0.0, 0.001, 0.002, 0.003)

        def boom():
            raise ValueError("a painter fell over")

        with clock, self.assertRaises(ValueError):
            timer._wrap("draw", timer._wrap("enemies", boom))()
        self.assertEqual(timer.frame(), {})
        self.assertEqual(timer.calls[-1], {})


class RollbackTests(unittest.TestCase):
    """`install` and `uninstall` leave nothing half on, even when an
    attribute cannot be set or put back."""

    class _Plain:
        def draw(self):
            return "plain"

    class _ReadOnly:
        @property
        def draw(self):                      # no setter, no deleter
            return lambda: "read only"

    def test_an_install_that_cannot_set_an_attribute_undoes_the_rest(self):
        plain, stuck = self._Plain(), self._ReadOnly()
        timer = DL.LayerTimer()
        with mock.patch.object(DL.LayerTimer, "_targets", staticmethod(
                lambda ps: {"plain": plain, "stuck": stuck})), \
                mock.patch.object(DL, "LAYERS", (("a", "plain", "draw"), ("b", "stuck", "draw"))), \
                self.assertRaisesRegex(AttributeError, "setter"):
            timer.install(object())
        self.assertNotIn("draw", vars(plain))             # back to the class's own
        self.assertFalse(timer.installed)

    def test_uninstall_puts_back_the_rest_when_one_restore_fails(self):
        plain, stuck = self._Plain(), self._ReadOnly()
        plain.draw = lambda: "wrapped"
        timer = DL.LayerTimer()
        # Reversed on uninstall: `stuck` is tried first and fails.
        timer._undo = [(plain, "draw", False, None), (stuck, "draw", False, None)]
        with self.assertRaisesRegex(AttributeError, "deleter"):
            timer.uninstall()
        self.assertNotIn("draw", vars(plain))
        self.assertFalse(timer.installed)


class SkipTests(unittest.TestCase):
    def test_a_skipped_layer_is_left_unwrapped(self):
        # `layer_probes` leaves the nested timers off to cost them.
        a, b = RollbackTests._Plain(), RollbackTests._Plain()
        timer = DL.LayerTimer(skip={"b"})
        with mock.patch.object(DL.LayerTimer, "_targets", staticmethod(lambda ps: {"a": a, "b": b})), \
                mock.patch.object(DL, "LAYERS", (("a", "a", "draw"), ("b", "b", "draw"))):
            timer.install(object())
        try:
            self.assertIn("draw", vars(a))
            self.assertNotIn("draw", vars(b))
        finally:
            timer.uninstall()
        self.assertNotIn("draw", vars(a))


class BareFramesTests(unittest.TestCase):
    def test_the_bare_frames_of_each_list(self):
        alt = DL.Alternate(DL.LayerTimer(), ps=None)
        alt.bare, alt.timed = [0, 2], [1, 3]
        self.assertEqual(DL.bare_frames(alt, [10, 11, 12, 13], "abcd"),
                         [[10, 12], ["a", "c"]])


class HeadlineTests(unittest.TestCase):
    """`spawn_stress.draw_headline`: under `--layers`, the bare frames
    alone, each frame's update paired with its own draw."""

    def test_layers_reads_the_bare_frames_each_update_with_its_own_draw(self):
        alt = DL.Alternate(DL.LayerTimer(), ps=None)
        alt.bare, alt.timed = [0, 2], [1, 3]
        # Bare frames 0 and 2: updates 1 and 3, draws 10 and 12, in view 7 and 9;
        # the timed frames (1, 3) are far off, so taking them would show.
        lines = S.draw_headline([1.0, 50.0, 3.0, 50.0], [10.0, 90.0, 12.0, 90.0],
                                [7, 99, 9, 99], alt)
        self.assertEqual(lines[0], "  (the update line above: every frame; the lines below: the 2 frames "
                                   "drawn without the timers)")
        self.assertEqual(lines[1], "  draw   p50 10.00  p90 12.00  p99 12.00  max 12.00 ms  |  "
                                   "in view p50 7 max 9")
        # 1 + 10 = 11 and 3 + 12 = 15: an update paired with another
        # frame's draw would give 13s.
        self.assertEqual(lines[2], "  update + draw   p50 11.00  p90 15.00  p99 15.00  max 15.00 ms  |  "
                                   "over 16.67 ms: 0 / 2")

    def test_without_layers_every_frame(self):
        lines = S.draw_headline([1.0, 2.0], [10.0, 20.0], [5, 6])
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1], "  update + draw   p50 11.00  p90 22.00  p99 22.00  max 22.00 ms  |  "
                                   "over 16.67 ms: 1 / 2")


class AlternateTests(unittest.TestCase):
    def test_every_frames_garbage_is_collected_with_no_timer_on(self):
        # After both kinds alike, so neither kind of frame starts from a
        # different collector state: after a bare frame before the timers
        # go on, after a timed one once they are off.
        timer = DL.LayerTimer()
        events = mock.Mock()
        timer.install = mock.Mock(side_effect=lambda ps: (
            events.install(), timer._undo.append((None, "x", True, 0))))
        timer.uninstall = mock.Mock(side_effect=lambda: (events.uninstall(), timer._undo.clear()))
        timer.frame = mock.Mock()
        alt = DL.Alternate(timer, ps=object())
        with mock.patch.object(DL.gc, "collect", events.collect):
            alt()                                    # after a bare frame
            alt()                                    # after a timed frame
            alt()                                    # after a bare frame
        self.assertEqual(events.mock_calls, [
            mock.call.collect(0), mock.call.install(),
            mock.call.uninstall(), mock.call.collect(0),
            mock.call.collect(0), mock.call.install()])

    def test_the_timers_are_on_every_other_frame_the_first_bare(self):
        timer = DL.LayerTimer()
        timer.install = mock.Mock(side_effect=lambda ps: timer._undo.append((None, "x", True, 0)))
        timer.uninstall = mock.Mock(side_effect=timer._undo.clear)
        timer.frame = mock.Mock()
        alt = DL.Alternate(timer, ps=object())
        for _ in range(5):
            alt()
        self.assertEqual((alt.bare, alt.timed), ([0, 2, 4], [1, 3]))
        self.assertEqual(timer.frame.call_count, 2)
        self.assertTrue(timer.installed)                       # on for a sixth frame
        alt.close()
        self.assertFalse(timer.installed)


class WiringTests(unittest.TestCase):
    """One packed fight, seed 35, 60 alive, shared; the terrain's clock is
    pinned and the aura shed (random) held still, so a frame is a pure
    function of the state."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = S.build(SEED, 60, 0, 300.0, config.ENEMY_LOD_SKIP,
                                   save_path=_fresh_save())
        cls.ps.game_map.renderer.clock = lambda: 0.0
        S.run(cls.ps, 10)
        S.cascade_setup(cls.ps, prime=False)
        S.run(cls.ps, 90, render=True)             # past the spawn bursts: sprites, not veils
        assert not cls.ps.run.spawn_fx, "the crowd is still spawning"
        cls.clean = cls._attributes(cls.ps)        # before any test has installed a timer

    def tearDown(self):
        # Every test leaves the fight as it found it, so none leans on
        # another's uninstall.
        self.assertEqual(self._attributes(self.ps), self.clean)

    def _frame(self, timer=None):
        s = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        with mock.patch.object(element_layers, "_shed", lambda *a: None):
            self.ps.draw(s)
        if timer is not None:
            timer.frame()
        return pygame.image.tobytes(s, "RGBA")

    @staticmethod
    def _attributes(ps):
        targets = DL.LayerTimer._targets(ps)
        return {(where, attr): (attr in vars(targets[where]), vars(targets[where]).get(attr))
                for _label, where, attr in DL.LAYERS}

    def test_the_picture_is_the_same_with_and_without_the_timers(self):
        bare = self._frame()
        self.assertEqual(self._frame(), bare)                   # stable
        timer = DL.LayerTimer().install(self.ps)
        try:
            timed = self._frame(timer)
        finally:
            timer.uninstall()
        self.assertEqual(timed, bare)
        self.assertEqual(self._frame(), bare)                   # and after

    def test_no_timed_layer_runs_from_the_update(self):
        # Every row is inside the `draw` root: a wrapped entry point the
        # update called too would add time outside the draw and inflate
        # the totals without a word.
        timer = DL.LayerTimer().install(self.ps)
        try:
            with mock.patch.object(element_layers, "_shed", lambda *a: None):
                for _ in range(3):
                    self.ps.update(1 / 60)
            self.assertEqual(timer.frame(), {})
            self.assertEqual(timer.calls[-1], {})
        finally:
            timer.uninstall()

    def test_uninstall_leaves_every_attribute_as_it_was(self):
        timer = DL.LayerTimer().install(self.ps)
        self.assertNotEqual(self._attributes(self.ps), self.clean)
        with self.assertRaises(RuntimeError):
            timer.install(self.ps)
        timer.uninstall()
        self.assertEqual(self._attributes(self.ps), self.clean)
        # The painters and the terrain's passes are the classes' own again.
        for obj, attr in ((self.ps, "_draw_one_enemy"), (self.ps, "draw"),
                          (self.ps.game_map.renderer, "ghost_pass")):
            with self.subTest(attr=attr):
                self.assertNotIn(attr, vars(obj))

    def test_a_crowd_frame_shows_every_layer_it_always_calls(self):
        timer = DL.LayerTimer().install(self.ps)
        try:
            self.ps.draw(pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT)))
            f = timer.frame()
        finally:
            timer.uninstall()
        # Every layer a crowd frame calls whatever happens in it.
        for layer in ("draw", "world", "water", "ground", "scenery", "scenery_list", "flat",
                      "flat/player_shots", "flat/elemental", "elemental_sort", "enemies",
                      "enemies/shade", "enemies/hpbar", "enemies/marks", "player", "ghost",
                      "projectiles", "particles", "numbers", "reactions", "key_marker",
                      "hints", "hud", "feedback"):
            with self.subTest(layer=layer):
                self.assertIn(layer, f)

    def test_each_scenery_item_is_timed(self):
        r = self.ps.game_map.renderer
        items = len(r.banded_scenery(self.ps.camera))
        self.assertGreater(items, 10)
        timer = DL.LayerTimer().install(self.ps)
        try:
            self._frame(timer)
        finally:
            timer.uninstall()
        self.assertEqual(timer.calls[0]["scenery"], items)

    def test_the_scenes_other_actors_go_through_the_timed_painters(self):
        # Summons, death poofs and spawn bursts are drawn through the state's
        # forwarders, which the timer wraps: stood in the view, each is timed
        # under its own row, not folded into `world`.
        from types import SimpleNamespace

        from game.states.playing.visual import scene

        run = self.ps.run
        here = pygame.Vector2(self.ps.player.pos)
        body = SimpleNamespace(pos=here, flying=False)
        timer = DL.LayerTimer().install(self.ps)
        try:
            with mock.patch.object(run, "summons", [body]), \
                    mock.patch.object(run, "death_fx", [body]), \
                    mock.patch.object(run, "spawn_fx", [(None, body)]), \
                    mock.patch.object(self.ps.renderer, "one_summon", lambda s, b: None), \
                    mock.patch.object(self.ps.renderer, "death_fx", lambda s, b: None), \
                    mock.patch.object(self.ps.renderer, "spawn_fx", lambda s, b: None):
                surface = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
                for _level, _depth, fn in scene.actor_items(self.ps):
                    fn(surface)
            f = timer.frame()
        finally:
            timer.uninstall()
        for layer in ("summons", "death_fx", "spawn_fx"):
            with self.subTest(layer=layer):
                self.assertIn(layer, f)

    def test_an_install_that_fails_leaves_nothing_on(self):
        with mock.patch.object(DL, "LAYERS", DL.LAYERS + (("bogus", "ps", "no_such_attribute"),)), \
                self.assertRaises(AttributeError):
            DL.LayerTimer().install(self.ps)
        # tearDown: every attribute back as it was

    def test_a_real_draw_that_raises_drops_its_partial_frame(self):
        timer = DL.LayerTimer().install(self.ps)
        try:
            with mock.patch.object(self.ps.renderer, "one_enemy",
                                   side_effect=RuntimeError("a painter fell over")), \
                    self.assertRaises(RuntimeError):
                self._frame()
            self.assertEqual(timer.frame(), {})
        finally:
            timer.uninstall()

    def test_layered_run_alternates_on_a_real_run(self):
        times, draws, in_view, alt = S.layered_run(self.ps, 4, jitter=0.0)
        self.assertEqual((alt.bare, alt.timed), ([0, 2], [1, 3]))
        self.assertFalse(alt.timer.installed)
        self.assertEqual(len(alt.timer.frames), 2)
        self.assertEqual(len(times) == len(draws) == len(in_view) == 4, True)
        self.assertEqual(len(alt.timer.calls), len(alt.timed))
        # On the wall clock: each timed frame's parts fit inside the draw
        # `run` timed around them, so no bare frame's time leaked into a
        # timed one (a wrapper that cached work would show here).
        for total, i in zip(alt.timer.totals(), alt.timed, strict=True):
            with self.subTest(frame=i):
                self.assertLessEqual(total, draws[i])
                self.assertGreater(total, 0.0)

    def test_layered_run_forwards_its_jitter_pump_and_instruments(self):
        pump = mock.Mock()
        instruments = mock.Mock()
        with mock.patch.object(S, "run", wraps=S.run) as run:
            S.layered_run(self.ps, 2, jitter=30.0, pump=pump, instruments=instruments)
        kwargs = run.call_args.kwargs
        self.assertEqual((kwargs["jitter"], kwargs["pump"], kwargs["instruments"], kwargs["render"]),
                         (30.0, pump, instruments, True))
        self.assertEqual((pump.call_count, instruments.frame.call_count), (2, 2))

    def test_layered_run_takes_the_timers_off_when_the_run_raises(self):
        # The first frame is bare and installs the timers after its draw; the
        # second frame's update raises with them on. tearDown checks that
        # every attribute is back.
        with mock.patch.object(self.ps, "update",
                               side_effect=[None, RuntimeError("the run fell over")]), \
                self.assertRaises(RuntimeError):
            S.layered_run(self.ps, 4, jitter=0.0)

    def test_the_enemies_calls_are_the_enemies_drawn(self):
        pad = config.RENDER_ACTOR_CULL_PAD
        view = self.ps.camera.visible_rect().inflate(2 * pad, 2 * pad)
        drawn = sum(1 for e in self.ps.run.enemies if view.collidepoint(e.pos.x, e.pos.y))
        self.assertGreater(drawn, 30)
        timer = DL.LayerTimer().install(self.ps)
        try:
            self._frame(timer)
        finally:
            timer.uninstall()
        self.assertEqual(timer.calls[0]["enemies"], drawn)


class ShortfallTests(unittest.TestCase):
    """The harness says when the director's cap refused part of the crowd."""

    def _ps(self, alive: int, cap: int, most: int | None = None):
        from types import SimpleNamespace
        most = cap if most is None else most
        director = SimpleNamespace(enemy_count_cap=lambda elapsed: most if elapsed > 1e8 else cap)
        return SimpleNamespace(enemies=[object()] * alive,
                               spawn=SimpleNamespace(master=SimpleNamespace(director=director)))

    def test_nothing_to_say_when_the_crowd_is_whole(self):
        self.assertIsNone(S.shortfall(self._ps(200, 200), 200, 400.0))

    def test_the_live_cap_is_named_when_no_run_could_seat_it(self):
        self.assertEqual(S.shortfall(self._ps(250, 250, most=250), 300, 5000.0),
                         "  asked for 300 alive, built 250: the cap at 5000 s is 250; "
                         "the director seats no more than 250 (the live cap)")

    def test_both_caps_named_when_the_clock_still_holds_it_back(self):
        self.assertEqual(S.shortfall(self._ps(175, 175, most=250), 300, 300.0),
                         "  asked for 300 alive, built 175: the cap at 300 s is 175; "
                         "the director seats no more than 250 (the live cap); raise --elapsed to reach it")

    def test_the_cap_is_named_and_the_fix_given(self):
        self.assertEqual(S.shortfall(self._ps(175, 175, most=250), 250, 300.0),
                         "  asked for 250 alive, built 175: the cap at 300 s is 175; raise --elapsed")

    def test_a_shortfall_under_the_cap_says_it_was_not_the_cap(self):
        msg = S.shortfall(self._ps(240, 250, most=250), 250, 600.0)
        self.assertEqual(msg, "  asked for 250 alive, built 240: the cap at 600 s is 250, so not the "
                              "cap: placement found no room for the rest")


class ElementPathTests(unittest.TestCase):
    """The busy update `--cascade --element-rate` times: infused weapons, a
    primed packed crowd, the pump and the instruments, seed 35. No timed
    layer runs from it either, so the totals stay the draw's."""

    def test_no_timed_layer_runs_from_the_cascade_update(self):
        _game, ps = S.build(SEED, 30, 0, 300.0, config.ENEMY_LOD_SKIP, save_path=_fresh_save())
        S.infuse(ps, SEED)
        pump = S.element_pump(ps, 4, SEED)
        S.run(ps, 5, pump=pump)
        S.cascade_setup(ps)                                  # primed: reactions chain
        instruments = S.Instruments(ps)
        timer = DL.LayerTimer().install(ps)
        try:
            S.run(ps, 10, pump=pump, instruments=instruments)
            self.assertEqual(timer.frame(), {})
            self.assertEqual(timer.calls[-1], {})
        finally:
            timer.uninstall()
        self.assertGreater(sum(instruments.reactions), 0)    # the busy path really ran


class VillagersAndHutsTests(unittest.TestCase):
    """Seed 35's villagers, fish huts and boats, each brought into view by
    standing the hero on it; their draw functions are timed."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = S.build(SEED, 10, 0, 300.0, config.ENEMY_LOD_SKIP,
                                   save_path=_fresh_save())
        cls.ps.game_map.renderer.clock = lambda: 0.0

    def _frame_at(self, pos):
        """Stand the hero on `pos`; draw it bare and timed, check the two
        pictures are the same, and return the timed frame's calls."""
        self.ps.player.pos.update(pos)
        self.ps.camera.snap_to(self.ps.player.pos)   # the camera eases; snap it
        S.run(self.ps, 1, jitter=0.0)
        timer = DL.LayerTimer()
        bare = _picture(self.ps)
        timer.install(self.ps)
        try:
            timed = _picture(self.ps)
            timer.frame()
        finally:
            timer.uninstall()
        self.assertEqual(timed, bare)
        return timer.calls[0]

    def test_a_villager_in_view_is_timed(self):
        self.assertTrue(self.ps.npcs)
        calls = self._frame_at(self.ps.npcs[0].pos)
        self.assertGreaterEqual(calls.get("villagers", 0), 1)

    def test_a_fish_hut_in_view_is_timed(self):
        self.assertTrue(self.ps.fish_huts)
        calls = self._frame_at(self.ps.fish_huts[0].pos)
        self.assertGreaterEqual(calls.get("huts", 0), 1)


class BossTests(unittest.TestCase):
    """The big crowds need a late run clock, past the boss's time (570 s on
    normal): the harness holds the boss back unless asked. Seed 35."""

    def _built(self, elapsed: float = 600.0, **options):
        return S.build(SEED, 10, 0, elapsed, config.ENEMY_LOD_SKIP,
                       save_path=_fresh_save(), **options)[1]

    def _run_past_the_boss(self, **options):
        ps = self._built(**options)
        S.run(ps, 5, jitter=0.0)
        return ps

    def test_before_any_frame_the_line_says_when_it_is_due(self):
        self.assertIn("boss due now", S.display_line(self._built(boss=True)))
        self.assertIn("boss due at 570 s", S.display_line(self._built(300.0, boss=True)))
        self.assertIn("boss held back", S.display_line(self._built()))

    def test_the_boss_is_timed_under_its_own_row_and_drawn_the_same(self):
        ps = self._run_past_the_boss(boss=True)
        ps.game_map.renderer.clock = lambda: 0.0
        ps.player.pos.update(ps.run.boss.pos)
        ps.camera.snap_to(ps.player.pos)
        bare = _picture(ps)
        timer = DL.LayerTimer().install(ps)
        try:
            timed = _picture(ps)
            f = timer.frame()
        finally:
            timer.uninstall()
        self.assertIn("boss", f)
        self.assertEqual(timed, bare)

    def test_a_boss_that_came_and_went_is_beaten_not_due(self):
        ps = self._run_past_the_boss(boss=True)
        ps.run.boss = None                       # as the fight's end leaves it
        self.assertEqual(S.boss_state(ps), "beaten")

    def test_held_back_by_default(self):
        ps = self._run_past_the_boss()
        self.assertIsNone(ps.run.boss)
        self.assertIn("boss held back", S.display_line(ps))

    def test_let_in_when_asked(self):
        ps = self._run_past_the_boss(boss=True)
        self.assertIsNotNone(ps.run.boss)
        self.assertIn("boss fighting", S.display_line(ps))


class MainTests(unittest.TestCase):
    """`python -m tools.benchmarks.spawn_stress` itself, seed 35, on a save
    of defaults (`Game` reads `save.DEFAULT_PATH` when given none)."""

    def setUp(self):
        from game import save as save_mod
        patcher = mock.patch.object(save_mod, "DEFAULT_PATH", _fresh_save())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_layers_forwards_the_pump_and_the_instruments(self):
        # --element-rate makes a pump, --cascade the instruments; under
        # --layers both must reach the timed run.
        with mock.patch.object(S, "layered_run", wraps=S.layered_run) as layered, \
                contextlib.redirect_stdout(io.StringIO()):
            S.main(["--seed", str(SEED), "--live", "20", "--dormant", "0", "--frames", "2",
                    "--layers", "--cascade", "--element-rate", "2"])
        kwargs = layered.call_args.kwargs
        self.assertIsNotNone(kwargs["pump"])
        self.assertIsInstance(kwargs["instruments"], S.Instruments)

    def test_the_profile_path_reports_the_boss_after_timing_too(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            S.main(["--seed", str(SEED), "--live", "20", "--dormant", "0", "--frames", "2",
                    "--profile"])
        self.assertIn("  boss at the end of timing: held back", out.getvalue())

    def test_the_boss_is_reported_after_timing(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            S.main(["--seed", str(SEED), "--live", "20", "--elapsed", "600", "--boss",
                    "--dormant", "0", "--frames", "2"])
        text = out.getvalue()
        self.assertIn("boss due now", text)                       # before the frames
        self.assertIn("  boss at the end of timing: fighting", text)

    def test_both_caps_named_when_both_bind(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            S.main(["--seed", str(SEED), "--live", "300", "--elapsed", "300",
                    "--dormant", "0", "--frames", "1"])
        self.assertIn("  asked for 300 alive, built 175: the cap at 300 s is 175; the director "
                      "seats no more than 250 (the live cap); raise --elapsed to reach it",
                      out.getvalue())

    def test_layers_prints_the_breakdown_and_reads_the_bare_frames(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            S.main(["--seed", str(SEED), "--live", "40", "--pack", "--layers", "--frames", "4",
                    "--dormant", "0"])
        text = out.getvalue()
        self.assertIn("  (the update line above: every frame; the lines below: the 2 frames "
                      "drawn without the timers)", text)
        self.assertIn("over 16.67 ms: ", text)
        self.assertRegex(text, r"over 16\.67 ms: \d+ / 2\n")
        self.assertIn("draw by layer, exclusive ms over 2 timed frames", text)
        self.assertIn("the 2 frames between, drawn without the timers", text)

    def test_the_harness_prints_the_shortfall(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            S.main(["--seed", str(SEED), "--live", "120", "--elapsed", "0", "--dormant", "0",
                    "--frames", "1"])
        self.assertIn("  asked for 120 alive, built 100: the cap at 0 s is 100; raise --elapsed",
                      out.getvalue())


class CommandLineTests(unittest.TestCase):
    def test_layers_implies_render(self):
        args = S.parse(["--layers"])
        self.assertTrue(args.layers and args.render)
        self.assertFalse(S.parse([]).layers)

    def test_the_boss_flag_reaches_build(self):
        self.assertTrue(S.build_options(S.parse(["--boss"]))["boss"])
        self.assertFalse(S.build_options(S.parse([]))["boss"])

    def test_layers_needs_two_frames(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            S.parse(["--layers", "--frames", "1"])
        self.assertIn("--frames must be at least 2", err.getvalue().strip().splitlines()[-1])

    def test_layers_is_refused_with_profile_and_with_bump(self):
        for argv, why in ((["--layers", "--profile"], "drop --profile"),
                          (["--bump", "--layers"], "drop --layers")):
            with self.subTest(argv=argv):
                err = io.StringIO()
                with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
                    S.parse(argv)
                self.assertEqual(cm.exception.code, 2)
                # The error line itself, not the usage line above it, which
                # names every flag.
                error = err.getvalue().strip().splitlines()[-1]
                self.assertIn(why, error)


if __name__ == "__main__":
    unittest.main()
