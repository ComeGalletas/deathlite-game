"""Window-size arithmetic, with no pygame in it.

The render target is fixed (`config.SCREEN_WIDTH x SCREEN_HEIGHT`, the
*logical* size); the window it is scaled into can be any size. These are the
rules that pick and bound that window size (journal: "Dynamic window
scaling", 2026-09-15). Pure functions so the tests need no display.

Sizes are `(w, h)` tuples of pixels. `desktop` is what SDL reports for the
display; `usable` is the desktop minus the taskbar when the shim can ask
(`game/display/native.usable_bounds`), else the desktop.
"""
from __future__ import annotations


def fit_window(logical: tuple[int, int], desktop: tuple[int, int],
               usable: tuple[int, int] | None = None, dpi_scale: float = 1.0,
               minimum: tuple[int, int] = (800, 450),
               fraction: float = 0.9) -> tuple[int, int]:
    """The first-launch window: the logical size at the display's DPI (so a
    1600x900 window looks the size it always did on a 125 % desktop), shrunk
    to fit `fraction` of the usable desktop keeping its aspect, never below
    `minimum`."""
    usable = usable or desktop
    w = float(logical[0]) * max(0.01, float(dpi_scale))
    h = float(logical[1]) * max(0.01, float(dpi_scale))
    cap_w, cap_h = usable[0] * fraction, usable[1] * fraction
    s = min(1.0, cap_w / w, cap_h / h)
    w, h = w * s, h * s
    up = max(1.0, minimum[0] / w, minimum[1] / h)
    return (int(round(w * up)), int(round(h * up)))


def clamp_window(size: tuple[int, int], minimum: tuple[int, int],
                 maximum: tuple[int, int]) -> tuple[int, int]:
    """A saved or requested size held inside `minimum..maximum` per axis.
    The maximum is the desktop: a window larger than the screen is never
    useful, and the desktop can change between sessions, so this runs when
    the size is applied, not when it is loaded."""
    w = min(max(int(size[0]), int(minimum[0])), max(int(minimum[0]), int(maximum[0])))
    h = min(max(int(size[1]), int(minimum[1])), max(int(minimum[1]), int(maximum[1])))
    return (w, h)


def letterbox(window: tuple[int, int], logical: tuple[int, int]) -> tuple[float, tuple[float, float]]:
    """How the logical surface sits in the window: the uniform scale and the
    top-left offset of the image (the bars are what is left)."""
    scale = min(window[0] / float(logical[0]), window[1] / float(logical[1]))
    ox = (window[0] - logical[0] * scale) / 2.0
    oy = (window[1] - logical[1] * scale) / 2.0
    return scale, (ox, oy)


def resolution_entries(candidates, desktop: tuple[int, int],
                       minimum: tuple[int, int]) -> list[tuple[int, int]]:
    """The Options "Resolution" list: the candidates that fit this desktop
    and clear the floor, smallest first."""
    out = [(int(w), int(h)) for w, h in candidates
           if w <= desktop[0] and h <= desktop[1] and w >= minimum[0] and h >= minimum[1]]
    return sorted(set(out))


def nearest_entry(entries: list[tuple[int, int]], size: tuple[int, int]) -> int:
    """Index of the entry closest in width to `size` (-1 when there are
    none) -- where the cycle starts from a custom, dragged size."""
    if not entries:
        return -1
    return min(range(len(entries)), key=lambda i: abs(entries[i][0] - size[0]))
