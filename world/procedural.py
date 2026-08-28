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

# Room floor size as a fraction of the chunk. `IRREGULAR_ROOMS` widens the band
# and rolls a bigger room now and then; off keeps the original single band.
_SIZE_FRAC = (0.42, 0.88)
_BIG_ROOM_FRAC = (0.78, 0.94)
_BIG_ROOM_CHANCE = 0.18
_LEGACY_SIZE_FRAC = (0.55, 0.86)

# Corner-bite ("notch") shaping: a few 2-3-cell blocks removed from the room's
# corners -> L / T / plus / stepped floors, all tile-aligned.
_NOTCH_MIN, _NOTCH_MAX = 2, 3
_MIN_ROOM_CELLS = 9

# Multi-chunk growth (W5): a combat room may extend a tile-aligned block into one
# empty adjacent chunk cell, capped at config.ROOM_SIZE_MAX_CELLS.
_MULTICHUNK_ROOM_CHANCE = 0.16
_GROW_TILES = (3, 7)

# Trees have a small collision ring (entities/obstacle.py KINDS["tree"]) so a
# denser canopy still leaves rooms walkable. After the main scatter, `_topup_trees`
# adds this fraction more trees world-wide, each seeded next to a randomly chosen
# existing tree so the extra growth thickens the groves already there rather than
# sprinkling the open floor. 0.0 disables the pass.
_TREE_DENSITY_BOOST = 0.25
# Offset of a top-up tree from its anchor tree: ~0.55 to ~1.5 tiles.
_TREE_THICKET_MIN = 36.0
_TREE_THICKET_MAX = 96.0
# Placement separation: a tree keeps only this clear of another tree (a small
# trunk gap -> groves), but the full `_OBSTACLE_GAP` off rocks / pillars / houses.
_TREE_TREE_GAP = 22
_OBSTACLE_GAP = 46

# Houses (config.TERRAIN_BUILDINGS): a circular `Obstacle` skinned per colour,
# placed off-centre in big rooms; a roomy room grows a colour-matched village
# cluster. `variant` = colour_band * 3 + (type - 1) + 1, indexing the 15-entry
# data/terrain.json `obstacle_decor.rigs["house"]` list. Keep in sync with
# entities/obstacle.py KINDS["house"]; the sprite scales off this radius.
_HOUSE_RADIUS = 31
_HOUSE_ROOM_CHANCE = 0.35
_HOUSE_MIN_ROOM_CELLS = 60
_HOUSE_GLOBAL_CAP = 7
_VILLAGE_MIN_ROOM_CELLS = 100
_VILLAGE_EXTRA = (1, 3)                 # extra buildings beyond the first
_VILLAGE_RADIUS = (3, 5)               # cluster spread, in tiles, from the first


@dataclass
class Room:
    id: int
    cell: tuple[int, int]
    rect: pygame.Rect          # world-pixel bounding box of the floor
    kind: str
    neighbors: list[int] = field(default_factory=list)
    # Room-relative (col, row) tile coords that make up the floor. Relative
    # because room rects are tile-*sized* but not world-tile-*aligned*. A plain
    # rectangular room is the full W x H set; a shaped one has corner bites.
    cells: frozenset = field(default_factory=frozenset)

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
    irregular = config.IRREGULAR_ROOMS
    rooms: list[Room] = []
    for cell in order:
        rid = occupied[cell]
        full = _cell_rect(cell, chunk)
        w = max(3 * px, round(full.width * _room_frac(rng, irregular) / px) * px)
        h = max(3 * px, round(full.height * _room_frac(rng, irregular) / px) * px)
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
        if rooms[a].cell[0] == rooms[b].cell[0]:           # vertical neighbour
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

    # --- room floor shape (tile masks) -----------------------
    # Plain rectangle by default. `IRREGULAR_ROOMS`: some combat rooms first grow
    # a block into one empty neighbour chunk (W5), then every combat room may get
    # 2-3-cell corner bites (L / T / plus / stepped).
    if irregular:
        grew = _grow_rooms(rooms, corridors, occupied, rng, start_id, boss_id)
        _carve_room_shapes(rooms, rng, start_id, boss_id)
        if grew:
            _relink_corridors(rooms, corridors)
    else:
        for room in rooms:
            room.cells = _full_cells(*room.tile_dims)

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
    union.move_ip(shift)

    # Scatter obstacles last, in the final (0,0)-based coordinate space, so the
    # corridor-doorway keep-clear rects match the world the game sees.
    obstacles = _scatter_obstacles(rooms, corridors, rng, start_id, boss_id)

    return WorldLayout(seed, rooms, corridors, union, start_id, boss_id, obstacles)


