"""The village island's own props (`world/gen/village/`): the biome
scatter outside the settlement, the fill sweep over what it left empty,
and the tree top-up that deepens the groves.
"""
from __future__ import annotations

import math

from entities.obstacle import KINDS, Obstacle
from world.gen.tuning import (
    _DIRS, _GRID_OBSTACLES_PER_1000, _TREE_THICKET_MAX_GRID, _TREE_THICKET_MIN_GRID, _V_FILL_BAND, _V_FILL_CHANCE, _V_FILL_GAP, _V_FILL_INNER, _V_SCATTER_GAP, _V_SCATTER_SCALE, _V_SCATTER_TREES, _V_TREE_GAP, _V_TREE_TOPUP,
)
from world.rules import biome as biomes
from world.gen.village.site import _Site


def _scatter(site: _Site, pen=None) -> None:
    """The village island's own obstacle scatter (`world/gen/scatter.py`
    passes over the island). Same mix as the biome's, `_V_SCATTER_SCALE`
    of its density, same rules as every other village circle plus a wider
    gap to the buildings, and only outside the settlement disc so its centre
    stays open."""
    room, rng, px = site.room, site.rng, site.px
    sheet = room.palette.get(room.floor) if room.palette else None
    mix = biomes.scatter_mix(sheet)
    kinds, weights, per_1000 = mix or (("tree", "rock", "pillar"), (4, 3, 2),
                                       _GRID_OBSTACLES_PER_1000)
    # Only obstacle kinds, filtered once before the draw rather than tested on
    # every one. Nothing is filtered today -- `shrub` left the biome mixes with
    # B3 -- but the mix is data, and a draw this pass cannot place would
    # otherwise reach `KINDS[kind]` and raise.
    kinds, weights = zip(*[(k, w * (_V_SCATTER_TREES if k == "tree" else 1.0))
                           for k, w in zip(kinds, weights) if k in KINDS])
    fam = biomes.biome_of(sheet) if sheet else ""
    cells = sorted(room.cells)
    fx, fy = site.forge
    keep_sq = site.settlement ** 2
    pen_keep = pen.inflate(4 * px, 4 * px) if pen is not None else None
    tries = int(len(cells) * per_1000 * _V_SCATTER_SCALE / 1000.0)
    for _ in range(tries):
        kind = rng.choices(kinds, weights=weights, k=1)[0]
        col, row = rng.choice(cells)
        x = room.rect.left + col * px + rng.uniform(px * 0.28, px * 0.72)
        y = room.rect.top + row * px + rng.uniform(px * 0.28, px * 0.72)
        if (x - fx) ** 2 + (y - fy) ** 2 < keep_sq:
            continue                    # inside the settlement
        if pen_keep is not None and pen_keep.collidepoint(x, y):
            continue                    # a canopy over the sheep
        if not site.prop_fits(kind, x, y, _V_SCATTER_GAP):
            continue                    # a canopy over the hall
        o = Obstacle(kind, x, y, rng.randint(1, 4))
        o.biome = fam
        site.placed.append(o)
def _edge_distance(cells) -> dict:
    """Tiles from the shore, per walkable cell: 1 on the coast itself, then
    inward. A plain breadth-first walk from every cell that has a
    non-walkable orthogonal neighbour -- the island is a couple of hundred
    cells, so this costs nothing and saves the fill sweep from guessing at
    "outside" with a radius from the middle, which on a ragged island is not
    the same thing at all."""
    cells = set(cells)
    frontier = [c for c in cells
                if any((c[0] + dx, c[1] + dy) not in cells for dx, dy in _DIRS)]
    out = {c: 1 for c in frontier}
    d = 1
    while frontier:
        d += 1
        nxt = []
        for col, row in frontier:
            for dx, dy in _DIRS:
                n = (col + dx, row + dy)
                if n in cells and n not in out:
                    out[n] = d
                    nxt.append(n)
        frontier = nxt
    return out
