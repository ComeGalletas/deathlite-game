"""Milestone 4: the three special weapon effects -- cone, orbit, chain params."""
import math
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from tests import worlds as W

SEED = W.pinned(0)

from combat.weapons import Weapon, FireContext
from game.content import get_content
from tests.combat.fakes import FakeProj, FakeTarget


def ctx(enemies, sink, anchor=None):
    return FireContext(
        origin=pygame.Vector2(0, 0), enemies=enemies,
        damage_multiplier=1.0, attack_speed_multiplier=1.0,
        projectile_speed_multiplier=1.0, area_multiplier=1.0,
        fallback_dir=pygame.Vector2(1, 0),
        spawn_projectile=lambda **kw: sink.append(FakeProj(**kw)) or sink[-1],
        anchor=anchor or pygame.Vector2(0, 0))


def chain_weapon():
    """Chain is an upgrade now (design §3.5): the chain path is exercised on
    the Rod with the old Thunder Orb's chain fields."""
    d = dict(get_content().weapon("magic_rod"))
    d.update(special_effect="chain", chain_count=3, chain_range=220)
    return Weapon("chain_rod", d), d


class ConeTests(unittest.TestCase):
    def test_sword_spawns_a_cone_shaped_hit(self):
        w = Weapon("sword", get_content().weapon("sword"))
        shots = []
        # CB-2: the sword only swings at a foe inside its reach ring (== the
        # cone tip, its `area`), so the target has to sit within that.
        reach = get_content().weapon("sword")["area"]
        w.update(0.016, ctx([FakeTarget(reach * 0.6, 0)], shots))
        self.assertEqual(len(shots), 1)
        s = shots[0]
        self.assertGreater(s.cone_half_angle, 0.0)
        self.assertAlmostEqual(s.vel.length(), 0.0)      # stationary arc
        self.assertGreater(s.radius, 20)                  # wide area
        # cone points at the target
        self.assertAlmostEqual(s.cone_dir.x, 1.0, places=3)


class OrbitTests(unittest.TestCase):
    # CB-2 decision 6: the embers only orbit while a foe is inside `reach`
    # (ember_ring reach 140), so every case keeps an enemy in the ring.
    def test_maintains_projectile_count_orbiters(self):
        w = Weapon("ember_ring", get_content().weapon("ember_ring"))
        want = w._projectile_count()
        shots = []
        w.update(0.016, ctx([FakeTarget(60, 0)], shots))
        self.assertEqual(len(shots), want)
        self.assertTrue(all(o.orbit_radius > 0 and o.orbit_speed != 0 for o in shots))

    def test_does_not_overspawn_on_repeated_updates(self):
        w = Weapon("ember_ring", get_content().weapon("ember_ring"))
        shots = []
        for _ in range(10):
            w.update(0.016, ctx([FakeTarget(60, 0)], shots))
        self.assertEqual(len(shots), w._projectile_count())

    def test_extra_projectile_bonus_adds_an_orbiter_and_respaces(self):
        w = Weapon("ember_ring", get_content().weapon("ember_ring"))
        shots = []
        w.update(0.016, ctx([FakeTarget(60, 0)], shots))
        w.bonus["projectile_count"] = 1
        w.update(0.016, ctx([FakeTarget(60, 0)], shots))
        self.assertEqual(len(shots), w._projectile_count())
        angles = sorted(o.orbit_angle for o in shots)
        # evenly spaced around the circle
        gaps = [b - a for a, b in zip(angles, angles[1:])]
        for g in gaps:
            self.assertAlmostEqual(g, math.tau / len(shots), places=3)


    def test_an_orbiter_is_never_spent_by_a_hit(self):
        """`pierce` is a shot's budget; an orbiter has none to spend. The
        Rod carries `pierce: 0` into the Arcane Storm forge, and before this
        each mote died on its first touch and was replanted at the hero's
        feet next frame -- 2 787 hits in ten seconds on the dummy."""
        from entities.projectile import Projectile
        anchor = pygame.Vector2(0, 0)
        o = Projectile()
        o.reset(pos=anchor, vel=pygame.Vector2(), damage=5, radius=8, lifetime=999,
                pierce=0, anchor=anchor, orbit_radius=100, orbit_speed=2.0,
                rehit_interval=0.5, weapon_id="magic_rod")
        o.active = True
        for _ in range(3):
            o.on_hit()
        self.assertTrue(o.active)
        self.assertTrue(o.is_orbiter)
        s = Projectile()
        s.reset(pos=anchor, vel=pygame.Vector2(1, 0), damage=5, radius=8,
                lifetime=1.0, pierce=0, weapon_id="bow")
        s.active = True
        s.on_hit()
        self.assertFalse(s.active)                     # a plain shot still is

    def test_a_recycled_orbiter_is_not_reclaimed(self):
        """Projectiles are pooled. An orbiter retired by something other
        than the weapon can be handed to another weapon and come back
        `active`; the maintainer must not treat it as its own and rewrite
        its radius and damage -- that is how the Hammer's blow became a 6 px
        mote and never landed."""
        w = Weapon("ember_ring", get_content().weapon("ember_ring"))
        want = w._projectile_count()
        shots = []
        w.update(0.016, ctx([FakeTarget(60, 0)], shots))
        gone = shots[0]
        gone.active = False                            # retired from outside
        gone.active = True                             # ...and recycled:
        gone.weapon_id, gone.orbit_speed, gone.radius, gone.damage = "hammer", 0.0, 65.0, 40.0
        w.update(0.016, ctx([FakeTarget(60, 0)], shots))
        self.assertEqual(len(shots), want + 1)         # a fresh mote replaced it
        self.assertNotIn(gone, w._orbiters)
        self.assertEqual((gone.radius, gone.damage), (65.0, 40.0))


