"""May a body step from one tile to the next?

`walk_links` in `world/gen/height/graph.py` is the authority on this -- it
is what `check_grid` validates every generated island against -- but it
reads a room-relative grid and allocates the whole neighbour list per call.
These mirror it against the `LevelIndex` instead, in world tiles and without
allocating, so the collider and the flow field can both ask the same
question thousands of times a frame and cannot drift from generation or
from each other. `tests/world/test_elevation.py` checks the two agree on
every cell of every island.

Kept faithful to the original down to the asymmetry in the two flight kinds:
a straight flight's foot is row `drop - 1`, an east/west flight's is row
`drop`, because the jogged unit spans one row more than it descends.
"""
from __future__ import annotations

from world.layout import GROUND, VSTAIR


def _flight_opens(index, ftile, gtile) -> bool:
    """Does the flight at `ftile` open onto the ground tile `gtile`?

    A flight is not walkable from just anywhere along its length -- only its
    head joins the terrace above and only its foot the terrace below, and an
    east/west flight also reaches sideways because the wall jogs a row across
    it. Asking the flight (rather than deriving it from the ground side) is
    what keeps the relation symmetric, exactly as `walk_links` does."""
    cell = index.flight_at(*ftile)
    if cell is None:
        return False
    c, r = ftile

    def ground(p, level) -> bool:
        return (p == gtile and index.kind_at(*p) == GROUND
                and index.level_at(*p) == level)

    if cell.kind == VSTAIR:
        return ((cell.row == 0 and ground((c, r - 1), cell.level))
                or (cell.row == cell.drop - 1
                    and ground((c, r + 1), cell.level - cell.drop)))

    if str(cell.tag).startswith("side_"):
        # The runtime half of the lateral rule in `graph.walk_links`. The two
        # are written together on purpose: `check_grid` validates generation
        # against that one, while the collider and the flow field ask this one,
        # and a disagreement between them is its own class of bug.
        dc = 1 if cell.tag.endswith("e") else -1
        low = cell.level - cell.drop
        # The column the unit sits in carries on north of the head and south of
        # the foot, and on a *protruding* crossing what carries on there is the
        # lower terrace -- flat ground with no stone in it, because a plateau's
        # side face has none. Refusing those two edges put an invisible wall on
        # open ground at both ends of nine crossings in ten. They open onto
        # whichever terrace actually lies there; only a cliff still stops you.
        #
        # Letting the head reach the low terrace is what the `walk_links`
        # comment warns about -- it is the corner-cutting hole -- so it is safe
        # only because `can_step` refuses any diagonal between two ground
        # tiles of different levels outright. The foot never had that problem:
        # both of its edges lead to the low terrace, so no level is gained.
        #
        # The head's *downhill* edge goes with them, and for the same reason
        # read off the art rather than off the level. The ramp's top tile is a
        # diagonal wedge: 64 of 64 pixels along its uphill edge and **0** along
        # its downhill one, where the tile is transparent and the low terrace
        # shows through. A wall there is a wall across open ground. The stone
        # of the drop is drawn on the *foot's* uphill flank -- 58 of 64 -- and
        # that is the one edge of the unit that stays shut.
        # North is the one edge where a terrace above may still be walled, and
        # the test is the renderer's: `grid_paint` paints a backdrop cliff on
        # the head exactly when the tile above is ground at the head's own
        # level -- a crossing notched *into* the terrace, with that terrace
        # dropping into the notch. There is a face drawn between the two, so
        # walking south off it is walking off a cliff. Such a crossing is
        # entered from its uphill flank instead, which is what a notch is for.
        # Ground at the *foot's* level above is the other alignment: the low
        # terrace running straight into the crossing, nothing drawn, no wall.
        if cell.row == 0:                              # head: the upper end
            return (ground((c - dc, r), cell.level)
                    or ground((c, r - 1), low)
                    or ground((c + dc, r), low))
        # The foot's uphill flank is open too, by the same judgement applied to
        # the ramp rather than to the tilesheet. The sheet does draw 58 of 64
        # pixels of rocky step along that edge, so this is not the "no art, no
        # wall" rule -- it is the ramp being a ramp: you may step onto it
        # sideways from the terrace it descends from, and off it the same way.
        # Both cells of the unit therefore touch both terraces, which is safe
        # for the same reason the head's reach is: `diagonal_blocked` refuses
        # the ground-to-ground corner, so a body still has to stand on the
        # crossing to change level.
        return cell.row == cell.drop and (ground((c + dc, r), low)
                                          or ground((c, r + 1), low)
                                          or ground((c - dc, r), cell.level))

    entry = 1 if cell.tag == "w" else -1     # "w" descends west, entered east
    low = cell.level - cell.drop
    if cell.row == 0 and (ground((c + entry, r), cell.level)
                          or ground((c, r - 1), cell.level)):
        return True
    return cell.row == cell.drop and (ground((c - entry, r), low)
                                      or ground((c, r + 1), low))


