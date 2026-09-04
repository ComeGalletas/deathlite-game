"""Spawn points and resource anchors, decided once the world is final.

Phase S1 of `documentation/spawn_master_design.md`. The run used to pick a
spawn spot by trying random cells of a nearby island a dozen times
(`GameMap.offscreen_spawn_point`) with no obstacle, terrace or clearance
check, so an enemy could materialise on a rock or astride a rim. This
stage runs last in `generate_world_steps` -- after the scatter and the
unseal repair, so the obstacles and the lattice the game steers on are
what the points are tested against -- and writes `layout.spawn_points`
and `layout.resource_points`. The run reads a list.

**Enemy points, per terrace.** A ground cell's centre is a candidate when

1. it is plain ground, not a flight or the landing a flight joins
   (`scatter._flight_keepouts`);
2. it stands `margin` px inside its terrace (`inset.world_clear`), the
   body's radius plus the terrace margin every body keeps;
3. no obstacle comes within the body's radius plus a gap
   (`_SPAWN_OBSTACLE_GAP`);
4. it is outside every bridge-mouth keep-clear rect (`scatter._blocks`,
   the same test the scatter runs);
5. it keeps the clear disc the scatter keeps round a special island's
   interactable, the boss arena, and -- wider, `_SPAWN_START_CLEAR_TILES`
   -- the hero's first position;
6. the navigation lattice of the widest class says a body of that radius
   can stand on the cell (`NavGrid.passable_world`), which is also what
   ties it to everywhere else the unseal repair reached.

Every candidate is tested at the widest body in the game and again at the
small class. `settings.spawn_points_per_floor` are picked per terrace by
farthest-point sampling -- start from the candidate nearest the terrace's
centroid, then repeatedly add the one farthest from every point kept -- so
ten points cover a terrace instead of huddling. Large-class candidates are
drawn first; a floor short of the target tops up from small-only ones, and
one short of `_SPAWN_RELAX_BELOW` even at that retries with the terrace
margin alone. What is still short is logged and left short: a two-tile
upper terrace does not need ten spawn points, and the director draws from
the whole active zone.

**Resource anchors, per island.** The same candidates at the small class,
minus anything within two tiles of an enemy point or of the straight line
between two bridge mouths, preferring cells that touch a cliff or an
obstacle so a chest has something to sit against. Nothing reads them yet.

**RNG.** The only draw is the resource kind, from a private
`random.Random` keyed by seed and island, so the stage takes nothing from
the world's stream and moves no room, bridge or obstacle -- the digests of
those are unchanged with the stage on or off (`test_spawn_points`).
"""
from __future__ import annotations

import logging
import math
import random

import pygame

from game import config
from world.gen.scatter import (_blocks, _clear_radius, _corridor_doorways,
                               _doors_near, _flight_keepouts, _keep_clear_pad)
from world.gen.settings import settings_or_config
from world.gen.tuning import (
    SPECIAL_KINDS, _RESOURCE_KINDS, _RESOURCE_OFF_PATH_TILES,
    _RESOURCE_OFF_SPAWN_TILES, _RESOURCE_POINTS_PER_ISLAND, _RESOURCE_WEIGHTS,
    _SPAWN_BRIDGE_TILES, _SPAWN_EDGE_TILES, _SPAWN_MIN_SPACING_TILES,
    _SPAWN_OBSTACLE_GAP, _SPAWN_RELAX_BELOW, _SPAWN_START_CLEAR_TILES,
)
from world.layout import CLIFF, GROUND, LAKE, VOID, ResourcePoint, SpawnPoint
from world.nav.field import _NAV_CLASSES
from world.nav.lattice import NavGrid
from world.rules import inset as terrain_inset

log = logging.getLogger(__name__)

__all__ = ["place_points", "body_radii"]


def body_radii() -> tuple[float, float]:
    """`(small, large)`: the body radius of the narrowest and the widest
    navigation class, read from the classes the game steers on rather than
    restated here."""
    radii = sorted(float(c[3]) for c in _NAV_CLASSES)
    return radii[0], radii[-1]


def _widest_cell() -> int:
    return int(max(_NAV_CLASSES, key=lambda c: c[3])[1])


