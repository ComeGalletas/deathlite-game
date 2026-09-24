"""ENT-013: the Hexcaller's cast is drawn where it will land, for the whole
wind-up.

Pure: stand-ins for the run, the camera and the caster, the real asset
loader and the real `cast_marker` module. The caster's own numbers come from
`data/enemies/enemies.json`.
"""
import copy
import inspect
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.ai.machine import ATTACK_SLOT, _MACHINE
from game.assets import get_assets
from game.content import get_content
from game.states.playing.visual import cast_marker, scene

BG = (0, 0, 0)


class _BB:
    def __init__(self):
        self._slots = {}

    def slot(self, key):
        return self._slots.setdefault(key, {})


def _caster(pos=(40, 200), cast_at=(300, 200), telegraphing=True, t=0.4, cfg=None):
    e = SimpleNamespace(cfg=cfg if cfg is not None else copy.deepcopy(
                            get_content().enemies["hex_shaman"]),
                        alive=True, telegraphing=telegraphing,
                        pos=pygame.Vector2(pos), bb=_BB())
    if cast_at is not None:
        e.bb.slot(ATTACK_SLOT)["cast_at"] = pygame.Vector2(cast_at)
    e.bb.slot(_MACHINE)["entered"] = t
    return e


def _ps(enemies):
    camera = SimpleNamespace(zoom=1.0, world_to_screen=lambda p: (p[0], p[1]))
    run = SimpleNamespace(enemies=enemies, camera=camera)
    renderer = SimpleNamespace(run=run, _off_band=lambda level, pos: False)
    return SimpleNamespace(run=run, renderer=renderer,
                           game=SimpleNamespace(assets=get_assets()))


def _drawn_near(surface, x, y, r=20):
    """How many pixels within `r` of (x, y) are not the background."""
    n = 0
    for dx in range(-r, r + 1, 2):
        for dy in range(-r, r + 1, 2):
            if surface.get_at((x + dx, y + dy))[:3] != BG:
                n += 1
    return n


class CastMarkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    def _draw(self, *enemies):
        surf = pygame.Surface((400, 400))
        surf.fill(BG)
        cast_marker.draw(surf, _ps(list(enemies)))
        return surf

    def test_the_wind_up_is_drawn_at_the_landing_spot_not_at_the_caster(self):
        surf = self._draw(_caster(pos=(40, 200), cast_at=(300, 200)))
        self.assertGreater(_drawn_near(surf, 300, 200), 0, "nothing at cast_at")
        self.assertEqual(_drawn_near(surf, 40, 200), 0, "drawn at the caster")

    def test_nothing_is_drawn_outside_the_wind_up(self):
        surf = self._draw(_caster(telegraphing=False))
        self.assertEqual(_drawn_near(surf, 300, 200), 0)

    def test_nothing_is_drawn_without_a_snapshot(self):
        surf = self._draw(_caster(cast_at=None))
        self.assertEqual(_drawn_near(surf, 300, 200), 0)

    def test_an_enemy_without_a_cast_marker_draws_nothing(self):
        cfg = copy.deepcopy(get_content().enemies["hex_shaman"])
        cfg.pop("cast_marker")
        surf = self._draw(_caster(cfg=cfg))
        self.assertEqual(_drawn_near(surf, 300, 200), 0)

    def test_the_footprint_fades_in_over_the_wind_up(self):
        total = get_content().enemies["hex_shaman"]["cast_telegraph"]
        self.assertAlmostEqual(cast_marker.progress(_caster(t=0.0)), 0.0)
        self.assertAlmostEqual(cast_marker.progress(_caster(t=total / 2)), 0.5)
        self.assertAlmostEqual(cast_marker.progress(_caster(t=total * 3)), 1.0)

    def test_the_footprint_is_the_hazard_sprite_at_the_hazard_size(self):
        """The same `scale_for` path the landed hazard uses, so the ring
        marks the area that will actually burn."""
        cfg = get_content().enemies["hex_shaman"]
        a = get_assets()
        foot = cast_marker._footprint(a, _caster(), 1.0)
        self.assertIsNotNone(foot)
        self.assertEqual(foot.get_size(), a.scale_for(cfg["hazard_sprite"]))

    def test_the_hexcaller_declares_it_in_the_data(self):
        marker = get_content().enemies["hex_shaman"]["cast_marker"]
        self.assertEqual(marker["sprite"], "hex_shaman_cast_charge")
        lo, hi = marker["footprint_alpha"]
        self.assertTrue(0 <= lo < hi <= 255)

    def test_it_is_drawn_with_the_flat_effects_after_the_hazards(self):
        """Flat on its terrace under the characters -- a ground effect -- and
        after the hazard pools, so a cast landing on a live pool still shows."""
        src = inspect.getsource(scene.draw_flat_effects)
        self.assertLess(src.index("ren.hazards"), src.index("cast_marker.draw"))


if __name__ == "__main__":
    unittest.main()
