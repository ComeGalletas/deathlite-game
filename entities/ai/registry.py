"""Name -> Behavior builder.

`@behavior("kite_shoot")` registers a builder `fn(cfg) -> Behavior`, where `cfg`
is the enemy's `data/enemies.json` block. `build_behavior(name, cfg)` resolves
it. Behaviour modules (`entities/ai/behaviors/*`) register on import; the game
imports them once at start-up.
"""
from __future__ import annotations

from typing import Callable

from entities.ai.machine import Behavior

_BUILDERS: dict[str, Callable[[dict], Behavior]] = {}


def behavior(name: str):
    def deco(fn: Callable[[dict], Behavior]) -> Callable[[dict], Behavior]:
        if name in _BUILDERS:
            raise ValueError(f"ai behavior {name!r} already registered")
        _BUILDERS[name] = fn
        return fn
    return deco


def build_behavior(name: str, cfg: dict | None = None) -> Behavior:
    try:
        builder = _BUILDERS[name]
    except KeyError:
        raise KeyError(f"unknown ai behavior {name!r}; "
                       f"registered: {sorted(_BUILDERS)}") from None
    return builder(cfg or {})


def registered() -> list[str]:
    return sorted(_BUILDERS)