class _Island:
    """Everything one island's candidates are tested against, gathered once."""

    def __init__(self, layout, room, grid, doors, keepouts, pad, px) -> None:
        self.room = room
        self.grid = grid
        self.px = px
        r = room.rect
        self.doors = _doors_near(doors, r, pad)
        self.keepouts = [k for k in keepouts if k.colliderect(r)]
        # Obstacles that could come within reach of a point on this island.
        reach = max((float(o.radius) for o in layout.obstacles), default=0.0)
        box = r.inflate(2 * reach + 128, 2 * reach + 128)
        self.obstacles = [o for o in layout.obstacles
                          if box.collidepoint(o.pos.x, o.pos.y)]
        # Discs kept clear: the scatter's own (interactable / arena / hero),
        # and the wider one round the hero's first position.
        self.clear = []
        clear = _clear_radius(room, layout.start_id, layout.boss_id)
        centres = ((room.center.x, room.center.y), (r.centerx, r.centery))
        if room.id == layout.start_id:
            clear = max(clear, _SPAWN_START_CLEAR_TILES * px)
        if clear:
            self.clear = [(cx, cy, clear) for cx, cy in centres]

    # --- the six tests ------------------------------------------------
    def cell_centre(self, col: int, row: int) -> tuple[float, float]:
        r = self.room.rect
        return (r.left + (col + 0.5) * self.px, r.top + (row + 0.5) * self.px)

    def on_keepout(self, x: float, y: float) -> bool:
        return any(k.collidepoint(x, y) for k in self.keepouts)

    def obstacle_free(self, x: float, y: float, radius: float) -> bool:
        for o in self.obstacles:
            reach = radius + float(o.radius) + _SPAWN_OBSTACLE_GAP
            if (x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < reach * reach:
                return False
        return True

    def in_clear_disc(self, x: float, y: float) -> bool:
        return any((x - cx) ** 2 + (y - cy) ** 2 < rr * rr
                   for cx, cy, rr in self.clear)

    def fits(self, x: float, y: float, radius: float, margin: float) -> bool:
        return (terrain_inset.world_clear(self.room, x, y, margin)
                and self.obstacle_free(x, y, radius)
                and not _blocks(self.doors, x, y, radius)
                and self.grid.passable_world(x, y, radius))


def _floors(room) -> dict[int, list[tuple[int, int]]]:
    """`level -> [(col, row)]` of the plain ground cells, per terrace."""
    out: dict[int, list] = {}
    for pos, cell in room.grid.items():
        if cell.kind == GROUND:
            out.setdefault(cell.level, []).append(pos)
    for cells in out.values():
        cells.sort()
    return out


def _farthest_first(cands: list, keep: list, target: int, min_gap: float) -> None:
    """Farthest-point sampling: extend `keep` from `cands` until it holds
    `target` points, each time taking the candidate farthest from every
    point already kept. `keep` may start non-empty (a top-up pass), and a
    candidate closer than `min_gap` to a kept point is never taken."""
    if not cands:
        return
    gap_sq = min_gap * min_gap
    # Distance from each candidate to the nearest kept point.
    if keep:
        near = [min((c[0] - k[0]) ** 2 + (c[1] - k[1]) ** 2 for k in keep)
                for c in cands]
    else:
        # Seed from the centroid: the first point sits in the middle of the
        # terrace and the rest fan out from it.
        cx = sum(c[0] for c in cands) / len(cands)
        cy = sum(c[1] for c in cands) / len(cands)
        i = min(range(len(cands)),
                key=lambda k: (cands[k][0] - cx) ** 2 + (cands[k][1] - cy) ** 2)
        keep.append(cands[i])
        near = [(c[0] - cands[i][0]) ** 2 + (c[1] - cands[i][1]) ** 2
                for c in cands]
    while len(keep) < target:
        i = max(range(len(cands)), key=near.__getitem__)
        if near[i] < gap_sq:
            break
        k = cands[i]
        keep.append(k)
        for j, c in enumerate(cands):
            d = (c[0] - k[0]) ** 2 + (c[1] - k[1]) ** 2
            if d < near[j]:
                near[j] = d


def _near_coast(room, col: int, row: int, tiles: int) -> bool:
    """Is water -- the sea past the island's edge, or a lake -- within
    `tiles` of the cell? Cliffs are land: a terrace wall is not a coast."""
    grid = room.grid
    for dr in range(-tiles, tiles + 1):
        for dc in range(-tiles, tiles + 1):
            c = grid.get((col + dc, row + dr))
            if c is None or c.kind in (LAKE, VOID):
                return True
    return False


def _near_rect(x: float, y: float, rects, reach: float) -> bool:
    for r in rects:
        cx = min(max(x, r.left), r.right)
        cy = min(max(y, r.top), r.bottom)
        if (x - cx) ** 2 + (y - cy) ** 2 <= reach * reach:
            return True
    return False


def _tags(island: _Island, layout, col: int, row: int, x: float, y: float,
          level: int) -> frozenset:
    room = island.room
    tags = set()
    if level > 0:
        tags.add("upper")
    if room.id == layout.boss_id:
        tags.add("boss")
    if _near_coast(room, col, row, _SPAWN_EDGE_TILES):
        tags.add("edge")
    if _near_rect(x, y, island.doors, _SPAWN_BRIDGE_TILES * island.px):
        tags.add("bridge")
    return frozenset(tags)


def _island_spawn_points(layout, island: _Island, target: int,
                         small: float, large: float, body: float) -> list:
    room, px = island.room, island.px
    out: list[SpawnPoint] = []
    min_gap = _SPAWN_MIN_SPACING_TILES * px
    for level, cells in sorted(_floors(room).items()):
        def candidates(radius: float, margin: float) -> list:
            found = []
            for col, row in cells:
                x, y = island.cell_centre(col, row)
                if island.on_keepout(x, y) or island.in_clear_disc(x, y):
                    continue
                if island.fits(x, y, radius, margin):
                    found.append((x, y, col, row))
            return found

        big = candidates(large, large + body)
        keep: list = []
        _farthest_first(big, keep, target, min_gap)
        big_set = set(keep)
        if len(keep) < target:
            _farthest_first(candidates(small, small + body), keep, target, min_gap)
        if len(keep) < _SPAWN_RELAX_BELOW:
            # A cramped terrace: the margin alone, so the widest bodies
            # still fit between the rocks but may stand nearer the rim.
            _farthest_first(candidates(small, body), keep, target, min_gap)
        if len(keep) < target:
            log.info("seed %d island %d floor %d seats %d of %d spawn points",
                     layout.seed, room.id, level, len(keep), target)
        for x, y, col, row in keep:
            out.append(SpawnPoint(
                room.id, level, x, y,
                "large" if (x, y, col, row) in big_set else "small",
                _tags(island, layout, col, row, x, y, level)))
    return out


def _mouth_segments(island: _Island) -> list:
    """The straight lines between this island's bridge mouths -- the
    routes a player crossing it walks."""
    mouths = [pygame.Vector2(d.center) for d in island.doors]
    return [(a, b) for i, a in enumerate(mouths) for b in mouths[i + 1:]]


def _seg_dist_sq(p: pygame.Vector2, a: pygame.Vector2, b: pygame.Vector2) -> float:
    ab = b - a
    ll = ab.length_squared()
    if ll < 1e-9:
        return (p - a).length_squared()
    t = max(0.0, min(1.0, (p - a).dot(ab) / ll))
    return (p - (a + ab * t)).length_squared()


def _against_something(island: _Island, col: int, row: int, x: float, y: float) -> bool:
    """Does the cell touch a cliff, or stand within a tile and a half of an
    obstacle? A chest against a wall reads as placed; one in open ground
    reads as dropped."""
    grid = island.room.grid
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            c = grid.get((col + dc, row + dr))
            if c is not None and c.kind == CLIFF:
                return True
    reach = island.px * 1.5
    return any((x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < reach * reach
               for o in island.obstacles)


def _island_resource_points(layout, island: _Island, spawns: list,
                            small: float, body: float, rng: random.Random) -> list:
    room, px = island.room, island.px
    off_spawn = (_RESOURCE_OFF_SPAWN_TILES * px) ** 2
    off_path = (_RESOURCE_OFF_PATH_TILES * px) ** 2
    segs = _mouth_segments(island)
    spawn_xy = [(s.x, s.y) for s in spawns]
    preferred, plain = [], []
    for level, cells in sorted(_floors(room).items()):
        for col, row in cells:
            x, y = island.cell_centre(col, row)
            if island.on_keepout(x, y) or island.in_clear_disc(x, y):
                continue
            if not island.fits(x, y, small, small + body):
                continue
            if any((x - sx) ** 2 + (y - sy) ** 2 < off_spawn for sx, sy in spawn_xy):
                continue
            p = pygame.Vector2(x, y)
            if any(_seg_dist_sq(p, a, b) < off_path for a, b in segs):
                continue
            entry = (x, y, col, row, level)
            (preferred if _against_something(island, col, row, x, y)
             else plain).append(entry)
    keep: list = []
    gap = _SPAWN_MIN_SPACING_TILES * px
    _farthest_first(preferred, keep, _RESOURCE_POINTS_PER_ISLAND, gap)
    if len(keep) < _RESOURCE_POINTS_PER_ISLAND:
        _farthest_first(plain, keep, _RESOURCE_POINTS_PER_ISLAND, gap)
    return [ResourcePoint(room.id, level, x, y,
                          rng.choices(_RESOURCE_KINDS, weights=_RESOURCE_WEIGHTS, k=1)[0])
            for x, y, _col, _row, level in keep]


def place_points(layout, settings=None):
    """Fill `layout.spawn_points` and `layout.resource_points`, one island at
    a time; a generator that yields the island just done, so the loading
    screen can keep drawing between them. Idempotent: it starts from empty
    lists each call."""
    settings = settings_or_config(settings)
    target = int(settings.spawn_points_per_floor)
    layout.spawn_points = []
    layout.resource_points = []
    if target <= 0 or not layout.rooms:
        return
    px = config.TILE_PX
    small, large = body_radii()
    body = terrain_inset.body_inset()
    # One lattice at the widest class: `passable` reads a per-cell clearance,
    # so both radii are asked of the same grid.
    grid = NavGrid(layout, layout.obstacles, _widest_cell())
    doorways = _corridor_doorways(layout.rooms, layout.corridors)
    doors = [d for slabs in doorways.values() for d in slabs]
    keepouts = _flight_keepouts(layout.rooms)
    pad = _keep_clear_pad()
    for room in layout.rooms:
        island = _Island(layout, room, grid, doors, keepouts, pad, px)
        spawns = _island_spawn_points(layout, island, target, small, large, body)
        rng = random.Random(layout.seed * 7919 + room.id)
        resources = _island_resource_points(layout, island, spawns, small, body, rng)
        layout.spawn_points.extend(spawns)
        layout.resource_points.extend(resources)
        yield room
