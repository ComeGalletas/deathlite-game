"""Where a spawn request lands: a filtered, weighted pick over the spawn
points of the rooms in play, plus how a company packs around its leader.

Spawn master S3. The run used to try a dozen random cells of a nearby
island (the fallback now called `GameMap.spawn_point_near`); now it asks this for one of the
points generation already vetted (`world/gen/spawnpoints.py`).

`choose(request, host, now, debt_age)` filters the candidate points,
cheapest test first:

1. the point's island is in `request.room_weights` (the zone), and that
   weight is its base weight;
2. the point is not on cooldown -- each remembers when it was last used,
   so one pack does not stack on the next;
3. it is inside the distance band around the player -- at least
   `far_min_distance` away and no farther than `far_max_distance`. The
   camera is not consulted: where the view is, or how wide it is, never
   moves a spawn (owner, 2026-09-15);
4. its clearance class fits the request;
5. no live body stands within twice the request's radius of it;
6. a point on the player's floor is weighted up by `same_floor_weight`,
   unless the request prefers `"upper"`; a point carrying any preferred
   tag is weighted up by `prefer_weight`.

Then one weighted draw from the host's RNG.

**The relaxation ladder.** Rule 3 is not pass/fail: `choose` walks three
rungs and takes the first that offers anything.

    FAR        between `far_min_distance` and `far_max_distance` from the
               player -- the strict arrival
    NEAR       the ceiling is dropped; `near_min_distance` is the keep-away.
               A request whose debt has aged past `relax_after` starts here
    STARVED    `starved_min_distance` becomes the keep-away and
               `starved_cooldown` the point cooldown, and candidates are
               weighted by distance so the draw leans outward

The bottom rung exists because a player who stays on one island starves the
top one (owner, 2026-09-12): the zone is then a single island of a few dozen
points, and with the hero parked they are permanently either on cooldown or
inside the keep-away. Measured while camping, the strict rung was empty on
90 % of frames and roughly half of every pack the director emitted was
deferred. The owner's call is that spawns continue even when the camera can
see them.

The rungs used to be built from the camera's visible rect ("outside the
padded view", "outside the bare view"). They became distance bands on
2026-09-15 (S11) so that a wider render (21:9) does not push every spawn
further out: whether an arrival is on screen is now a consequence of the
band and the view, never a rule.

Rules 1, 4 and 5 hold at every rung -- the zone, the clearance class and a
body already standing on the point are physical, not aesthetic. `None` now
means no point in the zone is usable at all, and the master keeps such a
request as debt.

`pack(...)` seats a company around its leader. Concentric rings are the
skeleton -- the first clears the leader, each one after it is a body
diameter further out -- and every body is then nudged a random distance
inside its own cell, so the group reads as a crowd rather than as a target
painted on the ground. A candidate must be walkable *and* clear of every
body already seated. A follower that fits nowhere is dropped: a company
spawns short rather than stacked.

This replaced a single circle of radius leader + follower + gap (G0a,
2026-09-17). That circle only ever tested the terrain, never the bodies
already placed, so it capped near 24 seated and stacked badly above it --
twenty bodies on a 34 px circle have 214 px of arc to share and need 800.
Measured on a booted run, the packer seats forty small bodies inside 174 px
with zero overlaps at every anchor tried, and the jitter costs nothing in
fill.

Every number comes from the `placement` section of
`data/enemies/spawn_tables.json`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pygame

from spawn.points import PointIndex, SpawnPoint

__all__ = ["Placement", "SpawnRequest"]

_KEYS = ("cooldown", "far_min_distance", "far_max_distance", "near_min_distance",
         "relax_after", "same_floor_weight", "prefer_weight",
         "starved_min_distance", "starved_cooldown",
         "pack_gap", "pack_jitter", "pack_tries", "pack_spread", "pack_max_radius")

# Consecutive rings are twisted against each other so their slots do not line
# up into spokes. Geometry, not tuning -- the jitter is what makes a company
# look irregular, and that is a knob.
_RING_TWIST = 0.6

# The relaxation ladder, strictest first. `choose` walks it and takes the
# first rung that offers anything, so a request fails only when no point in
# the zone is physically usable at all.
FAR = 0            # `far_min_distance` .. `far_max_distance` from the player
NEAR = 1           # beyond `near_min_distance`; no ceiling
STARVED = 2        # beyond `starved_min_distance`; `starved_*` rules instead
_LADDER = (FAR, NEAR, STARVED)


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
        self.far_min_distance = float(knobs["far_min_distance"])
        self.far_max_distance = float(knobs["far_max_distance"])
        self.near_min_distance = float(knobs["near_min_distance"])
        self.relax_after = float(knobs["relax_after"])
        self.pack_gap = float(knobs["pack_gap"])
        self.pack_jitter = float(knobs["pack_jitter"])
        self.pack_tries = int(knobs["pack_tries"])
        self.pack_spread = float(knobs["pack_spread"])
        self.pack_max_radius = float(knobs["pack_max_radius"])
        self.same_floor_weight = float(knobs["same_floor_weight"])
        self.prefer_weight = float(knobs["prefer_weight"])
        self.starved_min_distance = float(knobs["starved_min_distance"])
        self.starved_cooldown = float(knobs["starved_cooldown"])
        self._used: dict[SpawnPoint, float] = {}

    # --- cooldown ------------------------------------------------------
    def mark_used(self, point: SpawnPoint, now: float) -> None:
        self._used[point] = now

    def on_cooldown(self, point: SpawnPoint, now: float, tier: int = FAR) -> bool:
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
        return NEAR if debt_age >= self.relax_after else FAR

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
        # The band this rung allows, squared. Only the strict rung has a
        # ceiling; the keep-away shrinks rung by rung. The camera is never
        # asked (owner, 2026-09-15).
        if tier >= STARVED:
            min_sq, max_sq = self.starved_min_distance ** 2, None
        elif tier >= NEAR:
            min_sq, max_sq = self.near_min_distance ** 2, None
        else:
            min_sq, max_sq = self.far_min_distance ** 2, self.far_max_distance ** 2
        need_large = request.clearance == "large"
        body = 2.0 * request.radius
        out: list[tuple[SpawnPoint, float]] = []
        for rid, base in request.room_weights.items():
            for p in self.index.by_room.get(rid, ()):
                if self.on_cooldown(p, now, tier):
                    continue
                dist_sq = (p.x - ppos.x) ** 2 + (p.y - ppos.y) ** 2
                if dist_sq < min_sq or (max_sq is not None and dist_sq > max_sq):
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
                    # This close, distance is the only thing left separating
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
        either on cooldown or inside the keep-away, so the strict rung is empty
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

    # --- seating a company ---------------------------------------------
    def pack(self, centre: pygame.Vector2, leader_radius: float,
             follower_radii: list[float], is_walkable, rng) -> list[pygame.Vector2 | None]:
        """One position per follower, in the order given, or `None` where
        nothing fits.

        The leader stands at `centre` and is seated already; the followers
        take ring slots outward from it in turn, each nudged inside its own
        cell if the nudge lands somewhere legal and dropped on the exact slot
        otherwise. Rings are spaced for the *largest* follower, so a heavy
        arriving late still fits any slot that is free -- the order the
        bodies come in does not decide who gets seated.

        The ring radius is bounded by the company: enough room for `n` bodies
        at `pack_spread`, never more than `pack_max_radius`, and always at
        least two rings so a blocked first choice can still be retried wider
        the way the old single circle did.
        """
        n = len(follower_radii)
        if n == 0:
            return []
        big = max(follower_radii)
        start = leader_radius + big + self.pack_gap      # the first ring clears the leader
        step = 2.0 * big + self.pack_gap                 # one body diameter per ring
        limit = min(self.pack_max_radius,
                    max(start + step,
                        start + step * self.pack_spread * math.sqrt(n)))
        slots = self._slots(centre, start, step, limit, rng.uniform(0.0, math.tau))
        taken: list[tuple[pygame.Vector2, float]] = [(pygame.Vector2(centre), leader_radius)]
        out: list[pygame.Vector2 | None] = [None] * n
        for i, fr in enumerate(follower_radii):
            for base in slots:
                spot = self._seat(base, fr, step, taken, is_walkable, rng)
                if spot is not None:
                    taken.append((spot, fr))
                    out[i] = spot
                    break
            else:
                break            # the rings ran out; nobody after this fits either
        return out

    @staticmethod
    def _slots(centre: pygame.Vector2, start: float, step: float, limit: float,
               phase: float):
        """Ring slots outward from the leader, nearest first."""
        rad, turn = start, 0
        while rad <= limit:
            count = max(1, int(math.tau * rad / step))
            off = phase + turn * _RING_TWIST
            for i in range(count):
                ang = off + (i / count) * math.tau
                yield pygame.Vector2(centre.x + math.cos(ang) * rad,
                                     centre.y + math.sin(ang) * rad)
            rad += step
            turn += 1

    def _seat(self, base: pygame.Vector2, radius: float, step: float,
              taken: list, is_walkable, rng) -> pygame.Vector2 | None:
        """`base` nudged inside its own cell, the exact slot as the fallback,
        or `None` if neither is legal."""
        reach = self.pack_jitter * step
        for _ in range(self.pack_tries if reach > 0.0 else 0):
            ang = rng.uniform(0.0, math.tau)
            d = rng.uniform(0.0, reach)
            cand = pygame.Vector2(base.x + math.cos(ang) * d, base.y + math.sin(ang) * d)
            if self._clear(cand, radius, taken, is_walkable):
                return cand
        return base if self._clear(base, radius, taken, is_walkable) else None

    @staticmethod
    def _clear(pos: pygame.Vector2, radius: float, taken: list, is_walkable) -> bool:
        # Bodies first: pure arithmetic, and the dense middle of a company is
        # where most candidates die. Terrain second -- it is the grid lookup.
        for q, qr in taken:
            reach = radius + qr
            if (pos.x - q.x) ** 2 + (pos.y - q.y) ** 2 < reach * reach:
                return False
        return is_walkable(pos, radius)
