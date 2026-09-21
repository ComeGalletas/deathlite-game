"""The village, one step at a time (`world/gen/village/`).

`_lay_out` runs the steps in the order they must run: the forge, the roads,
the north axis, the houses, the military row, the pen, the props, then the
tidy pass and the `Village` record. Each step owns one decision and
mutates the `_Site`; what the next step needs, it returns.
"""
from __future__ import annotations

import math

import pygame

from world.gen.tuning import (
    _V_CLUSTER_MAX, _V_HALL_ABOVE, _V_HEAL_FLANK, _V_HEAL_NORTH, _V_HEAL_RADIUS, _V_HOUSES, _V_HOUSE_LINK, _V_LANE_HALF, _V_MILITARY_FLANK, _V_MILITARY_INLAND, _V_MILITARY_PITCH, _V_RING, _V_SCATTER_GAP, _V_SLOTS,
)
from world.gen.village_tidy import BUILDINGS, flank_spot, military_spot, tidy
from world.layout import Village
from world.gen.village.site import COLOURS, _Cycle, _seg_dist, _road, _circles, _Site
from world.gen.village.pen import _place_pen
from world.gen.village.scatter import _scatter, _fill_scatter, _grow_trees


def _lay_out(site: _Site, town_hall: bool) -> Village:
    """The village, one step at a time, in the order they run.

    Each step below owns one decision and mutates `site`; what the next step
    needs, it returns. The order is not arbitrary and mostly cannot change:
    the roads are drawn to the forge, the axis stands on the forge, the ring
    is measured from it, the military row follows the roads, and the pen goes
    where the bridges are not. The two places where the order *is* a choice
    are marked where they happen.
    """
    colours = _Cycle(site.rng, len(COLOURS))
    mouths = [pygame.Vector2(d.center) for d in site.doors]
    forge = _seat_forge(site, mouths)
    fvec = pygame.Vector2(forge)
    dirs = _lay_roads(site, mouths, fvec)
    heal = _seat_axis(site, forge, colours, town_hall)
    want, placed = _seat_houses(site, forge, heal, colours)
    posts = _seat_military(site, mouths, dirs, colours)
    back = _seat_pen(site, fvec, dirs)
    # A choice, not a sequence: the corral claims its ground before the house
    # row is finished, because a village has one pen and may have five houses.
    # Filling the row first cost one village in fifty-two its pen.
    if placed < want:
        _fill_beside(site, colours, site.rng, want, placed)
    _decorate(site)
    return _record(site, heal, mouths, posts, back)
def _seat_forge(site: _Site, mouths) -> tuple:
    """Step 1. Returns the forge's world position; `site.forge` is set."""
    px = site.px
    room = site.room
    # 1. The forge, at the walkable centroid -- or the nearest cell to it
    #    that takes the forge *and leaves the axis room*: ground for the
    #    heal two tiles north and for the hall four to five and a half
    #    tiles north. A centroid a few tiles off the north coast would
    #    otherwise put the hall in the sea, and the whole village slides
    #    south a little instead.
    c = room.center
    cells = sorted(room.cells, key=lambda p: (site.tile_centre(*p)[0] - c.x) ** 2
                   + (site.tile_centre(*p)[1] - c.y) ** 2)


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
            legs = [leg for m in mouths for leg in _road(m, cand, px)]
            if all(_seg_dist(cx, cy, a, b) >= cr + keep
                   for cx, cy, cr in _circles("monastery", mx, my) for a, b in legs):
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
    site.boxes.append(site.art_rect("forge", *forge))
    return forge
def _lay_roads(site: _Site, mouths, fvec) -> list:
    """Step 2. Returns the way in from each mouth; `site.lanes` and
    `site.mouth_dirs` are filled."""
    px = site.px
    # 2. The roads: one lane from each bridge mouth, in to a knee on the
    #    street (the forge's row) and along it to the forge (`_road`),
    #    kept clear of everything but the guards that flank it. `dirs` is
    #    the way in from each mouth -- the first leg -- for the military
    #    row and the pen.
    dirs = []
    for m in mouths:
        legs = _road(m, fvec, px)
        site.lanes.extend(legs)
        a, b = legs[0]
        v = b - a
        if v.length_squared() > 1e-6:
            dirs.append(v.normalize())
    site.mouth_dirs = list(zip(mouths, dirs))
    return dirs
