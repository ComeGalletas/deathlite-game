"""Change request 2 (weapon_system_journal.md): the weapon effect sheets
moved into per-weapon folders; every rig must resolve on disk; the Sword
swings two slashes from Combat-Sheet.png, the first flipped vertically, and
alternates them by the attack's ordinal."""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import FireContext, Weapon
from game.assets import Assets, reset_assets
from game.content import get_content
from game.states.playing.projectiles import cone as cone_mod
from tests.combat.fakes import FakeEnemy

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
ASSETS = os.path.join(ROOT, "assets")


def _display():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))


class RigFilesTests(unittest.TestCase):
    """A sheet move can never silently blank an effect again."""

    def test_every_rig_sheet_exists(self):
        missing = []
        for rig, r in get_content().sprites.items():
            files = [r["file"]] if "file" in r else [a["file"] for a in r.get("anims", {}).values()]
            for f in files:
                if not os.path.exists(os.path.join(ASSETS, f)):
                    missing.append(f"{rig}: {f}")
        self.assertEqual(missing, [])

    def test_the_moved_weapon_sheets_point_into_their_folders(self):
        s = get_content().sprites
        self.assertTrue(s["arcane_circle"]["anims"]["loop"]["file"].startswith("effects/weapons/magic_rod/"))
        self.assertTrue(s["thunder_ball"]["anims"]["loop"]["file"].startswith("effects/weapons/magic_rod/"))
        self.assertTrue(s["thunder_aura"]["anims"]["loop"]["file"].startswith("effects/weapons/magic_rod/"))
        self.assertTrue(s["soul_slash"]["anims"]["loop"]["file"].startswith("effects/weapons/sword/"))
        self.assertTrue(s["hammer_impact"]["anims"]["loop"]["file"].startswith("effects/weapons/hammer/"))


class SwordSlashRigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        reset_assets()
        cls.a = Assets()
        cls.s = get_content().sprites

    def test_the_two_sheets_cut_from_the_combat_sheet(self):
        down, up = self.s["sword_slash_down"], self.s["sword_slash_up"]
        for rig in (down, up):
            self.assertEqual(rig["frame"], [64, 64])
            self.assertFalse(rig["anims"]["loop"]["loop"], "a swing plays once")
            self.assertNotIn("flip_v", rig["anims"]["loop"], "the flip is baked into the sheet")
        self.assertEqual(down["anims"]["loop"]["file"], "effects/weapons/sword/slash_down.png")
        self.assertEqual(down["anims"]["loop"]["frames"], 4)
        self.assertEqual(up["anims"]["loop"]["file"], "effects/weapons/sword/slash_up.png")
        self.assertEqual(up["anims"]["loop"]["frames"], 6)

    def test_the_down_sheet_is_strip_2_flipped_vertically(self):
        """`slash_down.png` was cut from Combat-Sheet strip 2 (row index 1)
        with the vertical flip baked in; the rig loads it as is."""
        frames = self.a.frames("sword_slash_down", "loop")
        self.assertEqual(len(frames), 4)
        combat = pygame.image.load(os.path.join(ASSETS, "effects/weapons/sword/Combat-Sheet.png")).convert_alpha()
        raw = combat.subsurface(pygame.Rect(64, 64, 64, 64)).copy()      # strip 2, frame 2
        flipped = pygame.transform.flip(raw, False, True)
        got = frames[1]
        self.assertEqual(got.get_size(), (64, 64))
        self.assertEqual(pygame.image.tobytes(got, "RGBA"), pygame.image.tobytes(flipped, "RGBA"))
        self.assertNotEqual(pygame.image.tobytes(got, "RGBA"), pygame.image.tobytes(raw, "RGBA"),
                            "the strip is asymmetric top to bottom, so a flip shows")

    def test_the_up_sheet_is_row_27_as_authored(self):
        """The slash-up moved (owner, 2026-09-10) to the third row from the
        bottom of the combat sheet: the tan crescent, row 27, 6 frames."""
        frames = self.a.frames("sword_slash_up", "loop")
        self.assertEqual(len(frames), 6)
        combat = pygame.image.load(os.path.join(ASSETS, "effects/weapons/sword/Combat-Sheet.png")).convert_alpha()
        for i in (0, 2, 5):
            raw = combat.subsurface(pygame.Rect(i * 64, 26 * 64, 64, 64)).copy()
            self.assertEqual(pygame.image.tobytes(frames[i], "RGBA"), pygame.image.tobytes(raw, "RGBA"))

    def test_the_loader_can_still_flip_vertically_on_request(self):
        """`flip_v` stays available for a sheet authored the other way up."""
        import copy
        meta = copy.deepcopy(self.s["sword_slash_up"])
        meta["anims"]["loop"]["flip_v"] = True
        self.a.meta["_flip_probe"] = meta
        try:
            plain = self.a.frames("sword_slash_up", "loop")[2]
            flipped = self.a.frames("_flip_probe", "loop")[2]
            self.assertEqual(pygame.image.tobytes(flipped, "RGBA"),
                             pygame.image.tobytes(pygame.transform.flip(plain, False, True), "RGBA"))
        finally:
            self.a.meta.pop("_flip_probe", None)

    def test_the_swings_play_out_within_the_swords_hit(self):
        life = get_content().weapon("sword")["projectile_lifetime"]
        for rig in ("sword_slash_down", "sword_slash_up"):
            n, fps = self.a.frame_count(rig, "loop"), self.a.fps(rig, "loop")
            self.assertGreaterEqual(n / fps, life * 0.9, rig)   # the whole strip is seen


