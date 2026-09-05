"""Milestone 1 pure-logic tests: input direction, frame-rate independent
movement, world clamping, damage/armor."""
import unittest

import pygame

from entities.player import Player, input_vector
from game import config


# The default layout's tables (CB-5): WASD walks, the arrows aim.
WASD = config.KEY_LAYOUTS["wasd_move"]["move"]
ARROWS = config.KEY_LAYOUTS["wasd_move"]["aim"]


def keys(*pressed):
    """Build a dict usable as a pygame key-state sequence for the given keys."""
    return {k: (k in pressed) for k in (
        pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s,
        pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN,
    )}


class InputVectorTests(unittest.TestCase):
    def test_no_keys_is_zero(self):
        self.assertEqual(input_vector(keys(), WASD).length_squared(), 0.0)

    def test_cardinal_is_unit(self):
        self.assertAlmostEqual(input_vector(keys(pygame.K_d), WASD).x, 1.0)
        self.assertAlmostEqual(input_vector(keys(pygame.K_w), WASD).y, -1.0)

    def test_diagonal_is_normalised(self):
        v = input_vector(keys(pygame.K_d, pygame.K_s), WASD)
        self.assertAlmostEqual(v.length(), 1.0, places=6)

    def test_opposite_keys_cancel(self):
        self.assertEqual(input_vector(keys(pygame.K_a, pygame.K_d), WASD).x, 0.0)

    def test_only_the_given_keyset_moves(self):
        # CB-5: the arrows belong to the aim table, so they no longer walk the
        # hero under the default layout -- and vice versa under the swap.
        self.assertEqual(input_vector(keys(pygame.K_LEFT), WASD).length_squared(), 0.0)
        self.assertAlmostEqual(input_vector(keys(pygame.K_LEFT), ARROWS).x, -1.0)
        swapped = config.KEY_LAYOUTS["arrows_move"]
        self.assertAlmostEqual(input_vector(keys(pygame.K_LEFT), swapped["move"]).x, -1.0)
        self.assertEqual(input_vector(keys(pygame.K_a), swapped["move"]).length_squared(), 0.0)
        self.assertAlmostEqual(input_vector(keys(pygame.K_a), swapped["aim"]).x, -1.0)


class _RectWorld:
    """Minimal world: keeps the entity centre inside a rectangle (stand-in for
    GameMap.resolve_movement in movement tests)."""
    def __init__(self, w, h):
        self.w, self.h = w, h

    def resolve_movement(self, prev, new, radius, flying=False):
        return pygame.Vector2(min(max(new.x, radius), self.w - radius),
                              min(max(new.y, radius), self.h - radius))


class MovementTests(unittest.TestCase):
    def test_framerate_independent(self):
        """1 second of travel is the same distance at 30 and 144 fps."""
        world = _RectWorld(config.WORLD_WIDTH, config.WORLD_HEIGHT)

        def travel(fps):
            p = Player(1000, 1000)
            p.handle_input(keys(pygame.K_d), WASD)
            dt = 1.0 / fps
            for _ in range(fps):
                p.update(dt, world)
            return p.pos.x - 1000

        self.assertAlmostEqual(travel(30), travel(144), places=3)
        self.assertAlmostEqual(travel(30), config.PLAYER_DEFAULTS["move_speed"],
                               places=3)

    def test_clamped_inside_world(self):
        world = _RectWorld(config.WORLD_WIDTH, config.WORLD_HEIGHT)
        p = Player(5, 5)
        p.handle_input(keys(pygame.K_a, pygame.K_w), WASD)
        for _ in range(600):
            p.update(1 / 60, world)
        self.assertGreaterEqual(p.pos.x, p.radius)
        self.assertGreaterEqual(p.pos.y, p.radius)


class DamageTests(unittest.TestCase):
    def test_armor_reduces_damage(self):
        p = Player(0, 0)
        p.stats["armor"] = 3.0
        taken = p.take_damage(10.0)
        self.assertEqual(taken, 7.0)
        self.assertEqual(p.hp, p.max_hp - 7.0)

    def test_death_sets_flag_and_floors_hp(self):
        p = Player(0, 0)
        p.take_damage(9999.0)
        self.assertFalse(p.alive)
        self.assertEqual(p.hp, 0.0)

    def test_invulnerable_takes_nothing(self):
        p = Player(0, 0)
        p.invulnerable = True
        self.assertEqual(p.take_damage(50.0), 0.0)
        self.assertEqual(p.hp, p.max_hp)


class AnimStateTests(unittest.TestCase):
    """Phase B: sprite-animation timers/facing on Player (no gameplay effect)."""

    def _world(self):
        return _RectWorld(config.WORLD_WIDTH, config.WORLD_HEIGHT)

    def test_hurt_timer_set_on_damage_and_decays(self):
        p = Player(100, 100)
        p.take_damage(10.0)
        self.assertGreater(p._hurt_t, 0.0)
        for _ in range(30):                       # 0.5 s
            p.update(1 / 60, self._world())
        self.assertEqual(p._hurt_t, 0.0)

    def test_no_hurt_timer_when_damage_is_fully_mitigated(self):
        p = Player(0, 0)
        p.stats["armor"] = 999
        p.take_damage(5.0)
        self.assertEqual(p._hurt_t, 0.0)

    def test_attack_timer_via_trigger_and_decays(self):
        p = Player(0, 0)
        p.trigger_attack_anim()
        self.assertGreater(p._attack_t, 0.0)
        for _ in range(40):
            p.update(1 / 60, self._world())
        self.assertEqual(p._attack_t, 0.0)

    def test_facing_follows_horizontal_input_and_persists_when_still(self):
        p = Player(1000, 1000)
        p.handle_input(keys(pygame.K_d), WASD)
        p.update(1 / 60, self._world())
        self.assertEqual(p._facing, 1)
        p.handle_input(keys(pygame.K_a), WASD)
        p.update(1 / 60, self._world())
        self.assertEqual(p._facing, -1)
        p.handle_input(keys(), WASD)                    # released -> keep last facing
        p.update(1 / 60, self._world())
        self.assertEqual(p._facing, -1)


if __name__ == "__main__":
    unittest.main()
