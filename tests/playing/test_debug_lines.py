"""RND-010.5: the F1 overlay's lines are computed only while it is shown
(`crowd_draw_journal.md`; plan 4.1, `crowd_performance_plan.md`).

`PlayingState`'s update used to fill the overlay's metrics every frame,
hidden or not, and one of them (`active_auras`) walks the whole crowd.
Pinned, on a booted seed-35 run: with the overlay hidden an update calls
neither `report_debug` nor `active_auras`; shown, it calls each once a
frame and the overlay's lines are filled.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config
from game.game import Game
from game.states.menu_state import MenuState
from tests.boot import start_run
from tests.devtools import (
    test_draw_layers as TDL,  # an alias: its classes are not collected twice
)

SEED = 35
FRAMES = 3


class DebugLinesTests(unittest.TestCase):
    """One booted run, shared; each test puts the overlay back hidden."""

    @classmethod
    def setUpClass(cls):
        cls.game = Game(save_path=TDL._fresh_save())
        cls.game.state_machine.change(MenuState(cls.game))
        cls.ps = start_run(cls.game, SEED)

    def tearDown(self):
        self.game.debug.visible = False
        self.game.debug._metrics.clear()

    def _frames(self, visible: bool):
        """`FRAMES` updates with the overlay `visible`; the two calls counted."""
        ps, run = self.ps, self.ps.run
        self.game.debug.visible = visible
        with mock.patch.object(ps.dev, "report_debug", wraps=ps.dev.report_debug) as report, \
                mock.patch.object(run.elements, "active_auras",
                                  wraps=run.elements.active_auras) as auras:
            for _ in range(FRAMES):
                ps.update(1 / 60)
        return report.call_count, auras.call_count

    def test_hidden_the_lines_are_never_computed(self):
        self.assertEqual(self._frames(visible=False), (0, 0))
        self.assertEqual(self.game.debug._metrics, {})

    def test_shown_they_are_computed_once_a_frame(self):
        self.assertEqual(self._frames(visible=True), (FRAMES, FRAMES))
        metrics = self.game.debug._metrics
        self.assertEqual(metrics["state"], "PLAYING")
        self.assertEqual(metrics["enemies"], str(len(self.ps.run.enemies)))
        self.assertIn("auras", metrics)

    def test_f1_fills_the_lines_on_the_next_update_and_hides_them_again(self):
        """Through the real key: `Game` handles input before the update, so
        F1 pressed in play shows filled lines on that same frame."""
        f1, ps, debug = config.DEBUG_KEYS["toggle_overlay"], self.ps, self.game.debug
        self.assertTrue(self.game._handle_debug_key(f1))
        self.assertTrue(debug.visible)
        ps.update(1 / 60)
        self.assertEqual(debug._metrics["enemies"], str(len(ps.run.enemies)))
        self.assertTrue(self.game._handle_debug_key(f1))
        self.assertFalse(debug.visible)
        self.assertEqual(debug._metrics, {})
        ps.update(1 / 60)
        self.assertEqual(debug._metrics, {})


if __name__ == "__main__":
    unittest.main()
