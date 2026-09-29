"""`tools/benchmarks/timer_regime.py` (SYS-011): the eval's own judgment,
without a window. The eval itself opens a real window and minimizes it, so
it is run by hand; what is pinned here is how it reads what it measures."""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tools.benchmarks import timer_regime as tr


def _arm(regime="1 ms timer", period_p50=16.7):
    return {"regime": regime, "period_p50": period_p50,
            "sleep_before": 1.5, "sleep_after": 1.5}


class RegimeTests(unittest.TestCase):
    def test_the_two_timers_and_the_gap_between_them(self):
        self.assertEqual(tr.regime(1.51), "1 ms timer")
        self.assertEqual(tr.regime(15.3), "coarse (~15.6 ms)")
        self.assertTrue(tr.regime(7.0).startswith("unclear"))
        # The thresholds sit between the two regimes, with room either side.
        self.assertLess(1.6, tr.FINE_SLEEP_MS)
        self.assertGreater(15.0, tr.COARSE_SLEEP_MS)

    def test_an_arm_is_one_regime_only_when_both_readings_agree(self):
        """Windows can apply its rule while an arm is being measured (seen:
        a first arm read 1.5 ms before its frames and held 30.7 ms frames)."""
        clock = tr._TimedClock(mock.Mock(tick=lambda fps: 16))

        def frames(game, seconds):          # what `_step` does: one tick a frame
            periods = [16.0, 17.0, 31.0] if seconds else []
            for _ in periods:
                clock.tick(62)
            return periods

        with mock.patch.object(tr, "SETTLE_S", 0.0), \
                mock.patch.object(tr, "_run_for", frames), \
                mock.patch.object(tr, "_sleep_median_ms", side_effect=[1.5, 15.3]):
            arm = tr.measure_arm(object(), object(), clock, 0.1)
        self.assertEqual(arm["regime"], "changed mid-arm")
        self.assertEqual((arm["sleep_before"], arm["sleep_after"]), (1.5, 15.3))
        self.assertEqual(arm["frames"], 3)
        self.assertEqual(arm["period_p50"], 17.0)

        with mock.patch.object(tr, "SETTLE_S", 0.0), \
                mock.patch.object(tr, "_run_for", frames), \
                mock.patch.object(tr, "_sleep_median_ms", side_effect=[15.3, 15.6]):
            self.assertEqual(tr.measure_arm(object(), object(), clock, 0.1)["regime"],
                             "coarse (~15.6 ms)")


class JudgeTests(unittest.TestCase):
    def results(self, managed, honored, again):
        return {"managed": managed, "honored": honored, "managed again": again}

    def test_the_fix_passes_on_the_1_ms_timer_at_the_caps_period(self):
        coarse = _arm("coarse (~15.6 ms)", 30.7)
        control, passed = tr.judge(self.results(coarse, _arm(), coarse), vsync=False)
        self.assertEqual(control, "REPRODUCED in both")
        self.assertTrue(passed)

    def test_the_control_never_fails_the_eval(self):
        """Windows not applying its rule this time says nothing about the fix."""
        control, passed = tr.judge(self.results(_arm(), _arm(), _arm()), vsync=False)
        self.assertEqual(control, "NOT reproduced")
        self.assertTrue(passed)
        coarse = _arm("coarse (~15.6 ms)", 30.7)
        control, _ = tr.judge(self.results(coarse, _arm(), _arm()), vsync=False)
        self.assertEqual(control, "reproduced in one")

    def test_a_coarse_or_changing_honored_arm_fails(self):
        coarse = _arm("coarse (~15.6 ms)", 30.7)
        for honored in (coarse, _arm("changed mid-arm", 16.7),
                        _arm("unclear (a loaded machine?)", 16.7)):
            with self.subTest(regime=honored["regime"]):
                _, passed = tr.judge(self.results(coarse, honored, coarse), vsync=False)
                self.assertFalse(passed)

    def test_without_vsync_the_frame_must_keep_the_caps_period(self):
        """The sleep alone is not enough when nothing else paces the frame:
        a 1 ms sleep with 31 ms frames means the cap is not what held it."""
        _, passed = tr.judge(self.results(_arm(), _arm(period_p50=30.7), _arm()), vsync=False)
        self.assertFalse(passed)

    def test_with_vsync_the_present_owns_the_period(self):
        """Minimized under vsync the present takes ~33 ms and the tick never
        waits, so only the sleep decides."""
        _, passed = tr.judge(self.results(_arm(), _arm(period_p50=33.5), _arm()), vsync=True)
        self.assertTrue(passed)


class ToolTests(unittest.TestCase):
    def test_the_timed_clock_times_the_tick_and_passes_the_rest_through(self):
        inner = mock.Mock()
        inner.tick.return_value = 16
        inner.get_fps.return_value = 60.0
        clock = tr._TimedClock(inner)
        self.assertEqual(clock.tick(62), 16)
        inner.tick.assert_called_once_with(62)
        self.assertEqual(len(clock.waits), 1)
        self.assertGreaterEqual(clock.waits[0], 0.0)
        self.assertEqual(clock.get_fps(), 60.0)

    def test_importing_it_opens_no_real_window(self):
        """The drivers are set in `main`, never at import: this test's own
        process kept the suite's dummy driver."""
        self.assertEqual(os.environ.get("SDL_VIDEODRIVER"), "dummy")

    def test_percentile(self):
        self.assertEqual(tr._pctl([3.0, 1.0, 2.0, 4.0], 0.9), 4.0)
        self.assertEqual(tr._pctl([5.0], 0.9), 5.0)


class CommandLineTests(unittest.TestCase):
    """In the integration tier (`tests/conftest.py`): the tier audit reads
    `main` as far as the `Game` it builds on Windows, past the early return
    this test takes."""

    def test_off_windows_it_says_so_and_touches_nothing(self):
        before = dict(os.environ)
        with mock.patch.object(tr.sys, "platform", "linux"), \
                mock.patch("builtins.print") as printed:
            self.assertEqual(tr.main([]), 2)
        self.assertIn("Windows only", printed.call_args[0][0])
        self.assertEqual(dict(os.environ), before)


if __name__ == "__main__":
    unittest.main()