class SlashChoiceTests(unittest.TestCase):
    def _p(self, fx, swing):
        return SimpleNamespace(fx=fx, swing=swing, cone_half_angle=1.0,
                               cone_dir=pygame.Vector2(1, 0), radius=74, age=0.0)

    def test_the_sword_is_a_sequence_so_the_cone_draws_no_slash_itself(self):
        fx = get_content().weapon_visual("sword").fx
        self.assertEqual(fx["slash_mode"], "sequence")
        self.assertEqual(fx["slash"], ["sword_slash_down", "sword_slash_up"])
        self.assertIsNone(cone_mod.slash_rig(self._p(fx, 1)))

    def test_a_list_without_sequence_mode_alternates_by_the_swing_ordinal(self):
        fx = {"slash": ["a", "b"]}
        self.assertEqual(cone_mod.slash_rig(self._p(fx, 1)), "a")
        self.assertEqual(cone_mod.slash_rig(self._p(fx, 2)), "b")
        self.assertEqual(cone_mod.slash_rig(self._p(fx, 3)), "a")
        self.assertEqual(cone_mod.slash_rig(self._p(fx, 0)), "a")            # unset -> first

    def test_a_slash_of_false_draws_the_sector_alone(self):
        self.assertIsNone(cone_mod.slash_rig(self._p({"slash": False}, 1)))
        self.assertIsNone(cone_mod.slash_rig(self._p({"slash": []}, 1)))

    def test_legacy_true_and_no_fx_keep_the_old_rig(self):
        self.assertEqual(cone_mod.slash_rig(self._p({"slash": True}, 2)), "soul_slash")
        self.assertEqual(cone_mod.slash_rig(SimpleNamespace()), "soul_slash")

    def test_the_forged_swords_inherit(self):
        c = get_content()
        for forge in ("whirlwind", "greatsword"):
            self.assertNotIn(forge, c.weapon_visuals, "no entry of its own -> the Sword's")


class SwingOrdinalTests(unittest.TestCase):
    def test_each_sword_attack_carries_its_ordinal(self):
        w = Weapon("sword", get_content().weapon("sword"))
        sink = []
        for expected in (1, 2, 3):
            w._cd = 0.0
            w.update(1 / 60, FireContext(
                origin=pygame.Vector2(), enemies=[FakeEnemy(25, 0)],
                damage_multiplier=1.0, attack_speed_multiplier=1.0,
                projectile_speed_multiplier=1.0, area_multiplier=1.0,
                fallback_dir=pygame.Vector2(1, 0),
                spawn_projectile=lambda **kw: sink.append(kw)))
            self.assertEqual(sink[-1]["swing"], expected)


