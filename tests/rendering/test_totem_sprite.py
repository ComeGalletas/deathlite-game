"""The Grave Totem's sprite (assets journal, "Grave Totem sprite -- wiring",
2026-09-12): four strips cut from the blue sheet, a rig that names them one
file each, and the totem's appear / idle / attack / leaving phases that
drive which strip shows and when the totem may fire.

Real assets, no world. The strips are checked against the cutting script
so a re-cut can never drift from what is committed; the phases are walked
with a scripted target and a recorder for the bolts.
"""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.summon import Summon
from game.assets import get_assets

FOLDER = os.path.join("assets", "effects", "weapons", "grave_totem")
RIG = "grave_totem"
STRIPS = {"appear": 8, "idle": 7, "attack": 7, "disappear": 14}


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


class SheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        cls.assets = get_assets()

    def test_the_rig_names_one_file_per_action(self):
        for anim, frames in STRIPS.items():
            with self.subTest(anim=anim):
                spec = self.assets.meta[RIG]["anims"][anim]
                self.assertEqual(spec["frames"], frames)
                self.assertNotIn("row", spec, "a strip is its own file, not a row of the sheet")
                self.assertTrue(spec["file"].startswith("effects/weapons/grave_totem/totem_"))

    def test_each_strip_exists_and_is_exactly_its_frames_wide(self):
        for anim, frames in STRIPS.items():
            with self.subTest(anim=anim):
                path = os.path.join("assets", self.assets.meta[RIG]["anims"][anim]["file"])
                self.assertTrue(os.path.exists(path), path)
                w, h = pygame.image.load(path).get_size()
                self.assertEqual((w, h), (64 * frames, 96))

    def test_the_strips_are_what_the_cutting_script_produces(self):
        """`utilities/cut_totem_sheets.py --check` compares every committed
        strip with a fresh cut of the blue sheet. The script looks for the
        sheet in the folder and in `unused/`, where spent sources are
        archived; exit 2 means it is gone from both and there is nothing to
        compare against -- the strips themselves are still pinned above."""
        from utilities import cut_totem_sheets
        code = cut_totem_sheets.main(["--check"])
        if code == 2:
            self.skipTest("the source sheet has been archived away entirely")
        self.assertEqual(code, 0)

    def test_every_frame_of_every_strip_loads(self):
        for anim, frames in STRIPS.items():
            for i in range(frames):
                with self.subTest(anim=anim, frame=i):
                    self.assertIsNotNone(self.assets.frame(RIG, anim, i))

    def test_only_appear_attack_and_disappear_are_one_shots(self):
        for anim in ("appear", "attack", "disappear"):
            self.assertFalse(self.assets.loops(RIG, anim))
        self.assertTrue(self.assets.loops(RIG, "idle"))


class _Ctx:
    def __init__(self, enemies):
        self.enemies = enemies
        self.player_pos = pygame.Vector2(0, 0)
        self.shots = []

    def spawn_projectile(self, **kw):
        self.shots.append(kw)


def _totem(lifetime=8.0, interval=0.5):
    s = Summon()
    s.reset(kind="totem", pos=pygame.Vector2(0, 0), damage=7, lifetime=lifetime,
            color=(1, 2, 3), tags=("summon",), attack_range=400,
            attack_interval=interval, weapon_id="grave_totem")
    s.active = True                    # the pool sets this on acquire; `reset` does not
    return s


