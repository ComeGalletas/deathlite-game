"""Name -> Behavior.

A behaviour name (`enemies.json` / `bosses.json` `behavior`) resolves in two
places, in order (ENT-017):

1. **A template** in `data/enemies/behaviors.json`. Its numbers merge shared
   defaults -> the template's -> the enemy's block, and its `shape` builds
   the machine: a generic shape in `entities/ai/templates.py`, or a
   code-built one registered here.
2. **A code-built behaviour** registered with `@behavior(name)`, a builder
   `fn(cfg) -> Behavior` (the bespoke shapes in `entities/ai/behaviors/*`,
   and tests' own demo behaviours). It still gets the shared defaults.

Behaviour modules register on import; the game imports them once at start-up.
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
    from entities.ai import templates
    tpl = templates.template(name)
    if tpl is None and name not in _BUILDERS:
        raise KeyError(f"unknown ai behavior {name!r}; "
                       f"registered: {registered()}")
    merged = templates.merged(tpl, cfg or {})
    if tpl is None:
        built = _BUILDERS[name](merged)
    else:
        shape = tpl["shape"]
        if shape in templates.SHAPES:
            built = templates.SHAPES[shape](tpl, merged)
        elif shape in _BUILDERS:
            built = _BUILDERS[shape](merged)
        else:
            raise KeyError(f"behavior {name!r}: unknown shape {shape!r}")
    # LD-9 D7: every behaviour is gated behind the aggro check from one place
    # rather than in twelve builders. A type with no `aggro_range` /
    # `pursuit_seconds` in its JSON block comes back untouched.
    from entities.ai.components.aggro import with_aggro
    return with_aggro(built, merged)


def code_shapes() -> list[str]:
    """The code-built behaviours and shapes (`@behavior`)."""
    return sorted(_BUILDERS)


def registered() -> list[str]:
    """Every name `build_behavior` resolves: the templates and the code-built
    behaviours."""
    from entities.ai import templates
    return sorted(set(_BUILDERS) | set(templates.names()))
