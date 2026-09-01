"""Obstacle skins, tree drop-shadows and non-colliding decor scatter.

W5 of `journals/world_refactor.md`. Moved verbatim off `GameMap`; `store` is
the `GameMap`. Reads `store.obstacles`, `store.layout`, `store._point_ok`;
writes `store._decos`, `store._sprite_drop`, `store._tree_shadows`,
`store._room_decor`, `store._void_decor`.
"""
from __future__ import annotations

import random

import pygame

from game import config
from world.gen import biomes


def _tree_routines(terrain) -> tuple:
    """`((fps, phase), ...)` for the tree sway, from `terrain.json`.

    Same shape and the same reason as `foam_routines`: one clock for every
    instance of an animation makes a whole coastline -- or a whole forest --
    breathe in step, which reads as a single object rather than many. Empty
    when nothing is declared, and then a tree keeps its rig's own fps and no
    offset, exactly as before.
    """
    out = tuple((max(0.1, float(r["fps"])), int(r.get("phase", 0)))
                for r in terrain.get("tree_routines", [])
                if float(r.get("fps", 0)) > 0)
    return out


def _routine_of(routines, o):
    """Which routine this tree sways on -- a stable spatial bucket, so two
    trees in one grove differ and a rebake does not reshuffle them.

    Bucketed at half a tile rather than the foam's full tile: trees stand
    closer together than shore patches do (`_TREE_TREE_GAP` is 22 px), and a
    whole-tile bucket would hand a pair in the same tile the same clock.
    """
    key = (int(o.pos.x) // 32) * 31 + (int(o.pos.y) // 32) * 17
    return routines[key % len(routines)]


def build_obstacle_decor(store, a) -> None:
    """Skin each obstacle with a decoration rig scaled to its collider.

    `obstacle_decor.rigs` maps the obstacle kind to a list of interchangeable
    rigs; `Obstacle.variant` (from the run seed) picks one. The rig's frame
    is scaled so its measured `footprint` (content width in source px) covers
    `2 * radius * size_boost` on screen, and its anchor scales to match.
    `obstacle_decor.render_radius` may override the radius used *for drawing*
    per kind, so a kind can keep its sprite size while its collider shrinks
    (trees: small trunk ring, full-size canopy).

    The entry is `(anchor_x, anchor_y, fps, frames, phase)`. `phase` is a frame
    offset and, for a tree, `fps` comes from its `tree_routines` entry rather
    than from the rig -- see `_tree_routines`.

    LD-10: a biome may name its own `trees`, and an obstacle standing on that
    biome indexes its variant into that list instead of the global one. The
    five tree rigs fall into two groups the eye reads immediately -- pines
    (1, 2, 5) and autumn crowns (3, 4) -- and mixing them across a terrace was
    the last thing keeping an island from looking like one place. The biome
    comes off the obstacle, stamped there by the scatter, so nothing is
    re-derived here.
    """
    conf = a.terrain.get("obstacle_decor", {})
    rig_map = conf.get("rigs", {})
    if not rig_map:
        return
    boost = float(conf.get("size_boost", 1.25))
    render_radius = conf.get("render_radius", {})
    store._sprite_drop = {
        kind: float(value)
        for kind, value in conf.get("sprite_drop", {}).items()
    }
    resolved: dict[tuple, tuple | None] = {}      # (rig, size) -> entry | None

    routines = _tree_routines(a.terrain)
    biome_trees = {fam: spec["trees"]
                   for fam, spec in a.terrain.get("biomes", {}).items()
                   if spec.get("trees")}

    for i, o in enumerate(store.obstacles):
        choices = rig_map.get(o.kind)
        if o.kind == "tree":
            choices = biome_trees.get(getattr(o, "biome", ""), choices)
        if not choices:
            continue
        rig = choices[(int(getattr(o, "variant", 1)) - 1) % len(choices)]
        meta = a.rig(rig)
        if not meta:
            continue
        fw, fh = meta["frame"]
        footprint = float(meta.get("footprint") or fw)
        draw_r = float(render_radius.get(o.kind, o.radius))
        scale = (2.0 * draw_r * boost) / footprint
        size = (max(1, round(fw * scale)), max(1, round(fh * scale)))
        key = (rig, size)
        if key not in resolved:
            frs = a.frames(rig, "loop", size=size)
            if not frs:
                resolved[key] = None
            else:
                ax0, ay0 = a.anchor(rig)
                fps = a.fps(rig, "loop") if len(frs) > 1 else 0.0
                resolved[key] = (ax0 * scale, ay0 * scale, fps, frs)
        entry = resolved[key]
        if entry is not None:
            ax, ay, fps, frs = entry
            if o.kind == "tree" and routines and len(frs) > 1:
                fps, phase = _routine_of(routines, o)
            else:
                phase = 0
            store._decos[i] = (ax, ay, fps, frs, phase)

    if config.TERRAIN_SHADOWS:
        build_tree_shadows(store, conf)


def build_tree_shadows(store, conf: dict) -> None:
    """Build one soft round shade patch for every skinned tree obstacle."""
    spec = conf.get("tree_shadow", {})
    rs = float(spec.get("radius_scale", 1.9))
    padding = int(spec.get("radius_padding", 0))
    render_radius = conf.get("render_radius", {})
    color = tuple(spec.get("color", (12, 18, 22)))[:3]
    alpha = int(spec.get("alpha", 66))
    cache: dict[int, pygame.Surface] = {}

    def disc(r: int) -> pygame.Surface:
        if r not in cache:
            surf = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
            # a few concentric fills -> denser at the centre, soft at the rim
            for k in range(4, 0, -1):
                aa = max(1, round(alpha * k / 4 * 0.62))
                pygame.draw.circle(surf, (*color, aa), (r, r), r * k / 4)
            cache[r] = surf
        return cache[r]

    for i, o in enumerate(store.obstacles):
        if o.kind == "tree" and i in store._decos:
            draw_r = float(render_radius.get(o.kind, o.radius))
            r = max(1, round(draw_r * rs) + padding)
            store._tree_shadows[i] = (o.pos.x, o.pos.y, r, disc(r))


def _cell_biomes(room, floor) -> dict:
    """`{(col, row): biome}` for a height-map room's interior cells.

    Empty for a legacy room: no grid, no palette, nothing to key on -- and the
    callers then treat every entry as universal, which is what that world has
    always done.
    """
    if not floor or not room.grid or not room.palette:
        return {}
    out = {}
    for pos in floor:
        cell = room.grid.get(pos)
        if cell is None:
            continue
        sheet = room.palette.get(cell.level)
        if sheet:
            out[pos] = biomes.biome_of(sheet)
    return out


def _terraces(room, floor) -> list:
    """`[(biome, cells)]` -- the room's interior split by the biome standing on
    it. One `(None, floor)` group for a legacy room, which is what keeps that
    world's decor exactly as it was."""
    fam_of = _cell_biomes(room, floor)
    if not fam_of:
        return [(None, floor or [])]
    groups: dict = {}
    for cell in floor:
        groups.setdefault(fam_of.get(cell), []).append(cell)
    return sorted(groups.items(), key=lambda kv: (kv[0] is None, kv[0] or ""))


def _budget_scale(terrain, fam, n_cells, legal) -> float:
    """How far to stretch the authored `per_room` counts on this terrace.

    `per_room` was tuned against LD-8 rooms of ~60 cells and is being applied
    to height-map islands of 700-1000 -- the same mismatch the obstacle scatter
    had before D8 gave it a per-thousand rate, and the reason a terrace could
    render with four pebbles on it. A biome's `decor.per_1000` is that rate: it
    sets the terrace's whole budget, and the authored counts become the
    *weights* by which the legal props share it.

    A biome that declares no rate returns 1.0 and the counts are used as
    written -- a floor, not a default, and the only thing the legacy world
    ever sees.
    """
    spec = (terrain.get("biomes", {}).get(fam, {}).get("decor") if fam else None)
    if not spec or not legal or not n_cells:
        return 1.0
    want = n_cells * float(spec["per_1000"]) / 1000.0
    expect = sum((e.get("per_room", [0, 2])[0] + e.get("per_room", [0, 2])[1]) / 2
                 for e in legal)
    return want / expect if expect > 0 else 1.0


def build_decor_scatter(store, a) -> None:
    """Seeded, non-colliding scenery from `terrain.json` "decorations":
    interior clutter per room + water scenery in the void.

    Deterministic per `(layout.seed, room id / void grid cell)` -- a string
    seed so it is stable regardless of `PYTHONHASHSEED`. These are cosmetic:
    nothing here touches `store.obstacles` or `is_walkable`. A new prop is a
    new rig + a new "decorations" entry, no code. `collision: true` entries
    are handled by world generation (trees, T9), not here.

    LD-10 step 4: an entry may name the `biomes` it belongs to, and is then
    only placed on terraces wearing one of them -- bones on sand, fungi in the
    forest, mossy stone in the wetland. An entry that names none is universal,
    which is the default a new prop gets and what keeps every terrace from
    being able to come out bare. The filter is per **terrace**, not per island:
    a volcanic island can be wetland at the waterline and rock at the summit,
    and the pumpkins have no business up top.

    The same split fixes a density mismatch that predates it: `per_room` was
    authored for LD-8 rooms of ~60 cells and was being applied whole to islands
    of 700-1000, so a terrace could come out with four pebbles on it. A biome's
    `decor.per_1000` now sets each terrace's budget and the authored counts are
    the weights by which its legal props share it.
    """
    reg = a.terrain.get("decorations", [])
    if not reg:
        return
    px = int(a.terrain.get("tile_px", 64))
    resolved: dict[tuple, tuple | None] = {}       # (rig, size) -> entry|None

    def load(rig: str, scale: float):
        meta = a.rig(rig)
        if not meta:
            return None
        fw, fh = meta["frame"]
        size = (max(1, round(fw * scale)), max(1, round(fh * scale)))
        key = (rig, size)
        if key not in resolved:
            frs = a.frames(rig, "loop", size=size)
            if not frs:
                resolved[key] = None
            else:
                ax, ay = a.anchor(rig)
                fps = a.fps(rig, "loop") if len(frs) > 1 else 0.0
                resolved[key] = (frs, ax * scale, ay * scale, fps)
        return resolved[key]
    if store.layout is None:
        return
    seed = store.layout.seed
    room_reg = [e for e in reg if e.get("placement") == "room_interior"
                and not e.get("collision")]
    void_reg = [e for e in reg if e.get("placement") == "void"]

    # --- room interiors: clutter on interior cells, clear of the centre ---
    _ORTHO = ((1, 0), (-1, 0), (0, 1), (0, -1))
    for room in store.layout.rooms:
        rng = random.Random(f"{seed}:{room.id}:decor")
        r = room.rect
        cols, rows = max(3, r.width // px), max(3, r.height // px)
        # clutter only on fully-interior cells (all four neighbours floor),
        # so a pebble never sits on a half-water shoreline / notch-edge tile
        floor = ([c for c in sorted(room.cells)
                  if all((c[0] + dc, c[1] + dr) in room.cells for dc, dr in _ORTHO)]
                 if room.cells else None)
        cx, cy = room.center
        clear_sq = (min(r.width, r.height) * 0.22) ** 2
        placed: list[tuple] = []
        # per-prop minimum separation, kept parallel to `placed` (not stored
        # in the instance tuple -- `_blit_one_decor` unpacks it as a 6-tuple).
        # Between two props the larger of their two `min_gap`s wins, so a
        # small `min_gap` lets flora (mushrooms, flowers) bunch into patches
        # while a default-gap prop (bush, pebble) still holds everything off.
        gaps: list[float] = []
        # One pass per terrace rather than one per island. An island can be
        # wetland at the waterline and rock at the summit, so neither "which
        # props suit this island" nor "how many does it want" is a question
        # with a single answer.
        for fam, where in _terraces(room, floor):
            legal = ([e for e in room_reg
                      if not e.get("biomes") or fam in e["biomes"]]
                     if fam else room_reg)
            k = _budget_scale(a.terrain, fam, len(where), legal)
            for e in legal:
                lo, hi = e.get("per_room", [0, 2])
                entry = load(e["rig"], float(e.get("scale", 1.0)))
                if entry is None:
                    continue
                frs, ax, ay, fps = entry
                my_gap = float(e.get("min_gap", 40))
                for _ in range(round(rng.randint(lo, hi) * k)):
                    for _try in range(6):
                        if where:
                            col, row = rng.choice(where)
                        else:
                            col = rng.randint(1, cols - 2)
                            row = rng.randint(1, rows - 2)
                        x = r.x + col * px + rng.uniform(6, px - 6)
                        y = r.y + row * px + rng.uniform(6, px - 6)
                        if (x - cx) ** 2 + (y - cy) ** 2 < clear_sq:
                            continue
                        if any((x - o.pos.x) ** 2 + (y - o.pos.y) ** 2
                               < (o.radius + 20) ** 2 for o in store.obstacles):
                            continue
                        if any((x - p[4]) ** 2 + (y - p[5]) ** 2
                               < max(my_gap, g) ** 2
                               for p, g in zip(placed, gaps)):
                            continue
                        placed.append((frs, ax, ay, fps, x, y))
                        gaps.append(my_gap)
                        break
        if placed:
            store._room_decor[room.id] = placed

    # --- the void: water scenery on the open water near the play area ----
    if not void_reg:
        return
    weights = [max(0.0, float(e.get("chance", 0.1))) for e in void_reg]
    total = sum(weights)
    if total <= 0:
        return
    if store.layout is not None:
        b = store.layout.bounds
        step = 160
        inset = config.CHUNK_SIZE // 3
        out: list[tuple] = []
        gy = b.y + inset
        while gy < b.bottom - inset and len(out) < 240:
            gx = b.x + inset
            while gx < b.right - inset and len(out) < 240:
                rng = random.Random(f"{seed}:{gx}:{gy}:void")
                if rng.random() < total:
                    x = gx + rng.uniform(0, step)
                    y = gy + rng.uniform(0, step)
                    on_land = store._point_ok(x, y) or any(
                        store._point_ok(x + dx, y + dy)
                        for dx in (-36, 36) for dy in (-36, 36))
                    if not on_land:
                        e = rng.choices(void_reg, weights=weights, k=1)[0]
                        entry = load(e["rig"], float(e.get("scale", 1.0)))
                        if entry is not None:
                            frs, ax, ay, fps = entry
                            out.append((frs, ax, ay, fps, x, y))
                gx += step
            gy += step
        store._void_decor = out
