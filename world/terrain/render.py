"""`TerrainRenderer` -- everything that turns the baked terrain + obstacle
skins into pixels on the frame.

`self.gm` is the `GameMap`: the layout, the elevation index, the zoom cache,
and -- through its forwarding properties -- the `BakedTerrain` it holds
after the first draw. Drawing happens here and nowhere else.
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
        # Animation time source. `None` reads the pygame clock; a test or the
        # frame digest (`world/digest.py`) sets a callable returning fixed
        # seconds so foam and decor land on a known frame.
        self.clock = None
        # The tree-shadow index and the shade scratch surfaces
        # (`shade_character_frame`), built on first use.
        self._shade_index: dict | None = None
        self._shade_index_key: tuple | None = None
        self._shade_scratch: dict[tuple, tuple] = {}
        # The obstacle-art index and the characters drawn this frame
        # (`record_character` / `ghost_pass`): bodies behind obstacle art
        # are drawn again through it as a translucent silhouette.
        self._art_buckets: dict | None = None
        self._art_buckets_key: tuple | None = None
        self._ghost_queue: list = []
        self._ghost_cache: dict[int, tuple] = {}

    def seconds(self) -> float:
        return (self.clock() if self.clock is not None
                else pygame.time.get_ticks() * 0.001)

    def draw(self, surface: pygame.Surface, camera) -> None:
        """Whole map in one pass, with tree shades and obstacles depth-sorted."""
        self.draw_ground(surface, camera)
        if self.gm.layout is None:
            return
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
        self._prepare(surface, camera)
        z = self.gm._render_zoom
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

    def _prepare(self, surface, camera) -> None:
        """Bake if the world has not been baked, and re-sync the zoom cache.
        Every entry point starts here, because any of them may be the first."""
        if not self.gm._tiles_ready:
            self.gm._build_tiles()
        z = getattr(camera, "zoom", 1.0)
        if z != self.gm._render_zoom:
            self.gm._render_zoom = z
            self.gm._blit_cache.clear()

    def _draw_water_band(self, surface, camera) -> None:
        """Sea, shoreline foam, and the scenery floating on it -- the band that
        sits under every terrace. Factored out of `_draw_tiled` so the banded
        caller can paint it once before the first terrace."""
        gm = self.gm
        z = gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        if gm._water_buf is not None:
            wt = gm._water_tile
            surface.blit(self._z_surf(gm._water_buf),
                         (-(ox % wt) * z, -(oy % wt) * z))
        else:
            surface.fill(_VOID)
        view = camera.visible_rect()
        if gm._foam:
            seconds = self.seconds()
            fsz = gm._foam[0].get_width()
            fhalf = fsz // 2 - config.TILE_PX // 2
            fview = view.inflate(fsz, fsz)
            for wx, wy in gm._shore:
                if fview.collidepoint(wx, wy):
                    surface.blit(self._z_surf(gm._foam_frame_at(wx, wy, seconds)),
                                 ((wx - ox - fhalf) * z, (wy - oy - fhalf) * z))
        if gm._void_decor:
            self._blit_decor(surface, camera, gm._void_decor, view)

    def _screen_rect(self, rect: pygame.Rect, camera) -> pygame.Rect:
        z = self.gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        return pygame.Rect(round((rect.x - ox) * z), round((rect.y - oy) * z),
                           round(rect.width * z), round(rect.height * z))

    def level_at(self, wx: float, wy: float) -> int:
        """Which terrace a world point stands on -- 0 when the world has no
        elevation index at all, which collapses the whole banded path back to
        a single band and the ordering this had before A5."""
        ix = self.gm._levels
        if ix is None:
            return 0
        got = ix.level_at_point(wx, wy)
        return 0 if got < 0 else got

    def ground_levels(self) -> list:
        """Every terrace level the baked world holds, ascending."""
        return sorted({lvl for _b, _s, lvl in self.gm._grid_surfs}) or [0]

    def draw_water(self, surface, camera) -> None:
        """The band under everything: sea, shoreline foam, and the water
        scenery that floats on it. Split out of `draw_ground` so the caller can
        put the terrace bands -- and the sprites between them -- on top."""
        self._prepare(surface, camera)
        if self.gm.layout is None or not self.gm._tiles_ok:
            self.draw_ground(surface, camera)
            return
        self._draw_water_band(surface, camera)

    def draw_ground_band(self, surface, camera, level: int) -> None:
        """One terrace level of the whole world, south-first within it."""
        gm = self.gm
        if gm.layout is None or not gm._tiles_ok or not gm._grid_surfs:
            return
        self._prepare(surface, camera)
        z, ox, oy = gm._render_zoom, camera.pos.x, camera.pos.y
        view = camera.visible_rect()
        for blit, surf, lvl in sorted(gm._grid_surfs, key=lambda t: t[0].y):
            if lvl == level and blit.colliderect(view):
                surface.blit(self._z_surf(surf),
                             ((blit.x - ox) * z, (blit.y - oy) * z))
        if level == self.ground_levels()[0]:
            for rect, surf, _lvl in gm._corr_surfs:
                if rect.colliderect(view):
                    surface.blit(self._z_surf(surf),
                                 ((rect.x - ox) * z, (rect.y - oy) * z))

    def scenery_drawables(self, camera) -> list:
        """`(depth_y, draw_fn)` for every visible interior-clutter decoration and
        obstacle. `depth_y` is the world y of the sprite's ground contact; the
        caller merges these with the entities and paints them back-to-front, so
        a sprite lower on the map overlaps the ones above it and a character
        standing behind (a lower y than) an obstacle is hidden by it."""
        return [(depth, fn) for _lvl, depth, fn in self.banded_scenery(camera)]

    def banded_scenery(self, camera) -> list:
        """`(level, depth_y, draw_fn)` -- the same items, each tagged with the
        terrace it stands on so the caller can slot it between two ground
        bands. The level has to be taken here, where the world position is
        still in hand; once an item is a closure it is gone.
        """
        if self.gm.layout is None:
            return []
        cull = camera.visible_rect().inflate(320, 320)
        out: list = []
        for inst_list in self.gm._room_decor.values():
            for inst in inst_list:
                if cull.collidepoint(inst[4], inst[5]):
                    out.append((self.level_at(inst[4], inst[5]), inst[5],
                                lambda s, c=camera, it=inst:
                                self._blit_one_decor(s, c, it)))
        for i, o in enumerate(self.gm.obstacles):
            if cull.collidepoint(o.pos.x, o.pos.y):
                lvl = self.level_at(o.pos.x, o.pos.y)
                shadow = self.gm._tree_shadows.get(i)
                if shadow is not None:
                    out.append((lvl, o.pos.y - 0.01,
                                lambda s, c=camera, sh=shadow:
                                self._draw_one_tree_shadow(s, c, sh)))
                out.append((lvl, o.pos.y,
                            lambda s, c=camera, idx=i, ob=o:
                            self._draw_one_obstacle(s, c, idx, ob)))
        return out

    def _draw_tiled(self, surface, camera) -> None:
        z = self.gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        self._draw_water_band(surface, camera)

        view = camera.visible_rect()
        gm = self.gm

        def _blit(rect, surf):
            if rect.colliderect(view):
                surface.blit(self._z_surf(surf),
                             ((rect.x - ox) * z, (rect.y - oy) * z))

        if gm.layout is None:
            # Interior clutter is NOT drawn here -- it is depth-sorted with the
            # obstacles and the characters (see `scenery_drawables`).
            return

        # One baked surface per *terrace*, composited level by level. Within
        # a level, south-first, so an island lower down the map overlaps the
        # one above it. Across levels, ascending, so a higher terrace is
        # always painted over the one it stands on -- which is what lets the
        # depth layer slot sprites between two bands (`ground_bands`).
        for blit, surf, _lvl in sorted(gm._grid_surfs,
                                       key=lambda t: (t[2], t[0].y)):
            _blit(blit, surf)
        for rect, surf, _lvl in gm._corr_surfs:
            _blit(rect, surf)
        # Interior clutter is NOT drawn here -- it is depth-sorted with the
        # obstacles and the characters (see `scenery_drawables`).

    def _blit_one_decor(self, surface, camera, inst) -> None:
        """Blit one `(frames, anchor_x, anchor_y, fps, wx, wy)` scenery instance:
        current animation frame, base on `(wx, wy)`."""
        frs, ax, ay, fps, wx, wy = inst
        z = self.gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        frame = (frs[int(self.seconds() * fps) % len(frs)]
                 if fps else frs[0])
        surface.blit(self._z_surf(frame),
                     (round((wx - ox) * z - ax * z), round((wy - oy) * z - ay * z)))

    def _blit_decor(self, surface, camera, instances, view=None) -> None:
        """View-culled batch blit of scenery instances -- the void scatter,
        which sits under the whole depth layer and needs no sorting."""
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
            ax, ay, fps, frs, phase = entry
            frame = (frs[(int(self.seconds() * fps) + phase) % len(frs)]
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

    _SHADE_CELL = 256      # world px; the widest shade is ~140 px across

    def _shadow_index(self) -> dict:
        """The tree shadows bucketed by a coarse world grid, each shadow in
        every cell its disc touches. Shadows are static once baked; the
        index is rebuilt only when the baked dict is replaced or grows."""
        shadows = self.gm._tree_shadows
        key = (id(shadows), len(shadows))
        if self._shade_index is None or self._shade_index_key != key:
            c = self._SHADE_CELL
            index: dict = {}
            for shadow in shadows.values():
                wx, wy, r, _surf = shadow
                for gx in range(int((wx - r) // c), int((wx + r) // c) + 1):
                    for gy in range(int((wy - r) // c), int((wy + r) // c) + 1):
                        index.setdefault((gx, gy), []).append(shadow)
            self._shade_index = index
            self._shade_index_key = key
        return self._shade_index

    def _scratch(self, size: tuple) -> tuple:
        """Two cleared SRCALPHA surfaces of `size`: the shade overlay and the
        shaded result. Reused across characters -- a frame is blitted the
        moment it is returned, so nothing holds the previous one."""
        pair = self._shade_scratch.get(size)
        if pair is None:
            pair = (pygame.Surface(size, pygame.SRCALPHA),
                    pygame.Surface(size, pygame.SRCALPHA))
            if len(self._shade_scratch) > 32:
                self._shade_scratch.clear()
            self._shade_scratch[size] = pair
        for surf in pair:
            surf.fill((0, 0, 0, 0))
        return pair

    def shade_character_frame(self, frame: pygame.Surface, dest, camera,
                              character_y: float) -> pygame.Surface:
        """Overlay intersecting tree shades through a character frame's alpha.

        The normal depth pass still controls shade-vs-scenery ordering. This
        character-only copy makes the same shade visible on a sprite regardless
        of whether that character sorts above or below the owning tree.

        Only the shadows whose discs touch the frame's footprint are looked
        at (`_shadow_index`); this used to walk every tree in the world for
        every character drawn, which was three quarters of the render.
        """
        shadows = self.gm._tree_shadows
        if not shadows:
            return frame
        frame_rect = frame.get_rect(topleft=(int(dest[0]), int(dest[1])))
        z = self.gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        # The frame's footprint in world space, then the index cells it spans.
        c = self._SHADE_CELL
        wx0, wy0 = ox + frame_rect.left / z, oy + frame_rect.top / z
        wx1, wy1 = ox + frame_rect.right / z, oy + frame_rect.bottom / z
        index = self._shadow_index()
        overlay = shaded = None
        seen: set = set()
        for gx in range(int(wx0 // c), int(wx1 // c) + 1):
            for gy in range(int(wy0 // c), int(wy1 // c) + 1):
                for shadow in index.get((gx, gy), ()):
                    key = id(shadow)
                    if key in seen:
                        continue
                    seen.add(key)
                    wx, wy, r, shade = shadow
                    if character_y < wy - 0.01:
                        continue                # the normal depth pass shades it later
                    scaled = self._z_surf(shade)
                    shade_rect = scaled.get_rect(topleft=(
                        round((wx - ox) * z - r * z),
                        round((wy - oy) * z - r * z),
                    ))
                    if not frame_rect.colliderect(shade_rect):
                        continue
                    if overlay is None:
                        overlay, shaded = self._scratch(frame.get_size())
                    overlay.blit(scaled, (shade_rect.x - frame_rect.x,
                                          shade_rect.y - frame_rect.y))
        if overlay is None:
            return frame
        overlay.blit(frame, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        shaded.blit(frame, (0, 0))
        shaded.blit(overlay, (0, 0))
        return shaded

    # --- ghost silhouettes -------------------------------------------
    def _art_index(self) -> dict:
        """The obstacle skins' art rectangles (world px, baked by
        `obstacle_skins`) bucketed the way the tree shadows are, holding
        `(obstacle index, rect)` for the kinds the data says cover a body."""
        rects = self.gm._art_rects
        ghost = self.gm._ghost
        key = (id(rects), len(rects), id(ghost))
        if self._art_buckets is None or self._art_buckets_key != key:
            kinds = set(ghost.get("kinds", ()))
            c = self._SHADE_CELL
            index: dict = {}
            for i, rect in rects.items():
                o = self.gm.obstacles[i]
                if o.kind not in kinds:
                    continue
                x0, y0, w, h = rect
                for gx in range(int(x0 // c), int((x0 + w) // c) + 1):
                    for gy in range(int(y0 // c), int((y0 + h) // c) + 1):
                        index.setdefault((gx, gy), []).append((i, rect))
            self._art_buckets = index
            self._art_buckets_key = key
        return self._art_buckets

    def begin_frame(self) -> None:
        """Forget the characters of the previous frame."""
        self._ghost_queue.clear()

    def record_character(self, frame: pygame.Surface, dest, character_y: float,
                         cacheable: bool = True) -> None:
        """A character was just drawn: `frame` (as drawn -- shaded, tinted,
        flipped) at screen `dest`, standing on ground-contact `character_y`.
        `cacheable` says the frame is a long-lived object whose ghost may be
        cached by identity; a per-frame copy (a shaded body) is not."""
        if self.gm._ghost.get("alpha", 0):
            self._ghost_queue.append((frame, (int(dest[0]), int(dest[1])), character_y,
                                      cacheable))

    def _ghost_of(self, frame: pygame.Surface, alpha: int) -> pygame.Surface:
        """`frame` with its alpha scaled to `alpha`, cached by the frame's
        identity (the animation frames are the asset cache's objects and come
        back unchanged for the whole animation). Never `set_alpha` on the
        frame itself: every other user would inherit it."""
        hit = self._ghost_cache.get(id(frame))
        if hit is not None and hit[0] is frame and hit[2] == alpha:
            return hit[1]
        ghost = frame.copy()
        ghost.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        if len(self._ghost_cache) >= 128:
            self._ghost_cache.clear()
        self._ghost_cache[id(frame)] = (frame, ghost, alpha)
        return ghost

    @staticmethod
    def _disjoint(pieces: list, rect: pygame.Rect) -> None:
        """Add `rect` to `pieces` as the parts of it not already covered by a
        piece, so the pieces stay pairwise disjoint. Two crowns over one
        body would otherwise each blit the ghost and the alpha would stack
        where they overlap (three crowns at 27 % read as 60 %)."""
        todo = [rect]
        for have in pieces:
            nxt = []
            for r in todo:
                if not r.colliderect(have):
                    nxt.append(r)
                    continue
                # up to four slivers of `r` around `have`
                if r.top < have.top:
                    nxt.append(pygame.Rect(r.left, r.top, r.width, have.top - r.top))
                if r.bottom > have.bottom:
                    nxt.append(pygame.Rect(r.left, have.bottom, r.width, r.bottom - have.bottom))
                top, bottom = max(r.top, have.top), min(r.bottom, have.bottom)
                if r.left < have.left:
                    nxt.append(pygame.Rect(r.left, top, have.left - r.left, bottom - top))
                if r.right > have.right:
                    nxt.append(pygame.Rect(have.right, top, r.right - have.right, bottom - top))
            todo = [t for t in nxt if t.width > 0 and t.height > 0]
            if not todo:
                return
        pieces.extend(todo)

    @staticmethod
    def _ghost_uncached(frame: pygame.Surface, alpha: int) -> pygame.Surface:
        ghost = frame.copy()
        ghost.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        return ghost

    def ghost_pass(self, surface, camera) -> int:
        """Draw every recorded character again, at the data's ghost alpha,
        through the obstacle art that covers it and sorts in front of it --
        clipped to that art, so the uncovered part of the body is not drawn
        twice. Returns how many clipped blits were made."""
        ghost = self.gm._ghost
        alpha = int(ghost.get("alpha", 0))
        if not alpha or not self._ghost_queue:
            return 0
        index = self._art_index()
        if not index:
            return 0
        z = self.gm._render_zoom
        ox, oy = camera.pos.x, camera.pos.y
        c = self._SHADE_CELL
        obstacles = self.gm.obstacles
        blits = 0
        for frame, dest, character_y, cacheable in self._ghost_queue:
            frame_rect = frame.get_rect(topleft=dest)
            wx0, wy0 = ox + frame_rect.left / z, oy + frame_rect.top / z
            wx1, wy1 = ox + frame_rect.right / z, oy + frame_rect.bottom / z
            seen: set = set()
            pieces: list = []
            for gx in range(int(wx0 // c), int(wx1 // c) + 1):
                for gy in range(int(wy0 // c), int(wy1 // c) + 1):
                    for i, (ax, ay, aw, ah) in index.get((gx, gy), ()):
                        if i in seen:
                            continue
                        seen.add(i)
                        if obstacles[i].pos.y <= character_y:
                            continue          # painted before the body: it is behind
                        art = pygame.Rect(round((ax - ox) * z), round((ay - oy) * z),
                                          round(aw * z), round(ah * z))
                        clip = art.clip(frame_rect)
                        if clip.width > 0 and clip.height > 0:
                            self._disjoint(pieces, clip)
            if not pieces:
                continue
            drawn = (self._ghost_of(frame, alpha) if cacheable
                     else self._ghost_uncached(frame, alpha))
            for piece in pieces:
                surface.set_clip(piece)
                surface.blit(drawn, dest)
                blits += 1
            surface.set_clip(None)
        return blits

    def draw_tree_shadows(self, surface, camera) -> None:
        """Compatibility painter; depth-aware callers use `scenery_drawables`."""
        view = camera.visible_rect().inflate(200, 200)
        for shadow in self.gm._tree_shadows.values():
            if view.collidepoint(shadow[0], shadow[1]):
                self._draw_one_tree_shadow(surface, camera, shadow)

    def _draw_obstacles(self, surface, camera) -> None:
        """Every visible obstacle, unsorted -- only the whole-map `draw()` path."""
        view = camera.visible_rect().inflate(260, 260)
        for i, o in enumerate(self.gm.obstacles):
            if view.collidepoint(o.pos.x, o.pos.y):
                self._draw_one_obstacle(surface, camera, i, o)

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

