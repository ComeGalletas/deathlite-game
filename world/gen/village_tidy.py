"""The village tidy pass (LD-Z): what the layout pass leaves, made clean.

`world/gen/village.py` places by collider: circles, a gap, the coast pad,
the doorways and the lanes. The art is two to four times the collider --
a house collides on 41 px and paints 102 wide and 143 tall -- so two
buildings whose circles clear each other still paint over one another,
and the y-sort then hides whichever stands higher. This pass runs once the
village is laid out and makes three promises the placement cannot:

1. **Nothing paints over the forge, the heal zone or the town hall** (the
   monastery). Those three are protected -- never moved, never removed.
   Any other building, fence post or prop whose painted box crosses one of
   theirs is relocated by the same rules it was placed by (`_Site.fits`,
   which since this pass also keeps art clear of art) and, if it fits
   nowhere, removed -- satellites with it.
2. **No building paints over another.** The later-placed one moves; the
   one that will not move goes.
3. **The heal has company.** At least `_V_HEAL_COMPANY` buildings besides
   the forge and the hall stand within `_V_HEAL_NEAR` tiles of it, on the
   flank slots `_V_HEAL_FLANK` tiles east and west of it, so the sanctuary
   reads as the village square rather than a glow on a lawn. A spare
   house is pulled onto the flank, nearest first -- the nearest is the
   one standing just outside the flank and blocking it; when none can
   move the count stays short and the record says so (`Village.company`).

Painted boxes come from `frontier.paint_reach` -- the rigs' measured
`paint` boxes at the scale and drop the skins will draw them -- so the
pass and the renderer cannot drift. "Crosses" allows `_V_ART_TOL` px of
overlap both ways: the boxes are bounding boxes and a sprite's corner is
transparent.

Deterministic: walks `site.placed` in order and draws nothing from any
RNG. The layout pass's placement rules (ground with the coast pad, clear
of the bridge mouths, off the lanes, the collider gap) hold for every
position this pass chooses, since it chooses through the same `fits`.
"""
from __future__ import annotations

import math

import pygame

from world.gen.tuning import (
    _V_CLUSTER_MAX, _V_HEAL_COMPANY, _V_HEAL_FLANK, _V_HEAL_NEAR,
    _V_HOUSE_LINK, _V_MILITARY_REACH, _V_RING,
)

# What counts as a building: these paint over one another and flank the heal.
BUILDINGS = ("forge", "monastery", "house", "barracks", "tower", "archery")
# Never moved, never removed. The heal is the third protected thing; it is
# an interactable, not an obstacle, and lives in `site.boxes`.
KEY = ("forge", "monastery")
MILITARY = ("barracks", "tower", "archery")

__all__ = ["tidy", "flank_spot", "military_spot", "BUILDINGS", "KEY", "clips"]


def clips(a: pygame.Rect, b: pygame.Rect, tol: float) -> bool:
    """Do two painted boxes overlap by more than `tol` px both ways?"""
    c = a.clip(b)
    return c.width > tol and c.height > tol


def tidy(site, heal, mouths, back) -> dict:
    """Clean `site` in place; `heal` is the heal's world position, `mouths`
    the bridge-mouth centres, `back` the pen's direction. Returns a small
    report: what moved, what went, how many buildings flank the heal."""
    report = {"moved": [], "removed": [], "company": 0}
    _clear_protected(site, mouths, report)
    _unclip_buildings(site, mouths, report)
    _repen(site, back, report)
    report["company"] = _flank_heal(site, heal, report)
    return report


# --- 1. nothing over the forge, the heal or the hall ------------------------
def _clear_protected(site, mouths, report) -> None:
    for o in list(site.placed):
        if not o.skin or o.kind in KEY or o.kind == "fence":
            continue                    # the pen is judged whole, below
        if o not in site.placed:
            continue
        box = site.art_of(o)
        if not any(clips(box, p, site.art_tol) for p in site.boxes):
            continue
        _move_or_drop(site, o, mouths, report)


# --- 2. no building over another --------------------------------------------
def _unclip_buildings(site, mouths, report) -> None:
    """Pairs in placement order: the later one gives way, a key building
    never does. A moved building is re-tested against everything by
    `fits`, so one pass usually suffices; the second catches a move that
    landed on a pair the first pass had already walked."""
    for _round in range(2):
        moved = False
        prims = [o for o in site.placed if o.skin and o.kind in BUILDINGS]
        for i, a in enumerate(prims):
            for b in prims[i + 1:]:
                if b not in site.placed or a not in site.placed:
                    continue
                if not clips(site.art_of(a), site.art_of(b), site.art_tol):
                    continue
                victim = b if (a.kind in KEY or b.kind not in KEY) else a
                _move_or_drop(site, victim, mouths, report)
                moved = True
        if not moved:
            break


def _move_or_drop(site, o, mouths, report) -> None:
    kind, old = o.kind, (o.pos.x, o.pos.y)
    variant = o.variant
    site.remove(o)
    pos = None
    if kind == "house":
        pos = _house_spot(site, old)
    elif kind in MILITARY:
        pos = military_spot(site, kind, old, site.mouth_dirs)
    # a prop (tree, rock, pillar) is plentiful and fits nowhere better: it goes
    if pos is None:
        report["removed"].append((kind, *old))
        return
    site.add(kind, *pos, variant=variant)
    report["moved"].append((kind, *old, *pos))