def _fill_scatter(site: _Site, pen=None) -> None:
    """The second decoration sweep (the owner's, 2026-09-12): once the
    village stands, fill what is left of the island -- chiefly its outside.

    The first scatter throws `tries` darts at random cells, which leaves the
    coverage to luck and the shore half bare. This walks every walkable cell
    in order and offers the empty ones a prop, at `_V_FILL_CHANCE` within
    `_V_FILL_BAND` tiles of the shore and a fraction of that further in. The
    mix is the island's own biome again, trees weighted as before, so the
    two sweeps read as one meadow; `_V_FILL_GAP` is the spacing that keeps
    it open ground rather than a wood. Everything the first sweep keeps
    clear -- the settlement's radius, the pen, the roads, the bridge
    mouths, the coast pad, the three protected boxes -- this keeps clear
    too, through the same tests.
    """
    room, rng, px = site.room, site.rng, site.px
    sheet = room.palette.get(room.floor) if room.palette else None
    mix = biomes.scatter_mix(sheet)
    kinds, weights, _per_1000 = mix or (("tree", "rock", "pillar"), (4, 3, 2),
                                        _GRID_OBSTACLES_PER_1000)
    # Only obstacle kinds, as in `_scatter` above: a sweep that visits each
    # cell once must not spend a cell on a draw it cannot place.
    kinds, weights = zip(*[(k, w * (_V_SCATTER_TREES if k == "tree" else 1.0))
                           for k, w in zip(kinds, weights) if k in KINDS])
    fam = biomes.biome_of(sheet) if sheet else ""
    edge = _edge_distance(room.cells)
    fx, fy = site.forge
    keep_sq = site.square ** 2
    pen_keep = pen.inflate(4 * px, 4 * px) if pen is not None else None
    for col, row in sorted(room.cells):
        chance = (_V_FILL_CHANCE if edge.get((col, row), 99) <= _V_FILL_BAND
                  else _V_FILL_CHANCE * _V_FILL_INNER)
        if rng.random() >= chance:
            continue
        kind = rng.choices(kinds, weights=weights, k=1)[0]
        x = room.rect.left + col * px + rng.uniform(px * 0.28, px * 0.72)
        y = room.rect.top + row * px + rng.uniform(px * 0.28, px * 0.72)
        if (x - fx) ** 2 + (y - fy) ** 2 < keep_sq:
            continue                    # the village square
        if pen_keep is not None and pen_keep.collidepoint(x, y):
            continue                    # a canopy over the sheep
        if not site.prop_fits(kind, x, y, _V_FILL_GAP):
            continue
        o = Obstacle(kind, x, y, rng.randint(1, 4))
        o.biome = fam
        site.placed.append(o)
def _grow_trees(site: _Site, pen=None) -> None:
    """`_V_TREE_TOPUP` more trees, each grown beside one already standing.

    The owner asked for four more trees a village (2026-09-12). Adding them
    to the fill sweep's chance would have sprinkled them over the whole
    island; this is the world scatter's own move (`_topup_trees`) at village
    scale -- pick a tree, step `_TREE_THICKET_MIN_GRID` to
    `_TREE_THICKET_MAX_GRID` px off it, and plant there -- so what a village
    gains is a deeper grove rather than a lawn dotted with trunks. Tree to
    tree the spacing is `_V_TREE_GAP`; to everything else it is the fill
    sweep's, and the square, the pen, the roads, the bridge mouths, the
    coast pad and the three protected boxes are kept exactly as before.
    """
    room, rng, px = site.room, site.rng, site.px
    if _V_TREE_TOPUP <= 0:
        return
    fam = ""
    sheet = room.palette.get(room.floor) if room.palette else None
    if sheet:
        fam = biomes.biome_of(sheet)
    fx, fy = site.forge
    keep_sq = site.square ** 2
    pen_keep = pen.inflate(4 * px, 4 * px) if pen is not None else None
    # Gathered once and appended to as the grove grows, rather than rebuilt
    # on each try: `site.placed` only ever gains trees from here, so the list
    # this walks is the same one the rebuild produced.
    trees = [o for o in site.placed if o.kind == "tree"]
    if not trees:
        return
    grown = 0
    for _ in range(_V_TREE_TOPUP * 30):
        if grown >= _V_TREE_TOPUP:
            return
        anchor = rng.choice(trees)
        a = rng.uniform(0.0, 2 * math.pi)
        d = rng.uniform(_TREE_THICKET_MIN_GRID, _TREE_THICKET_MAX_GRID)
        x, y = anchor.pos.x + math.cos(a) * d, anchor.pos.y + math.sin(a) * d
        col = int((x - room.rect.left) // px)
        row = int((y - room.rect.top) // px)
        if (col, row) not in room.cells:
            continue                    # off the island
        if (x - fx) ** 2 + (y - fy) ** 2 < keep_sq:
            continue                    # the village square
        if pen_keep is not None and pen_keep.collidepoint(x, y):
            continue                    # a canopy over the sheep
        if not site.prop_fits("tree", x, y, _V_FILL_GAP):
            continue
        o = Obstacle("tree", x, y, rng.randint(1, 4))
        o.biome = fam
        site.placed.append(o)
        trees.append(o)
        grown += 1
