"""Six-weapon system P4 (design §10, §11): the per-enemy hit memory, the
Rod's mark, the six explicit synergies, Hunter's Mark, and the 1.5 s window
every one of them shares and states."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat import synergy
from combat.weapons import Weapon
from game import config
from game.content import get_content
from game.states.playing.combat import CombatResolver
from progression.blessings import get_catalog
from tests.combat.fakes import FakeEnemy, fake_ps

C = get_content()
CAT = get_catalog(C)
W = config.SYNERGY_WINDOW_S


def owned(ps, wid, **effects):
    w = Weapon(wid, C.weapon(wid))
    w.effects.update(effects)
    ps.player.weapons.append(w)
    return w


def hit(ps, enemy, wid, damage=10.0, at=None, cone=None):
    """One hit by `wid` on `enemy` at run time `at` (defaults to the clock)."""
    if at is not None:
        ps.stats["time"] = at
    ps.projectiles.clear()
    kw = dict(pos=enemy.pos, vel=(0, 0), damage=damage, radius=20, lifetime=0.2,
              pierce=999, weapon_id=wid, source_tags=("ranged",))
    if cone is not None:                                # a swing from the origin
        kw.update(pos=(0, 0), cone_dir=cone, cone_half_angle=1.0, radius=60)
    ps._spawn_projectile(**kw)
    CombatResolver(ps).projectile_hits()


class WindowTests(unittest.TestCase):
    def test_the_window_is_one_and_a_half_seconds(self):
        self.assertAlmostEqual(W, 1.5)
        self.assertAlmostEqual(synergy.window(), 1.5)

    def test_every_synergy_card_states_the_window(self):
        syn = [b for b in CAT.by_id.values() if b.category == "synergy"]
        self.assertEqual(len(syn), 6 + 2, "the six of §10 plus Weak Point / Demolitionist")
        timed = ("syn_after_", "syn_vs_marked", "crossfire_", "hunters_")
        for b in syn:
            if any(e.key.startswith(timed) for e in b.effects):
                self.assertIn("1.5 s", b.describe(1), b.id)
        # Crowd Cleaner is the one behavioural synergy (a pull): no window.
        self.assertNotIn("1.5 s", CAT.get("sword_crowd_cleaner").describe(1))
        self.assertIn("1.5 s", CAT.get("bow_hunters_mark").describe(1))


class HitMemoryTests(unittest.TestCase):
    def test_a_hit_is_remembered_with_its_time_and_weapon(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "sword")
        hit(ps, e, "sword", at=3.0)
        self.assertEqual(e.recent_hits, {"sword": 3.0})
        self.assertEqual(e.hit_streak, {"sword": 1})

    def test_streak_grows_inside_the_window_and_restarts_outside(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "bow")
        hit(ps, e, "bow", at=0.0)
        hit(ps, e, "bow", at=1.0)
        hit(ps, e, "bow", at=2.4)                       # 1.4 s after the last
        self.assertEqual(e.hit_streak["bow"], 3)
        hit(ps, e, "bow", at=4.0)                       # 1.6 s: too late
        self.assertEqual(e.hit_streak["bow"], 1)

    def test_a_shot_from_no_weapon_records_nothing(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        hit(ps, e, "")
        self.assertEqual(e.recent_hits, {})

    def test_hit_within_respects_the_window_edge(self):
        e = FakeEnemy(0, 0)
        e.recent_hits["sword"] = 10.0
        self.assertTrue(synergy.hit_within(e, "sword", 11.49))
        self.assertFalse(synergy.hit_within(e, "sword", 11.51))
        self.assertFalse(synergy.hit_within(e, "bow", 10.0))


class MarkTests(unittest.TestCase):
    def test_the_rod_marks_what_it_hits_for_one_window(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "magic_rod")
        hit(ps, e, "magic_rod")
        self.assertTrue(synergy.is_marked(e))
        e.status.update(W - 0.01, lambda a: None)
        self.assertTrue(synergy.is_marked(e))
        e.status.update(0.02, lambda a: None)
        self.assertFalse(synergy.is_marked(e))

    def test_the_mark_is_data_on_the_rod_only(self):
        self.assertTrue(C.weapon("magic_rod").get("mark_on_hit"))
        for wid in ("sword", "hammer", "daggers", "bow", "bomb"):
            self.assertFalse(C.weapon(wid).get("mark_on_hit", False), wid)
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "bow")
        hit(ps, e, "bow")
        self.assertFalse(synergy.is_marked(e))


class PairTests(unittest.TestCase):
    """Each explicit pair: the bonus inside the window, none outside."""

    def _two(self, first, second, key, value):
        e_in, e_out = FakeEnemy(0, 0), FakeEnemy(0, 0)
        ps = fake_ps([e_in])
        owned(ps, first)
        owned(ps, second, **{key: value})
        hit(ps, e_in, first, at=0.0)
        hit(ps, e_in, second, at=1.4)
        ps.enemies = [e_out]
        hit(ps, e_out, first, at=5.0)
        hit(ps, e_out, second, at=6.6)
        return e_in.hp, e_out.hp

    def test_blood_in_the_water_sword_then_daggers(self):
        inside, outside = self._two("sword", "daggers", "syn_after_sword", 0.5)
        self.assertAlmostEqual(inside, 100 - 10 - 15)
        self.assertAlmostEqual(outside, 100 - 10 - 10)

    def test_linebreaker_hammer_then_bow(self):
        inside, outside = self._two("hammer", "bow", "syn_after_hammer", 1.0)
        self.assertAlmostEqual(inside, 100 - 10 - 20)
        self.assertAlmostEqual(outside, 80)

    def test_demolition_hammer_then_bomb(self):
        inside, outside = self._two("hammer", "bomb", "syn_after_hammer", 0.25)
        self.assertAlmostEqual(inside, 100 - 10 - 12.5)
        self.assertAlmostEqual(outside, 80)

    def test_marked_prey_rod_then_daggers(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "magic_rod")
        owned(ps, "daggers", syn_vs_marked=0.6)
        hit(ps, e, "magic_rod", at=0.0)
        e.status.update(0.5, lambda a: None)
        hit(ps, e, "daggers", at=0.5)
        self.assertAlmostEqual(e.hp, 100 - 10 - 16)
        e.status.update(2.0, lambda a: None)            # the mark is gone
        hit(ps, e, "daggers", at=2.5)
        self.assertAlmostEqual(e.hp, 100 - 10 - 16 - 10)

    def test_crossfire_both_halves(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "magic_rod")
        owned(ps, "bow", syn_vs_marked=0.5, crossfire_rod_bonus=0.5)
        hit(ps, e, "bow", at=0.0)                       # unmarked: plain
        self.assertAlmostEqual(e.hp, 90)
        hit(ps, e, "magic_rod", at=0.5)                 # bow hit 0.5 s ago: x1.5, and marks
        self.assertAlmostEqual(e.hp, 75)
        hit(ps, e, "bow", at=1.0)                       # marked: x1.5
        self.assertAlmostEqual(e.hp, 60)
        hit(ps, e, "magic_rod", at=3.0)                 # last bow hit 2 s ago: plain
        self.assertAlmostEqual(e.hp, 50)

    def test_a_synergy_needs_its_partner_to_have_hit(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "daggers", syn_after_sword=1.0)     # no sword hit ever
        hit(ps, e, "daggers")
        self.assertAlmostEqual(e.hp, 90)

    def test_synergy_bonuses_add_with_conditional_blessings(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "hammer")
        owned(ps, "bomb", syn_after_hammer=0.5, demolition_mult=0.5)
        e.status.apply("stun", 1.0, 1.0)
        hit(ps, e, "hammer", at=0.0)
        hit(ps, e, "bomb", at=0.5)                      # x1.5 (P2) x1.5 (P4)
        self.assertAlmostEqual(e.hp, 100 - 10 - 22.5)


class HuntersMarkTests(unittest.TestCase):
    def test_each_consecutive_arrow_adds_up_to_the_cap(self):
        e = FakeEnemy(0, 0, hp=10_000)
        ps = fake_ps([e])
        owned(ps, "bow", hunters_mark_per_hit=0.1, hunters_mark_max=3)
        dealt = []
        hp = e.hp
        for i in range(6):
            hit(ps, e, "bow", at=0.5 * i)
            dealt.append(hp - e.hp)
            hp = e.hp
        self.assertEqual([round(d, 6) for d in dealt], [10, 11, 12, 13, 13, 13])

    def test_a_gap_resets_the_ramp(self):
        e = FakeEnemy(0, 0, hp=10_000)
        ps = fake_ps([e])
        owned(ps, "bow", hunters_mark_per_hit=0.1, hunters_mark_max=5)
        hit(ps, e, "bow", at=0.0)
        hit(ps, e, "bow", at=1.0)
        hp = e.hp
        hit(ps, e, "bow", at=5.0)                       # 4 s later
        self.assertAlmostEqual(hp - e.hp, 10.0)


class CrowdCleanerTests(unittest.TestCase):
    def test_a_sword_hit_drags_the_target_toward_the_swing_centre(self):
        e = FakeEnemy(30, 20)                           # inside the cone, off its line
        ps = fake_ps([e])
        owned(ps, "sword", pull_strength=100)
        hit(ps, e, "sword", cone=pygame.Vector2(1, 0))  # centre at (30, 0)
        self.assertEqual(e.knocks, [100])
        self.assertLess(e._knock.y, 0)                  # dragged toward y = 0
        self.assertAlmostEqual(e._knock.x, 0.0, places=5)

    def test_no_pull_without_the_blessing(self):
        e = FakeEnemy(30, 20)
        ps = fake_ps([e])
        owned(ps, "sword")
        hit(ps, e, "sword", cone=pygame.Vector2(1, 0))
        self.assertEqual(e.knocks, [])                  # weightless test shot: nothing

    def test_pull_helper_aims_at_the_cone_centre(self):
        from types import SimpleNamespace
        e = FakeEnemy(0, 40)
        proj = SimpleNamespace(pos=pygame.Vector2(0, 0), cone_dir=pygame.Vector2(1, 0),
                               cone_half_angle=1.0, radius=80)
        synergy.pull(e, proj, 50)
        d = e._knock.normalize()
        want = (pygame.Vector2(40, 0) - e.pos).normalize()
        self.assertAlmostEqual(d.x, want.x, places=5)
        self.assertAlmostEqual(d.y, want.y, places=5)


if __name__ == "__main__":
    unittest.main()
