"""Room-floor and plank-bridge painters.

W4 of `journals/world_refactor.md`. Moved verbatim out of
`GameMap._build_tiles`; the closure-captured locals are now explicit params.

`paint_room(store, sheets, layout, r)` bakes one room's grass `Surface` and
appends shoreline anchors to `store._shore`. It reads `store._cliff_capped`
(the LD-7a set `_build_tiles` fills just before the room pass).

`paint_corridor(sheets, layout, c)` bakes one corridor's plank bridge; it
touches neither `store` nor any run state.
"""
from __future__ import annotations

import pygame

from world.terrain import autotile

_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def paint_room(store, sheets, layout, r) -> pygame.Surface:
    px = sheets.px
    sheet = sheets.sheet_for(r.floor, r.kind)
    raised = r.floor > 0
    mask = r.cells       # always populated by generate_world (W1)
    # LD-5: a ground room autotiles against its cells *plus* any annex
    # (a staircase-unit bottom landing sitting one tile above its top
    # edge), so the edge cell next to a landing drops its foam.
    shape = mask | r.annex
    # SRCALPHA: bitten-out cells stay transparent (foam / water show
    # through), and the autotile edge tiles keep their water-facing alpha
    # (see assets_journal.md T6).
    surf = pygame.Surface(r.rect.size, pygame.SRCALPHA)
    for col, row in mask:
        m = r.tile_meta.get((col, row))
        # LD-2 E1/E10: a ground room autotiles against the foam block;
        # a raised room autotiles against `slots.raised`, whose edges
        # are cliff grass instead of shoreline surf. Both are real
        # authored tiles -- corners included -- so a plateau needs no
        # procedural edge dressing.
        capped = (r.id, col, row) in store._cliff_capped
        if raised and sheets.raised_slots and m is not None:
            idx = sheets.raised_idx(m)
        elif raised:
            idx = sheets.interior
        elif capped:
            # LD-7a: stone hangs directly over this cell -- close its
            # north side so it does not autotile / foam as a shoreline.
            idx = autotile.mask_slot(shape | {(col, row - 1)}, col, row, sheets.slots)
        else:
            idx = autotile.mask_slot(shape, col, row, sheets.slots)
        surf.blit(sheets.cell(sheet, idx), (col * px, row * px))
        if (not raised and not capped
                and any((col + dc, row + dr) not in mask
                        for dc, dr in _NEIGHBOURS)):
            store._shore.append((r.rect.x + col * px, r.rect.y + row * px))
    return surf


def paint_corridor(sheets, layout, c) -> tuple[pygame.Rect, pygame.Surface]:
    """Bake the plank bridge for corridor `c`. It spans mouth to mouth
    and **one tile past each mouth into the room**, so the end-cap tile
    overlaps the room's shoreline tile (the bridge reads as anchored to
    the shore, not falling short of it) -- not buried at the room centres
    the collision rect runs between. Returns the blit rect (differs from
    `c.rect`) and the surface."""
    px = sheets.px
    lo = layout.room(c.room_low).rect
    hi = layout.room(c.room_high).rect
    if c.axis == "h":
        span0, span1 = lo.right - px, hi.left + px   # 1 tile into each room
        ncells = max(2, round((span1 - span0) / px))
        w, h = ncells * px, px
        bx = span0 - (w - (span1 - span0)) // 2      # centre the run
        blit = pygame.Rect(bx, c.rect.y, w, h)
    else:
        span0, span1 = lo.bottom - px, hi.top + px
        ncells = max(2, round((span1 - span0) / px))
        w, h = px, ncells * px
        by = span0 - (h - (span1 - span0)) // 2
        blit = pygame.Rect(c.rect.x, by, w, h)
    fallback_sheet = sheets.sheet_for(layout.room(c.a).floor)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(ncells):
        if sheets.bridge_ok:
            name = autotile.bridge_slot(c.axis, i, ncells)
            tile_surf = sheets.cell(str(sheets.b_sheet),
                                    sheets.b_slots.get(name, sheets.b_slots["h_mid"]),
                                    sheets.b_cols)
        else:
            tile_surf = sheets.cell(fallback_sheet, sheets.interior)
        pos = (i * px, 0) if c.axis == "h" else (0, i * px)
        surf.blit(tile_surf, pos)
    return blit, surf
