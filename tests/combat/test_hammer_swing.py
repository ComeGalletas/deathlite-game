"""The Hammer swings before it
lands. A swing time gates the blow, the direction locks at the start, the
blow is a circle 40 px ahead with radius 52, Haste shortens the swing and
cooldown reductions the cooldown, the forged Hammers swing too, the
indicator darkens over the swing and the impact sheet plays at the blow (change request 1, weapon_system_journal.md)."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.weapons import FireContext, Weapon, WeaponMods
from combat.weapons.forge import apply_forge, get_forges
from game import config
from game.content import get_content
from game.states.playing.visual import slam_fx
from game.states.playing.core.aim import AimInput
from tests.combat.fakes import FakeEnemy

C = get_content()
H = C.weapon("hammer")
SW = float(H["swing_time"])          # the owner tunes this in play; the tests follow it


class _Shot:
    def __init__(self, **kw):
        self.active = True
        self.__dict__.update(kw)


def hammer(forge=None):
    w = Weapon("hammer", C.weapon("hammer"))
    if forge:
        apply_forge(w, get_forges(C).get(forge))
    w._cd = 0.0
    return w


def ctx(enemies, sink, **over):
    base = dict(origin=pygame.Vector2(), enemies=list(enemies),
                damage_multiplier=1.0, attack_speed_multiplier=1.0,
                projectile_speed_multiplier=1.0, area_multiplier=1.0,
                fallback_dir=pygame.Vector2(1, 0),
                spawn_projectile=lambda **kw: (sink.append(_Shot(**kw)), sink[-1])[1])
    base.update(over)
    return FireContext(**base)


def run(w, seconds, enemies=(FakeEnemy(60, 0),), dt=1 / 60, **over):
    """Tick the weapon for `seconds`; return (shots, attack beats)."""
    sink, beats = [], 0
    for _ in range(int(round(seconds / dt))):
        beats += w.update(dt, ctx(enemies, sink, **over))
    return sink, beats


class DataTests(unittest.TestCase):
    def test_the_hammer_is_a_slam_with_the_agreed_numbers(self):
        self.assertEqual(H["special_effect"], "slam")
        self.assertGreater(H["damage"], 0)                # 25 agreed, tuned since (27)
        self.assertGreater(H["swing_time"], 0.0)          # 1.2 agreed, tuned since (0.8)
        self.assertEqual(H["impact_offset"], 40)
        self.assertGreater(H["area"], 0)            # 52 agreed; the owner tunes it in play
        self.assertNotIn("cone_half_angle", H)
        self.assertEqual(H["impact_rig"], "hammer_impact",
                         "a base name -- the element picks the variant")

    def test_the_impact_rig_matches_the_sheet(self):
        """The rig's frame count is the strip's, and the cells are square.

        Asserted as a relationship rather than as `frames == 5` and
        `size == (400, 80)`: re-cutting the sheet is an art change, and the
        claim worth keeping is that the data still agrees with the file.
        """
        rig = C.sprites["hammer_impact_plain"]
        self.assertFalse(rig["anims"]["loop"]["loop"])
        path = os.path.join(os.path.dirname(__file__), "..", "..", "assets",
                            rig["anims"]["loop"]["file"])
        w, h = pygame.image.load(path).get_size()
        fw, fh = rig["frame"]
        # The cells used to be square, because the sheet was cut on a square
        # grid. M13's strips are trimmed to the union of the art's own
        # frames, so a cell is as wide and as tall as the art -- which makes
        # this a stronger claim than squareness ever was: the data has to
        # account for the file exactly, in both directions.
        self.assertEqual(fh, h, "the frame height is not the strip's")
        self.assertEqual(rig["anims"]["loop"]["frames"] * fw, w,
                         "the frames do not tile the strip's width")

    def test_the_impact_crop_is_the_splashs_bounding_box(self):
        """The rig's `content` crops the 80 x 80 cell to the art over all
        five frames, so centring the frame centres the splash on the blow."""
        rig = C.sprites["hammer_impact_plain"]
        path = os.path.join(os.path.dirname(__file__), "..", "..", "assets",
                            rig["anims"]["loop"]["file"])
        pygame.display.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))
        sheet = pygame.image.load(path).convert_alpha()
        fw, fh = rig["frame"]
        union = None
        for i in range(rig["anims"]["loop"]["frames"]):
            r = sheet.subsurface(
                pygame.Rect(i * fw, 0, fw, fh)).get_bounding_rect(min_alpha=16)
            union = r if union is None else union.union(r)
        self.assertEqual(list(rig["content"]), list(union))
        # Centred, where the old splash sat 8 crop px low. That lift was
        # for art whose mass hung below its own box; M13's impact is a
        # radial star and its centre is the blow (within a pixel of the
        # crop's, since the cut trims to the union of all frames).
        self.assertAlmostEqual(rig["anchor"][0], union.width // 2, delta=1)
        self.assertAlmostEqual(rig["anchor"][1], union.height // 2, delta=1)

    def test_the_splash_is_centred_on_the_blow(self):
        """It used to be lifted about five screen pixels, because the old
        splash's mass hung below its own crop and the anchor was set eight
        crop px low to compensate. M13's impact is a radial star centred on
        its own box, so the lift is gone and the claim is the simpler one:
        the effect lands *on* the blow. The scaling rule -- the anchor
        follows the frame -- is still what is being exercised."""
        from game.assets import get_assets
        assets = get_assets()
        rig = "hammer_impact_plain"
        frame_w, frame_h = C.sprites[rig]["frame"]
        for radius, zoom in ((42, 1.0), (52, 1.0), (42, 2.0)):
            with self.subTest(radius=radius, zoom=zoom):
                size = slam_fx.impact_size(assets, rig, radius, zoom)
                x, y = slam_fx.impact_topleft(assets, rig, size, 500, 300)
                cx, cy = x + size[0] / 2, y + size[1] / 2
                # Within one *source* pixel, which is more than one screen
                # pixel once the frame is scaled up. The anchor is the
                # original 64 px cell's centre carried into the trimmed
                # crop, so on an odd-sized frame it sits half a pixel off
                # the crop's own centre -- and that half pixel grows with
                # the draw.
                self.assertAlmostEqual(cx, 500, delta=1 + size[0] / frame_w)
                self.assertAlmostEqual(cy, 300, delta=1 + size[1] / frame_h)

    def test_the_impact_is_drawn_a_quarter_wider_than_the_circle_with_the_crops_aspect(self):
        from game.assets import get_assets
        rig = C.sprites["hammer_impact_plain"]
        # This one stays a literal: it is the owner's decision, not tuning
        # that drifts ("about 25 % bigger").
        self.assertAlmostEqual(rig["over_circle"], 1.25)
        # The size itself is derived from the rig, so re-cropping the sheet or
        # retuning the overhang does not fail a test about the *rule*.
        radius = 52
        _cx, _cy, crop_w, crop_h = rig["content"]
        w, h = slam_fx.impact_size(get_assets(), "hammer_impact_plain", radius, 1.0)
        self.assertEqual(w, round(radius * 2 * rig["over_circle"]))
        self.assertEqual(h, round(w * crop_h / crop_w))
        # Halve the zoom, halve the drawn size -- derived from the rig, so
        # re-cutting the art does not fail a test about the *rule*.
        w2, h2 = slam_fx.impact_size(get_assets(), "hammer_impact_plain", 52, 0.5)
        self.assertEqual(w2, round(radius * 2 * 0.5 * rig["over_circle"]))
        self.assertEqual(h2, round(w2 * crop_h / crop_w))

    def test_reach_is_offset_plus_radius(self):
        w = hammer()
        r = H["area"]
        self.assertAlmostEqual(w._reach(1.0), 40 + r)
        w.bonus["area"] += 10
        self.assertAlmostEqual(w._reach(1.0), 50 + r)
        self.assertAlmostEqual(w._reach(1.5), 40 + (r + 10) * 1.5)


class SwingTests(unittest.TestCase):
    def test_nothing_lands_before_the_swing_time(self):
        w = hammer()
        shots, beats = run(w, SW - 0.08)
        self.assertEqual(shots, [])
        self.assertEqual(beats, 0)
        self.assertIsNotNone(w._swing_dir)
        self.assertGreater(w.swing_progress, 0.85)

    def test_the_blow_lands_once_at_the_locked_centre(self):
        w = hammer()
        shots, beats = run(w, SW + 0.05)
        self.assertEqual(len(shots), 1)
        self.assertEqual(beats, 1)
        s = shots[0]
        self.assertAlmostEqual(s.pos.x, 40.0)
        self.assertAlmostEqual(s.pos.y, 0.0)
        self.assertAlmostEqual(s.radius, H["area"])
        self.assertEqual(s.vel.length(), 0.0)
        self.assertEqual(getattr(s, "cone_half_angle", 0.0), 0.0)
        self.assertEqual(s.style, "hidden")
        self.assertTrue(s.no_block)
        # The blow carries the weapon's damage, whatever it is tuned to -- the
        # rule, rather than the number it happened to be.
        self.assertEqual(s.damage, H["damage"])
        self.assertAlmostEqual(s.stun_chance, H["stun_chance"])
        self.assertIsNone(w._swing_dir)

    def test_the_direction_locks_when_the_swing_starts(self):
        w = hammer()
        sink = []
        w.update(1 / 60, ctx([FakeEnemy(60, 0)], sink))         # locks +x
        for _ in range(int(SW * 60) + 6):
            w.update(1 / 60, ctx([FakeEnemy(0, 60)], sink))     # the target moved
        self.assertAlmostEqual(sink[0].pos.x, 40.0)
        self.assertAlmostEqual(sink[0].pos.y, 0.0)

    def test_the_circle_travels_with_the_hero(self):
        w = hammer()
        sink = []
        w.update(1 / 60, ctx([FakeEnemy(60, 0)], sink))
        for _ in range(int(SW * 60) + 6):
            w.update(1 / 60, ctx([FakeEnemy(60, 0)], sink, origin=pygame.Vector2(100, 30)))
        self.assertAlmostEqual(sink[0].pos.x, 140.0)
        self.assertAlmostEqual(sink[0].pos.y, 30.0)

    def test_the_cooldown_runs_from_the_impact(self):
        w = hammer()
        shots, _ = run(w, SW + 0.05)
        self.assertEqual(len(shots), 1)
        self.assertAlmostEqual(w._cd, H["cooldown"], delta=0.05)
        shots, _ = run(w, H["cooldown"] - 0.1)
        self.assertEqual(shots, [], "still cooling: no new blow")
        self.assertIsNone(w._swing_dir, "and no new swing yet")
        shots, _ = run(w, 0.2 + SW + 0.05)
        self.assertEqual(len(shots), 1, "then the next swing lands")

    def test_a_manual_aim_starts_the_swing_that_way(self):
        w = hammer()
        sink = []
        held = AimInput(pygame.Vector2(0, -1), "keys", held=True)
        w.update(1 / 60, ctx([], sink, aim=held))               # empty ring, still swings
        self.assertIsNotNone(w._swing_dir)
        for _ in range(int(SW * 60) + 6):
            w.update(1 / 60, ctx([], sink))
        self.assertAlmostEqual(sink[0].pos.x, 0.0, places=5)
        self.assertAlmostEqual(sink[0].pos.y, -40.0)

    def test_auto_attack_off_holds_the_swing(self):
        w = hammer()
        shots, _ = run(w, 2.0, auto_attack=False)
        self.assertEqual(shots, [])
        self.assertIsNone(w._swing_dir)

    def test_no_target_no_swing(self):
        w = hammer()
        shots, _ = run(w, 2.0, enemies=[FakeEnemy(300, 0)])
        self.assertEqual(shots, [])


class SpeedTests(unittest.TestCase):
    def test_haste_shortens_the_swing_not_the_cooldown(self):
        w = hammer()
        shots, _ = run(w, SW / 2 + 0.05, attack_speed_multiplier=2.0)   # half the swing
        self.assertEqual(len(shots), 1)
        self.assertAlmostEqual(w._cd, H["cooldown"], delta=0.05)

    def test_cooldown_reductions_shorten_the_cooldown_not_the_swing(self):
        w = hammer()
        mods = lambda weapon: WeaponMods(cooldown_mult=0.5)
        shots, _ = run(w, SW - 0.05, weapon_mods=mods)
        self.assertEqual(shots, [], "the swing is untouched")
        shots, _ = run(w, 0.1, weapon_mods=mods)
        self.assertEqual(len(shots), 1)
        self.assertAlmostEqual(w._cd, H["cooldown"] * 0.5, delta=0.05)
        w2 = hammer()
        w2.bonus["cooldown_mult"] = 0.5
        run(w2, SW + 0.05)
        self.assertAlmostEqual(w2._cd, H["cooldown"] * 0.5, delta=0.05)


class ForgeTests(unittest.TestCase):
    def test_earthshaker_swings_then_lands_the_blow_and_the_shockwave(self):
        w = hammer("earthshaker")
        shots, _ = run(w, SW - 0.08)
        self.assertEqual(shots, [])
        shots, _ = run(w, 0.15)
        kinds = sorted(getattr(s, "style", "") for s in shots)
        self.assertEqual(kinds, ["blast", "hidden"])
        blast = next(s for s in shots if s.style == "blast")
        self.assertAlmostEqual(blast.pos.x, 40.0)
        self.assertAlmostEqual(blast.radius, 90.0)

    def test_meteor_hammer_lands_its_crater_at_the_centre(self):
        w = hammer("meteor_hammer")
        craters = []
        run(w, SW + 0.05, spawn_hazard=lambda **kw: craters.append(kw))
        self.assertEqual(len(craters), 1)
        self.assertAlmostEqual(craters[0]["pos"].x, 40.0)
        self.assertAlmostEqual(craters[0]["dps"],
                               float(w.definition["damage"]) * 0.35)   # the Forge's lighter blow


class VisualTests(unittest.TestCase):
    def test_the_indicator_ramps_from_faint_to_dark(self):
        faint, dark = config.SLAM_INDICATOR_ALPHA
        self.assertEqual(slam_fx.indicator_alpha(0.0), faint)
        self.assertEqual(slam_fx.indicator_alpha(1.0), dark)
        mid = slam_fx.indicator_alpha(0.5)
        self.assertGreater(mid, faint)
        self.assertLess(mid, dark)
        self.assertGreater(faint, 0)
        self.assertLess(dark, 255)
        self.assertEqual(slam_fx.indicator_alpha(2.0), dark)

    def test_the_impact_is_requested_at_the_centre_with_the_rig(self):
        w = hammer()
        impacts = []
        run(w, SW + 0.05, spawn_impact=lambda **kw: impacts.append(kw))
        self.assertEqual(len(impacts), 1)
        self.assertEqual(impacts[0]["rig"], "hammer_impact")
        self.assertAlmostEqual(impacts[0]["pos"].x, 40.0)
        self.assertAlmostEqual(impacts[0]["radius"], H["area"])

    def test_pending_swings_report_centre_radius_and_progress(self):
        from types import SimpleNamespace
        w = hammer()
        run(w, SW / 2)
        ps = SimpleNamespace(player=SimpleNamespace(pos=pygame.Vector2(10, 10),
                                                    weapons=[w], stats={"area_multiplier": 1.0}))
        (weapon, centre, radius, progress), = slam_fx.pending_swings(ps)
        self.assertIs(weapon, w)
        self.assertAlmostEqual(centre.x, 50.0)
        self.assertAlmostEqual(radius, H["area"])
        self.assertAlmostEqual(progress, 0.5, delta=0.03)

    def test_the_impact_visual_plays_through_then_goes(self):
        from types import SimpleNamespace
        from game.assets import get_assets
        ps = SimpleNamespace(_impacts=[], game=SimpleNamespace(assets=get_assets()))
        assets = get_assets()
        slam_fx.spawn_impact(ps, pos=(0, 0), radius=52, rig="hammer_impact")
        self.assertEqual(len(ps._impacts), 1, "the base name resolves to a variant")
        # Read the length off the rig rather than writing it down: M13
        # replaced the five-frame splash with a fourteen-frame one and a
        # literal here would have to change again next time.
        rig = "hammer_impact_plain"
        span = assets.frame_count(rig, "loop") / assets.fps(rig, "loop")
        slam_fx.update_impacts(ps, span - 0.02)
        self.assertEqual(len(ps._impacts), 1)
        slam_fx.update_impacts(ps, 0.05)
        self.assertEqual(ps._impacts, [])
        slam_fx.spawn_impact(ps, pos=(0, 0), radius=52, rig="")
        self.assertEqual(ps._impacts, [])


if __name__ == "__main__":
    unittest.main()
