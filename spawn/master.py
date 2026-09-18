"""`SpawnMaster`: the facade the run talks to.

Spawn master S3 / S4. Ties the budget director (`spawn/budget.py`, *how
many and which*) to placement (`spawn/placement.py`, *where*), the active
zone (`spawn/locality.py`, *which islands*) and the live / dormant
registry (`spawn/population.py`, *which enemies are simulated*), through
the `Host` protocol (`spawn/host.py`). It is the one place enemies are
brought into the run:

    update(dt)                    locality, hibernation, waking, debt, and
                                  the director's tick; a pack it emits is
                                  placed together on one point
    spawn_at(enemy_id, pos, owner)   one enemy, at `pos` or at a chosen point
    spawn_group(name, at, owner)  a template from the tables' `groups`
    set_modifier / clear_modifier named factors; `pressure` is the standing
                                  base (`pacing.base`) times the pacing
                                  value (`spawn/pacing.py`, read off the
                                  run's condition) times their product,
                                  and scales the director's cadence

**Zone.** The islands in play are the player's, the one they are heading
to (weight `heading_weight`) and the one just left (`grace_weight`).
`use_locality = False` (a test switch; the S4 config gate it replaced
came out in S7) falls back to the player's island and its tree
neighbours at weight 1, with nothing put to sleep. A world with no spawn points -- the one-room
test world, or the knob at 0 -- places through `host.fallback_point()`.

**Population.** When an island joins the zone its dormant records are
queued to wake a few per frame, and on its first visit it is seeded with
residents (`residents` in the tables, packs rolled off the director's
current phase, owner `resident`). Every `population.tick` seconds the
idle enemies outside the zone are put to sleep.

**Debt.** A pack the placement cannot seat this frame is queued, oldest
first, and retried every tick; past `relax_after` the view rule loosens
(`Placement`). The queue is capped so a stuck run does not bank a flood.

**The stagger (G0b).** A company the director emits materialises over
`company_stagger` seconds rather than appearing on one frame: the leader
lands at once and the followers are released oldest first, the last as the
window closes. Nothing about the company is decided during that window --
its point, its packed spots and the cap it pays are all settled when it is
seated, so it arrives at the same places whatever the knob says, and `0`
(the whole company on one frame) is a supported setting. The cap is
therefore charged once, by `_cap_room`, and a body still in flight counts
as live for every check made meanwhile, so a run cannot overshoot by the
size of the companies in the air. Only the director's companies stagger:
`spawn_at`, `spawn_group`, the residents and the dev menu have callers
that count what came back, and land whole. `drop_pending()` abandons a
company mid-arrival; a `frozen` run still finishes one it has paid for.

**Caps.** Two: the director's time-growing cap clamped to
`config.ENEMY_LIVE_CAP` bounds what is simulated, and
`config.ENEMY_COUNT_HARD_CAP` bounds live + dormant. Every entry point
checks both per body. The master owns the exception too: owners under
`owners.cap_exempt` (an arena's scripted elites) are always seated. The
hero's own summons (wolf, totem) are not enemies and never come here.

**Watchdog.** Every tick the watchdog (`spawn/watchdog.py`) is asked for
its verdicts and `recycle()` acts on them: the body is put to sleep with
its state, moved to a fresh point of its island (the nearest free one if
placement has nothing in the band), and woken; an owner in `never_sleep`
(an arena's elite, whose identity the arena tracks) is relocated as the
same object. A body recycled more than `max_recycles` times is dropped
and logged: that is a generation bug, not a gameplay event.

**Dev switches.** `all_active` puts every island in the zone (a stress
test); `frozen` stops the director, residents included, without stopping
the zone.
"""
from __future__ import annotations

import logging

from game import config
from spawn.locality import Locality
from spawn.placement import Placement, SpawnRequest
from spawn.points import PointIndex
from spawn.pacing import Pacing
from spawn.population import Population
from spawn.watchdog import Watchdog

__all__ = ["SpawnMaster", "ENEMY_SPAWNED", "ROOM_ACTIVATED", "ROOM_DORMANT", "ENEMY_RECYCLED"]

