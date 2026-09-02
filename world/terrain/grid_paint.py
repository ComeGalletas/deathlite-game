"""LD-9 Phase C: bake a height-map room straight from its grid.

This is the whole terrain painter for a room now -- one pass over
`Room.grid`, one tile per cell. It replaces the LD-8 arrangement where the
room floor, the cliff band under its south rim, the band's underlay tiles, the
drop shadow and the ramp units were five separate collections stitched
together by `_draw_tiled` in a fixed order. Since generation already decided
every cell's kind and level, rendering has nothing left to derive.

Layering inside the returned surface, per cell:

    lake      nothing painted -- the world's water buffer shows through
    ground    the biome sheet for its level, autotiled by its open sides
    cliff     the stone face, `row` down the stack, run-capped left/right
    vstair    the grass channel, plus the stone sprite on top when "rock"
    ewstair   the biome `slots.ramp` wedge for its descent direction

A side counts as **open** (and so gets a grass fringe / shoreline edge) only
where the neighbour is water or void, or where it is the south side looking
over this terrace's own drop. A cell at the *foot* of a wall keeps its north
side flat -- the stone stands on it, so a fringe there would read as a beach
running under the cliff.
"""
from __future__ import annotations

import pygame

from world.layout import GROUND, CLIFF, VSTAIR, EWSTAIR, LAKE
from world.terrain import autotile


_SIDES = (("n", 0, -1), ("s", 0, 1), ("w", -1, 0), ("e", 1, 0))


def _open_channel(nb, side) -> bool:
    """Is `nb` a pathway this cell should run straight into?

    A grass vertical pathway is a gap cut clean through the wall and walked
    into from the north, so a rim across its head fences off the very opening
    it is meant to be. The tile above one is therefore flat, and the grass
    channel reads as continuous from the terrace down through the wall.

    Only the grass pathways. A stone-cut staircase keeps its rim -- the stair
    sprite drawn on top is what fills that channel. So do the east/west
    flights, which are notches entered from the side, where the rim above is
    the wall's own and reads correctly.

    Only the south side, too: this opens the way *into* the channel, and a
    pathway lying north of a ground cell is a different thing that should still
    read as the floor ending."""
    return side == "s" and nb.kind == VSTAIR and nb.tag != "rock"


def _floor_sides(grid, col, row, level) -> str:
    """Which sides of this ground cell get a fringe.

    A ground tile is autotiled relative to the floor it is on. Its own floor's
    ground continues on a side, or the floor ends there and the side is fringed.
    Two things are *not* the end of the floor:

    * **anything at a higher level** -- a cliff or a flight standing on this
      cell, or a terrace butting against it with no wall between. The floor
      runs on underneath; drawing an edge there traces the *upper* floor's
      outline onto the lower one, so every level boundary came out with a
      doubled rim, one on each side of it. Ground is painted below everything,
      so the structure on top covers whatever runs under it.
    * more of this floor's own ground.

    Everything else fringes, which is what keeps this floor's own topography:
    the open sea and inland lakes, ground at a *lower* level (the floor really
    does end and look over a drop), and stone at this cell's own level -- its
    terrace's own rim, the grass lip along the top of its wall.

    A flight at this level is rim to the *south* only -- the lip carries
    straight past a crossing rather than stopping either side of it -- and
    never to the west or east: a flight is part of its floor's outline, not a
    break in it, so the tile alongside one keeps the plain bottom-line rim it
    would have had if the wall ran on unbroken instead of turning a corner into
    the gap. The head of a grass vertical pathway is the one place even the
    south rim goes; see `_open_channel`."""
    out = []
    for side, dx, dy in _SIDES:
        nb = grid.get((col + dx, row + dy))
        if nb is None or nb.kind == LAKE:
            out.append(side)
        elif nb.level > level:
            continue
        elif nb.kind == GROUND and nb.level == level:
            continue
        elif nb.kind in (VSTAIR, EWSTAIR) and nb.level == level:
            # The rule below is written for a flight cut *into* a wall, which
            # is part of its floor's outline -- the terrace carries its rim
            # straight past rather than stopping either side of it.
            #
            # A lateral crossing is not that: it sits on the far side of the
            # boundary, so the terrace really does end against it. Only at the
            # **foot**, though. The head tile of the ramp carries a grass
            # fringe in its own art, and a second one on the terrace beside it
            # reads as a doubled line; the foot tile has stone there instead
            # and leaves the terrace's grass running into it unfringed.
            if (side in "we" and str(nb.tag).startswith("side_")
                    and nb.row == nb.drop):
                out.append(side)
            elif side in "we" or _open_channel(nb, side):
                continue
            else:
                out.append(side)
        else:
            out.append(side)
    return "".join(out)


