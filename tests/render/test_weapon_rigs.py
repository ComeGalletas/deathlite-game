"""The weapon effect sheets
moved into per-weapon folders; every rig must resolve on disk; the Sword
swings two slashes from Combat-Sheet.png, the first flipped vertically, and
alternates them by the attack's ordinal (change request 2, weapon_system_journal.md)."""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import FireContext, Weapon
from game.assets import Assets, reset_assets
from game.content import get_content
from game.states.playing.visual.projectiles import cone as cone_mod
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
        self.assertTrue(s["hammer_impact_plain"]["anims"]["loop"]["file"].startswith("effects/weapons/hammer/"))


class SheetLoaderTests(unittest.TestCase):
    """What `SwordSlashRigTests` used to cover.

    Most of it described the two strips cut from `Combat-Sheet.png` -- their
    frame counts, that `slash_down` was strip 2 flipped, that both play
    once. M13 replaced both with one fanned arc from the effects pack, so
    that art is gone and so are the tests that measured it.

    The loader behaviour is not about that art and stays: a sheet authored
    the other way up can still ask for a vertical flip, which is the escape
    hatch the Sword's old down-strip once needed.
    """

    @classmethod
    def setUpClass(cls):
        _display()
        reset_assets()
        cls.a = Assets()
        cls.s = get_content().sprites

    def test_the_loader_can_still_flip_vertically_on_request(self):
        import copy
        meta = copy.deepcopy(self.s["sword_slash_plain"])
        meta["anims"]["loop"]["flip_v"] = True
        self.a.meta["_flip_probe"] = meta
        try:
            plain = self.a.frames("sword_slash_plain", "loop")[2]
            flipped = self.a.frames("_flip_probe", "loop")[2]
            self.assertEqual(pygame.image.tobytes(flipped, "RGBA"),
                             pygame.image.tobytes(
                                 pygame.transform.flip(plain, False, True), "RGBA"))
        finally:
            self.a.meta.pop("_flip_probe", None)

    def test_a_swing_plays_once_and_covers_the_hit(self):
        life = get_content().weapon("sword")["projectile_lifetime"]
        for variant in ("plain", "fire", "ice", "thunder", "wind"):
            rig = f"sword_slash_{variant}"
            with self.subTest(rig=rig):
                self.assertFalse(self.s[rig]["anims"]["loop"]["loop"],
                                 "a swing plays once")
                n = self.a.frame_count(rig, "loop")
                fps = self.a.fps(rig, "loop")
                self.assertGreaterEqual(n / fps, life * 0.9,
                                        "the whole strip is seen")


