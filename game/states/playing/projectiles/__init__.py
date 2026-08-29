"""Per-family projectile rendering.

Each visual family registers a draw function with `@style("name")`; `classify()`
maps a live `Projectile` to a family from the fields it already carries, and
`draw_projectile()` dispatches. `WorldRenderer.player_projectiles` /
`hostile_projectiles` are thin loops over this — adding an animated projectile
type is a new small module here, not another branch in `rendering.py`.

Style fn signature: `fn(surface, sx, sy, proj, ctx)` where `sx, sy` are screen
pixels and `ctx` is a `DrawCtx(assets, now, zoom)` (shared with `summons/`).

Part of the projectile-FX work in `journals/assets_journal.md`.
"""
from __future__ import annotations

from typing import Callable

from game.states.playing.drawctx import DrawCtx

ProjCtx = DrawCtx        # back-compat alias

_STYLES: dict[str, Callable] = {}


def style(name: str):
    """Register `fn(surface, sx, sy, proj, ctx)` as the draw for family `name`."""
    def deco(fn: Callable) -> Callable:
        if name in _STYLES:
            raise ValueError(f"projectile style {name!r} already registered")
        _STYLES[name] = fn
        return fn
    return deco


def classify(proj, default: str) -> str:
    """Pick a style for a live projectile: an explicit `proj.style` wins,
    otherwise infer from the fields it already sets."""
    if getattr(proj, "style", ""):
        return proj.style
    if proj.cone_half_angle > 0.0:
        return "cone"
    if proj.orbit_speed != 0.0 and proj.anchor is not None:
        return "orbit"
    return default


def draw_projectile(surface, sx, sy, proj, ctx: ProjCtx, *, default: str) -> None:
    name = classify(proj, default)
    fn = _STYLES.get(name) or _STYLES.get(default)
    if fn is not None:                       # unknown style -> default (e.g. "orbit"
        fn(surface, sx, sy, proj, ctx)       # before its module lands)


def registered() -> tuple[str, ...]:
    return tuple(_STYLES)


# Import the family modules so their @style decorators run.
from game.states.playing.projectiles import simple as _simple  # noqa: E402,F401
from game.states.playing.projectiles import cone as _cone      # noqa: E402,F401
from game.states.playing.projectiles import orbit as _orbit    # noqa: E402,F401
from game.states.playing.projectiles import melee as _melee    # noqa: E402,F401
