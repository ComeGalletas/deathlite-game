"""R4 -- timing/predicate plumbing and the attack/action components, ticked
against fakes. Plus a mini telegraph->attack->recover machine wired from the
new pieces to prove the FSM pattern composes."""
import random
import unittest
from types import SimpleNamespace

import pygame

from entities.ai import (ATTACK_SLOT, Behavior, Blackboard, Blink, CastHazard,
                         Charge, Cooldown, Explode, Explosion, FireProjectile,
                         OnEnter, SeekTarget, SummonBrood, Transition, after,
                         in_range, ready)


def _actor(pos=(0.0, 0.0), speed=100.0, radius=10.0, hp=10.0):
    return SimpleNamespace(pos=pygame.Vector2(pos), vel=pygame.Vector2(),
                           radius=radius, speed=speed, alive=True, hp=hp,
                           contact_damage=1.0, contact_cd=5.0, facing=-1,
                           bb=Blackboard())


def _per(player=(0.0, -200.0), dt=0.1, seed=0):
    return SimpleNamespace(dt=dt, now=0.0, player_pos=pygame.Vector2(player),
                           player=object(), rng=random.Random(seed),
                           nav_dir=lambda p, r: pygame.Vector2(),
                           neighbors=lambda p, r: [], obstacles_near=lambda p, r: [],
                           is_walkable=lambda p, r: True,
                           resolve_movement=lambda a, b, r, **kw: b)


def _spy_combat():
    calls = {"fire": [], "summon": [], "explosion": [], "hazard": []}
    return SimpleNamespace(
        fire_projectile=lambda **kw: calls["fire"].append(kw),
        summon=lambda i, p, n: calls["summon"].append((i, n)),
        explosion=lambda p, r, d: calls["explosion"].append((r, d)),
        spawn_hazard=lambda p, r, dps, dur, tick=None, sprite=None:
            calls["hazard"].append((tuple(p), r, dps, dur)),
        report_damage=lambda a: None), calls


def _tick_one(comp, actor, per, cmb=None):
    from entities.ai import Steering
    comp.key = comp.key or "t#0:x"
    comp.tick(actor, per, cmb, Steering())


class CooldownTests(unittest.TestCase):
    def test_counts_down_and_reloads(self):
        cd = Cooldown(seconds=0.3, start_ready=False)
        cd.key = "cd"
        a = _actor()
        self.assertFalse(cd.ready(a))
        for _ in range(3):
            _tick_one(cd, a, _per(dt=0.1))
        self.assertTrue(cd.ready(a))
        cd.trigger(a)
        self.assertFalse(cd.ready(a))

    def test_start_ready_begins_ready(self):
        cd = Cooldown(seconds=1.0, start_ready=True)
        cd.key = "cd"
        a = _actor()
        _tick_one(cd, a, _per())
        self.assertTrue(cd.ready(a))


class PredicateTests(unittest.TestCase):
    def test_in_range_and_after(self):
        a = _actor(pos=(0, 0))
        self.assertTrue(in_range(250)(a, _per(player=(0, -200))))
        self.assertFalse(in_range(150)(a, _per(player=(0, -200))))
        a.bb.slot("__machine__")["entered"] = 0.5
        self.assertTrue(after(0.4)(a, _per()))
        self.assertFalse(after(0.9)(a, _per()))