class SwingSequenceTests(unittest.TestCase):
    """One Sword attack plays the down strip, then the up strip, as a timed
    visual that outlives the 0.14 s hit (`slash_fx`)."""

    @classmethod
    def setUpClass(cls):
        _display()
        reset_assets()
        cls.a = Assets()

    def _ps(self):
        from game.states.playing import slash_fx
        return SimpleNamespace(_slashes=[], game=SimpleNamespace(assets=self.a)), slash_fx

    def _cone(self, fx):
        return SimpleNamespace(fx=fx, cone_half_angle=1.0, cone_dir=pygame.Vector2(0, 1),
                               pos=pygame.Vector2(100, 50), radius=32, fire_level=-1)

    def test_a_sword_cone_queues_one_sequence_entry(self):
        ps, slash_fx = self._ps()
        fx = get_content().weapon_visual("sword").fx
        slash_fx.spawn_from_cone(ps, self._cone(fx))
        self.assertEqual(len(ps._slashes), 1)
        e = ps._slashes[0]
        self.assertEqual(e["rigs"], ["sword_slash_down", "sword_slash_up"])
        self.assertEqual(len(e["durs"]), 2)
        self.assertGreater(sum(e["durs"]), get_content().weapon("sword")["projectile_lifetime"],
                           "the sequence outlives the hit, which is why it is its own visual")
        self.assertEqual(e["pos"], pygame.Vector2(100, 50))
        self.assertEqual(e["dir"], pygame.Vector2(0, 1))

    def test_the_daggers_and_a_plain_shot_queue_nothing(self):
        ps, slash_fx = self._ps()
        slash_fx.spawn_from_cone(ps, self._cone(get_content().weapon_visual("daggers").fx))
        shot = self._cone(get_content().weapon_visual("sword").fx)
        shot.cone_half_angle = 0.0
        slash_fx.spawn_from_cone(ps, shot)
        self.assertEqual(ps._slashes, [])

    def test_down_plays_first_then_up_then_the_entry_goes(self):
        ps, slash_fx = self._ps()
        slash_fx.spawn_from_cone(ps, self._cone(get_content().weapon_visual("sword").fx))
        e = ps._slashes[0]
        d_down, d_up = e["durs"]
        self.assertEqual(slash_fx.current(e)[0], "sword_slash_down")
        slash_fx.update(ps, d_down - 0.01)
        self.assertEqual(slash_fx.current(e)[0], "sword_slash_down")
        slash_fx.update(ps, 0.02)
        rig, t = slash_fx.current(e)
        self.assertEqual(rig, "sword_slash_up")
        self.assertAlmostEqual(t, 0.01, places=5)
        slash_fx.update(ps, d_up)
        self.assertEqual(ps._slashes, [])

    def test_the_draw_asks_each_rig_for_its_frame_in_turn(self):
        ps, slash_fx = self._ps()
        calls = []
        real = self.a.frame_rotated
        self.a.frame_rotated = lambda *args, **kw: (calls.append(args), real(*args, **kw))[1]
        try:
            ps.camera = SimpleNamespace(zoom=1.0, world_to_screen=lambda pos: (pos.x, pos.y))
            ps.renderer = SimpleNamespace(_off_band=lambda level, pos: False)
            slash_fx.spawn_from_cone(ps, self._cone(get_content().weapon_visual("sword").fx))
            surf = pygame.Surface((300, 300), pygame.SRCALPHA)
            slash_fx.draw(surf, ps)
            self.assertEqual(calls[-1][0], "sword_slash_down")
            self.assertEqual(calls[-1][2], 0)
            slash_fx.update(ps, ps._slashes[0]["durs"][0] + 0.03)
            slash_fx.draw(surf, ps)
            self.assertEqual(calls[-1][0], "sword_slash_up")
            self.assertEqual(calls[-1][2], int(0.03 * self.a.fps("sword_slash_up", "loop")))
        finally:
            self.a.frame_rotated = real

    def test_both_sword_strips_are_half_again_as_big(self):
        s = get_content().sprites
        for rig in ("sword_slash_down", "sword_slash_up"):
            self.assertEqual(s[rig]["scale"], [97, 97])              # 72 -> 108 -> -10 %
            self.assertEqual(s[rig]["anchor"], [48, 48])


