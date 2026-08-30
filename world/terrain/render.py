"""`TerrainRenderer` -- everything that turns the baked terrain + obstacle
skins into pixels on the frame.

W6 of `journals/world_refactor.md`. Lifted verbatim off `GameMap`; `self.gm`
is the `GameMap`, which still owns the bake (`_build_tiles`) and every `_*surfs`
/ `_shore` / `_decos` / `_tree_shadows` container this reads, plus
`_foam_frame_at` / `_foam_routine_index`. Cross-method calls stay `self.*`;
state and the two painters a test monkey-patches on the instance
(`_draw_one_obstacle`, `_draw_one_tree_shadow`) route through `self.gm.*` so the
patch still wins. `GameMap` keeps a thin delegator for every name
`game/states/playing` or the rendering tests call.
"""
from __future__ import annotations

import pygame

from game import config

_VOID = (10, 10, 14)
_FLOOR = (26, 26, 34)
_WALL = (68, 70, 92)
_GRID = (32, 33, 44)

_SPECIAL_FLOORS = {
    "start": (24, 34, 30), "boss": (44, 22, 26),
    "shrine": (30, 34, 48), "treasure": (44, 40, 24),
    "fountain": (22, 38, 44), "altar": (40, 24, 40),
    "merchant": (40, 36, 28), "elite_arena": (46, 26, 30),
}


