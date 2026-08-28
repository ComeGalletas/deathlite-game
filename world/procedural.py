"""Seeded procedural world generation (spec 5.2 / 5.4).

Authored chunks assembled procedurally, not per-tile noise. The world is a
lattice of chunk cells; rooms occupy single cells and are joined by short
corridors. Generation grows a *tree* from the start cell, so the connectivity
graph is always fully reachable -- "Do not generate unreachable critical rooms"
(spec 5.4).

`generate_world(seed)` is pure: the same seed and the same code produce an
identical `WorldLayout` (spec 8: "Procedural generation determinism").
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

import pygame

from entities.obstacle import Obstacle
from game import config

# Room kinds. `combat` is the filler; the rest are special locations whose
# interactions arrive in Milestone 10 -- Milestone 8 only places and labels them.
SPECIAL_KINDS = ("shrine", "treasure", "fountain", "altar", "merchant", "elite_arena")

_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass
class Room:
    id: int
    cell: tuple[int, int]
    rect: pygame.Rect          # world-pixel floor rectangle
    kind: str
    neighbors: list[int] = field(default_factory=list)

    @property
    def center(self) -> pygame.Vector2:
        return pygame.Vector2(self.rect.centerx, self.rect.centery)


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


@dataclass
class WorldLayout:
    seed: int
    rooms: list[Room]
    corridors: list[Corridor]
    bounds: pygame.Rect
    start_id: int
    boss_id: int
    obstacles: list = field(default_factory=list)

    def room(self, rid: int) -> Room:
        return self.rooms[rid]

    def walkable_rects(self) -> list[pygame.Rect]:
        return [r.rect for r in self.rooms] + [c.rect for c in self.corridors]

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


def _cell_rect(cell: tuple[int, int], chunk: int) -> pygame.Rect:
    return pygame.Rect(cell[0] * chunk, cell[1] * chunk, chunk, chunk)


def generate_world(seed: int, room_count: int | None = None) -> WorldLayout:
    rng = random.Random(seed)
    chunk = config.CHUNK_SIZE
    room_count = room_count or config.WORLD_ROOM_COUNT

    # --- grow a tree of occupied cells ---------------------------
    start_cell = (0, 0)
    occupied: dict[tuple[int, int], int] = {start_cell: 0}
    order = [start_cell]
    edges: list[tuple[int, int]] = []

    while len(occupied) < room_count:
        # frontier: free cells orthogonally adjacent to an occupied cell
        frontier = []
        for cell in order:
            for dx, dy in _DIRS:
                nb = (cell[0] + dx, cell[1] + dy)
                if nb not in occupied:
                    frontier.append((nb, cell))
        if not frontier:
            break
        new_cell, parent = rng.choice(frontier)
        new_id = len(occupied)
        occupied[new_cell] = new_id
        order.append(new_cell)
        edges.append((occupied[parent], new_id))

    # --- build rooms (random floor size within each cell) --------
    # Snapped to config.TILE_PX so the tiled renderer's cell grid covers the
    # room exactly (no clipped autotile edge). Min 3 tiles -> a real interior.
    px = config.TILE_PX
    rooms: list[Room] = []
    for cell in order:
        rid = occupied[cell]
        full = _cell_rect(cell, chunk)
        w = max(3 * px, round(full.width * rng.uniform(0.55, 0.86) / px) * px)
        h = max(3 * px, round(full.height * rng.uniform(0.55, 0.86) / px) * px)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = full.center
        rooms.append(Room(rid, cell, rect, "combat"))

    for a, b in edges:
        rooms[a].neighbors.append(b)
        rooms[b].neighbors.append(a)

    # --- corridors along each tree edge -----------------------
    # One tile wide -- rendered as a plank bridge over the water (terrain T7).
    # Each corridor records which edge is which (west/east or north/south) so the
    # renderer draws the matching end-cap tile at each mouth.
    corridors: list[Corridor] = []
    width = px
    for a, b in edges:
        ra, rb = rooms[a].rect, rooms[b].rect
        if ra.centerx == rb.centerx:                       # vertical neighbour
            (lo, lo_r), (hi, hi_r) = sorted(
                ((a, ra), (b, rb)), key=lambda t: t[1].centery)
            rect = pygame.Rect(0, 0, width, hi_r.centery - lo_r.centery)
            rect.center = (ra.centerx, (lo_r.centery + hi_r.centery) // 2)
            axis, e_lo, e_hi = "v", "north", "south"
        else:                                              # horizontal neighbour
            (lo, lo_r), (hi, hi_r) = sorted(
                ((a, ra), (b, rb)), key=lambda t: t[1].centerx)
            rect = pygame.Rect(0, 0, hi_r.centerx - lo_r.centerx, width)
            rect.center = ((lo_r.centerx + hi_r.centerx) // 2, ra.centery)
            axis, e_lo, e_hi = "h", "west", "east"
        corridors.append(Corridor(a, b, rect, axis, e_lo, e_hi, lo, hi))

    # --- assign roles ------------------------------------------
    start_id = 0
    dist = _distances(rooms, start_id)
    boss_id = max(dist, key=dist.get)
    _assign_kinds(rooms, rng, start_id, boss_id, dist)

    # --- scatter obstacles (spec 5.3) ------------------------
    obstacles = _scatter_obstacles(rooms, rng, start_id, boss_id)

    # --- bounds (union of everything + margin) ---------------
    union = rooms[0].rect.copy()
    for r in rooms:
        union.union_ip(r.rect)
    for c in corridors:
        union.union_ip(c.rect)
    union.inflate_ip(chunk, chunk)

    # Shift the whole world so bounds start at (0, 0) -- keeps camera clamp simple.
    shift = pygame.Vector2(-union.x, -union.y)
    for r in rooms:
        r.rect.move_ip(shift)
    for c in corridors:
        c.rect.move_ip(shift)
    for o in obstacles:
        o.pos += shift
    union.move_ip(shift)

    return WorldLayout(seed, rooms, corridors, union, start_id, boss_id, obstacles)


def _distances(rooms: list[Room], source: int) -> dict[int, int]:
    dist = {source: 0}
    q = deque([source])
    while q:
        cur = q.popleft()
        for nb in rooms[cur].neighbors:
            if nb not in dist:
                dist[nb] = dist[cur] + 1
                q.append(nb)
    return dist


def _scatter_obstacles(rooms, rng, start_id, boss_id) -> list:
    """A few convex obstacles per room, kept away from the room centre (spawn /
    doorway paths) so enemies do not get boxed in (spec 5.3)."""
    out = []
    for room in rooms:
        if room.id in (start_id, boss_id):
            continue
        density = 4 if room.kind == "elite_arena" else (
            2 if room.kind in ("shrine", "treasure", "fountain", "altar", "merchant")
            else rng.randint(3, 7))
        r = room.rect
        cx, cy = r.center
        clear = min(r.width, r.height) * 0.22   # keep the middle open
        for _ in range(density):
            for _try in range(8):
                x = rng.uniform(r.left + 40, r.right - 40)
                y = rng.uniform(r.top + 40, r.bottom - 40)
                if (x - cx) ** 2 + (y - cy) ** 2 < clear ** 2:
                    continue
                if any((x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < (o.radius + 46) ** 2
                       for o in out):
                    continue
                kind = rng.choices(("tree", "rock", "pillar", "shrub"),
                                   weights=(4, 3, 2, 3), k=1)[0]
                out.append(Obstacle(kind, x, y))
                break

    # Cosmetic decoration variant per obstacle (see world/map.py). Assigned in a
    # separate pass so placement above is byte-identical to before this existed.
    for o in out:
        o.variant = rng.randint(1, 4)
    return out


def _assign_kinds(rooms, rng, start_id, boss_id, dist) -> None:
    rooms[start_id].kind = "start"
    rooms[boss_id].kind = "boss"
    others = [r.id for r in rooms if r.id not in (start_id, boss_id)]
    rng.shuffle(others)
    # One of each special where room budget allows; the rest stay "combat".
    for kind, rid in zip(SPECIAL_KINDS, others):
        rooms[rid].kind = kind
