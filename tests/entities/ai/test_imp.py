"""The Imp ("Cinder"): a three-part attack that leaves fire on the ground.

`documentation/journals/imp_journal.md`. Two firsts, both pinned here:

* the attack is a **hazard**, not a hitbox or a shot -- the flame pools in
  front, sits there and bites over time, which is what the art draws;
* the animation runs `attack_start` -> `attack_loop` -> `attack_end` across
  the cycle's telegraph, attack and recover states. The tail plays during
  *recover*, which is not an attacking state, so `Enemy._anim_name()` had to
  stop gating a named strip on `_attacking`.
"""
import os
import random
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.ai import Blackboard, build_behavior
from entities.ai.machine import ATTACK_SLOT
from game.content import get_content


def _source_paths() -> dict:
    """Where the imp's art is, and where its editor source is archived."""
    root = Path(__file__).resolve().parents[3]
    return {"root": root,
            "shipped": root / "assets" / "enemies" / "imp",
            "archived": root / "assets" / "unused" / "enemies" / "imp" / "Imp.aseprite"}


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
        fire_projectile=lambda **kw: sink["shots"].append(kw),
        summon=lambda i, p, n: None,
        melee_hit=lambda pos, rad, dmg, life: sink["hits"].append(rad),
        explosion=lambda p, r, d: None,
        spawn_hazard=lambda pos, radius, dps, dur, tick=None, sprite=None:
            sink["hazards"].append((pygame.Vector2(pos), radius, dps, dur, tick, sprite)),
        report_damage=lambda a: None)


def _drive(cfg, frames=900, player=(26.0, 0.0)):
    """Tick the imp in range, recording each hazard and the strip named on
    entering every state."""
    sink = {"hazards": [], "hits": [], "shots": [], "by_state": [], "states": []}
    beh = build_behavior(cfg["behavior"], cfg)
    actor, ctx = _actor(cfg), _ctx(sink, player)
    prev = None
    for _ in range(frames):
        st = beh.state_of(actor)
        sink["states"].append(st)
        if st != prev:
            sink["by_state"].append((st, actor.bb.slot(ATTACK_SLOT).get("anim")))
        prev = st
        beh.tick(actor, ctx, ctx)
    return sink


class BreathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = get_content().enemies["imp"]

    def test_it_leaves_a_hazard_rather_than_a_hitbox_or_a_shot(self):
        s = _drive(self.cfg)
        self.assertTrue(s["hazards"], "the imp never breathed")
        self.assertEqual(s["hits"], [])
        self.assertEqual(s["shots"], [])

    def test_the_pool_lands_in_front_of_it(self):
        c = self.cfg
        s = _drive(c)
        want = c["radius"] + c["breath_offset"]
        for pos, *_rest in s["hazards"]:
            self.assertGreater(pos.x, 0.0)                  # toward the player
            self.assertAlmostEqual(pos.length(), want, places=3)

    def test_the_pool_carries_its_data(self):
        c = self.cfg
        _pos, radius, dps, dur, tick, sprite = _drive(c)["hazards"][0]
        self.assertAlmostEqual(radius, c["hazard_radius"])
        self.assertAlmostEqual(dps, c["hazard_dps"])
        self.assertAlmostEqual(dur, c["hazard_duration"])
        self.assertAlmostEqual(tick, c["hazard_tick"])

    def test_the_pool_has_no_sprite_of_its_own(self):
        """The imp's frames already draw the flame; a hazard sprite on top
        would render it twice."""
        self.assertIsNone(_drive(self.cfg)["hazards"][0][5])

    def test_the_burn_lasts_the_loop_and_the_embers(self):
        """Not just the `attack` state: the art keeps drawing fire while the
        pool breaks up, so the damage has to cover the recover too."""
        c = self.cfg
        self.assertAlmostEqual(c["hazard_duration"],
                               c["attack_active"] + c["attack_recover"], places=6)

    def test_it_does_not_breathe_out_of_range(self):
        far = _drive(self.cfg, player=(3000.0, 0.0))
        self.assertEqual(far["hazards"], [])

    def test_the_body_bite_is_disabled_so_only_the_fire_hurts(self):
        self.assertFalse(self.cfg["contact_damage_enabled"])

    def test_the_pool_stays_inside_the_drawn_flame(self):
        """The burn must never reach past fire the player can see. Measured
        half-width of the `attack_loop` pool is about 17 world px; the owner's
        35 % area cut (2026-09-17) took the radius to 15.3, so it now sits
        inside that rather than on its edge."""
        self.assertLessEqual(self.cfg["hazard_radius"], 17.0)

    def test_the_area_cut_was_an_area_cut(self):
        """A percentage on a size means area in this project, not the linear
        knob: 19 -> 15.3 is sqrt(0.65), a 35 % smaller disc."""
        import math
        before = math.pi * 19 ** 2
        after = math.pi * self.cfg["hazard_radius"] ** 2
        self.assertAlmostEqual(after / before, 0.65, places=2)

    def test_it_breathes_again_on_its_cooldown(self):
        s = _drive(self.cfg, frames=1200)
        self.assertGreaterEqual(len(s["hazards"]), 2)


class ThreePartAnimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = get_content().enemies["imp"]

    def test_each_state_names_its_own_strip(self):
        s = _drive(self.cfg)
        named = {st: anim for st, anim in s["by_state"] if anim is not None}
        self.assertEqual(named.get("telegraph"), "attack_start")
        self.assertEqual(named.get("attack"), "attack_loop")
        self.assertEqual(named.get("recover"), "attack_end")

    def test_the_name_is_cleared_when_the_cycle_ends(self):
        """Otherwise the imp would walk around holding its last flame frame."""
        s = _drive(self.cfg)
        chases = [anim for st, anim in s["by_state"] if st == "chase"]
        self.assertTrue(chases)
        self.assertEqual(set(chases[1:]), {None},
                         f"a strip survived into chase: {chases}")

    def test_the_cycle_visits_all_four_states(self):
        self.assertEqual(set(_drive(self.cfg)["states"]),
                         {"chase", "telegraph", "attack", "recover"})


class RigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        cls.cfg = get_content().enemies["imp"]
        cls.rig = get_content().sprites["imp"]

    def _enemy(self):
        from entities.enemy import Enemy
        return Enemy("imp", self.cfg, 0.0, 0.0)

    def test_the_id_is_its_sprite(self):
        self.assertEqual(self.cfg["sprite"], "imp")

    def test_every_strip_it_names_exists(self):
        from game.assets import get_assets
        assets = get_assets()
        for anim in ("idle", "walk", "attack", "attack_start",
                     "attack_loop", "attack_end"):
            with self.subTest(anim=anim):
                self.assertGreater(assets.frame_count("imp", anim), 0)

    def test_the_loop_strip_loops_and_the_other_two_do_not(self):
        anims = self.rig["anims"]
        self.assertTrue(anims["attack_loop"]["loop"])
        self.assertFalse(anims["attack_start"]["loop"])
        self.assertFalse(anims["attack_end"]["loop"])

    def test_it_faces_right_like_the_rest_of_the_pack(self):
        """Measured, not assumed: the flame's pixels sit right of the body's,
        so the imp spits forward along +x. A rig declared "left" would never
        be flipped at all -- `rendering.py` only flips when face == "right"."""
        self.assertEqual(self.rig["face"], "right")

    def test_the_body_knows_all_three_variant_strips(self):
        self.assertEqual(self._enemy()._attack_anims,
                         frozenset({"attack_start", "attack_loop", "attack_end"}))

    def test_the_tail_plays_during_recover_which_is_not_an_attack_state(self):
        e = self._enemy()
        e.bb.slot("__machine__")["state"] = "recover"
        e.bb.slot(ATTACK_SLOT)["anim"] = "attack_end"
        self.assertFalse(e._attacking)
        self.assertEqual(e._anim_name(), "attack_end")

    def test_the_editor_source_is_archived_and_not_shipped(self):
        """`.aseprite` sources are kept, and kept out of the shipped folders.

        Both halves are asserted, because both are now true in every
        checkout. The source does not sit beside the strip the game loads,
        and it *is* archived where `CREDITS.md` says it is.

        The second half used to `skipTest` itself, and the reason was a
        contradiction in the repo rather than anything about the imp.
        `CREDITS.md` promised the source was "archived ... rather than
        deleted", while `.gitignore` swept it up twice over -- once as
        `*.aseprite` ("asset cruft") and again inside the whole-folder
        `assets/unused/` exclusion. So the file lived in exactly one working
        copy and in no clone or `git worktree`, and a test that asserted the
        promise passed on one machine and failed everywhere else. Skipping
        made the suite green but checked nothing. The reserve block in
        `.gitignore` now re-includes editor sources -- 52 KB, and the source
        for art we ship -- so the promise is one the suite can hold it to.
        """
        imp = _source_paths()
        self.assertEqual(sorted(p.name for p in imp["shipped"].glob("*.aseprite")), [],
                         "an editor source is shipped beside the loaded strip")
        self.assertTrue(imp["archived"].is_file(),
                        f"the archived editor source is missing: {imp['archived']}")

    def test_credits_names_the_folder_the_source_is_archived_in(self):
        """The doc and the disk are pinned to each other, because it was
        exactly their drifting apart that hid the problem above: CREDITS
        described an arrangement `.gitignore` had quietly stopped keeping."""
        imp = _source_paths()
        credits = (imp["root"] / "assets" / "CREDITS.md").read_text(encoding="utf-8")
        self.assertIn("assets/unused/enemies/imp/", credits)


class RosterTests(unittest.TestCase):
    def test_it_is_the_only_breather(self):
        breathers = [e for e, c in get_content().enemies.items()
                     if c.get("behavior") == "path_chase_breath"]
        self.assertEqual(breathers, ["imp"])

    def test_it_is_the_only_enemy_leaving_ground_fire(self):
        """Hexcaller drops a hazard too, but from range as a cast; this is a
        contact-range breath. If a third arrives, the roster needs a look."""
        hazardous = sorted(e for e, c in get_content().enemies.items()
                           if "hazard_dps" in c)
        self.assertEqual(hazardous, ["hex_shaman", "imp"])
