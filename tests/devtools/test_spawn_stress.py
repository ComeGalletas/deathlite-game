"""RND-008.2: the crowd stress harness measures play, not the run's opening
(`frame_time_journal.md`).

What is pinned: the opening hints are dismissed unless asked for, `--hints`
shows them even with the Options "Tutorials" row off, and a kept hint never
clears under the harness's jitter (why they are dismissed); the master stays
frozen through the timed frames, with nothing in flight, while
`live_director` still lets companies in (the control that shows the freeze
is what keeps them out); the isolated bump pass does the same work every
pass, meets real pairs and never the parked hero, and leaves the run as it
found it; one budget counts the frames over it; and each command-line flag
reaches `build` on its own.

No timing is asserted: a timing assertion would only ever be flaky. The
numbers live in the journal. Runs are booted on seed 35, the harness's
default and the journal's, each on a fresh save so the owner's settings
cannot reach the tests.
"""
import contextlib
import inspect
import io
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config, save as save_mod
from tests import boot
from tools.benchmarks import spawn_stress as S

SEED = 35
# Long enough that a live director seats at least one company from seed 35
# at the harness's 300 s (it seated 17 bodies in 300 frames when measured).
FRAMES = 300


def _fresh_save(**settings) -> str:
    path = os.path.join(tempfile.mkdtemp(), "save.json")
    data = save_mod.SaveData()
    data.settings.update(settings)
    save_mod.save(data, path)
    return path


def _build(**kw):
    kw.setdefault("save_path", _fresh_save())
    return S.build(SEED, 30, 0, 300.0, config.ENEMY_LOD_SKIP, **kw)


class HarnessDefaultsTests(unittest.TestCase):
    """A default build: hints off, director frozen.

    One run is shared. The bump test packs the crowd round the hero, so
    every other test reads what `setUpClass` recorded before it, or
    settings the packing does not touch."""

    @classmethod
    def setUpClass(cls):
        # Seed 35 happens to have no company in flight when the harness
        # freezes the master, so one is put in the air: a body due long
        # after the timed frames, which only `drop_pending` removes.
        real_settle = boot.settle

        def settle_mid_arrival(game):
            ps = real_settle(game)
            p = ps.player.pos
            ps.spawn.master._pending.append(
                (1.0e9, "bear", p.x + 200.0, p.y, "director", None))
            return ps

        with mock.patch.object(boot, "settle", settle_mid_arrival):
            cls.game, cls.ps = _build()
        cls.pending_after_build = len(cls.ps.spawn.master._pending)
        cls.before = list(cls.ps.enemies)
        S.run(cls.ps, FRAMES)
        cls.came = S.arrivals(cls.ps, cls.before)

    def test_the_opening_hints_are_dismissed(self):
        # Enabled (the fresh save has Tutorials on) and not shown: they
        # were dismissed, not switched off.
        self.assertTrue(self.ps.hints.enabled)
        self.assertFalse(self.ps.hints.visible)

    def test_the_master_stays_frozen_through_the_timed_frames(self):
        self.assertTrue(self.ps.spawn.master.frozen)

    def test_no_company_is_left_in_flight(self):
        self.assertEqual(self.pending_after_build, 0)

    def test_the_director_adds_no_one(self):
        self.assertNotIn("director", self.came, self.came)

    def test_the_display_line_names_the_settings(self):
        line = S.display_line(self.ps)
        self.assertIn("hints off", line)
        self.assertIn("director frozen", line)
        self.assertIn(f"budget {S.BUDGET_MS:.2f} ms", line)
        self.assertIn(f"zoom {config.effective_zoom():.3f}", line)

    def test_the_bump_pass_repeats_the_same_work_and_leaves_the_run_as_found(self):
        ps = self.ps
        S.cascade_setup(ps, prime=False)
        hero = ps.player.pos.copy()
        spots = [e.pos.copy() for e in ps.enemies]
        knocks = [e._knock.copy() for e in ps.enemies]
        pushed = []                  # per pass: bodies shoved, total impulse added
        hero_met = []
        real_resolve, real_bump = ps.bump.resolve, ps.bump._bump

        def resolve():
            real_resolve()
            added = [(e._knock - k).length() for e, k in zip(ps.enemies, knocks)]
            pushed.append((sum(1 for a in added if a > 0.0), round(sum(added), 6)))

        def bump(a, b, **kw):
            if ps.player in (a, b):
                hero_met.append((a, b))
            return real_bump(a, b, **kw)

        ps.bump.resolve, ps.bump._bump = resolve, bump
        try:
            times = S.bump_times(ps, 5)
        finally:
            del ps.bump.resolve, ps.bump._bump
        self.assertEqual(len(times), 5)
        self.assertGreater(pushed[0][0], 0, "the packed crowd shoved no one")
        # The impulses go back after every pass, so each pass meets the
        # same crowd: without that they pile up and later passes differ.
        self.assertEqual(pushed, [pushed[0]] * 5)
        self.assertEqual(hero_met, [])
        self.assertEqual(ps.player.pos, hero)
        self.assertEqual([e.pos for e in ps.enemies], spots)
        self.assertEqual([e._knock for e in ps.enemies], knocks)


