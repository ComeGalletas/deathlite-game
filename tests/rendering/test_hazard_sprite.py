"""The warlock pool's flair.

The ring states the exact damage edge and the disc states the area; both
are what a player reads, so the art is layered between them and never
replaces either. It plays once, at its own speed, timed to *end* as the
pool does -- which reads as the blast going off rather than as the pool
simmering for three and a half seconds.
"""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.hazard import Hazard
from game.assets import get_assets
from game.content import get_content
from game.states.playing import rendering
from tests import worlds as W

RIG = "hex_shaman_explosion_spell"


class _Recorder:
    """A surface that only remembers what was blitted onto it."""

    def __init__(self):
        self.blits = []

    def blit(self, frame, dest):
        self.blits.append((frame, dest))


def _renderer(zoom=1.0):
    ps = SimpleNamespace(
        game=SimpleNamespace(assets=get_assets()),
        camera=SimpleNamespace(zoom=zoom,
                               world_to_screen=lambda p: (p.x, p.y)))
    return rendering.WorldRenderer(ps)


class RigTests(unittest.TestCase):
    def setUp(self):
        W.display()

    def test_the_spell_rig_loads_and_slices(self):
        a = get_assets()
        self.assertEqual(a.frame_count(RIG, "loop"), 10)
        self.assertEqual(len(a.frames(RIG, "loop")), 10)
        self.assertFalse(a.loops(RIG, "loop"), "the blast is a one-shot")

    def test_the_art_is_drawn_at_the_damage_diameter(self):
        """`scale` follows `hazard_radius`: the flair can never disagree with
        the circle a player is reading."""
        radius = get_content().enemies["warlock"]["hazard_radius"]
        self.assertEqual(get_assets().scale_for(RIG), (2 * radius, 2 * radius))

    def test_the_warlock_names_the_rig(self):
        self.assertEqual(get_content().enemies["warlock"]["hazard_sprite"], RIG)


class TimingTests(unittest.TestCase):
    """`_hazard_sprite` decides *when* the strip shows and which frame."""

    def setUp(self):
        W.display()
        self.r = _renderer()
        a = get_assets()
        self.n = a.frame_count(RIG, "loop")
        self.span = self.n / a.fps(RIG, "loop")          # 10 / 14 == 0.714 s

    def _draw(self, life, max_life=3.5, sprite=RIG):
        hz = Hazard(0.0, 0.0, 92.0, 20.0, max_life, sprite=sprite)
        hz.life = life
        rec = _Recorder()
        self.r._hazard_sprite(rec, hz, 0.0, 0.0, 1.0)
        return rec.blits

    def test_silent_while_the_pool_is_still_simmering(self):
        for life in (3.5, 2.0, self.span + 0.05):
            self.assertEqual(self._draw(life), [], f"drew at life {life}")

    def test_it_plays_over_the_final_span_and_ends_with_the_pool(self):
        frames = get_assets().frames(RIG, "loop", size=get_assets().scale_for(RIG))
        first = self._draw(self.span - 0.001)
        last = self._draw(0.0)
        self.assertEqual(len(first), 1)
        self.assertIs(first[0][0], frames[0], "the strip did not start at frame 0")
        self.assertIs(last[0][0], frames[-1], "the strip did not end on the last frame")

    def test_the_index_is_clamped_not_wrapped(self):
        """A pool that outlives its own strip (a longer `hazard_duration`, a
        stalled frame) holds the last frame instead of starting over."""
        frames = get_assets().frames(RIG, "loop", size=get_assets().scale_for(RIG))
        for life in (0.0, -0.5, -10.0):
            blits = self._draw(life)
            self.assertEqual(len(blits), 1)
            self.assertIs(blits[0][0], frames[-1])

    def test_a_pool_with_no_rig_draws_no_art(self):
        self.assertEqual(self._draw(0.1, sprite=None), [])

    def test_the_art_is_centred_on_the_pool(self):
        (frame, dest), = self._draw(0.0)
        self.assertEqual(pygame.Rect(dest).center, (0, 0))
        self.assertEqual(pygame.Rect(dest).size, frame.get_size())


class LayerTests(unittest.TestCase):
    def setUp(self):
        W.display()

    def test_the_disc_is_fainter_than_it_was_and_the_ring_is_untouched(self):
        """The numbers the owner asked to move, and the one they asked to
        leave alone."""
        self.assertEqual((rendering._HAZARD_FILL_ALPHA, rendering._HAZARD_FILL_FLOOR),
                         (35, 10))
        self.assertLess(rendering._HAZARD_FILL_ALPHA + rendering._HAZARD_FILL_FLOOR,
                        70 + 20, "the fill is not fainter than before")

    def test_the_ring_is_drawn_after_the_art(self):
        """Ring last means ring on top: the edge a player judges safety by is
        never painted over by the flair."""
        import inspect
        src = inspect.getsource(rendering.WorldRenderer.hazards)
        art = src.index("_hazard_sprite")
        ring = src.rindex("pygame.draw.circle(surface, hz.color")
        self.assertLess(art, ring)


if __name__ == "__main__":
    unittest.main()
