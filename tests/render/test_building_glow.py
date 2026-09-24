"""CMB-009.1: the faint element glow under an elemental buff building.

Pure: a real `Interactable`, a stand-in camera and a blank surface -- no
world, no run. The glow's numbers come from `data/world/buildings.json`, so
the assertions read them from there rather than restating them.
"""
import copy
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.elements.ids import ELEMENTS
from entities.interactable import Interactable
from game import content as content_mod
from game.content import ContentError, get_content
from game.states.playing.visual.elements import ElementVisuals
from game.states.playing.visual.elements.building_glow import BuildingGlow


class _Camera:
    zoom = 1.0

    def world_to_screen(self, pos):
        return pos.x, pos.y


def _cfg():
    return get_content().buildings["elements"]["glow"]


def _surface():
    surf = pygame.Surface((400, 400), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    return surf


class BuildingGlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.visuals = ElementVisuals(get_content())

    def _building(self, element):
        return Interactable("magnet", 200, 200, element=element)

    def test_a_run_gets_a_glow_from_the_data(self):
        self.assertIsInstance(self.visuals.building_glow, BuildingGlow)
        self.assertEqual(self.visuals.building_glow.cfg, _cfg())

    def test_an_elemental_building_glows_in_its_elements_tint(self):
        for element in ELEMENTS:
            surf = _surface()
            drew = self.visuals.building_glow.draw(
                surf, _Camera(), self._building(element), self.visuals.tint, 0.0)
            self.assertTrue(drew, element)
            r, g, b, a = surf.get_at((200, 200))
            self.assertGreater(a, 0, f"{element}: nothing under the building")
            self.assertEqual((r, g, b), tuple(self.visuals.tint(element)), element)

    def test_it_stays_faint(self):
        """Never brighter than `alpha_max` at the centre, where the rings
        stack -- the art covers the middle, but a glow that could reach
        full opacity would not be faint."""
        surf = _surface()
        self.visuals.building_glow.draw(
            surf, _Camera(), self._building(ELEMENTS[0]), self.visuals.tint, 0.0)
        self.assertLessEqual(surf.get_at((200, 200)).a, int(_cfg()["alpha_max"]))

    def test_it_reaches_past_the_building(self):
        """The rim is what shows, so the disc must be wider than the
        building's own interaction circle."""
        b = self._building(ELEMENTS[0])
        d = self.visuals.building_glow.cache.diameter(2.0 * b.radius, 1.0)
        self.assertGreater(d, 2 * b.radius)

    def test_a_plain_building_does_not_glow(self):
        surf = _surface()
        drew = self.visuals.building_glow.draw(
            surf, _Camera(), self._building(None), self.visuals.tint, 0.0)
        self.assertFalse(drew)
        self.assertEqual(surf.get_at((200, 200)).a, 0)

    def test_a_used_building_goes_out(self):
        b = self._building(ELEMENTS[0])
        b.used = True
        surf = _surface()
        self.assertFalse(self.visuals.building_glow.draw(
            surf, _Camera(), b, self.visuals.tint, 0.0))
        self.assertEqual(surf.get_at((200, 200)).a, 0)

    def test_the_breath_stays_between_its_two_alphas(self):
        cfg = _cfg()
        glow = self.visuals.building_glow
        seen = set()
        for step in range(40):
            now = step * float(cfg["period"]) / 40
            surf = _surface()
            glow.draw(surf, _Camera(), self._building(ELEMENTS[0]),
                      self.visuals.tint, now)
            seen.add(surf.get_at((200, 200)).a)
        self.assertGreater(len(seen), 1, "the glow does not breathe")
        self.assertLessEqual(max(seen), int(cfg["alpha_max"]))


class GlowDataTests(unittest.TestCase):
    """The block is read with no defaults, so bad data stops the boot."""

    def _check(self, glow):
        block = copy.deepcopy(get_content().buildings["elements"])
        if glow is None:
            block.pop("glow")
        else:
            block["glow"] = glow
        content_mod._check_building_elements({"elements": block})

    def test_the_shipped_block_passes(self):
        self._check(copy.deepcopy(_cfg()))

    def test_a_missing_block_is_refused(self):
        with self.assertRaises(ContentError):
            self._check(None)

    def test_a_missing_field_is_refused(self):
        for field in ("scale", "alpha_min", "alpha_max", "period", "steps"):
            glow = copy.deepcopy(_cfg())
            glow.pop(field)
            with self.subTest(field=field), self.assertRaises(ContentError):
                self._check(glow)

    def test_alphas_out_of_order_or_range_are_refused(self):
        for lo, hi in ((80, 40), (-1, 40), (40, 300)):
            glow = dict(_cfg(), alpha_min=lo, alpha_max=hi)
            with self.subTest(lo=lo, hi=hi), self.assertRaises(ContentError):
                self._check(glow)


if __name__ == "__main__":
    unittest.main()
