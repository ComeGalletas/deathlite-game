"""Where every drawn text ends up, through the panels it was composed on
(UI-014.11).

`record(draw, size)` calls `draw(surface)` on a `size` surface and returns
`(placed, rendered)`: the `Placed` texts -- each string a font rendered,
with the rect its ink landed on the screen and whether a surface on the
way cut it -- and every string rendered while `draw` ran. Tracking is by
object:

* inside `tracking()` every font `game.fonts` builds is wrapped, and a
  wrapped font reports each `render` to the record running *now* (kept
  alive, so an `id` is never reused). A font built earlier and kept by a
  state -- the run's banner font, the HUD's -- is only tracked if it was
  built inside `tracking()`, so a test that shares one booted run opens
  `tracking()` before booting it (`test_fit.setUpModule`);
* `pygame.Surface` is swapped for a subclass while `draw` runs, so a panel,
  card or shadow surface a screen composes text onto remembers what it
  holds -- its `copy()` too -- and passes it on, shifted, when it is
  blitted in turn;
* `pygame.transform`'s scalers and flips hand a text surface's text to
  their result.

The ink is `get_bounding_rect()`, the glyphs' own box: two lines that only
share their fonts' line gaps do not touch.

What is not tracked: a text surface `convert`ed or `convert_alpha`ed (a
new plain surface), a panel holding text that is transformed, and
`pygame.freetype.render_to`. None of them loses text silently: the text
is in `rendered` and not in `placed`, which `lost()` reports.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import fonts

_BaseSurface = pygame.Surface
DOTS = "..."
SHADOW_PX = 6       # a drop shadow's or outline's offset, at most: the same text within it is one
_TRANSFORMS = ("scale", "smoothscale", "scale_by", "smoothscale_by", "flip", "rotate",
               "rotozoom")


@dataclass(frozen=True)
class Placed:
    text: str
    rect: pygame.Rect           # the ink, in screen coordinates (uncut)
    cut: bool                   # a surface on the way, or the screen, cut it


class _Record:
    def __init__(self):
        self.texts: dict[int, str] = {}
        self.keep: list = []
        self.rendered: list[str] = []

    def note(self, surface, text: str) -> None:
        self.texts[id(surface)] = text
        self.keep.append(surface)


_STATE = {"rec": None, "depth": 0, "patch": None}


class _Tag:
    """A font that reports its renders to the record running now."""

    def __init__(self, font):
        self.font = font

    def render(self, text, *a, **k):
        out = self.font.render(text, *a, **k)
        rec, s = _STATE["rec"], str(text)
        if rec is not None and s.strip():
            rec.note(out, s)
            rec.rendered.append(s)
        return out

    def __getattr__(self, name):
        return getattr(self.font, name)


def _forget_fit_fonts():
    import ui.text
    ui.text._FIT_CACHE.clear()


@contextmanager
def tracking():
    """Wrap every font `game.fonts` builds while inside; nests."""
    if _STATE["depth"] == 0:
        _forget_fit_fonts()
        real = fonts._load
        _STATE["patch"] = mock.patch.object(fonts, "_load", lambda *a, **k: _Tag(real(*a, **k)))
        _STATE["patch"].start()
    _STATE["depth"] += 1
    try:
        yield
    finally:
        _STATE["depth"] -= 1
        if _STATE["depth"] == 0:
            _STATE["patch"].stop()
            _forget_fit_fonts()


def _dest_xy(dest):
    if isinstance(dest, pygame.Rect):
        return dest.x, dest.y
    if hasattr(dest, "x") and hasattr(dest, "y") and not isinstance(dest, (tuple, list)):
        return int(dest.x), int(dest.y)
    return int(dest[0]), int(dest[1])


def record(draw, size) -> tuple[list[Placed], list[str]]:
    """`(placed, rendered)`: the texts `draw` put on a `size` screen, and
    every string a font rendered while it ran."""
    rec = _Record()

    class Surface(_BaseSurface):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.placed: list[Placed] = []
            self.frames: list[Frame] = []
            rec.keep.append(self)

        def copy(self):
            out = super().copy()
            out.placed = list(getattr(self, "placed", ()))
            out.frames = list(getattr(self, "frames", ()))
            rec.keep.append(out)
            return out

        def _take(self, src, dest, area):
            if not hasattr(self, "placed"):
                self.placed, self.frames = [], []
            x, y = _dest_xy(dest)
            if area is not None:
                area = pygame.Rect(area)
                x, y = x - area.x, y - area.y
            if isinstance(src, Surface):
                self.frames += [Frame(f.rect.move(x, y), f.label)
                                for f in getattr(src, "frames", ())]
            if id(src) in rec.texts:
                ink = src.get_bounding_rect()
                if ink.w == 0 or ink.h == 0:
                    return
                items = [Placed(rec.texts[id(src)], ink, False)]
            elif isinstance(src, Surface):
                items = getattr(src, "placed", [])
            else:
                return
            bounds = self.get_clip()
            if area is not None:
                bounds = bounds.clip(pygame.Rect(x + area.x, y + area.y, area.w, area.h))
            for p in items:
                r = p.rect.move(x, y)
                self.placed.append(Placed(p.text, r, p.cut or not bounds.contains(r)))

        def blit(self, source, dest=(0, 0), area=None, special_flags=0):
            out = super().blit(source, dest, area, special_flags)
            self._take(source, dest, area)
            return out

        def blits(self, blit_sequence, doreturn=True):
            out = [self.blit(*item) for item in blit_sequence]
            return out if doreturn else None

        def fblits(self, blit_sequence, special_flags=0):
            for src, dest in blit_sequence:
                self.blit(src, dest, None, special_flags)

    def carried(fn):
        def wrapped(src, *a, **k):
            out = fn(src, *a, **k)
            if id(src) in rec.texts:
                rec.note(out, rec.texts[id(src)])
            return out
        return wrapped

    def framed(fn):
        def wrapped(surface, assets, rect, *a, **k):
            out = fn(surface, assets, rect, *a, **k)
            label = a[0] if a else k.get("label")
            if isinstance(surface, Surface):
                surface.frames.append(Frame(pygame.Rect(rect), str(label) if label else None))
            return out
        return wrapped

    from ui import widgets
    patches = [mock.patch.object(pygame, "Surface", Surface)]
    patches += [mock.patch.object(widgets, n, framed(getattr(widgets, n)))
                for n in ("draw_button", "draw_ribbon")]
    patches += [mock.patch.object(pygame.transform, n, carried(getattr(pygame.transform, n)))
                for n in _TRANSFORMS if hasattr(pygame.transform, n)]
    with tracking():
        _STATE["rec"] = rec
        try:
            for p in patches:
                p.start()
            screen = Surface(size)
            draw(screen)
        finally:
            for p in reversed(patches):
                p.stop()
            _STATE["rec"] = None
    placed = Drawn(screen.placed)
    placed.frames = list(screen.frames)
    return placed, rec.rendered


@dataclass(frozen=True)
class Frame:
    """Button, card or ribbon art (`ui.widgets`) as drawn: where, and the
    label `ui.widgets` drew on it itself (None when the screen draws its own
    text on it -- a card, a row with a value)."""
    rect: pygame.Rect
    label: str | None


class Drawn(list):
    """The `Placed` texts of one screen, with the `frames` drawn on it."""
    frames: list


def crossing(placed, min_px: int = 2) -> list[tuple[Placed, Frame]]:
    """Texts on art they do not belong to: running over the edge of a
    button, card or ribbon (inside it by more than a `min_px` square, not
    wholly inside), or on a button that carries its own label and is not
    it -- the menu's summary line over its lower buttons. The art is drawn
    on the screen, so neither is a cut or a text-on-text overlap."""
    out = []
    for p in placed:
        for f in getattr(placed, "frames", ()):
            c = p.rect.clip(f.rect)
            if c.w < min_px or c.h < min_px:
                continue
            if not f.rect.contains(p.rect) or (f.label is not None and p.text != f.label):
                out.append((p, f))
    return out


def lost(placed: list[Placed], rendered: list[str]) -> list[str]:
    """Strings rendered while drawing that never reached the screen."""
    return sorted(set(rendered) - {p.text for p in placed})


def overlaps(placed: list[Placed], min_px: int = 2) -> list[tuple[Placed, Placed]]:
    """Pairs of texts whose ink shares more than a `min_px` square. The same
    string within `SHADOW_PX` of itself is one text (a drop shadow, an
    outline); the same string further off -- two "Nv. 3" rows collapsing --
    is an overlap."""
    out = []
    for i, a in enumerate(placed):
        for b in placed[i + 1:]:
            if a.text == b.text and abs(a.rect.x - b.rect.x) <= SHADOW_PX \
                    and abs(a.rect.y - b.rect.y) <= SHADOW_PX:
                continue
            c = a.rect.clip(b.rect)
            if c.w >= min_px and c.h >= min_px:
                out.append((a, b))
    return out


def trimmed(placed: list[Placed]) -> list[str]:
    return sorted({p.text for p in placed if p.text.rstrip().endswith(DOTS)})
