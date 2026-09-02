"""Loading a decoration rig's frames at a given draw scale.

One leaf of the decor package, shared by the room scatter and the water
scatter, which both place from the same `decorations` registry.
"""
from __future__ import annotations


def load_rig(a, resolved: dict, rig: str, scale: float):
    """`(frames, anchor_x, anchor_y, fps)` for a decoration rig at `scale`, or
    `None` when the rig or its art is missing.

    `resolved` is the caller's `(rig, size) -> entry` cache: one scaled copy of
    a prop's frames is shared by every instance of it, which is what keeps a
    few hundred pebbles to a handful of surfaces. Shared with the water scatter
    (`world/terrain/water_decor.py`), which loads from the same registry.
    """
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
