"""`TileSheets` -- the adapter over `data/terrain.json`'s tileset metadata plus
the per-bake tile cache.

W2 of `journals/world_refactor.md`. `GameMap._build_tiles` used to hold this as
nine closures capturing ~15 locals, which is why the room / corridor / cliff /
stair painters could not move out of `world/map.py`. One `TileSheets` instance
is built per bake and handed to every painter.

Reads (through the assets handle): `terrain["tile_px"]`, `["floor_sheet"]`,
`["floor_sheets"]`, `["room_palettes"]`, `["slots"]` (incl. `["cliff"]`,
`["raised"]`, `["ramp"]`), `["bridge"]`. Owns the tile-surface cache and the
synthesised 3-sided-grass cache. Writes nothing back.
"""
from __future__ import annotations

import pygame


class TileSheets:
    def __init__(self, assets) -> None:
        t = assets.terrain
        self._a = assets

        self.px = int(t.get("tile_px", 64))
        self.floor_sheet = t.get("floor_sheet")
        self.slots = t.get("slots", {})
        self.interior = self.slots.get("interior", 10)
        self.palettes = t.get("room_palettes", {})
        # LD-2 E1: elevation grass sheets (same slot layout). JSON keys -> int.
        self.floor_sheets = {int(k): v for k, v in t.get("floor_sheets", {}).items()}

        # LD-2 E2: cliff autotile slots (left / mid / right / single x top /
        # body / bottom). LD-2 E10: `slots.raised` -- the sheet's second 16-tile
        # autotile block, keyed by exposed sides. LD-3 R4: ramp pieces keyed by
        # descent direction -> [top, bottom].
        self.cliff_slots = self.slots.get("cliff", {})
        self.raised_slots = {k: int(v) for k, v in self.slots.get("raised", {}).items()}
        self.ramp_slots = {k: [int(i) for i in v]
                           for k, v in self.slots.get("ramp", {}).items()}
        # LD-8a: the rock north/south staircase overlay (`vstairs.png`, one
        # 192x128 SRCALPHA sprite -- ~1-tile stone core + a foliage wing each
        # side). Drawn on top of all terrain for a `Stair.style == "rock"` unit;
        # a `"grass"` unit renders the biome `ramp` tiles instead.
        self.vstair = t.get("vstair", {})

        # Bridge tiles for corridors / plank stairs (own sheet + grid).
        bridge = t.get("bridge", {})
        self.b_sheet = bridge.get("sheet")
        self.b_cols = int(bridge.get("grid", [3, 4])[0])
        self.b_slots = bridge.get("slots", {})

        self._cell_cache: dict[tuple, pygame.Surface] = {}
        self._three_cache: dict[tuple, pygame.Surface] = {}
        self.probe = (assets.tile(self.floor_sheet, self.interior)
                      if isinstance(self.floor_sheet, str) else None)
        self.bridge_ok = (
            self.b_sheet is not None and "h_mid" in self.b_slots
            and assets.tile(self.b_sheet, self.b_slots["h_mid"],
                            cols=self.b_cols) is not None)

    @property
    def ok(self) -> bool:
        """The tileset loaded -- `_build_tiles` bails to the flat renderer
        otherwise (a missing `floor_sheet` or an unreadable probe tile)."""
        return isinstance(self.floor_sheet, str) and self.probe is not None

    def cell(self, sheet: str, idx: int, cols: int | None = None) -> pygame.Surface:
        key = (sheet, idx, cols)
        if key not in self._cell_cache:
            self._cell_cache[key] = self._a.tile(sheet, idx, cols=cols) or self.probe
        return self._cell_cache[key]

    def sheet_for(self, floor: int, kind: str = "") -> str:
        """Grass sheet for a room / stair: an elevation sheet for a raised
        floor, otherwise the kind palette (or the ground sheet)."""
        if floor > 0 and floor in self.floor_sheets:
            return self.floor_sheets[floor]
        return self.palettes.get(kind, self.floor_sheet)

    def cliff_idx(self, row: str, edge: str) -> int:
        rs = self.cliff_slots.get(row, {})
        return rs.get(edge, rs.get("mid", self.interior))

    def raised_idx(self, m) -> int:
        """Autotile slot for a raised room's cell, from its metadata.

        LD-3: a cell a ramp run starts at drops its **south** side -- the run's
        grass has to flow off the plateau there, and an `s` edge tile would cut
        a cliff fringe straight across the top of the ramp."""
        south = bool(m.cliff) and not m.ramp
        sides = "".join(d for d in "nswe"
                        if (d == "s" and south) or (d != "s" and d in m.lip))
        return self.raised_slots.get(sides, self.raised_slots.get("", self.interior))

    @property
    def cliff_shadow(self) -> pygame.Surface | None:
        """The soft drop shadow a cliff casts on whatever it stands on.

        One 192x192 sprite (the `terrain_shadow` rig -- a ~1-tile blob with a
        feathered bleed into the ring of cells around it), shared with the LD-8
        band renderer. `None` when the rig is missing; callers just skip the
        pass."""
        key = ("cliff-shadow",)
        if key not in self._cell_cache:
            frs = self._a.frames("terrain_shadow", "loop")
            if not frs:
                return None
            self._cell_cache[key] = frs[0]
        return self._cell_cache[key]

    def vstair_sprite(self, drop: int) -> pygame.Surface | None:
        """LD-9: the stone flight for a `drop`-level descent -- one tile wide,
        `drop` tiles tall. Two sprites are authored (`vstairs_1` / `vstairs_2`)
        rather than one rescaled, so the steps stay square at either depth.
        `None` when the art is missing; the caller keeps the grass channel."""
        key = ("vstair-sprite", drop)
        if key not in self._cell_cache:
            rel = self.vstair.get("sheets", {}).get(str(drop))
            img = self._a._load_image(rel) if rel else None
            if img is None:
                return None
            want = (self.px, max(1, drop) * self.px)
            self._cell_cache[key] = (img if img.get_size() == want
                                     else pygame.transform.smoothscale(img, want))
        return self._cell_cache[key]

    def vstair_overlay(self, band_tiles: int) -> pygame.Surface | None:
        """LD-8a: the rock N/S stair as one overlay sprite, scaled to
        `band_tiles` tiles tall (its aspect kept). Cached. `None` when the sheet
        is missing -> the caller renders the biome grass ramp instead."""
        sheet = self.vstair.get("sheet")
        if not sheet:
            return None
        img = self._a._load_image(sheet)
        if img is None:
            return None
        h = max(1, int(band_tiles)) * self.px
        w = max(1, round(img.get_width() * h / img.get_height()))
        key = ("vstair", w, h)
        if key not in self._cell_cache:
            self._cell_cache[key] = pygame.transform.smoothscale(img, (w, h))
        return self._cell_cache[key]

    def three_sided(self, sheet: str, open_sides: str, band: int = 15
                    ) -> pygame.Surface:
        """LD-5: a grass tile with strands on `open_sides` (subset of "nswe")
        and flat everywhere else. The sheet has a 4-sided grass tile but no
        3-sided one -- start from the biome's flat `interior` and blit a
        `band`-px strip of the 4-sided tile back over each open edge."""
        key = (sheet, "".join(sorted(open_sides)))
        if key in self._three_cache:
            return self._three_cache[key]
        px = self.px
        four = self.raised_slots.get("nswe", self.slots.get("single", self.interior))
        base4 = self.cell(sheet, four)
        s = self.cell(sheet, self.interior).copy()
        if "n" in open_sides:
            s.blit(base4, (0, 0), pygame.Rect(0, 0, px, band))
        if "s" in open_sides:
            s.blit(base4, (0, px - band), pygame.Rect(0, px - band, px, band))
        if "w" in open_sides:
            s.blit(base4, (0, 0), pygame.Rect(0, 0, band, px))
        if "e" in open_sides:
            s.blit(base4, (px - band, 0), pygame.Rect(px - band, 0, band, px))
        self._three_cache[key] = s
        return s