def _house_spot(site, old):
    """The nearest ring spot to where the house stood that takes it now:
    the ring's distances from the forge, the angle fanned out from the
    house's own, off the axis, and within `_V_HOUSE_LINK` of another house
    when there is one (the cluster stays one piece)."""
    fx, fy = site.forge
    a0 = math.atan2(old[1] - fy, old[0] - fx)
    others = [o.pos for o in site.placed if o.skin and o.kind == "house"]
    px = site.px

    def ok(x, y):
        if site.on_axis(math.atan2(y - fy, x - fx)):
            return False
        return (not others
                or min(p.distance_to((x, y)) for p in others) <= _V_HOUSE_LINK * px)

    return site.ring("house", _V_RING, a0, math.pi, ok=ok)


def military_spot(site, kind, old, mouth_dirs):
    """Beside the road in from a bridge -- `mouth_dirs` is `(mouth, way
    in)` per bridge -- at the row's own kind of distances, the spot
    nearest `old` first, and never farther from the mouth than
    `_V_MILITARY_REACH` tiles (the guards' promise). The layout pass
    falls back on this for a road its row will not fit beside; the tidy
    pass relocates with it."""
    px = site.px
    best = None
    for m, d in mouth_dirs:
        perp = pygame.Vector2(-d.y, d.x)
        for inland in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0):
            for flank in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5):
                for side in (perp, -perp):
                    p = m + d * inland * px + side * flank * px
                    x, y = site.snap(p.x, p.y)
                    if m.distance_to((x, y)) > _V_MILITARY_REACH * px:
                        continue
                    if not site.fits(kind, x, y, lane=True):
                        continue
                    dd = (x - old[0]) ** 2 + (y - old[1]) ** 2
                    if best is None or dd < best[0]:
                        best = (dd, (x, y))
    return best[1] if best else None


# --- the pen, judged whole ----------------------------------------------------
def _repen(site, back, report) -> None:
    """A fence post under the heal, the hall or a building's art moves the
    whole pen: the ring comes out and `_place_pen` runs again. The art
    rules are on in `_pen_fits`, so a fresh pen lands clean; what this
    catches is a pen placed before a building moved onto it."""
    posts = [o for o in site.placed if o.kind == "fence"]
    if not posts:
        return
    if all(site.art_ok("fence", o.pos.x, o.pos.y, skip=o) for o in posts):
        return
    from world.gen.village import _place_pen
    for o in posts:
        site.remove(o)
    site.pen = _place_pen(site, pygame.Vector2(site.forge), back)
    report["moved"].append(("pen",))


# --- 3. the heal has company ------------------------------------------------
def flank_spot(site, heal, side: int, ok=None):
    """A tile centre for a house on the `side` (+1 east, -1 west) of the
    heal: `_V_HEAL_FLANK` tiles out, nearest first, level with the heal or
    half a tile to a tile off, that `fits` -- roads, art and all -- and
    passes `ok(x, y)` when given. `None` when the flank has no room. The
    layout pass seats the square with this and the tidy pass fills it."""
    px = site.px
    heal = pygame.Vector2(heal)
    for dx in _V_HEAL_FLANK:
        for dy in (0.0, 1.0, -1.0):
            x, y = site.snap(heal.x + side * dx * px, heal.y + dy * px)
            if pygame.Vector2(x, y).distance_to(heal) > _V_HEAL_NEAR * px:
                continue
            if site.fits("house", x, y, lane=True) and (ok is None or ok(x, y)):
                return (x, y)
    return None


def _company(site, heal) -> list:
    near = _V_HEAL_NEAR * site.px
    return [o for o in site.placed
            if o.skin and o.kind in BUILDINGS and o.kind not in KEY
            and o.pos.distance_to(heal) <= near]


def _flank_heal(site, heal, report) -> int:
    heal = pygame.Vector2(heal)
    have = _company(site, heal)
    if len(have) >= _V_HEAL_COMPANY:
        return len(have)
    houses = [o for o in site.placed if o.skin and o.kind == "house"]
    # nearest the heal first -- the house just outside the flank is the
    # one standing on the flank's spot; the company already there stays
    houses = sorted((h for h in houses if h not in have),
                    key=lambda h: h.pos.distance_to(heal))
    for h in houses:
        if len(have) >= _V_HEAL_COMPANY:
            break
        # the emptier side first
        east = sum(1 for o in have if o.pos.x > heal.x)
        west = len(have) - east
        sides = (1, -1) if east <= west else (-1, 1)
        old = (h.pos.x, h.pos.y)
        variant = h.variant
        site.remove(h)
        spot = None
        for side in sides:
            spot = flank_spot(site, heal, side, ok=lambda x, y: _cluster_holds(site, (x, y)))
            if spot:
                break
        if spot is None:
            site.add("house", *old, variant=variant)      # back where it was
            continue
        site.add("house", *spot, variant=variant)
        report["moved"].append(("house", *old, *spot))
        have = _company(site, heal)
    return len(have)


def _cluster_holds(site, new) -> bool:
    """With a house at `new`, does every house still stand within
    `_V_CLUSTER_MAX` tiles of some other building? The village is one
    piece round its square: two houses flanking the heal are five tiles
    apart and both a stone's throw from the forge and the hall."""
    blds = [o.pos for o in site.placed if o.skin and o.kind in BUILDINGS]
    houses = [o.pos for o in site.placed if o.skin and o.kind == "house"]
    new = pygame.Vector2(new)
    blds.append(new)
    houses.append(new)
    link = _V_CLUSTER_MAX * site.px
    return all(min(h.distance_to(b) for b in blds if b is not h) <= link
               for h in houses)
