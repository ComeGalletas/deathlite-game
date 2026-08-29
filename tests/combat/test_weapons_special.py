"""Milestone 4: the three special weapon effects -- cone, orbit, chain params."""
import math
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import Weapon, FireContext
from game.content import get_content


class FakeEnemy:
    def __init__(self, x, y):
        self.pos = pygame.Vector2(x, y)


class FakeProj:
    """Minimal stand-in the orbit maintainer can hold and mutate."""
    def __init__(self, **kw):
        self.active = True
        self.__dict__.update(kw)


def ctx(enemies, sink, anchor=None):
    return FireContext(
        origin=pygame.Vector2(0, 0), enemies=enemies,
        damage_multiplier=1.0, attack_speed_multiplier=1.0,
        projectile_speed_multiplier=1.0, area_multiplier=1.0,
        fallback_dir=pygame.Vector2(1, 0),
        spawn_projectile=lambda **kw: sink.append(FakeProj(**kw)) or sink[-1],
        anchor=anchor or pygame.Vector2(0, 0))


class ConeTests(unittest.TestCase):
    def test_scythe_spawns_a_cone_shaped_hit(self):
        w = Weapon("soul_scythe", get_content().weapon("soul_scythe"))
        shots = []
        # CB-2: the scythe only swings at a foe inside its reach ring (== the
        # cone tip, area 74), so the target has to sit within that.
        w.update(0.016, ctx([FakeEnemy(50, 0)], shots))
        self.assertEqual(len(shots), 1)
        s = shots[0]
        self.assertGreater(s.cone_half_angle, 0.0)
        self.assertAlmostEqual(s.vel.length(), 0.0)      # stationary arc
        self.assertGreater(s.radius, 40)                  # wide area
        # cone points at the target
        self.assertAlmostEqual(s.cone_dir.x, 1.0, places=3)


class OrbitTests(unittest.TestCase):
    # CB-2 decision 6: the embers only orbit while a foe is inside `reach`
    # (ember_ring reach 140), so every case keeps an enemy in the ring.
    def test_maintains_projectile_count_orbiters(self):
        w = Weapon("ember_ring", get_content().weapon("ember_ring"))
        want = w._projectile_count()
        shots = []
        w.update(0.016, ctx([FakeEnemy(60, 0)], shots))
        self.assertEqual(len(shots), want)
        self.assertTrue(all(o.orbit_radius > 0 and o.orbit_speed != 0 for o in shots))

    def test_does_not_overspawn_on_repeated_updates(self):
        w = Weapon("ember_ring", get_content().weapon("ember_ring"))
        shots = []
        for _ in range(10):
            w.update(0.016, ctx([FakeEnemy(60, 0)], shots))
        self.assertEqual(len(shots), w._projectile_count())

    def test_extra_projectile_bonus_adds_an_orbiter_and_respaces(self):
        w = Weapon("ember_ring", get_content().weapon("ember_ring"))
        shots = []
        w.update(0.016, ctx([FakeEnemy(60, 0)], shots))
        w.bonus["projectile_count"] = 1
        w.update(0.016, ctx([FakeEnemy(60, 0)], shots))
        self.assertEqual(len(shots), w._projectile_count())
        angles = sorted(o.orbit_angle for o in shots)
        # evenly spaced around the circle
        gaps = [b - a for a, b in zip(angles, angles[1:])]
        for g in gaps:
            self.assertAlmostEqual(g, math.tau / len(shots), places=3)


class ChainTests(unittest.TestCase):
    def test_thunder_orb_tags_projectile_with_chain_charges(self):
        w = Weapon("thunder_orb", get_content().weapon("thunder_orb"))
        shots = []
        w.update(0.016, ctx([FakeEnemy(200, 0)], shots))
        self.assertEqual(shots[0].chain_left,
                         get_content().weapon("thunder_orb")["chain_count"])
        self.assertGreater(shots[0].chain_range, 0)


class MainWeaponAttackAnimTests(unittest.TestCase):
    """The hero attack animation syncs to `weapons[0]` (the starting weapon)
    only -- a picked-up second weapon firing must not drive it."""

    def _playing(self):
        from game.game import Game
        from game.states.menu_state import MenuState
        from game.states.playing_state import PlayingState
        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        g.state_machine.change(MenuState(g))
        for _ in range(2):
            g.state_machine.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        p = g.state_machine.current
        assert isinstance(p, PlayingState)
        p._spawn_enemy("chaser", at=p.player.pos + pygame.Vector2(60, 0))
        return g, p

    def test_main_weapon_fire_beat_triggers_the_anim(self):
        g, p = self._playing()
        p.player._attack_t = 0.0
        p._phase_combat(0.5)                         # weapons[0] fires this frame
        self.assertGreater(p.player._attack_t, 0.0)
        pygame.quit()

    def test_secondary_weapon_fire_beat_does_not_trigger_the_anim(self):
        g, p = self._playing()
        p.player.weapons[0]._cd = 999.0             # main weapon parked
        p.player.weapons.append(
            Weapon("arcane_bolt", get_content().weapon("arcane_bolt")))
        p.player._attack_t = 0.0
        before = len(p.projectiles)
        p._phase_combat(0.5)
        self.assertGreater(len(p.projectiles), before, "the secondary weapon never fired")
        self.assertEqual(p.player._attack_t, 0.0, "secondary weapon drove the attack anim")
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