class PhaseTests(unittest.TestCase):
    """Walked at 1/60 s with an enemy 100 px away the whole time."""

    @classmethod
    def setUpClass(cls):
        _display()
        cls.assets = get_assets()
        cls.appear_s = 8 / 12.0
        cls.attack_s = 7 / 14.0
        cls.leave_s = 14 / 14.0

    def _walk(self, s, ctx, seconds):
        for _ in range(int(round(seconds * 60))):
            s.update(1 / 60, ctx)

    def test_no_bolt_while_appearing_then_the_first_bolt_bursts(self):
        s = _totem()
        ctx = _Ctx([SimpleNamespace(pos=pygame.Vector2(100, 0), alive=True)])
        self.assertEqual(s._phase, "appearing")
        self.assertEqual(s.anim.anim, "appear")
        self._walk(s, ctx, self.appear_s - 0.05)
        self.assertEqual(ctx.shots, [], "a bolt left during the appear strip")
        self._walk(s, ctx, 0.15)
        self.assertEqual(len(ctx.shots), 1)
        self.assertEqual(s._phase, "attack")
        self.assertEqual(s.anim.anim, "attack")
        self.assertEqual(ctx.shots[0]["weapon_id"], "grave_totem")

    def test_after_the_burst_the_totem_idles_until_the_next_bolt(self):
        s = _totem(interval=1.0)
        ctx = _Ctx([SimpleNamespace(pos=pygame.Vector2(100, 0), alive=True)])
        self._walk(s, ctx, self.appear_s + 0.1)          # first bolt fired
        self.assertEqual(s._phase, "attack")
        self._walk(s, ctx, self.attack_s + 0.05)         # burst over, interval not
        self.assertEqual(s._phase, "idle")
        self.assertEqual(s.anim.anim, "idle")
        self._walk(s, ctx, 0.5)                           # interval over -> next bolt
        self.assertEqual(len(ctx.shots), 2)
        self.assertEqual(s._phase, "attack")

    def test_the_burst_fits_inside_the_data_attack_interval(self):
        """0.7 s between bolts in `data/weapons.json`; a 0.5 s burst always
        completes before the next one restarts it."""
        import json
        interval = json.load(open("data/weapons.json"))["grave_totem"]["summon_attack_interval"]
        self.assertLess(self.attack_s, interval)

    def test_leaving_starts_a_strip_before_the_end_and_holds_fire(self):
        s = _totem(lifetime=3.0)
        ctx = _Ctx([SimpleNamespace(pos=pygame.Vector2(100, 0), alive=True)])
        self._walk(s, ctx, 3.0 - self.leave_s - 0.05)
        self.assertNotEqual(s._phase, "leaving")
        self._walk(s, ctx, 0.1)
        self.assertEqual(s._phase, "leaving")
        self.assertEqual(s.anim.anim, "disappear")
        before = len(ctx.shots)
        self._walk(s, ctx, self.leave_s - 0.1)
        self.assertEqual(len(ctx.shots), before, "a bolt left while the totem was leaving")
        self.assertTrue(s.active)
        self._walk(s, ctx, 0.2)
        self.assertFalse(s.active)

    def test_no_target_means_idle_not_attack(self):
        s = _totem()
        ctx = _Ctx([])
        self._walk(s, ctx, self.appear_s + 0.5)
        self.assertEqual(s._phase, "idle")
        self.assertEqual(ctx.shots, [])

    def test_a_missing_rig_passes_the_phases_through_at_once(self):
        """With no strips (an empty `assets/`) every strip is zero-length: the
        totem is idle on its first frame, fires on the old schedule, and
        never enters `leaving`."""
        s = _totem()
        s.anim.rig = "no_such_rig"
        ctx = _Ctx([SimpleNamespace(pos=pygame.Vector2(100, 0), alive=True)])
        s.update(1 / 60, ctx)
        self.assertEqual(s._phase, "idle")
        self._walk(s, ctx, 0.4)
        self.assertEqual(len(ctx.shots), 1)
        self._walk(s, ctx, 7.7)
        self.assertNotEqual(s._phase, "leaving")


class DrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def _draw(self, s, assets):
        from game.states.playing.summons import draw_summon
        from game.states.playing.drawctx import DrawCtx
        surface = pygame.Surface((160, 160), pygame.SRCALPHA)
        draw_summon(surface, 80, 100, s, DrawCtx(assets, 0.0, 1.0))
        return surface

    def _ink(self, surface):
        return sum(1 for x in range(0, 160, 2) for y in range(0, 160, 2)
                   if surface.get_at((x, y))[3] > 0)

    def test_the_sprite_is_drawn_standing_on_its_anchor(self):
        s = _totem()
        s._phase = "idle"
        s.anim.play("idle")
        surface = self._draw(s, get_assets())
        self.assertGreater(self._ink(surface), 40)
        # Bottom-centre anchor 12 px under the summon centre: ink ends just
        # below y=100+12 and there is none far below it.
        rows = [y for y in range(160) if any(surface.get_at((x, y))[3] > 0 for x in range(0, 160, 2))]
        self.assertLessEqual(rows[-1], 100 + 12 + 2)
        self.assertGreaterEqual(rows[-1], 100 + 12 - 6)

    def test_without_the_rig_the_primitive_draws(self):
        s = _totem()
        s.anim.rig = "no_such_rig"
        surface = self._draw(s, get_assets())
        self.assertGreater(self._ink(surface), 20)
        # The primitive is the 14 x 24 rounded rectangle centred on the summon.
        self.assertGreater(surface.get_at((80, 100))[3], 0)


if __name__ == "__main__":
    unittest.main()