class ActionComponentTests(unittest.TestCase):
    def test_fire_projectile_respects_interval_and_range(self):
        fp = FireProjectile(interval=0.5, damage=7, speed=200, radius=6,
                            max_range=100)
        fp.key = "fp"
        a = _actor(pos=(0, 0))
        cmb, calls = _spy_combat()
        # player out of range -> no shot even once the timer elapses
        for _ in range(10):
            fp.tick(a, _per(player=(0, -400), dt=0.1), cmb, None)
        self.assertEqual(calls["fire"], [])
        # in range -> one shot when the timer hits zero, then every `interval`
        for _ in range(6):
            fp.tick(a, _per(player=(0, -50), dt=0.1), cmb, None)
        self.assertEqual(len(calls["fire"]), 1)

    def test_summon_brood_on_interval(self):
        sb = SummonBrood(interval=0.3, enemy_id="swarm", count=3)
        sb.key = "sb"
        a = _actor()
        cmb, calls = _spy_combat()
        for _ in range(7):
            sb.tick(a, _per(dt=0.1), cmb, None)
        self.assertGreaterEqual(len(calls["summon"]), 2)
        self.assertEqual(calls["summon"][0], ("swarm", 3))

    def test_explode_kills_the_actor_in_fuse_range(self):
        ex = Explode(fuse_range=40)
        ex.key = "ex"
        far = _actor(pos=(0, 0))
        ex.tick(far, _per(player=(0, -100)), None, None)
        self.assertTrue(far.alive)
        near = _actor(pos=(0, 0))
        ex.tick(near, _per(player=(0, -30)), None, None)
        self.assertFalse(near.alive)
        self.assertEqual(near.hp, 0.0)

    def test_blink_teleports_near_the_player_and_is_deterministic(self):
        def run():
            b = Blink(min_offset=20, max_offset=70, damage=16)
            b.key = "b"
            a = _actor(pos=(500, 0))
            a.bb.slot("__machine__")["visit"] = 1        # simulate a fresh entry
            b.tick(a, _per(player=(0, 0), seed=3), None, None)
            return tuple(round(v, 4) for v in a.pos), a.contact_damage
        r1 = run()
        r2 = run()
        self.assertEqual(r1, r2)
        self.assertLess(pygame.Vector2(r1[0]).length(), 80)   # landed near (0,0)


class FSMPatternTests(unittest.TestCase):
    """chase -> telegraph (rooted) -> attack (one blast) -> recover -> chase,
    wired from Cooldown / SeekTarget / Explosion / OnEnter / predicates."""

    def _behaviour(self):
        cd = Cooldown(seconds=2.0, start_ready=False)

        def lock_dir(actor, per, cmb):
            actor.bb.slot(ATTACK_SLOT)["dir"] = pygame.Vector2(0, -1)

        return Behavior(
            always=[cd],
            states={
                "chase":     [SeekTarget(via="straight", slew=0.0)],
                "telegraph": [],
                "attack":    [Explosion(radius=100, damage=20)],
                "recover":   [SeekTarget(via="straight", slew=0.0, weight=0.3)],
            },
            transitions=[
                Transition("chase", "telegraph",
                           when=lambda a, p: in_range(120)(a, p) and cd.ready(a)),
                Transition("telegraph", "attack", when=after(0.3), on=lock_dir),
                Transition("attack", "recover", when=after(0.2)),
                Transition("recover", "chase",
                           when=after(0.4), on=lambda a, p, c: cd.trigger(a)),
            ],
            initial="chase",
        )

    def test_full_cycle(self):
        b = self._behaviour()
        a = _actor(pos=(0, 0), speed=100)
        cmb, calls = _spy_combat()
        seen = []
        for _ in range(200):
            b.tick(a, _per(player=(0, -80), dt=1 / 60), cmb)
            seen.append(b.state_of(a))
        self.assertEqual({"chase", "telegraph", "attack", "recover"} & set(seen),
                         {"chase", "telegraph", "attack", "recover"})
        self.assertGreaterEqual(len(calls["explosion"]), 1)      # blast fired
        # exactly one blast per attack visit (not once per frame)
        attack_frames = seen.count("attack")
        self.assertGreater(attack_frames, 3)
        self.assertLess(len(calls["explosion"]), attack_frames)

    def test_rooted_during_telegraph(self):
        b = self._behaviour()
        a = _actor(pos=(0, 0), speed=100)
        cmb, _ = _spy_combat()
        # drive to telegraph
        for _ in range(300):
            b.tick(a, _per(player=(0, -80), dt=1 / 60), cmb)
            if b.state_of(a) == "telegraph":
                break
        self.assertEqual(b.state_of(a), "telegraph")
        b.tick(a, _per(player=(0, -80), dt=1 / 60), cmb)
        self.assertEqual(a.vel, pygame.Vector2())


if __name__ == "__main__":
    unittest.main()
