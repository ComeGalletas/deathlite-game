"""The window the fixed-size frame is scaled into (journal: "Dynamic window
scaling", 2026-09-15).

    fit.py      -- the pure size arithmetic: first-launch fit, clamps, the
                   letterbox, the Resolution list
    native.py   -- the SDL calls pygame does not expose, through ctypes,
                   each with a fallback
    window.py   -- `DisplayWindow`: open, windowed / borderless, the
                   Resolution row, drag resizes, the saved settings
"""
from game.display.window import DisplayWindow, MODES, MODE_LABELS

__all__ = ["DisplayWindow", "MODES", "MODE_LABELS"]
