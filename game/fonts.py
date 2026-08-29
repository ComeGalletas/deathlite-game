"""Text fonts -- one bundled cartoonish face (Fredoka) with a graceful degrade.

Every `pygame.font.SysFont("georgia" / "arialrounded" / "consolas", ...)` call
site goes through `heading()` / `body()` / `mono()` here instead, so the game
ships a consistent look and the browser build -- which has no system fonts --
renders in the intended face rather than the pygame default.

Degrade contract (same as `game/assets.py` and `game/save.py`): a missing or
unreadable font file falls back to `SysFont`, which itself falls back to the
pygame default font. Text always renders; it never raises.

No module-level cache: like the `SysFont` calls it replaces, every call builds a
fresh `Font`. Callers that need a font per frame (only `ui/damage_numbers.py`)
keep their own cache. A cache here would hand back `Font` objects created before
a `pygame.quit()` / `pygame.init()` cycle -- a segfault waiting to happen in the
test suite.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pygame

log = logging.getLogger(__name__)

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# Bundled faces, by role. Fredoka is a variable font -- pygame renders it at its
# default instance; emphasis is a synthetic bold via `Font.set_bold`.
_FILES = {
    "sans": "Fredoka-VariableFont_wdth,wght.ttf",
}

# SysFont names tried when the bundled file is absent (desktop only -- in the
# browser SysFont yields the default face anyway).
_SYS_FALLBACK = {
    "sans": "georgia",
    "mono": "consolas",
}

_warned: set[str] = set()


def _load(role: str, px: int, bold: bool) -> pygame.font.Font:
    font: pygame.font.Font | None = None
    fname = _FILES.get(role)
    if fname:
        path = FONTS_DIR / fname
        if path.exists():
            try:
                font = pygame.font.Font(str(path), px)
            except (pygame.error, OSError) as exc:
                if role not in _warned:
                    log.warning("font %s unreadable (%s) -- using SysFont", path, exc)
                    _warned.add(role)
        elif role not in _warned:
            log.info("bundled font %s missing -- using SysFont", path)
            _warned.add(role)

    if font is None:
        font = pygame.font.SysFont(_SYS_FALLBACK.get(role, "georgia"), px)

    if bold:
        font.set_bold(True)
    return font


def heading(px: int, *, bold: bool = True) -> pygame.font.Font:
    """Titles, banners, hero names -- the bundled cartoonish face, bold."""
    return _load("sans", px, bold)


def body(px: int, *, bold: bool = False) -> pygame.font.Font:
    """Menu rows, HUD, instructions, floating damage -- the bundled face."""
    return _load("sans", px, bold)


def mono(px: int, *, bold: bool = False) -> pygame.font.Font:
    """Fixed-width, for the dev overlay / dev menu column alignment. There is no
    bundled monospace face: SysFont('consolas') on desktop, default in-browser."""
    return _load("mono", px, bold)