def diagonal_blocked(index, a, b) -> bool:
    """Is the diagonal `a` -> `b` illegal on its endpoints alone?

    Two *ground* tiles of different levels are never one move apart, whatever
    detour composes the diagonal: nothing on this terrain changes level without
    standing on a flight. Stating that directly is what lets a flight's head
    open onto both terraces -- the corner-cut it used to enable is now refused
    where it happens rather than by denying the head a neighbour.

    Both the collider (`can_step`) and the baked step mask in
    `world/pathfinding.py` consult this, so the two cannot drift."""
    return (index.kind_at(*a) == GROUND and index.kind_at(*b) == GROUND
            and index.level_at(*a) != index.level_at(*b))


def can_cross(index, a, b) -> bool:
    """May a body move from tile `a` to the orthogonally adjacent tile `b`?

    Ground joins ground of its own level; a flight joins the flight cells above
    and below it in its own stack, and joins ground only at its head and foot.
    Anything else -- a lateral level change with no stone in it, a terrace's
    back edge, the middle of a staircase -- is a wall you cannot walk through
    even though both tiles are floor.

    Non-adjacent or diagonal pairs return False. A diagonal step is the
    caller's to compose from its two orthogonal parts, which is also what stops
    a body cutting the corner of a drop."""
    if a == b:
        return True
    dc = b[0] - a[0]
    dr = b[1] - a[1]
    if abs(dc) + abs(dr) != 1:
        return False
    ka = index.kind_at(*a)
    kb = index.kind_at(*b)
    if not ka or not kb:                 # no surface recorded at either tile
        return False
    if ka == GROUND:
        if kb == GROUND:
            return index.level_at(*a) == index.level_at(*b)
        return _flight_opens(index, b, a)
    if kb == GROUND:
        return _flight_opens(index, a, b)
    # both flights: the next cell up or down the same stack, never sideways
    return dr != 0


def can_step(index, a, b) -> bool:
    """`can_cross`, plus the diagonal case composed from its orthogonal parts.

    A diagonal is open only if one of its two right-angle detours is open end
    to end, *and* its endpoints are not two ground tiles of different levels.
    Both halves stop a body slipping across the corner of a drop; the detour
    test catches it where the corner has stone in it, `diagonal_blocked` where
    the detour runs through a flight that legitimately touches both terraces."""
    if a == b:
        return True
    dc = b[0] - a[0]
    dr = b[1] - a[1]
    if dc and dr and abs(dc) == 1 and abs(dr) == 1:
        if diagonal_blocked(index, a, b):
            return False
        via_h = (a[0] + dc, a[1])
        via_v = (a[0], a[1] + dr)
        return ((can_cross(index, a, via_h) and can_cross(index, via_h, b))
                or (can_cross(index, a, via_v) and can_cross(index, via_v, b)))
    return can_cross(index, a, b)