def _wet_sides(grid, col, row) -> set:
    """The sides of this cell that front open sea or a lake."""
    out = set()
    for side, dx, dy in _SIDES:
        nb = grid.get((col + dx, row + dy))
        if nb is None or nb.kind == LAKE:
            out.add(side)
    return out


def _stone_edge(grid, col, row, level, sides) -> bool:
    """Does any fringed side of this cell butt against stone at its own level?

    That is this terrace's own rim -- the wall it stands on the top of -- and it
    is the one thing that outvotes water when picking a fringe block."""
    for side, dx, dy in _SIDES:
        if side not in sides:
            continue
        nb = grid.get((col + dx, row + dy))
        if nb is not None and nb.kind in _WALL_KINDS and nb.level == level:
            return True
    return False


def _ground_tile(grid, sheets, slots, col, row, level, under=False,
                 beachless=False):
    """The tile for ground of `level` at this position.

    Which *sides* are fringed is `_floor_sides`; this picks which of the
    sheet's two fringe blocks draws them. They are different art for different
    situations -- the shoreline block has white surf and belongs against water,
    the raised block a dark rim and belongs against stone -- and a tile can only
    be drawn from one of them, so the shoreline block wins wherever **any**
    fringed side fronts water -- foam is the stronger cue and a bank should read
    as a bank whatever else the tile happens to border. The exception is stone
    at the cell's own level: white surf wrapping around a cliff foot reads as
    the water being up on the plateau, so the rim wins there.

    `beachless=True` for a tileset whose shoreline block is not real surf
    (`TileSheets.has_shoreline`); it takes the raised block everywhere, which
    says "this biome has no beaches" rather than drawing a sand bank where a
    lapping shore belongs.

    `under=True` for the floor laid behind a wall, which never takes the
    shoreline block whatever it borders. A wall's foot is not a beach: the
    face's outer margin is transparent, so surf painted behind it leaks out
    around the stone and puts the waterline at the wall's own height.

    Returns `(slot, over_water)`. Every fringe tile is drawn with a ragged,
    partly transparent outer margin -- that is how surf and grass strands
    composite over whatever lies beyond them -- so the caller has to know
    whether there *is* meant to be water behind it. `over_water` false means the
    fringe faces land and needs the floor below laid behind it first."""
    sides = _floor_sides(grid, col, row, level)
    wet = _wet_sides(grid, col, row)
    # backing is needed wherever a fringed side faces land, whichever block draws it
    over_water = not sides or wet.issuperset(sides)
    if (sides and wet and not under and not beachless
            and not _stone_edge(grid, col, row, level, sides)):
        return autotile.ground_slot(slots, sides), over_water
    return (sheets.raised_slots.get(sides,
                                    sheets.raised_slots.get("", sheets.interior)),
            over_water)


_WALL_KINDS = (CLIFF, VSTAIR, EWSTAIR)


def _open_side(grid, pos, level) -> bool:
    """Is the space beside a cliff face at `level` genuinely open?

    Open means there is nothing at this cliff's own height to butt against:
    the sea, a lake, or a *lower* terrace looking up at the wall. Anything at
    the wall's own level closes the side -- another cliff, a flight cut through
    it, or the terrace grass itself where the rim jogs a row and the wall's
    neighbour is the plateau top rather than more stone.

    That last case is the one that used to be wrong. A cliff run only ends
    where you can see past it; where grass at the wall's own level sits
    alongside, a rounded cap would open a transparent notch into solid ground.
    """
    nb = grid.get(pos)
    if nb is None or nb.kind == LAKE:
        return True
    if nb.kind in _WALL_KINDS:
        return False
    return nb.level < level