def _seat_axis(site: _Site, forge, colours, town_hall: bool) -> tuple:
    """Step 3. Returns the heal's world position; the hall stands above it."""
    px = site.px
    # 3. The north axis. The heal zone stands `_V_HEAL_NORTH` tiles due
    #    north of the forge -- an interactable, not an obstacle, so it only
    #    reserves its disc -- and the town hall (the monastery) due north of
    #    that. Either slides up the axis a tile or two if its spot is taken.
    heal = None
    for up in (0.0, 1.0, 2.0):
        x, y = site.snap(forge[0], forge[1] - (_V_HEAL_NORTH + up) * px)
        if site.circle_ok(x, y, _V_HEAL_RADIUS, lane=False):
            heal = (x, y)
            break
    if heal is None:
        heal = (forge[0], forge[1] - _V_HEAL_NORTH * px)
    site.reserved.append((*heal, _V_HEAL_RADIUS))
    site.boxes.append(site.heal_box(*heal))
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
            site.boxes.append(site.art_rect("monastery", *pos))
    return heal
def _seat_houses(site: _Site, forge, heal, colours) -> tuple:
    """Step 4. Returns `(wanted, placed)` -- the row may come up short on a
    small island, and `_fill_beside` finishes it after the pen."""
    rng, px = site.rng, site.px
    # 4. The houses. The square first (LD-Z): one house on each flank of
    #    the heal, `_V_HEAL_FLANK` tiles east and west of it, so the
    #    sanctuary has company. Then the rest clustered: a walk round the
    #    ring, off the axis (the north three slots of eight are the
    #    hall's), starting at a random slot and going one way, each house
    #    placed within `_V_HOUSE_LINK` tiles of the one before it. A spot
    #    that will not take a house is stepped past, never skipped a
    #    whole slot, so the walk's houses stay one piece; the street lies
    #    between them and the flank houses, and the whole is one village
    #    round the forge (`_V_CLUSTER_MAX`).
    step = 2 * math.pi / _V_SLOTS
    free = [k for k in range(_V_SLOTS) if not site.on_axis(k * step)]   # E, SE, S, SW, W
    n = rng.randint(*_V_HOUSES)
    last = None
    placed_houses = 0
    first = rng.choice((1, -1))
    for side in (first, -first):
        spot = flank_spot(site, heal, side)
        if spot is None:
            continue
        colour = colours.next()
        site.add("house", *spot, variant=colour * 3 + rng.randint(0, 2) + 1)
        placed_houses += 1
    a = rng.choice(free) * step + rng.uniform(-0.2, 0.2)
    turn = rng.choice((1, -1))
    swept = 0.0
    while placed_houses < n and swept < 2 * math.pi:
        pos = None
        if not site.on_axis(a):
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
            last = pos
            placed_houses += 1
            a += turn * 0.4
            swept += 0.4
        else:
            a += turn * 0.15
            swept += 0.15
    return n, placed_houses
def _seat_military(site: _Site, mouths, dirs, colours) -> list:
    """Step 5. Returns the guard posts, as the buildings placed at each."""
    px = site.px
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
            o = site.add(kind, x, y, variant=colours.next() + 1)
            if kind in ("barracks", "tower"):
                pair.append(o)
        if pair:
            posts.append(pair)
    if not posts and site.mouth_dirs:
        # No row fit beside any road (short legs in to the street, a
        # coast at the elbow): the village still gets its guards, by the
        # broad search the tidy pass relocates with, nearest the first
        # road's own row. Per village, not per bridge -- a second garrison
        # would take the room the pen needs.
        m, d = site.mouth_dirs[0]
        near = m + d * _V_MILITARY_INLAND * px
        pair = []
        for kind in ("barracks", "tower"):
            spot = military_spot(site, kind, (near.x, near.y), site.mouth_dirs)
            if spot is not None:
                pair.append(site.add(kind, *spot, variant=colours.next() + 1))
        if pair:
            posts.append(pair)
    return posts
