"""LD-9 D10: shots respect elevation.

The rule, as set with the rest of the phase: a projectile travels over its own
floor and over anything lower, so firing *down* off a terrace works. Firing
*up* does not -- it dies against the cliffside. Together with elevation-blind
aggro that makes high ground asymmetrically strong, which is deliberate.

The interesting half is *where* an upward shot dies. A cliff face has no
walkable level, so a test against `LevelIndex.level_at_point` would let the
shot through the wall and only stop it on the plateau beyond, reading as if it
had passed through solid rock. `top_at_point` reports the terrace a face holds
up, which is what puts the impact on the face.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.projectile import Projectile
from game import config
from world.elevation import NONE
from world.layout import CLIFF
from tests import worlds as W
from world.map import GameMap

SEED = 21


class _Particles:
    def __init__(self):
        self.bursts = 0

    def burst(self, *a, **kw):
        self.bursts += 1


class _Map:
    """Just the two attributes `TransientFx` touches for this rule."""

    def __init__(self, levels):
        self._levels = levels


class _PS:
    def __init__(self, levels):
        self.game_map = _Map(levels)
        self.particles = _Particles()


def _fx(levels):
    from game.states.playing.effects import TransientFx
    return TransientFx(_PS(levels))


class _World(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.gm = W.game_map(SEED)
        cls.levels = cls.gm._levels


    def _world_of(self, col, row):
        ox, oy = self.levels.origin
        px = config.TILE_PX
        return pygame.Vector2(ox + col * px + px / 2, oy + row * px + px / 2)

    def _step(self, col, row, dr):
        """A column where the terrain height changes going `dr` rows: returns
        `(from_cell, to_cell)` tile coords, or None."""
        a = self.levels.top_at(col, row)
        b = self.levels.top_at(col, row + dr)
        if a == NONE or b == NONE or a == b:
            return None
        return (col, row), (col, row + dr)

    def _find(self, rising: bool):
        """A pair of adjacent tiles where the terrain rises (or falls) going
        north, both real terrain."""
        for row in range(1, self.levels.rows - 1):
            for col in range(self.levels.cols):
                pair = self._step(col, row, -1)
                if pair is None:
                    continue
                lo = self.levels.top_at(*pair[0])
                hi = self.levels.top_at(*pair[1])
                if (hi > lo) is rising:
                    return pair
        return None


class TerrainTopTests(_World):
    def test_a_cliff_face_reports_the_terrace_it_holds_up(self):
        """`level_at_point` cannot answer this -- a face is not walkable -- and
        it is the whole reason `top_at` exists."""
        px = config.TILE_PX
        checked = 0
        for room in self.gm.layout.rooms:
            if not room.grid:
                continue
            c0 = (int(room.rect.left) - self.levels.origin[0]) // px
            r0 = (int(room.rect.top) - self.levels.origin[1]) // px
            for (col, row), cell in room.grid.items():
                if cell.kind != CLIFF:
                    continue
                self.assertEqual(self.levels.top_at(c0 + col, r0 + row),
                                 cell.level)
                self.assertEqual(self.levels.level_at(c0 + col, r0 + row), NONE)
                checked += 1
        self.assertGreater(checked, 0, "no cliff in this world to check")

    def test_the_void_has_no_top(self):
        """Otherwise a shot could not cross the sea between two islands."""
        self.assertEqual(self.levels.top_at(-5, -5), NONE)


class BlockTests(_World):
    def _shoot(self, at, fire_level):
        p = Projectile()
        p.reset(pos=at, vel=(0, 0), damage=1, radius=4, lifetime=1)
        p.active = True
        p.fire_level = fire_level
        fx = _fx(self.levels)
        fx.block_on_terrain(p)
        return p, fx.ps.particles.bursts

    def test_a_shot_dies_on_terrain_above_the_floor_it_left(self):
        pair = self._find(rising=True)
        self.assertIsNotNone(pair, "no rising step in this world")
        lo_t, hi_t = pair
        p, bursts = self._shoot(self._world_of(*hi_t),
                                self.levels.top_at(*lo_t))
        self.assertFalse(p.active, "the shot went through the cliff")
        self.assertEqual(bursts, 1, "no impact effect")

    def test_a_shot_crosses_terrain_at_or_below_its_own_floor(self):
        pair = self._find(rising=True)
        lo_t, hi_t = pair
        # fired from the high side, travelling down: the low tile must not stop it
        p, bursts = self._shoot(self._world_of(*lo_t),
                                self.levels.top_at(*hi_t))
        self.assertTrue(p.active, "firing down off a terrace was blocked")
        self.assertEqual(bursts, 0)

    def test_same_floor_is_never_blocked(self):
        pair = self._find(rising=True)
        lo_t, _hi = pair
        level = self.levels.top_at(*lo_t)
        p, _ = self._shoot(self._world_of(*lo_t), level)
        self.assertTrue(p.active)

    def test_open_sea_does_not_stop_anything(self):
        p, _ = self._shoot(pygame.Vector2(-9999, -9999), 0)
        self.assertTrue(p.active, "a shot died over open water")


class ExemptionTests(_World):
    def test_a_projectile_with_no_recorded_floor_is_left_alone(self):
        """`NONE` is what a flat world and every unit test that builds a
        projectile by hand get, so the rule has to be inert for them."""
        p = Projectile()
        p.reset(pos=(0, 0), vel=(0, 0), damage=1, radius=4, lifetime=1)
        p.active = True
        self.assertEqual(p.fire_level, NONE)
        fx = _fx(self.levels)
        fx.block_on_terrain(p)
        self.assertTrue(p.active)

    def test_an_orbiter_is_exempt(self):
        """Ember Ring circles the player and is not travelling anywhere -- the
        same reason it skips the obstacle test."""
        pair = self._find(rising=True)
        lo_t, hi_t = pair
        p = Projectile()
        p.reset(pos=self._world_of(*hi_t), vel=(0, 0), damage=1, radius=4,
                lifetime=1, orbit_speed=2.0, anchor=pygame.Vector2())
        p.active = True
        p.fire_level = self.levels.top_at(*lo_t)
        fx = _fx(self.levels)
        fx.block_on_terrain(p)
        self.assertTrue(p.active)

    def test_reset_clears_the_recorded_floor(self):
        """The pool recycles projectiles; a stale level would judge the next
        shot against the last one's ground."""
        p = Projectile()
        p.reset(pos=(0, 0), vel=(0, 0), damage=1, radius=4, lifetime=1)
        p.fire_level = 2
        p.reset(pos=(0, 0), vel=(0, 0), damage=1, radius=4, lifetime=1)
        self.assertEqual(p.fire_level, NONE)


if __name__ == "__main__":
    unittest.main()