def _wall_foot(grid, col, row, level, drop) -> int:
    """The grid row of the bottom-most cell of the wall this cell belongs to.

    A wall is one to `drop` cells deep, so `single` cannot be decided from the
    cell's own south neighbour -- for a two-deep wall that neighbour is the
    wall's own second row. The pillar test asks what the wall as a whole stands
    over, so walk the stack down to its foot first."""
    r = row
    for _ in range(drop + 2):
        nb = grid.get((col, r + 1))
        if nb is None or nb.kind not in _WALL_KINDS                 or nb.level != level or nb.drop != drop:
            break
        r += 1
    return r


def _run_var(grid, col, row, level=None, drop=None) -> str:
    """The left / mid / right / single face variant for a cliff cell.

    `mid` is the default: a cliff face is square-shouldered unless a side is
    open (see `_open_side`), in which case that side takes its rounded corner.
    `single` -- the free-standing pillar -- needs west, east *and* the ground
    under the wall's foot all open, so it is reserved for stone that really is
    isolated rather than merely un-flanked."""
    if level is None:
        cell = grid.get((col, row))
        level, drop = cell.level, cell.drop
    ow = _open_side(grid, (col - 1, row), level)
    oe = _open_side(grid, (col + 1, row), level)
    if ow and oe:
        foot = _wall_foot(grid, col, row, level, max(1, drop))
        if _open_side(grid, (col, foot + 1), level):
            return "single"
        return "left"
    return "left" if ow else "right" if oe else "mid"


class _Missing:
    kind = ""


_NONE = _Missing()


def _shadow_casts(grid, col, row, c, x, y, px) -> list:
    """The shadow blits this cell contributes: `(bx, by, clip)` entries.

    Stone drops one, unclipped: cliff faces, east/west flights (a cliff stands
    behind those) and the stone-cut vertical staircases, which are structures
    standing on the floor like any wall. A **grass** vertical pathway drops
    none -- it is a channel cut through the wall that you walk down.

    Plain ground drops one per side where a ground tile at a *lower* level lies
    beside it, clipped to that side's cell -- a bare level change with no stone
    in it, which happens wherever a wall jogs away and leaves a flank exposed.
    **Unless anything drops away to the north, in which case it casts nothing
    at all.** A shadow falling north is inconsistent with the rest of the
    lighting, so a plateau's north edge, which is its back, is left clean --
    and so are the corner tiles where such an edge meets a flank. Suppressing
    only the northward half of a corner's shadow and letting it keep its
    sideways one was tried, and still read wrong; the whole tile goes quiet.

    The cost, accepted with the rule: a flank's band starts one tile below the
    top of the flank, that top tile being a corner.

    Clipping a ground caster is cheap here in a way it was not when this pass
    ran after all the ground was painted: the blob's core lands on the caster's
    own cell and is covered by that tile either way, so clipping costs only the
    spill. Lateral bands do thin very slightly -- median coverage 5.27% ->
    5.08% -- because a north-edge caster used to spill sideways onto them as
    well, and those casters are now silent."""
    # Each entry carries the level of the terrace the blob falls *on*. Only
    # the banded painter reads it, and only to choose a surface -- a shadow has
    # to be laid onto the floor it darkens, and stone can drop two levels, so
    # "one below the caster" is not good enough.
    if c.kind == VSTAIR:
        return [(x, y, None, max(0, c.level - c.drop))] if c.tag == "rock" else []
    if c.kind == EWSTAIR and str(c.tag).startswith("side_"):
        # Only the lower of the unit's two tiles casts. Both did at first,
        # which is right for a cliff run -- every cell of it is wall standing
        # the full height -- and wrong here: the upper tile is the ramp's own
        # surface, level with the terrace it leaves, and it is the foot that
        # stands proud of the floor below. `row == drop` is the foot, the same
        # test `walk_links` uses to find the end that opens onto that floor.
        return ([(x, y, None, max(0, c.level - c.drop))]
                if c.row == c.drop else [])
    if c.kind != GROUND:
        return [(x, y, None, max(0, c.level - c.drop))]

    def below(dx, dy):
        nb = grid.get((col + dx, row + dy))
        if nb is not None and nb.kind == GROUND and nb.level < c.level:
            return nb.level
        return None

    # A tile that fringes north casts nothing at all. The rule is older than
    # this line -- a shadow falling north fights the rest of the lighting, so a
    # plateau's back edge and the corners where it meets a flank are left clean
    # -- but it used to ask only whether lower *ground* dropped away north, and
    # a north edge has three other causes: stone, a flight, and open sea. The
    # tile below a lateral crossing's foot is the case that showed it up: its
    # north neighbour is the stair, so the old test saw nothing and let it cast
    # sideways onto the terrace below, which reads as the shade bleeding into
    # the tile next door.
    if "n" in _floor_sides(grid, col, row, c.level):
        return []
    out = []
    for side, dx, dy in _SIDES:
        if side == "n":
            continue
        lvl = below(dx, dy)
        if lvl is not None:
            out.append((x, y, pygame.Rect(x + dx * px, y + dy * px, px, px), lvl))
    return out


