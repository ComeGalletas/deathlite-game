"""Live and dormant: which enemies are simulated, and the records of the
ones that are not.

Spawn master S4. An enemy is **live** (an object in the run's list, full
AI) or **dormant** (a `DormantEnemy` record in `Population.dormant`, no
cost). The conversion is the host's business -- `host.sleep(enemy)` and
`host.wake(record, x, y)` -- because only the run knows what an `Enemy`
is; this module decides *when*.

**Hibernate**, every `tick` seconds: a live enemy whose island is not in
the active zone, whose owner is not in `never_sleep`, and whose pursuit
timer has lapsed, becomes a record. An enemy still chasing stays live
wherever it is; that is the chase the player is watching. One on a bridge
(no island under it) is left alone.

**Wake** when an island enters the zone: its records are queued, farthest
from the player first, and woken `wake_budget` per frame so a full island
never lands on one frame. A record's spot is checked for floor and a
blocked one moves to the nearest free spawn point on its floor; a record
asleep longer than `scatter_after` is re-placed on a random point of its
island instead, so the player cannot memorise where the threats stood.

Dormant records **freeze**: no movement, no healing, no regrouping.

Knobs from the `population` section of `data/spawn_tables.json`.
"""
from __future__ import annotations

import pygame

__all__ = ["DormantEnemy", "Population"]

_KEYS = ("tick", "wake_budget", "scatter_after")


class DormantEnemy:
    """What survives hibernation. Roughly 150 bytes; the world cap of 600
    is under 100 KB of these."""

    __slots__ = ("enemy_id", "room_id", "floor", "x", "y", "hp", "max_hp",
                 "shield_hp", "speed", "status", "owner", "spawned_at", "slept_at",
                 "recycles")

    def __init__(self, enemy_id: str, x: float, y: float, hp: float, max_hp: float,
                 shield_hp: float, speed: float, status=None, owner: str = "direct",
                 spawned_at: float = 0.0, room_id: int = -1, floor: int = 0,
                 slept_at: float = 0.0, recycles: int = 0) -> None:
        self.enemy_id = enemy_id
        self.x, self.y = float(x), float(y)
        self.hp, self.max_hp = float(hp), float(max_hp)
        self.shield_hp, self.speed = float(shield_hp), float(speed)
        self.status = status
        self.owner = owner
        self.spawned_at = float(spawned_at)
        self.room_id, self.floor = int(room_id), int(floor)
        self.slept_at = float(slept_at)
        self.recycles = int(recycles)      # S5: how often the watchdog moved it

    def __repr__(self) -> str:
        return (f"DormantEnemy({self.enemy_id!r}, room {self.room_id}, "
                f"({self.x:.0f}, {self.y:.0f}), hp {self.hp:.0f}/{self.max_hp:.0f})")


class Population:
    def __init__(self, knobs: dict, never_sleep=()) -> None:
        missing = [k for k in _KEYS if k not in knobs]
        if missing:
            raise KeyError(f"spawn_tables.json `population` lacks {missing}")
        self.tick = float(knobs["tick"])
        self.wake_budget = int(knobs["wake_budget"])
        self.scatter_after = float(knobs["scatter_after"])
        self.never_sleep = frozenset(never_sleep)
        self.dormant: dict[int, list[DormantEnemy]] = {}
        self.seeded: set[int] = set()          # islands that got their residents
        self._queue: list[DormantEnemy] = []   # waiting to wake, farthest first
        self._next_tick = 0.0
        self.slept = 0
        self.woken = 0

    # --- counts -----------------------------------------------------------
    @property
    def total_dormant(self) -> int:
        return sum(len(v) for v in self.dormant.values()) + len(self._queue)

    @property
    def waking(self) -> int:
        return len(self._queue)

    def dormant_in(self, room_id: int) -> int:
        return len(self.dormant.get(room_id, ()))

    # --- hibernate --------------------------------------------------------
    def hibernate(self, host, active, now: float) -> dict[int, int]:
        """Put the out-of-zone, idle enemies to sleep. Runs every `tick`
        seconds; returns `{room_id: count}` of what slept this call."""
        if now < self._next_tick:
            return {}
        self._next_tick = now + self.tick
        slept: dict[int, int] = {}
        for e in list(host.live_enemies()):
            if not getattr(e, "alive", True):
                continue
            if host.owner_of(e) in self.never_sleep:
                continue
            room = host.room_at(e.pos)
            if room is None or room.id in active:
                continue
            if host.is_pursuing(e):
                continue
            rec = host.sleep(e)
            rec.room_id = room.id
            rec.floor = host.floor_at(e.pos)
            rec.slept_at = now
            self.dormant.setdefault(room.id, []).append(rec)
            slept[room.id] = slept.get(room.id, 0) + 1
            self.slept += 1
        return slept

    # --- wake ---------------------------------------------------------------
    def activate(self, room_id: int, host) -> int:
        """Queue an island's records to wake, farthest from the player
        first. Returns how many were queued."""
        recs = self.dormant.pop(room_id, [])
        if not recs:
            return 0
        p = host.player_pos()
        recs.sort(key=lambda r: -((r.x - p.x) ** 2 + (r.y - p.y) ** 2))
        self._queue.extend(recs)
        return len(recs)

    def wake_some(self, host, index, placement, now: float) -> int:
        """Wake up to `wake_budget` queued records. Returns how many woke."""
        n = 0
        while self._queue and n < self.wake_budget:
            rec = self._queue.pop(0)
            x, y = self._spot(rec, host, index, placement, now)
            if x is None:
                # Nowhere to stand: keep it dormant in its island rather
                # than lose it; the next activation tries again.
                self.dormant.setdefault(rec.room_id, []).append(rec)
                continue
            host.wake(rec, x, y)
            self.woken += 1
            n += 1
        return n

    def _spot(self, rec: DormantEnemy, host, index, placement, now: float):
        radius = host.enemy_radius(rec.enemy_id)
        points = index.by_floor.get((rec.room_id, rec.floor)) or index.by_room.get(rec.room_id, [])
        if now - rec.slept_at >= self.scatter_after and points:
            free = self._free(points, host, radius, now, placement)
            if free:
                p = host.rng.choice(free)
                return p.x, p.y
        if host.is_walkable(pygame.Vector2(rec.x, rec.y), radius):
            return rec.x, rec.y
        free = self._free(points, host, radius, now, placement)
        if not free:
            return None, None
        p = min(free, key=lambda q: (q.x - rec.x) ** 2 + (q.y - rec.y) ** 2)
        return p.x, p.y

    @staticmethod
    def _free(points, host, radius: float, now: float, placement) -> list:
        body = 2.0 * radius
        out = []
        for p in points:
            if placement.on_cooldown(p, now):
                continue
            if not host.is_walkable(p.pos, radius):      # a hazard, a live wall
                continue
            if any((p.x - e.pos.x) ** 2 + (p.y - e.pos.y) ** 2 < body * body
                   for e in host.neighbors_near(p.pos, body)
                   if getattr(e, "alive", True)):
                continue
            out.append(p)
        return out
