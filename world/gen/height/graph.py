"""What connects to what, and whether the grid is legal.

Split out of `world/gen/heightmap.py`. `walk_links` is the authority on
adjacency -- `world/elevation.py` mirrors it at runtime rather than deriving its
own -- and `check_grid` is the list of invariants every generated room has to
satisfy.
"""
from __future__ import annotations

from world.layout import GROUND, CLIFF, VSTAIR, EWSTAIR, LAKE, VOID, WALKABLE_KINDS
from world.gen.height.const import MAX_DROP, MAX_LEVEL

# --- connectivity ---------------------------------------------------------

def walk_links(grid, pos) -> list:
    """Walkable cells reachable from `pos` in one step.

    Ground joins ground of the same level. A straight flight joins the terrace
    directly north of its top cell and the one directly south of its foot. An
    east/west flight joins the upper terrace beside its top cell and the lower
    terrace on the opposite side of its foot -- the entry and exit tiles the
    journal's diagram calls for."""
    cell = grid.get(pos)
    if cell is None or cell.kind not in WALKABLE_KINDS:
        return []
    c, r = pos
    out = []

    def ground(p, level):
        g = grid.get(p)
        if g is not None and g.kind == GROUND and g.level == level:
            out.append(p)

    def stair(p):
        g = grid.get(p)
        if g is not None and g.kind in (VSTAIR, EWSTAIR):
            out.append(p)

    if cell.kind == GROUND:
        for p in ((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)):
            ground(p, cell.level)
        # ... plus any flight whose own end opens onto this cell. Asking the
        # flight keeps the relation symmetric instead of re-deriving it here.
        for p in ((c, r - 1), (c, r + 1), (c - 1, r), (c + 1, r)):
            g = grid.get(p)
            if g is not None and g.kind in (VSTAIR, EWSTAIR) \
                    and pos in walk_links(grid, p):
                out.append(p)
        return out

    # inside a flight: the cell above and below in the same stack
    stair((c, r - 1))
    stair((c, r + 1))
    if cell.kind == VSTAIR:
        if cell.row == 0:
            ground((c, r - 1), cell.level)
        if cell.row == cell.drop - 1:
            ground((c, r + 1), cell.level - cell.drop)
    elif str(cell.tag).startswith("side_"):
        # A lateral crossing on a plateau's bare side face. Both halves of the
        # unit behave the same: the terrace it was cut from lies behind on the
        # entry side, the terrace it descends to in front on the exit side, and
        # the column it sits in carries on above and below so walking the rim
        # past a crossing still works. The two halves link to each other
        # through the `stair` calls above.
        dc = 1 if cell.tag.endswith("e") else -1        # the drop direction
        low = cell.level - cell.drop
        # Head and foot, exactly as a wall-cut flight has them -- and for the
        # same reason. Only the head reaches the terrace above and only the
        # foot the one below; letting the *foot* reach up would put the whole
        # drop one step from the low ground.
        #
        # The head does now touch both terraces, through the low tile north of
        # it. That was the corner-cutting hole for a while: a body could take
        # the diagonal from the low ground to the high ground past the
        # crossing, never standing on it, because `can_step` only asked whether
        # one right-angle detour was open end to end. It asks something else as
        # well now -- `elevation.diagonal_blocked` refuses any diagonal between
        # two ground tiles of different levels, which is where that move was
        # actually wrong -- so the reach is safe and the wall it used to cost
        # is gone.
        #
        # The column also carries on past both ends of the unit, and on a
        # crossing that protrudes from the side what lies there is the *low*
        # terrace. Those two edges are open as well -- a side face has no stone
        # in it, so refusing them walled off open ground. Only a cliff, or
        # nothing at all, still stops you.
        # The head's downhill edge is open too. The ramp's top tile is a
        # diagonal wedge with no art at all along that edge -- the low terrace
        # shows through it -- so the only wall the unit keeps is the foot's
        # uphill flank, which is where the drop is actually drawn.
        # North opens onto the *low* terrace only. Ground at the head's own
        # level above means the crossing is notched into the terrace and a
        # backdrop cliff is painted between them, so that edge is a drawn face
        # and stays shut; the notch is entered from its uphill flank.
        if cell.row == 0:                              # head: the upper end
            ground((c - dc, r), cell.level)
            ground((c, r - 1), low)
            ground((c + dc, r), low)
        # ...and the foot's uphill flank, so the unit may be stepped onto
        # sideways from either terrace at either of its cells. A ramp is a
        # ramp; the flank is drawn, but it is not a wall.
        if cell.row == cell.drop:                      # foot: the lower end
            ground((c + dc, r), low)
            ground((c, r + 1), low)
            ground((c - dc, r), cell.level)
    else:
        # East/west flight. The wall jogs one row across it, so the upper
        # terrace reaches the flight's head from the side the wall has not
        # dropped yet, and the lower terrace meets its foot on the opposite
        # side -- the `= > #` / `# > =` pair in the journal's diagram. The head
        # and foot also open along the column, north onto the terrace above and
        # south onto the one below, exactly as a straight flight does.
        entry = 1 if cell.tag == "w" else -1     # "w" descends west, enters east
        if cell.row == 0:
            ground((c + entry, r), cell.level)
            ground((c, r - 1), cell.level)
        if cell.row == cell.drop:
            ground((c - entry, r), cell.level - cell.drop)
            ground((c, r + 1), cell.level - cell.drop)
    return out




