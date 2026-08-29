"""Per-kind summon rendering.

Each summon kind registers a draw function with `@summon_style("kind")`;
`draw_summon()` dispatches on `Summon.kind`. `WorldRenderer.one_summon` is a
thin call into this — an animated summon (the Spirit Wolf) is a new small module
here, not another branch in `rendering.py`.

Style fn signature: `fn(surface, sx, sy, summon, ctx)` where `sx, sy` are screen
pixels and `ctx` is a `DrawCtx(assets, now, zoom)` (shared with `projectiles/`).

Part of the weapon/summon-animation work in `journals/assets_journal.md` (WA1).
"""
from __future__ import annotations

from typing import Callable

import pygame

from game.states.playing.drawctx import DrawCtx  # noqa: F401 (re-export)

_STYLES: dict[str, Callable] = {}


def summon_style(kind: str):
    """Register `fn(surface, sx, sy, summon, ctx)` as the draw for `kind`."""
    def deco(fn: Callable) -> Callable:
        if kind in _STYLES:
            raise ValueError(f"summon style {kind!r} already registered")
        _STYLES[kind] = fn
        return fn
    return deco


@summon_style("disc")
def _disc(surface, sx, sy, s, ctx) -> None:
    """Generic fallback: the summon's colour disc plus a bright core."""
    pygame.draw.circle(surface, s.color, (int(sx), int(sy)), round(9 * ctx.zoom))
    pygame.draw.circle(surface, (240, 245, 255), (int(sx), int(sy)), round(3 * ctx.zoom))


def draw_summon(surface, sx, sy, s, ctx: DrawCtx, *, default: str = "disc") -> None:
    fn = _STYLES.get(s.kind) or _STYLES.get(default)
    if fn is not None:
        fn(surface, sx, sy, s, ctx)


def registered() -> tuple[str, ...]:
    return tuple(_STYLES)


# Import the kind modules so their @summon_style decorators run.
from game.states.playing.summons import totem as _totem  # noqa: E402,F401
from game.states.playing.summons import wolf as _wolf    # noqa: E402,F401
