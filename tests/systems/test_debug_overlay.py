"""The F1 developer overlay (`systems/debug_overlay.py`): hidden it draws
nothing; shown it draws a box of FPS, the smoothed timings and every metric
a state has fed it."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from systems.debug_overlay import DebugOverlay


class _Clock:
    def get_fps(self):
        return 59.94


class _RecordingFont:
    """The real font, remembering every line rendered through it."""

    def __init__(self, font):
        self._font = font
        self.lines = []

    def render(self, text, *a, **kw):
        self.lines.append(text)
        return self._font.render(text, *a, **kw)

    def __getattr__(self, name):
        return getattr(self._font, name)


class DebugOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def _shown(self):
        o = DebugOverlay()
        o.visible = True
        o._font = _RecordingFont(o._ensure_font())
        return o

    def test_it_starts_as_the_config_says_and_toggles(self):
        o = DebugOverlay()
        self.assertEqual(o.visible, config.DEBUG_OVERLAY_DEFAULT)
        o.toggle()
        self.assertEqual(o.visible, not config.DEBUG_OVERLAY_DEFAULT)
        o.toggle()
        self.assertEqual(o.visible, config.DEBUG_OVERLAY_DEFAULT)

    def test_metrics_are_kept_as_text(self):
        o = DebugOverlay()
        o.set_metric("enemies", 42)
        o.set_metric("nav", "on 3 ms")
        self.assertEqual(o._metrics, {"enemies": "42", "nav": "on 3 ms"})

    def test_timings_are_smoothed_a_tenth_at_a_time(self):
        o = DebugOverlay()
        o.record_timing(10.0, 20.0)
        self.assertAlmostEqual(o._update_ms, 1.0)
        self.assertAlmostEqual(o._render_ms, 2.0)
        for _ in range(200):
            o.record_timing(10.0, 20.0)
        self.assertAlmostEqual(o._update_ms, 10.0, places=3)
        self.assertAlmostEqual(o._render_ms, 20.0, places=3)

    def test_hidden_it_draws_nothing(self):
        o = DebugOverlay()
        o.visible = False
        surface = pygame.Surface((320, 200))
        surface.fill((10, 20, 30))
        o.draw(surface, _Clock())
        self.assertEqual(surface.get_at((20, 20))[:3], (10, 20, 30))
        self.assertIsNone(o._font, "a hidden overlay never even loads its font")

    def test_shown_it_draws_fps_timings_and_every_metric(self):
        o = self._shown()
        o.set_metric("enemies", 42)
        o.record_timing(5.0, 7.0)
        surface = pygame.Surface((320, 200))
        surface.fill((200, 200, 200))
        o.draw(surface, _Clock())
        lines = o._font.lines
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0].startswith("FPS") and "59.9" in lines[0])
        self.assertIn("0.50", lines[1])                  # update ms, smoothed
        self.assertIn("0.70", lines[2])                  # render ms, smoothed
        self.assertTrue(lines[3].startswith("enemies") and lines[3].endswith("42"))
        # the translucent box darkens what was under it
        self.assertLess(sum(surface.get_at((10, 10))[:3]), 3 * 200)
        self.assertEqual(surface.get_at((300, 190))[:3], (200, 200, 200))


if __name__ == "__main__":
    unittest.main()
