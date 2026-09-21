"""Six blessings per weapon (2026-09-19): the engine hooks the new cards
need -- crit damage, the ember ring's rehit / radius / reach, the summons'
bite interval / speed / leash, weapon on-hit statuses, Flurry, Pack Tactics,
Sticky Bomb and Powder Keg."""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat import synergy
from combat.weapons import FireContext, Weapon
from entities.player import Player
from game.content import get_content
from game.states.playing.core.combat import CombatResolver
from progression.blessings import apply_blessing, get_catalog
from tests.combat.fakes import FakeEnemy, fake_ps
from tests.combat.test_summons import SummonPool, fire_ctx

C = get_content()
CAT = get_catalog(C)
DT = 1 / 60


def weapon(wid, **effects):
    w = Weapon(wid, C.weapon(wid))
    w._cd = 0.0
    w.effects.update(effects)
    return w


def ctx(enemies, spawn, **over):
    base = dict(origin=pygame.Vector2(0, 0), enemies=list(enemies),
                damage_multiplier=1.0, attack_speed_multiplier=1.0,
                projectile_speed_multiplier=1.0, area_multiplier=1.0,
                fallback_dir=pygame.Vector2(1, 0), spawn_projectile=spawn,
                anchor=pygame.Vector2(0, 0))
    base.update(over)
    return FireContext(**base)


def sink_ctx(enemies, sink, **over):
    return ctx(enemies, lambda **kw: (sink.append(kw), kw)[1], **over)


def owned(ps, wid, **effects):
    w = weapon(wid, **effects)
    ps.player.weapons.append(w)
    return w


def hit(ps, enemy, wid, damage=10.0, at=None, tags=("ranged",)):
    if at is not None:
        ps.stats["time"] = at
    ps.projectiles.clear()
    ps._spawn_projectile(pos=enemy.pos, vel=(0, 0), damage=damage, radius=20,
                         lifetime=0.2, pierce=999, weapon_id=wid, source_tags=tags)
    CombatResolver(ps).projectile_hits()


def hero(*wids):
    p = Player(0, 0)
    p.weapons = [Weapon(w, C.weapon(w)) for w in wids]
    return p


class CritDamageTests(unittest.TestCase):
    def test_the_crit_damage_bonus_raises_a_crits_amount(self):
        sink = []
        w = weapon("bow")
        w.bonus["crit_chance"] = 1.0
        w.bonus["crit_damage"] = 0.5
        w.update(DT, sink_ctx([FakeEnemy(100, 0)], sink, crit_multiplier=2.0,
                              rng=random.Random(1)))
        self.assertTrue(sink[0]["is_crit"])
        self.assertAlmostEqual(sink[0]["damage"], 10 * 2.5)

    def test_critical_edge_carries_chance_and_damage(self):
        p = hero("sword")
        for _ in range(5):
            apply_blessing(p, CAT.get("sword_critical_edge"))
        w = p.weapons[0]
        self.assertAlmostEqual(w.bonus["crit_chance"], 0.25)
        self.assertAlmostEqual(w.bonus["crit_damage"], 0.5)


