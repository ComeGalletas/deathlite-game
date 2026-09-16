"""The few things pygame 2.6 does not expose about its own window, asked of
SDL directly through `ctypes`.

pygame's `SCALED` window keeps the display surface at the logical size and
scales it into the window on the GPU -- but it also pins the window's
minimum size to the logical size, and in windowed mode turns on SDL's
*integer* scaling, so a 1920x1080 window shows the 1600x900 frame centred
and unscaled with the mouse mapped offset-only. Two SDL calls undo that
(journal "Dynamic window scaling", probes #2 and #3, 2026-09-15). The
usable desktop bounds and the display DPI are the other two things the
fit rule wants and pygame cannot say.

Every function here returns `False` / `None` on any failure and logs why:
a missing symbol or an odd driver degrades one capability, never the
window. This is the only module that touches `ctypes` or
`pygame._sdl2`; nothing else should.

`ctypes.CDLL("SDL2.dll")` after `pygame.init()` binds the SDL that pygame
already loaded (Windows returns the loaded module by name), so the packaged
build needs no path.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import logging
import sys

log = logging.getLogger(__name__)

_SDL_WINDOWPOS_CENTERED = 0x2FFF0000
_lib = None          # the SDL2 library, False once loading failed


class _Rect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int),
                ("w", ctypes.c_int), ("h", ctypes.c_int)]


def _sdl():
    global _lib
    if _lib is None:
        try:
            if sys.platform == "win32":
                _lib = ctypes.CDLL("SDL2.dll")
            else:
                name = ctypes.util.find_library("SDL2")
                _lib = ctypes.CDLL(name) if name else False
        except OSError as exc:
            log.info("SDL2 not reachable through ctypes (%s)", exc)
            _lib = False
    return _lib or None


_wrapper = None      # the one `Window` wrapper of the display window, kept alive


def _window():
    """`(sdl, SDL_Window*)` for pygame's display window, or `(None, None)`.

    The `pygame._sdl2.video.Window` wrapper is created **once** and kept
    for the life of the process. pygame stores a pointer to the wrapper in
    the SDL window's own data and resolves window events through it, so a
    wrapper made per call and dropped leaves that pointer dangling and the
    next resize event reads freed memory -- an access violation in the
    event pump that came and went with the heap layout (found 2026-09-15:
    the Resolution row crashed the game on a fresh save and not on a saved
    one). The wrapper is remade only if its window is gone (a new
    `set_mode`)."""
    global _wrapper
    sdl = _sdl()
    if sdl is None:
        return None, None
    try:
        sdl.SDL_GetWindowFromID.restype = ctypes.c_void_p
        sdl.SDL_GetWindowFromID.argtypes = [ctypes.c_uint32]
        ptr = sdl.SDL_GetWindowFromID(_wrapper.id) if _wrapper is not None else None
        if not ptr:
            from pygame._sdl2.video import Window
            _wrapper = Window.from_display_module()
            ptr = sdl.SDL_GetWindowFromID(_wrapper.id)
        return (sdl, ptr) if ptr else (None, None)
    except Exception as exc:          # pygame.error, ImportError, AttributeError
        log.info("SDL window handle unavailable (%s)", exc)
        _wrapper = None
        return None, None


def forget_window() -> None:
    """Drop the kept wrapper before `pygame.display.quit()`: its window is
    about to be destroyed, and asking a destroyed window for its id would
    read freed memory."""
    global _wrapper
    _wrapper = None


def set_minimum_size(width: int, height: int) -> bool:
    """Lift pygame's minimum (the logical size) so the window can shrink."""
    sdl, win = _window()
    if win is None:
        return False
    try:
        sdl.SDL_SetWindowMinimumSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        sdl.SDL_SetWindowMinimumSize(win, int(width), int(height))
        return True
    except Exception as exc:
        log.info("SDL_SetWindowMinimumSize failed (%s)", exc)
        return False


def set_integer_scale(enabled: bool) -> bool:
    """SDL's integer-scale flag on pygame's renderer. Off is what lets a
    windowed frame scale by 1.2x or 0.75x instead of sitting unscaled in
    the middle; pygame turns it back on when leaving fullscreen, so this is
    re-applied after every toggle and size change."""
    sdl, win = _window()
    if win is None:
        return False
    try:
        sdl.SDL_GetRenderer.restype = ctypes.c_void_p
        sdl.SDL_GetRenderer.argtypes = [ctypes.c_void_p]
        ren = sdl.SDL_GetRenderer(win)
        if not ren:
            return False
        sdl.SDL_RenderSetIntegerScale.argtypes = [ctypes.c_void_p, ctypes.c_int]
        sdl.SDL_RenderSetIntegerScale(ren, 1 if enabled else 0)
        return True
    except Exception as exc:
        log.info("SDL_RenderSetIntegerScale failed (%s)", exc)
        return False


def usable_bounds(display: int = 0) -> tuple[int, int] | None:
    """The desktop minus the taskbar, as `(w, h)`; None when SDL will not say."""
    sdl = _sdl()
    if sdl is None:
        return None
    try:
        rect = _Rect()
        sdl.SDL_GetDisplayUsableBounds.argtypes = [ctypes.c_int, ctypes.POINTER(_Rect)]
        if sdl.SDL_GetDisplayUsableBounds(int(display), ctypes.byref(rect)) != 0:
            return None
        return (int(rect.w), int(rect.h)) if rect.w > 0 and rect.h > 0 else None
    except Exception as exc:
        log.info("SDL_GetDisplayUsableBounds failed (%s)", exc)
        return None


def dpi_scale(display: int = 0) -> float | None:
    """The display's scale factor (1.25 on a 125 % desktop), from its
    horizontal DPI over 96. Only meaningful once SDL is DPI-aware
    (`SDL_WINDOWS_DPI_AWARENESS`); an unaware process reports 96."""
    sdl = _sdl()
    if sdl is None:
        return None
    try:
        d, h, v = ctypes.c_float(), ctypes.c_float(), ctypes.c_float()
        sdl.SDL_GetDisplayDPI.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_float),
                                          ctypes.POINTER(ctypes.c_float),
                                          ctypes.POINTER(ctypes.c_float)]
        if sdl.SDL_GetDisplayDPI(int(display), ctypes.byref(d), ctypes.byref(h),
                                 ctypes.byref(v)) != 0:
            return None
        return float(h.value) / 96.0 if h.value > 0 else None
    except Exception as exc:
        log.info("SDL_GetDisplayDPI failed (%s)", exc)
        return None


def set_window_size(width: int, height: int, centre: bool = True) -> bool:
    """Resize the window (the logical surface is untouched) and, by
    default, re-centre it on its display."""
    sdl, win = _window()
    if win is None:
        return False
    try:
        sdl.SDL_SetWindowSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        sdl.SDL_SetWindowSize(win, int(width), int(height))
        if centre:
            sdl.SDL_SetWindowPosition.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
            sdl.SDL_SetWindowPosition(win, _SDL_WINDOWPOS_CENTERED, _SDL_WINDOWPOS_CENTERED)
        return True
    except Exception as exc:
        log.info("SDL_SetWindowSize failed (%s)", exc)
        return False