def reachable(grid, start=None) -> set:
    """Every walkable cell reachable from `start` (or the lowest-then-westmost
    walkable cell, which is always on the outer shore)."""
    walk = [p for p, cell in grid.items() if cell.kind in WALKABLE_KINDS]
    if not walk:
        return set()
    if start is None:
        start = min(walk, key=lambda p: (-p[1], p[0]))
    seen = {start}
    stack = [start]
    while stack:
        for nb in walk_links(grid, stack.pop()):
            if nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return seen




def _components(grid) -> list[set]:
    """Walkable cells grouped into connected components, largest first."""
    todo = {p for p, cell in grid.items() if cell.kind in WALKABLE_KINDS}
    out = []
    while todo:
        part = reachable(grid, next(iter(todo)))
        out.append(part)
        todo -= part
    out.sort(key=len, reverse=True)
    return out




def _prune_unreachable(grid) -> None:
    """Drop walkable pockets nothing can reach -- an eroded corner that ended up
    walled off, say. They become void rather than teasing the player with floor
    they cannot stand on."""
    walk = {p for p, cell in grid.items() if cell.kind in WALKABLE_KINDS}
    keep = reachable(grid)
    for p in walk - keep:
        del grid[p]
    # a wall with nothing left above it is not holding anything up
    for p, cell in list(grid.items()):
        if cell.kind == CLIFF and (p[0], p[1] - 1) not in grid:
            del grid[p]


# --- verification ---------------------------------------------------------



# --- verification ---------------------------------------------------------

def check_grid(grid) -> list[str]:
    """Every invariant in the module docstring, as a list of complaints (empty
    when the grid is sound). Used by the tests and the ASCII dumper."""
    bad = []
    for (c, r), cell in grid.items():
        if cell.kind == GROUND:
            if cell.level > 0 and (c, r + 1) not in grid:
                bad.append(f"floating ground at ({c},{r}) level {cell.level}")
            # Only a drop to the *south* needs a wall: that is the face the
            # camera sees. A rise to the north, east or west is the back or
            # flank of a plateau, drawn by the higher terrace's own edge tile.
            south = grid.get((c, r + 1))
            if south is not None and south.kind == GROUND \
                    and south.level < cell.level:
                bad.append(f"level drops {cell.level}->{south.level} south of "
                           f"({c},{r}) with no wall between")
            for p in ((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)):
                nb = grid.get(p)
                if nb is not None and nb.kind == GROUND \
                        and abs(nb.level - cell.level) > MAX_DROP:
                    bad.append(f"levels {cell.level}/{nb.level} touch at "
                               f"({c},{r}) -- more than {MAX_DROP} apart")
        if cell.kind in (VSTAIR, EWSTAIR):
            if cell.drop > MAX_DROP:
                bad.append(f"stair drop {cell.drop} at ({c},{r})")
            # a flight must meet other levels only at its own two ends
            ends = set(walk_links(grid, (c, r)))
            for p in ((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)):
                nb = grid.get(p)
                if (nb is not None and nb.kind == GROUND
                        and nb.level != cell.level and p not in ends):
                    bad.append(f"flight at ({c},{r}) is open to level "
                               f"{nb.level} at its side")
    walk = {p for p, cell in grid.items() if cell.kind in WALKABLE_KINDS}
    if walk and reachable(grid) != walk:
        bad.append(f"{len(walk - reachable(grid))} unreachable walkable cells")
    return bad


_GLYPH = {GROUND: "=", CLIFF: "#", VSTAIR: "0", LAKE: "~"}




def to_ascii(grid) -> str:
    """The grid in the journal's own notation -- the quickest way to eyeball a
    generated room.

    Nothing calls this. It is kept on purpose: the level-design journal writes
    every layout in this notation, so it is the bridge between the grid the code
    builds and the diagrams that explain it, and it is the first thing to reach
    for when a generated room looks wrong."""
    if not grid:
        return ""
    cs = [p[0] for p in grid]
    rs = [p[1] for p in grid]
    lines = []
    for r in range(min(rs), max(rs) + 1):
        line = []
        for c in range(min(cs), max(cs) + 1):
            cell = grid.get((c, r))
            if cell is None:
                line.append(" ")
            elif cell.kind == EWSTAIR:
                line.append(">" if cell.tag == "w" else "<")
            else:
                line.append(_GLYPH.get(cell.kind, "?"))
        lines.append(" ".join(line))
    return "\n".join(lines)
