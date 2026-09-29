"""How a projectile meets the terrain's elevation (CMB-010, after LD-9 D10).

Two rules, picked by whether the shot bounces (`Projectile.bounces_left`).

**A plain shot keeps a floor that only rises.** The floor starts at the level
a body would stand on under the muzzle (`muzzle_floor`). Terrain at or below
it never stops the shot, so firing *down* off a terrace works and a shot that
climbed still crosses a gap onto another terrace of the same height. Terrain
*above* it stops the shot unless the shot got there the way a body would: the
step into that tile is one `world/rules/steps.py: can_step` allows -- a
stair's foot, up its flight, its head onto the terrace. A cliff face, a
plateau flank or the side of a flight is a wall. So a shot from the low floor
reaches high ground through a staircase and nowhere else. The void (`NONE`)
stops nothing, which is what lets a shot cross the sea between islands.

The floor is raised only when the climb lands on **ground**. A flight reports
its upper terrace as its height, but a shot on it has not reached that
terrace yet: it is still climbing, exactly like a body on the stairs, and
every step it takes while there is judged by `can_step`. Raising the floor on
the flight's first cell would let a shot turn off the stairs and pass through
the cliff face beside them. For the same reason a shot fired *from* a flight
leaves from the flight's low end.

**A bouncing shot moves like a walking body.** `body_blocks` is the
collider's own test -- `GameMap.is_walkable` with `frm`: the floor, the
terrace margin, the radius probes -- with the steps walked exactly (below)
instead of by `path_ok`'s half-tile samples, and without the props that do
not block projectiles. Anything a body could not cross is a wall to it
whatever the height, up *or* down -- so a pinball fired on a terrace stays on
it unless it rolls down the stairs. Its floor follows the
ground it rolls on (`ground_floor`), which is only read by what it spawns.
A ball whose centre starts off the floor (fired from over the sea, a lake or
a cliff face) has no ground to roll on yet. It flies until its whole body is
over ground (`on_ground`), walled by the edge of the world and, if it carries
a floor, by ground of any other level anywhere along its move
(`lands_off_floor`) -- it comes down only on its own floor. A ball with no
floor (fired from over the sea) comes down on whatever ground it reaches, as
a plain shot from over the sea is stopped by nothing. Once on the ground a
ball stays there (`Projectile.landed`).

Both rules walk the frame's move **tile by tile in the order the segment
crosses them** (`_crossings`, an Amanatides-Woo grid traversal), each crossing
one orthogonal step. Sampling points along the move is not enough: a sample
can jump a tile corner, and a diagonal `can_step` accepts *either* detour,
so a shot could clip through a face on the corner it actually crossed, and
whether it did would depend on the frame rate. Only a segment passing exactly
through a tile corner makes a diagonal step.

Reads a `LevelIndex` and a `GameMap`; owns no state. The projectile carries
its floor (`Projectile.floor`).
"""
from __future__ import annotations

import pygame

from world.elevation import NONE
from world.layout import GROUND
from world.rules.steps import can_step

# Two boundary crossings closer than this (as a fraction of the move) are one
# corner: accumulated float error must not split a diagonal into two steps.
_TIE = 1e-9

# How far short of the wall that stopped it a blocked shot is seated, in world
# px: against the wall, on the tile it was legally on.
_INTO_WALL = 0.5


def standing_level(levels, col: int, row: int) -> int:
    """The level a body stands on at this tile, as far as a shot is
    concerned: a flight's **low** end (it has not reached the terrace above
    yet), otherwise the terrain's top -- `NONE` over the void."""
    cell = levels.flight_at(col, row)
    if cell is not None:
        return cell.level - cell.drop
    return levels.top_at(col, row)


def muzzle_floor(levels, pos) -> int:
    """The floor a shot leaves from: `standing_level` under the muzzle.

    Sampled at the muzzle rather than on the projectile's first update: a fast
    shot has already moved several pixels by then, which at a terrace rim is
    enough to sample the tile past the edge and judge it against the wrong
    floor. `NONE` over the void, which switches the plain rule off for the
    shot's whole flight (a barrage fired from over the sea)."""
    return standing_level(levels, *levels.tile_of(pos.x, pos.y))


def _crossings(levels, start, end):
    """Yield `(tile, t)` for every tile boundary the segment crosses, in
    order: the tile entered and the fraction of the move at which it is
    entered. Orthogonal steps only, except exactly through a tile corner.

    The end tile is `tile_of(end)`, and an axis stops stepping once it has
    reached it: a move ending exactly on a boundary, going the negative way,
    stays in the tile `tile_of` gives it and never enters the next one."""
    px = levels.px
    ox, oy = levels.origin
    col, row = levels.tile_of(start.x, start.y)
    col1, row1 = levels.tile_of(end.x, end.y)
    x0, y0 = (start.x - ox) / px, (start.y - oy) / px
    dx, dy = (end.x - ox) / px - x0, (end.y - oy) / px - y0
    step_c = 1 if dx > 0 else -1
    step_r = 1 if dy > 0 else -1
    inf = float("inf")
    tx = ((col + 1 - x0) if dx > 0 else (x0 - col)) / abs(dx) if dx else inf
    ty = ((row + 1 - y0) if dy > 0 else (y0 - row)) / abs(dy) if dy else inf
    dtx = 1.0 / abs(dx) if dx else inf
    dty = 1.0 / abs(dy) if dy else inf
    while (col, row) != (col1, row1):
        ax = tx if col != col1 else inf
        ay = ty if row != row1 else inf
        if ax != inf and ay != inf and abs(ax - ay) <= _TIE:
            ay = ax                             # one corner, not two float crossings
        if ax < ay:
            col += step_c
            t = tx
            tx += dtx
        elif ay < ax:
            row += step_r
            t = ty
            ty += dty
        elif ax != inf:                         # exactly through a corner
            col += step_c
            row += step_r
            t = tx
            tx += dtx
            ty += dty
        else:                                   # float drift: land on the end
            return
        yield (col, row), min(t, 1.0)


