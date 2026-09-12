"""Interior clutter: seeded, non-colliding scenery on a room's own floor.

The land half of the decoration scatter; `scatter_water.py` is the other. What
this owns is *placement* -- the rules about where a prop may stand. How many of
them there should be lives in `budget.py`, the frontier rules in
`world/rules/frontier.py`, and the separation test in `world/rules/spacing.py`.

Three objects, because the pass asks three sizes of question. `_Bake` is what
holds for the whole world -- the placement knobs, the rig loader, one index of
every obstacle. `_RoomSite` is one room's state while its clutter is seated:
the disc kept clear at its centre, what has gone down, and the index that
spaces the next one. Between them, `seat` places one registry entry and `spot`
tries six points for one prop. It was a single 135-line function five loops
deep before, which is why "why is this cell rejected" was hard to answer.
"""
from __future__ import annotations

import random

from world.rules import frontier
from world.terrain.decor.budget import _terraces, _tier_scales
from world.terrain.decor.rigs import load_rig
from world.rules.spacing import _Neighbourhood


class _Bake:
    """What every room's clutter is judged by, gathered once for the bake."""

    __slots__ = ("px", "inset", "keepback", "centre_clear", "village_boost",
                 "load", "obstacles", "prop_cell")

    def __init__(self, a, store, place, room_reg, load) -> None:
        self.px = int(a.terrain.get("tile_px", 64))
        self.inset = float(place.get("edge_inset", 6))
        self.keepback = float(place.get("uphill_keepback", 1.0))
        self.centre_clear = float(place.get("centre_clear", 0.0))
        # A village island carries more clutter than the rest (the owner's,
        # 2026-09-12: the edges filled out by about a third). It can afford
        # to: the settlement's own disc is blanked in `_RoomSite`, so every
        # extra prop lands on the ground between the buildings and the shore,
        # which is the part that read as bare lawn.
        self.village_boost = float(place.get("village_boost", 1.0))
        self.load = load
        # One index over every obstacle, built once. Queried with `gap = 0` so
        # the stored `(radius + 20)` is the whole rule, exactly as the scan it
        # replaced.
        self.obstacles = _Neighbourhood(
            max((o.radius for o in store.obstacles), default=0.0) + 20.0)
        for o in store.obstacles:
            self.obstacles.add(o.pos.x, o.pos.y, o.radius + 20.0)
        # The prop index's cell must be at least the widest separation any
        # prop asks for, or a rejecting neighbour could sit outside the nine
        # cells searched.
        self.prop_cell = max((float(e.get("min_gap", 40)) for e in room_reg),
                             default=40.0)


