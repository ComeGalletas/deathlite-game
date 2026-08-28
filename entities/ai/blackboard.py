"""Per-actor, per-component scratch state.

Replaces the untyped `enemy.ai` dict: a component only ever touches
`actor.bb.slot(self.key)`, and `Behavior` hands every component a stable unique
key, so two components can never clash on a name.
"""
from __future__ import annotations


class Blackboard:
    __slots__ = ("_slots",)

    def __init__(self) -> None:
        self._slots: dict[str, dict] = {}

    def slot(self, key: str) -> dict:
        """The private dict for `key`, created empty on first access."""
        s = self._slots.get(key)
        if s is None:
            s = self._slots[key] = {}
        return s

    def clear(self) -> None:
        self._slots.clear()

    def __contains__(self, key: str) -> bool:
        return key in self._slots
