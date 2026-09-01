"""Stacking the plateaus: each cap is the one below it, eroded inward.

Split out of `world/gen/heightmap.py`. The asymmetry in `_cap` is what makes a
mountain rather than a dome, and `_carve_canyons` is what stops the north of an
island having no way up.
"""
from __future__ import annotations

from world.gen.height.const import (
    _NB, CAP_INSET_S, CAP_INSET_N, CAP_INSET_W, CAP_INSET_E, CAP_ROUGHNESS,
    MIN_CAP_CELLS, CANYONS, CANYON_DEPTH, CANYON_WIDTH,
)
from world.gen.height.coast import _despike, _one_piece

def _all_neighbours_in(p, cells) -> bool:
    return all((p[0] + dx, p[1] + dy) in cells
               for dx, dy in _NB)




def _cap(below: frozenset, rng, inset=None, roughness: float = None
         ) -> frozenset:
    """The next plateau up: `below` eroded inward, harder from the south than
    the north, then roughened.

    The asymmetry is what makes a mountain rather than a dome -- each cap hugs
    the island's back, so the rims stack into a slope facing the camera. The
    roughening then keeps the rim from reading as a smooth contour line.

    `inset` is `(south, north, west, east)`; `roughness` the chance a rim cell
    is nibbled off. Both come from `game.config` (`HEIGHTMAP_CAP_*`)."""
    if not below:
        return frozenset()
    s, n, w, e = inset or (CAP_INSET_S, CAP_INSET_N, CAP_INSET_W, CAP_INSET_E)
    rough = CAP_ROUGHNESS if roughness is None else roughness
    keep = set()
    for p in below:
        c, r = p
        if all((c, r + k) in below for k in range(1, s + 1)) \
                and all((c, r - k) in below for k in range(1, n + 1)) \
                and all((c - k, r) in below for k in range(1, w + 1)) \
                and all((c + k, r) in below for k in range(1, e + 1)):
            keep.add(p)
    # roughen: nibble the rim in a few places and let a few nubs stand proud
    edge = [p for p in keep if not _all_neighbours_in(p, keep)]
    for p in edge:
        if rng.random() < rough:
            keep.discard(p)
    return _despike(keep) if keep else frozenset()




def _carve_canyons(cap: frozenset, rng, count: int = None, depth=None,
                   width=None) -> frozenset:
    """Cut canyons up into a plateau from its southern rim.

    A south-facing wall only exists where the level *drops* going south, and
    around a concentric cap that is the southern arc alone -- which is why the
    north of an island ends up with no way up. A canyon fixes that at the
    source: it is a finger of lower ground reaching north into the cap, and its
    **head** is a south-facing wall sitting deep in the northern half. Its
    flanks face east and west, so they stay open ground.

    It also breaks a big cap into lobes, which stops the upper floors reading
    as one unbroken slab."""
    count = CANYONS if count is None else count
    depth = depth or CANYON_DEPTH
    width = width or CANYON_WIDTH
    keep = set(cap)
    if not keep:
        return cap
    for _ in range(count):
        rim = [p for p in keep if (p[0], p[1] + 1) not in keep]
        if not rim:
            break
        c, r = rim[rng.randrange(len(rim))]
        cut = set()
        w = rng.randint(*width)
        for step in range(rng.randint(*depth)):
            row = r - step
            here = {(c + dx, row) for dx in range(-(w // 2), w - w // 2)}
            if not (here & keep):
                break
            cut |= here
            c += rng.choice((-1, 0, 0, 1))          # let it meander
        # Step the head. Left flat, a canyon's head is a short level run of
        # wall, and a level run only ever fits a *straight* flight -- an
        # east/west one needs the wall a row lower on one side than the other.
        # Pushing a single column of the head one row further north creates
        # exactly that jog, which is what lets side stairs appear up here at
        # all. Without it the northern half gets straight flights and nothing
        # else.
        if cut:
            head = min(r for _c, r in cut)
            at_head = [cc for cc, rr in cut if rr == head]
            lean = min(at_head) if rng.random() < 0.5 else max(at_head)
            cut.add((lean, head - 1))
        trial = keep - cut
        if trial and _one_piece(trial) and len(trial) >= MIN_CAP_CELLS:
            keep = trial
    return frozenset(keep)


