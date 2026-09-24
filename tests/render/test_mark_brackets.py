"""RND-007: the `mark` status's lock-on brackets art.

The strip is cut from fourteen archived Gigapack frames by
`tools/asset_pipeline/cut_mark_brackets.py`, and its `--check` runs here so a
replaced source or a changed hue cannot leave a stale strip behind (the
regenerable-art rule). The sources are tracked in
`assets/effects/status/unused/mark/`, so the check always has its input.
"""
import colorsys
import json
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.assets import get_assets
from game.content import get_content

RIG = "status_mark"


def _hues(frame):
    out = []
    w, h = frame.get_size()
    for x in range(w):
        for y in range(h):
            r, g, b, a = frame.get_at((x, y))
            if a > 160:
                hh, s, _v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                if s > 0.3:
                    out.append(hh * 360)
    return out


def _hue_gap(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


class MarkBracketArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        a = get_assets()
        cls.frames = a.frames(RIG, "loop", size=a.scale_for(RIG))

    def test_the_strip_matches_the_script(self):
        from tools.asset_pipeline import cut_mark_brackets
        self.assertEqual(cut_mark_brackets.main(["--check"]), 0,
                         "cut_mark_brackets --check failed (2 = source frames missing)")

    def test_the_fourteen_source_frames_are_archived(self):
        from tools.asset_pipeline import cut_mark_brackets
        self.assertEqual(len(cut_mark_brackets.frames()), 14)

    def test_the_rig_plays_the_whole_loop(self):
        self.assertEqual(get_assets().frame_count(RIG, "loop"), 14)
        self.assertEqual(len(self.frames), 14)
        self.assertTrue(all(f.get_bounding_rect().width > 0 for f in self.frames))

    def test_no_leader_line_is_left_above_the_brackets(self):
        """The top row of every frame is a bracket's, so nothing trails off
        the box: the left brackets' top equals the frame's top."""
        for i, f in enumerate(self.frames):
            box = f.get_bounding_rect()
            left = pygame.Rect(box.left, 0, 3, f.get_height())
            top_left = min(y for x in range(left.left, left.right)
                           for y in range(f.get_height()) if f.get_at((x, y)).a > 0)
            with self.subTest(frame=i):
                self.assertEqual(box.top, top_left)

    def test_the_art_is_raspberry_and_well_apart_from_fire(self):
        """The data's hue, and far from the fire element's orange -- the
        owner's rule for this mark. Raspberry sits 42 degrees from fire; the
        pack's own red, rejected for this, sat 8 off. 30 is the floor."""
        spec = get_content().status_visuals["mark"]
        hue = spec["recolour"]["hue"]
        fire = get_content().element_visuals["elements"]["fire"]["colour"]
        fire_hue = colorsys.rgb_to_hsv(*(c / 255 for c in fire))[0] * 360
        hues = sorted(h for f in self.frames[::3] for h in _hues(f))
        median = hues[len(hues) // 2]
        self.assertLess(_hue_gap(median, hue), 4)
        self.assertGreater(_hue_gap(median, fire_hue), 30)

    def test_the_fallback_ring_is_the_same_raspberry(self):
        spec = get_content().status_visuals["mark"]
        h = colorsys.rgb_to_hsv(*(c / 255 for c in spec["colour"]))[0] * 360
        self.assertLess(_hue_gap(h, spec["recolour"]["hue"]), 2)


if __name__ == "__main__":
    unittest.main()