class SlashChoiceTests(unittest.TestCase):
    def _p(self, fx, swing):
        return SimpleNamespace(fx=fx, swing=swing, cone_half_angle=1.0,
                               cone_dir=pygame.Vector2(1, 0), radius=74, age=0.0)

    def test_the_sword_is_a_sequence_so_the_cone_draws_no_slash_itself(self):
        """M13 replaced the down-then-up pair with one fanned arc, and the
        name in the data is now a *base* the element picks a colour of."""
        fx = get_content().weapon_visual("sword").fx
        self.assertEqual(fx["slash_mode"], "sequence")
        self.assertEqual(fx["slash"], ["sword_slash"])
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

    def test_slash_true_or_no_fx_swings_the_default_soul_slash(self):
        """`soul_slash` is the current default for a cone with `slash: true`
        or no visuals entry at all, not a legacy path."""
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
    """A Sword attack is a timed visual that outlives its own 0.14 s hit
    (`slash_fx`).

    It used to be two strips back to back, a downward slash then an upward
    one. M13 replaced both with a single fanned arc, so the sequence is one
    entry long -- the machinery is unchanged and still has to hold, because
    a sequence weapon's cone draws no slash of its own and would show
    nothing if this broke."""

    @classmethod
    def setUpClass(cls):
        _display()
        reset_assets()
        cls.a = Assets()

    def _ps(self):
        from game.states.playing.visual import slash_fx
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
        self.assertEqual(e["rigs"], ["sword_slash_plain"],
                         "an uninfused Sword draws the plain variant")
        self.assertEqual(len(e["durs"]), 1)
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

    def test_the_strip_plays_through_and_then_the_entry_goes(self):
        ps, slash_fx = self._ps()
        slash_fx.spawn_from_cone(ps, self._cone(get_content().weapon_visual("sword").fx))
        e = ps._slashes[0]
        d_down = e["durs"][0]
        self.assertEqual(slash_fx.current(e)[0], "sword_slash_plain")
        slash_fx.update(ps, d_down - 0.01)
        rig, t = slash_fx.current(e)
        self.assertEqual(rig, "sword_slash_plain", "still on its one strip")
        self.assertAlmostEqual(t, d_down - 0.01, places=5)
        slash_fx.update(ps, 0.02)
        self.assertEqual(ps._slashes, [], "past the last frame, the entry goes")

    def test_an_infused_sword_draws_its_element(self):
        """The whole point of M13: the rig in the data is a base and the
        weapon's infusion picks which colour of it is drawn."""
        from combat.elements.ids import ELEMENTS

        fx = get_content().weapon_visual("sword").fx
        for element in ELEMENTS:
            with self.subTest(element=element.key):
                ps, slash_fx = self._ps()
                cone = self._cone(fx)
                cone.infusion = element
                slash_fx.spawn_from_cone(ps, cone)
                self.assertEqual(ps._slashes[0]["rigs"],
                                 [f"sword_slash_{element.key}"])

    def test_it_is_the_infusion_that_picks_the_colour_not_the_hit(self):
        """`element` is what this hit *applies* and is not the same thing.
        Painting from it left the three time-mode weapons plain at every
        element and drew the Daggers plain on two swings in three, because
        both stamp `NONE` on the attacks that do not apply (M13 C)."""
        from combat.elements.ids import ElementId

        ps, slash_fx = self._ps()
        cone = self._cone(get_content().weapon_visual("sword").fx)
        cone.element = ElementId.NONE
        cone.infusion = ElementId.FIRE
        slash_fx.spawn_from_cone(ps, cone)
        self.assertEqual(ps._slashes[0]["rigs"], ["sword_slash_fire"])

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
            self.assertEqual(calls[-1][0], "sword_slash_plain")
            self.assertEqual(calls[-1][2], 0, "the first frame first")
            # Part way in, the same rig at a later index. This used to step
            # from the down strip to the up one; M13 made the swing one
            # strip, so what it checks now is that the index advances with
            # the clock rather than that the rig changes.
            fps = self.a.fps("sword_slash_plain", "loop")
            slash_fx.update(ps, 3.5 / fps)
            slash_fx.draw(surf, ps)
            self.assertEqual(calls[-1][0], "sword_slash_plain")
            self.assertEqual(calls[-1][2], 3)
        finally:
            self.a.frame_rotated = real

    def test_every_sword_variant_shares_one_geometry(self):
        """Five colours of one animation: they must agree on frame and
        anchor or the swing would jump when a weapon is infused."""
        s = get_content().sprites
        base = None
        for variant in ("plain", "fire", "ice", "thunder", "wind"):
            rig = s[f"sword_slash_{variant}"]
            got = (tuple(rig["frame"]), tuple(rig["anchor"]))
            base = base or got
            self.assertEqual(got, base, f"{variant} does not match plain")