class DaggersSlashTests(unittest.TestCase):
    """The Daggers' slash: row 18 of the combat sheet cut into its own
    sheet, drawn 10 % bigger than the cone (assets journal, 2026-09-10)."""

    @classmethod
    def setUpClass(cls):
        _display()
        reset_assets()
        cls.a = Assets()

    def test_the_sheet_is_row_18_of_the_combat_sheet(self):
        rig = get_content().sprites["daggers_slash"]
        self.assertEqual(rig["anims"]["loop"]["file"], "effects/weapons/daggers/slash.png")
        self.assertEqual(rig["anims"]["loop"]["frames"], 6)
        self.assertFalse(rig["anims"]["loop"]["loop"])
        frames = self.a.frames("daggers_slash", "loop")
        self.assertEqual(len(frames), 6)
        combat = pygame.image.load(os.path.join(ASSETS, "effects/weapons/sword/Combat-Sheet.png")).convert_alpha()
        for i in (1, 3):
            raw = combat.subsurface(pygame.Rect(i * 64, 17 * 64, 64, 64)).copy()   # row 18
            self.assertEqual(pygame.image.tobytes(frames[i], "RGBA"), pygame.image.tobytes(raw, "RGBA"))

    def test_the_daggers_swing_only_the_stab_with_the_crescent_parked(self):
        # Owner (2026-09-10): the crescent is "commented out" -- kept in the
        # data under `_slash_disabled`, a key the game never reads -- so the
        # stab is the only Daggers animation. Move it back to re-enable.
        fx = get_content().weapon_visual("daggers").fx
        self.assertEqual(fx["slash"], ["daggers_stab"])
        self.assertEqual(fx["_slash_disabled"], ["daggers_slash"])
        self.assertNotEqual(fx.get("slash_mode"), "sequence")
        p = SimpleNamespace(fx=fx, swing=1, cone_half_angle=1.0,
                            cone_dir=pygame.Vector2(1, 0), radius=46, age=0.0)
        for swing in (1, 2, 3):
            p.swing = swing
            self.assertEqual(cone_mod.slash_rig(p), "daggers_stab")
        self.assertIn("daggers_slash", get_content().sprites, "the rig itself stays")

    def test_the_stab_sheet_is_row_13_of_the_combat_sheet(self):
        rig = get_content().sprites["daggers_stab"]
        self.assertEqual(rig["anims"]["loop"]["file"], "effects/weapons/daggers/stab.png")
        self.assertEqual(rig["anims"]["loop"]["frames"], 5)
        self.assertFalse(rig["anims"]["loop"]["loop"])
        frames = self.a.frames("daggers_stab", "loop")
        self.assertEqual(len(frames), 5)
        combat = pygame.image.load(os.path.join(ASSETS, "effects/weapons/sword/Combat-Sheet.png")).convert_alpha()
        for i in (1, 2, 4):
            raw = combat.subsurface(pygame.Rect(i * 64, 12 * 64, 64, 64)).copy()   # row 13
            self.assertEqual(pygame.image.tobytes(frames[i], "RGBA"), pygame.image.tobytes(raw, "RGBA"))
        life = get_content().weapon("daggers")["projectile_lifetime"]
        n, fps = self.a.frame_count("daggers_stab", "loop"), self.a.fps("daggers_stab", "loop")
        self.assertGreaterEqual(n / fps, life * 0.9)

    def test_the_sprite_follows_the_cone_at_the_datas_factor(self):
        # 1.1 first ("10 % bigger"), then "tighter": 0.8 of the diameter.
        fx = get_content().weapon_visual("daggers").fx
        self.assertAlmostEqual(fx["slash_size"], 0.8)
        p = SimpleNamespace(fx=fx, radius=46)
        self.assertEqual(cone_mod.slash_size(p, self.a, "daggers_slash"), (74, 74))
        p.radius = 60                                                 # follows the reach
        self.assertEqual(cone_mod.slash_size(p, self.a, "daggers_slash"), (96, 96))

    def test_the_sword_follows_the_area_too(self):
        # Owner (2026-09-10): like the Daggers -- 1.5 x the cone's diameter,
        # 96 px at the current reach of 32, growing with area blessings.
        fx = get_content().weapon_visual("sword").fx
        self.assertAlmostEqual(fx["slash_size"], 1.5)
        p = SimpleNamespace(fx=fx, radius=32)
        self.assertEqual(cone_mod.slash_size(p, self.a, "sword_slash_down"), (96, 96))
        p.radius = 48
        self.assertEqual(cone_mod.slash_size(p, self.a, "sword_slash_down"), (144, 144))

    def test_a_visual_without_the_factor_uses_the_rigs_fixed_scale(self):
        p = SimpleNamespace(fx={"slash": ["sword_slash_down"]}, radius=32)
        self.assertEqual(cone_mod.slash_size(p, self.a, "sword_slash_down"),
                         tuple(get_content().sprites["sword_slash_down"]["scale"]))

    def test_the_strip_fits_the_daggers_hit(self):
        life = get_content().weapon("daggers")["projectile_lifetime"]
        n, fps = self.a.frame_count("daggers_slash", "loop"), self.a.fps("daggers_slash", "loop")
        self.assertGreaterEqual(n / fps, life * 0.9)
        self.assertLessEqual(n / fps, life * 1.5)


