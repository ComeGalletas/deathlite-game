"""Obstacle / tree / house scatter: what stands on each island, placed on
floor cells and kept clear of every bridge mouth, flight and landing."""
from __future__ import annotations

import pygame

from entities.obstacle import KINDS, Obstacle
from game import config
from world.rules import frontier
from world.rules import biome as biomes
from world.gen.height.graph import walk_links
from world.gen.settings import settings_or_config
from world.layout import VSTAIR, EWSTAIR
from world.gen.tuning import (
    SPECIAL_KINDS, _OBSTACLE_GAP, _TREE_DENSITY_BOOST,
    _TREE_TREE_GAP_GRID, _TREE_THICKET_MIN_GRID, _TREE_THICKET_MAX_GRID,
    _HOUSE_RADIUS, _HOUSE_ROOM_CHANCE,
    _HOUSE_MIN_ROOM_CELLS, _HOUSE_GLOBAL_CAP, _VILLAGE_MIN_ROOM_CELLS,
    _VILLAGE_EXTRA, _VILLAGE_RADIUS,
    _GRID_OBSTACLES_PER_1000, _GRID_PLACE_TRIES, _GRID_CLEAR_RADIUS,
    _GRID_BOSS_CLEAR_RADIUS, _GRID_SPAWN_CLEAR,
)


def _blocks(doors, x: float, y: float, radius: float) -> bool:
    """Does an obstacle of `radius` centred at (x, y) intrude on a keep-clear
    rectangle?

    The test used to be `rect.collidepoint(x, y)` -- the obstacle's *centre*
    against the rect -- which let a rock sit one pixel outside a bridge mouth
    and still put thirty pixels of itself across the only way in. Measured at
    the large navigation class (radius 22, 48 px lattice), between two and six
    obstacles per world did exactly that, and removing just those took one
    sample seed from 6,315 unreachable cells to zero. Testing the circle is the
    whole fix for that class of seal."""
    for d in doors:
        if d.collidepoint(x, y):
            return True
        cx = min(max(x, d.left), d.right)
        cy = min(max(y, d.top), d.bottom)
        if (x - cx) ** 2 + (y - cy) ** 2 < radius * radius:
            return True
    return False


def _keep_clear_pad() -> int:
    """How far outside an island's rect a keep-clear rect can still matter:
    the widest collider any obstacle carries, plus one."""
    return int(max((float(KINDS[k][0]) for k in KINDS), default=0.0)) + 1


def _doors_near(doors, rect, pad: int) -> list:
    """The keep-clear rects that can intersect an obstacle centred inside
    `rect`. `_blocks` tests a disc of at most `pad` px, so a door farther
    than that from the rect cannot block anything on it and need not be
    scanned. Every placement try used to scan the world-wide list -- 2.1 M
    rect tests a build, 27 % of the whole generation."""
    box = rect.inflate(2 * pad, 2 * pad)
    return [d for d in doors if d.colliderect(box)]


def _tree_spacing(room):
    """`(tree_gap, thicket_min, thicket_max)`: canopy spacing, see
    `tuning._TREE_TREE_GAP_GRID`. Read through one helper so the scatter and
    the top-up cannot pick different answers."""
    return (_TREE_TREE_GAP_GRID, _TREE_THICKET_MIN_GRID,
            _TREE_THICKET_MAX_GRID)


def _uphill_ok(room, x: float, y: float, kind: str, reach: dict, px: int) -> bool:
    """May an obstacle of `kind` stand here without its art reaching onto a
    terrace above the one it stands on?

    `reach` is per *kind* rather than per instance because the rig an obstacle
    ends up wearing is drawn in a later pass (`variant`) and depends on the
    biome; see `frontier.obstacle_reach`. Trees are what this is really for --
    a canopy is 256 px tall and reaches some four tiles north of its trunk.
    """
    level = frontier.tile_level(room, x, y, px)
    if level is None:
        return True
    north, west, east = reach.get(kind, (0.0, 0.0, 0.0))
    return frontier.uphill_clear(room, x, y, level, north, west, east, px)


def _radius(kind: str) -> float:
    """The radius `_blocks` should test this obstacle with.

    Zero for `shrub`, which makes `_blocks` fall back to the centre test: it
    rides the weighted pick so the spacing draws stay where they were, but it
    is decoration, dropped before the list is returned, with no entry in
    `KINDS` and nothing to intrude with."""
    entry = KINDS.get(kind)
    return float(entry[0]) if entry else 0.0