class LiveDirectorTests(unittest.TestCase):
    """`hints=True, live_director=True`, on a save with Tutorials off: the
    behaviour before RND-008, whatever the Options say."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = _build(hints=True, live_director=True,
                                  save_path=_fresh_save(tutorials=False))
        before = list(cls.ps.enemies)
        S.run(cls.ps, FRAMES)
        cls.came = S.arrivals(cls.ps, before)

    def test_the_director_adds_companies(self):
        self.assertFalse(self.ps.spawn.master.frozen)
        self.assertGreater(self.came.get("director", 0), 0, self.came)

    def test_the_hints_show_with_tutorials_off_and_the_setting_is_kept(self):
        self.assertFalse(self.game.tutorials)
        self.assertTrue(self.ps.hints.enabled)

    def test_a_kept_hint_never_clears_under_the_jitter(self):
        # The hero never gets 96 px from the spawn, so the Move stage holds
        # for every frame: the cost the first findings report measured.
        jitter = inspect.signature(S.run).parameters["jitter"].default
        self.assertLess(jitter, config.HINT_MOVE_DISTANCE)
        self.assertEqual(self.ps.hints.stage, "move")


class _Stop(Exception):
    pass


class FlagPlumbingTests(unittest.TestCase):
    """Each flag reaches `build` on its own; nothing is booted."""

    def _build_kwargs(self, *flags):
        seen = {}

        def fake_build(*_a, **kw):
            seen.update(kw)
            raise _Stop

        with mock.patch.object(S, "build", fake_build):
            with self.assertRaises(_Stop):
                S.main(["--frames", "1", *flags])
        return seen

    def test_no_flags_mean_hints_off_and_the_director_frozen(self):
        kw = self._build_kwargs()
        self.assertFalse(kw["hints"])
        self.assertFalse(kw["live_director"])

    def test_hints_alone(self):
        kw = self._build_kwargs("--hints")
        self.assertTrue(kw["hints"])
        self.assertFalse(kw["live_director"])

    def test_live_director_alone(self):
        kw = self._build_kwargs("--live-director")
        self.assertFalse(kw["hints"])
        self.assertTrue(kw["live_director"])

    def test_bump_refuses_the_flags_it_would_ignore_or_distort(self):
        for flag in ("--render", "--profile", "--elements", "--cascade"):
            with self.subTest(flag=flag), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    S.main(["--bump", flag])

    def test_no_frames_is_refused(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                S.main(["--frames", "0"])


class CommandLineTests(unittest.TestCase):
    def test_a_bump_run_prints_its_display_and_passes(self):
        out = io.StringIO()
        with mock.patch.object(S, "build", wraps=S.build) as spy:
            with contextlib.redirect_stdout(out):
                code = S.main(["--seed", str(SEED), "--live", "10", "--dormant", "0",
                               "--frames", "3", "--pack", "--bump"])
        text = out.getvalue()
        self.assertEqual(code, 0)
        self.assertEqual(spy.call_count, 1)
        self.assertIn("hints off", text)
        self.assertIn("director frozen", text)
        self.assertIn("bump 3 passes", text)


class BudgetTests(unittest.TestCase):
    def test_the_budget_is_one_60_hz_period(self):
        self.assertAlmostEqual(S.BUDGET_MS, 1000.0 / 60.0)

    def test_only_frames_past_the_budget_count(self):
        self.assertEqual(S.over_budget([16.0, 16.66, 16.67, 17.0, 40.0]), 3)
        self.assertEqual(S.over_budget([]), 0)


if __name__ == "__main__":
    unittest.main()