class _RoomSite:
    """One room, while its clutter is being seated."""

    __slots__ = ("room", "rng", "bake", "cols", "rows", "cx", "cy",
                 "clear_sq", "boost", "near", "placed")

    def __init__(self, room, rng, bake: _Bake, village) -> None:
        self.room, self.rng, self.bake = room, rng, bake
        r, px = room.rect, bake.px
        self.cols, self.rows = max(3, r.width // px), max(3, r.height // px)
        self.cx, self.cy = room.center
        # A fixed disc round the island's centre (`centre_clear`, px). A
        # fraction of the room's own size was right for a 60-cell room, but on
        # a 3200 x 1792 island it is a 394 px radius, blanking a 788 px circle
        # out of the middle of every island -- no amount of raising the biome
        # rates would have shown through it.
        self.clear_sq = bake.centre_clear ** 2
        self.boost = 1.0
        if village is not None:
            # A village (HI-2) is designed round its forge: clutter, like the
            # trees, keeps outside the settlement's radius (`Village.radius`),
            # spread round it.
            self.cx, self.cy = village.forge
            self.clear_sq = float(village.radius) ** 2
            self.boost = bake.village_boost
        self.placed: list[tuple] = []
        # Separations live in the index rather than in a list parallel to
        # `placed`: at ground-cover densities the old pairwise scan was the
        # dominant cost of the whole bake. See `_Neighbourhood`.
        self.near = _Neighbourhood(bake.prop_cell)

    def spot(self, where, reach, my_gap):
        """Six tries at a point for one prop: a cell of `where` (or any
        interior cell when the terrace lists none), a point inside it, then the
        tests -- off the centre disc, clear of the frontier and of the terrace
        above, off every obstacle, and `my_gap` from the clutter already
        placed. `(x, y)`, or `None` when six tries found nowhere."""
        room, rng, bake = self.room, self.rng, self.bake
        r, px, inset = room.rect, bake.px, bake.inset
        north, west, east = reach
        for _try in range(6):
            if where:
                col, row = rng.choice(where)
            else:
                col = rng.randint(1, self.cols - 2)
                row = rng.randint(1, self.rows - 2)
            x = r.x + col * px + rng.uniform(inset, px - inset)
            y = r.y + row * px + rng.uniform(inset, px - inset)
            if (x - self.cx) ** 2 + (y - self.cy) ** 2 < self.clear_sq:
                continue
            lvl = frontier.cell_level(room, (col, row))
            if not frontier.frontier_clear(room, x, y, lvl, inset, px):
                continue
            if not frontier.uphill_clear(room, x, y, lvl, north, west, east, px):
                continue
            if bake.obstacles.blocked(x, y):
                continue
            if self.near.blocked(x, y, my_gap):
                continue
            return x, y
        return None

    def seat(self, e, where, scale: float) -> None:
        """As many of registry entry `e` as its share of this terrace's budget
        asks for, each at the first point six tries find. A prop that fits
        nowhere is simply not placed -- that costs density and keeps the mix
        honest, the same rule the obstacle scatter follows."""
        lo, hi = e.get("per_room", [0, 2])
        entry = self.bake.load(e["rig"], float(e.get("scale", 1.0)))
        if entry is None:
            return
        frs, ax, ay, fps = entry
        # How far this rig's art reaches from its anchor. `ax` / `ay` are the
        # scaled anchor, so they *are* the west and north reaches; east is
        # whatever frame is left to the right of it.
        keep = self.bake.keepback
        reach = (ay * keep, ax * keep, (frs[0].get_width() - ax) * keep)
        my_gap = float(e.get("min_gap", 40))
        for _ in range(round(self.rng.randint(lo, hi) * scale)):
            at = self.spot(where, reach, my_gap)
            if at is None:
                continue
            self.placed.append((frs, ax, ay, fps, *at))
            self.near.add(at[0], at[1], my_gap)


def build_decor_scatter(store, a) -> None:
    """Seeded, non-colliding scenery from `terrain.json` "decorations":
    interior clutter per room + water scenery in the void.

    Deterministic per `(layout.seed, room id / void grid cell)` -- a string
    seed so it is stable regardless of `PYTHONHASHSEED`. These are cosmetic:
    nothing here touches `store.obstacles` or `is_walkable`. A new prop is a
    new rig + a new "decorations" entry, no code. `collision: true` entries
    are handled by world generation (trees), not here.

    An entry may name the `biomes` it belongs to, and is then
    only placed on terraces wearing one of them -- bones on sand, fungi in the
    forest, mossy stone in the wetland. An entry that names none is universal,
    which is the default a new prop gets and what keeps every terrace from
    being able to come out bare. The filter is per **terrace**, not per island:
    a volcanic island can be wetland at the waterline and rock at the summit,
    and the pumpkins have no business up top.

    The same split fixes a density mismatch that predates it: `per_room` was
    authored for rooms of ~60 cells and was being applied whole to islands
    of 700-1000, so a terrace could come out with four pebbles on it. A biome's
    `decor.per_1000` now sets each terrace's budget and the authored counts are
    the weights by which its legal props share it.
    """
    reg = a.terrain.get("decorations", [])
    if not reg or store.layout is None:
        return
    resolved: dict[tuple, tuple | None] = {}       # (rig, size) -> entry|None

    def load(rig: str, scale: float):
        return load_rig(a, resolved, rig, scale)

    room_reg = [e for e in reg if e.get("placement") == "room_interior"
                and not e.get("collision")]
    bake = _Bake(a, store, a.terrain.get("decor_placement", {}), room_reg, load)
    villages = {v.room_id: v for v in getattr(store.layout, "villages", ())}
    seed = store.layout.seed

    # --- room interiors: clutter on interior cells, clear of the centre ---
    for room in store.layout.rooms:
        site = _RoomSite(room, random.Random(f"{seed}:{room.id}:decor"), bake,
                         villages.get(room.id))
        # clutter only on fully-interior cells (all four neighbours floor
        # *of the same terrace*), so a pebble never sits on a half-water
        # shoreline, a notch edge, or hard against a level change
        floor = frontier.interior_cells(room)
        # One pass per terrace rather than one per island. An island can be
        # wetland at the waterline and rock at the summit, so neither "which
        # props suit this island" nor "how many does it want" is a question
        # with a single answer.
        for fam, where in _terraces(room, floor):
            legal = ([e for e in room_reg
                      if not e.get("biomes") or fam in e["biomes"]]
                     if fam else room_reg)
            scales = _tier_scales(a.terrain, fam, len(where), legal)
            for e in legal:
                site.seat(e, where, scales.get(e["tier"], 1.0) * site.boost)
        if site.placed:
            store.room_decor[room.id] = site.placed