def _flight_keepouts(rooms) -> list:
    """Tiles no obstacle may sit on: every height-map flight, and the ground it
    joins at each end.

    A flight is one tile wide and is the *only* route between two terraces, so
    one tree on it or on its landing seals a whole plateau off -- a much worse
    failure than a blocked corner of a room, and one nothing else would catch.

    The tiles are taken straight from `heightmap.walk_links` rather than
    re-derived: it already knows that a straight flight opens north at its head
    and south at its foot, and that an east/west flight also reaches sideways
    because the wall jogs a row across it.
    """
    px = config.TILE_PX
    out = []
    for room in rooms:
        grid = room.grid
        for pos, cell in grid.items():
            if cell.kind not in (VSTAIR, EWSTAIR):
                continue
            for col, row in (pos, *walk_links(grid, pos)):
                out.append(pygame.Rect(room.rect.left + col * px,
                                       room.rect.top + row * px, px, px))
    return out


def _corridor_doorways(rooms, corridors) -> dict:
    """For each room id, the keep-clear rectangle at every bridge mouth: the
    two tiles at each end of the bridge -- the last plank tile and the
    landing tile beyond it -- plus one tile of margin all round. Obstacles
    are never placed inside these, so stepping off a bridge is never into a
    rock.

    Read off the bridge's own rect, not the island's. A bridge is seated
    beach to beach, and an island's coast wanders inside its rect, so the
    rect edge is open water: the mouth used to be computed there, and over
    the four pinned seeds it covered none of the 102 bridge ends while eight
    of them had an obstacle standing on the landing. The rect's two end tiles
    are not symmetric either -- the low end includes its beach tile, the high
    end stops at the beach's edge -- which is why both the end tile and the
    tile beyond it are taken on each side."""
    px = config.TILE_PX
    out: dict[int, list[pygame.Rect]] = {}
    for c in corridors:
        r = c.rect
        if c.axis == "h":
            ends = ((c.room_low, pygame.Rect(r.left - px, r.top, 2 * px, r.height)),
                    (c.room_high, pygame.Rect(r.right - px, r.top, 2 * px, r.height)))
        else:
            ends = ((c.room_low, pygame.Rect(r.left, r.top - px, r.width, 2 * px)),
                    (c.room_high, pygame.Rect(r.left, r.bottom - px, r.width, 2 * px)))
        for rid, door in ends:
            if rid < 0:
                rid = c.a if door.colliderect(rooms[c.a].rect) else c.b
            out.setdefault(rid, []).append(door.inflate(2 * px, 2 * px))
    return out


# The fallback mix for a terrace whose biome declares no `scatter` block.
# `shrub` is decoration -- dropped before the list is returned -- and rides
# the pick only so the spacing draws stay where they were.
_DEFAULT_KINDS = ("tree", "rock", "pillar", "shrub")
_DEFAULT_WEIGHTS = (4, 3, 2, 3)


def _biome_batches(room) -> list:
    """One scatter batch per terrace, mixed for its biome.

    The mix and the density both belong to the biome, not to the room. A rocky
    terrace wants boulders where a forest one wants trunks -- "a rocky layout
    for tilemap_6 needs a lot more rocks than trees" -- and open sand is meant
    to read as open, so it takes 40 attempts per thousand cells against the
    forest's 100. That cannot be decided per room: a volcanic island can wear
    wetland at the waterline, forest above it and rock on top, and the three
    should not scatter alike.

    So the floor is split by level first and each terrace scattered on its own
    terms. `room.palette` is the island's `{level: sheet}`, decided back in
    generation (`world/gen/biomes.py`) -- reading it here rather than
    re-deriving it is what keeps the rocks and the rock tiles on the same
    terrace.

    A terrace whose biome declares no `scatter` block falls back to the default
    mix at `_GRID_OBSTACLES_PER_1000`. That is a floor, not a per-biome
    default: every declared biome carries its own block, and a test says so.
    """
    levels: dict[int, list] = {}
    for pos in room.cells:
        cell = room.grid.get(pos)
        levels.setdefault(cell.level if cell else 0, []).append(pos)
    out = []
    for level in sorted(levels):
        cells = sorted(levels[level])
        sheet = room.palette.get(level)
        mix = biomes.scatter_mix(sheet)
        kinds, weights, per_1000 = mix or (_DEFAULT_KINDS, _DEFAULT_WEIGHTS,
                                           _GRID_OBSTACLES_PER_1000)
        out.append((biomes.biome_of(sheet) if sheet else "", cells, kinds,
                    weights, int(len(cells) * per_1000 / 1000.0)))
    return out


