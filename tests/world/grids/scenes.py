"""Hand-built height maps, drawn as ASCII, and the `LevelIndex` over them.

Legend (every flight here spans one level, 1 down to 0):

    1   ground, level 1         0   ground, level 0
    #   cliff holding up level 1
    v   straight flight cut in a south-facing wall (`VSTAIR`, dir "s")
    ^   north flight on a plateau's back rim (`VSTAIR`, dir "n")
    H F lateral crossing on a plateau's east flank (`EWSTAIR`, tag
        "side_e"): H is its head (row 0), F its foot (row 1)
    .   nothing (open sea)
"""
from __future__ import annotations

from types import SimpleNamespace

import pygame

from game import config
from world.elevation import LevelIndex
from world.layout import CLIFF, EWSTAIR, GROUND, VSTAIR, Cell

_LEGEND = {
    "1": Cell(GROUND, level=1),
    "0": Cell(GROUND, level=0),
    "#": Cell(CLIFF, level=1, drop=1, row=0),
    "v": Cell(VSTAIR, level=1, drop=1, row=0, dir="s"),
    "^": Cell(VSTAIR, level=1, drop=1, row=0, dir="n"),
    "H": Cell(EWSTAIR, level=1, drop=1, row=0, tag="side_e"),
    "F": Cell(EWSTAIR, level=1, drop=1, row=1, tag="side_e"),
}

# A south wall with one straight flight cut in it.
WALL_FLIGHT = """
11111
11111
##v##
00000
00000
"""

# A plateau's east flank with a protruding lateral crossing: the low terrace
# carries on north and south of the unit, and the flank itself is a bare
# level change with no stone in it.
LATERAL = """
1110000
1110000
111H000
111F000
1110000
"""

# A plateau's back: no wall, the rim cell itself is the flight down north.
NORTH_RIM = """
00000
00000
11^11
11111
"""

SCENES = {"wall_flight": WALL_FLIGHT, "lateral": LATERAL, "north_rim": NORTH_RIM}


def grid(drawing: str) -> dict:
    """`{(col, row): Cell}` for an ASCII drawing; `.` cells are left out."""
    rows = [line for line in drawing.strip("\n").splitlines()]
    return {(c, r): _LEGEND[ch]
            for r, line in enumerate(rows) for c, ch in enumerate(line)
            if ch != "."}


def layout(drawing: str):
    """A one-room layout carrying `drawing`, tile-aligned at the origin -- the
    shape `LevelIndex` reads (`bounds`, `rooms`, `corridors`)."""
    g = grid(drawing)
    px = config.TILE_PX
    cols = 1 + max(c for c, _ in g)
    rows = 1 + max(r for _, r in g)
    rect = pygame.Rect(0, 0, cols * px, rows * px)
    room = SimpleNamespace(id=0, rect=rect, grid=g)
    return SimpleNamespace(bounds=rect.copy(), rooms=[room], corridors=[])


def index(drawing: str) -> LevelIndex:
    return LevelIndex(layout(drawing))
