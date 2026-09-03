"""The generation knobs, snapshotted once per world.

`generate_world` used to read `game.config` fifteen times across its
stages, and the stages beneath it read it again. A test that changed a knob
had to change the global and remember to restore it, and a world could be
generated under one setting and read under another. This is the fix: one
frozen value built at the top of `generate_world` (or handed in by a test),
passed down to every stage that needs a knob, and never read from the global
below that point.

Only *generation* knobs live here. `TILE_PX` is the world's grid unit,
shared with the data (`terrain.json` `tile_px`), the bake and the renderer,
and stays a global constant; the rendering and decoration flags are the
bake's business.

Every field is named after its `game.config` key, so a test can say
`GenSettings.from_config(unseal=False)` and mean `HEIGHTMAP_UNSEAL = False`.
"""
from __future__ import annotations

from dataclasses import dataclass, fields

from game import config

_KEYS = {
    "chunk_cols": "HEIGHTMAP_CHUNK_COLS",
    "chunk_rows": "HEIGHTMAP_CHUNK_ROWS",
    "room_count": "HEIGHTMAP_ROOM_COUNT",
    "room_cols": "HEIGHTMAP_ROOM_COLS",
    "room_rows": "HEIGHTMAP_ROOM_ROWS",
    "coast_keep": "HEIGHTMAP_COAST_KEEP",
    "coast_preset": "HEIGHTMAP_COAST_PRESET",
    "coast_presets": "HEIGHTMAP_COAST_PRESETS",
    "shore_ring": "HEIGHTMAP_SHORE_RING",
    "stairs_per_region": "HEIGHTMAP_STAIRS_PER_REGION",
    "stair_region": "HEIGHTMAP_STAIR_REGION",
    "stair_spacing": "HEIGHTMAP_STAIR_SPACING",
    "lakes": "HEIGHTMAP_LAKES",
    "lake_size": "HEIGHTMAP_LAKE_SIZE",
    "cap_inset_s": "HEIGHTMAP_CAP_INSET_S",
    "cap_inset_n": "HEIGHTMAP_CAP_INSET_N",
    "cap_inset_w": "HEIGHTMAP_CAP_INSET_W",
    "cap_inset_e": "HEIGHTMAP_CAP_INSET_E",
    "cap_roughness": "HEIGHTMAP_CAP_ROUGHNESS",
    "cap_min_cells": "HEIGHTMAP_CAP_MIN_CELLS",
    "canyons": "HEIGHTMAP_CANYONS",
    "canyon_depth": "HEIGHTMAP_CANYON_DEPTH",
    "canyon_width": "HEIGHTMAP_CANYON_WIDTH",
    "topographies": "HEIGHTMAP_TOPOGRAPHIES",
    "boss_topography": "HEIGHTMAP_BOSS_TOPOGRAPHY",
    "bridge_min_gap": "HEIGHTMAP_BRIDGE_MIN_GAP",
    "bridge_max": "HEIGHTMAP_BRIDGE_MAX",
    "shortcuts": "HEIGHTMAP_SHORTCUTS",
    "shortcut_gap": "HEIGHTMAP_SHORTCUT_GAP",
    "unseal": "HEIGHTMAP_UNSEAL",
    "buildings": "TERRAIN_BUILDINGS",
}


@dataclass(frozen=True)
class GenSettings:
    chunk_cols: int
    chunk_rows: int
    room_count: int
    room_cols: tuple
    room_rows: tuple
    coast_keep: int
    coast_preset: str
    coast_presets: dict
    shore_ring: int
    stairs_per_region: int
    stair_region: int
    stair_spacing: int
    lakes: int
    lake_size: tuple
    cap_inset_s: int
    cap_inset_n: int
    cap_inset_w: int
    cap_inset_e: int
    cap_roughness: float
    cap_min_cells: int
    canyons: int
    canyon_depth: tuple
    canyon_width: tuple
    topographies: dict
    boss_topography: str
    bridge_min_gap: int
    bridge_max: int
    shortcuts: bool
    shortcut_gap: int
    unseal: bool
    buildings: bool

    @classmethod
    def from_config(cls, **overrides) -> "GenSettings":
        """A snapshot of `game.config` as it is now, with `overrides` (by
        field name) applied on top."""
        values = {name: getattr(config, key) for name, key in _KEYS.items()}
        unknown = set(overrides) - set(values)
        if unknown:
            raise TypeError(f"not generation settings: {sorted(unknown)}")
        values.update(overrides)
        return cls(**values)

    @property
    def cap_inset(self) -> tuple:
        """`(south, north, west, east)`, the order `build_grid` takes."""
        return (self.cap_inset_s, self.cap_inset_n,
                self.cap_inset_w, self.cap_inset_e)

    def topography(self, room) -> dict:
        """This island's topography spec, `{}` when it has none yet."""
        return self.topographies.get(room.topography, {})


def settings_or_config(settings: GenSettings | None) -> GenSettings:
    """The stages accept `settings=None` so that a caller that has none --
    a test driving one stage on its own -- gets today's config."""
    return settings if settings is not None else GenSettings.from_config()


__all__ = ["GenSettings", "settings_or_config", "fields"]
