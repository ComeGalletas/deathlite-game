"""Floating damage numbers: the common (outgoing) style vs the incoming style
(red, 25% larger) shown when the hero takes damage."""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from ui.damage_numbers import DamageNumbers, _BASE_PT, _IN_PT


class StyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def test_incoming_font_is_25_percent_bigger_than_common(self):
        self.assertEqual(_IN_PT, round(_BASE_PT * 1.25))
        dn = DamageNumbers()
        common, _crit, incoming = dn._fonts()
        self.assertGreater(incoming.get_height(), common.get_height())

    def test_add_flags_incoming(self):
        dn = DamageNumbers()
        dn.add(pygame.Vector2(0, 0), 12, incoming=True)
        dn.add(pygame.Vector2(0, 0), 7)
        flags = sorted(n.incoming for n in dn._pool)
        self.assertEqual(flags, [False, True])

    def test_incoming_renders_in_the_red_damage_colour(self):
        from systems.camera import Camera
        dn = DamageNumbers()
        dn.add(pygame.Vector2(0, 0), 9, incoming=True)
        surf = pygame.Surface((120, 60), pygame.SRCALPHA)
        dn.draw(surf, Camera(2000, 2000))
        r, g, b = config.COLOR_DAMAGE_IN
        hit = any(surf.get_at((x, y))[:3] == (r, g, b)
                  for x in range(0, 120, 2) for y in range(0, 60, 2))
        self.assertTrue(hit, "no pixel in COLOR_DAMAGE_IN was drawn")


class HeroDamageTests(unittest.TestCase):
    def test_player_damaged_pushes_an_incoming_number(self):
        from game.game import Game
        from game.states.menu_state import MenuState
        from game.states.playing_state import PlayingState

        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        g.state_machine.change(MenuState(g))
        for _ in range(2):
            g.state_machine.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        from tests.boot import settle
        p = settle(g)                  # through the loading screen
        assert isinstance(p, PlayingState)

        before = len(p.damage_numbers)
        p._on_player_damaged(amount=8.0)
        self.assertEqual(len(p.damage_numbers), before + 1)
        self.assertTrue(list(p.damage_numbers._pool)[-1].incoming)

        p._on_player_damaged(amount=0.0)      # fully absorbed -> no number
        self.assertEqual(len(p.damage_numbers), before + 1)
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
