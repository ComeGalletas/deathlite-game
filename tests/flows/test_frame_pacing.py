"""Who paces the main loop (BLD-003.3).

On the desktop `Game._step` caps the frame with `clock.tick(config.FPS)`. In
the browser pygbag resumes the loop from `requestAnimationFrame` (per a
comment in its `aio.run`; not measured), so the web profile sets
`config.HOST_PACES_FRAMES` in the emscripten runtime only and `_step` then
ticks without a cap. In the model, a 60 fps cap there would spin the page's
thread on a display faster than 60 Hz if the runtime lacks Asyncify
(unconfirmed), and drops a 12 ms frame to 50 fps at 75 Hz (the model and the
trade-off are in `journals/web_frame_time_journal.md`). `main.py --web`
applies the same profile on the desktop, where nothing else paces the loop,
so it keeps the cap (D4).

`sys.platform` is patched only while the profile is applied, which is the
one place the runtime is read for this; the `Game` itself is built as the
desktop one.
"""
import contextlib
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config
from game.game import Game
from tests.web_profile import config_restored


@contextlib.contextmanager
def _profile_on(platform: str):
    """The web profile as `platform`'s runtime applies it, for the block."""
    with config_restored():
        with mock.patch("sys.platform", platform):
            config.apply_web_profile()
        yield


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
    with tempfile.TemporaryDirectory() as d:
        game = Game(save_path=os.path.join(d, "save.json"))
        game.clock = _Clock()
        game._start()
        for _ in range(frames):
            game._step()
        return game.clock.asked


class HostPacingFlagTests(unittest.TestCase):
    def test_the_desktop_paces_its_own_frames(self):
        self.assertFalse(config.HOST_PACES_FRAMES)

    def test_the_browser_runtime_hands_pacing_to_the_host(self):
        with _profile_on("emscripten"):
            self.assertTrue(config.HOST_PACES_FRAMES)
        self.assertFalse(config.HOST_PACES_FRAMES, "the helper restores it")

    def test_the_web_profile_on_the_desktop_keeps_the_cap(self):
        """`main.py --web`: same profile, but `asyncio.sleep(0)` paces
        nothing on the desktop."""
        with _profile_on("win32"):
            self.assertFalse(config.HOST_PACES_FRAMES)


class StepTickTests(unittest.TestCase):
    def test_the_desktop_step_caps_at_62(self):
        """Pinned, not read back from `config.FPS`, so a change to the
        desktop's own pacing fails here (rubric item 6 of BLD-003)."""
        self.assertEqual(_ticks(), [62] * 3)

    def test_the_browser_step_asks_for_no_cap(self):
        with _profile_on("emscripten"):
            self.assertEqual(_ticks(), [0] * 3)

    def test_the_web_profile_on_the_desktop_steps_at_60(self):
        with _profile_on("win32"):
            self.assertEqual(_ticks(), [60] * 3)


if __name__ == "__main__":
    unittest.main()
