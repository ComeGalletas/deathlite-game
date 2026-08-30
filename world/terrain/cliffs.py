"""The cliff-face and plank-stair painters -- the most-churned terrain code
(LD-1 through LD-7 all landed here).

W4 of `journals/world_refactor.md`. Lifted verbatim out of
`GameMap._build_tiles`; the tileset closures are `sheets.` reads now and the
run-state lists live on `store` (the `GameMap`).

`paint_cliff(store, sheets, layout, r)` bakes the stone face hanging below a
raised room's south rim and returns `(blit_rect, surface, floor)` or `None`.
It appends to `store._cliff_foam`, `store._cliff_shadow`,
`store._cliff_underlay` and `store._ramp_surfs`.

`paint_stair(sheets, layout, st)` bakes a non-ramp `Stair` as a plank bridge
and returns `(blit_rect, surface, high_room_id)`; it reads no run state.
"""
from __future__ import annotations

import pygame

from game import config
from world.terrain import autotile


def paint_cliff(store, sheets, layout, r):
    """LD-2 E2/E7/E8/E10: the stone cliff-face hanging below a raised
    room's south rim, read straight off `Room.tile_meta`. `body` tiles
    hang under each south-rim cell, all in the same `cliff_var` (left /
    mid / right / single -- picked at generation) so the vertical stone
    seam lines up.

    E10: the rim cell itself is **not** drawn here any more. `slots.raised`
    gives `paint_room` the real south-edge tiles (23-26: grass with the
    strand fringe where it meets the drop, and no north fringe), so the
    face starts one row below the rim. That retires E6's crop of the
    `top` merge tile, which only existed because `slots.cliff.top`
    points at the block's *horizontal strip* row (32-35, fringed n+s)
    and its unwanted north fringe had to be cut away.

    E7 / LD-6: no flat teal backfill (its square corners were a boxy
    margin past the rounded run ends and its top edge a horizontal
    line). Tiles are blitted at **native 64 px** size -- E7 scaled them
    64 -> 80 px to force the cores to overlap, but that stretched the
    art toward the transparent side. Instead every interior seam
    between two adjacent rim columns is closed by a half-tile-*offset*
    `mid` patch (a `mid` tile is opaque on both edges, so its core
    straddles the gap); each column is also backed by its own `body`
    variant tiled at a half-tile vertical stagger so the transparent
    gap between stacked face tiles never shows the void through. A run
    end keeps its own left / right / single tile with its void-facing
    outer edge (and the dark outline pixels on it) transparent.

    E8: each column asks `layout.tile_at` what sits directly below its
    foot (`ground_k`, which since E8a samples the column's full width).
    **Void** -> the face runs the full `face_h`, its foot is the foamy
    `bottom` tile (the pale scalloped shoreline art), and -- when the
    foot is clear of any bridge / stair span -- a `_cliff_foam` point
    is seeded so the animated foam laps against it.
    **A tile** (a lower room / bridge / stair) covering the whole
    column -> the face is cut to land flush on that surface and is
    capped with a plain `body` tile (no foam art, no foam point) so the
    stone reads as sunk into the ground, not dropping into water."""
    px = sheets.px
    cell = sheets.cell
    interior = sheets.interior
    sheet_for = sheets.sheet_for
    cliff_slots = sheets.cliff_slots
    cliff_idx = sheets.cliff_idx
    three_sided = sheets.three_sided
    ramp_slots = sheets.ramp_slots

    if not cliff_slots or not r.tile_meta:
        return None
    face_h = max(1, min(r.floor, 2) * int(config.CLIFF_TILES))
    rim = [(c, ro, m.cliff_var) for (c, ro), m in r.tile_meta.items()
           if m.cliff == "top"]
    if not rim:
        return None
    sheet = sheet_for(r.floor)
    lap = px // 2
    surf = pygame.Surface((r.rect.width, r.rect.height + face_h * px),
                          pygame.SRCALPHA)
    run_cols = {c for c, _ro, _v in rim}

    # LD-6: tiles are drawn at **native size** -- E7's 64->80 px scale
    # stretched the art and pushed the run's transparent outer edges
    # further out. Instead the inter-column seam is closed by a
    # half-tile-*offset* `mid` patch on every interior seam (a `mid`
    # tile is opaque on both sides, so its core straddles the gap),
    # while a run end keeps its own `left` / `right` / `single` tile
    # with its transparent outer edge intact.
    def face(idx: int) -> pygame.Surface:
        return cell(sheet, idx)

    def ground_k(col: int, row: int) -> int | None:
        """First step `k` (1..face_h+1) below the rim where the column
        is **fully** covered by real tiles, or `None` if it drops into
        the void.

        E8a: sampled at the column's left edge, centre and right edge,
        not just the centre. Corridor / stair rects are tile-*sized*
        but not aligned to any room's column grid, so a bridge can
        cover half a rim column; a lone centre probe then read
        "grounded", the whole face was dropped, and the uncovered half
        left a strip of void (see the level-design journal, E8a). Every
        probe must agree -- a partially covered column keeps its full
        face, which is free because corridors and stairs are painted
        after the cliff pass and cover it anyway."""
        xs = (r.rect.x + col * px + 2,
              r.rect.x + col * px + px // 2,
              r.rect.x + (col + 1) * px - 3)
        for k in range(1, face_h + 2):
            cy = r.rect.y + (row + k) * px + px // 2
            if all(layout.tile_at(cx, cy) is not None for cx in xs):
                return k
        return None

    # LD-4: a **staircase unit** cut into this band -- 3 columns wide,
    # 2 band rows deep. `meta.ramp` tags the stair's own column and the
    # descent direction; the two landings sit one column out at the top
    # and one column in at the bottom:
    #
    #   band row 0:  # # # > = # #     stair top + top landing (c+d)
    #   band row 1:  # # = > # # #     bottom landing (c-d) + stair
    #
    # `unit[col] = (part, direction, low_room)`.
    unit: dict[int, tuple[str, str, int]] = {}
    if ramp_slots:
        have = {c for c, _r, _v in rim}
        for (c0, ro0), m0 in r.tile_meta.items():
            if not m0.ramp:
                continue
            d = 1 if m0.ramp == "w" else -1
            lo_id = next((st.low_room for st in layout.stairs
                          if st.ramp and st.high_room == r.id), -1)
            unit[c0] = ("stair", m0.ramp, lo_id)
            unit[c0 + d] = ("top", m0.ramp, lo_id)
            unit[c0 - d] = ("bot", m0.ramp, lo_id)
            # LD-5: STRUCT_ANNEX can strip `cliff="top"` from the
            # top-landing column (a landing counts as floor below it),
            # so it may be missing from `rim`. The unit still needs it
            # painted -- add it at the stair's row, plain `mid` face.
            for uc in (c0 + d, c0 - d):
                if uc not in have:
                    rim.append((uc, ro0, "mid"))
                    have.add(uc)
    # bridge / stair spans below the plateau are "sky", not sea -- a
    # cliff foot over one of them gets the foamy tile art but no lapping
    # foam effect (matches E3's foam-free sky bridges).
    dry = [c.rect.inflate(px, px) for c in layout.corridors] \
        + [s.rect.inflate(px, px) for s in layout.stairs]

    body_mid = cell(sheet, cliff_idx("body", "mid"))
    bot_mid = cell(sheet, cliff_idx("bottom", "mid"))

    def south_room(col: int, foot_row: int):
        """LD-7a: the lower room floor **directly south** of a cliff
        foot cell (`foot_row + 1`, centre probe), or `None`. When set,
        one tile of that room's grass is drawn at the foot cell and the
        foot goes plain (no foam)."""
        m = layout.tile_at(r.rect.x + col * px + px // 2,
                           r.rect.y + (foot_row + 1) * px + px // 2)
        if m is not None and m.surface == "room" and m.floor < r.floor:
            return layout.room(m.room_id)
        return None

    unit_paint: list = []      # (x, y, tile) into the lifted ramp surface
    for col, row, var in rim:
        x = col * px
        # a right neighbour in the run to bridge with a `mid` patch --
        # `mid` / `left` variants have one; `right` / `single` are the
        # run's east end and must keep their transparent outer edge.
        seam_r = var in ("mid", "left") and (col + 1) in run_cols
        body = face(cliff_idx("body", var))
        gk = ground_k(col, row)
        grounded = gk is not None
        draw_h = min(face_h, gk - 1) if grounded else face_h
        lower = south_room(col, row + draw_h)
        landed = grounded or lower is not None

        if col in unit:
            part, direction, lo_id = unit[col]
            band0, band1 = (row + 1) * px, (row + 2) * px
            lo_room = layout.room(lo_id) if lo_id >= 0 else None
            # LD-7: the cliff-behind (`mid`, opaque both sides so the
            # crevasse never shows the sea) stays in the cliff surface
            # -- the lowest layer -- but the unit's own walkable tiles
            # (landings + the 1x2 stair piece) are collected into
            # `unit_paint` and lifted into `_ramp_surfs`, so they paint
            # above the room floors and the drop shadow, not under them.
            surf.blit(body_mid, (x, band0))
            surf.blit(bot_mid, (x, band1))
            if part == "stair":
                piece = ramp_slots.get(direction)
                if piece:
                    unit_paint.append((x, band0, cell(sheet, piece[0])))
                    unit_paint.append((x, band0 + px, cell(sheet, piece[1])))
            elif part == "top":
                # top landing -- plateau's own grass, 3-sided: strands
                # face the cut (the +d side) and the band below (s),
                # flat toward the stair and the plateau above.
                opp = "e" if direction == "w" else "w"
                unit_paint.append((x, band0, three_sided(sheet, opp + "s")))
            else:
                # bottom landing -- the low room's grass, 3-sided:
                # strands face the cut (the -d side) and the band above
                # (n), flat toward the stair and the low room below.
                lsheet = (sheet_for(lo_room.floor, lo_room.kind)
                          if lo_room is not None else sheet)
                cut = "w" if direction == "w" else "e"
                unit_paint.append((x, band1, three_sided(lsheet, cut + "n")))
            continue

        if draw_h >= 1:
            # opaque underlay, half-tile staggered vertically so no row
            # seam shows the void; and -- on an interior seam -- a
            # half-tile-offset `mid` patch whose opaque core straddles
            # the col / col+1 gap. E10: starts flush at the rim cell's
            # bottom edge.
            y = (row + 1) * px
            while y <= (row + draw_h) * px - lap:
                surf.blit(body, (x, y))
                if seam_r:
                    surf.blit(body_mid, (x + lap, y))
                y += lap
            # crisp layer: correct left / mid / right / single edges.
            last = draw_h if landed else draw_h - 1
            for i in range(1, last + 1):
                surf.blit(body, (x, (row + i) * px))
                if seam_r:
                    surf.blit(body_mid, (x + lap, (row + i) * px))
            if not landed:
                # E8 void foot: foamy shoreline tile, + lapping foam
                # unless the foot hangs over a bridge / stair span.
                fy_row = (row + draw_h) * px
                surf.blit(face(cliff_idx("bottom", var)), (x, fy_row))
                if seam_r:
                    surf.blit(bot_mid, (x + lap, fy_row))
                fx = r.rect.x + col * px
                fy = r.rect.y + fy_row
                if not any(d.collidepoint(fx + px // 2, fy + px // 2)
                           for d in dry):
                    store._cliff_foam.append((fx, fy))
            else:
                # LD-6/7a: the foot lands on something -- the plain
                # `body` foot is already drawn (`last == draw_h`), and
                # no `_cliff_foam` is seeded. When a lower room floor is
                # directly south of the foot cell, draw one tile of that
                # room's grass at the foot cell (LD-7a underlay pass,
                # before the cliffs) and a drop shadow immediately above
                # it. A foot grounded only on a bridge / stair gets the
                # plain cap and nothing else.
                fx = r.rect.x + col * px
                fy = r.rect.y + (row + draw_h) * px
                if lower is not None:
                    store._cliff_underlay.append(
                        (pygame.Rect(fx, fy, px, px),
                         cell(sheet_for(lower.floor, lower.kind),
                              interior)))
                    store._cliff_shadow.append((fx, fy))
    # LD-7: lift the staircase unit's own tiles into a small surface
    # drawn in the walkable-structure layer (above the drop shadow)
    # rather than baked into the cliff surface. The cliff-behind `mid`
    # fill was already blitted into `surf` above, so the crevasse never
    # shows the sea.
    if unit_paint:
        minc = min(unit)
        ux0 = minc * px
        uy0 = min(uy for _ux, uy, _t in unit_paint)
        uw = (max(unit) - minc + 1) * px
        uh = max(uy for _ux, uy, _t in unit_paint) + px - uy0
        usurf = pygame.Surface((uw, uh), pygame.SRCALPHA)
        for ux, uy, tile in unit_paint:
            usurf.blit(tile, (ux - ux0, uy - uy0))
        store._ramp_surfs.append(
            (pygame.Rect(r.rect.x + ux0, r.rect.y + uy0, uw, uh),
             usurf, r.floor))
    blit = pygame.Rect(r.rect.x, r.rect.y,
                       r.rect.width, r.rect.height + face_h * px)
    return blit, surf, r.floor


def paint_stair(sheets, layout, st):
    """LD-5: a non-ramp `Stair` is a **plank bridge** over the gap
    between its two rooms, exactly like a corridor -- mouth to mouth
    plus one tile into each room, `width_tiles` strips side by side.
    (It used to be a bare grass strip in the high room's sheet, which
    drew in the wrong palette against whichever room it did not
    belong to.)"""
    px = sheets.px
    cell = sheets.cell
    interior = sheets.interior
    sheet_for = sheets.sheet_for
    bridge_ok = sheets.bridge_ok
    b_sheet = sheets.b_sheet
    b_cols = sheets.b_cols
    b_slots = sheets.b_slots

    lo = layout.room(st.low_room).rect
    hi = layout.room(st.high_room).rect
    n = max(1, int(st.width_tiles))
    if st.axis == "h":
        (a, b) = sorted((lo, hi), key=lambda r: r.centerx)
        span0, span1 = a.right - px, b.left + px
        ncells = max(2, round((span1 - span0) / px))
        w, h = ncells * px, n * px
        bx = span0 - (w - (span1 - span0)) // 2
        by = st.rect.centery - h // 2
    else:
        (a, b) = sorted((lo, hi), key=lambda r: r.centery)
        span0, span1 = a.bottom - px, b.top + px
        ncells = max(2, round((span1 - span0) / px))
        w, h = n * px, ncells * px
        bx = st.rect.centerx - w // 2
        by = span0 - (h - (span1 - span0)) // 2
    blit = pygame.Rect(bx, by, w, h)
    fallback = sheet_for(layout.room(st.high_room).floor)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(ncells):
        if bridge_ok:
            name = autotile.bridge_slot(st.axis, i, ncells)
            tsurf = cell(str(b_sheet), b_slots.get(name, b_slots["h_mid"]),
                         b_cols)
        else:
            tsurf = cell(fallback, interior)
        for k in range(n):
            pos = ((i * px, k * px) if st.axis == "h"
                   else (k * px, i * px))
            surf.blit(tsurf, pos)
    return blit, surf, st.high_room
