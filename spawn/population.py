"""Live and dormant: which enemies are simulated, and the records of the
ones that are not.

Spawn master S4. An enemy is **live** (an object in the run's list, full
AI) or **dormant** (a `DormantEnemy` record in `Population.dormant`, no
cost). The conversion is the host's business -- `host.sleep(enemy)` and
`host.wake(record, x, y)` -- because only the run knows what an `Enemy`
is; this module decides *when*.

**The ring** (owner, 2026-09-18/19) is the rule that matters most. A live
body further than `despawn_radius` from the hero is hibernated **whatever
island it stands on and whether or not it is chasing** -- distance wins.
That is what stops a tail of abandoned bodies holding live-cap slots the
player will never meet: before it, a body could stand three screens away on
the hero's own island, fully simulated, for the whole run, because the
hero's island is always in the zone.

**Hibernate**, every `tick` seconds, sleeps a body when either rule fires:

1. the **ring** -- it is beyond `despawn_radius`; or
2. the **zone** -- its island is not in the active zone *and* its pursuit
   timer has lapsed. Inside the ring a chaser still stays live, because that
   is the chase the player is watching and it is close enough to matter.

An owner in `never_sleep` is exempt from both. One on a bridge (no island
under it) is left alone, because a record is filed by island and there is
none to file it under.

**Wake** happens two ways, and the second is what the ring made necessary:

* when an **island enters the zone**, its records are queued farthest from
  the player first;
* when the hero comes within `wake_radius` of a record, wherever it is
  filed. Without this, a body the ring slept on an island the hero never
  left would be stranded: `activate` only fires on a zone *entry*, which
  that island never makes.

`wake_radius` sits **inside** `despawn_radius` on purpose. The gap is
hysteresis -- without it a body pacing the boundary would sleep and wake on
alternate ticks.

Either way the queue is drained `wake_budget` per frame so a full island
never lands on one frame. A record's spot is checked for floor and a
blocked one moves to the nearest free spawn point on its floor; a record
asleep longer than `scatter_after` is re-placed on a random point of its
island instead, so the player cannot memorise where the threats stood.

Records are bounded by `dormant_cap`, past which the **oldest-slept** is
dropped. That is a rail rather than a mechanism: the measured peak in play
is 20 records for a hero standing still, 22 for one patrolling and 1304 for
one touring every island, against a cap several times higher. It exists so
that a run nobody anticipated cannot grow the list forever.

Waking does **not** consult the live cap. It may push the live count past
it, and when that happens the company gate simply refuses until the
overflow drains through kills -- nothing force-despawns to claw back under
(owner, 2026-09-18).

Dormant records **freeze**: no movement, no healing, no regrouping.

Knobs from the `population` section of `data/enemies/spawn_tables.json`.
"""
from __future__ import annotations

import pygame

__all__ = ["DormantEnemy", "Population"]

_KEYS = ("tick", "wake_budget", "scatter_after",
         "despawn_radius", "wake_radius", "dormant_cap")


