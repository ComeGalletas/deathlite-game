"""AI building blocks.

Steering (R2): SeekTarget, Flee, MaintainRange, Separation, AvoidObstacles, Unstick
Timing / machine (R4): Cooldown, OnEnter + the transition predicates
Actions (R4): FireProjectile, SummonBrood, CastHazard, Charge, Blink, Explosion, Explode
"""
from entities.ai.components.attacks import Blink, Charge, Explode, Explosion
from entities.ai.components.crowd import AvoidObstacles, Separation
from entities.ai.components.ranged import CastHazard, FireProjectile, SummonBrood
from entities.ai.components.recovery import Unstick
from entities.ai.components.seek import Flee, MaintainRange, SeekTarget
from entities.ai.components.timing import (Cooldown, OnEnter, after, all_of,
                                           any_of, in_range, out_of_range, ready)

__all__ = [
    "SeekTarget", "Flee", "MaintainRange", "Separation", "AvoidObstacles", "Unstick",
    "Cooldown", "OnEnter",
    "after", "in_range", "out_of_range", "ready", "all_of", "any_of",
    "FireProjectile", "SummonBrood", "CastHazard",
    "Charge", "Blink", "Explosion", "Explode",
]