def _room_frac(rng: random.Random, irregular: bool) -> float:
    if not irregular:
        return rng.uniform(*_LEGACY_SIZE_FRAC)
    band = _BIG_ROOM_FRAC if rng.random() < _BIG_ROOM_CHANCE else _SIZE_FRAC
    return rng.uniform(*band)


def _full_cells(w: int, h: int) -> frozenset:
    return frozenset((cx, cy) for cx in range(w) for cy in range(h))


def _four_connected(cells: set) -> bool:
    if not cells:
        return False
    start = next(iter(cells))
    seen = {start}
    stack = [start]
    while stack:
        cx, cy = stack.pop()
        for dx, dy in _DIRS:
            nb = (cx + dx, cy + dy)
            if nb in cells and nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return len(seen) == len(cells)


def _borders_intact(cells: set, w: int, h: int) -> bool:
    """Every border row / column still has a cell -- so the room's bounding box
    (which the renderer + corridors use) does not shrink."""
    return (any(c[0] == 0 for c in cells) and any(c[0] == w - 1 for c in cells)
            and any(c[1] == 0 for c in cells) and any(c[1] == h - 1 for c in cells))


def _try_one_notch(cells: set, w: int, h: int, rng: random.Random) -> None:
    """Remove one 2-3-cell block from a random corner, in place, if it keeps the
    room 4-connected, above the min size, and with its bounding box intact.
    Always draws the same 3 rng values so generation stays deterministic."""
    nw = min(rng.randint(_NOTCH_MIN, _NOTCH_MAX), w // 2 - 1)
    nh = min(rng.randint(_NOTCH_MIN, _NOTCH_MAX), h // 2 - 1)
    corner_x, corner_y = rng.choice(((0, 0), (1, 0), (0, 1), (1, 1)))
    if nw < _NOTCH_MIN or nh < _NOTCH_MIN:
        return
    xs = range(nw) if corner_x == 0 else range(w - nw, w)
    ys = range(nh) if corner_y == 0 else range(h - nh, h)
    trial = cells - {(x, y) for x in xs for y in ys}
    if (len(trial) >= _MIN_ROOM_CELLS and _borders_intact(trial, w, h)
            and _four_connected(trial)):
        cells.clear()
        cells.update(trial)


def _carve_room_shapes(rooms: list[Room], rng: random.Random,
                       start_id: int, boss_id: int) -> None:
    """Bite corner blocks out of each room's cell mask. `start` / `boss` stay
    rectangular arenas; special rooms get at most one bite; combat rooms 1-3.
    Corners only (never edge midpoints) with a centre-line clearance, so a
    corridor -- which always attaches at an edge midpoint -- is never blocked."""
    for room in rooms:
        w, h = room.tile_dims
        cells = set(_full_cells(w, h))
        if room.id in (start_id, boss_id) or w < 6 or h < 6:
            room.cells = frozenset(cells)
            continue
        n = rng.randint(0, 1) if room.kind in SPECIAL_KINDS else rng.randint(1, 3)
        for _ in range(n):
            _try_one_notch(cells, w, h, rng)
        room.cells = frozenset(cells)


def _grow_rooms(rooms, corridors, occupied, rng, start_id, boss_id) -> bool:
    """W5: a combat room may extend a tile-aligned, full-width/height block into
    one **empty** adjacent chunk cell, making a large 2-chunk arena. Skips any
    growth that would overlap another room or a corridor, or push past
    `config.ROOM_SIZE_MAX_CELLS`. Runs before `_carve_room_shapes`, so the corner
    bites then apply to the grown shape. Returns whether any room grew."""
    px = config.TILE_PX
    chunk = config.CHUNK_SIZE
    grew = False
    for room in rooms:
        if room.id in (start_id, boss_id) or room.kind in SPECIAL_KINDS:
            continue
        if rng.random() >= _MULTICHUNK_ROOM_CHANCE:
            continue
        cx, cy = room.cell
        empties = [d for d in _DIRS if (cx + d[0], cy + d[1]) not in occupied]
        if not empties:
            continue
        dx, dy = rng.choice(sorted(empties))
        w, h = room.tile_dims
        depth = rng.randint(*_GROW_TILES)
        span = h if dx else w
        while depth >= 2 and len(room.cells) + depth * span > config.ROOM_SIZE_MAX_CELLS:
            depth -= 1
        if depth < 2:
            continue
        r = room.rect
        block = {
            (-1, 0): pygame.Rect(r.left - depth * px, r.top, depth * px, r.height),
            (1, 0): pygame.Rect(r.right, r.top, depth * px, r.height),
            (0, -1): pygame.Rect(r.left, r.top - depth * px, r.width, depth * px),
            (0, 1): pygame.Rect(r.left, r.bottom, r.width, depth * px),
        }[(dx, dy)]
        # must stay within the home chunk + the one target empty chunk
        reach = _cell_rect(room.cell, chunk).union(
            _cell_rect((cx + dx, cy + dy), chunk)).inflate(px, px)
        if not reach.contains(block):
            continue
        if any(block.colliderect(o.rect) for o in rooms if o is not room):
            continue
        if any(block.colliderect(c.rect) for c in corridors):
            continue

        room.rect = r.union(block)
        off_c = (r.left - room.rect.left) // px       # 0, or `depth` if grew west
        off_r = (r.top - room.rect.top) // px         # 0, or `depth` if grew north
        merged = {(c[0] + off_c, c[1] + off_r) for c in room.cells}
        bx = (block.left - room.rect.left) // px
        by = (block.top - room.rect.top) // px
        for bc in range(block.width // px):
            for br in range(block.height // px):
                merged.add((bx + bc, by + br))
        room.cells = frozenset(merged)
        grew = True
    return grew


def _relink_corridors(rooms, corridors) -> None:
    """Re-seat every corridor's collision rect in the overlap of its two (now
    possibly grown) rooms, spanning mouth-to-mouth. Axis / end labels unchanged."""
    px = config.TILE_PX
    for c in corridors:
        lo, hi = rooms[c.room_low].rect, rooms[c.room_high].rect
        if c.axis == "h":
            mid = (max(lo.top, hi.top) + min(lo.bottom, hi.bottom)) // 2
            x0, x1 = lo.right - px, hi.left + px
            c.rect = pygame.Rect(x0, mid - px // 2, max(px, x1 - x0), px)
        else:
            mid = (max(lo.left, hi.left) + min(lo.right, hi.right)) // 2
            y0, y1 = lo.bottom - px, hi.top + px
            c.rect = pygame.Rect(mid - px // 2, y0, px, max(px, y1 - y0))


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


def _corridor_doorways(rooms, corridors) -> dict:
    """For each room id, the keep-clear rectangle at every corridor mouth: the
    64 px tile where the corridor meets the room edge, plus one tile of margin.
    Obstacles are never placed inside these so a doorway is always walkable."""
    px = config.TILE_PX
    out: dict[int, list[pygame.Rect]] = {}
    for c in corridors:
        for rid in (c.a, c.b):
            room = rooms[rid].rect
            mouth = c.rect.clip(room)
            if mouth.width <= 0 or mouth.height <= 0:
                continue
            if getattr(c, "axis", "h") == "h":
                near_left = abs(mouth.left - room.left) <= abs(mouth.right - room.right)
                x = room.left if near_left else room.right - px
                door = pygame.Rect(x, mouth.top, px, mouth.height)
            else:
                near_top = abs(mouth.top - room.top) <= abs(mouth.bottom - room.bottom)
                y = room.top if near_top else room.bottom - px
                door = pygame.Rect(mouth.left, y, mouth.width, px)
            out.setdefault(rid, []).append(door.inflate(2 * px, 2 * px))
    return out


def _scatter_obstacles(rooms, corridors, rng, start_id, boss_id) -> list:
    """A few convex obstacles per room, placed on floor cells and always clear
    of every corridor doorway (so movement is never blocked). Count scales with
    a room's cell area. **Special** rooms also keep a clear central disc for
    their interaction / fight space; plain `combat` rooms fill freely -- spec 5.3.
    """
    doorways = _corridor_doorways(rooms, corridors)
    all_doors = [d for slabs in doorways.values() for d in slabs]
    px = config.TILE_PX
    out = []

    # Houses first, so the small obstacles below space themselves off a house
    # via the shared `(o.radius + 46)` check. Gated -> off is byte-identical.
    if config.TERRAIN_BUILDINGS:
        _scatter_houses(rooms, all_doors, rng, boss_id, out)

    for room in rooms:
        if room.id in (start_id, boss_id):
            continue
        special = room.kind in SPECIAL_KINDS
        base = 4 if room.kind == "elite_arena" else 2 if special else rng.randint(3, 7)
        bonus = 0 if special else len(room.cells) // 48
        density = min(base + bonus, 14)
        r = room.rect
        floor = sorted(room.cells) if room.cells else None
        # Keep the interaction / fight space clear around *both* the shaped-room
        # centroid and the bounding-box centre -- for an L / T room the two can
        # sit a cell or two apart, and a shot-blocker near either reads as
        # "middle of the room".
        centres = ((room.center.x, room.center.y), (r.centerx, r.centery))
        clear = min(r.width, r.height) * 0.24 if special else 0.0
        for _ in range(density):
            for _try in range(12):
                # Kind is drawn first so the placement gap can depend on it:
                # tree-next-to-tree keeps only `_TREE_TREE_GAP` (groves), every
                # other pairing keeps the full `_OBSTACLE_GAP`.
                kind = rng.choices(("tree", "rock", "pillar", "shrub"),
                                   weights=(4, 3, 2, 3), k=1)[0]
                if floor:
                    col, row = rng.choice(floor)
                    x = r.left + col * px + rng.uniform(px * 0.28, px * 0.72)
                    y = r.top + row * px + rng.uniform(px * 0.28, px * 0.72)
                else:
                    x = rng.uniform(r.left + 40, r.right - 40)
                    y = rng.uniform(r.top + 40, r.bottom - 40)
                if clear and any((x - mx) ** 2 + (y - my) ** 2 < clear ** 2
                                 for mx, my in centres):
                    continue
                if any(d.collidepoint(x, y) for d in all_doors):
                    continue
                if any((x - o.pos.x) ** 2 + (y - o.pos.y) ** 2
                       < (o.radius + (_TREE_TREE_GAP
                                      if kind == "tree" and o.kind == "tree"
                                      else _OBSTACLE_GAP)) ** 2
                       for o in out):
                    continue
                out.append(Obstacle(kind, x, y))
                break

    # Cosmetic decoration variant per obstacle (see world/map.py). Assigned in a
    # separate pass so placement above is byte-identical to before this existed.
    # Houses already carry a colour/type `variant` from `_scatter_houses`.
    for o in out:
        if o.kind != "house":
            o.variant = rng.randint(1, 4)

    # Global +25% tree top-up, clumped into the existing groves. Runs after the
    # variant pass so every obstacle above keeps its exact `variant` draw.
    _topup_trees(rooms, all_doors, rng, start_id, boss_id, out)

    # Bushes are non-colliding decoration now, not obstacles. They still ride the
    # weighted pick above (and consume a `variant` draw) so the `(radius + gap)`
    # spacing and every downstream RNG value stay byte-identical to when `shrub`
    # was a real obstacle; they are simply dropped from the returned list here.
    # data/terrain.json `decorations` (bush_a..d) scatters the visible bushes.
    return [o for o in out if o.kind != "shrub"]


def _topup_trees(rooms, all_doors, rng, start_id, boss_id, out) -> None:
    """Append `_TREE_DENSITY_BOOST` x the current tree count in extra trees, each
    placed 0.55-1.5 tiles from a randomly chosen existing tree (drawn uniformly
    across the whole world -> a global boost) and kept on that tree's room floor,
    clear of corridor doorways and special-room centre discs. Tree<->tree spacing
    is the tight `_TREE_TREE_GAP`; everything else keeps `_OBSTACLE_GAP`."""
    if _TREE_DENSITY_BOOST <= 0:
        return
    px = config.TILE_PX
    total = sum(1 for o in out if o.kind == "tree")
    extra = round(_TREE_DENSITY_BOOST * total)
    if extra <= 0:
        return

    # Every existing tree tagged with the room it sits in (skip start / boss --
    # the main loop never scatters there).
    tagged: list[tuple] = []
    room_clear: dict[int, tuple] = {}
    for room in rooms:
        if room.id in (start_id, boss_id) or not room.cells:
            continue
        rr = room.rect
        cellset = room.cells
        rtrees = [o for o in out if o.kind == "tree"
                  and rr.collidepoint(o.pos.x, o.pos.y)
                  and (int((o.pos.x - rr.left) // px),
                       int((o.pos.y - rr.top) // px)) in cellset]
        if not rtrees:
            continue
        special = room.kind in SPECIAL_KINDS
        room_clear[room.id] = (
            ((room.center.x, room.center.y), (rr.centerx, rr.centery)),
            min(rr.width, rr.height) * 0.24 if special else 0.0)
        for t in rtrees:
            tagged.append((t, room))
    if not tagged:
        return

    placed = 0
    for _ in range(extra * 20):
        if placed >= extra:
            break
        anchor, room = rng.choice(tagged)
        rr = room.rect
        cellset = room.cells
        centres, clear = room_clear[room.id]
        off = pygame.Vector2(rng.uniform(_TREE_THICKET_MIN, _TREE_THICKET_MAX), 0)
        off.rotate_ip(rng.uniform(0, 360))
        x, y = anchor.pos.x + off.x, anchor.pos.y + off.y
        col, row = int((x - rr.left) // px), int((y - rr.top) // px)
        if (col, row) not in cellset:
            continue
        if clear and any((x - mx) ** 2 + (y - my) ** 2 < clear ** 2
                         for mx, my in centres):
            continue
        if any(d.collidepoint(x, y) for d in all_doors):
            continue
        gap_hit = False
        for o in out:
            gap = _TREE_TREE_GAP if o.kind == "tree" else _OBSTACLE_GAP
            if (x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < (o.radius + gap) ** 2:
                gap_hit = True
                break
        if gap_hit:
            continue
        t = Obstacle("tree", x, y)
        t.variant = rng.randint(1, 4)
        out.append(t)
        tagged.append((t, room))
        placed += 1


def _scatter_houses(rooms, all_doors, rng, boss_id, out) -> None:
    """One house in ~35% of big rooms (any kind but `boss`), placed off-centre
    and clear of every corridor doorway; a roomy room grows a colour-matched
    village cluster around it. Appends `Obstacle("house", ...)` to `out`."""
    px = config.TILE_PX
    r_h = _HOUSE_RADIUS
    door_pad = int(2 * r_h)
    fat_doors = [d.inflate(door_pad, door_pad) for d in all_doors]
    placed = 0

    for room in rooms:
        if placed >= _HOUSE_GLOBAL_CAP:
            break
        if room.id == boss_id or not room.cells:
            continue
        rr = room.rect
        if min(rr.width, rr.height) < 6 * px or len(room.cells) < _HOUSE_MIN_ROOM_CELLS:
            continue
        if rng.random() >= _HOUSE_ROOM_CHANCE:
            continue

        if room.kind == "start":
            keep = max(min(rr.width, rr.height) * 0.25, r_h + 2 * px)
        elif room.kind in SPECIAL_KINDS:
            keep = max(min(rr.width, rr.height) * 0.22, r_h + 2 * px)
        else:
            keep = max(min(rr.width, rr.height) * 0.30, r_h + 2 * px)
        centres = ((room.center.x, room.center.y), (rr.centerx, rr.centery))
        cells = sorted(room.cells)
        cellset = room.cells
        colour = rng.randint(0, 4)              # one colour band per village

        def _spot(near):
            for _try in range(16):
                col, row = rng.choice(cells)
                if any((col + dc, row + dr) not in cellset
                       for dc in (-1, 0, 1) for dr in (-1, 0, 1)):
                    continue                     # keep the house comfortably inland
                x = rr.left + col * px + px * 0.5
                y = rr.top + row * px + px * 0.5
                if any((x - mx) ** 2 + (y - my) ** 2 < keep ** 2
                       for mx, my in centres):
                    continue
                if any(d.collidepoint(x, y) for d in fat_doors):
                    continue
                if near is not None:
                    lo, hi = _VILLAGE_RADIUS
                    if (x - near[0]) ** 2 + (y - near[1]) ** 2 > (hi * px) ** 2:
                        continue
                if any((x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < (2 * r_h) ** 2
                       for o in out if o.kind == "house"):
                    continue
                return x, y
            return None

        first = _spot(None)
        if first is None:
            continue
        used_types = set()
        cluster = [first]

        def _add(pos):
            nonlocal placed
            t = next((k for k in (1, 2, 3) if k not in used_types),
                     rng.randint(1, 3))
            used_types.add(t)
            h = Obstacle("house", pos[0], pos[1])
            h.variant = colour * 3 + (t - 1) + 1        # 1..15
            out.append(h)
            placed += 1

        _add(first)
        if len(room.cells) >= _VILLAGE_MIN_ROOM_CELLS:
            for _ in range(rng.randint(*_VILLAGE_EXTRA)):
                if placed >= _HOUSE_GLOBAL_CAP:
                    break
                spot = _spot(cluster[0])
                if spot is None:
                    break
                cluster.append(spot)
                _add(spot)


def _assign_kinds(rooms, rng, start_id, boss_id, dist) -> None:
    rooms[start_id].kind = "start"
    rooms[boss_id].kind = "boss"
    others = [r.id for r in rooms if r.id not in (start_id, boss_id)]
    rng.shuffle(others)
    # One of each special where room budget allows; the rest stay "combat".
    for kind, rid in zip(SPECIAL_KINDS, others):
        rooms[rid].kind = kind