class EmberRingTests(unittest.TestCase):
    def _ring(self, enemy_x=50, **bonus):
        e = FakeEnemy(enemy_x, 0)
        ps = fake_ps([e])
        w = weapon("ember_ring")
        w.bonus.update(bonus)
        return ps, w, ctx([e], ps._spawn_projectile)

    def _embers(self, ps):
        return [p for p in ps.projectiles if p.active]

    def test_fanned_flames_spins_the_ring_and_shortens_the_rehit_on_live_embers(self):
        ps, w, c = self._ring()
        w.update(DT, c)
        d = C.weapon("ember_ring")
        rehit, speed = float(d["rehit_interval"]), float(d["orbit_speed"])
        self.assertTrue(all(abs(p.rehit_interval - rehit) < 1e-9 for p in self._embers(ps)))
        w.bonus["rehit_mult"] = 0.5
        w.bonus["orbit_speed_mult"] = 2.0
        w.update(DT, c)
        for p in self._embers(ps):
            self.assertAlmostEqual(p.rehit_interval, rehit * 0.5)
            self.assertLessEqual(p.rehit_timer, rehit * 0.5 + 1e-9)
            self.assertAlmostEqual(p.orbit_speed, speed * 2.0)

    def test_far_orbit_moves_the_ring_out(self):
        ps, w, c = self._ring(orbit_radius=60.0)
        w.update(DT, c)
        base = float(C.weapon("ember_ring")["orbit_radius"])
        self.assertTrue(self._embers(ps))
        self.assertTrue(all(abs(p.orbit_radius - (base + 60)) < 1e-9 for p in self._embers(ps)))

    def test_far_orbit_wakes_the_ring_further_away(self):
        reach = float(C.weapon("ember_ring")["reach"])
        ps, w, c = self._ring(enemy_x=reach + 50)
        w.update(DT, c)
        self.assertEqual(self._embers(ps), [], "outside the ring: the embers stay down")
        w.bonus["reach"] = 80.0
        self.assertAlmostEqual(w._reach(1.0), reach + 80)
        w.update(DT, c)
        self.assertTrue(self._embers(ps))


class SummonBonusTests(unittest.TestCase):
    def test_rapid_bolts_reach_the_planted_totem(self):
        w = weapon("grave_totem")
        w.bonus["attack_interval_mult"] = 0.5
        pool, shots = SummonPool(), []
        w.update(DT, fire_ctx(pool, shots))
        base = float(C.weapon("grave_totem")["summon_attack_interval"])
        self.assertAlmostEqual(pool.made[0].attack_interval, base * 0.5)

    def test_long_stride_speeds_and_leashes_the_wolf(self):
        w = weapon("spirit_wolf")
        w.bonus["summon_speed"] = 150.0
        w.bonus["summon_reach"] = 150.0
        pool, shots = SummonPool(), []
        w.update(DT, fire_ctx(pool, shots))
        d = C.weapon("spirit_wolf")
        self.assertAlmostEqual(pool.made[0].speed, float(d["summon_speed"]) + 150)
        self.assertAlmostEqual(pool.made[0].reach, float(d["summon_reach"]) + 150)

    def test_a_live_summon_picks_up_a_new_interval(self):
        w = weapon("spirit_wolf")
        pool, shots = SummonPool(), []
        w.update(DT, fire_ctx(pool, shots))
        wolf = pool.made[0]
        base = float(C.weapon("spirit_wolf")["summon_attack_interval"])
        wolf.attack_cd = 10.0                       # a long wait already banked
        w.bonus["attack_interval_mult"] = 0.5
        w.update(DT, fire_ctx(pool, shots))
        self.assertAlmostEqual(wolf.attack_interval, base * 0.5)
        self.assertLessEqual(wolf.attack_cd, base * 0.5)


