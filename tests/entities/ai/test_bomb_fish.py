"""The Bloat throws its bomb instead of being one.

`documentation/journals/bomb_fish_journal.md`. Its `shoot.png` has been wired
as the rig's `attack` strip since the sprite shipped, but `exploder` never
enters a telegraph or attack state, so `Enemy._anim_name()` never returned
"attack" and those seven frames had never played. The art was always a fish
lobbing a bomb.

What is new underneath: a hostile shot can now be a *bomb* -- it flies, stops,
fuses and detonates -- and the blast lands on the player's side of the fight
rather than the hero's.
"""
import os
import random
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.ai import Blackboard, build_behavior
from entities.projectile import Projectile
from game import config
from game.content import get_content

DT = 1 / 60


def _actor(cfg, pos=(0.0, 0.0)):
    return SimpleNamespace(
        pos=pygame.Vector2(pos), vel=pygame.Vector2(), radius=cfg["radius"],
        speed=cfg["speed"], alive=True, contact_damage=cfg["contact_damage"],
        _base_contact=cfg["contact_damage"], contact_cd=0.0, facing=1,
        bb=Blackboard())


def _fire(cfg, player=None):
    """Tick the enemy's own behaviour until it throws, and return the call."""
    fired = []
    beh = build_behavior(cfg["behavior"], cfg)
    at = player or (cfg["prefer_distance"], 0.0)
    actor = _actor(cfg)
    ctx = SimpleNamespace(
        dt=DT, now=0.0, player_pos=pygame.Vector2(at), player=object(),
        rng=random.Random(0),
        nav_dir=lambda p, r: pygame.Vector2(),
        neighbors=lambda p, r: [], obstacles_near=lambda p, r: [],
        is_walkable=lambda p, r: True, resolve_movement=lambda a, b, r, **kw: b,
        fire_projectile=lambda **kw: fired.append(kw),
        summon=lambda i, p, n: None, melee_hit=lambda *a: None,
        explosion=lambda p, r, d: None,
        spawn_hazard=lambda *a, **kw: None, report_damage=lambda a: None)
    for _ in range(1200):
        beh.tick(actor, ctx, ctx)
        if fired:
            return fired[0]
    raise AssertionError("the Bloat never threw")


class ThrowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = get_content().enemies["bomb_fish"]

    def test_it_throws_instead_of_detonating_itself(self):
        self.assertEqual(self.cfg["behavior"], "kite_shoot")
        self.assertNotEqual(self.cfg["behavior"], "exploder")

    def test_the_shot_is_a_bomb(self):
        self.assertEqual(_fire(self.cfg)["style"], "bomb")

    def test_the_bomb_is_tinted_the_hostile_red(self):
        """"similar to the previous enemy arrow" -- the same constant the
        hostile arrow wears, so an incoming bomb reads as incoming."""
        self.assertEqual(tuple(_fire(self.cfg)["fx"]["tint"]),
                         tuple(config.HOSTILE_ARROW_TINT))

    def test_the_bomb_carries_its_blast_and_fuse(self):
        c, kw = self.cfg, _fire(self.cfg)
        self.assertAlmostEqual(kw["blast_radius"], c["shot_blast_radius"])
        self.assertAlmostEqual(kw["stop_after"], c["shot_stop_after"])
        self.assertAlmostEqual(kw["lifetime"], c["shot_lifetime"])

    def test_the_bomb_scores_no_direct_hit(self):
        """`inert`: a bomb is its blast, not a bullet. Otherwise it would
        damage on contact *and* explode."""
        self.assertTrue(_fire(self.cfg)["inert"])

    def test_it_fuses_before_it_blows(self):
        c = self.cfg
        self.assertGreater(c["shot_lifetime"], c["shot_stop_after"])

    def test_an_ordinary_kiter_is_untouched_by_all_of_this(self):
        """Slinger names none of the bomb keys and must still fire a plain,
        non-exploding, non-inert shot."""
        kw = _fire(get_content().enemies["slingshot_gnome"])
        self.assertEqual(kw["blast_radius"], 0.0)
        self.assertEqual(kw["stop_after"], 0.0)
        self.assertFalse(kw["inert"])
        self.assertNotIn("tint", kw["fx"] or {})


class FlightTests(unittest.TestCase):
    """The bomb's life, driven through the real `Projectile`."""

    @classmethod
    def setUpClass(cls):
        cls.cfg = get_content().enemies["bomb_fish"]

    def _bomb(self):
        c = self.cfg
        p = Projectile()
        p.reset(pos=pygame.Vector2(0, 0), vel=pygame.Vector2(c["shot_speed"], 0),
                damage=c["shoot_damage"], radius=c["shot_radius"],
                lifetime=c["shot_lifetime"], hostile=True, style="bomb",
                fx={"tint": tuple(config.HOSTILE_ARROW_TINT)},
                stop_after=c["shot_stop_after"],
                blast_radius=c["shot_blast_radius"], inert=True)
        # `reset` does not activate: the pool's `acquire()` does, and these
        # tests build the projectile directly.
        p.active = True
        return p

    def test_it_halts_partway_and_then_expires(self):
        c, p = self.cfg, self._bomb()
        for _ in range(int(c["shot_stop_after"] / DT) + 2):
            p.update(DT)
        self.assertAlmostEqual(p.vel.length(), 0.0, places=6)
        self.assertTrue(p.active, "it expired before it even landed")
        travelled = p.pos.x
        for _ in range(int(c["shot_lifetime"] / DT) + 4):
            p.update(DT)
        self.assertFalse(p.active)
        self.assertAlmostEqual(p.pos.x, travelled, places=3)   # it stayed put

    def test_the_landing_spot_is_inside_the_range_it_holds(self):
        """It must not lob past the player it is kiting."""
        c = self.cfg
        self.assertLess(c["shot_speed"] * c["shot_stop_after"],
                        c["prefer_distance"] * 1.8)


class DrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))

    def _draw(self, fx):
        from game.assets import get_assets
        from game.states.playing.visual.drawctx import DrawCtx
        from game.states.playing.visual.projectiles import draw_projectile
        p = Projectile()
        p.reset(pos=pygame.Vector2(0, 0), vel=pygame.Vector2(120, 0), damage=5,
                radius=9, lifetime=2.0, hostile=True, style="bomb", fx=fx)
        surface = pygame.Surface((160, 160), pygame.SRCALPHA)
        draw_projectile(surface, 80, 80, p, DrawCtx(assets=get_assets(), now=0.0,
                                                    zoom=1.0), default="arrow")
        return surface

    def _pixels(self, surface):
        surface.lock()
        out = [surface.get_at((x, y)) for y in range(160) for x in range(160)
               if surface.get_at((x, y))[3] > 0]
        surface.unlock()
        return out

    def test_the_tinted_bomb_is_redder_than_the_plain_one(self):
        """The tint is additive, not a multiply: a multiply on a dark bomb
        gives near-black, which is why `frame(tint=)` is not used here."""
        plain = self._pixels(self._draw(None))
        red = self._pixels(self._draw({"tint": tuple(config.HOSTILE_ARROW_TINT)}))
        self.assertTrue(plain and red)
        mean = lambda px, i: sum(p[i] for p in px) / len(px)
        self.assertGreater(mean(red, 0), mean(plain, 0))        # more red
        self.assertGreater(mean(red, 0) - mean(red, 2),
                           mean(plain, 0) - mean(plain, 2))     # and redder

    def test_an_untinted_bomb_still_draws(self):
        self.assertTrue(self._pixels(self._draw(None)))


class RigTests(unittest.TestCase):
    def test_the_shoot_strip_is_finally_reachable(self):
        """`kite_shoot` has no telegraph state either, so this pins the thing
        that made the art dead rather than pretending it is now animated: the
        strip exists and is wired. Driving it on screen is a follow-up."""
        from game.assets import get_assets
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        self.assertGreater(get_assets().frame_count("bomb_fish", "attack"), 0)

    def test_it_still_pops_when_killed(self):
        """The corpse blast is not the attack and was not removed: a fish
        full of bombs still goes off when it dies."""
        c = get_content().enemies["bomb_fish"]
        self.assertGreater(c["explode_radius"], 0)
        self.assertGreater(c["explode_damage"], 0)


class ShakeTests(unittest.TestCase):
    """The thrown bomb no longer shakes the screen (owner, 2026-09-19); the
    corpse blast on death still does. Both go through the same hostile
    `explosion` helper, so this pins which side of the `shake` switch each
    caller is on."""

    def _ps(self):
        from tests.combat.fakes import fake_ps
        ps = fake_ps()
        ps.shakes = []
        ps.shake = SimpleNamespace(add=lambda amt: ps.shakes.append(amt))
        # far enough that neither blast reaches the hero: only the shake matters
        ps.player.pos = pygame.Vector2(10_000, 10_000)
        return ps

    def test_a_landed_bomb_detonates_without_a_shake(self):
        """Driven through the hostile loop, as in play: a spent bomb in
        `ps.hostiles` bursts on the player's side and leaves the screen
        still."""
        ps = self._ps()
        c = get_content().enemies["bomb_fish"]
        p = ps.hostiles.acquire()
        p.reset(pos=pygame.Vector2(0, 0), vel=pygame.Vector2(),
                damage=c["shoot_damage"], radius=c["shot_radius"],
                lifetime=DT / 2, hostile=True, style="bomb",
                blast_radius=c["shot_blast_radius"], inert=True)
        ps.fx.update_projectiles(DT)
        self.assertTrue(p.detonated, "the spent bomb never went off")
        self.assertEqual(len(ps._explosions), 1)
        self.assertEqual(ps.shakes, [])

    def test_the_corpse_blast_still_shakes(self):
        """`combat.py` calls the helper with no `shake` argument for the
        death pop, and that default stays on."""
        ps = self._ps()
        c = get_content().enemies["bomb_fish"]
        ps.fx.explosion(pygame.Vector2(0, 0), c["explode_radius"],
                        c["explode_damage"])
        self.assertEqual(len(ps.shakes), 1)