log = logging.getLogger(__name__)

ENEMY_SPAWNED = "enemy_spawned"
ROOM_ACTIVATED = "room_activated"
ROOM_DORMANT = "room_dormant"
ENEMY_RECYCLED = "enemy_recycled"
_MAX_DEBT = 20
_RESIDENT_KINDS = ("start", "boss", "combat", "village")


class SpawnMaster:
    def __init__(self, host, director, tables=None, index: PointIndex | None = None) -> None:
        self.host = host
        self.director = director
        self.tables = tables if tables is not None else director.tables
        self.index = index if index is not None else PointIndex(host.layout)
        self.placement = Placement(self.index, self.tables.placement)
        owners = self.tables.owners
        self._cap_exempt = frozenset(owners.get("cap_exempt", ()))
        self.locality = Locality(self.tables.locality)
        self.population = Population(self.tables.population, owners.get("never_sleep", ()))
        self.watchdog = Watchdog(self.tables.watchdog)
        self.pacing = Pacing(self.tables.pacing)
        # The two run signals pacing cannot see from here. Event names are
        # the bus's strings; the payloads are the run's (`amount`, and the
        # kill's `pos` / `xp` / ... which pacing ignores).
        host.subscribe("player_damaged", self._on_player_damaged)
        host.subscribe("enemy_killed", self._on_enemy_killed)
        self.use_locality = True
        self.all_active = False
        self.frozen = False
        if director.live_cap is None:
            director.live_cap = config.ENEMY_LIVE_CAP
        self.world_cap = int(config.ENEMY_COUNT_HARD_CAP)
        self._active: set[int] = set()
        self._small, self._large = self._class_radii()
        self._modifiers: dict[str, float] = {}
        # (queued_at, ids, owner, stagger)
        self._debt: list[tuple[float, list[str], str, bool]] = []
        # A company already committed, materialising body by body:
        # (due, enemy_id, x, y, owner, room_id). See `company_stagger`.
        self._pending: list[tuple[float, str, float, float, str, object]] = []
        self.company_stagger = float(self.tables.company_stagger)
        self.spawned = 0
        self.deferred = 0
        self.recycled = 0
        self.discarded = 0

    @staticmethod
    def _class_radii() -> tuple[float, float]:
        from world.nav.field import _NAV_CLASSES
        radii = sorted(float(c[3]) for c in _NAV_CLASSES)
        return radii[0], radii[-1]

    # --- modifiers ----------------------------------------------------
    def set_modifier(self, name: str, factor: float) -> None:
        self._modifiers[name] = max(0.0, float(factor))

    def clear_modifier(self, name: str) -> None:
        self._modifiers.pop(name, None)

    @property
    def modifiers(self) -> dict:
        return dict(self._modifiers)

    @property
    def modifier_product(self) -> float:
        p = 1.0
        for f in self._modifiers.values():
            p *= f
        return p

    @property
    def pressure(self) -> float:
        """The cadence multiplier: the standing base (`pacing.base`, 5), times
        the pacing value, times every modifier."""
        return self.pacing.base * self.pacing.value * self.modifier_product

    # --- pacing signals (S6) --------------------------------------------
    def _on_player_damaged(self, amount: float = 0.0, **_kw) -> None:
        max_hp = self.host.player_max_hp()
        self.pacing.on_damage(self.host.elapsed, (amount / max_hp) if max_hp > 0 else 0.0)

    def _on_enemy_killed(self, **_kw) -> None:
        self.pacing.on_kill(self.host.elapsed)

    # --- zone -----------------------------------------------------------
    def _locality_on(self) -> bool:
        return self.use_locality and bool(self.index.spawn)

    def zone(self) -> dict[int, float]:
        """Island id -> base weight of the rooms placement may use."""
        if self.all_active:
            return {rid: 1.0 for rid in self.index.rooms()}
        if self._locality_on():
            weights = self.locality.weights()
            return weights or {rid: 1.0 for rid in self.index.rooms()}
        room = self.host.room_at(self.host.player_pos())
        if room is None:
            return {rid: 1.0 for rid in self.index.rooms()}
        weights = {room.id: 1.0}
        for nb in getattr(room, "neighbors", ()):
            weights[nb] = 1.0
        return weights

    @property
    def active(self) -> set[int]:
        return set(self._active)

    @property
    def debt(self) -> int:
        return len(self._debt)

    @property
    def pending(self) -> int:
        """Bodies of a committed company that have not landed yet."""
        return len(self._pending)

    # --- the stagger ----------------------------------------------------
    def _release_pending(self, now: float) -> None:
        """Land the bodies of a committed company whose turn has come.

        Nothing is re-decided here. The spots were packed and the cap was
        paid when the company was seated, and a body still waiting counts as
        live for every check made since, so a staggered arrival can neither
        overshoot the cap nor land on top of something. Each entry is made
        exactly once and leaves the queue as it does.
        """
        if not self._pending:
            return
        due = [p for p in self._pending if p[0] <= now]
        if not due:
            return
        self._pending = [p for p in self._pending if p[0] > now]
        for _due, eid, x, y, owner, rid in due:
            self._make(eid, x, y, owner, rid)

    def drop_pending(self) -> int:
        """Forget a company still materialising without making the rest of
        it. Returns how many bodies were dropped."""
        n = len(self._pending)
        self._pending.clear()
        return n

    # --- per frame ------------------------------------------------------
    def update(self, dt: float) -> None:
        host = self.host
        now = host.elapsed
        # Before anything looks at the world, and before the `frozen` gate:
        # these bodies are already committed, so they finish arriving.
        self._release_pending(now)
        if self._locality_on():
            self._tick_zone(now)
            if self.population.waking:
                self.population.wake_some(host, self.index, self.placement, now)
        for v in self.watchdog.update(host, now):
            self.recycle(v.enemy, v.reason, v.poof)
        self.pacing.update(dt, now, host.player_hp_fraction(), host.live_count(),
                           self.director.enemy_count_cap(now))
        if self.frozen:
            return
        self._retry_debt(now)
        ids = self.director.update(dt * self.pressure, now, host.live_count())
        if ids:
            self._place_pack(ids, "director", now, stagger=True)

    def _tick_zone(self, now: float) -> None:
        host = self.host
        self.locality.update(host, now)
        active = set(self.index.rooms()) if self.all_active else self.locality.active()
        if active != self._active:
            new = active - self._active
            self._active = active
            for rid in sorted(new):
                woke = self.population.activate(rid, host)
                seeded = 0
                if rid not in self.population.seeded and not self.frozen:
                    self.population.seeded.add(rid)
                    seeded = self._seed_residents(rid, now)
                host.publish(ROOM_ACTIVATED, room=rid, woke=woke, seeded=seeded)
        for rid, n in self.population.hibernate(host, self._active, now).items():
            host.publish(ROOM_DORMANT, room=rid, slept=n)

    def _seed_residents(self, room_id: int, now: float) -> int:
        """An island's first population: `residents` packs off the director's
        current phase, seated on that island only (in the placement band
        around the hero). Returns how many enemies were made."""
        table = self.tables.residents
        if not table:
            return 0
        room = self.host.room(room_id)
        kind = room.kind if room.kind in _RESIDENT_KINDS else "special"
        spec = table.get(kind, 0)
        n = self.host.rng.randint(int(spec[0]), int(spec[1])) if isinstance(spec, list) else int(spec)
        scale = table.get("difficulty_scale", {}).get(self.host.difficulty, 1.0)
        n = int(round(n * float(scale)))
        made = 0
        for _ in range(n):
            ids = self.director.roll_pack(now)
            got = self._place_pack(ids, "resident", now, room_weights={room_id: 1.0},
                                   queue=False)
            made += len(got or ())
        return made

    # --- recycling (S5) -----------------------------------------------
    def recycle(self, enemy, reason: str, poof: bool = False) -> None:
        """Move a stuck or lost body to a fresh point of its island, keeping
        its state. Nothing is granted: no XP, no heal."""
        host = self.host
        now = host.elapsed
        where = enemy.pos.copy()
        room = host.room_at(where)
        room_weights = {room.id: 1.0} if room is not None else self.zone()
        point = self._choose([enemy.enemy_id], 0.0, room_weights=room_weights)
        radius = host.enemy_radius(enemy.enemy_id)
        # A vetted point is floor by construction; a hazard on it is not,
        # so ask once more before landing a body there.
        if point is not None and host.is_walkable(point.pos, radius):
            landing = (point.x, point.y)
        else:
            landing = self._nearest_free(enemy, room, now)
        owner = host.owner_of(enemy)
        if poof:
            host.poof(where)
        if owner in self.population.never_sleep:
            # The arena tracks its elites by identity: same object, new spot.
            if landing is not None:
                host.relocate(enemy, *landing)
        else:
            rec = host.sleep(enemy)
            rec.recycles += 1
            if rec.recycles > self.watchdog.max_recycles:
                self.discarded += 1
                log.warning("spawn master: %s at (%.0f, %.0f) recycled %d times "
                            "(%s), dropped -- likely a generation bug",
                            rec.enemy_id, where.x, where.y, rec.recycles - 1, reason)
                host.publish(ENEMY_RECYCLED, enemy_id=rec.enemy_id, reason="discarded")
                return
            rec.room_id = room.id if room is not None else -1
            rec.floor = host.floor_at(where)
            rec.slept_at = now
            if landing is None:
                self.population.dormant.setdefault(rec.room_id, []).append(rec)
            else:
                host.wake(rec, *landing)
        self.recycled += 1
        host.publish(ENEMY_RECYCLED, enemy_id=enemy.enemy_id, reason=reason)

    def _nearest_free(self, enemy, room, now: float):
        """A free point of the island nearest the body, when placement has
        none in the band to offer; `None` when there is none at all."""
        if room is None:
            return None
        points = self.index.by_room.get(room.id, [])
        radius = self.host.enemy_radius(enemy.enemy_id)
        free = self.population._free(points, self.host, radius, now, self.placement)
        if not free:
            return None
        p = min(free, key=lambda q: (q.x - enemy.pos.x) ** 2 + (q.y - enemy.pos.y) ** 2)
        return (p.x, p.y)

    def _retry_debt(self, now: float) -> None:
        if not self._debt:
            return
        # Retries never re-queue themselves (`queue=False`); what still
        # cannot be seated goes back in its old place, so the list holds
        # each pack once and the oldest keeps its age.
        waiting, self._debt = self._debt, []
        for queued_at, ids, owner, stagger in waiting:
            if self._place_pack(ids, owner, queued_at, queue=False,
                                stagger=stagger) is None:
                self._debt.append((queued_at, ids, owner, stagger))

    # --- entry points ---------------------------------------------------
    def spawn_at(self, enemy_id: str, pos=None, owner: str = "direct"):
        """One enemy at `pos`, or at a chosen point when `pos` is None.
        Returns the enemy, or None when the cap or the placement refused."""
        if not self._under_cap(owner):
            return None
        if pos is None:
            point = self._choose([enemy_id], 0.0)
            if point is None:
                fb = self.host.fallback_point()
                if fb is None:
                    return None
                return self._make(enemy_id, fb.x, fb.y, owner, None)
            return self._make(enemy_id, point.x, point.y, owner, point.room_id)
        return self._make(enemy_id, pos.x, pos.y, owner, None)

    def spawn_group(self, name: str, at=None, owner: str = "group") -> list:
        """A template from the tables: the leader plus each follower kind
        rolled in its span, placed together."""
        g = self.tables.group(name)
        ids = [g["leader"]]
        for eid, (lo, hi) in g.get("followers", {}).items():
            ids.extend([eid] * self.host.rng.randint(lo, hi))
        prefer = tuple(g.get("prefer", ()))
        clearance = g.get("clearance")
        return self._place_pack(ids, owner, self.host.elapsed, at=at,
                                prefer=prefer, clearance=clearance, queue=False) or []

    # --- placing a pack -------------------------------------------------
    def _place_pack(self, ids: list, owner: str, queued_at: float, at=None,
                    prefer: tuple = (), clearance: str | None = None, queue: bool = True,
                    room_weights: dict | None = None, stagger: bool = False):
        """Seat `ids` together: the leader on a point (or `at`), the rest
        packed around it. Returns the enemies made, or None when nothing
        could be seated (queued as debt when `queue`).

        `stagger` lets the company materialise over `company_stagger`
        seconds instead of landing on one frame. Everything that decides the
        company still happens here and now -- the point, the packed spots,
        the cap -- so the only difference is when each body appears. The
        return value is therefore what has landed *so far*, the leader; the
        rest is counted by `pending`.
        """
        host = self.host
        now = host.elapsed
        if not ids or not self._under_cap(owner):
            return None
        leader = ids[0]
        if at is not None:
            cx, cy, rid = at.x, at.y, None
        else:
            point = self._choose(ids, now - queued_at, prefer, clearance, room_weights)
            if point is None:
                fb = host.fallback_point() if not self.index.spawn else None
                if fb is None:
                    if queue and len(self._debt) < _MAX_DEBT:
                        self._debt.append((queued_at, list(ids), owner, stagger))
                        self.deferred += 1
                    return None
                cx, cy, rid = fb.x, fb.y, None
            else:
                cx, cy, rid = point.x, point.y, point.room_id
        made = [self._make(leader, cx, cy, owner, rid)]
        followers = ids[1:]
        if followers:
            centre = made[0].pos
            radii = [host.enemy_radius(e) for e in followers]
            spots = self.placement.pack(centre, host.enemy_radius(leader), radii,
                                        host.is_walkable, host.rng)
            seats = [(eid, s) for eid, s in zip(followers, spots) if s is not None]
            # The cap is settled once, here, for the whole company: what does
            # not fit is dropped now rather than discovered halfway through
            # an arrival, so a company lands the same way whether it is
            # staggered or not.
            room = self._cap_room(owner)
            if room is not None:
                seats = seats[:room]
            wait = self.company_stagger if stagger else 0.0
            if wait > 0.0 and seats:
                # Oldest first, the last body landing as the window closes.
                step = wait / len(seats)
                for i, (eid, spot) in enumerate(seats):
                    self._pending.append((now + (i + 1) * step, eid,
                                          spot.x, spot.y, owner, rid))
            else:
                made.extend(self._make(eid, spot.x, spot.y, owner, rid)
                            for eid, spot in seats)
        return made

    def _choose(self, ids: list, debt_age: float, prefer: tuple = (),
                clearance: str | None = None, room_weights: dict | None = None):
        if not self.index.spawn:
            return None
        radius = max(self.host.enemy_radius(e) for e in ids)
        if clearance is None:
            clearance = "large" if radius > self._small else "small"
        req = SpawnRequest(radius=radius, clearance=clearance,
                           room_weights=room_weights if room_weights is not None else self.zone(),
                           prefer=prefer, player_floor=self.host.player_floor())
        return self.placement.choose(req, self.host, self.host.elapsed, debt_age)

    def _cap_room(self, owner: str) -> int | None:
        """How many more bodies this owner may seat, or `None` when it is
        exempt. A body committed but not yet landed counts as live, so a
        company still materialising cannot be double-spent."""
        if owner in self._cap_exempt:
            return None
        live = self.host.live_count() + len(self._pending)
        return max(0, min(self.director.enemy_count_cap(self.host.elapsed) - live,
                          self.world_cap - live - self.population.total_dormant))

    def _under_cap(self, owner: str) -> bool:
        room = self._cap_room(owner)
        return room is None or room > 0

    def _make(self, enemy_id: str, x: float, y: float, owner: str, room_id):
        hp_mult, spd_mult = self.director.stat_multipliers(self.host.elapsed)
        enemy = self.host.make_enemy(enemy_id, x, y, hp_mult, spd_mult, owner)
        self.spawned += 1
        self.pacing.on_spawn(self.host.elapsed)
        self.host.publish(ENEMY_SPAWNED, enemy_id=enemy_id, owner=owner, room=room_id)
        return enemy
