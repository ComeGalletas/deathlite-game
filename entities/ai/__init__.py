"""Composable enemy AI (refactor -- see journals/enemy_ai.md).

R1 scaffold: the interfaces and the machine, no behaviours yet.

Public surface:
    Perception, Combat   -- the two things the AI needs from the host game
    Actor                -- what a component may touch on the entity it drives
    Blackboard           -- per-actor, per-component scratch state
    Steering             -- movement-intent accumulator
    Component, Transition, Behavior
    behavior, build_behavior, registered   -- the name registry
"""
from entities.ai.actor import Actor
from entities.ai.blackboard import Blackboard
from entities.ai.components import (AvoidObstacles, Blink, CastHazard, Charge,
                                    Cooldown, Explode, Explosion, FireProjectile,
                                    Flee, MaintainRange, OnEnter, SeekTarget,
                                    Separation, SummonBrood, Unstick, after,
                                    all_of, any_of, in_range, out_of_range, ready)
from entities.ai.context import Combat, Perception
from entities.ai.machine import (ATTACK_SLOT, Behavior, Component, OneShot,
                                 Transition, time_in_state)
from entities.ai.registry import behavior, build_behavior, registered
from entities.ai.steering import Steering
from entities.ai import behaviors as _behaviors  # noqa: F401  -- runs @behavior registration

__all__ = [
    "Actor", "Blackboard", "Combat", "Perception",
    "Behavior", "Component", "OneShot", "Transition", "Steering",
    "ATTACK_SLOT", "time_in_state",
    "behavior", "build_behavior", "registered",
    # steering (R2)
    "SeekTarget", "Flee", "MaintainRange", "Separation", "AvoidObstacles", "Unstick",
    # timing / predicates (R4)
    "Cooldown", "OnEnter", "after", "in_range", "out_of_range", "ready",
    "all_of", "any_of",
    # actions (R4)
    "FireProjectile", "SummonBrood", "CastHazard",
    "Charge", "Blink", "Explosion", "Explode",
]
