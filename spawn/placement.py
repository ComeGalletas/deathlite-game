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

Then one weighted draw from the host's RNG.

**The relaxation ladder.** Rule 3 is not pass/fail: `choose` walks three
rungs and takes the first that offers anything.

    OFFSCREEN  outside the view inflated by `view_pad`, and beyond
               `min_distance` from the player -- the strict arrival
    NEAR       outside the bare view; the keep-away is dropped. A request
               whose debt has aged past `relax_after` starts here
    STARVED    the view is no longer a wall. `starved_min_distance` becomes
               the keep-away and `starved_cooldown` the point cooldown, and
               candidates are weighted by distance so the draw leans to the
               far edge of the screen

The bottom rung exists because a player who stays on one island starves the
top one (owner, 2026-09-12): the zone is then a single island of a few dozen
points, and with the hero parked they are permanently either on cooldown or
inside the view. Measured while camping, the strict rung was empty on 90 % of
frames and roughly half of every pack the director emitted was deferred. The
owner's call is that spawns continue even when the camera can see them.

Rules 1, 4 and 5 hold at every rung -- the zone, the clearance class and a
body already standing on the point are physical, not aesthetic. `None` now
means no point in the zone is usable at all, and the master keeps such a
request as debt.

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
         "same_floor_weight", "prefer_weight", "starved_min_distance",
         "starved_cooldown")

# The relaxation ladder, strictest first. `choose` walks it and takes the
# first rung that offers anything, so a request fails only when no point in
# the zone is physically usable at all.
OFFSCREEN = 0      # outside the padded view, beyond `min_distance`
NEAR = 1           # outside the bare view; the keep-away is dropped
STARVED = 2        # the view is not a wall; `starved_*` rules instead
_LADDER = (OFFSCREEN, NEAR, STARVED)


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
        self.starved_min_distance = float(knobs["starved_min_distance"])
        self.starved_cooldown = float(knobs["starved_cooldown"])
        self._used: dict[SpawnPoint, float] = {}

    # --- cooldown ------------------------------------------------------
    def mark_used(self, point: SpawnPoint, now: float) -> None:
        self._used[point] = now

    def on_cooldown(self, point: SpawnPoint, now: float, tier: int = OFFSCREEN) -> bool:
        last = self._used.get(point)
        if last is None:
            return False
        wait = self.starved_cooldown if tier >= STARVED else self.cooldown
        return now - last < wait

    # --- the pick ------------------------------------------------------
    def first_tier(self, debt_age: float) -> int:
        """The strictest rung this request is entitled to. A request whose
        debt has aged past `relax_after` has already waited, so it skips the
        keep-away rung rather than paying for it twice."""
        return NEAR if debt_age >= self.relax_after else OFFSCREEN

    def candidates(self, request: SpawnRequest, host, now: float,
                   debt_age: float = 0.0,
                   tier: int | None = None) -> list[tuple[SpawnPoint, float]]:
        """The points that pass at `tier`, each with its weight. Exposed for
        the tests and the overlay; `choose` walks the ladder over it.

        `tier` defaults to the rung `debt_age` earns, so a caller that knows
        nothing about the ladder gets exactly what it used to.
        """
        if tier is None:
            tier = self.first_tier(debt_age)
        ppos = host.player_pos()
        if tier >= STARVED:
            # The view stops being a wall here; a plain keep-away radius
            # takes its place, so an enemy arrives at the edge of the screen
            # rather than on top of the hero.
            view = None
            min_sq = self.starved_min_distance ** 2
        else:
            view = host.visible_rect()
            if tier <= OFFSCREEN:
                view = view.inflate(2 * self.view_pad, 2 * self.view_pad)
                min_sq = self.min_distance ** 2
            else:
                min_sq = 0.0
        need_large = request.clearance == "large"
        body = 2.0 * request.radius
        out: list[tuple[SpawnPoint, float]] = []
        for rid, base in request.room_weights.items():
            for p in self.index.by_room.get(rid, ()):
                if self.on_cooldown(p, now, tier):
                    continue
                if view is not None and view.collidepoint(p.x, p.y):
                    continue
                dist_sq = (p.x - ppos.x) ** 2 + (p.y - ppos.y) ** 2
                if dist_sq < min_sq:
                    continue
                if need_large and p.clearance != "large":
                    continue
                # Never relaxed, at any rung: these two are physical rather
                # than aesthetic. A body cannot share a point, and a large
                # enemy cannot stand on a small one.
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
                if tier >= STARVED and self.starved_min_distance > 0.0:
                    # On screen, distance is the only thing left separating
                    # a fair arrival from a body appearing next to the hero,
                    # so it is what the draw is biased by.
                    w *= math.sqrt(dist_sq) / self.starved_min_distance
                if w > 0.0:
                    out.append((p, w))
        return out

    def choose(self, request: SpawnRequest, host, now: float,
               debt_age: float = 0.0) -> SpawnPoint | None:
        """The first rung of the ladder that offers anything.

        Walking down instead of giving up is what keeps a camping player
        under pressure (owner, 2026-09-12): on one island the zone holds only
        a few dozen points, and with the hero parked they are permanently
        either on cooldown or inside the view, so the strict rung is empty
        almost every frame and every pack used to become debt. `None` now
        means no point in the zone is usable at all -- occupied, of the wrong
        clearance, or too close to the hero to be a fair arrival."""
        for tier in _LADDER[self.first_tier(debt_age):]:
            cands = self.candidates(request, host, now, debt_age, tier=tier)
            if not cands:
                continue
            points = [p for p, _w in cands]
            weights = [w for _p, w in cands]
            point = host.rng.choices(points, weights=weights, k=1)[0]
            self.mark_used(point, now)
            return point
        return None

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