class DaggersSlashTests(unittest.TestCase):
    """The Daggers' effects.

    They used to be cut from `Combat-Sheet.png` -- the crescent from row 18,
    the stab from row 13 -- and the tests pinned that provenance. M13
    replaced both with art from the effects pack, five colour variants
    each, so the provenance claims are gone and what stays is the
    behaviour: which rig is swung, that the crescent is still parked, and
    that a strip covers its own hit.
    """

    @classmethod
    def setUpClass(cls):
        _display()
        reset_assets()
        cls.a = Assets()

    def test_the_daggers_swing_only_the_stab_with_the_crescent_parked(self):
        # Owner (2026-09-10): the crescent is "commented out" -- kept in the
        # data under `_slash_disabled`, a key the game never reads -- so the
        # stab is the only Daggers animation. Move it back to re-enable.
        # M13 changed the art behind both names, not this arrangement.
        fx = get_content().weapon_visual("daggers").fx
        self.assertEqual(fx["slash"], ["daggers_stab"])
        self.assertEqual(fx["_slash_disabled"], ["daggers_slash"])
        self.assertNotEqual(fx.get("slash_mode"), "sequence")
        p = SimpleNamespace(fx=fx, swing=1, cone_half_angle=1.0,
                            cone_dir=pygame.Vector2(1, 0), radius=46, age=0.0)
        for swing in (1, 2, 3):
            p.swing = swing
            self.assertEqual(cone_mod.slash_rig(p), "daggers_stab")

    def test_both_daggers_effects_have_all_five_variants(self):
        s = get_content().sprites
        for base in ("daggers_stab", "daggers_slash"):
            geometry = None
            for variant in ("plain", "fire", "ice", "thunder", "wind"):
                rig = s.get(f"{base}_{variant}")
                with self.subTest(rig=f"{base}_{variant}"):
                    self.assertIsNotNone(rig)
                    self.assertFalse(rig["anims"]["loop"]["loop"],
                                     "a swing plays once")
                    got = (tuple(rig["frame"]), tuple(rig["anchor"]))
                    geometry = geometry or got
                    self.assertEqual(got, geometry,
                                     "the variants must share a geometry or "
                                     "the swing would jump when infused")

    def test_the_stab_covers_the_daggers_hit(self):
        life = get_content().weapon("daggers")["projectile_lifetime"]
        n = self.a.frame_count("daggers_stab_plain", "loop")
        fps = self.a.fps("daggers_stab_plain", "loop")
        self.assertGreaterEqual(n / fps, life * 0.9)

    def test_the_sprite_follows_the_cone_at_the_datas_factor(self):
        # 1.1 first ("10 % bigger"), then "tighter": 0.8 of the diameter.
        fx = get_content().weapon_visual("daggers").fx
        self.assertAlmostEqual(fx["slash_size"], 0.8)
        p = SimpleNamespace(fx=fx, radius=46)
        self.assertEqual(cone_mod.slash_size(p, self.a, "daggers_slash_plain"), (74, 74))
        p.radius = 60                                                 # follows the reach
        self.assertEqual(cone_mod.slash_size(p, self.a, "daggers_slash_plain"), (96, 96))

    def test_the_sword_follows_the_area_too(self):
        # Owner (2026-09-10): like the Daggers -- 1.5 x the cone's diameter,
        # 96 px at the current reach of 32, growing with area blessings.
        fx = get_content().weapon_visual("sword").fx
        self.assertAlmostEqual(fx["slash_size"], 1.5)
        p = SimpleNamespace(fx=fx, radius=32)
        self.assertEqual(cone_mod.slash_size(p, self.a, "sword_slash_plain"), (96, 96))
        p.radius = 48
        self.assertEqual(cone_mod.slash_size(p, self.a, "sword_slash_plain"), (144, 144))

    def test_a_visual_without_the_factor_uses_the_rigs_fixed_scale(self):
        """The fallback, on a rig that still carries a `scale`.

        It used to be checked on the Sword's slash. M13's melee rigs have
        no `scale` of their own -- both weapons that use them set
        `slash_size`, so the reach decides -- and a rig with neither
        reports `(0, 0)`, which means absent. Both halves are worth
        holding."""
        p = SimpleNamespace(fx={"slash": ["soul_slash"]}, radius=32)
        self.assertEqual(cone_mod.slash_size(p, self.a, "soul_slash"),
                         tuple(get_content().sprites["soul_slash"]["scale"]))
        self.assertEqual(cone_mod.slash_size(p, self.a, "sword_slash_plain"), (0, 0))

    def test_the_parked_crescent_would_also_fit_the_hit(self):
        """It is disabled, not broken: if the owner moves it back out of
        `_slash_disabled` it should still play inside the swing."""
        life = get_content().weapon("daggers")["projectile_lifetime"]
        n = self.a.frame_count("daggers_slash_plain", "loop")
        fps = self.a.fps("daggers_slash_plain", "loop")
        self.assertGreaterEqual(n / fps, life * 0.9)
        # Against the *cooldown*, not the hit. The old upper bound was 1.5x
        # the 0.1 s hit, which was really a statement about a five-frame
        # strip; what has to be true is that a swing's visual is finished
        # before the next swing starts, or the Daggers would stack slashes
        # at 0.4 s a swing.
        self.assertLess(n / fps, get_content().weapon("daggers")["cooldown"])


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
        from game.states.playing.visual.projectiles import registered
        vis = get_content().weapon_visual("fan_of_blades")
        self.assertEqual(vis.style, "thrown")
        self.assertEqual(vis.fx["rig"], "throwing_dagger")
        self.assertIn("thrown", registered())
        self.assertEqual(get_content().weapon_visual("daggers").style, "cone")   # the base stays

    def test_the_turn_cancels_the_arts_own_heading(self):
        from game.states.playing.visual.projectiles import thrown as t
        self.assertAlmostEqual(t.rotation_for(self.a, "throwing_dagger", -135.0), 0.0)
        self.assertAlmostEqual(t.rotation_for(self.a, "throwing_dagger", 0.0), 135.0)
        self.assertAlmostEqual(t.rotation_for(self.a, "arrow", 30.0), 30.0)  # no key -> as is
        p = SimpleNamespace(vel=pygame.Vector2(0, 5))
        self.assertAlmostEqual(t.heading_of(p), 90.0)

    def test_a_right_going_dagger_lies_flat_and_a_down_going_one_stands(self):
        from game.states.playing.visual.projectiles import thrown as t
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
        from game.states.playing.visual.projectiles import draw_projectile
        from game.states.playing.visual.drawctx import DrawCtx
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
        from game.states.playing.visual.projectiles import draw_projectile
        from game.states.playing.visual.drawctx import DrawCtx
        p = SimpleNamespace(vel=pygame.Vector2(3, 0), fx={"rig": "no_such_rig"},
                            style="thrown", cone_half_angle=0.0, orbit_speed=0.0,
                            anchor=None, color=(9, 8, 7), radius=4)
        surf = pygame.Surface((100, 100), pygame.SRCALPHA)
        draw_projectile(surf, 50, 50, p, DrawCtx(self.a, 0.0, 1.0), default="bolt")
        self.assertEqual(surf.get_at((50, 50))[:3], (9, 8, 7))
