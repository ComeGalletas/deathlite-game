"""Compatibility shim -- world generation moved to the `world.gen` package
and the data model to `world.layout` (W0/W1 of journals/world_refactor.md).

Kept because tests and gameplay import `generate_world`, `SPECIAL_KINDS`, the
model types, and a few private helpers straight from `world.procedural`.
"""
from __future__ import annotations

from world.layout import Corridor, Room, Stair, TileMeta, WorldLayout
from world.gen import generate_world
from world.gen.tuning import (
    SPECIAL_KINDS, _HOUSE_RADIUS, _VILLAGE_MIN_ROOM_CELLS, _VILLAGE_RADIUS,
)
from world.gen.rooms import _four_connected
from world.gen.scatter import _corridor_doorways

__all__ = [
    "generate_world", "SPECIAL_KINDS",
    "Corridor", "Room", "Stair", "TileMeta", "WorldLayout",
    "_four_connected", "_corridor_doorways", "_HOUSE_RADIUS",
    "_VILLAGE_MIN_ROOM_CELLS", "_VILLAGE_RADIUS",
]
