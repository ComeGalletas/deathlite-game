"""Skinning obstacles with decoration rigs.

Obstacles are placed by world generation (`world/gen/scatter.py`); this decides
what each one looks like -- which rig, at what scale, on which animation clock.
Separate from the scatter passes, which place things generation knows nothing
about.
"""
from __future__ import annotations

from game import config
from world.rules import frontier
from world.terrain.decor.shadows import build_tree_shadows


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
    closer together than shore patches do (`_TREE_TREE_GAP_GRID` is 55 px), and a
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

    A biome may name its own `trees`, and an obstacle standing on that
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
    render_scale = conf.get("render_scale", {})
    store.sprite_drop = {
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
        draw_r = float(render_radius.get(o.kind, o.radius))
        scale = frontier.rig_scale(meta, draw_r, boost,
                                   render_scale.get(o.kind))
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
            store.decos[i] = (ax, ay, fps, frs, phase)
            # Where `_draw_one_obstacle` will put the art, in world px: the
            # ghost pass tests characters against these rectangles.
            fw_s, fh_s = frs[0].get_size()
            drop = store.sprite_drop.get(o.kind, config.SPRITE_ANCHOR_DROP) * o.radius
            store.art_rects[i] = (o.pos.x - ax, o.pos.y - ay + drop, fw_s, fh_s)
    store.ghost = dict(conf.get("ghost", {}))

    if config.TERRAIN_SHADOWS:
        build_tree_shadows(store, conf)