def _shade(surf, sheets, casters, px) -> None:
    """Lay the drop shadow between the ground and whatever stands on it.

    Every caster (see `_shadow_casts`) drops the same soft 192px blob, centred on
    itself, so a wall or a plateau flank reads as standing *above* what it
    fronts rather than being painted flat onto it. It goes on after the terrace
    tiles of pass 1 and before the faces of pass 3 -- ground, shadow, stone.

    The blob is a whole tile square and is laid at the caster's *own* cell, not
    beside it. What makes that read as a cast shadow is the order the painter
    works in -- floor by floor, ascending, each level's shadows going down
    between the floor beneath and that level's own tiles. The sprite's core is a
    shade wider than a cell, so it spills a few pixels onto every neighbour;
    the caster's own tile and its same-level neighbours are painted afterwards
    and cover their share, and only the spill onto the floor below -- already
    painted -- survives.

    Stone carries `clip = None` and drops its blob whole. Ground is clipped to
    the side it falls on, which is how the northward half is kept off the
    board; see `_shadow_casts`.

    Accumulated on a scratch layer with `BLEND_RGBA_MAX` rather than blitted
    straight down: the blobs are three cells wide but sit one cell apart, so
    along a continuous run six of them overlap on every tile and normal alpha
    compositing stacks into lumpy over-darkened patches. Taking the per-pixel
    maximum merges the run into one even strip. (The LD-8 band renderer hit
    this and solved it the same way; see `terrain/render.py`.)"""
    shadow = sheets.cliff_shadow
    if shadow is None or not casters:
        return
    half = shadow.get_width() // 2 - px // 2
    scratch = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    for x, y, clip, _dest in casters:
        scratch.set_clip(clip)
        scratch.blit(shadow, (x - half, y - half),
                     special_flags=pygame.BLEND_RGBA_MAX)
    scratch.set_clip(None)
    surf.blit(scratch, (0, 0))


def paint_room_grid(store, sheets, layout, room):
    """`(blit_rect, surface)` for one height-map room, or `None` with no grid.

    The surface can reach further south than the room's own rect: a terrace on
    the room's southern edge grows a wall below it so it is not left floating,
    and that wall hangs into the sea."""
    got = _paint_room(store, sheets, layout, room, banded=False)
    return got[0][:2] if got else None


def paint_room_levels(store, sheets, layout, room):
    """`[(blit_rect, surface, level)]` -- the same island, split into one band
    per terrace so the renderer can interleave sprites between them.

    A band holds a terrace's own ground *and the stone that stands on it*: a
    wall belongs to the terrace it drops onto, not to the one it holds up.
    That is what lets a character at a cliff foot draw over the face in front
    of them while still being covered by the terrace above -- the wall is
    already down when their band is painted, and the higher ground is not.

    Composited in level order this is pixel-identical to `paint_room_grid`,
    which is the property that makes the split safe; `tests/rendering/
    test_level_bands.py` asserts it.
    """
    return _paint_room(store, sheets, layout, room, banded=True)