def _seat(levels, tile, point):
    """`point`, pulled inside `tile` by `_INTO_WALL`: where a blocked shot is
    placed. `tile` is the last one it was legally on, so the impact is against
    the wall, and anything it spawns (a bomb's blast and bomblets) starts on
    ground it may stand on -- never inside the wall, and never on a neighbour
    across a corner."""
    px = levels.px
    left = levels.origin[0] + tile[0] * px
    top = levels.origin[1] + tile[1] * px
    return pygame.Vector2(
        min(max(point.x, left + _INTO_WALL), left + px - _INTO_WALL),
        min(max(point.y, top + _INTO_WALL), top + px - _INTO_WALL))


def travel(levels, floor: int, start, end):
    """Walk a plain shot from `start` to `end` on `floor`.

    Returns `(floor, blocked)`: the floor it arrives on, raised by every climb
    that lands on ground, and the point against the first wall it meets, on
    the tile before it -- or `None` when the whole move is clear. The start tile is judged
    too: standing above the floor there means the shot was never legally led
    onto it (a spawn placed there, a sticky bomb carried there), and it
    stops where it is. `start == end` asks that single point."""
    cur = levels.tile_of(start.x, start.y)
    here = standing_level(levels, *cur)
    if here != NONE and here > floor:
        return floor, pygame.Vector2(start)
    if cur == levels.tile_of(end.x, end.y):
        return floor, None                      # most frames: no boundary crossed
    d = end - start
    for nxt, t in _crossings(levels, start, end):
        top = levels.top_at(*nxt)
        if top != NONE and top > floor:
            if not can_step(levels, cur, nxt):
                return floor, _seat(levels, cur, start + d * t)
            if levels.kind_at(*nxt) == GROUND:
                floor = top                     # off the stairs, onto the terrace
        cur = nxt
    return floor, None


def steps_clear(levels, start, end) -> bool:
    """Is every tile boundary the move crosses one a body may step across?
    The exact form of `GameMap.path_ok`, for the bouncing rule."""
    cur = levels.tile_of(start.x, start.y)
    for nxt, _t in _crossings(levels, start, end):
        if not can_step(levels, cur, nxt):
            return False
        cur = nxt
    return True


def on_ground(game_map, pos, radius: float) -> bool:
    """Has a ball of `radius` at `pos` got ground under it? Its whole body on
    floor (`GameMap.on_floor`: the centre and the radius probes), with no
    terrace margin and no obstacle, so a ball hugging a rim or brushing a
    bush is still on the ground. The centre alone is not enough: a ball that
    has just come ashore with its radius over the water would find every way
    on refused by the probes and every way back refused by the floor."""
    return game_map.on_floor(pos, radius)


def lands_off_floor(game_map, start, end, floor: int) -> bool:
    """Would a ball in flight on `floor`, moving from `start` to `end`, pass
    over ground of a different level? A wall to it: it comes down only on its
    own floor. Every tile the move crosses is judged, and the end point
    exactly (a bridge is not tile-aligned); `NONE` (fired over the sea) lands
    anywhere."""
    levels = getattr(game_map, "_levels", None)
    if levels is None or floor == NONE:
        return False

    def other(tile) -> bool:
        if not levels.kind_at(*tile):
            return False                        # no floor on this tile
        here = standing_level(levels, *tile)
        return here != NONE and here != floor

    for tile, _t in _crossings(levels, start, end):
        if other(tile):
            return True
    return (not game_map.is_open_water(end.x, end.y)
            and other(levels.tile_of(end.x, end.y)))


def body_blocks(game_map, pos, radius: float, frm) -> bool:
    """Would a bouncing shot moving from `frm` to `pos` hit a wall? The
    collider's test for a body of the shot's radius -- off the floor, into
    the terrace margin -- with the steps walked exactly.

    Two differences from a body, both because this is a projectile. It
    passes the props that do not block projectiles (a bush, a scarecrow), as
    a plain shot does; the ones that do are `bounce`'s own obstacle test. And
    a ball already overhanging the water (a shooter smaller than its shot, at
    a shoreline or a bridge mouth) may keep rolling on its centre until it is
    clear of the edge again -- "cannot enter, may leave", as the collider
    treats the terrace margin -- instead of finding every way refused."""
    probe = radius if game_map.on_floor(frm, radius) else 0.0
    if not game_map.is_walkable(pos, probe, frm=frm, path=False, obstacles=False):
        return True
    levels = getattr(game_map, "_levels", None)
    return levels is not None and not steps_clear(levels, frm, pos)


def ground_floor(levels, pos, floor: int) -> int:
    """A grounded bouncing shot's floor after a clear move: `standing_level`
    where it is now (a ball from over the sea takes the ground it came down
    on). Keeps the old value where there is no level."""
    here = standing_level(levels, *levels.tile_of(pos.x, pos.y))
    return floor if here == NONE else here
