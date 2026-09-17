"""What a hostile shot is *drawn* as, and whether it pierces.

R1 of `documentation/journals/enemy_roster_expansion_journal.md`. Until it
landed, `TransientFx.fire_hostile` took only `pos / vel / damage / radius`, so
every enemy shot in the game was the same red-tinted `arrow` however the enemy
was armed -- which is why the slingshot gnome's own acorn art had sat unread
since it was delivered. `Projectile.reset` had always accepted `style`, `fx`
and `pierce`; that one call site was the only thing in the way.

These tests pin both halves: the defaults still produce exactly the old shot,
and an enemy whose JSON block names ammunition gets it all the way through to
the projectile.
"""
import os
import random
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.ai import build_behavior
from entities.ai import Blackboard
from entities.ai.components import FireProjectile
from game.content import get_content

DT = 1 / 60
RANGED_IDS = ("slingshot_gnome", "gnoll", "harpoon_shark")


def _actor(pos=(0.0, 0.0)):
    return SimpleNamespace(pos=pygame.Vector2(pos), vel=pygame.Vector2(),
                           radius=12.0, speed=80.0, alive=True,
                           contact_damage=1.0, facing=1, bb=Blackboard())


def _ctx(fired, player=(200.0, 0.0)):
    return SimpleNamespace(
        dt=DT, now=0.0, player_pos=pygame.Vector2(player), player=object(),
        rng=random.Random(0),
        nav_dir=lambda p, r: pygame.Vector2(),
        neighbors=lambda p, r: [], obstacles_near=lambda p, r: [],
        is_walkable=lambda p, r: True, resolve_movement=lambda a, b, r, **kw: b,
        fire_projectile=lambda **kw: fired.append(kw),
        summon=lambda i, p, n: None,
        explosion=lambda p, r, d: None,
        spawn_hazard=lambda p, r, dps, dur, tick=None, sprite=None: None,
        report_damage=lambda a: None)


def _fire_once(component):
    """Tick `component` until it emits, and return the one call's kwargs."""
    fired = []
    component.key = "t#0:FireProjectile"
    actor, ctx = _actor(), _ctx(fired)
    for _ in range(600):
        component.tick(actor, ctx, ctx, None)
        if fired:
            return fired[0]
    raise AssertionError("the component never fired")


class ComponentTests(unittest.TestCase):
    def test_an_unarmed_component_fires_the_shot_it_always_did(self):
        kw = _fire_once(FireProjectile(interval=0.1, damage=7, speed=200, radius=6))
        self.assertEqual(kw["style"], "")
        self.assertIsNone(kw["fx"])
        self.assertEqual(kw["pierce"], 0)

    def test_style_rig_and_pierce_reach_the_shot(self):
        kw = _fire_once(FireProjectile(interval=0.1, damage=7, speed=200, radius=6,
                                       style="spin", rig="gnoll_bone", pierce=2))
        self.assertEqual(kw["style"], "spin")
        self.assertEqual(kw["fx"], {"rig": "gnoll_bone"})
        self.assertEqual(kw["pierce"], 2)

    def test_a_style_without_a_rig_sends_no_fx(self):
        """`fx={"rig": ""}` would make `thrown` and `spin` look up an empty
        rig every frame rather than falling back once."""
        kw = _fire_once(FireProjectile(interval=0.1, damage=7, speed=200,
                                       radius=6, style="bolt"))
        self.assertIsNone(kw["fx"])


class BehaviourTests(unittest.TestCase):
    """`kite_shoot` reads the ammunition off the enemy's JSON block."""

    def _fire_from_cfg(self, cfg):
        fired = []
        beh = build_behavior("kite_shoot", cfg)
        actor, ctx = _actor(), _ctx(fired, player=(cfg.get("prefer_distance", 240), 0.0))
        for _ in range(900):
            beh.tick(actor, ctx, ctx)
            if fired:
                return fired[0]
        raise AssertionError("the behaviour never fired")

    def test_a_block_with_no_shot_keys_is_untouched(self):
        kw = self._fire_from_cfg({"prefer_distance": 260, "shoot_interval": 0.2})
        self.assertEqual(kw["style"], "")
        self.assertIsNone(kw["fx"])
        self.assertEqual(kw["pierce"], 0)

    def test_the_shot_keys_are_carried_through(self):
        kw = self._fire_from_cfg({"prefer_distance": 260, "shoot_interval": 0.2,
                                  "shot_style": "thrown", "shot_rig": "harpoon_spear",
                                  "shot_pierce": 2, "shot_radius": 8})
        self.assertEqual(kw["style"], "thrown")
        self.assertEqual(kw["fx"], {"rig": "harpoon_spear"})
        self.assertEqual(kw["pierce"], 2)
        self.assertEqual(kw["radius"], 8)


class RosterTests(unittest.TestCase):
    """The shipped data, not a fixture: every ranged enemy names ammunition
    that exists, so a typo fails here rather than at minute eight."""

    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        cls.enemies = get_content().enemies
        cls.sprites = get_content().sprites

    def test_every_ranged_enemy_names_a_rig_that_exists(self):
        for eid in RANGED_IDS:
            with self.subTest(enemy=eid):
                cfg = self.enemies[eid]
                rig = cfg.get("shot_rig")
                self.assertTrue(rig, f"{eid} names no shot rig")
                self.assertIn(rig, self.sprites, f"{eid}: unknown rig {rig!r}")

    def test_no_ranged_enemy_still_fires_the_generic_arrow(self):
        """The point of R1: the acorn, the bone and the harpoon all exist, so
        nothing ranged should be falling back to the shared red arrow."""
        for eid in RANGED_IDS:
            with self.subTest(enemy=eid):
                self.assertIn(self.enemies[eid].get("shot_style"), ("spin", "thrown"))

    def test_a_spin_rig_carries_the_strip_the_style_plays(self):
        from game.assets import get_assets
        assets = get_assets()
        for eid in RANGED_IDS:
            cfg = self.enemies[eid]
            if cfg.get("shot_style") != "spin":
                continue
            with self.subTest(enemy=eid):
                self.assertGreater(assets.frame_count(cfg["shot_rig"], "spin"), 1)

    def test_a_thrown_rig_declares_the_heading_its_art_points_in(self):
        for eid in RANGED_IDS:
            cfg = self.enemies[eid]
            if cfg.get("shot_style") != "thrown":
                continue
            with self.subTest(enemy=eid):
                self.assertIn("heading_deg", self.sprites[cfg["shot_rig"]])

    def test_the_two_new_enemies_have_their_full_animation_set(self):
        from game.assets import get_assets
        assets = get_assets()
        for eid in ("gnoll", "harpoon_shark"):
            with self.subTest(enemy=eid):
                self.assertEqual(self.enemies[eid]["sprite"], eid)
                for anim in ("idle", "walk", "attack"):
                    self.assertGreater(assets.frame_count(eid, anim), 0,
                                       f"{eid} has no {anim}")

    def test_only_the_harpoon_pierces(self):
        """Gaffjaw's spear running through a crowd is its whole identity; if
        every ranged enemy picked it up the trait would stop reading."""
        piercing = [e for e in RANGED_IDS if self.enemies[e].get("shot_pierce", 0)]
        self.assertEqual(piercing, ["harpoon_shark"])
