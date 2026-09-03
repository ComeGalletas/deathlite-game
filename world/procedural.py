"""The public entry point to world generation.

Generation lives in the `world.gen` package and the data model in
`world.layout`; this module re-exports the names gameplay and the tests
import: `generate_world`, `SPECIAL_KINDS`, the model types, and a few
private helpers.
"""
from __future__ import annotations

from world.layout import Corridor, Room, TileMeta, WorldLayout
from world.gen import generate_world
from world.gen.tuning import (
    SPECIAL_KINDS, _HOUSE_RADIUS, _VILLAGE_MIN_ROOM_CELLS, _VILLAGE_RADIUS,
)
from world.gen.rooms import _four_connected
from world.gen.scatter import _corridor_doorways

__all__ = [
    "generate_world", "SPECIAL_KINDS",
    "Corridor", "Room", "TileMeta", "WorldLayout",
    "_four_connected", "_corridor_doorways", "_HOUSE_RADIUS",
    "_VILLAGE_MIN_ROOM_CELLS", "_VILLAGE_RADIUS",
]