def _paint_room(store, sheets, layout, room, banded: bool):
    """The one painter behind both entry points above.

    `banded` only decides *which surface* each blit lands on -- never what is
    blitted, or in what order. One implementation rather than two is what keeps
    the banded and unbanded pictures from drifting apart.
    """
    grid = room.grid
    if not grid:
        return []
    px = sheets.px
    cell = sheets.cell
    interior = sheets.interior
    sheet_for = sheets.sheet_for
    cliff_idx = sheets.cliff_idx
    ramp_slots = sheets.ramp_slots
    slots = sheets.slots

    cols = [p[0] for p in grid]
    rows = [p[1] for p in grid]
    c0, r0 = min(cols), min(rows)
    w = (max(cols) - c0 + 1) * px
    h = (max(rows) - r0 + 1) * px

    levels = sorted({c.level for c in grid.values()})
    if banded:
        bands = {lvl: pygame.Surface((w, h), pygame.SRCALPHA) for lvl in levels}
    else:
        one = pygame.Surface((w, h), pygame.SRCALPHA)
        bands = {lvl: one for lvl in levels}

    def band(level):
        """The surface a blit at this terrace lands on. Clamped, because a wall
        can drop below the lowest level any *cell* stands at."""
        if level in bands:
            return bands[level]
        near = min(levels, key=lambda l: abs(l - level))
        return bands[near]

    order = sorted(grid.items(), key=lambda kv: kv[0][1])
    walls = []                       # (col, row, cell, x, y) -- stone to come
    floors: dict = {}                # level -> the ground tiles painted at it
    shadows: dict = {}               # level -> the casters standing at it

    def ground(col, row, level, x, y, under=False, on=None):
        """Paint ground of `level` at this cell -- `under` for the floor that
        runs on beneath a wall."""
        surf = on if on is not None else band(level)
        face = sheet_for(level, room.kind, room)
        idx, wet = _ground_tile(grid, sheets, slots, col, row, level, under,
                                beachless=not sheets.has_shoreline(face))
        if not wet:
            # This tile's fringe faces land, and the fringe art is ragged and
            # part-transparent at that margin. With an empty room surface
            # behind it the world's water buffer shows through the gaps,
            # drawing a blue outline around the tile -- most visible on an
            # upper terrace, where every cell of a rim had one. Lay the floor
            # below behind it: it is what genuinely runs on under the fringe,
            # so the strands sit against grass, not sea.
            surf.blit(cell(sheet_for(max(0, level - 1), room.kind, room),
                           interior),
                      (x, y))
        surf.blit(cell(face, idx), (x, y))

    # --- pass 1: sort every cell into the floor it paints on ---------------
    for (col, row), c in order:
        x, y = (col - c0) * px, (row - r0) * px
        if c.kind == LAKE:
            continue                       # the water buffer shows through

        shadows.setdefault(c.level, []).extend(
            _shadow_casts(grid, col, row, c, x, y, px))

        if c.kind == GROUND:
            floors.setdefault(c.level, []).append((col, row, c.level, x, y,
                                                   False))
            continue

        walls.append((col, row, c, x, y))
        if c.kind == VSTAIR:
            continue                       # a channel you walk down, not stone
        if (c.kind == CLIFF and c.row == c.drop - 1
                and grid.get((col, row + 1)) is None):
            continue                       # hanging over open water, no floor
        # The run-end face variants keep their outer edge transparent, which is
        # the point -- but with nothing behind them that edge would show the sea
        # straight through a wall standing on land. Lay the terrace the wall
        # drops onto underneath it first -- autotiled, not a plain tile: the
        # floor genuinely runs on under the stone, and where it runs out at the
        # water's edge the exposed sliver has to be a shore tile or it reads as
        # grass floating on the sea. Inland it comes out plain anyway, since a
        # floor running under a wall has nothing to fringe against.
        low = max(0, c.level - c.drop)
        floors.setdefault(low, []).append((col, row, low, x, y, True))

    # --- pass 2: floor by floor, each level's shadows under its own tiles ---
    # The order is the whole trick. A shadow square sits at its caster's own
    # cell; laying it after the floor below and before that level's tiles means
    # the caster and its same-level neighbours paint over their share of it and
    # only what falls on the floor beneath is left. Painting all the ground
    # first and all the shadows afterwards cannot do this -- there is nothing
    # left to cover the parts that should not show.
    for lvl in sorted(set(floors) | set(shadows)):
        # A shadow belongs to the terrace it *falls on*, one below its caster,
        # and has to be laid straight onto that floor. Put it on its caster's
        # own band instead and it blends against transparency, so the composite
        # comes out darker than the single-surface picture -- which is exactly
        # what the first banded build did. `band` clamps, so level 0's shade
        # still lands on level 0, ahead of its own tiles, as it always did.
        # Onto the *highest* terrace any of this level's blobs reach. Bands
        # composite in order, so a blob meant for a deeper floor still shows
        # over it from here, while one meant for this terrace would be buried
        # if it were laid any lower. Splitting the group per destination is not
        # an option: `_shade` merges a run with BLEND_RGBA_MAX, and separating
        # it would let two groups alpha-stack into the lumpy over-darkening
        # that trick exists to prevent.
        casts = shadows.get(lvl, ())
        _shade(band(max((c[3] for c in casts), default=lvl - 1)),
               sheets, casts, px)
        target = band(lvl)
        for col, row, level, x, y, under in floors.get(lvl, ()):
            ground(col, row, level, x, y, under, on=target)

    # --- pass 3: the stone itself -----------------------------------------
    tall = []
    for col, row, c, x, y in walls:
        sheet = sheet_for(c.level, room.kind, room)
        low = sheet_for(max(0, c.level - c.drop), room.kind, room)
        # The terrace this stone *stands on*, not the one it holds up. A wall
        # painted with the level above it would cover anything standing at its
        # foot -- which is the one place a character is guaranteed to be.
        surf = band(max(0, c.level - c.drop))

        if c.kind == CLIFF:
            var = _run_var(grid, col, row)
            foot = c.row == c.drop - 1 and grid.get((col, row + 1)) is None
            surf.blit(cell(sheet, cliff_idx("bottom" if foot else "body", var)),
                      (x, y))
        elif c.kind == VSTAIR:
            piece = ramp_slots.get("s", (interior, interior))
            idx = piece[0] if (c.row == 0 and c.drop > 1) else piece[-1]
            surf.blit(cell(sheet if c.row == 0 else low, idx), (x, y))
            if c.tag == "rock" and c.row == 0:
                tall.append((x, y, sheets.vstair_sprite(c.drop), surf))
        elif str(c.tag).startswith("side_"):
            # A lateral crossing: the two-tile ramp unit laid straight onto a
            # plateau's bare side face. Top wedge on row 0, the piece carrying
            # the rocky step on row 1 -- the same pair a wall-cut flight uses,
            # and drawn in this terrace's own material.
            #
            # A lateral crossing casts a drop shadow like any other structure
            # standing on a terrace -- `_shadow_casts` gives it the same
            # unclipped blob at its own cell that a `CLIFF` gets, laid in pass
            # 2 and so under the ramp painted here in pass 3. It was excluded
            # at first, on the reasoning that a side face carries no stone; but
            # the crossing itself stands proud of the floor below it whichever
            # alignment it takes, and without the shade it reads as painted
            # flat onto that floor.
            #
            # The backdrop, and only on the head. A crossing notched *into*
            # the terrace leaves a terrace tile standing directly above it, and
            # that tile drops into the notch -- without its wall drawn the
            # crossing reads as a hole rather than a way down. A crossing that
            # protrudes from the terrace side has nothing above it and takes
            # none. The drop is one level, so one tile of face is the whole
            # wall, which is why the foot never carries it.
            if c.row == 0:
                over = grid.get((col, row - 1))
                if (over is not None and over.kind == GROUND
                        and over.level == c.level):
                    surf.blit(cell(sheet, cliff_idx("body", "single")), (x, y))
            #
            # The side is taken straight from the tag: a crossing that drops
            # east draws `ramp.e`. I had this mirrored at first, reasoning from
            # a one-tile prototype about which way the riser should face; in
            # the finished two-tile unit that puts the ramps facing the wrong
            # way round, which is plain enough on screen.
            piece = ramp_slots.get(c.tag[-1])
            if piece:
                surf.blit(cell(sheet, piece[0] if c.row == 0 else piece[-1]),
                          (x, y))
        else:                                       # EWSTAIR
            # An east/west flight is a notch cut into the wall, not a hole
            # through it, so the **wall stands behind it** -- and that stone is
            # an ordinary cliff face: it takes its left / mid / right / single
            # variant from its neighbours exactly as any other does, so the rim
            # reads as one continuous run straight past the flight. The wedge's
            # own corners are transparent, which is how the stone shows.
            surf.blit(cell(sheet, cliff_idx("body", _run_var(grid, col, row,
                                                             c.level, c.drop))),
                      (x, y))
            piece = ramp_slots.get(c.tag)
            if piece:
                surf.blit(cell(sheet, piece[0] if c.row == 0 else piece[-1]),
                          (x, y))

    # --- pass 4: sprites taller than their cell ---------------------------
    # A drop-2 stone flight is 64x128 and hangs into the row below it, so it has
    # to go on after every one-cell blit -- otherwise the grass of the cell it
    # hangs into paints over its bottom half.
    for x, y, spr, target in tall:
        if spr is not None:
            target.blit(spr, (x, y))

    # Trim each band to what it actually holds. A terrace occupies a fraction
    # of the island's bounding box, and an untrimmed band would cost the whole
    # of it -- the split is only affordable because most of each band is empty.
    out = []
    for lvl in levels:
        surface = bands[lvl]
        if not banded:
            out.append((pygame.Rect(room.rect.x + c0 * px,
                                    room.rect.y + r0 * px, w, h), surface, lvl))
            break
        clip = surface.get_bounding_rect()
        if clip.width <= 0 or clip.height <= 0:
            continue
        out.append((pygame.Rect(room.rect.x + (c0 * px) + clip.x,
                                room.rect.y + (r0 * px) + clip.y,
                                clip.width, clip.height),
                    surface.subsurface(clip).copy(), lvl))
    return out


