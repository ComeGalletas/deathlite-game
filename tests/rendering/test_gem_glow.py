"""The XP-orb glow in the world pass (group B of the glow plan): under each
orb, sized from the orb, breathing on the gem's own age, view-culled, and
gone when the config turns it off."""
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.game import Game
from game.states.menu_state import MenuState
from game.states.playing_state import PlayingState


def _key(game, k):
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


def _run():
    from tests.boot import settle
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    for _ in range(2):
        _key(game, pygame.K_RETURN)
    ps = settle(game)
    assert isinstance(ps, PlayingState)
    return game, ps


class _Spy(pygame.Surface):
    """Records every blit's source size and destination rect."""
    def __init__(self, size):
        super().__init__(size)
        self.blits = []

    def blit(self, src, dest, *a, **k):
        r = dest if isinstance(dest, pygame.Rect) else pygame.Rect(dest, src.get_size())
        self.blits.append((src, pygame.Rect(r)))
        return super().blit(src, dest, *a, **k)


class GemGlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = _run()

    def setUp(self):
        ps = self.ps
        ps.gems.clear()                                    # the run's own drops are gone
        ps.renderer._glow.clear()
        self.level = None                                  # every band

    def _gem(self, offset, tier_value=1, age=0.0):
        g = self.ps.gems.acquire()
        g.reset(self.ps.player.pos + pygame.Vector2(offset), tier_value)
        g.age = age
        return g

    def _draw(self):
        screen = _Spy(self.game.screen.get_size())
        self.ps.renderer.gems(screen, self.level)
        return screen.blits

    def test_glow_is_blitted_under_the_orb_and_centred_on_it(self):
        self._gem((40, 0))
        blits = self._draw()
        self.assertEqual(len(blits), 2)                       # glow, then orb
        glow, orb = blits
        self.assertGreater(glow[1].width, orb[1].width)       # the halo is the bigger one
        self.assertEqual(glow[1].center, orb[1].center)
        z = self.ps.camera.zoom
        want = self.ps.renderer._glow.diameter(8, z)          # tier 0 orb is 8 world px
        self.assertEqual(glow[1].size, (want, want))
        self.assertEqual(glow[0].get_at((want // 2, want // 2)).a,
                         self.ps.renderer._glow.pulsed(8, z, 0.0).get_at((want // 2, want // 2)).a)

    def test_glow_breathes_on_the_gems_own_age(self):
        p = config.XP_GLOW["period"]
        self._gem((40, 0), age=p / 4)                          # peak
        self._gem((-40, 0), age=3 * p / 4)                     # trough
        blits = self._draw()
        halos = [b for b in blits if b[1].width > 12]
        self.assertEqual(len(halos), 2)
        a = [h[0].get_at((h[1].width // 2, h[1].width // 2)).a for h in halos]
        self.assertEqual(sorted(a), [config.XP_GLOW["alpha_min"], config.XP_GLOW["alpha_max"]])

    def test_off_screen_gems_draw_nothing(self):
        far = self.ps.camera.visible_rect().width + 500
        self._gem((far, 0))
        self.assertEqual(self._draw(), [])

    def test_turning_the_glow_off_leaves_only_the_orb(self):
        self._gem((40, 0))
        with mock.patch.dict(config.XP_GLOW, {"scale": 0}):
            self.ps.renderer._glow.clear()
            blits = self._draw()
        self.assertEqual(len(blits), 1)

    def test_a_field_of_orbs_touches_few_surfaces(self):
        for i in range(40):
            self._gem((20 * (i % 8) - 70, 20 * (i // 8) - 40), age=i * 0.137)
        self._draw()
        self.assertLessEqual(len(self.ps.renderer._glow), config.XP_GLOW["steps"])


if __name__ == "__main__":
    unittest.main()
