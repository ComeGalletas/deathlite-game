"""The watchdog: enemies that are stuck or off the floor get recycled.

Spawn master S5. Independent of the AI's `Unstick` steering nudge, which
stays: that one frees a body wedged against a corner; this one catches
what the nudge cannot -- a body embedded in a cliff after a knockback, one
lost off the world, one that has made no headway for seconds while
trying to.

Every live enemy is sampled once per `sample_interval`, staggered by its
identity so a hundred bodies spread over a second rather than all landing
on one frame. Two verdicts:

**Off floor** -- the spot under the body is not floor (`host.is_walkable`
at its radius) and not a bridge, or no island and no bridge holds it at
all (off the world). Recycled at once.

**Stuck** -- the body is in pursuit (`host.is_pursuing`) and wants to
move (`host.wants_to_move`), is not in an attack (`host.is_attacking`),
stands farther than contact range from the player, and its last `window`
samples all lie within its own radius of the first. Recycled. An idle
wanderer is never stuck: it pauses for seconds at a time on purpose.

A verdict on a body the player can see is **held** until it leaves the
view or `on_screen_wait` passes, and then carries a poof so the vanish
reads as intentional. `update()` returns the recycles due this frame; the
master does the moving (`SpawnMaster.recycle`), since only it knows the
points, the caps and the owners.

Knobs from the `watchdog` section of `data/spawn_tables.json`.
"""
from __future__ import annotations

import pygame

__all__ = ["Watchdog", "Verdict"]

_KEYS = ("sample_interval", "window", "on_screen_wait", "max_recycles", "contact_margin")


class Verdict:
    __slots__ = ("enemy", "reason", "poof")

    def __init__(self, enemy, reason: str, poof: bool) -> None:
        self.enemy, self.reason, self.poof = enemy, reason, poof

    def __repr__(self) -> str:
        return f"Verdict({self.reason}, poof={self.poof})"


class _Track:
    __slots__ = ("next_sample", "samples", "held_since")

    def __init__(self, next_sample: float) -> None:
        self.next_sample = next_sample
        self.samples: list[pygame.Vector2] = []
        self.held_since: float | None = None


class Watchdog:
    def __init__(self, knobs: dict) -> None:
        missing = [k for k in _KEYS if k not in knobs]
        if missing:
            raise KeyError(f"spawn_tables.json `watchdog` lacks {missing}")
        self.sample_interval = float(knobs["sample_interval"])
        self.window = int(knobs["window"])
        self.on_screen_wait = float(knobs["on_screen_wait"])
        self.max_recycles = int(knobs["max_recycles"])
        self.contact_margin = float(knobs["contact_margin"])
        self._tracks: dict[int, _Track] = {}
        self.flagged = 0

    def _stagger(self, enemy) -> float:
        return (id(enemy) // 16 % 1000) / 1000.0 * self.sample_interval

    def update(self, host, now: float) -> list[Verdict]:
        live = host.live_enemies()
        alive_ids = {id(e) for e in live}
        for key in [k for k in self._tracks if k not in alive_ids]:
            del self._tracks[key]
        out: list[Verdict] = []
        view = None
        for e in live:
            if not getattr(e, "alive", True):
                continue
            tr = self._tracks.get(id(e))
            if tr is None:
                tr = self._tracks[id(e)] = _Track(now + self._stagger(e))
            if now < tr.next_sample:
                continue
            tr.next_sample = now + self.sample_interval
            reason = self._judge(e, tr, host)
            if reason is None:
                tr.held_since = None
                continue
            if view is None:
                view = host.visible_rect()
            poof = False
            if view.collidepoint(e.pos.x, e.pos.y):
                if tr.held_since is None:
                    tr.held_since = now
                    self.flagged += 1
                if now - tr.held_since < self.on_screen_wait:
                    continue
                poof = True
            elif tr.held_since is None:
                self.flagged += 1
            tr.samples.clear()
            tr.held_since = None
            out.append(Verdict(e, reason, poof))
        return out

    def _judge(self, e, tr: _Track, host) -> str | None:
        on_bridge = host.corridor_at(e.pos) is not None
        if not on_bridge and host.room_at(e.pos) is None:
            return "off_world"
        if not on_bridge and not host.is_walkable(e.pos, e.radius):
            return "off_floor"
        tr.samples.append(pygame.Vector2(e.pos))
        if len(tr.samples) > self.window:
            del tr.samples[0]
        if len(tr.samples) < self.window:
            return None
        # Only a chase can be stuck: an idle wanderer pauses for seconds at
        # a time on purpose and would read as stuck under the spread test.
        if not host.is_pursuing(e) or not host.wants_to_move(e) or host.is_attacking(e):
            return None
        reach = e.radius + host.player_radius() + self.contact_margin
        if (e.pos - host.player_pos()).length_squared() <= reach * reach:
            return None
        first = tr.samples[0]
        spread_sq = max((s - first).length_squared() for s in tr.samples)
        if spread_sq < e.radius * e.radius:
            return "stuck"
        return None
