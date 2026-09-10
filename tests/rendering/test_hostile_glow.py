"""The faint steady glow under hostile shots (group D of the glow plan):
under the arrow, sized from the shot's collider, one constant alpha shared
by a whole volley, view-culled, off with the config."""
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
    def __init__(self, size):
        super().__init__(size)
        self.blits = []

    def blit(self, src, dest, *a, **k):
        r = dest if isinstance(dest, pygame.Rect) else pygame.Rect(dest, src.get_size())
        self.blits.append((src, pygame.Rect(r)))
        return super().blit(src, dest, *a, **k)


class HostileGlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = _run()

    def setUp(self):
        self.ps.hostiles.clear()
        self.ps.renderer._glow.clear()

    def _shot(self, offset, radius=6.0):
        ps = self.ps
        ps.fx.fire_hostile(pos=ps.player.pos + pygame.Vector2(offset),
                           vel=pygame.Vector2(-1, 0) * 230, damage=6, radius=radius)
        return ps.hostiles.active[-1]

    def _draw(self):
        screen = _Spy(self.game.screen.get_size())
        self.ps.renderer.hostile_projectiles(screen)
        return screen.blits

    def test_glow_under_the_arrow_sized_from_the_collider(self):
        self._shot((60, 0), radius=6.0)
        blits = self._draw()
        self.assertEqual(len(blits), 2)                          # glow, then arrow
        glow, arrow = blits
        self.assertEqual(glow[1].center, arrow[1].center)
        want = round(6.0 * 2 * config.HOSTILE_GLOW["scale"] * self.ps.camera.zoom)
        self.assertEqual(glow[1].size, (want, want))
        self.assertEqual(glow[0].get_at((want // 2, want // 2)).a, config.HOSTILE_GLOW["alpha"])

    def test_alpha_is_steady_over_the_flight(self):
        shot = self._shot((60, 0))
        first = self._draw()[0][0]
        shot.lifetime -= 2.0                                     # later in its life
        for _ in range(30):
            self.ps.fx.update_projectiles(1 / 60)
        if not self.ps.hostiles.active:
            self.skipTest("shot expired or hit something")
        self.assertIs(self._draw()[0][0], first)                 # same cached surface

    def test_a_barrage_shares_one_surface(self):
        import math
        for i in range(20):                                      # the boss's radial ring
            ang = math.tau / 20 * i
            self.ps.fx.fire_hostile(pos=self.ps.player.pos + pygame.Vector2(80, 0),
                                    vel=pygame.Vector2(math.cos(ang), math.sin(ang)) * 190,
                                    damage=12, radius=7)
        blits = self._draw()
        self.assertEqual(len(blits), 40)
        self.assertEqual(len(self.ps.renderer._glow), 1)
        halos = {id(b[0]) for b in blits[0::2]}
        self.assertEqual(len(halos), 1)

    def test_off_screen_shots_draw_nothing(self):
        far = self.ps.camera.visible_rect().width + 500
        self._shot((far, 0))
        self.assertEqual(self._draw(), [])

    def test_off_switch_leaves_only_the_arrow(self):
        self._shot((60, 0))
        with mock.patch.dict(config.HOSTILE_GLOW, {"scale": 0}):
            self.assertEqual(len(self._draw()), 1)
        with mock.patch.dict(config.HOSTILE_GLOW, {"alpha": 0}):
            self.assertEqual(len(self._draw()), 1)

    def test_glow_colour_is_its_own_bright_red(self):
        colour = tuple(config.HOSTILE_GLOW["colour"])
        self.assertEqual(colour, tuple(config.HOSTILE_GLOW_COLOUR))
        self.assertNotEqual(colour, tuple(config.HOSTILE_ARROW_TINT))     # not the dark tint
        r, g, b = colour
        self.assertGreater(r, 200)                                          # bright...
        self.assertGreater(r, g + 60)                                       # ...and red
        self.assertGreater(r, b + 60)
        self._shot((60, 0))
        glow = self._draw()[0]
        w = glow[1].width
        self.assertEqual(tuple(glow[0].get_at((w // 2, w // 2)))[:3], colour)

    def test_steady_alpha_is_a_single_faint_level(self):
        # No breathing: one constant, kept well under the orbs' peak so a
        # boss volley never outshines the pickups.
        self.assertLess(config.HOSTILE_GLOW["alpha"], config.XP_GLOW["alpha_max"])
        self.assertGreater(config.HOSTILE_GLOW["alpha"], 0)


if __name__ == "__main__":
    unittest.main()