class OnHitStatusTests(unittest.TestCase):
    def test_lacerate_bleeds_for_a_fraction_of_the_hit(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "daggers", bleed_on_hit_frac=0.1, bleed_on_hit_duration=2.0)
        hit(ps, e, "daggers", damage=20.0)
        self.assertIn("bleed", e.status)
        ticks = []
        e.status.update(0.4, lambda amount, source: ticks.append((amount, source)))
        self.assertEqual(ticks, [(2.0, "daggers")])

    def test_chilling_bolts_slow_the_target(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "grave_totem", chill_on_hit_potency=0.3, chill_on_hit_duration=1.5)
        hit(ps, e, "grave_totem")
        self.assertAlmostEqual(e.status.speed_multiplier(), 0.7)
        e.status.update(1.6, lambda amount, source: None)
        self.assertAlmostEqual(e.status.speed_multiplier(), 1.0)

    def test_a_status_needs_its_duration(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        owned(ps, "daggers", bleed_on_hit_frac=0.1)
        hit(ps, e, "daggers")
        self.assertNotIn("bleed", e.status)

    def test_scorch_through_the_catalog(self):
        p = hero("ember_ring")
        apply_blessing(p, CAT.get("ember_ring_scorch"))
        w = p.weapons[0]
        self.assertAlmostEqual(w.effects["burn_on_hit_frac"], 0.04)
        self.assertAlmostEqual(w.effects["burn_on_hit_duration"], 2.0)


class FlurryTests(unittest.TestCase):
    def test_stacks_shorten_the_cooldown_while_warm(self):
        w = weapon("daggers", flurry_per_hit=0.1, flurry_max=5)
        base = w._cooldown(1.0)
        w.note_flurry(3, 1.5)
        self.assertAlmostEqual(w._cooldown(1.0), base / 1.3)
        w.note_flurry(9, 1.5)                          # capped at flurry_max
        self.assertAlmostEqual(w._cooldown(1.0), base / 1.5)
        self.assertEqual(w.flurry_stacks, 5)
        w.update(1.6, sink_ctx([], []))                # the window passes
        self.assertEqual(w.flurry_stacks, 0)
        self.assertAlmostEqual(w._cooldown(1.0), base)

    def test_a_hit_feeds_the_targets_streak_to_the_weapon(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        w = owned(ps, "daggers", flurry_per_hit=0.1, flurry_max=5)
        for t in (0.0, 0.4, 0.8):
            hit(ps, e, "daggers", at=t)
        self.assertEqual(w.flurry_stacks, 3)
        hit(ps, e, "daggers", at=3.0)                  # outside the window: restarts
        self.assertEqual(w.flurry_stacks, 1)

    def test_a_weapon_without_flurry_ignores_streaks(self):
        w = weapon("daggers")
        base = w._cooldown(1.0)
        w.note_flurry(5, 1.5)
        self.assertAlmostEqual(w._cooldown(1.0), base)


class PackTacticsTests(unittest.TestCase):
    def test_needs_another_weapons_hit_inside_the_window(self):
        e = FakeEnemy(0, 0)
        ps = fake_ps([e])
        wolf = owned(ps, "spirit_wolf", pack_tactics_mult=0.5)
        e.recent_hits = {"spirit_wolf": 1.0}
        self.assertAlmostEqual(synergy.synergy_multiplier(ps.player, wolf, e, 1.5), 1.0)
        e.recent_hits["sword"] = 1.0
        self.assertAlmostEqual(synergy.synergy_multiplier(ps.player, wolf, e, 1.5), 1.5)
        self.assertAlmostEqual(synergy.synergy_multiplier(ps.player, wolf, e, 3.0), 1.0)


class StickyBombTests(unittest.TestCase):
    TAGS = ("ranged", "area", "explosive")

    def _bomb(self, ps, x, sticky=True):
        return ps._spawn_projectile(
            pos=(x, 0), vel=(300, 0), damage=20.0, radius=8, lifetime=1.1, pierce=0,
            weapon_id="bomb", source_tags=self.TAGS, inert=True, stop_after=1.0,
            blast_radius=42, blast_lifetime=0.12, sticky=sticky)

    def test_the_data_flag_rides_the_throw(self):
        sink = []
        weapon("bomb", sticky=1).update(DT, sink_ctx([FakeEnemy(40, 0)], sink))
        self.assertTrue(sink[0]["sticky"])
        sink = []
        weapon("bomb").update(DT, sink_ctx([FakeEnemy(40, 0)], sink))
        self.assertFalse(sink[0]["sticky"])

    def test_a_bomb_attaches_to_the_enemy_it_touches_and_rides_it(self):
        e = FakeEnemy(30, 0)
        ps = fake_ps([e])
        owned(ps, "bomb", sticky=1, sticky_damage_mult=0.5)
        p = self._bomb(ps, 25)
        CombatResolver(ps).projectile_hits()
        self.assertIs(p.stuck_to, e)
        self.assertEqual(p.vel.length(), 0.0)
        self.assertAlmostEqual(p.damage, 30.0)
        e.pos.update(80, 40)
        ps.fx.update_projectiles(DT)
        self.assertEqual(p.pos, e.pos)
        self.assertTrue(p.active)
        e.alive = False
        ps.fx.update_projectiles(DT)
        self.assertIsNone(p.stuck_to)

    def test_it_never_scores_a_direct_hit(self):
        e = FakeEnemy(30, 0)
        ps = fake_ps([e])
        owned(ps, "bomb", sticky=1, sticky_damage_mult=0.5)
        self._bomb(ps, 25)
        CombatResolver(ps).projectile_hits()
        self.assertEqual(e.hp, 100.0)

    def test_a_plain_bomb_does_not_stick(self):
        e = FakeEnemy(30, 0)
        ps = fake_ps([e])
        owned(ps, "bomb")
        p = self._bomb(ps, 25, sticky=False)
        CombatResolver(ps).projectile_hits()
        self.assertIsNone(p.stuck_to)


class PowderKegTests(unittest.TestCase):
    BLAST = ("ranged", "area", "explosive", "blast")

    def _kill(self, ps, enemy, shot):
        from game.states.playing.core.state import PlayingState
        enemy.alive = False
        enemy.killed_by = "bomb"
        enemy.killed_by_shot = shot
        PlayingState._apply_on_kill_effects(ps, enemy)
        return [p for p in ps.projectiles if p.active]

    def test_the_detonation_tags_its_blast(self):
        ps = fake_ps([])
        p = ps._spawn_projectile(pos=(0, 0), vel=(0, 0), damage=20.0, radius=8, lifetime=0.0,
                                 pierce=0, weapon_id="bomb", source_tags=StickyBombTests.TAGS,
                                 inert=True, blast_radius=42, blast_lifetime=0.12)
        ps.fx.detonate(p)
        blasts = [q for q in ps.projectiles if q.active and q.style == "blast"]
        self.assertEqual(len(blasts), 1)
        self.assertIn("blast", blasts[0].source_tags)

    def test_a_blast_kill_bursts_for_a_fraction_of_the_blast(self):
        e = FakeEnemy(50, 20)
        ps = fake_ps([e])
        owned(ps, "bomb", keg_frac=0.5)
        live = self._kill(ps, e, (self.BLAST, 40.0, 50.0))
        self.assertEqual(len(live), 1)
        keg = live[0]
        self.assertIn("keg", keg.source_tags)
        self.assertAlmostEqual(keg.damage, 20.0)
        self.assertAlmostEqual(keg.radius, 30.0)
        self.assertEqual(keg.pos, e.pos)
        self.assertEqual(keg.weapon_id, "bomb")

    def test_a_burst_never_bursts_again(self):
        e = FakeEnemy(50, 20)
        ps = fake_ps([e])
        owned(ps, "bomb", keg_frac=0.5)
        self.assertEqual(self._kill(ps, e, (self.BLAST + ("keg",), 20.0, 30.0)), [])

    def test_a_direct_hit_kill_does_not_burst(self):
        e = FakeEnemy(50, 20)
        ps = fake_ps([e])
        owned(ps, "bomb", keg_frac=0.5)
        self.assertEqual(self._kill(ps, e, (("ranged",), 40.0, 50.0)), [])

    def test_the_resolver_records_the_killing_shot(self):
        e = FakeEnemy(0, 0, hp=5.0)
        ps = fake_ps([e])
        owned(ps, "bomb")
        hit(ps, e, "bomb", damage=20.0, tags=self.BLAST)
        self.assertFalse(e.alive)
        self.assertEqual(e.killed_by_shot, (self.BLAST, 20.0, 20))


if __name__ == "__main__":
    unittest.main()
