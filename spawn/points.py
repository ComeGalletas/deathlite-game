"""Spawn points and resource anchors, indexed for the run.

The records themselves are part of the world data model
(`world/layout.py`), because `generate_world` produces them; this is the
read side. `PointIndex` groups a layout's points by island and by
`(island, floor)` once, so placement (S3) and the dev overlay ask a dict
instead of scanning the list.
"""
from __future__ import annotations

from world.layout import ResourcePoint, SpawnPoint

__all__ = ["PointIndex", "ResourcePoint", "SpawnPoint"]


class PointIndex:
    def __init__(self, layout) -> None:
        self.spawn: list[SpawnPoint] = list(getattr(layout, "spawn_points", ()))
        self.resource: list[ResourcePoint] = list(getattr(layout, "resource_points", ()))
        self.by_room: dict[int, list[SpawnPoint]] = {}
        self.by_floor: dict[tuple[int, int], list[SpawnPoint]] = {}
        for p in self.spawn:
            self.by_room.setdefault(p.room_id, []).append(p)
            self.by_floor.setdefault((p.room_id, p.floor), []).append(p)
        self.resource_by_room: dict[int, list[ResourcePoint]] = {}
        for p in self.resource:
            self.resource_by_room.setdefault(p.room_id, []).append(p)

    def __len__(self) -> int:
        return len(self.spawn)

    def in_rooms(self, room_ids) -> list[SpawnPoint]:
        """Every enemy point on the given islands, in layout order."""
        wanted = set(room_ids)
        return [p for p in self.spawn if p.room_id in wanted]

    def rooms(self) -> list[int]:
        return sorted(self.by_room)
