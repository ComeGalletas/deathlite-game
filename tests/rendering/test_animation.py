"""Asset Phase B: the frame-timed `Animator` (pure timing logic)."""
import unittest

from systems.animation import Animator


class FakeAssets:
    """Minimal stand-in for game.assets.Assets -- fixed clip params."""
    def __init__(self, frames=4, fps=10.0, loop=False):
        self._frames, self._fps, self._loop = frames, fps, loop

    def frame_count(self, rig, anim):
        return self._frames

    def fps(self, rig, anim):
        return self._fps

    def loops(self, rig, anim):
        return self._loop

    def frame(self, rig, anim, index, *, size=None, flip=False):
        return ("frame", index, size, flip)


class AnimatorTests(unittest.TestCase):
    def test_starts_at_frame_zero(self):
        a = Animator(FakeAssets(), "rig", start="walk")
        self.assertEqual(a.anim, "walk")
        self.assertEqual(a.index, 0)

    def test_advances_by_fps(self):
        a = Animator(FakeAssets(frames=8, fps=10.0, loop=True), "rig")
        a.update(0.25)               # 2.5 frames
        self.assertEqual(a.index, 2)
        a.update(0.10)               # 3.5 frames
        self.assertEqual(a.index, 3)

    def test_loop_wraps(self):
        a = Animator(FakeAssets(frames=4, fps=10.0, loop=True), "rig")
        a.update(0.55)               # 5.5 frames -> 5 % 4 == 1
        self.assertEqual(a.index, 1)
        self.assertFalse(a.finished)

    def test_oneshot_clamps_and_reports_finished(self):
        a = Animator(FakeAssets(frames=4, fps=10.0, loop=False), "rig")
        a.update(0.29)               # 2.9 -> frame 2, not finished
        self.assertEqual(a.index, 2)
        self.assertFalse(a.finished)
        a.update(0.20)               # 4.9 -> clamps to last frame, finished
        self.assertEqual(a.index, 3)
        self.assertTrue(a.finished)

    def test_play_resets_only_on_change(self):
        a = Animator(FakeAssets(), "rig", start="idle")
        a.update(0.5)
        a.play("idle")               # same anim -> keep phase
        self.assertGreater(a.t, 0.0)
        a.play("walk")               # change -> reset
        self.assertEqual(a.t, 0.0)
        a.update(0.5)
        a.play("walk", restart=True)
        self.assertEqual(a.t, 0.0)

    def test_frame_delegates_with_size_and_flip(self):
        a = Animator(FakeAssets(frames=6, fps=12.0, loop=True), "hero")
        a.update(0.30)               # frame 3
        self.assertEqual(a.frame(size=(48, 48), flip=True),
                         ("frame", 3, (48, 48), True))


if __name__ == "__main__":
    unittest.main()
