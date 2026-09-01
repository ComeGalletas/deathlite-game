"""The LD-8 world: frozen, kept for reference only.

Before LD-9 an island was *one* `floor` integer with a cliff band hanging off
its south rim, and the terrain was painted by stitching that band to the room
and corridor surfaces. LD-9 replaced the model outright: a room is a per-cell
height map now, and `world/terrain/grid_paint.py` renders it in a single pass
with no band, underlay, drop shadow or ramp collection to stitch.

The old generator still runs -- `config.HEIGHTMAP_ROOMS = False` selects it, and
a dozen pinned-seed test modules describe it seed by seed, which is why it was
frozen rather than deleted. Everything here is reached only through that flag:

    verticality.py       floor assignment, ramp planning, the cliff-band carve
                         and the per-tile metadata pass
    terrain_rooms.py     `paint_room` / `paint_corridor` -- the flat painters
    terrain_cliffs.py    `paint_cliff` / `paint_stair` -- the band painters

**Nothing new should import from here.** It is collected in one package so the
live code stops interleaving with it: every change this session that touched
generation needed a gate (`scatter._radius`, `repair.unseal`,
`tuning.special_kinds`) precisely because the two models shared files.
"""
