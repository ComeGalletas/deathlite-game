"""Fonts, and the text rendered from them, kept by the object that draws
them (RND-008.3, `frame_time_journal.md`).

`game/fonts.py` builds a new `Font` from the bundled variable TTF on every
call and keeps nothing, on purpose: a module-level cache would hand back
`Font` objects across a `pygame.quit()` / `pygame.init()` cycle, which
segfaults the suite. But a new `Font` also starts with an empty glyph
cache, so its first `render` rasterises every glyph, about 1.4 ms a call on
the owner's machine. Done every frame, that cost the run's opening hints
about 17 ms of draw.

A `TextCache` is that cache with an owner. The run holds one
(`PlayingState.text_cache`), so it lives and dies inside one pygame session,
the way `ui/damage_numbers.py` keeps its fonts. It holds the fonts by role,
design size and weight, and the surfaces rendered from them by text and
colour. Every key carries `config.RENDER_SCALE`, which sets the native size
of both, and the owner replaces its cache when the display is re-opened,
so nothing sized for one scale is drawn at another.

The surfaces handed back are shared: blit them, never draw on them or
change their alpha.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from ui import text

# The roles `game/fonts.py` serves, by the name of its function. Looked up
# on the module at build time, not bound here, so a patched face is used.
_ROLES = ("body", "heading", "mono")


class TextCache:
    # Rendered surfaces kept before the cache starts over. The run draws a
    # few dozen distinct strings (hint words, cap labels); this only stops a
    # caller that renders changing text from growing it without end.
    MAX_TEXTS = 256

    def __init__(self) -> None:
        self._fonts: dict[tuple, pygame.font.Font] = {}
        self._texts: dict[tuple, pygame.Surface] = {}

    def font(self, role: str, px: int, *, bold: bool = False) -> pygame.font.Font:
        """The `role` face ("body", "heading" or "mono") at design size
        `px`, built once per render scale."""
        key = (role, px, bold, config.RENDER_SCALE)
        found = self._fonts.get(key)
        if found is None:
            if role not in _ROLES:
                raise ValueError(f"unknown font role {role!r}")
            found = self._fonts[key] = getattr(fonts, role)(px, bold=bold)
        return found

    def render(self, role: str, px: int, words: str, colour, *,
               bold: bool = False) -> pygame.Surface:
        """`words` rendered antialiased in `colour`, as `Font.render` would."""
        key = ("plain", role, px, bold, config.RENDER_SCALE, words, tuple(colour))
        found = self._texts.get(key)
        if found is None:
            found = self._keep(key, self.font(role, px, bold=bold).render(words, True, colour))
        return found

    def shadowed(self, role: str, px: int, words: str, colour, *,
                 bold: bool = False) -> pygame.Surface:
        """`words` over its drop shadow, as `ui.text.shadowed` draws it."""
        key = ("shadowed", role, px, bold, config.RENDER_SCALE, words, tuple(colour))
        found = self._texts.get(key)
        if found is None:
            found = self._keep(key, text.shadowed(self.font(role, px, bold=bold), words, colour))
        return found

    def _keep(self, key: tuple, surface: pygame.Surface) -> pygame.Surface:
        if len(self._texts) >= self.MAX_TEXTS:
            self._texts.clear()
        self._texts[key] = surface
        return surface