class TerrainRenderer:
    def __init__(self, game_map) -> None:
        self.gm = game_map

    def draw(self, surface: pygame.Surface, camera) -> None:
        """Whole map in one pass, with tree shades and obstacles depth-sorted."""
        self.draw_ground(surface, camera)
        if self.gm.layout is None:
            return
        #self.gm._draw_room_clutter(surface, camera)
        for _depth, draw in sorted(self.scenery_drawables(camera), key=lambda item: item[0]):
            draw(surface)

    def _z_surf(self, surf: pygame.Surface | None) -> pygame.Surface | None:
        """`surf` scaled by the current render zoom (cached by source id).
        Identity at zoom 1.0 -- callers and tests see the original object."""
        z = self.gm._render_zoom
        if z == 1.0 or surf is None:
            return surf
        got = self.gm._blit_cache.get(id(surf))
        if got is None:
            w, h = surf.get_size()
            got = pygame.transform.scale(
                surf, (max(1, round(w * z)), max(1, round(h * z))))
            self.gm._blit_cache[id(surf)] = got
        return got

    def draw_ground(self, surface: pygame.Surface, camera) -> None:
        """Terrain only -- water, void scenery, foam, room floors, bridges (or
        the flat fallback). The depth-sorted layer (`scenery_drawables` +
        entities) is composited on top by the caller."""
        if not self.gm._tiles_ready:
            self.gm._build_tiles()

        z = getattr(camera, "zoom", 1.0)
        if z != self.gm._render_zoom:
            self.gm._render_zoom = z
            self.gm._blit_cache.clear()

        ox, oy = camera.pos.x, camera.pos.y
        if self.gm.layout is None:
            surface.fill(_VOID)
            floor = pygame.Rect(round(-ox * z), round(-oy * z),
                                round(self.gm.width * z), round(self.gm.height * z))
            pygame.draw.rect(surface, _FLOOR, floor)
            pygame.draw.rect(surface, _WALL, floor, width=3)
            self._draw_grid(surface, camera, floor)
            return

        if self.gm._tiles_ok:
            self._draw_tiled(surface, camera)
        else:
            self._draw_flat_layout(surface, camera)
            for r in self.gm.layout.rooms:      # grey wall border (flat mode only)
                pygame.draw.rect(surface, _WALL, self._screen_rect(r.rect, camera),
                                 width=3)

    def _screen_rect(self, rect: pygame.Rect, camera) -> pygame.Rect:
        z = self.gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        return pygame.Rect(round((rect.x - ox) * z), round((rect.y - oy) * z),
                           round(rect.width * z), round(rect.height * z))

    def scenery_drawables(self, camera) -> list:
        """`(depth_y, draw_fn)` for every visible interior-clutter decoration and
        obstacle. `depth_y` is the world y of the sprite's ground contact; the
        caller merges these with the entities and paints them back-to-front, so
        a sprite lower on the map overlaps the ones above it and a character
        standing behind (a lower y than) an obstacle is hidden by it."""
        if self.gm.layout is None:
            return []
        cull = camera.visible_rect().inflate(320, 320)
        out: list = []
        """
        for inst_list in self.gm._room_decor.values():
            for inst in inst_list:
                if cull.collidepoint(inst[4], inst[5]):
                    out.append((inst[5],
                                lambda s, c=camera, it=inst:
                                self._blit_one_decor(s, c, it)))
        """
        for i, o in enumerate(self.gm.obstacles):
            if cull.collidepoint(o.pos.x, o.pos.y):
                shadow = self.gm._tree_shadows.get(i)
                if shadow is not None:
                    out.append((o.pos.y - 0.01,
                                lambda s, c=camera, sh=shadow:
                                self.gm._draw_one_tree_shadow(s, c, sh)))
                out.append((o.pos.y,
                            lambda s, c=camera, idx=i, ob=o:
                            self.gm._draw_one_obstacle(s, c, idx, ob)))
        return out

    def _draw_tiled(self, surface, camera) -> None:
        z = self.gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        if self.gm._water_buf is not None:
            wt = self.gm._water_tile
            surface.blit(self._z_surf(self.gm._water_buf),
                         (-(ox % wt) * z, -(oy % wt) * z))
        else:
            surface.fill(_VOID)

        view = camera.visible_rect()
        # Foam is the first layer above water. Ground shoreline cells, bridge
        # planks, cliffs, props, and every entity therefore cover it.
        if self.gm._foam:
            seconds = pygame.time.get_ticks() * 0.001
            frame_size = self.gm._foam[0].get_width()
            half = frame_size // 2 - config.TILE_PX // 2
            fview = view.inflate(frame_size, frame_size)
            # `_shore` = ocean shoreline; `_cliff_foam` = E8 cliff feet over
            # open water. Coordinates choose one of three independent routines.
            for wx, wy in self.gm._shore + self.gm._cliff_foam:
                if fview.collidepoint(wx, wy):
                    frame = self.gm._foam_frame_at(wx, wy, seconds)
                    zframe = self._z_surf(frame)
                    surface.blit(zframe, ((wx - ox - half) * z, (wy - oy - half) * z))
        # Void props are above foam so rocks, ducks, and other water scenery are
        # never washed over by a shoreline animation.
        if self.gm._void_decor:
            self._blit_decor(surface, camera, self.gm._void_decor, view)
        # ... then the terrain surfaces (LD-7 order): the LD-7a cliff-foot
        # underlay + drop shadow, the cliff faces, the baked room floors
        # (bottom floor up), then stairs / ramp units / corridors. Flat worlds
        # have no cliffs, so this is just the room + corridor pass.
        def _blit(rect, surf):
            if rect.colliderect(view):
                surface.blit(self._z_surf(surf),
                             ((rect.x - ox) * z, (rect.y - oy) * z))

        if self.gm.layout is not None:
            # LD-7a: the one exception to "cliffs paint before everything" --
            # one tile of the lower room's grass at each cliff-foot cell that
            # has a room directly south of it, painted first so the cliff sits
            # on grass instead of showing the sea through its foot. Never fills
            # a cell nothing else is drawn on.
            for rect, tile in self.gm._cliff_underlay:
                _blit(rect, tile)
            # LD-6/LD-7a: the static drop shadow, immediately above the underlay
            # tiles and below the cliff faces -- a tight contact shadow at the
            # cliff base rather than a blob on the open field.
            if self.gm._shadow is not None and self.gm._cliff_shadow:
                sh_half = self.gm._shadow.get_width() // 2 - config.TILE_PX // 2
                sview = view.inflate(self.gm._shadow.get_width(),
                                     self.gm._shadow.get_height())
                zsh = self._z_surf(self.gm._shadow)
                vis = [(wx, wy) for wx, wy in self.gm._cliff_shadow
                       if sview.collidepoint(wx, wy)]
                if vis:
                    # Accumulate on a scratch layer with MAX so overlapping
                    # blobs of a continuous run merge into one soft strip
                    # instead of stacking their alpha and over-darkening.
                    scratch = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
                    for wx, wy in vis:
                        scratch.blit(zsh, ((wx - ox - sh_half) * z,
                                           (wy - oy - sh_half) * z),
                                     special_flags=pygame.BLEND_RGBA_MAX)
                    surface.blit(scratch, (0, 0))
            # LD-7: cliff faces are the lowest terrain layer proper -- they
            # paint before every room floor, corridor, plank bridge, stair and
            # ramp unit, regardless of the owning room's elevation, so a
            # walkable surface always covers the stone where the two meet and
            # the face shows only over the void or over lower ground. (The
            # LD-7a underlay + shadow above are the sole thing drawn earlier.)
            for blit, surf, _fl in self.gm._cliff_surfs:
                _blit(blit, surf)
            # ... then the baked room floors, bottom floor up so a higher
            # plateau's grass overlaps the one below it.
            floors = sorted({r.floor for r in self.gm.layout.rooms})
            for f in floors:
                for r in self.gm.layout.rooms:
                    if r.floor == f:
                        _blit(r.rect, self.gm._room_surfs[r.id])
            # ... walkable structures over the room floors: plank stairs, the
            # LD-4 staircase units (lifted out of the cliff surface), then
            # corridors last so their grass renders over nearby shoreline foam.
            for blit, surf, _fl in self.gm._stair_surfs:
                _blit(blit, surf)
            for blit, surf, _fl in self.gm._ramp_surfs:
                _blit(blit, surf)
            for rect, surf in self.gm._corr_surfs:
                _blit(rect, surf)
        # Interior clutter is NOT drawn here -- it is depth-sorted with the
        # obstacles and the characters (see `scenery_drawables`).

    def draw_room_clutter(self, surface, camera) -> None:
        """All interior clutter, unsorted -- only the whole-map `draw()` path.
            Public method so it can be called from outside the class to draw room clutter and don't belong in the depth culling / sorting of the main draw pass.
        """
        if self.gm.layout is not None:
            view = camera.visible_rect()
            for r in self.gm.layout.rooms:
                inst = self.gm._room_decor.get(r.id)
                if inst and r.rect.colliderect(view):
                    self._blit_decor(surface, camera, inst, view)

    def _blit_one_decor(self, surface, camera, inst) -> None:
        """Blit one `(frames, anchor_x, anchor_y, fps, wx, wy)` scenery instance:
        current animation frame, base on `(wx, wy)`."""
        frs, ax, ay, fps, wx, wy = inst
        z = self.gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        frame = (frs[int(pygame.time.get_ticks() * 0.001 * fps) % len(frs)]
                 if fps else frs[0])
        surface.blit(self._z_surf(frame),
                     (round((wx - ox) * z - ax * z), round((wy - oy) * z - ay * z)))

    def _blit_decor(self, surface, camera, instances, view=None) -> None:
        """View-culled batch blit of scenery instances (void scatter + the
        unsorted `draw()` clutter path)."""
        if view is None:
            view = camera.visible_rect()
        cull = view.inflate(256, 256)
        for inst in instances:
            if cull.collidepoint(inst[4], inst[5]):
                self._blit_one_decor(surface, camera, inst)

    def _draw_flat_layout(self, surface, camera) -> None:
        surface.fill(_VOID)
        if self.gm.layout is not None:
            for c in self.gm.layout.corridors:
                pygame.draw.rect(surface, _FLOOR, self._screen_rect(c.rect, camera))
            for r in self.gm.layout.rooms:
                pygame.draw.rect(surface, _SPECIAL_FLOORS.get(r.kind, _FLOOR),
                                 self._screen_rect(r.rect, camera))

    def _draw_one_obstacle(self, surface, camera, i, o) -> None:
        """One obstacle: the scaled decoration skin, seated below the collider
        centre by `config.SPRITE_ANCHOR_DROP` (same as the characters -- more of
        the skin sits inside the collision circle), or a fallback circle if no
        rig resolved. Tree shades are separate depth drawables on the same world
        anchor, sorted immediately before their owning tree."""
        z = self.gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        sx, sy = (o.pos.x - ox) * z, (o.pos.y - oy) * z
        entry = self.gm._decos.get(i)
        if entry is not None:
            ax, ay, fps, frs = entry
            frame = (frs[int(pygame.time.get_ticks() * 0.001 * fps) % len(frs)]
                     if fps else frs[0])
            drop_scale = self.gm._sprite_drop.get(o.kind, config.SPRITE_ANCHOR_DROP)
            drop = drop_scale * o.radius * z
            surface.blit(self._z_surf(frame),
                         (round(sx - ax * z), round(sy - ay * z + drop)))
        else:
            pygame.draw.circle(surface, o.color, (int(sx), int(sy)),
                               round(o.radius * z))
            pygame.draw.circle(surface, _WALL, (int(sx), int(sy)),
                               round(o.radius * z), 2)

    def _draw_one_tree_shadow(self, surface, camera, shadow) -> None:
        """Blit one tree shade supplied by the depth-sorted scenery layer."""
        z = self.gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        wx, wy, r, surf = shadow
        surface.blit(self._z_surf(surf),
                     (round((wx - ox) * z - r * z),
                      round((wy - oy) * z - r * z)))

    def shade_character_frame(self, frame: pygame.Surface, dest, camera,
                              character_y: float) -> pygame.Surface:
        """Overlay intersecting tree shades through a character frame's alpha.

        The normal depth pass still controls shade-vs-scenery ordering. This
        character-only copy makes the same shade visible on a sprite regardless
        of whether that character sorts above or below the owning tree.
        """
        if not self.gm._tree_shadows:
            return frame
        frame_rect = frame.get_rect(topleft=(int(dest[0]), int(dest[1])))
        overlay = None
        z = self.gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        for wx, wy, r, shade in self.gm._tree_shadows.values():
            if character_y < wy - 0.01:
                continue                    # the normal depth pass shades it later
            scaled = self._z_surf(shade)
            assert scaled is not None
            shade_rect = scaled.get_rect(topleft=(
                round((wx - ox) * z - r * z),
                round((wy - oy) * z - r * z),
            ))
            if not frame_rect.colliderect(shade_rect):
                continue
            if overlay is None:
                overlay = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
            overlay.blit(scaled, (shade_rect.x - frame_rect.x,
                                  shade_rect.y - frame_rect.y))
        if overlay is None:
            return frame
        overlay.blit(frame, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        shaded = frame.copy()
        shaded.blit(overlay, (0, 0))
        return shaded

    def draw_tree_shadows(self, surface, camera) -> None:
        """Compatibility painter; depth-aware callers use `scenery_drawables`."""
        view = camera.visible_rect().inflate(200, 200)
        for shadow in self.gm._tree_shadows.values():
            if view.collidepoint(shadow[0], shadow[1]):
                self.gm._draw_one_tree_shadow(surface, camera, shadow)

    def _draw_obstacles(self, surface, camera) -> None:
        """Every visible obstacle, unsorted -- only the whole-map `draw()` path."""
        view = camera.visible_rect().inflate(260, 260)
        for i, o in enumerate(self.gm.obstacles):
            if view.collidepoint(o.pos.x, o.pos.y):
                self.gm._draw_one_obstacle(surface, camera, i, o)

    def _draw_grid(self, surface, camera, floor_rect) -> None:
        z = self.gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        step = 128
        for x in range(0, self.gm.width + step, step):
            sx = (x - ox) * z
            pygame.draw.line(surface, _GRID, (sx, floor_rect.top), (sx, floor_rect.bottom))
        for y in range(0, self.gm.height + step, step):
            sy = (y - oy) * z
            pygame.draw.line(surface, _GRID, (floor_rect.left, sy), (floor_rect.right, sy))

