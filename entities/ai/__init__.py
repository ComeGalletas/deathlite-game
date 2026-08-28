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
from entities.ai.context import Combat, Perception
from entities.ai.machine import Behavior, Component, Transition
from entities.ai.registry import behavior, build_behavior, registered
from entities.ai.steering import Steering

__all__ = [
    "Actor", "Blackboard", "Combat", "Perception",
    "Behavior", "Component", "Transition", "Steering",
    "behavior", "build_behavior", "registered",
]
