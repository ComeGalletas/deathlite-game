"""The window the fixed-size frame is scaled into.

The game draws every frame to a `config.SCREEN_WIDTH x SCREEN_HEIGHT`
display surface (the *logical* size) and never learns how big the window
is: pygame's `SCALED` mode scales the finished frame into the window on
the GPU, aspect kept, black bars for the rest, and maps the mouse back
into logical coordinates. So the camera, the zoom, the HUD and every
click target are the same on a 1366x768 laptop and a 3440x1440 monitor
(journal: "Dynamic window scaling", 2026-09-15).

`DisplayWindow` owns that window:

* `prepare()` -- the SDL environment hints, before `pygame.init()`.
* `open()` -- the single `set_mode` of the process (a second one that
  changes fullscreen fails: probe #5), vsync first and the plain fixed
  window as the fallback, then the SDL shims (`native.py`) that let the
  window shrink and scale freely, and the saved or fitted size.
* `set_mode("windowed" | "borderless")` -- borderless is SDL's desktop
  fullscreen through `pygame.display.toggle_fullscreen()`: no display-mode
  switch, ever. The last windowed size is kept for the way back.
* `set_windowed_size` / `cycle_resolution` -- the Options "Resolution" row.
* `handle_event` -- a drag resize is remembered (persisted at quit).
* `settings()` / `restore()` -- `save.settings["display"]`.

`available` is False when `SCALED` was refused (the headless dummy driver,
some remote desktops) or in the browser build: the window is then the plain
fixed one and every method here is a no-op, which the Options rows report.
The Options screen is the only place any of this changes (owner's rule):
there is no hotkey, and a change can never happen during a run.
"""
from __future__ import annotations

import logging
import os
import sys

import pygame

from game import config
from game.display import fit, native

log = logging.getLogger(__name__)

MODES = ("windowed", "borderless")
MODE_LABELS = {"windowed": "Windowed", "borderless": "Borderless"}


def _logical() -> tuple[int, int]:
    return (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)


def _scalable() -> bool:
    return bool(config.WINDOW_RESIZABLE) and sys.platform != "emscripten"


