"""The browser pacing model (BLD-003, `tools/benchmarks/raf_pacing.py`).

Pins the facts `journals/web_frame_time_journal.md` draws from it: a 60 fps
cap costs nothing on a 60 Hz display; on a faster one it spins to hold
62.5 fps (pygame-ce's 16 whole-ms frame); at 75 Hz it drops a 12 ms frame
to 50 fps where the refresh gives 75; with no cap nothing spins and a light
step runs at the display's rate; the refresh's phase moves the spin, not
the fps; and the journal prints the model's current table.
"""
import contextlib
import io
import unittest
from pathlib import Path

from tools.benchmarks import raf_pacing as P


class PacingModelTests(unittest.TestCase):
    def test_the_cap_is_free_at_60_hz(self):
        for work in (1.0, 5.0, 12.0, 16.0):
            with self.subTest(work=work):
                p = P.simulate(60, work, 60)
                self.assertAlmostEqual(p.fps, 60.0, delta=0.05)
                self.assertEqual(p.spin_ms, 0.0)

    def test_a_light_step_spins_to_the_16_ms_frame_on_a_fast_display(self):
        for hz in (75, 90, 120, 144, 165):
            with self.subTest(hz=hz):
                p = P.simulate(hz, 5.0, 60)
                self.assertAlmostEqual(p.fps, 1000.0 / 16, delta=0.05)
                self.assertGreater(p.spin_ms, 5.0)

    def test_the_cap_drops_a_12_ms_step_to_50_fps_at_75_hz(self):
        self.assertAlmostEqual(P.simulate(75, 12.0, 60).fps, 50.0, delta=0.05)
        self.assertAlmostEqual(P.simulate(75, 12.0, None).fps, 75.0, delta=0.05)

    def test_no_cap_never_spins_and_follows_the_display(self):
        for hz in P.DISPLAYS_HZ:
            with self.subTest(hz=hz):
                p = P.simulate(hz, 5.0, None)
                self.assertEqual(p.spin_ms, 0.0)
                self.assertAlmostEqual(p.fps, float(hz), delta=0.05)

    def test_a_step_longer_than_a_period_skips_refreshes(self):
        """90 Hz is 11.1 ms a refresh; a 12 ms step takes two, capped or not."""
        self.assertAlmostEqual(P.simulate(90, 12.0, None).fps, 45.0, delta=0.05)
        self.assertAlmostEqual(P.simulate(90, 12.0, 60).fps, 45.0, delta=0.05)

    def test_the_phase_moves_the_spin_but_not_the_fps(self):
        for hz, work in ((75, 5.0), (90, 5.0), (165, 5.0), (75, 12.0)):
            with self.subTest(hz=hz, work=work):
                runs = [P.simulate(hz, work, 60, phase_ms=p) for p in P.PHASES]
                fps = {round(r.fps, 1) for r in runs}
                self.assertEqual(len(fps), 1, fps)
                r = P.row(hz, work)
                self.assertLessEqual(r.spin_lo, r.spin_hi)
                self.assertEqual(r.spin_lo, min(x.spin_ms for x in runs))

    def test_the_markdown_table_has_a_row_per_pair(self):
        text = P.markdown(P.table())
        self.assertEqual(len(text.splitlines()),
                         2 + len(P.DISPLAYS_HZ) * len(P.WORK_MS))

    def test_the_journal_prints_the_models_current_table(self):
        """The journal's table is the tool's output, regenerated, never
        hand-edited: a change to the model changes the journal with it."""
        journal = (Path(__file__).resolve().parents[2] / "documentation"
                   / "journals" / "web_frame_time_journal.md")
        self.assertIn(P.markdown(P.table()), journal.read_text(encoding="utf-8"))

    def test_the_command_line_prints_the_table(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = P.main(["--hz", "60,75", "--work", "12"])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(),
                         P.markdown(P.table((60.0, 75.0), (12.0,))))


if __name__ == "__main__":
    unittest.main()
