"""Which islands are in play: the one the player is on, the one they are
heading to, and the one they just left.

Spawn master S4. Everything else in the package asks this one question --
`is_active(room_id)` -- and the placement weights come from `weights()`.

**Current** is the island whose floor the player stands on, re-read only
when they leave it. On a bridge there is no island under the player:
current stays what it was and the bridge's *other* end becomes the
heading, no guessing.

**Heading** is the neighbour of the current island best aligned with the
player's movement (the dot product of the unit vector to the neighbour's
centre with the unit move direction), accepted only when the alignment
clears `align` and the same neighbour has been the best for `dwell`
seconds running. Standing still or circling makes the candidate `None`,
and after the dwell the heading clears too. The dwell is the hysteresis
that stops an island flapping in and out of the zone as the player
strafes.

**Grace** is the island the player most recently left, kept in play for
`grace` seconds so pursuers crossing the bridge behind them are not put
to sleep mid-chase.

Knobs from the `locality` section of `data/spawn_tables.json`.
"""
from __future__ import annotations

__all__ = ["Locality"]

_KEYS = ("dwell", "grace", "align", "heading_weight", "grace_weight")


class Locality:
    def __init__(self, knobs: dict) -> None:
        missing = [k for k in _KEYS if k not in knobs]
        if missing:
            raise KeyError(f"spawn_tables.json `locality` lacks {missing}")
        self.dwell = float(knobs["dwell"])
        self.grace = float(knobs["grace"])
        self.align = float(knobs["align"])
        self.heading_weight = float(knobs["heading_weight"])
        self.grace_weight = float(knobs["grace_weight"])
        self.current: int | None = None
        self.heading: int | None = None
        self.grace_room: int | None = None
        self._grace_until = 0.0
        self._candidate: int | None = None
        self._candidate_since = 0.0

    # --- queries ----------------------------------------------------------
    def active(self) -> set[int]:
        return {r for r in (self.current, self.heading, self.grace_room) if r is not None}

    def is_active(self, room_id: int) -> bool:
        return room_id in self.active()

    def weights(self) -> dict[int, float]:
        """Island id -> placement weight. Empty when the player is on no
        island yet (no layout, or off every floor)."""
        out: dict[int, float] = {}
        if self.grace_room is not None:
            out[self.grace_room] = self.grace_weight
        if self.heading is not None:
            out[self.heading] = self.heading_weight
        if self.current is not None:
            out[self.current] = 1.0
        return out

    # --- per frame ------------------------------------------------------
    def update(self, host, now: float) -> bool:
        """Re-read the player's position and movement. Returns whether the
        active set changed."""
        before = self.active()
        pos = host.player_pos()
        room = host.room_at(pos)
        if room is None:
            bridge = host.corridor_at(pos)
            if bridge is not None and self.current in bridge:
                other = bridge[1] if bridge[0] == self.current else bridge[0]
                self.heading = other
                self._candidate, self._candidate_since = other, now
        else:
            if room.id != self.current:
                if self.current is not None:
                    self.grace_room = self.current
                    self._grace_until = now + self.grace
                self.current = room.id
                self.heading = None
                self._candidate, self._candidate_since = None, now
            self._track_heading(host, pos, now)
        if self.grace_room is not None and (
                now >= self._grace_until or self.grace_room in (self.current, self.heading)):
            self.grace_room = None
        return self.active() != before

    def _track_heading(self, host, pos, now: float) -> None:
        best, best_score = None, self.align
        move = host.player_heading()
        if move.length_squared() > 1e-6:
            move = move.normalize()
            for nb in host.room(self.current).neighbors:
                d = host.room(nb).center - pos
                if d.length_squared() < 1e-6:
                    continue
                score = d.normalize().dot(move)
                if score >= best_score:
                    best, best_score = nb, score
        if best != self._candidate:
            self._candidate, self._candidate_since = best, now
        elif now - self._candidate_since >= self.dwell and self.heading != best:
            self.heading = best
