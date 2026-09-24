"""The gnome split: a melee Hammer Gnome, and a Beekeeper whose torch swing
summons and hits on the same beat.

`documentation/journals/gnome_split_journal.md`. The point of `path_chase_summon`
is that the summon stops being an invisible timer: plain `summoner` holds range
in a single `move` state, and `Enemy._anim_name()` only returns "attack" while
the machine sits in `telegraph`/`attack`, so the old Beekeeper's sprite never
animated when it summoned. Both payloads now land on one transition, which is
what makes the animation and the event the same thing.
"""
import os
import random
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.ai import Blackboard, build_behavior
from game.content import get_content

DT = 1 / 60


def _actor(cfg, pos=(0.0, 0.0)):
    return SimpleNamespace(
        pos=pygame.Vector2(pos), vel=pygame.Vector2(), radius=cfg["radius"],
        speed=cfg["speed"], alive=True, contact_damage=cfg["contact_damage"],
        _base_contact=cfg["contact_damage"], contact_cd=0.0, facing=1,
        bb=Blackboard())


def _ctx(sink, player=(20.0, 0.0)):
    return SimpleNamespace(
        dt=DT, now=0.0, player_pos=pygame.Vector2(player), player=object(),
        rng=random.Random(0),
        nav_dir=lambda p, r: pygame.Vector2(1, 0),
        neighbors=lambda p, r: [], obstacles_near=lambda p, r: [],
        is_walkable=lambda p, r: True, resolve_movement=lambda a, b, r, **kw: b,
        fire_projectile=lambda **kw: None,
        summon=lambda i, p, n: sink["summon"].append((i, int(n))),
        melee_hit=lambda pos, rad, dmg, life: sink["hit"].append(
            (pygame.Vector2(pos), rad, dmg, life)),
        explosion=lambda p, r, d: None,
        spawn_hazard=lambda p, r, dps, dur, tick=None, sprite=None: None,
        report_damage=lambda a: None)


def _drive(cfg, frames=400, player=(20.0, 0.0)):
    """Tick the enemy's own behaviour with the player in contact range."""
    sink = {"summon": [], "hit": [], "states": []}
    beh = build_behavior(cfg["behavior"], cfg)
    actor, ctx = _actor(cfg), _ctx(sink, player)
    for _ in range(frames):
        sink["states"].append(beh.state_of(actor))
        beh.tick(actor, ctx, ctx)
    return sink


class BeekeeperSwingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = get_content().enemies["torch_goblin"]

    def test_the_swing_summons_and_hits_on_the_same_beat(self):
        """One transition, both payloads -- so the bees appear exactly when
        the torch comes round, not on a timer of their own."""
        s = _drive(self.cfg)
        self.assertEqual(len(s["summon"]), len(s["hit"]))
        self.assertTrue(s["summon"], "the Beekeeper never swung")

    def test_it_summons_what_its_data_says_and_how_many(self):
        s = _drive(self.cfg)
        self.assertEqual(set(s["summon"]),
                         {(self.cfg["summon_id"], self.cfg["summon_count"])})

    def test_the_swing_walks_the_telegraph_cycle(self):
        """The states the sprite reads to play its attack animation."""
        s = _drive(self.cfg)
        self.assertEqual(set(s["states"]),
                         {"chase", "telegraph", "attack", "recover"})

    def test_the_hitbox_lands_in_front_and_lasts_the_swing(self):
        s = _drive(self.cfg)
        pos, radius, damage, life = s["hit"][0]
        self.assertGreater(pos.x, 0.0)                      # toward the player
        self.assertAlmostEqual(radius, self.cfg["radius"] / 2.0)
        self.assertEqual(damage, self.cfg["contact_damage"])
        self.assertAlmostEqual(life, self.cfg["attack_active"])

    def test_the_swing_damage_is_a_garnish_not_a_melee_threat(self):
        """The owner's brief: 'a small one on top of the summons'."""
        husk = get_content().enemies["skull"]
        self.assertLess(self.cfg["contact_damage"], husk["contact_damage"])

    def test_it_swings_far_outside_melee_reach(self):
        """Changed deliberately (owner, 2026-09-17): the swing used to wait
        for contact range -- about 26 px for this body. It no longer does.
        400 px is fifteen times the old trigger and well inside aggro."""
        far = _drive(self.cfg, frames=600, player=(400.0, 0.0))
        self.assertTrue(far["summon"], "the Beekeeper never swung at range")
        self.assertEqual(len(far["summon"]), len(far["hit"]))

    def test_aggro_still_gates_it(self):
        """"No range gate" is about the *swing*, not about noticing the
        player: `with_aggro` wraps every behaviour, so a Beekeeper that has
        never seen the player stands idle rather than summoning into an empty
        island."""
        beyond = self.cfg["aggro_range"] * 4
        self.assertEqual(_drive(self.cfg, frames=600,
                                player=(beyond, 0.0))["summon"], [])

    def test_the_swing_lands_on_a_fixed_cadence(self):
        """One cycle is telegraph + active + recover + cooldown, and nothing
        about the player's position enters it."""
        c = self.cfg
        period = (c["attack_telegraph"] + c["attack_active"]
                  + c["attack_recover"] + c["attack_cooldown"])
        frames = int(period * 3.5 / DT)
        near = _drive(c, frames=frames)
        far = _drive(c, frames=frames, player=(400.0, 0.0))
        self.assertEqual(len(near["summon"]), len(far["summon"]))
        self.assertGreaterEqual(len(near["summon"]), 3)

    def test_a_swing_out_of_reach_still_drops_its_hitbox(self):
        """Both payloads fire on the same transition whatever the distance --
        the hitbox simply misses, rather than being skipped."""
        far = _drive(self.cfg, frames=600, player=(400.0, 0.0))
        pos, radius, damage, _life = far["hit"][0]
        self.assertAlmostEqual(radius, self.cfg["radius"] / 2.0)
        self.assertEqual(damage, self.cfg["contact_damage"])
        self.assertAlmostEqual(pos.length(), self.cfg["radius"], places=3)

    def test_the_body_bite_is_disabled_so_only_the_swing_hurts(self):
        self.assertFalse(self.cfg["contact_damage_enabled"])


class HammerGnomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.enemies = get_content().enemies
        cls.gnome = cls.enemies["hammer_gnome"]
        cls.husk = cls.enemies["skull"]

    def test_it_runs_the_husks_beat(self):
        self.assertEqual(self.gnome["behavior"], self.husk["behavior"])

    def test_it_is_a_tougher_harder_hitting_slower_husk(self):
        """The shape of the gnome against the Husk, not its numbers
        (TST-005.4): the data is tuned by hand, so only the relation is
        pinned."""
        self.assertGreater(self.gnome["hp"], self.husk["hp"])
        self.assertGreater(self.gnome["contact_damage"], self.husk["contact_damage"])
        self.assertLess(self.gnome["speed"], self.husk["speed"])

    def test_it_is_heavier_than_the_husk(self):
        self.assertGreater(self.gnome["weight"], self.husk["weight"])

    def test_it_only_chases_and_swings(self):
        """No summoning: that moved to the Beekeeper."""
        self.assertNotIn("summon_id", self.gnome)

    def test_it_swings_a_hitbox_like_the_husk(self):
        s = _drive(self.gnome)
        self.assertTrue(s["hit"])
        self.assertEqual(s["summon"], [])
        _pos, radius, damage, _life = s["hit"][0]
        self.assertAlmostEqual(radius, self.gnome["radius"] / 2.0)
        self.assertEqual(damage, self.gnome["contact_damage"])


class RigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        cls.enemies = get_content().enemies
        cls.sprites = get_content().sprites

    def test_both_gnomes_carry_a_full_animation_set(self):
        from game.assets import get_assets
        assets = get_assets()
        for eid in ("hammer_gnome", "torch_goblin"):
            for anim in ("idle", "walk", "attack"):
                with self.subTest(enemy=eid, anim=anim):
                    self.assertGreater(assets.frame_count(eid, anim), 0)

    def test_the_old_gnome_rig_is_gone_but_the_slingshot_gnome_stays(self):
        self.assertNotIn("gnome", self.sprites)
        self.assertIn("slingshot_gnome", self.sprites)

    def test_the_torch_goblin_faces_right_like_the_rest_of_the_pack(self):
        self.assertEqual(self.sprites["torch_goblin"]["face"], "right")


class BeeSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bee = get_content().enemies["bumblebee"]
        cls.rig = get_content().sprites["bumblebee"]

    def test_the_drawn_bee_covers_its_collider(self):
        """The sprite is drawn at least as wide as the body it stands for,
        whatever the two are tuned to (TST-005.4)."""
        self.assertGreaterEqual(self.rig["scale"][0], 2 * self.bee["radius"])

    def test_the_drawn_size_keeps_the_art_s_proportions(self):
        """`scale` follows the sheet's `content` box, so resizing the bee
        does not stretch it."""
        _x, _y, cw, ch = self.rig["content"]
        sw, sh = self.rig["scale"]
        self.assertAlmostEqual(sw / sh, cw / ch, delta=0.05 * cw / ch)

    def test_the_bee_is_still_a_small_body(self):
        """The bee's radius stays under the small nav class's clearance, so
        placement and the nav classes are untouched."""
        from world.nav.field import _NAV_CLASSES
        small = min(float(c[3]) for c in _NAV_CLASSES)
        self.assertLessEqual(self.bee["radius"], small)

    def test_every_summoner_gets_the_bigger_bee(self):
        """The size is on the enemy, not on whoever summons it -- the boss's
        eight come out the same size as the Beekeeper's three."""
        import json
        from pathlib import Path
        bosses = json.loads(
            (Path(__file__).resolve().parents[3] / "data" / "enemies" /
             "bosses.json").read_text(encoding="utf-8"))
        summoned = {p["summon_id"] for b in bosses.values()
                    for p in b.get("patterns", []) if "summon_id" in p}
        self.assertIn("bumblebee", summoned)
