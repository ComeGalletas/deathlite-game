"""The Whirlspear: a melee sweep, and the game's first enemy with two swings.

`documentation/journals/spear_goblin_journal.md`. Two things here are new to
the codebase and both are worth pinning:

* the hitbox is a disc **centred on the actor**, not the small front-facing
  one `path_chase_attack` drops. The art is a full 360 degree spin, so there
  is no safe side -- only a safe distance;
* the machine picks *which* attack strip plays. `Enemy._anim_name()` used to
  answer "attack" and nothing else, so a second swing had no way to be seen.
"""
import os
import random
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.ai import Blackboard, build_behavior
from entities.ai.machine import ATTACK_SLOT
from game.content import get_content

DT = 1 / 60


def _actor(cfg, pos=(0.0, 0.0)):
    return SimpleNamespace(
        pos=pygame.Vector2(pos), vel=pygame.Vector2(), radius=cfg["radius"],
        speed=cfg["speed"], alive=True, contact_damage=cfg["contact_damage"],
        _base_contact=cfg["contact_damage"], contact_cd=0.0, facing=1,
        bb=Blackboard())


def _ctx(sink, player):
    return SimpleNamespace(
        dt=DT, now=0.0, player_pos=pygame.Vector2(player), player=object(),
        rng=random.Random(0),
        nav_dir=lambda p, r: pygame.Vector2(1, 0),
        neighbors=lambda p, r: [], obstacles_near=lambda p, r: [],
        is_walkable=lambda p, r: True, resolve_movement=lambda a, b, r, **kw: b,
        fire_projectile=lambda **kw: None, summon=lambda i, p, n: None,
        melee_hit=lambda pos, rad, dmg, life: sink["hit"].append(
            (pygame.Vector2(pos), rad, dmg, life)),
        explosion=lambda p, r, d: None,
        spawn_hazard=lambda p, r, dps, dur, tick=None, sprite=None: None,
        report_damage=lambda a: None)


def _drive(cfg, frames=900, player=(18.0, 0.0)):
    """Tick the enemy in contact range, recording one entry per *swing*
    rather than per frame: the anim it named on entering `telegraph`, and how
    many frames that wind-up lasted."""
    sink = {"hit": [], "anims": [], "windups": [], "states": []}
    beh = build_behavior(cfg["behavior"], cfg)
    actor, ctx = _actor(cfg), _ctx(sink, player)
    prev = None
    for _ in range(frames):
        st = beh.state_of(actor)
        sink["states"].append(st)
        if st == "telegraph":
            if prev != "telegraph":
                sink["anims"].append(actor.bb.slot(ATTACK_SLOT).get("anim"))
                sink["windups"].append(0)
            sink["windups"][-1] += 1
        prev = st
        beh.tick(actor, ctx, ctx)
    return sink


class SweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = get_content().enemies["spear_goblin"]

    def test_the_hitbox_is_centred_on_the_body_not_in_front(self):
        """The difference from every other melee enemy: no safe side."""
        s = _drive(self.cfg)
        self.assertTrue(s["hit"], "the Whirlspear never swung")
        for pos, _r, _d, _l in s["hit"]:
            self.assertAlmostEqual(pos.length(), 0.0, places=3)

    def test_the_ring_is_wider_than_a_poke_would_be(self):
        s = _drive(self.cfg)
        poke = self.cfg["radius"] / 2.0
        for _pos, radius, _d, _l in s["hit"]:
            self.assertGreater(radius, poke)

    def test_the_fast_sweep_reaches_what_its_data_says(self):
        s = _drive(self.cfg)
        want = self.cfg["radius"] + self.cfg["sweep_reach"]
        fast = [r for _p, r, _d, _l in s["hit"] if r == want]
        self.assertTrue(fast, f"no sweep at radius {want}")

    def test_the_hitbox_lives_for_the_swing(self):
        s = _drive(self.cfg)
        for _p, _r, _d, life in s["hit"]:
            self.assertAlmostEqual(life, self.cfg["attack_active"])


class TwoSwingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = get_content().enemies["spear_goblin"]

    def test_every_nth_swing_is_the_heavy_whirl(self):
        c = self.cfg
        s = _drive(c)
        strong_r = c["radius"] + c["strong_reach"]
        fast_r = c["radius"] + c["sweep_reach"]
        seq = ["strong" if r == strong_r else "fast" for _p, r, _d, _l in s["hit"]]
        self.assertGreaterEqual(len(seq), c["strong_every"] * 2,
                                "not enough swings to see the pattern")
        for i, kind in enumerate(seq, 1):
            with self.subTest(swing=i):
                self.assertEqual(kind, "strong" if i % c["strong_every"] == 0
                                 else "fast")
        self.assertNotEqual(strong_r, fast_r)

    def test_the_heavy_whirl_hits_harder(self):
        c = self.cfg
        s = _drive(c)
        strong_r = c["radius"] + c["strong_reach"]
        dmg = {r: d for _p, r, d, _l in s["hit"]}
        self.assertAlmostEqual(dmg[strong_r],
                               c["contact_damage"] * c["strong_damage_mult"])
        self.assertAlmostEqual(dmg[c["radius"] + c["sweep_reach"]],
                               c["contact_damage"])

    def test_the_heavy_whirl_is_read_for_longer(self):
        """A ring cannot be side-stepped, only backed out of, so the bigger
        one has to be announced for longer."""
        c = self.cfg
        self.assertGreater(c["strong_telegraph"], c["attack_telegraph"])
        # and the cycle honours it -- the heavy swing's wind-up really is the
        # longer one, measured in frames actually spent in `telegraph`.
        s = _drive(c)
        pairs = list(zip(s["anims"], s["windups"]))[:6]
        fast = [n for a, n in pairs if a == "attack"]
        strong = [n for a, n in pairs if a == "attack_strong"]
        self.assertTrue(fast and strong, f"only one kind of swing seen: {pairs}")
        self.assertGreater(min(strong), max(fast), f"wind-ups: {pairs}")

    def test_the_swing_names_the_strip_it_wants(self):
        s = _drive(self.cfg)
        self.assertEqual(set(s["anims"]), {"attack", "attack_strong"})

    def test_the_choice_is_made_when_the_windup_starts(self):
        """Not when the hit lands -- otherwise the telegraph the player reads
        would belong to a different swing than the one that arrives."""
        c = self.cfg
        s = _drive(c)
        strong_r = c["radius"] + c["strong_reach"]
        # the nth telegraph's anim matches the nth hitbox's size
        pairs = list(zip(s["anims"], [r for _p, r, _d, _l in s["hit"]]))
        for anim, radius in pairs:
            with self.subTest(anim=anim):
                self.assertEqual(anim == "attack_strong", radius == strong_r)


class AnimVariantTests(unittest.TestCase):
    """`Enemy._anim_name()` answering more than "attack" is new shared
    behaviour, so it is checked on a real body -- including that an enemy
    whose rig has no variant strip is completely unaffected."""

    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        cls.enemies = get_content().enemies

    def _enemy(self, eid):
        from entities.enemy import Enemy
        return Enemy(eid, self.enemies[eid], 0.0, 0.0)

    def test_the_whirlspear_knows_its_variant_strip(self):
        e = self._enemy("spear_goblin")
        self.assertEqual(e._attack_anims, frozenset({"attack_strong"}))

    def test_a_single_swing_enemy_has_no_variants(self):
        for eid in ("skull", "turtle", "hammer_gnome"):
            with self.subTest(enemy=eid):
                self.assertEqual(self._enemy(eid)._attack_anims, frozenset())

    def test_the_named_strip_is_played_while_attacking(self):
        e = self._enemy("spear_goblin")
        e.bb.slot("__machine__")["state"] = "attack"
        e.bb.slot(ATTACK_SLOT)["anim"] = "attack_strong"
        self.assertEqual(e._anim_name(), "attack_strong")

    def test_an_unknown_strip_falls_back_to_plain_attack(self):
        """A typo in the data, or a sheet that never shipped, must animate
        the ordinary swing rather than nothing at all."""
        e = self._enemy("spear_goblin")
        e.bb.slot("__machine__")["state"] = "attack"
        for bad in ("attack_nope", "", None):
            with self.subTest(anim=bad):
                e.bb.slot(ATTACK_SLOT)["anim"] = bad
                self.assertEqual(e._anim_name(), "attack")

    def test_an_enemy_that_names_nothing_still_animates_its_swing(self):
        e = self._enemy("skull")
        e.bb.slot("__machine__")["state"] = "telegraph"
        self.assertEqual(e._anim_name(), "attack")


class RosterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        cls.cfg = get_content().enemies["spear_goblin"]
        cls.rig = get_content().sprites["spear_goblin"]

    def test_the_id_is_its_sprite(self):
        self.assertEqual(self.cfg["sprite"], "spear_goblin")

    def test_the_rig_declares_both_swings(self):
        from game.assets import get_assets
        assets = get_assets()
        for anim in ("idle", "walk", "attack", "attack_strong"):
            with self.subTest(anim=anim):
                self.assertGreater(assets.frame_count("spear_goblin", anim), 0)

    def test_it_faces_right_like_the_rest_of_the_pack(self):
        self.assertEqual(self.rig["face"], "right")

    def test_the_body_bite_is_disabled_so_only_the_sweep_hurts(self):
        self.assertFalse(self.cfg["contact_damage_enabled"])

    def test_it_is_the_only_sweeper(self):
        """If every melee enemy picked this up, "no safe side" would stop
        being the Whirlspear's identity."""
        sweepers = [e for e, c in get_content().enemies.items()
                    if c.get("behavior") == "path_chase_sweep"]
        self.assertEqual(sweepers, ["spear_goblin"])
