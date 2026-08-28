"""R1 -- the composable-AI scaffold (`entities/ai/`): Blackboard, Steering, the
Component/Transition/Behavior machine, and the name registry. No behaviours or
game wiring yet -- just that the pieces compose."""
import random
import unittest
from dataclasses import dataclass
from types import SimpleNamespace

import pygame

from entities.ai import (Behavior, Blackboard, Component, Steering, Transition,
                         behavior, build_behavior, registered)


def _actor(**kw):
    d = dict(pos=pygame.Vector2(0, 0), vel=pygame.Vector2(), radius=10.0,
             speed=100.0, alive=True, contact_damage=1.0, facing=-1,
             bb=Blackboard())
    d.update(kw)
    return SimpleNamespace(**d)


def _per(dt=0.1):
    return SimpleNamespace(dt=dt, now=0.0, player_pos=pygame.Vector2(300, 0),
                           player=object(), rng=random.Random(0))


@dataclass
class Push(Component):
    dx: float = 1.0
    dy: float = 0.0

    def tick(self, actor, per, cmb, acc):
        acc.add(pygame.Vector2(self.dx, self.dy))


@dataclass
class Count(Component):
    def tick(self, actor, per, cmb, acc):
        s = actor.bb.slot(self.key)
        s["n"] = s.get("n", 0) + 1


class BlackboardTests(unittest.TestCase):
    def test_slots_are_isolated_stable_and_clearable(self):
        bb = Blackboard()
        bb.slot("a")["x"] = 1
        self.assertIs(bb.slot("a"), bb.slot("a"))
        self.assertEqual(bb.slot("a")["x"], 1)
        self.assertEqual(bb.slot("b"), {})
        self.assertIsNot(bb.slot("a"), bb.slot("b"))
        self.assertIn("a", bb)
        bb.clear()
        self.assertNotIn("a", bb)
        self.assertEqual(bb.slot("a"), {})


class SteeringTests(unittest.TestCase):
    def test_empty_resolves_to_zero(self):
        self.assertEqual(Steering().resolve(100), pygame.Vector2())
        self.assertTrue(Steering().is_empty)

    def test_forces_sum_then_normalise_to_speed(self):
        s = Steering()
        s.add(pygame.Vector2(1, 0))
        s.add(pygame.Vector2(0, 1))
        out = s.resolve(100)
        self.assertAlmostEqual(out.length(), 100)
        self.assertAlmostEqual(out.x, out.y)

    def test_weight_scales_a_force(self):
        s = Steering()
        s.add(pygame.Vector2(1, 0), weight=3.0)
        s.add(pygame.Vector2(-1, 0), weight=1.0)
        self.assertGreater(s.resolve(100).x, 0)

    def test_set_velocity_overrides_the_force_sum(self):
        s = Steering()
        s.add(pygame.Vector2(1, 0))
        s.set_velocity(pygame.Vector2(0, -640))
        self.assertEqual(s.resolve(100), pygame.Vector2(0, -640))


class BehaviorTests(unittest.TestCase):
    def test_single_state_runs_components_and_sets_vel(self):
        a = _actor()
        Behavior({"move": [Push(1, 0)]}).tick(a, _per(), None)
        self.assertAlmostEqual(a.vel.length(), a.speed)
        self.assertGreater(a.vel.x, 0)

    def test_empty_state_roots_the_actor(self):
        a = _actor(vel=pygame.Vector2(50, 50))
        Behavior({"idle": []}).tick(a, _per(), None)
        self.assertEqual(a.vel, pygame.Vector2())

    def test_component_state_is_isolated_per_actor(self):
        b = Behavior({"move": [Count()]})
        a1, a2 = _actor(), _actor()
        for _ in range(3):
            b.tick(a1, _per(), None)
        b.tick(a2, _per(), None)
        key = b.states["move"][0].key
        self.assertEqual(a1.bb.slot(key)["n"], 3)
        self.assertEqual(a2.bb.slot(key)["n"], 1)

    def test_time_in_state_accumulates_and_resets_on_transition(self):
        gate = {"go": False}
        b = Behavior(states={"a": [], "b": []},
                     transitions=[Transition("a", "b", lambda ac, pe: gate["go"])])
        a = _actor()
        b.tick(a, _per(0.1), None)
        b.tick(a, _per(0.1), None)
        self.assertAlmostEqual(b.time_in_state(a), 0.2)
        gate["go"] = True
        b.tick(a, _per(0.1), None)                 # transition fires this tick
        self.assertEqual(b.state_of(a), "b")
        self.assertEqual(b.time_in_state(a), 0.0)

    def test_transition_is_checked_after_the_state_ticks(self):
        gate = {"go": False}
        b = Behavior(states={"a": [Push(1, 0)], "b": [Push(-1, 0)]},
                     transitions=[Transition("a", "b", lambda ac, pe: gate["go"])])
        a = _actor()
        gate["go"] = True
        b.tick(a, _per(), None)                    # "a" ran, THEN we moved to "b"
        self.assertEqual(b.state_of(a), "b")
        self.assertGreater(a.vel.x, 0)             # this frame still shows "a"'s push
        b.tick(a, _per(), None)
        self.assertLess(a.vel.x, 0)               # now "b"

    def test_rejects_bad_construction(self):
        with self.assertRaises(ValueError):
            Behavior({})
        with self.assertRaises(ValueError):
            Behavior({"a": []}, initial="z")
        with self.assertRaises(KeyError):
            Behavior({"a": []}).set_state(_actor(), "nope")


@behavior("__scaffold_demo__")
def _demo(cfg):
    return Behavior({"move": [Push(cfg.get("dx", 1.0), 0.0)]})


class RegistryTests(unittest.TestCase):
    def test_build_behavior_passes_cfg_to_the_builder(self):
        a = _actor()
        build_behavior("__scaffold_demo__", {"dx": -3.0}).tick(a, _per(), None)
        self.assertLess(a.vel.x, 0)

    def test_build_behavior_defaults_cfg_to_empty(self):
        a = _actor()
        build_behavior("__scaffold_demo__").tick(a, _per(), None)
        self.assertGreater(a.vel.x, 0)

    def test_registered_lists_names(self):
        self.assertIn("__scaffold_demo__", registered())

    def test_unknown_name_raises_with_the_list(self):
        with self.assertRaises(KeyError) as cm:
            build_behavior("does_not_exist")
        self.assertIn("registered:", str(cm.exception))

    def test_double_registration_raises(self):
        with self.assertRaises(ValueError):
            behavior("__scaffold_demo__")(_demo)


if __name__ == "__main__":
    unittest.main()
