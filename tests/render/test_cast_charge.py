"""ENT-013: the Hexcaller's cast wind-up art.

The strip is joined from sixteen archived Gigapack frames by
`tools/asset_pipeline/cut_cast_charge.py`, and its `--check` runs here so a
replaced source cannot leave a stale strip behind (the regenerable-art rule).
The sources are tracked in `assets/enemies/hex_shaman/unused/cast_charge/`, so
the check always has its input -- no skip.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.assets import get_assets

RIG = "hex_shaman_cast_charge"


class CastChargeArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    def test_the_strip_matches_the_script(self):
        from tools.asset_pipeline import cut_cast_charge
        self.assertEqual(cut_cast_charge.main(["--check"]), 0,
                         "cut_cast_charge --check failed (2 = source frames missing)")

    def test_the_sixteen_source_frames_are_archived(self):
        from tools.asset_pipeline import cut_cast_charge
        self.assertEqual(len(cut_cast_charge.frames()), 16)

    def test_the_rig_plays_the_whole_strip(self):
        a = get_assets()
        self.assertEqual(a.frame_count(RIG, "loop"), 16)
        frames = a.frames(RIG, "loop", size=a.scale_for(RIG))
        self.assertEqual(len(frames), 16)
        self.assertTrue(all(f.get_bounding_rect().width > 0 for f in frames),
                        "a frame of the wind-up is empty")


if __name__ == "__main__":
    unittest.main()
