"""Where a spawn request lands: a filtered, weighted pick over the spawn
points of the rooms in play, plus the ring a pack's followers stand on.

Spawn master S3. The run used to try a dozen random cells of a nearby
island (`GameMap.offscreen_spawn_point`); now it asks this for one of the
points generation already vetted (`world/gen/spawnpoints.py`).

`choose(request, host, now, debt_age)` filters the candidate points,
cheapest test first:

1. the point's island is in `request.room_weights` (the zone), and that
   weight is its base weight;
2. the point is not on cooldown -- each remembers when it was last used,
   so one pack does not stack on the next;
3. it is outside the view inflated by `view_pad`, and farther than
   `min_distance` from the player (the two rules the old helper kept);
4. its clearance class fits the request;
5. no live body stands within twice the request's radius of it;
6. a point on the player's floor is weighted up by `same_floor_weight`,
   unless the request prefers `"upper"`; a point carrying any preferred
   tag is weighted up by `prefer_weight`.

Then one weighted draw from the host's RNG. Nothing surviving returns
`None` and the master keeps the request as debt; once `debt_age` passes
`relax_after`, rule 3 loosens to "outside the view" only.

`ring(...)` places followers around a leader: evenly spaced on a circle of
radius leader + follower + `ring_gap`, at a random phase, each checked for
floor and retried once on a wider circle. A follower that fits nowhere is
dropped -- a pack spawns short rather than stacked.

Every number comes from the `placement` section of
`data/spawn_tables.json`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pygame

from spawn.points import PointIndex, SpawnPoint

__all__ = ["Placement", "SpawnRequest"]

_KEYS = ("cooldown", "view_pad", "min_distance", "relax_after", "ring_gap",
         "same_floor_weight", "prefer_weight")


@dataclass
class SpawnRequest:
    radius: float                        # the leader's body radius
    clearance: str = "small"             # "small" | "large": the class it needs
    room_weights: dict = field(default_factory=dict)   # island id -> base weight
    prefer: tuple = ()                   # tags that weight a point up
    player_floor: int | None = None


class Placement:
    def __init__(self, index: PointIndex, knobs: dict) -> None:
        missing = [k for k in _KEYS if k not in knobs]
        if missing:
            raise KeyError(f"spawn_tables.json `placement` lacks {missing}")
        self.index = index
        self.cooldown = float(knobs["cooldown"])
        self.view_pad = float(knobs["view_pad"])
        self.min_distance = float(knobs["min_distance"])
        self.relax_after = float(knobs["relax_after"])
        self.ring_gap = float(knobs["ring_gap"])
        self.same_floor_weight = float(knobs["same_floor_weight"])
        self.prefer_weight = float(knobs["prefer_weight"])
        self._used: dict[SpawnPoint, float] = {}

    # --- cooldown ------------------------------------------------------
    def mark_used(self, point: SpawnPoint, now: float) -> None:
        self._used[point] = now

    def on_cooldown(self, point: SpawnPoint, now: float) -> bool:
        last = self._used.get(point)
        return last is not None and now - last < self.cooldown

    # --- the pick ------------------------------------------------------
    def candidates(self, request: SpawnRequest, host, now: float,
                   debt_age: float = 0.0) -> list[tuple[SpawnPoint, float]]:
        """The points that pass, each with its weight. Exposed for the
        tests and the overlay; `choose` draws from it."""
        relaxed = debt_age >= self.relax_after
        view = host.visible_rect()
        if not relaxed:
            view = view.inflate(2 * self.view_pad, 2 * self.view_pad)
        ppos = host.player_pos()
        min_sq = 0.0 if relaxed else self.min_distance ** 2
        need_large = request.clearance == "large"
        body = 2.0 * request.radius
        out: list[tuple[SpawnPoint, float]] = []
        for rid, base in request.room_weights.items():
            for p in self.index.by_room.get(rid, ()):
                if self.on_cooldown(p, now):
                    continue
                if view.collidepoint(p.x, p.y):
                    continue
                if (p.x - ppos.x) ** 2 + (p.y - ppos.y) ** 2 < min_sq:
                    continue
                if need_large and p.clearance != "large":
                    continue
                if any((p.x - e.pos.x) ** 2 + (p.y - e.pos.y) ** 2 < body * body
                       for e in host.neighbors_near(p.pos, body)
                       if getattr(e, "alive", True)):
                    continue
                w = float(base)
                if (request.player_floor is not None and p.floor == request.player_floor
                        and "upper" not in request.prefer):
                    w *= self.same_floor_weight
                if request.prefer and any(t in p.tags for t in request.prefer):
                    w *= self.prefer_weight
                if w > 0.0:
                    out.append((p, w))
        return out

    def choose(self, request: SpawnRequest, host, now: float,
               debt_age: float = 0.0) -> SpawnPoint | None:
        cands = self.candidates(request, host, now, debt_age)
        if not cands:
            return None
        points = [p for p, _w in cands]
        weights = [w for _p, w in cands]
        point = host.rng.choices(points, weights=weights, k=1)[0]
        self.mark_used(point, now)
        return point

    # --- followers ----------------------------------------------------
    def ring(self, centre: pygame.Vector2, leader_radius: float,
             follower_radii: list[float], is_walkable, rng) -> list[pygame.Vector2 | None]:
        """One position per follower (or `None` where nothing fits), on a
        circle round the leader."""
        n = len(follower_radii)
        if n == 0:
            return []
        phase = rng.uniform(0.0, math.tau)
        out: list = []
        for i, fr in enumerate(follower_radii):
            ang = phase + i * math.tau / n
            d = pygame.Vector2(math.cos(ang), math.sin(ang))
            placed = None
            for scale in (1.0, 1.6):
                pos = centre + d * (leader_radius + fr + self.ring_gap) * scale
                if is_walkable(pos, fr):
                    placed = pos
                    break
            out.append(placed)
        return out