def _biome_at(room, col, row) -> str:
    """The biome of the terrace `(col, row)` stands on -- what an obstacle
    records so the bake can skin it in that biome's trees without working the
    palette out a second time."""
    cell = room.grid.get((col, row)) if room.grid else None
    sheet = (room.palette.get(cell.level)
             if cell is not None and room.palette else None)
    return biomes.biome_of(sheet) if sheet else ""


def _clear_radius(room, start_id, boss_id) -> float:
    """The disc at a room's centre that no obstacle may enter.

    Shared by the scatter and the tree top-up. They used to decide it
    separately and disagreed: the top-up kept the old fraction-of-the-room
    rule even on a height-map island, so a thicket could grow into the arena
    the scatter had just held open.
    """
    special = room.kind in SPECIAL_KINDS
    if room.id == boss_id:
        return _GRID_BOSS_CLEAR_RADIUS           # the arena, kept open
    if room.id == start_id:
        # Not special treatment of the island -- just not dropping a boulder on
        # the pixel the hero materialises at. `GameMap.center` is the start
        # room's centroid and the hero spawns exactly there.
        return _GRID_SPAWN_CLEAR
    # The special-room "keep the interaction space clear" disc is a fraction of
    # the room's own size, which on a height-map island works out at ~460 px --
    # it blanks the entire upper plateau, since that is what sits in the middle
    # of a concentric island. A fixed few tiles is all the altar / shrine needs.
    return _GRID_CLEAR_RADIUS if special else 0.0


def _scatter_obstacles(rooms, corridors, rng, start_id, boss_id,
                       settings=None) -> list:
    """A few convex obstacles per room, placed on floor cells and always clear
    of every corridor doorway (so movement is never blocked). Count scales with
    a room's cell area. **Special** rooms also keep a clear central disc for
    their interaction / fight space; plain `combat` rooms fill freely.
    """
    doorways = _corridor_doorways(rooms, corridors)
    all_doors = [d for slabs in doorways.values() for d in slabs]
    px = config.TILE_PX
    # Imported here rather than at module scope for the reason `KINDS` is: this
    # module stays importable without the asset layer.
    from game.assets import get_assets
    reach = frontier.obstacle_reach(get_assets().terrain)
    # No obstacle on a flight or its landings: a flight is the only way
    # between two terraces, so one rock there seals a plateau off.
    all_doors.extend(_flight_keepouts(rooms))
    pad = _keep_clear_pad()
    out = []

    # Houses first, so the small obstacles below space themselves off a house
    # via the shared `(o.radius + 46)` check.
    if settings_or_config(settings).buildings:
        _scatter_houses(rooms, all_doors, rng, boss_id, out, reach)

    for room in rooms:
        # The start and boss islands scatter like any other. Skipping them
        # outright -- a safe spawn, a clear arena -- left two of nine islands
        # as bare slabs, a fifth of all the land. Each keeps a clear disc
        # instead (`_clear_radius`). Attempts scale with floor area, per
        # terrace, mixed for the terrace's biome.
        tries = _GRID_PLACE_TRIES
        batches = _biome_batches(room)
        r = room.rect
        doors = _doors_near(all_doors, r, pad)
        # Keep the interaction / fight space clear around *both* the shaped-room
        # centroid and the bounding-box centre -- for an L / T room the two can
        # sit a cell or two apart, and a shot-blocker near either reads as
        # "middle of the room".
        centres = ((room.center.x, room.center.y), (r.centerx, r.centery))
        clear = _clear_radius(room, start_id, boss_id)
        # The kind is drawn once per slot rather than again on every retry. A
        # biome's weights are a statement about the *mix*, and re-drawing
        # quietly re-weights it toward whatever is easiest to place: a slot
        # that opens as a tree and fails becomes a boulder, so the terrace
        # ends up with more boulders than the table asks for. The uphill
        # keep-back made that visible rather than causing it -- a canopy
        # reaches four tiles north where a boulder reaches half of one, so
        # trees are rejected far more often. A slot that cannot seat its kind
        # simply goes unfilled, which costs density and keeps the mix honest.
        tree_gap, _tmin, _tmax = _tree_spacing(room)
        for fam, floor, kinds, weights, density in batches:
            for _ in range(density):
                # Kind is drawn before the position either way, so the
                # placement gap can depend on it: tree-next-to-tree keeps only
                # `_TREE_TREE_GAP_GRID` (groves), every other pairing keeps the full
                # `_OBSTACLE_GAP`.
                kind = rng.choices(kinds, weights=weights, k=1)[0]
                for _try in range(tries):
                    if floor:
                        col, row = rng.choice(floor)
                        x = r.left + col * px + rng.uniform(px * 0.28, px * 0.72)
                        y = r.top + row * px + rng.uniform(px * 0.28, px * 0.72)
                    else:
                        x = rng.uniform(r.left + 40, r.right - 40)
                        y = rng.uniform(r.top + 40, r.bottom - 40)
                    if clear and any((x - mx) ** 2 + (y - my) ** 2 < clear ** 2
                                     for mx, my in centres):
                        continue
                    if _blocks(doors, x, y, _radius(kind)):
                        continue
                    # O(1), so it goes ahead of the O(n) spacing sweep below.
                    if not _uphill_ok(room, x, y, kind, reach, px):
                        continue
                    if any((x - o.pos.x) ** 2 + (y - o.pos.y) ** 2
                           < (o.radius + (tree_gap
                                          if kind == "tree" and o.kind == "tree"
                                          else _OBSTACLE_GAP)) ** 2
                           for o in out):
                        continue
                    ob = Obstacle(kind, x, y)
                    ob.biome = fam
                    out.append(ob)
                    break

    # Cosmetic decoration variant per obstacle (see world/map.py). Assigned in a
    # separate pass so placement above is byte-identical to before this existed.
    # Houses already carry a colour/type `variant` from `_scatter_houses`.
    for o in out:
        if o.kind != "house":
            o.variant = rng.randint(1, 4)

    # Global +25% tree top-up, clumped into the existing groves. Runs after the
    # variant pass so every obstacle above keeps its exact `variant` draw.
    _topup_trees(rooms, all_doors, rng, start_id, boss_id, out, reach)

    # Bushes are non-colliding decoration now, not obstacles. They still ride the
    # weighted pick above (and consume a `variant` draw) so the `(radius + gap)`
    # spacing and every downstream RNG value stay byte-identical to when `shrub`
    # was a real obstacle; they are simply dropped from the returned list here.
    # data/terrain.json `decorations` (bush_a..d) scatters the visible bushes.
    return [o for o in out if o.kind != "shrub"]


