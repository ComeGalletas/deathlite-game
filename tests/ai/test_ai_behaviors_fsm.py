"""`entities/ai/behaviors/ranged.py` + `melee.py` -- kite_shoot, summoner,
exploder, brute, fsm_charger, fsm_teleporter, fsm_warlock. Behaviour checks
against fakes (the flow field is silent, so movement is straight `_toward`)."""
import random
import unittest
from types import SimpleNamespace

import pygame

from entities.ai import Blackboard, build_behavior


def _enemy(pos, cfg=None, speed=90.0, radius=15.0, hp=200.0):
    return SimpleNamespace(pos=pygame.Vector2(pos), vel=pygame.Vector2(),
                           radius=radius, speed=speed, alive=True, hp=hp,
                           contact_damage=10.0, _base_contact=10.0, contact_cd=9.0,
                           facing=-1, cfg=dict(cfg or {}), bb=Blackboard())


def _calls():
    return {"fire": [], "summon": [], "explosion": [], "hazard": []}


def _ctx(dt, player, calls, rng):
    return SimpleNamespace(
        dt=dt, now=0.0, player_pos=pygame.Vector2(player), player=object(), rng=rng,
        nav_dir=lambda p, r: pygame.Vector2(),
        neighbors=lambda p, r: [], obstacles_near=lambda p, r: [],
        is_walkable=lambda p, r: True, resolve_movement=lambda a, b, r: b,
        fire_projectile=lambda **k: calls["fire"].append(round(k["damage"])),
        summon=lambda i, p, n: calls["summon"].append((i, n)),
        explosion=lambda p, r, d: calls["explosion"].append((round(r), round(d))),
        spawn_hazard=lambda p, r, dps, dur, tick=None: calls["hazard"].append(round(r)),
        report_damage=lambda a: None)


DT = 1 / 60


def _drive(name, cfg, frames, player_at):
    e = _enemy((0.0, 0.0), cfg)
    beh = build_behavior(name, cfg)
    calls = _calls()
    states, phase_speed = set(), {}
    for f in range(frames):
        pp = player_at(f)
        e.contact_damage = 10.0
        st = beh.state_of(e)                        # state whose components run now
        beh.tick(e, _ctx(DT, pp, calls, random.Random(f)),
                 _ctx(DT, pp, calls, random.Random(f)))
        states.add(st)
        phase_speed.setdefault(st, []).append(e.vel.length())
        e.pos += e.vel * DT
    return beh, e, calls, states, phase_speed


class TimerFreeMoverTests(unittest.TestCase):
    def test_kite_shoot_holds_range_and_fires_on_interval(self):
        _b, _e, c, states, sp = _drive(
            "kite_shoot", {"prefer_distance": 260, "shoot_interval": 1.2},
            420, lambda f: (0.0, -max(70, 520 - f)))
        self.assertEqual(states, {"move"})
        self.assertGreater(len(c["fire"]), 2)              # several shots
        self.assertEqual(set(c["fire"]), {6})              # default shoot_damage
        # while sitting in the hold band the actor roots
        self.assertIn(0.0, [round(s, 3) for s in sp["move"]])

    def test_summoner_summons_on_interval_and_backs_off_when_close(self):
        _b, _e, c, _states, sp = _drive(
            "summoner", {"summon_interval": 0.8, "summon_count": 3},
            360, lambda f: (0.0, -(400 if f < 180 else 120)))
        self.assertGreater(len(c["summon"]), 3)
        self.assertEqual(c["summon"][0], ("swarm", 3))
        self.assertAlmostEqual(max(sp["move"]), 90, delta=1)   # full-speed retreat

    def test_exploder_detonates_inside_the_fuse_range(self):
        _b, e, _c, _s, _sp = _drive(
            "exploder", {"fuse_range": 34}, 240,
            lambda f: (0.0, -max(20, 320 - f * 2)))
        self.assertFalse(e.alive)


class TelegraphFsmTests(unittest.TestCase):
    def test_charger_cycles_and_dashes_at_charge_speed(self):
        _b, _e, _c, states, sp = _drive(
            "fsm_charger",
            {"charge_range": 320, "charge_interval": 1.2, "charge_telegraph": 0.4,
             "charge_duration": 0.4, "charge_recover": 0.6, "charge_speed": 600,
             "charge_damage": 30}, 600, lambda f: (0.0, -140))
        self.assertEqual(states, {"chase", "telegraph", "attack", "recover"})
        self.assertEqual(max(sp["attack"]), 600)
        self.assertLess(max(sp["telegraph"]), 1e-6)
        self.assertAlmostEqual(max(sp["recover"]), 27, delta=1)    # 0.3 * speed
        self.assertAlmostEqual(max(sp["chase"]), 90, delta=1)

    def test_brute_telegraphs_then_slams_repeatedly(self):
        _b, _e, c, states, _sp = _drive(
            "brute",
            {"slam_interval": 1.2, "slam_range": 150, "slam_radius": 130,
             "slam_damage": 30, "slam_telegraph": 0.5}, 600, lambda f: (0.0, -80))
        self.assertEqual(states, {"chase", "telegraph"})
        self.assertGreaterEqual(len(c["explosion"]), 3)
        self.assertEqual(set(c["explosion"]), {(130, 30)})

    def test_teleporter_blinks_toward_the_player(self):
        _b, e, _c, states, sp = _drive(
            "fsm_teleporter",
            {"blink_trigger": 500, "blink_interval": 1.0, "blink_telegraph": 0.4,
             "blink_duration": 0.3, "blink_recover": 0.6, "blink_range": 70},
            400, lambda f: (0.0, -200.0))
        self.assertEqual(states, {"chase", "telegraph", "attack", "recover"})
        self.assertLess(max(sp["telegraph"] + sp["attack"]), 1e-6)   # rooted
        self.assertLess((e.pos - pygame.Vector2(0, -200)).length(), 120)

    def test_warlock_casts_a_hazard_each_cycle(self):
        _b, _e, c, states, _sp = _drive(
            "fsm_warlock",
            {"cast_range": 400, "cast_interval": 1.4, "cast_telegraph": 0.5,
             "cast_duration": 0.2, "cast_recover": 0.8, "hazard_radius": 92},
            500, lambda f: (0.0, -260))
        self.assertEqual(states, {"chase", "telegraph", "attack", "recover"})
        self.assertGreaterEqual(len(c["hazard"]), 2)
        self.assertEqual(set(c["hazard"]), {92})


if __name__ == "__main__":
    unittest.main()
