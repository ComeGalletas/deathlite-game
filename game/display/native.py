"""The few things pygame 2.6 does not expose about its own window, asked of
SDL directly through `ctypes`.

pygame's `SCALED` window keeps the display surface at the logical size and
scales it into the window on the GPU -- but it also pins the window's
minimum size to the logical size, and in windowed mode turns on SDL's
*integer* scaling, so a 1920x1080 window shows the 1600x900 frame centred
and unscaled with the mouse mapped offset-only. Two SDL calls undo that
(journal "Dynamic window scaling", probes #2 and #3, 2026-09-15). The
usable desktop bounds and the display DPI are the other two things the
fit rule wants and pygame cannot say. `system_cursor_ink_height` is the
one thing here that is not about the window: the size the desktop draws
its own arrow at, so the in-game arrow can match it.

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


# --- the system cursor ---------------------------------------------
# What the desktop draws its own arrow at, so the in-game arrow can be
# matched to it (journal "Cursor size", 2026-09-16). Windows sizes every
# cursor from `CursorBaseSize` -- the accessibility "Cursor size" slider,
# 32 by default and stored at 96 DPI -- scaled by the display's DPI. The
# visible arrow is only part of that bitmap, so its ink fraction is read
# from the bitmap itself; a custom cursor scheme is honoured that way.
_IDC_ARROW = 32512
_IMAGE_CURSOR = 2
_LR_SHARED = 0x8000
_CURSOR_BASE_DEFAULT = 32        # the slider's first stop
_ARROW_INK_FRACTION = 18.0 / 32.0    # the stock Windows 11 arrow, measured
_arrow_fraction = None           # the measured fraction, read once


class _IconInfo(ctypes.Structure):
    _fields_ = [("fIcon", ctypes.c_int), ("xHotspot", ctypes.c_uint32),
                ("yHotspot", ctypes.c_uint32), ("hbmMask", ctypes.c_void_p),
                ("hbmColor", ctypes.c_void_p)]


class _Bitmap(ctypes.Structure):
    _fields_ = [("bmType", ctypes.c_long), ("bmWidth", ctypes.c_long),
                ("bmHeight", ctypes.c_long), ("bmWidthBytes", ctypes.c_long),
                ("bmPlanes", ctypes.c_ushort), ("bmBitsPixel", ctypes.c_ushort),
                ("bmBits", ctypes.c_void_p)]


def _ink_fraction_of(gdi, bitmap_handle) -> float | None:
    """The share of a 32-bit colour bitmap's rows that carry an opaque
    pixel. None for a handle that will not read or is not 32-bit (the
    1-bit AND mask, on a cursor with no colour bitmap)."""
    if not bitmap_handle:
        return None
    bitmap = _Bitmap()
    if not gdi.GetObjectW(ctypes.c_void_p(bitmap_handle), ctypes.sizeof(_Bitmap),
                          ctypes.byref(bitmap)):
        return None
    if bitmap.bmBitsPixel != 32 or bitmap.bmHeight <= 0 or bitmap.bmWidth <= 0:
        return None
    size = bitmap.bmWidthBytes * bitmap.bmHeight
    buf = (ctypes.c_ubyte * size)()
    if not gdi.GetBitmapBits(ctypes.c_void_p(bitmap_handle), size, buf):
        return None
    rows = [y for y in range(bitmap.bmHeight)
            if any(buf[y * bitmap.bmWidthBytes + x * 4 + 3]
                   for x in range(bitmap.bmWidth))]
    if not rows:
        return None
    return float(rows[-1] - rows[0] + 1) / float(bitmap.bmHeight)


def _arrow_ink_fraction() -> float:
    """How much of the system arrow's bitmap its ink fills vertically.
    Read from the live cursor once; `_ARROW_INK_FRACTION` when it will not
    read, which is the stock arrow's own figure."""
    global _arrow_fraction
    if _arrow_fraction is not None:
        return _arrow_fraction
    _arrow_fraction = _ARROW_INK_FRACTION
    try:
        user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
        user.LoadImageW.restype = ctypes.c_void_p
        user.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user.GetIconInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi.GetObjectW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        gdi.GetBitmapBits.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p]
        gdi.DeleteObject.argtypes = [ctypes.c_void_p]
        cursor = user.LoadImageW(None, ctypes.c_void_p(_IDC_ARROW), _IMAGE_CURSOR,
                                 0, 0, _LR_SHARED)
        if not cursor:
            return _arrow_fraction
        info = _IconInfo()
        if not user.GetIconInfo(ctypes.c_void_p(cursor), ctypes.byref(info)):
            return _arrow_fraction
        try:
            measured = _ink_fraction_of(gdi, info.hbmColor)
            if measured:
                _arrow_fraction = measured
        finally:
            # GetIconInfo hands out copies; the caller owns them.
            for handle in (info.hbmMask, info.hbmColor):
                if handle:
                    gdi.DeleteObject(ctypes.c_void_p(handle))
    except Exception as exc:
        log.info("system arrow bitmap not readable (%s); assuming %.3f",
                 exc, _ARROW_INK_FRACTION)
    return _arrow_fraction


def system_cursor_ink_height(display: int = 0) -> float | None:
    """The height, in screen pixels, of the *visible* arrow the desktop
    draws -- what the in-game arrow is sized to match. None on any platform
    that will not say, which leaves the caller its own sizing."""
    if sys.platform != "win32":
        return None
    base = _CURSOR_BASE_DEFAULT
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors") as key:
            base = int(winreg.QueryValueEx(key, "CursorBaseSize")[0])
    except (OSError, ValueError, TypeError) as exc:
        log.info("CursorBaseSize unreadable (%s); assuming %d", exc, _CURSOR_BASE_DEFAULT)
    if base <= 0:
        base = _CURSOR_BASE_DEFAULT
    height = base * (dpi_scale(display) or 1.0) * _arrow_ink_fraction()
    return height if height > 0 else None