class DormantEnemy:
    """What survives hibernation. Roughly 150 bytes; the world cap of 600
    is under 100 KB of these."""

    __slots__ = ("enemy_id", "room_id", "floor", "x", "y", "hp", "max_hp",
                 "shield_hp", "speed", "status", "elemental", "owner",
                 "spawned_at", "slept_at", "recycles")

    def __init__(self, enemy_id: str, x: float, y: float, hp: float, max_hp: float,
                 shield_hp: float, speed: float, status=None, owner: str = "direct",
                 spawned_at: float = 0.0, room_id: int = -1, floor: int = 0,
                 slept_at: float = 0.0, recycles: int = 0, elemental=None) -> None:
        self.enemy_id = enemy_id
        self.x, self.y = float(x), float(y)
        self.hp, self.max_hp = float(hp), float(max_hp)
        self.shield_hp, self.speed = float(shield_hp), float(speed)
        self.status = status
        # The aura and its lock survive a nap, as the statuses do: an enemy
        # that hibernates mid-burn wakes still burning.
        self.elemental = elemental
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
        # The ring. `wake_radius` must stay inside `despawn_radius` or a body
        # on the boundary flaps between the two states every tick.
        self.despawn_radius = float(knobs["despawn_radius"])
        self.wake_radius = float(knobs["wake_radius"])
        if self.wake_radius >= self.despawn_radius:
            raise ValueError(
                f"spawn_tables.json `population`: wake_radius "
                f"({self.wake_radius}) must be inside despawn_radius "
                f"({self.despawn_radius}), or bodies flap at the boundary")
        # A rail, not a target. Measured peaks in play are 20 standing
        # still, 22 patrolling and 1304 for a hero touring every island for
        # five minutes, so this should never fire; it exists so an unbounded
        # list cannot grow forever in a run nobody expected.
        self.dormant_cap = int(knobs["dormant_cap"])
        self.never_sleep = frozenset(never_sleep)
        self.dormant: dict[int, list[DormantEnemy]] = {}
        self.seeded: set[int] = set()          # islands that got their residents
        self._queue: list[DormantEnemy] = []   # waiting to wake, farthest first
        self._next_tick = 0.0
        self._next_wake_scan = 0.0
        self.slept = 0
        self.woken = 0
        self.ringed = 0          # slept by the ring rather than by the zone
        self.evicted = 0         # records dropped at `dormant_cap`

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
        """Sleep what the hero has left behind. Runs every `tick` seconds;
        returns `{room_id: count}` of what slept this call.

        Two rules, either of which fires: the **ring** (beyond
        `despawn_radius`, no exemption for a chaser or for the hero's own
        island) and the older **zone** rule (a whole island the hero left,
        with its pursuit timer lapsed).
        """
        if now < self._next_tick:
            return {}
        self._next_tick = now + self.tick
        ppos = host.player_pos()
        ring_sq = self.despawn_radius * self.despawn_radius
        slept: dict[int, int] = {}
        for e in list(host.live_enemies()):
            if not getattr(e, "alive", True):
                continue
            if host.owner_of(e) in self.never_sleep:
                continue
            room = host.room_at(e.pos)
            if room is None:
                continue                  # on a bridge: nowhere to file it
            beyond = ((e.pos.x - ppos.x) ** 2
                      + (e.pos.y - ppos.y) ** 2) > ring_sq
            if not beyond:
                # Inside the ring the old rule still decides, chase and all.
                if room.id in active or host.is_pursuing(e):
                    continue
            else:
                self.ringed += 1
            rec = host.sleep(e)
            rec.room_id = room.id
            rec.floor = host.floor_at(e.pos)
            rec.slept_at = now
            self.dormant.setdefault(room.id, []).append(rec)
            slept[room.id] = slept.get(room.id, 0) + 1
            self.slept += 1
        self._evict()
        return slept

    def _evict(self) -> int:
        """Drop the oldest-slept records once past `dormant_cap`.

        Oldest-slept rather than farthest or fewest, so the island the
        player abandoned longest ago is the one that forgets its
        population -- the one they are least likely to walk back into, and
        the one whose records are most stale anyway.

        Deliberately not clever: it rescans to find each victim, which is
        fine because it should never run. The cap sits several times above
        the worst behaviour measured in play.
        """
        dropped = 0
        while self.total_dormant > self.dormant_cap:
            oldest_room, oldest_i, oldest_at = None, -1, None
            for rid, recs in self.dormant.items():
                for i, rec in enumerate(recs):
                    if oldest_at is None or rec.slept_at < oldest_at:
                        oldest_room, oldest_i, oldest_at = rid, i, rec.slept_at
            if oldest_room is None:
                break                     # only the wake queue is left
            recs = self.dormant[oldest_room]
            recs.pop(oldest_i)
            if not recs:
                del self.dormant[oldest_room]
            dropped += 1
            self.evicted += 1
        return dropped

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

    def wake_nearby(self, host, now: float) -> int:
        """Queue every record the hero has come within `wake_radius` of.

        The ring's other half. `activate` only fires when an island *enters*
        the zone, which never happens for the island the hero is standing
        on, so without this a body the ring slept underfoot would stay a
        record for the rest of the run.

        Nearest first, because these are the ones about to come into view --
        the opposite of `activate`, which takes an island's far side first
        so the near ground is not crowded on arrival.
        """
        if now < self._next_wake_scan:
            return 0
        self._next_wake_scan = now + self.tick
        if not self.dormant:
            return 0
        ppos = host.player_pos()
        band_sq = self.wake_radius * self.wake_radius
        queued = 0
        for rid in list(self.dormant):
            near, far = [], []
            for rec in self.dormant[rid]:
                d = (rec.x - ppos.x) ** 2 + (rec.y - ppos.y) ** 2
                (near if d <= band_sq else far).append(rec)
            if not near:
                continue
            if far:
                self.dormant[rid] = far
            else:
                del self.dormant[rid]
            near.sort(key=lambda r: (r.x - ppos.x) ** 2 + (r.y - ppos.y) ** 2)
            self._queue.extend(near)
            queued += len(near)
        return queued

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
