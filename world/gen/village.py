"""The village pass (HI-2): what stands on a human island.

`world/gen/scatter.py` passes over a `village` room and this decides
everything on it instead. The settlement is designed round a centre on a
north axis: the forge in the middle, the heal zone directly above it, the
town hall (the monastery) directly above that; the houses clustered on
adjacent slots of the ring round the forge; a military group -- barracks,
tower and, at the first bridge, the archery -- in a row beside the road in
from every bridge; a fenced sheep pen on the side of the island farthest
from the bridges; and the trees, rocks and clutter kept outside the
cluster, spread round it. Every
building is an `Obstacle` of its own kind (the houses reuse `house`), so
collision, navigation, the unseal repair, the ghost pass and the skins need
nothing new; a wide building is a *compound* of circles -- one primary that
carries the art plus the `satellites` its `terrain.json` entry declares,
which collide but are never drawn (`Obstacle.skin`).

What the run needs to know afterwards -- where the forge and the heal are,
which buildings stand where, where the guards post and where the pen is --
comes back as a `Village` record on the layout, so the interactables and
the NPCs (HI-3) read one source rather than sifting the obstacle list.

Colours are drawn from a shuffled cycle: no colour repeats until every one
has appeared, and there is deliberately no colour band per village.

Runs after the scatter and before the unseal repair, so a building that
seals the road is taken back like any other obstacle. Its RNG is private --
keyed by seed and island, the way the bridges and the palettes do it -- so
the pass draws nothing from the world stream: the tree top-up can change
and the village stays where it was, which `test_obstacle_families` pins.
The geometry rules -- every circle on `GROUND` with a tile of coast in
hand, clear of every bridge-mouth keep-clear rect, clear of each other, and
off the lanes from each bridge mouth to the forge -- are the same ones the
scatter keeps, so stepping off a bridge is never into a wall.
"""
from __future__ import annotations

import math
import random

import pygame

from entities.obstacle import KINDS, Obstacle, satellites_of
from game import config
from world.gen.scatter import _blocks, _corridor_doorways
from world.gen.settings import settings_or_config
from world.gen.tuning import (
    VILLAGE_KIND, _V_CLUSTER_RADIUS, _V_COAST_PAD, _V_GAP, _V_HALL_ABOVE,
    _V_HEAL_NORTH, _V_HEAL_RADIUS, _V_HOUSES, _V_HOUSE_LINK, _V_LANE_HALF,
    _V_MILITARY_FLANK,
    _V_MILITARY_INLAND, _V_MILITARY_PITCH, _V_PEN_DIST, _V_PEN_H, _V_PEN_SCALE,
    _V_PEN_W,
    _V_RING, _V_SCATTER_GAP, _V_SCATTER_SCALE, _V_SCATTER_TREES, _V_SLOTS,
    _GRID_OBSTACLES_PER_1000,
)
from world.layout import GROUND, Village
from world.rules import biome as biomes

# The order of the colour rig lists in `terrain.json` (`obstacle_decor.rigs`):
# a building's `variant` is its index here plus one, a house's is
# `colour * 3 + type + 1` over the fifteen house rigs.
COLOURS = ("blue", "red", "yellow", "purple", "black")
# The fence rigs, in `obstacle_decor.rigs["fence"]` order; `variant` indexes it.
FENCE_SLOTS = ("nw", "n1", "n2", "ne", "w", "e", "sw", "s_gate_l", "s_gate_r", "se")

__all__ = ["place_villages", "COLOURS", "FENCE_SLOTS"]


def place_villages(rooms, corridors, seed: int, settings=None) -> tuple[list, list]:
    """`(obstacles, villages)` for every village island. `obstacles` go on
    the layout's list after the scatter's; `villages` is one `Village` per
    island, in island order. Draws nothing from the world stream."""
    s = settings_or_config(settings)
    doorways = _corridor_doorways(rooms, corridors)
    out: list = []
    villages: list = []
    for room in rooms:
        if room.kind != VILLAGE_KIND:
            continue
        rng = random.Random(f"{seed}:village:{room.id}")
        site = _Site(room, doorways.get(room.id, []), rng)
        village = _lay_out(site, s.town_hall)
        out.extend(site.placed)
        villages.append(village)
    return out, villages


