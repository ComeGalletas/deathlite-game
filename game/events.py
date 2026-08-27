"""A tiny synchronous event bus (Observer pattern, spec section 11).

Systems publish named events; other systems subscribe with a callback. This
keeps combat / progression / UI decoupled: the weapon system does not need a
reference to the HUD to announce "enemy_killed".

Deliberately minimal:
  * synchronous dispatch (no queue) -- ordering is predictable and debuggable
  * exceptions in a handler are logged, not swallowed, and do not stop the
    other handlers for that event
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger(__name__)

Handler = Callable[..., None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._subscribers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: Handler) -> None:
        if handler in self._subscribers.get(event_name, []):
            self._subscribers[event_name].remove(handler)

    def clear(self) -> None:
        """Drop all subscriptions -- called when a run ends so stale closures
        from the previous run do not fire into the next one."""
        self._subscribers.clear()

    def publish(self, event_name: str, **payload: Any) -> None:
        for handler in list(self._subscribers.get(event_name, ())):
            try:
                handler(**payload)
            except Exception:  # noqa: BLE001 -- log with context, keep going
                log.exception(
                    "event handler %r failed for event %r (payload=%r)",
                    getattr(handler, "__qualname__", handler),
                    event_name,
                    payload,
                )


# Known event names, centralised so typos surface as attribute errors.
class Events:
    ENEMY_KILLED = "enemy_killed"
    PLAYER_DAMAGED = "player_damaged"
    PLAYER_LEVELED = "player_leveled"
    XP_COLLECTED = "xp_collected"
    ITEM_COLLECTED = "item_collected"
    BOSS_SPAWNED = "boss_spawned"
    BOSS_KILLED = "boss_killed"
    RUN_ENDED = "run_ended"
    DAMAGE_DEALT = "damage_dealt"
