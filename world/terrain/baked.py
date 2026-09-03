"""`BakedTerrain`: everything the bake produces, in one object.

The painters and the decor scatter used to hang their output off the
`GameMap` as a score of private fields, and the renderer read them back off
the map; the map was three things at once. This is the second of them,
separated: the surfaces, anchor lists and scenery instances a layout bakes
into, owned by the thing that made them. `GameMap.terrain` holds one after
the first draw, and forwards the old field names for the callers that read
them.

Built by `world/terrain/bake.py`; read by `world/terrain/render.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from game import config
from world.rules import floor


@dataclass
class BakedTerrain:
    layout: object                       # the `WorldLayout`, or None (no world)
    obstacles: list = field(default_factory=list)
    sheets: object = None                # the `TileSheets` the bake used
    ok: bool = False                     # False -> the tileset is missing; draw flat
    water_buf: pygame.Surface | None = None
    water_tile: int = 0                  # water tile size in world px (scroll stride)
    # `(blit_rect, surf, level)` -- one baked surface per *terrace* of every
    # island, tagged with its level so the renderer composites the world band
    # by band and can slot sprites between two bands.
    grid_surfs: list = field(default_factory=list)
    # `(blit_rect, surf, level)` -- one baked plank bridge each, at sea level.
    corr_surfs: list = field(default_factory=list)
    shore: list = field(default_factory=list)      # top-left world px of shoreline tiles
    shadow: pygame.Surface | None = None
    foam: list | None = None
    foam_routines: tuple = ((9.0, 0), (12.0, 5), (15.0, 10))
    # Obstacle index -> (anchor_x, anchor_y, fps, [frame, ...], phase). A
    # tree takes its `fps` and frame offset from `tree_routines` so a grove
    # does not sway in lock-step; everything else is (rig fps, 0). Obstacles
    # with no entry (missing tileset / flag off) fall back to a drawn circle.
    decos: dict = field(default_factory=dict)
    sprite_drop: dict = field(default_factory=dict)
    # Obstacle index -> (world_x, world_y, radius, surf) for tree shades.
    tree_shadows: dict = field(default_factory=dict)
    # Non-colliding scenery, resolved at bake time. Each instance is
    # (frames, anchor_x, anchor_y, fps, world_x, world_y).
    room_decor: dict = field(default_factory=dict)   # room id -> interior clutter
    void_decor: list = field(default_factory=list)   # water scenery in the void

    def point_ok(self, x: float, y: float) -> bool:
        """Is a world point on floor? The same rule the collider applies."""
        return self.layout is not None and floor.point_on_floor(self.layout, x, y)

    @staticmethod
    def foam_routine_index(wx: float, wy: float, count: int) -> int:
        """Stable spatial bucket so neighbouring shore patches do not lock-step."""
        col = int(wx) // config.TILE_PX
        row = int(wy) // config.TILE_PX
        return (col * 31 + row * 17) % max(1, count)

    def foam_frame_at(self, wx: float, wy: float, seconds: float) -> pygame.Surface:
        assert self.foam
        fps, phase = self.foam_routines[
            self.foam_routine_index(wx, wy, len(self.foam_routines))]
        return self.foam[(int(seconds * fps) + phase) % len(self.foam)]