def _seat_pen(site: _Site, fvec, dirs):
    """Step 6. Returns the direction the pen was sought in, which the tidy
    pass re-uses if it has to move it; `site.pen` is set."""
    # 6. The sheep pen, on the side of the island the bridges are not.
    back = -sum(dirs, pygame.Vector2()) if dirs else pygame.Vector2()
    if back.length_squared() < 1e-6:
        back = (pygame.Vector2(-dirs[0].y, dirs[0].x) if dirs
                else pygame.Vector2(0, -1))
    back = back.normalize()
    site.pen = _place_pen(site, fvec, back)
    return back
def _decorate(site: _Site) -> None:
    """Step 7. The three prop sweeps, in the order density is added: the
    biome's own scatter, the fill over what it left empty, then the trees."""
    # 7. Trees and rocks, last, in the band outside the cluster: the
    #    island's biome mix, kept off the roads, the pen and every building
    #    by `_V_SCATTER_GAP`, so the settlement sits in a meadow that
    #    thickens toward the coast -- and two tiles clear of the pen, whose
    #    posts are small and whose sheep a canopy would otherwise cover.
    _scatter(site, site.pen)
    #    ... then a second sweep over the cells the first left empty, chiefly
    #    the band round the shore (the owner's, 2026-09-12). Before the tidy
    #    pass, so anything it stands too near the square is judged with the
    #    rest.
    _fill_scatter(site, site.pen)
    _grow_trees(site, site.pen)
def _record(site: _Site, heal, mouths, posts, back) -> Village:
    """Step 8. The tidy pass, then the `Village` the run reads -- taken off
    the finished site, since the tidy pass may have moved or removed things."""
    px = site.px
    room = site.room
    fvec = pygame.Vector2(site.forge)
    # 8. The tidy pass (LD-Z, `world/gen/village_tidy.py`): nothing paints
    #    over the forge, the heal or the hall, no building over another,
    #    and the heal has company. Buildings may move or go here, so the
    #    record is read off the site afterwards, not off the steps above.
    report = tidy(site, heal, mouths, back)
    buildings = [(o.kind, o.pos.x, o.pos.y) for o in site.placed
                 if o.skin and o.kind in BUILDINGS]
    live = {id(o) for o in site.placed}
    posts = [tuple((o.pos.x, o.pos.y) for o in pair if id(o) in live)
             for pair in posts]
    posts = [p for p in posts if p]

    return Village(room_id=room.id, forge=fvec, heal=pygame.Vector2(heal),
                   buildings=buildings, posts=posts, pen=site.pen,
                   mouths=[(m.x, m.y) for m in mouths],
                   radius=site.settlement, company=report["company"])
def _fill_beside(site: _Site, colours, rng, want: int, placed: int) -> int:
    """Seat the houses the ring walk could not, on a tile centre next to one
    it did -- the eight neighbours of each house, the houses nearest the
    forge first, so the row closes up toward the middle rather than
    trailing off to the coast. Returns the new count."""
    px = site.px
    forge = pygame.Vector2(site.forge)
    around = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    # Gathered once, in `site.placed` order, and appended to below: the only
    # houses this loop can add are its own, so re-scanning `site.placed` each
    # time round produced the same list.
    row = [o for o in site.placed if o.skin and o.kind == "house"]
    while placed < want:
        spot = None
        for h in sorted(row, key=lambda o: (o.pos - forge).length_squared()):
            for dx, dy in around:
                x, y = site.snap(h.pos.x + dx * px, h.pos.y + dy * px)
                if site.fits("house", x, y):
                    spot = (x, y)
                    break
            if spot is not None:
                break
        if spot is None:
            return placed
        row.append(site.add("house", *spot,
                            variant=colours.next() * 3 + rng.randint(0, 2) + 1))
        placed += 1
    return placed
