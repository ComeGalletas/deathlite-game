"""The surface an AI component is allowed to touch on the thing it drives.

`Enemy` and `Boss` both satisfy it, so one behaviour path serves both.
"""
from __future__ import annotations

from typing import Protocol

import pygame

from entities.ai.blackboard import Blackboard


class Actor(Protocol):
    pos: pygame.Vector2
    vel: pygame.Vector2
    radius: float
    speed: float
    alive: bool
    contact_damage: float
    facing: int
    bb: Blackboard