class ThrownDaggerTests(unittest.TestCase):
    """The owner's `daggers/throwing_dagger.png` (one 32 x 32 frame, tip at
    the top-left) is the Fan of Blades' shot, turned so the tip leads."""

    @classmethod
    def setUpClass(cls):
        _display()
        reset_assets()
        cls.a = Assets()

    def test_the_rig_is_the_single_frame_with_its_own_heading(self):
        r = get_content().sprites["throwing_dagger"]
        self.assertEqual(r["file"], "effects/weapons/daggers/throwing_dagger.png")
        self.assertEqual(r["frame"], [32, 32])
        self.assertEqual(r["content"], [6, 6, 19, 19])
        self.assertEqual(r["heading_deg"], -135)                 # tip points up-left
        img = self.a.image("throwing_dagger")
        self.assertEqual(img.get_size(), (19, 19))
        sheet = pygame.image.load(os.path.join(ASSETS, r["file"]))
        self.assertEqual(sheet.get_size(), (32, 32))

    def test_the_fan_of_blades_draws_it_thrown(self):
        from game.states.playing.projectiles import registered
        vis = get_content().weapon_visual("fan_of_blades")
        self.assertEqual(vis.style, "thrown")
        self.assertEqual(vis.fx["rig"], "throwing_dagger")
        self.assertIn("thrown", registered())
        self.assertEqual(get_content().weapon_visual("daggers").style, "cone")   # the base stays

    def test_the_turn_cancels_the_arts_own_heading(self):
        from game.states.playing.projectiles import thrown as t
        self.assertAlmostEqual(t.rotation_for(self.a, "throwing_dagger", -135.0), 0.0)
        self.assertAlmostEqual(t.rotation_for(self.a, "throwing_dagger", 0.0), 135.0)
        self.assertAlmostEqual(t.rotation_for(self.a, "arrow", 30.0), 30.0)  # no key -> as is
        p = SimpleNamespace(vel=pygame.Vector2(0, 5))
        self.assertAlmostEqual(t.heading_of(p), 90.0)

    def test_a_right_going_dagger_lies_flat_and_a_down_going_one_stands(self):
        from game.states.playing.projectiles import thrown as t
        flat = self.a.rotated("throwing_dagger", t.rotation_for(self.a, "throwing_dagger", 0.0))
        tall = self.a.rotated("throwing_dagger", t.rotation_for(self.a, "throwing_dagger", 90.0))
        fb, tb = flat.get_bounding_rect(), tall.get_bounding_rect()
        self.assertGreater(fb.w, fb.h * 2)
        self.assertGreater(tb.h, tb.w * 2)
        # the blade (the lighter, longer half) leads: at heading 0 the right
        # half of the flat sprite holds the thin blade, the left the pommel.
        untouched = self.a.image("throwing_dagger").get_bounding_rect()
        self.assertEqual(untouched.size, (19, 19))

    def test_the_draw_blits_the_rotated_rig_centred_on_the_shot(self):
        from game.states.playing.projectiles import draw_projectile
        from game.states.playing.drawctx import DrawCtx
        calls = []
        real = self.a.rotated
        self.a.rotated = lambda *a, **k: (calls.append((a, k)), real(*a, **k))[1]
        try:
            p = SimpleNamespace(vel=pygame.Vector2(3, 0), fx={"rig": "throwing_dagger"},
                                style="thrown", cone_half_angle=0.0, orbit_speed=0.0,
                                anchor=None, color=(1, 2, 3), radius=4)
            surf = pygame.Surface((100, 100), pygame.SRCALPHA)
            draw_projectile(surf, 50, 50, p, DrawCtx(self.a, 0.0, 1.0), default="bolt")
        finally:
            self.a.rotated = real
        self.assertEqual(calls[0][0], ("throwing_dagger", 135.0))
        self.assertEqual(calls[0][1]["size"], (22, 22))
        self.assertGreater(surf.get_bounding_rect().w, 20)

    def test_a_missing_rig_falls_back_to_the_disc(self):
        from game.states.playing.projectiles import draw_projectile
        from game.states.playing.drawctx import DrawCtx
        p = SimpleNamespace(vel=pygame.Vector2(3, 0), fx={"rig": "no_such_rig"},
                            style="thrown", cone_half_angle=0.0, orbit_speed=0.0,
                            anchor=None, color=(9, 8, 7), radius=4)
        surf = pygame.Surface((100, 100), pygame.SRCALPHA)
        draw_projectile(surf, 50, 50, p, DrawCtx(self.a, 0.0, 1.0), default="bolt")
        self.assertEqual(surf.get_at((50, 50))[:3], (9, 8, 7))