class ChainTests(unittest.TestCase):
    def test_chain_weapon_tags_projectile_with_chain_charges(self):
        w, d = chain_weapon()
        shots = []
        w.update(0.016, ctx([FakeTarget(200, 0)], shots))
        self.assertEqual(shots[0].chain_left, d["chain_count"])
        self.assertGreater(shots[0].chain_range, 0)

    def test_fire_tags_the_projectile_with_its_weapon_id_not_a_look(self):
        # the logic layer forwards identity only; colour / style are resolved
        # from data/weapons/weapon_visuals.json on the spawn side.
        w = Weapon("magic_rod", get_content().weapon("magic_rod"))
        shots = []
        w.update(0.016, ctx([FakeTarget(200, 0)], shots))
        self.assertEqual(shots[0].weapon_id, "magic_rod")
        self.assertNotIn("color", shots[0].__dict__)
        self.assertNotIn("style", shots[0].__dict__)

    def test_weapon_visuals_carry_the_look(self):
        c = get_content()
        self.assertEqual(c.weapon_visual("bow").style, "arrow")
        self.assertEqual(c.weapon_visual("sword").style, "cone")
        self.assertTrue(c.weapon_visual("sword").fx["slash"])
        self.assertEqual(c.weapon_visual("daggers").fx["slash"], ["daggers_stab"])   # the crescent is parked
        self.assertEqual(c.weapon_visual("hammer").style, "")      # CR1: the blow is hidden
        self.assertEqual(c.weapon_visual("ember_ring").style, "")
        av = c.weapon_visual("magic_rod")
        self.assertEqual(av.style, "arcane")
        self.assertEqual(av.fx["dust_tint"], [90, 140, 255])


class MainWeaponAttackAnimTests(unittest.TestCase):
    """The hero attack animation syncs to `weapons[0]` (the starting weapon)
    only -- a picked-up second weapon firing must not drive it."""

    def _playing(self):
        from game.game import Game
        from game.states.menu_state import MenuState
        from game.states.playing.core.state import PlayingState
        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        g.state_machine.change(MenuState(g))
        from tests.boot import start_run
        p = start_run(g, SEED)         # through the loading screen
        assert isinstance(p, PlayingState)
        p._spawn_enemy("skull", at=p.player.pos + pygame.Vector2(25, 0))   # inside the sword's reach
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
            Weapon("magic_rod", get_content().weapon("magic_rod")))
        p.player._attack_t = 0.0
        before = len(p.projectiles)
        p._phase_combat(0.5)
        self.assertGreater(len(p.projectiles), before, "the secondary weapon never fired")
        self.assertEqual(p.player._attack_t, 0.0, "secondary weapon drove the attack anim")
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