class DisplayWindow:
    def __init__(self) -> None:
        self.available = False
        self.vsync = False
        self.surface: pygame.Surface | None = None
        self.mode = config.WINDOW_MODE_DEFAULT
        # The windowed size to use / return to: saved, else fitted at open.
        self.windowed_size: tuple[int, int] | None = None
        self.scale = 1.0                # window pixels per logical pixel
        self.on_scale_changed = None    # callable(scale); the cursor follows
        self.dirty = False              # a drag resize not yet persisted

    # --- before the window --------------------------------------------
    @staticmethod
    def prepare() -> None:
        """Hints SDL reads at init. `setdefault`, so a player's own
        environment wins. DPI awareness: without it Windows scales the
        whole output a second time on a 125 % desktop (probe #7). The
        scale filter: pygame forces `nearest`, which at 1.2x duplicates
        every fifth pixel row (probe #6)."""
        if not _scalable():
            return
        if config.WINDOW_DPI_AWARE and sys.platform == "win32":
            os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
        if config.WINDOW_SCALE_FILTER:
            os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", str(config.WINDOW_SCALE_FILTER))

    def restore(self, settings: dict | None) -> None:
        """Take the saved mode and windowed size (already normalised by
        `save._coerce`); anything missing keeps the defaults."""
        d = (settings or {}).get("display") or {}
        mode = d.get("mode")
        self.mode = mode if mode in MODES else config.WINDOW_MODE_DEFAULT
        win = d.get("window")
        if isinstance(win, (list, tuple)) and len(win) == 2:
            self.windowed_size = (int(win[0]), int(win[1]))

    # --- the window -------------------------------------------------
    @staticmethod
    def open_surface(flags: int = 0) -> tuple[pygame.Surface, bool]:
        """The display surface, synced to the display when `config.VSYNC`
        asks and the driver allows. Returns `(surface, vsync_on)`. A driver
        that cannot (the headless dummy driver, some remote desktops)
        raises `pygame.error`, and the plain window is the answer then --
        the game must never fail to open over presentation."""
        size = _logical()
        if config.VSYNC:
            try:
                surf = pygame.display.set_mode(
                    size, pygame.SCALED | pygame.DOUBLEBUF | flags, vsync=1)
                return surf, True
            except pygame.error as exc:
                log.info("vsync window refused (%s); plain window", exc)
        return pygame.display.set_mode(size), False

    def open(self) -> tuple[pygame.Surface, bool]:
        flags = 0
        if _scalable():
            flags |= pygame.RESIZABLE
            if self.mode == "borderless":
                flags |= pygame.FULLSCREEN
        self.surface, self.vsync = self.open_surface(flags)
        # The scaled path is the only one that scales; the plain fallback
        # is a fixed window and the feature stays dormant.
        self.available = bool(self.vsync) and _scalable()
        if not self.available:
            self.mode = "windowed"
            return self.surface, self.vsync
        native.set_minimum_size(*config.WINDOW_MIN)
        native.set_integer_scale(False)
        if self.windowed_size is None:
            self.windowed_size = self.fitted_size()
        if self.mode == "windowed":
            self._apply_windowed_size(self.windowed_size)
        self._refresh_scale()
        return self.surface, self.vsync

    # --- geometry -----------------------------------------------------
    def desktop_size(self) -> tuple[int, int]:
        try:
            sizes = pygame.display.get_desktop_sizes()
            if sizes:
                return (int(sizes[0][0]), int(sizes[0][1]))
        except pygame.error:
            pass
        return _logical()

    def fitted_size(self) -> tuple[int, int]:
        """The first-launch window, from the fit rule."""
        desktop = self.desktop_size()
        return fit.fit_window(_logical(), desktop, native.usable_bounds(0),
                              native.dpi_scale(0) or 1.0, config.WINDOW_MIN,
                              config.WINDOW_FIT_FRACTION)

    def _apply_windowed_size(self, size: tuple[int, int]) -> None:
        size = fit.clamp_window(size, config.WINDOW_MIN, self.desktop_size())
        # pygame re-pins the minimum to the logical size when it leaves
        # fullscreen (probe, 2026-09-15: a 1280x720 request came back as
        # 1600x900 after a toggle), so the floor is lifted before every
        # size, not only at open.
        native.set_minimum_size(*config.WINDOW_MIN)
        native.set_window_size(*size)
        native.set_integer_scale(False)
        self.windowed_size = size

    def _refresh_scale(self) -> None:
        try:
            ww, wh = pygame.display.get_window_size()
        except pygame.error:
            return
        lw, lh = _logical()
        scale = min(ww / float(lw), wh / float(lh)) if ww and wh else 1.0
        if abs(scale - self.scale) > 1e-6:
            self.scale = scale
            if self.on_scale_changed is not None:
                self.on_scale_changed(scale)

    # --- the Options rows -------------------------------------------
    def set_mode(self, mode: str) -> bool:
        """Windowed <-> borderless. Returns whether anything changed."""
        if mode not in MODES:
            raise ValueError(f"unknown display mode: {mode!r}")
        if not self.available or mode == self.mode:
            return False
        pygame.display.toggle_fullscreen()
        self.mode = mode
        if mode == "windowed":
            # pygame re-asserts integer scaling on the way back; and the
            # window comes back at whatever size SDL remembered.
            self._apply_windowed_size(self.windowed_size or self.fitted_size())
        else:
            native.set_integer_scale(False)
        self._refresh_scale()
        return True

    def set_windowed_size(self, size: tuple[int, int]) -> bool:
        """The Resolution row. In borderless the size is only remembered
        for the return to windowed (the row is greyed out then)."""
        if not self.available:
            return False
        if self.mode == "windowed":
            self._apply_windowed_size(size)
            self._refresh_scale()
        else:
            self.windowed_size = fit.clamp_window(size, config.WINDOW_MIN, self.desktop_size())
        self.dirty = False
        return True

    def resolution_entries(self) -> list[tuple[int, int]]:
        return fit.resolution_entries(config.WINDOW_RESOLUTIONS, self.desktop_size(),
                                      config.WINDOW_MIN)

    def resolution_index(self) -> int:
        """Index of the windowed size in the entries, -1 when it is a
        custom (dragged) size."""
        entries = self.resolution_entries()
        try:
            return entries.index(tuple(self.windowed_size or ()))
        except ValueError:
            return -1

    def cycle_resolution(self, direction: int) -> bool:
        """Left / Right on the Resolution row: the next listed size, from
        the nearest one when the current size is custom."""
        if not self.available or self.mode != "windowed":
            return False
        entries = self.resolution_entries()
        if not entries:
            return False
        i = self.resolution_index()
        if i < 0:
            i = fit.nearest_entry(entries, self.windowed_size or _logical())
            # From a custom size, Right goes to the nearest larger entry
            # and Left to the nearest smaller one.
            if direction > 0 and entries[i][0] <= (self.windowed_size or _logical())[0]:
                i += 1
            elif direction < 0 and entries[i][0] >= (self.windowed_size or _logical())[0]:
                i -= 1
            i = max(0, min(len(entries) - 1, i))
        else:
            i = (i + direction) % len(entries)
        return self.set_windowed_size(entries[i])

    def mode_label(self) -> str:
        return MODE_LABELS[self.mode] if self.available else "Unavailable"

    def resolution_label(self) -> str:
        """What the Resolution row shows: the desktop size in borderless,
        the windowed size otherwise ("Custom" when dragged)."""
        if not self.available:
            return "Unavailable"
        if self.mode == "borderless":
            w, h = self.desktop_size()
            return f"{w}x{h}"
        w, h = self.windowed_size or _logical()
        return f"{w}x{h}" if self.resolution_index() >= 0 else f"Custom {w}x{h}"

    def resolution_selectable(self) -> bool:
        return self.available and self.mode == "windowed"

    # --- events -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        """A drag resize: remember the new windowed size (persisted at
        quit) and re-apply the scaling fix. Never consumes the event."""
        if not self.available or event.type != pygame.WINDOWSIZECHANGED:
            return False
        if self.mode != "windowed":
            return False
        try:
            size = tuple(int(v) for v in pygame.display.get_window_size())
        except pygame.error:
            return False
        if size != self.windowed_size:
            self.windowed_size = size
            self.dirty = True
        native.set_integer_scale(False)
        self._refresh_scale()
        return False

    # --- persistence --------------------------------------------------
    def settings(self) -> dict:
        d: dict = {"mode": self.mode}
        if self.windowed_size is not None:
            d["window"] = [int(self.windowed_size[0]), int(self.windowed_size[1])]
        return d
