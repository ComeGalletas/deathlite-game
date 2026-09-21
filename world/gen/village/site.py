"""One village island's placement state and the geometry it is built on.

`_Site` holds what stands where so far and the tests every new thing has
to pass (`world/gen/village/`); `_road`, `_seg_dist` and `_circles` are
the pure geometry under it, and `_Cycle` the shuffled bag the colours and
the house types are drawn from.
"""
from __future__ import annotations

import math

import pygame

from entities.obstacle import KINDS, Obstacle, satellites_of
from game import config
from world.gen.scatter import _blocks
from world.gen.tuning import (
    _V_ART_TOL, _V_CLUSTER_RADIUS, _V_COAST_PAD, _V_FILL_SQUARE, _V_GAP, _V_HEAL_RADIUS, _V_LANE_HALF, _V_PAIR_GAPS, _V_SLOTS, _V_STREET_REACH,
)
from world.gen.village_tidy import BUILDINGS, clips
from world.layout import GROUND, Village
from world.rules import frontier


# The order of the colour rig lists in `terrain.json` (`obstacle_decor.rigs`):
# a building's `variant` is its index here plus one, a house's is
# `colour * 3 + type + 1` over the fifteen house rigs.
COLOURS = ("blue", "red", "yellow", "purple", "black")
# The fence rigs, in `obstacle_decor.rigs["fence"]` order; `variant` indexes it.
FENCE_SLOTS = ("nw", "n1", "n2", "ne", "w", "e", "sw", "s_gate_l", "s_gate_r", "se")
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
def _road(m: pygame.Vector2, f: pygame.Vector2, px: float) -> list:
    """The lane from bridge mouth `m` to forge `f`, as segments: in from
    the mouth to a *knee* on the street -- the forge's own row -- and
    along the street to the forge. The knee stands under the mouth, or
    `_V_STREET_REACH` tiles out from the axis on the mouth's side when the
    mouth is nearer than that, so no road cuts across the square north of
    the street where the heal and its flanking houses stand (LD-Z). A
    mouth already on the street gets the one straight segment."""
    dx = m.x - f.x
    reach = _V_STREET_REACH * px
    if abs(dx) < reach:
        kx = f.x + math.copysign(reach, dx if abs(dx) > 1e-6 else 1.0)
    else:
        kx = m.x
    knee = pygame.Vector2(kx, f.y)
    legs = []
    if (knee - m).length_squared() > 1e-6:
        legs.append((m, knee))
    legs.append((knee, f))
    return legs
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

    def __init__(self, room, doors, rng, terrain=None) -> None:
        self.room = room
        self.grid = room.grid
        self.rect = room.rect
        self.px = config.TILE_PX
        self.rng = rng
        self.doors = list(doors)
        self.placed: list[Obstacle] = []
        self.reserved: list[tuple[float, float, float]] = []   # (x, y, r): the heal prop
        self.lanes: list[tuple[pygame.Vector2, pygame.Vector2]] = []
        # LD-Z: the painted reach of every kind, `(north, south, west,
        # east)` from its position, and the protected boxes -- the forge,
        # the heal, the hall -- that nothing may paint over.
        terrain = terrain or {}
        self.reach = frontier.paint_reach(terrain, config.SPRITE_ANCHOR_DROP)
        fx_heal = terrain.get("rigs", {}).get("fx_heal")
        self.heal_reach = (frontier.paint_box(fx_heal, 1.0) if fx_heal
                           else (_V_HEAL_RADIUS,) * 4)
        self.boxes: list[pygame.Rect] = []
        self.art_tol = _V_ART_TOL
        self.parts: dict[int, list] = {}      # id(primary) -> its satellites
        self.forge = None
        self.pen = None
        # The two discs round the forge, in world px, converted once here so
        # no pass multiplies tiles by `px` for itself:
        #
        #   `settlement` -- the whole village's extent. The first scatter
        #   keeps its props outside it, the unseal repair will not take an
        #   obstacle back from inside it, and the bake's clutter pass keeps
        #   out too (both read it off `Village.radius`).
        #   `square` -- just the forge, the heal above it and the hall above
        #   that. The fill sweep and the tree top-up keep out of this one
        #   only, because the settlement disc is a circle while the buildings
        #   are not: on a ragged island they crowd one side and the lawn on
        #   the other is inside the circle with nothing in it.
        #
        # `settlement` is exported on the `Village` record, which the repair
        # and the bake read; `square` has no consumer outside generation and
        # stays here, so the record does not grow a field nobody asks for.
        self.settlement = _V_CLUSTER_RADIUS * self.px
        self.square = _V_FILL_SQUARE * self.px

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

    def free(self, x: float, y: float, r: float, gap: float, kind=None) -> bool:
        """Is `(x, y)` clear of everything placed by `gap` px -- or by the
        pairing's own gap, for the pairings `_V_PAIR_GAPS` lists."""
        for o in self.placed:
            keep = _V_PAIR_GAPS.get((kind, o.kind), gap)
            if (x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < (r + o.radius + keep) ** 2:
                return False
        for rx, ry, rr in self.reserved:
            if (x - rx) ** 2 + (y - ry) ** 2 < (r + rr + gap) ** 2:
                return False
        return True

    def off_lanes(self, x: float, y: float, r: float) -> bool:
        keep = r + _V_LANE_HALF * self.px
        return all(_seg_dist(x, y, a, b) >= keep for a, b in self.lanes)

    def circle_ok(self, x: float, y: float, r: float, lane: bool,
                  kind=None) -> bool:
        return (self.ground_disc(x, y, r + _V_COAST_PAD)
                and not _blocks(self.doors, x, y, r)
                and self.free(x, y, r, _V_GAP, kind)
                and (not lane or self.off_lanes(x, y, r)))

    def on_axis(self, angle: float) -> bool:
        """Is `angle` (radians, screen y down) within the north three of
        the eight ring slots -- the axis the heal and the hall stand on?"""
        step = 2 * math.pi / _V_SLOTS
        north = -math.pi / 2
        return abs(((angle - north + math.pi) % (2 * math.pi)) - math.pi) <= step * 1.5 - 1e-9

    # --- the art (LD-Z) ------------------------------------------------
    def art_rect(self, kind: str, x: float, y: float) -> pygame.Rect:
        """The box the art of `kind` at `(x, y)` will paint, world px."""
        n, s, w, e = self.reach.get(kind) or (0.0, 0.0, 0.0, 0.0)
        return pygame.Rect(round(x - w), round(y - n), round(w + e), round(n + s))

    def art_of(self, o: Obstacle) -> pygame.Rect:
        return self.art_rect(o.kind, o.pos.x, o.pos.y)

    def heal_box(self, x: float, y: float) -> pygame.Rect:
        """The heal effect's painted column plus its interactable disc."""
        n, s, w, e = self.heal_reach
        r = _V_HEAL_RADIUS
        box = pygame.Rect(round(x - w), round(y - n), round(w + e), round(n + s))
        return box.union(pygame.Rect(round(x - r), round(y - r), round(2 * r), round(2 * r)))

    def art_ok(self, kind: str, x: float, y: float, skip=None) -> bool:
        """Would the art of `kind` at `(x, y)` paint over a protected box
        (the forge, the heal, the hall) -- or, for a building or a fence
        post, over any building already standing? A prop may stand
        before or behind a house (that is a tree by a house); it may not
        stand over the three the village is built round."""
        box = self.art_rect(kind, x, y)
        if any(clips(box, p, self.art_tol) for p in self.boxes):
            return False
        if kind in BUILDINGS or kind == "fence":
            for o in self.placed:
                if o is skip or not o.skin or o.kind not in BUILDINGS:
                    continue
                if kind == "house" and o.kind == "house":
                    continue            # houses may crowd: owner, 2026-09-12
                if clips(box, self.art_of(o), self.art_tol):
                    return False
        return True

    def prop_fits(self, kind: str, x: float, y: float, gap: float) -> bool:
        """The guard every *prop* passes -- tree, rock, pillar, sign,
        scarecrow -- whichever sweep is placing it: on ground with the coast
        pad, out of every bridge mouth, `gap` px from anything standing (less
        between two trees, `_Site.free`), off the roads, and not painting
        over the forge, the heal or the hall.

        The three sweeps (`_scatter`, `_fill_scatter`, `_grow_trees`) differ
        only in how they pick the candidate point and what gap they ask for;
        they shared this chain by copy before, in three places that had to be
        kept in step by hand."""
        r = float(KINDS[kind][0])
        return (self.ground_disc(x, y, r + _V_COAST_PAD)
                and not _blocks(self.doors, x, y, r)
                and self.free(x, y, r, gap, kind)
                and self.off_lanes(x, y, r)
                and self.art_ok(kind, x, y))

    def fits(self, kind: str, x: float, y: float, lane: bool = True,
             art: bool = True) -> bool:
        return (all(self.circle_ok(cx, cy, cr, lane, kind)
                    for cx, cy, cr in _circles(kind, x, y))
                and (not art or self.art_ok(kind, x, y)))

    # --- placing ------------------------------------------------------
    def add(self, kind: str, x: float, y: float, variant: int = 1) -> Obstacle:
        """One building: the primary circle carries the skin, the satellites
        collide only."""
        circles = _circles(kind, x, y)
        primary = Obstacle(kind, x, y, variant)
        self.placed.append(primary)
        sats = []
        for cx, cy, cr in circles[1:]:
            sat = Obstacle(kind, cx, cy, variant)
            sat.radius = cr
            sat.skin = False
            self.placed.append(sat)
            sats.append(sat)
        self.parts[id(primary)] = sats
        return primary

    def remove(self, primary: Obstacle) -> None:
        """Take a building (or a post, or a prop) back, satellites with it."""
        gone = {id(primary)} | {id(s) for s in self.parts.pop(id(primary), ())}
        self.placed = [o for o in self.placed if id(o) not in gone]

    def ring(self, kind: str, d_range, angle: float, spread: float,
             lane: bool = True, ok=None):
        """The first tile centre that fits `kind`, searched outward from
        `angle` (radians, screen y down) over `d_range` tiles from the forge:
        nearest distance first, then the angle fanned out to `spread` each way.
        `None` when nothing in the fan fits. `ok(x, y)`, when given, is one
        more test a spot has to pass."""
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
                    if self.fits(kind, x, y, lane) and (ok is None or ok(x, y)):
                        return x, y
                k += 1
            d += 0.5
        return None
