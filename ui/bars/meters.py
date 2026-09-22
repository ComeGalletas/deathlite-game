"""HP / XP bars composed from the `assets/ui/04.png` hex family.

A bar is three layers at a shared origin, because the sheet is authored that
way: the column-0 sprite is a **housing** with a transparent trough, and the
fill sprites are self-contained bars carrying their own rails, which land on
the same scanlines as the housing's inner rails. So nothing here needs a
per-family offset table -- the rig's `well` says where the fill rests inside
the housing's art box and every layer blits against that.

The sheet ships six pre-rendered fill steps per colour (100 / 82 / 61 / 40 /
18 / 0 %), which is far too coarse for HP. Those steps are not the runtime
granularity: they exist so the artist could author a right terminus at each
length -- the hex point on this family. That terminus is simply the fill
sprite's own right cap, so cutting the 100 % sprite to an exact pixel length
through `slices.hslice` carries it along. The bar then moves continuously
while every edge on screen is still authored art, never a drawn rectangle.

`framed=False` drops the housing and returns the bare fill at the same
horizontal inset, which is how the XP bar sits slimmer than the HP bar
without a second art style, and stays aligned under it to the pixel.
"""
from __future__ import annotations

import pygame

from ui.bars import slices

_cache: dict[tuple, pygame.Surface | None] = {}
# Sized for the overhead enemy bars (journal: enemy_health_bar_journal.md).
# The HUD alone needs a couple of hundred entries -- a long bar at every fill
# position it passes through -- and the enemy bars add one family per distinct
# track length times that track's own fill positions, which is several hundred
# more. Over the cap the whole cache is dropped and the HUD's bars rebuild
# with it, so the cap has to clear the working set rather than sit inside it.
_CACHE_MAX = 1536


def _well(assets, frame: str) -> tuple[int, int, int, int] | None:
    """`(x, y, w, h)` of the fill's resting place inside `frame`'s art box."""
    spec = assets.rig(frame) or {}
    well = spec.get("well")
    if not well or len(well) != 4:
        return None
    return tuple(int(v) for v in well)          # type: ignore[return-value]


def inset(assets, *, frame: str) -> int | None:
    """Native px the housing `frame` spends either side of the fill track.

    `bar(width=...)` takes the bar's *outer* width, but a caller that sizes
    the **track** -- the part that carries meaning -- asks for `track +
    inset(...)`. The overhead enemy bar does, because its length states an
    enemy's maximum HP and a 6-px track inside a 14-px bar would say almost
    nothing. `None` when the art is missing, as everywhere else here.
    """
    well = _well(assets, frame)
    housing = assets.image(frame)
    if well is None or housing is None:
        return None
    return housing.get_width() - well[2]


def bar(assets, *, frame: str, fill: str, empty: str, width: int,
        fraction: float, framed: bool = True, scale: int = 1):
    """A finished bar Surface, or `None` when the art is missing.

    `width` is the bar's outer width in **native** px (the housing's art box
    rebuilt to that length); the result is `scale`d up from there, so a x3 bar
    moves its fill in 3-px screen steps and keeps a clean pixel grid.
    """
    width, scale = int(width), max(1, int(scale))
    fraction = max(0.0, min(1.0, float(fraction)))
    well = _well(assets, frame)
    housing = assets.image(frame)
    if well is None or housing is None:
        return None

    wx, wy, ww, wh = well
    track = width - (housing.get_width() - ww)
    filled = round(track * fraction)
    key = (frame, fill, empty, width, filled, framed, scale)
    if key in _cache:
        return _cache[key]

    out = pygame.Surface((width, housing.get_height() if framed else wh),
                         pygame.SRCALPHA)
    fy = wy if framed else 0

    trough = slices.hslice(assets, empty, track)
    if trough is None:
        _cache[key] = None
        return None
    out.blit(trough, (wx, fy))

    # Short of its own two caps the fill has no body left to draw, and forcing
    # one would widen the bar past `filled` -- an almost-dead hero would still
    # show a sliver of health. Below that it simply is not drawn.
    if filled >= sum(slices.caps(assets, fill)):
        cut = slices.hslice(assets, fill, filled)
        if cut is not None:
            out.blit(cut, (wx, fy))

    if framed:
        shell = slices.hslice(assets, frame, width)
        if shell is not None:
            out.blit(shell, (0, 0))

    if scale != 1:
        out = pygame.transform.scale(
            out, (out.get_width() * scale, out.get_height() * scale))

    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    _cache[key] = out
    return out


def clear_cache() -> None:
    """Test helper: drop cached bars."""
    _cache.clear()
