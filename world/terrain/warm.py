"""Scale every small surface a baked world can show, before the run starts
(RND-005).

The renderer scales a surface to the render zoom the first time it is drawn
and caches it by id (`TerrainRenderer._z_surf`). The loading screen already
draws the view round the start position (`LoadingState._warm_steps`), but a
run's first frame lands on an arbitrary animation phase, and an animation's
other frames -- foam, the decor scatter, animated obstacle skins -- were
scaled on the frame that first showed them.

`warm(gm)` walks every surface the renderer can scale **except the terrace
bands** and passes each through `_z_surf` at the current render zoom: about
240 surfaces and ~35 MB a world, in ~14 ms (measured on seeds 35, 7 and 123,
`journals/frame_warmup_journal.md`). The bands are left to the frame that
first shows them: warming every band would add 280-410 MB of scaled surfaces
a world to save a 2-11 ms hitch once per band, and that is the owner's call
(RND-005.D1).
"""
from __future__ import annotations


def scaled_sources(gm) -> list:
    """Every surface the renderer scales through `_z_surf`, bands excepted,
    once each: the water buffer, the foam frames, the bridges and their
    shadows, every frame of the decor scatter (room and void), every frame
    of every obstacle skin, and the tree shadows."""
    out: dict[int, object] = {}

    def add(surf) -> None:
        if surf is not None:
            out[id(surf)] = surf

    add(gm._water_buf)
    for foam in gm._foam or ():
        for frame in foam if isinstance(foam, (list, tuple)) else (foam,):
            add(frame)
    for _rect, surf, _lvl in (*gm._corr_shadows, *gm._corr_surfs):
        add(surf)
    for instances in gm._room_decor.values():
        for inst in instances:
            for frame in inst[0]:
                add(frame)
    for inst in gm._void_decor or ():
        for frame in inst[0]:
            add(frame)
    for entry in gm._decos.values():
        for frame in entry[3]:
            add(frame)
    for shadow in gm._tree_shadows.values():
        add(shadow[3])
    return list(out.values())


def warm(gm) -> int:
    """Scale every source in `scaled_sources` at the current render zoom.
    Returns how many were not cached yet. The render zoom is whatever the
    last draw set it to -- the loading screen's warm ring draws with the
    run's camera zoom first, so this lands in the cache the run will read."""
    renderer = gm.renderer
    cache = gm._blit_cache
    fresh = 0
    for surf in scaled_sources(gm):
        if id(surf) not in cache:
            fresh += 1
        renderer._z_surf(surf)
    return fresh