def paint_bridge(sheets, corridor):
    """`(blit_rect, surface)` for one plank bridge, tiled along its own rect.

    The LD-8 painter derived the span from the two rooms' rects. That no longer
    works: a height-map room's coastline wanders inside its rect, so a bridge
    drawn rect-to-rect stops short and hangs over open water. `_seat_corridors`
    has already stretched the rect coast to coast, so here the rect *is* the
    bridge."""
    px = sheets.px
    rect = corridor.rect
    surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    if not sheets.bridge_ok:
        return rect, surf
    n = max(1, (rect.height if corridor.axis == "v" else rect.width) // px)
    for i in range(n):
        name = autotile.bridge_slot(corridor.axis, i, n)
        tile = sheets.cell(str(sheets.b_sheet),
                           sheets.b_slots.get(name, sheets.b_slots["h_mid"]),
                           sheets.b_cols)
        surf.blit(tile, (0, i * px) if corridor.axis == "v" else (i * px, 0))
    return rect, surf


def grid_shore(room) -> list:
    """Top-left world pixels of this room's cells that face open water or a
    lake -- the anchors the animated foam laps against.

    Any floor counts, not only sea level. An inland pool can sit in a hollow
    ringed entirely by a raised terrace, and restricting this to level 0 left
    exactly those with no moving water at their edge at all."""
    from game import config
    px = config.TILE_PX
    out = []
    for (col, row), c in room.grid.items():
        if c.kind != GROUND:
            continue
        if any((room.grid.get((col + dx, row + dy)) or _NONE).kind in ("", LAKE)
               for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
            out.append((room.rect.x + col * px, room.rect.y + row * px))
    return out