def _topup_trees(rooms, all_doors, rng, start_id, boss_id, out, reach) -> None:
    """Append `_TREE_DENSITY_BOOST` x the current tree count in extra trees, each
    placed 0.55-1.5 tiles from a randomly chosen existing tree (drawn uniformly
    across the whole world -> a global boost) and kept on that tree's room floor,
    clear of corridor doorways and special-room centre discs. Tree<->tree spacing
    is the tight `_TREE_TREE_GAP_GRID`; everything else keeps `_OBSTACLE_GAP`."""
    if _TREE_DENSITY_BOOST <= 0:
        return
    px = config.TILE_PX
    total = sum(1 for o in out if o.kind == "tree")
    extra = round(_TREE_DENSITY_BOOST * total)
    if extra <= 0:
        return

    # Every existing tree tagged with the room it sits in.
    tagged: list[tuple] = []
    room_clear: dict[int, tuple] = {}
    pad = _keep_clear_pad()
    for room in rooms:
        if not room.cells:
            continue
        rr = room.rect
        cellset = room.cells
        rtrees = [o for o in out if o.kind == "tree"
                  and rr.collidepoint(o.pos.x, o.pos.y)
                  and (int((o.pos.x - rr.left) // px),
                       int((o.pos.y - rr.top) // px)) in cellset]
        if not rtrees:
            continue
        room_clear[room.id] = (
            ((room.center.x, room.center.y), (rr.centerx, rr.centery)),
            _clear_radius(room, start_id, boss_id),
            _doors_near(all_doors, rr, pad))
        for t in rtrees:
            tagged.append((t, room))
    if not tagged:
        return

    placed = 0
    for _ in range(extra * 20):
        if placed >= extra:
            break
        anchor, room = rng.choice(tagged)
        rr = room.rect
        cellset = room.cells
        centres, clear, doors = room_clear[room.id]
        tree_gap, thicket_min, thicket_max = _tree_spacing(room)
        off = pygame.Vector2(rng.uniform(thicket_min, thicket_max), 0)
        off.rotate_ip(rng.uniform(0, 360))
        x, y = anchor.pos.x + off.x, anchor.pos.y + off.y
        col, row = int((x - rr.left) // px), int((y - rr.top) // px)
        if (col, row) not in cellset:
            continue
        if clear and any((x - mx) ** 2 + (y - my) ** 2 < clear ** 2
                         for mx, my in centres):
            continue
        if _blocks(doors, x, y, _radius("tree")):
            continue
        if not _uphill_ok(room, x, y, "tree", reach, px):
            continue
        gap_hit = False
        for o in out:
            gap = tree_gap if o.kind == "tree" else _OBSTACLE_GAP
            if (x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < (o.radius + gap) ** 2:
                gap_hit = True
                break
        if gap_hit:
            continue
        t = Obstacle("tree", x, y)
        t.variant = rng.randint(1, 4)
        # Its own terrace, not the anchor's: a thicket can spill over a step.
        t.biome = _biome_at(room, col, row)
        out.append(t)
        tagged.append((t, room))
        placed += 1


def _scatter_houses(rooms, all_doors, rng, boss_id, out, reach) -> None:
    """One house in ~35% of big rooms (any kind but `boss`), placed off-centre
    and clear of every corridor doorway; a roomy room grows a colour-matched
    village cluster around it. Appends `Obstacle("house", ...)` to `out`."""
    px = config.TILE_PX
    r_h = _HOUSE_RADIUS
    door_pad = int(2 * r_h)
    fat_doors = [d.inflate(door_pad, door_pad) for d in all_doors]
    pad = _keep_clear_pad()
    placed = 0

    for room in rooms:
        if placed >= _HOUSE_GLOBAL_CAP:
            break
        if room.id == boss_id or not room.cells:
            continue
        rr = room.rect
        if min(rr.width, rr.height) < 6 * px or len(room.cells) < _HOUSE_MIN_ROOM_CELLS:
            continue
        doors = _doors_near(fat_doors, rr, pad)
        if rng.random() >= _HOUSE_ROOM_CHANCE:
            continue

        if room.kind == "start":
            keep = max(min(rr.width, rr.height) * 0.25, r_h + 2 * px)
        elif room.kind in SPECIAL_KINDS:
            keep = max(min(rr.width, rr.height) * 0.22, r_h + 2 * px)
        else:
            keep = max(min(rr.width, rr.height) * 0.30, r_h + 2 * px)
        centres = ((room.center.x, room.center.y), (rr.centerx, rr.centery))
        cells = sorted(room.cells)
        cellset = room.cells
        colour = rng.randint(0, 4)              # one colour band per village

        def _spot(near):
            for _try in range(16):
                col, row = rng.choice(cells)
                if any((col + dc, row + dr) not in cellset
                       for dc in (-1, 0, 1) for dr in (-1, 0, 1)):
                    continue                     # keep the house comfortably inland
                x = rr.left + col * px + px * 0.5
                y = rr.top + row * px + px * 0.5
                if any((x - mx) ** 2 + (y - my) ** 2 < keep ** 2
                       for mx, my in centres):
                    continue
                if _blocks(doors, x, y, _radius("house")):
                    continue
                if not _uphill_ok(room, x, y, "house", reach, px):
                    continue
                if near is not None:
                    lo, hi = _VILLAGE_RADIUS
                    if (x - near[0]) ** 2 + (y - near[1]) ** 2 > (hi * px) ** 2:
                        continue
                if any((x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < (2 * r_h) ** 2
                       for o in out if o.kind == "house"):
                    continue
                return x, y
            return None

        first = _spot(None)
        if first is None:
            continue
        used_types = set()
        cluster = [first]

        def _add(pos):
            nonlocal placed
            t = next((k for k in (1, 2, 3) if k not in used_types),
                     rng.randint(1, 3))
            used_types.add(t)
            h = Obstacle("house", pos[0], pos[1])
            h.variant = colour * 3 + (t - 1) + 1        # 1..15
            out.append(h)
            placed += 1

        _add(first)
        if len(room.cells) >= _VILLAGE_MIN_ROOM_CELLS:
            for _ in range(rng.randint(*_VILLAGE_EXTRA)):
                if placed >= _HOUSE_GLOBAL_CAP:
                    break
                spot = _spot(cluster[0])
                if spot is None:
                    break
                cluster.append(spot)
                _add(spot)
