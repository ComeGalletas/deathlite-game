"""`CharacterSelectState._draw_preview`: the hero previews under the cards.

The preview used to stretch every hero into one hand-tuned box, so the art was
distorted (Nihil is 56x33 in-game and was squeezed into a 184x130 upright box)
and all three read the same height. What is pinned here:

* a preview is the hero's *own* in-game draw size (`Assets.scale_for`, what
  `RenderPipeline.hero_sprite_frame` uses) times one shared multiplier, so the
  aspect ratio matches the run exactly and no per-hero table can creep back;
* the heroes keep their in-game height *order* -- the screen shows that Nihil
  is shorter than Aegis;
* every hero stands on one shared ground line, fixed for the screen, so
  arrowing between cards does not move it;
* at that multiplier the group still clears the cards above and the difficulty
  ribbon below -- the guard that keeps `_PREVIEW_ZOOM` honest.
"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.game import Game
from game.states.character_select_state import (
    CharacterSelectState, _PREVIEW_PHASES, _PREVIEW_PX, _PREVIEW_ZOOM,
)


def _select():
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    state = CharacterSelectState(game)
    game.state_machine.change(state)
    game.running = True
    return game, state


class HeroPreviewSizeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game, cls.state = _select()

    def test_preview_is_the_ingame_draw_size_times_the_shared_zoom(self):
        assets = self.game.assets
        for cid in self.state.ids:
            rig = self.state.content.characters[cid]["sprite"]
            bw, bh = assets.scale_for(rig)
            w, h, _below = self.state._preview_metrics(cid)
            self.assertEqual((w, h), (round(bw * _PREVIEW_ZOOM), round(bh * _PREVIEW_ZOOM)),
                             f"{cid} previews at a size the run never draws")

    def test_aspect_ratio_matches_the_ingame_sprite(self):
        assets = self.game.assets
        for cid in self.state.ids:
            rig = self.state.content.characters[cid]["sprite"]
            bw, bh = assets.scale_for(rig)
            w, h, _below = self.state._preview_metrics(cid)
            self.assertAlmostEqual(w / h, bw / bh, delta=0.02,
                                   msg=f"{cid} is stretched in the preview")

    def test_heroes_keep_their_relative_heights(self):
        assets = self.game.assets
        heights = {cid: self.state._preview_metrics(cid)[1] for cid in self.state.ids}
        ingame = {cid: assets.scale_for(self.state.content.characters[cid]["sprite"])[1]
                  for cid in self.state.ids}
        order = sorted(self.state.ids, key=lambda c: ingame[c])
        self.assertEqual(sorted(self.state.ids, key=lambda c: heights[c]), order)
        self.assertGreater(len(set(heights.values())), 1,
                           "every hero the same height -- the fixed box is back")

    def test_frames_are_built_at_that_size(self):
        for i, cid in enumerate(self.state.ids):
            self.state.index = i
            self.state._sync_preview()
            w, h, _below = self.state._preview_metrics(cid)
            for phase in _PREVIEW_PHASES:
                self.state._preview.play(phase, restart=True)
                frame = self.state._preview.frame(size=(w, h))
                self.assertEqual(frame.get_size(), (w, h), f"{cid} / {phase}")


class HeroPreviewPlacementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game, cls.state = _select()
        cls.state.draw(cls.game.screen)
        cls.layout = dict(cls.state._layout)

    def _extent(self, cid):
        """(top, bottom) of the hero's preview frame on the drawn screen."""
        _w, h, below = self.state._preview_metrics(cid)
        bottom = self.layout["preview_baseline"] + below
        return bottom - h, bottom

    def test_the_ground_line_is_shared_and_does_not_move_with_the_pick(self):
        top = self.layout["preview_top"]
        baseline = self.state._preview_baseline(top)
        for i in range(len(self.state.ids)):
            self.state.index = i
            self.state._sync_preview()
            self.assertEqual(self.state._preview_baseline(top), baseline)

    def test_feet_land_on_the_baseline(self):
        baseline = self.layout["preview_baseline"]
        for cid in self.state.ids:
            _top, bottom = self._extent(cid)
            below = self.state._preview_metrics(cid)[2]
            self.assertAlmostEqual(bottom - below, baseline, delta=1,
                                   msg=f"{cid} does not stand on the shared line")

    def test_the_group_clears_the_cards_and_the_ribbon(self):
        card_bottom = self.layout["card_bottom"]
        ribbon_top = self.layout["ribbon"].top
        for cid in self.state.ids:
            top, bottom = self._extent(cid)
            self.assertGreaterEqual(top, card_bottom, f"{cid} overlaps the hero cards")
            self.assertLessEqual(bottom, ribbon_top, f"{cid} overlaps the difficulty ribbon")

    def test_the_band_still_holds_the_group(self):
        """The preview band the layout reserves is the budget: the whole group
        fits within a `_PREVIEW_PX` window around the baseline, give or take
        the few px of frame that hang past it."""
        top = self.layout["preview_top"]
        tops = [self._extent(cid)[0] for cid in self.state.ids]
        bottoms = [self._extent(cid)[1] for cid in self.state.ids]
        self.assertLessEqual(max(bottoms) - min(tops), _PREVIEW_PX + 10)
        self.assertAlmostEqual((min(tops) + max(bottoms)) / 2,
                               top + _PREVIEW_PX / 2, delta=6,
                               msg="the group is not centred in its band")


if __name__ == "__main__":
    unittest.main()
