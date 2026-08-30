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


def build_obstacle_decor(store, a) -> None:
    """Skin each obstacle with a decoration rig scaled to its collider.

    `obstacle_decor.rigs` maps the obstacle kind to a list of interchangeable
    rigs; `Obstacle.variant` (from the run seed) picks one. The rig's frame
    is scaled so its measured `footprint` (content width in source px) covers
    `2 * radius * size_boost` on screen, and its anchor scales to match.
    `obstacle_decor.render_radius` may override the radius used *for drawing*
    per kind, so a kind can keep its sprite size while its collider shrinks
    (trees: small trunk ring, full-size canopy).
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

    for i, o in enumerate(store.obstacles):
        choices = rig_map.get(o.kind)
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
            store._decos[i] = entry

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


def build_decor_scatter(store, a) -> None:
    """Seeded, non-colliding scenery from `terrain.json` "decorations":
    interior clutter per room + water scenery in the void.

    Deterministic per `(layout.seed, room id / void grid cell)` -- a string
    seed so it is stable regardless of `PYTHONHASHSEED`. These are cosmetic:
    nothing here touches `store.obstacles` or `is_walkable`. A new prop is a
    new rig + a new "decorations" entry, no code. `collision: true` entries
    are handled by world generation (trees, T9), not here.
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
        for e in room_reg:
            lo, hi = e.get("per_room", [0, 2])
            entry = load(e["rig"], float(e.get("scale", 1.0)))
            if entry is None:
                continue
            frs, ax, ay, fps = entry
            my_gap = float(e.get("min_gap", 40))
            for _ in range(rng.randint(lo, hi)):
                for _try in range(6):
                    if floor:
                        col, row = rng.choice(floor)
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