class _Cycle:
    """A shuffled bag of `n` indices, refilled when empty: every value comes
    out once before any comes out twice."""

    def __init__(self, rng, n: int) -> None:
        self.rng, self.n, self.bag = rng, n, []

    def next(self) -> int:
        if not self.bag:
            self.bag = list(range(self.n))
            self.rng.shuffle(self.bag)
        return self.bag.pop()


def _seg_dist(x: float, y: float, a: pygame.Vector2, b: pygame.Vector2) -> float:
    """Distance from `(x, y)` to the segment `a`-`b`."""
    ab = b - a
    L = ab.length_squared()
    if L < 1e-9:
        return math.hypot(x - a.x, y - a.y)
    t = max(0.0, min(1.0, ((x - a.x) * ab.x + (y - a.y) * ab.y) / L))
    return math.hypot(x - (a.x + ab.x * t), y - (a.y + ab.y * t))


def _circles(kind: str, x: float, y: float) -> list:
    """The collision circles a building of `kind` stands on at `(x, y)`:
    the primary first, then its satellites, as `(x, y, radius)`."""
    out = [(x, y, float(KINDS[kind][0]))]
    for dx, dy, r in satellites_of(kind):
        out.append((x + dx, y + dy, r))
    return out


class _Site:
    """One island's placement state: what stands where so far, and the
    tests every new thing has to pass."""

    def __init__(self, room, doors, rng) -> None:
        self.room = room
        self.grid = room.grid
        self.rect = room.rect
        self.px = config.TILE_PX
        self.rng = rng
        self.doors = list(doors)
        self.placed: list[Obstacle] = []
        self.reserved: list[tuple[float, float, float]] = []   # (x, y, r): the heal prop
        self.lanes: list[tuple[pygame.Vector2, pygame.Vector2]] = []

    # --- coordinates --------------------------------------------------
    def tile_centre(self, col: int, row: int) -> tuple[float, float]:
        return (self.rect.left + (col + 0.5) * self.px,
                self.rect.top + (row + 0.5) * self.px)

    def cell_of(self, x: float, y: float) -> tuple[int, int]:
        return (int((x - self.rect.left) // self.px),
                int((y - self.rect.top) // self.px))

    def snap(self, x: float, y: float) -> tuple[float, float]:
        return self.tile_centre(*self.cell_of(x, y))

    # --- the tests ----------------------------------------------------
    def ground_disc(self, x: float, y: float, r: float) -> bool:
        """Every tile the square round the disc touches is plain ground."""
        c0, r0 = self.cell_of(x - r, y - r)
        c1, r1 = self.cell_of(x + r, y + r)
        for c in range(c0, c1 + 1):
            for rr in range(r0, r1 + 1):
                cell = self.grid.get((c, rr))
                if cell is None or cell.kind != GROUND:
                    return False
        return True

    def free(self, x: float, y: float, r: float, gap: float) -> bool:
        for o in self.placed:
            if (x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < (r + o.radius + gap) ** 2:
                return False
        for rx, ry, rr in self.reserved:
            if (x - rx) ** 2 + (y - ry) ** 2 < (r + rr + gap) ** 2:
                return False
        return True

    def off_lanes(self, x: float, y: float, r: float) -> bool:
        keep = r + _V_LANE_HALF * self.px
        return all(_seg_dist(x, y, a, b) >= keep for a, b in self.lanes)

    def circle_ok(self, x: float, y: float, r: float, lane: bool) -> bool:
        return (self.ground_disc(x, y, r + _V_COAST_PAD)
                and not _blocks(self.doors, x, y, r)
                and self.free(x, y, r, _V_GAP)
                and (not lane or self.off_lanes(x, y, r)))

    def fits(self, kind: str, x: float, y: float, lane: bool = True) -> bool:
        return all(self.circle_ok(cx, cy, cr, lane)
                   for cx, cy, cr in _circles(kind, x, y))

    # --- placing ------------------------------------------------------
    def add(self, kind: str, x: float, y: float, variant: int = 1) -> Obstacle:
        """One building: the primary circle carries the skin, the satellites
        collide only."""
        circles = _circles(kind, x, y)
        primary = Obstacle(kind, x, y, variant)
        self.placed.append(primary)
        for cx, cy, cr in circles[1:]:
            sat = Obstacle(kind, cx, cy, variant)
            sat.radius = cr
            sat.skin = False
            self.placed.append(sat)
        return primary

    def ring(self, kind: str, d_range, angle: float, spread: float,
             lane: bool = True):
        """The first tile centre that fits `kind`, searched outward from
        `angle` (radians, screen y down) over `d_range` tiles from the forge:
        nearest distance first, then the angle fanned out to `spread` each way.
        `None` when nothing in the fan fits."""
        fx, fy = self.forge
        lo, hi = d_range
        d = lo
        while d <= hi + 1e-9:
            k = 0
            while k * 0.25 <= spread + 1e-9:
                for sign in ((1,) if k == 0 else (1, -1)):
                    a = angle + sign * k * 0.25
                    x, y = self.snap(fx + math.cos(a) * d * self.px,
                                     fy + math.sin(a) * d * self.px)
                    if self.fits(kind, x, y, lane):
                        return x, y
                k += 1
            d += 0.5
        return None


def _lay_out(site: _Site, town_hall: bool) -> Village:
    rng, px = site.rng, site.px
    room = site.room
    colours = _Cycle(rng, len(COLOURS))
    buildings: list = []

    # 1. The forge, at the walkable centroid -- or the nearest cell to it
    #    that takes the forge *and leaves the axis room*: ground for the
    #    heal two tiles north and for the hall four to five and a half
    #    tiles north. A centroid a few tiles off the north coast would
    #    otherwise put the hall in the sea, and the whole village slides
    #    south a little instead.
    c = room.center
    cells = sorted(room.cells, key=lambda p: (site.tile_centre(*p)[0] - c.x) ** 2
                   + (site.tile_centre(*p)[1] - c.y) ** 2)

    mouths = [pygame.Vector2(d.center) for d in site.doors]

    def axis_room(x, y):
        # Ground for the heal straight above the forge, and for the hall's
        # whole footprint (satellites included) straight above the heal, on
        # the same x -- off the roads that would run from each bridge to a
        # forge here, since a road down the axis is the one thing the hall
        # cannot step aside from.
        hx, hy = site.snap(x, y - _V_HEAL_NORTH * px)
        if not site.ground_disc(hx, hy, _V_HEAL_RADIUS):
            return False
        cand = pygame.Vector2(x, y)
        for d in (_V_HALL_ABOVE[0], _V_HALL_ABOVE[0] + 0.5, _V_HALL_ABOVE[0] + 1.0,
                  _V_HALL_ABOVE[1]):
            mx, my = site.snap(hx, hy - d * px)
            if not site.fits("monastery", mx, my, lane=False):
                continue
            keep = _V_LANE_HALF * px
            if all(_seg_dist(cx, cy, m, cand) >= cr + keep
                   for cx, cy, cr in _circles("monastery", mx, my) for m in mouths):
                return True
        return False

    forge = next((site.tile_centre(*p) for p in cells[:120]
                  if site.fits("forge", *site.tile_centre(*p), lane=False)
                  and axis_room(*site.tile_centre(*p))), None)
    if forge is None:
        forge = next((site.tile_centre(*p) for p in cells[:120]
                      if site.fits("forge", *site.tile_centre(*p), lane=False)),
                     site.snap(c.x, c.y))
    site.forge = forge
    site.add("forge", *forge)
    buildings.append(("forge", *forge))
    fvec = pygame.Vector2(forge)

    # 2. The roads: one lane from each bridge mouth to the forge, kept clear
    #    of everything but the guards that flank it.
    dirs = []
    for m in mouths:
        site.lanes.append((m, fvec))
        v = fvec - m
        if v.length_squared() > 1e-6:
            dirs.append(v.normalize())

    # 3. The north axis. The heal zone stands `_V_HEAL_NORTH` tiles due
    #    north of the forge -- an interactable, not an obstacle, so it only
    #    reserves its disc -- and the town hall (the monastery) due north of
    #    that. Either slides up the axis a tile or two if its spot is taken.
    north = -math.pi / 2
    heal = None
    for up in (0.0, 1.0, 2.0):
        x, y = site.snap(forge[0], forge[1] - (_V_HEAL_NORTH + up) * px)
        if site.circle_ok(x, y, _V_HEAL_RADIUS, lane=False):
            heal = (x, y)
            break
    if heal is None:
        heal = (forge[0], forge[1] - _V_HEAL_NORTH * px)
    site.reserved.append((*heal, _V_HEAL_RADIUS))
    if town_hall:
        # Straight above the heal on the same x, sliding only up. The forge
        # was sited so that this fits (`axis_room`); the fall-back walk is
        # for a forge that took the plain fall-back itself.
        pos = None
        for d in (_V_HALL_ABOVE[0], _V_HALL_ABOVE[0] + 0.5, _V_HALL_ABOVE[0] + 1.0,
                  _V_HALL_ABOVE[1], _V_HALL_ABOVE[1] + 0.5):
            x, y = site.snap(heal[0], heal[1] - d * px)
            if site.fits("monastery", x, y, lane=True):
                pos = (heal[0], y)
                break
        if pos is not None:
            site.add("monastery", *pos, variant=colours.next() + 1)
            buildings.append(("monastery", *pos))

    # 4. The houses, clustered: a walk round the ring, off the axis (the
    #    north three slots of eight are the hall's), starting at a random
    #    slot and going one way, each house placed within `_V_HOUSE_LINK`
    #    tiles of the one before it. A spot that will not take a house is
    #    stepped past, never skipped a whole slot, so the cluster stays one
    #    piece. Close together on purpose.
    step = 2 * math.pi / _V_SLOTS
    free = [k for k in range(_V_SLOTS)
            if abs(((k * step - north + math.pi) % (2 * math.pi)) - math.pi)
            > step * 1.5 - 1e-9]                     # E, SE, S, SW, W
    n = rng.randint(*_V_HOUSES)
    a = rng.choice(free) * step + rng.uniform(-0.2, 0.2)
    turn = rng.choice((1, -1))
    last = None
    placed_houses = 0
    swept = 0.0
    while placed_houses < n and swept < 2 * math.pi:
        off_axis = (abs(((a - north + math.pi) % (2 * math.pi)) - math.pi)
                    > step * 1.5 - 1e-9)
        pos = None
        if off_axis:
            for d in (_V_RING[0], _V_RING[0] + 0.5, _V_RING[0] + 1.0, _V_RING[1]):
                x, y = site.snap(forge[0] + math.cos(a) * d * px,
                                 forge[1] + math.sin(a) * d * px)
                if site.fits("house", x, y) and (
                        last is None
                        or math.hypot(x - last[0], y - last[1]) <= _V_HOUSE_LINK * px):
                    pos = (x, y)
                    break
        if pos is not None:
            colour = colours.next()
            site.add("house", *pos, variant=colour * 3 + rng.randint(0, 2) + 1)
            buildings.append(("house", *pos))
            last = pos
            placed_houses += 1
            a += turn * 0.4
            swept += 0.4
        else:
            a += turn * 0.15
            swept += 0.15

    # 5. The military, grouped: a row beside the road in from every bridge
    #    -- the barracks nearest the road, the tower beyond it, and at the
    #    first bridge the archery beyond that -- on whichever side of the
    #    road seats more of them. They are the only buildings allowed this
    #    near a lane, and they still keep off it by their radius.
    posts: list = []
    for i, (m, d) in enumerate(zip(mouths, dirs)):
        perp = pygame.Vector2(-d.y, d.x)
        group = ["barracks", "tower"] + (["archery"] if i == 0 else [])
        best: list = []
        for side in (perp, -perp):
            row: list = []
            for j, kind in enumerate(group):
                found = None
                for inland in (0.0, 1.0, 2.0, -1.0):
                    flank = _V_MILITARY_FLANK + j * _V_MILITARY_PITCH
                    p = m + d * (_V_MILITARY_INLAND + inland) * px + side * flank * px
                    x, y = site.snap(p.x, p.y)
                    if (site.fits(kind, x, y, lane=True)
                            and all(math.hypot(x - qx, y - qy) > 0.5 * px
                                    for _k, qx, qy in row)):
                        found = (kind, x, y)
                        break
                if found is not None:
                    row.append(found)
            if len(row) > len(best):
                best = row
        # The trial rows were only tested, never placed; place the winner.
        pair = []
        for kind, x, y in best:
            if not site.fits(kind, x, y, lane=True):
                continue
            site.add(kind, x, y, variant=colours.next() + 1)
            buildings.append((kind, x, y))
            if kind in ("barracks", "tower"):
                pair.append((x, y))
        if pair:
            posts.append(tuple(pair))

    # 6. The sheep pen, on the side of the island the bridges are not.
    back = -sum(dirs, pygame.Vector2()) if dirs else pygame.Vector2()
    if back.length_squared() < 1e-6:
        back = (pygame.Vector2(-dirs[0].y, dirs[0].x) if dirs
                else pygame.Vector2(0, -1))
    back = back.normalize()
    pen = _place_pen(site, fvec, back)

    # 7. Trees and rocks, last, in the band outside the cluster: the
    #    island's biome mix, kept off the roads, the pen and every building
    #    by `_V_SCATTER_GAP`, so the settlement sits in a meadow that
    #    thickens toward the coast -- and two tiles clear of the pen, whose
    #    posts are small and whose sheep a canopy would otherwise cover.
    _scatter(site, pen)

    return Village(room_id=room.id, forge=fvec, heal=pygame.Vector2(heal),
                   buildings=buildings, posts=posts, pen=pen,
                   mouths=[(m.x, m.y) for m in mouths],
                   radius=_V_CLUSTER_RADIUS * px)


def _scatter(site: _Site, pen=None) -> None:
    """The village island's own obstacle scatter (`world/gen/scatter.py`
    passes over the island). Same mix as the biome's, `_V_SCATTER_SCALE`
    of its density, same rules as every other village circle plus a wider
    gap to the buildings, and only outside `_V_CLUSTER_RADIUS` of the forge
    so the settlement's centre stays open. `shrub` is decoration and is not
    placed."""
    room, rng, px = site.room, site.rng, site.px
    sheet = room.palette.get(room.floor) if room.palette else None
    mix = biomes.scatter_mix(sheet)
    kinds, weights, per_1000 = mix or (("tree", "rock", "pillar"), (4, 3, 2),
                                       _GRID_OBSTACLES_PER_1000)
    weights = [w * (_V_SCATTER_TREES if k == "tree" else 1.0)
               for k, w in zip(kinds, weights)]
    fam = biomes.biome_of(sheet) if sheet else ""
    cells = sorted(room.cells)
    fx, fy = site.forge
    keep_sq = (_V_CLUSTER_RADIUS * px) ** 2
    pen_keep = pen.inflate(4 * px, 4 * px) if pen is not None else None
    tries = int(len(cells) * per_1000 * _V_SCATTER_SCALE / 1000.0)
    for _ in range(tries):
        kind = rng.choices(kinds, weights=weights, k=1)[0]
        if kind not in KINDS:
            continue                    # `shrub`: decoration, not an obstacle
        col, row = rng.choice(cells)
        x = room.rect.left + col * px + rng.uniform(px * 0.28, px * 0.72)
        y = room.rect.top + row * px + rng.uniform(px * 0.28, px * 0.72)
        if (x - fx) ** 2 + (y - fy) ** 2 < keep_sq:
            continue                    # inside the settlement
        if pen_keep is not None and pen_keep.collidepoint(x, y):
            continue                    # a canopy over the sheep
        r = float(KINDS[kind][0])
        if not (site.ground_disc(x, y, r + _V_COAST_PAD)
                and not _blocks(site.doors, x, y, r)
                and site.free(x, y, r, _V_SCATTER_GAP)
                and site.off_lanes(x, y, r)):
            continue
        o = Obstacle(kind, x, y, rng.randint(1, 4))
        o.biome = fam
        site.placed.append(o)


def _place_pen(site: _Site, forge: pygame.Vector2, back: pygame.Vector2):
    """A `w x h` ring of fence tiles with a two-tile gate in the middle of
    its south side, its centre `_V_PEN_DIST` tiles from the forge along
    `back`. Returns the interior as a world-px `Rect` (what the sheep are
    leashed to), or `None` when no size at no distance fits.

    The fence has its own pitch, `_V_PEN_SCALE` of a world tile (the owner
    asked for a corral 40% smaller): the ring's tiles are laid `pitch` px
    apart from the pen's own origin, not on the world grid, and the art is
    drawn at the same scale so it still meets post to post. Two tiles of
    gate rather than one, from when the repair still judged the pen: a
    one-tile gap read as sealed whenever a lattice column landed off its
    middle, and the repair pulled a gate post out."""
    rng, px = site.rng, site.px
    pitch = px * _V_PEN_SCALE
    # Smallest first: on the quarter-smaller island (HI-3) a shuffled order
    # lost a third of the pens to sizes that had no room anywhere.
    sizes = sorted(((w, h) for w in range(_V_PEN_W[0], _V_PEN_W[1] + 1)
                    for h in range(_V_PEN_H[0], _V_PEN_H[1] + 1)),
                   key=lambda s: s[0] * s[1])
    lo, hi = _V_PEN_DIST
    fence_r = float(KINDS["fence"][0])
    # Nearest first, fanning out from `back` -- all the way round if the
    # far side of the island has no room, since a pen beside a road still
    # beats no pen.
    d = lo
    while d <= hi + 1e-9:
        for k in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7, 8, -8, 9, -9, 10):
            a = math.atan2(back.y, back.x) + k * 0.3
            cx = forge.x + math.cos(a) * d * px
            cy = forge.y + math.sin(a) * d * px
            for w, h in sizes:
                ox = round(cx - w * pitch / 2)
                oy = round(cy - h * pitch / 2)
                posts = [(ox + (col + 0.5) * pitch, oy + (row + 0.5) * pitch, slot)
                         for (col, row), slot in _pen_tiles(0, 0, w, h)]
                if _pen_fits(site, ox, oy, w * pitch, h * pitch, posts, fence_r):
                    for x, y, slot in posts:
                        site.add("fence", x, y, variant=FENCE_SLOTS.index(slot) + 1)
                    return pygame.Rect(round(ox + pitch), round(oy + pitch),
                                       round((w - 2) * pitch), round((h - 2) * pitch))
        d += 0.5
    return None


def _pen_tiles(c0: int, r0: int, w: int, h: int) -> list:
    """`((col, row), slot)` for the ring of a `w x h` pen whose top-left
    tile is `(c0, r0)`. The pack ships the south rail only as two gate
    halves, so the south side is corner, rail, gate-left, two open tiles,
    gate-right, rail, corner; the plain rail is the north tile, whose band
    the halves share."""
    c1, r1 = c0 + w - 1, r0 + h - 1
    gate = (c0 + w // 2 - 1, c0 + w // 2)   # the two open tiles
    out = [((c0, r0), "nw"), ((c1, r0), "ne"), ((c0, r1), "sw"), ((c1, r1), "se")]
    for i, col in enumerate(range(c0 + 1, c1)):
        out.append(((col, r0), "n1" if i % 2 == 0 else "n2"))
        if col == gate[0] - 1:
            out.append(((col, r1), "s_gate_l"))
        elif col == gate[1] + 1:
            out.append(((col, r1), "s_gate_r"))
        elif col not in gate:
            out.append(((col, r1), "n1" if i % 2 == 0 else "n2"))
    for row in range(r0 + 1, r1):
        out.append(((c0, row), "w"))
        out.append(((c1, row), "e"))
    return out


def _pen_fits(site: _Site, ox: float, oy: float, W: float, H: float, posts,
              fence_r) -> bool:
    """`(ox, oy)` is the ring's top-left corner and `W x H` its size, in
    world px; `posts` the fence centres. The whole footprint and a world
    tile round it must be plain ground, so the pen never straddles the
    coast and a sheep never bounces over the sea; every post passes the
    village's own tests; nothing already stands inside."""
    px = site.px
    c0, r0 = site.cell_of(ox - px, oy - px)
    c1, r1 = site.cell_of(ox + W + px, oy + H + px)
    for col in range(c0, c1 + 1):
        for row in range(r0, r1 + 1):
            cell = site.grid.get((col, row))
            if cell is None or cell.kind != GROUND:
                return False
    for x, y, _slot in posts:
        if (_blocks(site.doors, x, y, fence_r)
                or not site.free(x, y, fence_r, _V_GAP)
                or not site.off_lanes(x, y, fence_r)):
            return False
    inner = pygame.Rect(round(ox), round(oy), round(W), round(H))
    return not any(inner.collidepoint(o.pos.x, o.pos.y) for o in site.placed)
