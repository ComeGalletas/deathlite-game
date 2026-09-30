"""Who paces the main loop (BLD-003.3).

On the desktop `Game._step` caps the frame with `clock.tick(config.FPS)`. In
the browser pygbag steps the loop once per `requestAnimationFrame`, and a
capped tick would be pygame-ce's `SDL_Delay`, a busy-wait on the page's only
thread without Asyncify: the frame would be held twice. So the web profile
sets `config.HOST_PACES_FRAMES` in the emscripten runtime only, and `_step`
then ticks without a cap. `main.py --web` applies the same profile on the
desktop, where nothing else paces the loop, so it keeps the cap (D4).
"""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config
from game.game import Game
from tests.web_profile import web_profile


class _Clock:
    """Records what `_step` asks `tick` for; reports a 16 ms frame."""

    def __init__(self):
        self.asked = []

    def tick(self, framerate=0):
        self.asked.append(framerate)
        return 16

    def get_fps(self):
        return 60.0


def _ticks(frames: int = 3) -> list:
    """Build a game under the current config, drive `frames` loop steps
    through the menu, and return each `tick` argument."""
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.clock = _Clock()
    game._start()
    for _ in range(frames):
        game._step()
    return game.clock.asked


class HostPacingFlagTests(unittest.TestCase):
    def test_the_desktop_paces_its_own_frames(self):
        self.assertFalse(config.HOST_PACES_FRAMES)

    def test_the_browser_runtime_hands_pacing_to_the_host(self):
        with mock.patch("sys.platform", "emscripten"), web_profile():
            self.assertTrue(config.HOST_PACES_FRAMES)
        self.assertFalse(config.HOST_PACES_FRAMES, "the helper restores it")

    def test_the_web_profile_on_the_desktop_keeps_the_cap(self):
        """`main.py --web`: same profile, but `asyncio.sleep(0)` paces
        nothing on the desktop."""
        with mock.patch("sys.platform", "win32"), web_profile():
            self.assertFalse(config.HOST_PACES_FRAMES)


class StepTickTests(unittest.TestCase):
    def test_the_desktop_step_caps_at_fps(self):
        self.assertEqual(_ticks(), [config.FPS] * 3)

    def test_the_browser_step_asks_for_no_cap(self):
        with mock.patch("sys.platform", "emscripten"), web_profile():
            self.assertEqual(_ticks(), [0] * 3)

    def test_the_web_profile_on_the_desktop_steps_at_60(self):
        with mock.patch("sys.platform", "win32"), web_profile():
            self.assertEqual(_ticks(), [60] * 3)


if __name__ == "__main__":
    unittest.main()
