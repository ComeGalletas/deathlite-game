"""World data model -- the types `generate_world` produces and everything else
reads. `world.procedural` re-exports every name here, so
`from world.procedural import Room` still works.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import NamedTuple

import pygame

from game import config


class Cell(NamedTuple):
    """One tile of a room's **height map**. Generation emits a grid of these
    -- the machine-readable form of the ASCII layouts in the level-design
    journal -- and rendering is a pure function of the grid.

        `=` ground   walkable surface at `level`
        `#` cliff    the wall holding up `level`; not walkable
        `0` vstair   straight N/S flight, `level` down to `level - drop`
        `>` ewstair  east/west flight, same span, `tag` is the descent side
        `~` lake     inland water inside a terrace; not walkable
        ` ` void     open sea / nothing

    `level` is always the **upper** surface a cell belongs to: for a cliff or a
    stair that is the terrace it hangs from. `row` indexes a cliff / stair cell
    within its own vertical stack (0 = the topmost), so the renderer can pick
    the top / body / bottom art without re-deriving the stack.
    """
    kind: str
    level: int = 0
    drop: int = 0          # cliff / stair: levels spanned (1 or 2)
    row: int = 0           # cliff / stair: index down the stack, 0 = top
    tag: str = ""          # stair: "grass" / "rock", or the "w" / "e" descent


GROUND, CLIFF, VSTAIR, EWSTAIR, LAKE, VOID = (
    "ground", "cliff", "vstair", "ewstair", "lake", "void")
WALKABLE_KINDS = frozenset({GROUND, VSTAIR, EWSTAIR})


class TileMeta(NamedTuple):
    """Per-tile classification produced at world generation so the renderer
    -- and any later system (per-floor decor, footstep audio, minimap) --
    read one source of truth instead of re-deriving it. Room cells carry
    these in `Room.tile_meta` (room-relative keys); bridge cells are
    synthesised by `WorldLayout.tile_at`."""
    floor: int                 # the terrace level
    surface: str               # "room" | "corridor"
    foam: bool                 # may this cell join the water shoreline (`_shore`)?
    room_id: int = -1          # owning room, or -1 for a bridge cell
    # A flight cell: "s" for a straight north/south flight, "w" / "e" for an
    # east/west one, the direction it descends. "" on ground.
    ramp: str = ""


@dataclass
class Room:
    id: int
    cell: tuple[int, int]
    rect: pygame.Rect          # world-pixel bounding box of the island; tile-aligned
    kind: str
    neighbors: list[int] = field(default_factory=list)
    floor: int = 0             # the island's base level; always 0 today
    # Room-relative (col, row) tiles a body may stand on: the walkable subset
    # of `grid`. Collision and navigation read this and need to know nothing
    # about levels.
    cells: frozenset = field(default_factory=frozenset)
    tile_meta: dict = field(default_factory=dict)   # (col,row) -> TileMeta, room-relative
    # The island's height map, `(col, row) -> Cell`, room-relative. The source
    # of truth for the room's shape, elevation and flights; `cells` is derived
    # from it and `floor` is its base level.
    grid: dict = field(default_factory=dict)
    # The island's *shape* type -- "volcanic", "small", "boss". Separate from
    # `kind`, which says what happens on it: a shrine can stand on a small
    # island. Chosen once in `assign_topography` and read by the room sizing,
    # the coastline and the terrace count, so all three agree.
    topography: str = ""
    # `{level: sheet}` -- which ground tileset each terrace wears. Decided at
    # generation (`world/gen/biomes.py`), not at bake, because the obstacle
    # scatter reads the biome as well as the tile painter does, and one
    # authority is the point.
    palette: dict = field(default_factory=dict)
    # The terrace inset field (`world/rules/inset.py`): distance, per 8 px sample,
    # from that point to the nearest floor of a different level. Built once
    # when the grid is final and before anything is baked, scattered or
    # spawned, so every later stage asks one authority how far inside its own
    # terrace a point stands. `None` where the island has no level changes.
    inset: object = None

    @property
    def tile_dims(self) -> tuple[int, int]:
        px = config.TILE_PX
        return (self.rect.width // px, self.rect.height // px)

    @property
    def center(self) -> pygame.Vector2:
        """The floor centroid snapped to an occupied cell -- the coastline can
        put the bounding-box centre in a lake or over the sea. A room with no
        mask yet (or a full one) answers its bounding-box centre."""
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
    """A plank bridge between two islands. One tile wide; always at sea
    level, because a bridge only ever lands on a beach."""
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
    # Cross-axis centre of the connection, chosen on the two islands'
    # beaches by `_seat_corridors`.
    lane: int = 0


class SpawnPoint(NamedTuple):
    """A spot an enemy may materialise on, decided at generation
    (`world/gen/spawnpoints.py`) so the run never searches for one.

    `clearance` is the widest navigation class that fits: `"large"` seats
    any body in the game, `"small"` only the common ones. `tags` describe
    the spot for the placement rules that come later: `"upper"` (a terrace
    above sea level), `"edge"` (near the coast), `"bridge"` (near a bridge
    mouth), `"boss"` (in the boss island, for the fight's adds only).
    """
    room_id: int
    floor: int
    x: float
    y: float
    clearance: str = "large"
    tags: frozenset = frozenset()

    @property
    def pos(self) -> pygame.Vector2:
        return pygame.Vector2(self.x, self.y)


class ResourcePoint(NamedTuple):
    """An anchor for something to be found rather than fought -- a chest,
    a breakable, an ambient pickup. Emitted at generation next to the spawn
    points; nothing consumes them yet. `kind` is a hint drawn per point:
    `"chest"`, `"breakable"` or `"ambient"`."""
    room_id: int
    floor: int
    x: float
    y: float
    kind: str = "ambient"

    @property
    def pos(self) -> pygame.Vector2:
        return pygame.Vector2(self.x, self.y)


@dataclass
class WorldLayout:
    seed: int
    rooms: list[Room]
    corridors: list[Corridor]
    bounds: pygame.Rect
    start_id: int
    boss_id: int
    obstacles: list = field(default_factory=list)
    # Decided last, once the obstacles are final (`world/gen/spawnpoints.py`).
    spawn_points: list = field(default_factory=list)
    resource_points: list = field(default_factory=list)

    def room(self, rid: int) -> Room:
        return self.rooms[rid]

    def walkable_rects(self) -> list[pygame.Rect]:
        return [r.rect for r in self.rooms] + [c.rect for c in self.corridors]

    def tile_at(self, wx: float, wy: float) -> "TileMeta | None":
        """The `TileMeta` for the tile under a world point, or `None` in the
        void. Room cells read from `Room.tile_meta` (room-relative key);
        bridge cells are uniform enough to synthesise here."""
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
