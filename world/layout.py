"""World data model — the types `generate_world` produces and everything else
reads.

Split out of `world/procedural.py` (W0 of `journals/world_refactor.md`) so the
generation *stages* and the *shape they build* live apart. `world.procedural`
re-exports every name here, so `from world.procedural import Room` still works.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import NamedTuple

import pygame

from game import config


class TileMeta(NamedTuple):
    """LD-2 E0: per-tile classification produced at world generation so the
    renderer -- and any later system (per-floor decor, elevation tint, footstep
    audio, minimap, drop gameplay) -- read one source of truth instead of
    re-deriving it. Room cells carry these in `Room.tile_meta` (room-relative
    keys); corridor / stair cells are synthesised by `WorldLayout.tile_at`."""
    floor: int                 # 0..3
    surface: str               # "room" | "corridor" | "stair"
    foam: bool                 # may this cell join the water shoreline (`_shore`)?
    cliff: str = ""            # "" | "top" -- a raised room's south-rim cell (starts a cliff face)
    cliff_var: str = ""        # "" | "left" | "mid" | "right" | "single" (run position)
    lip: str = ""              # "" | any of "n"/"e"/"w" concatenated -- raised non-south exposed edges
    room_id: int = -1          # owning room, or -1 for a corridor / stair cell
    # LD-3: set on the single rim cell a ramp run starts at -- "w" or "e", the
    # direction it descends. The run's own cells live in the cliff band, which
    # is outside `Room.cells`, so the renderer and the nav layer walk the run
    # out from here: `face_h` steps, one column and one row each.
    ramp: str = ""


@dataclass
class Room:
    id: int
    cell: tuple[int, int]
    rect: pygame.Rect          # world-pixel bounding box of the floor
    kind: str
    neighbors: list[int] = field(default_factory=list)
    floor: int = 0             # LD-1 elevation index (0 = ground); >0 only with WORLD_VERTICALITY
    # Room-relative (col, row) tile coords that make up the floor. Relative
    # because room rects are tile-*sized* but not world-tile-*aligned*. A plain
    # rectangular room is the full W x H set; a shaped one has corner bites.
    cells: frozenset = field(default_factory=frozenset)
    tile_meta: dict = field(default_factory=dict)   # LD-2 E0: (col,row) -> TileMeta, room-relative
    # LD-5: structure tiles this room owns that are outside `cells` -- a
    # staircase-unit landing sitting in the cliff band, a plank end-cap. Folded
    # into the room's autotiled shape so its edges connect flat. Empty unless
    # config.STRUCT_ANNEX.
    annex: frozenset = field(default_factory=frozenset)

    @property
    def tile_dims(self) -> tuple[int, int]:
        px = config.TILE_PX
        return (self.rect.width // px, self.rect.height // px)

    @property
    def center(self) -> pygame.Vector2:
        """Bounding-box centre for a plain rectangle (unchanged); for a shaped
        room, the floor centroid snapped to an occupied cell (a corner bite can
        push the bbox centre into the void)."""
        px = config.TILE_PX
        w, h = self.tile_dims
        if not self.cells or len(self.cells) == w * h:
            return pygame.Vector2(self.rect.centerx, self.rect.centery)
        ax = sum(c[0] for c in self.cells) / len(self.cells)
        ay = sum(c[1] for c in self.cells) / len(self.cells)
        col, row = min(sorted(self.cells),
                       key=lambda c: (c[0] - ax) ** 2 + (c[1] - ay) ** 2)
        return pygame.Vector2(self.rect.left + (col + 0.5) * px,
                              self.rect.top + (row + 0.5) * px)


@dataclass
class Corridor:
    a: int
    b: int
    rect: pygame.Rect          # collision span: room centre to room centre
    # Bridge edge identity (terrain). `axis` fixes the pair of end tiles the
    # renderer uses; `end_low` / `end_high` name the two edges (the low one is
    # at the smaller world x for "h", smaller y for "v"); `room_low` / `room_high`
    # are the rooms those edges butt against.
    axis: str = "h"                    # "h" -> west/east ends | "v" -> north/south
    end_low: str = "west"             # "west"  (h) | "north" (v)
    end_high: str = "east"            # "east"  (h) | "south" (v)
    room_low: int = -1
    room_high: int = -1
    # Cross-axis centre of the connection. This is selected from the rooms'
    # shared tile-aligned edge span rather than always using both room centres.
    lane: int = 0


@dataclass
class Stair:
    """LD-1: a cross-floor room link. Same role as a `Corridor` (it replaces one
    on a tree edge whose rooms differ in `floor`) but 1-2 tiles wide and tagged
    with the elevation change. `axis` is the run direction ("h" west/east, "v"
    north/south); every system treats its `rect` as a plain walkable strip with
    corridor-style clearance leniency."""
    low_room: int
    high_room: int
    rect: pygame.Rect
    axis: str = "h"
    width_tiles: int = 1
    d_floor: int = 1
    # LD-3: set on the `face_h` one-tile steps of a ramp run, so a system can
    # tell a diagonal ramp step from a plank stair. Every step of one run
    # shares its `low_room` / `high_room`, and `ramp` is the descent direction
    # ("w" or "e"). "" for an ordinary stair.
    ramp: str = ""


@dataclass
class WorldLayout:
    seed: int
    rooms: list[Room]
    corridors: list[Corridor]
    bounds: pygame.Rect
    start_id: int
    boss_id: int
    obstacles: list = field(default_factory=list)
    stairs: list = field(default_factory=list)   # LD-1; empty without WORLD_VERTICALITY

    def room(self, rid: int) -> Room:
        return self.rooms[rid]

    def walkable_rects(self) -> list[pygame.Rect]:
        return ([r.rect for r in self.rooms] + [c.rect for c in self.corridors]
                + [s.rect for s in self.stairs])

    def tile_at(self, wx: float, wy: float) -> "TileMeta | None":
        """LD-2 E0: the `TileMeta` for the tile under a world point, or `None`
        in the void. Room cells read from `Room.tile_meta` (room-relative key);
        corridor / stair cells are uniform enough to synthesise here."""
        px = config.TILE_PX
        for r in self.rooms:
            rr = r.rect
            if rr.left <= wx < rr.right and rr.top <= wy < rr.bottom:
                m = r.tile_meta.get((int((wx - rr.left) // px),
                                     int((wy - rr.top) // px)))
                if m is not None:
                    return m
        for c in self.corridors:
            if c.rect.collidepoint(wx, wy):
                f = self.rooms[c.a].floor
                return TileMeta(floor=f, surface="corridor", foam=(f == 0))
        for s in self.stairs:
            if s.rect.collidepoint(wx, wy):
                return TileMeta(floor=self.rooms[s.high_room].floor,
                                surface="stair", foam=False)
        return None

    # --- graph queries (used by tests + gameplay) -----------------
    def bfs_distances(self, source: int) -> dict[int, int]:
        dist = {source: 0}
        q = deque([source])
        while q:
            cur = q.popleft()
            for nb in self.rooms[cur].neighbors:
                if nb not in dist:
                    dist[nb] = dist[cur] + 1
                    q.append(nb)
        return dist

    def is_connected(self) -> bool:
        return len(self.bfs_distances(self.start_id)) == len(self.rooms)
