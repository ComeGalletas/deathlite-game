"""World-layer rendering for PLAYING.

`WorldRenderer` owns every `_draw_*` painter that turns run state into pixels.
It is **read-only** with respect to `PlayingState`: it reads `ps.camera`,
`ps.player`, the entity/pool lists, `ps.game.assets`, the feedback timers, etc.,
and writes nothing back. `PlayingState.draw()` keeps the layer order and calls
these; a handful of thin delegators on `PlayingState` (`_draw_player`,
`_draw_one_enemy`, `_sprite_drop`, `_hit_tinted`, `_draw_cone`, ...) forward here
so existing call sites and tests keep working.

Part of the split tracked in `journals/playing_state_refactor.md` (P1).
"""
from __future__ import annotations

import math

import pygame

from game import config, fonts
from entities.pickup import XP_TIER_COLORS
from game.states.playing.drawctx import DrawCtx
from game.states.playing.projectiles import draw_projectile
from game.states.playing.summons import draw_summon
# Re-exported so `PlayingState._draw_cone` (a `test_depth_sort` entry point) and
# `_rendering.draw_cone` keep resolving after the move to the projectiles pkg.
from game.states.playing.projectiles.cone import draw_cone  # noqa: F401


_ORB_RIGS = {0: "xp_orb_small", 1: "xp_orb_medium", 2: "xp_orb_large"}
_STATUS_TINT = {"burn": (255, 130, 60), "chill": (140, 210, 255),
                "shock": (255, 230, 120)}
_HIT_TINT = (150, 30, 30)
_KNOCK_VEC_SCALE = 0.15     # dev overlay: `_knock` px/s -> screen px line length
_SPAWN_MARK_PX = 6          # dev overlay: half-size of a spawn-point mark, world px
# Hazard fill: alpha at spawn is FLOOR + ALPHA, fading to FLOOR as the pool
# expires. Halved from 70/20 when the pools gained art -- the disc still has
# to state the area, but it no longer has to carry the whole effect.
_HAZARD_FILL_ALPHA = 35
_HAZARD_FILL_FLOOR = 10


_TINT_CACHE: dict[int, tuple] = {}     # id(frame) -> (frame, tinted copy)
_TINT_CACHE_CAP = 128


def hit_tinted(frame):
    """A red-tinted copy of a sprite frame -- the damage flash for rigs with no
    `hurt` strip. `BLEND_RGBA_ADD` brightens toward red and leaves the alpha
    silhouette intact (transparent pixels stay transparent).

    Cached by the frame's identity: the animation frames are the asset
    cache's own objects, so the same one comes back for the whole 0.26 s
    hurt window, and this used to copy it on every frame of it. The source
    is kept in the entry so its id cannot be recycled under the cache."""
    hit = _TINT_CACHE.get(id(frame))
    if hit is not None and hit[0] is frame:
        return hit[1]
    out = frame.copy()
    out.fill((*_HIT_TINT, 0), special_flags=pygame.BLEND_RGBA_ADD)
    if len(_TINT_CACHE) >= _TINT_CACHE_CAP:
        _TINT_CACHE.clear()
    _TINT_CACHE[id(frame)] = (frame, out)
    return out


class WorldRenderer:
    def __init__(self, ps) -> None:
        self.ps = ps

    # --- geometry helper --------------------------------------------
    def sprite_drop(self, radius: float) -> float:
        """Downward render offset (screen px) that seats a rig's feet-anchor
        below the collider centre -- see config.SPRITE_ANCHOR_DROP. Render-only."""
        return config.SPRITE_ANCHOR_DROP * radius * self.ps.camera.zoom

    def _blit_character(self, surface, frame, dest, character_y: float) -> None:
        r = self.ps.game_map.renderer
        drawn = r.shade_character_frame(frame, dest, self.ps.camera, character_y)
        surface.blit(drawn, dest)
        # For the ghost pass. A shaded result lives in a scratch surface the
        # next character of the same size overwrites, so it is copied here;
        # the unshaded frame is the asset cache's own object and is recorded
        # as is (and the ghost of it is cached by identity).
        if drawn is frame:
            r.record_character(frame, dest, character_y)
        else:
            r.record_character(drawn.copy(), dest, character_y, cacheable=False)

    # --- feedback / hud-adjacent overlays --------------------------
    def feedback_overlays(self, surface: pygame.Surface) -> None:
        ps = self.ps
        w, h = surface.get_size()

        # Low-HP vignette (spec 3.6 player damage feedback) -- pulsing red frame.
        frac = ps.player.hp / ps.player.max_hp if ps.player.max_hp else 1.0
        if frac < 0.3:
            pulse = 60 + int(40 * math.sin(ps.stats["time"] * 8))
            vig = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(vig, (180, 20, 20, max(0, pulse)), (0, 0, w, h), 24)
            surface.blit(vig, (0, 0))

        # Brief full-screen red flash on taking a hit.
        if ps._hurt_flash_t > 0.0:
            a = int(120 * min(1.0, ps._hurt_flash_t / 0.35))
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            flash.fill((200, 30, 30, a))
            surface.blit(flash, (0, 0))

        # Boss-incoming warning banner (spec 3.6 "Boss warning").
        if ps._boss_warning_t > 0.0:
            blink = (ps._boss_warning_t * 4) % 1.0 < 0.6
            if blink:
                text = ps._banner_font.render(
                    f"{ps._boss_name} APPROACHES", True, (255, 90, 90))
                surface.blit(text, text.get_rect(center=(w // 2, 120)))

        # Interaction prompt when stood on a usable special location.
        it = ps.locations.nearby()
        if it is not None:
            afford = it.kind != "merchant" or ps.stats["gold"] >= it.cost
            col = (240, 240, 245) if afford else (200, 120, 120)
            prompt = ps._prompt_font.render(it.prompt, True, col)
            surface.blit(prompt, prompt.get_rect(center=(w // 2, h - 96)))

    # --- world props ----------------------------------------------
    def _off_band(self, level, pos) -> bool:
        """Is this flat effect on some other terrace than the band being
        painted? `level is None` means "draw it wherever it is", which is what
        every caller outside the banded world path passes."""
        if level is None:
            return False
        return self.ps.game_map.renderer.level_at(pos[0], pos[1]) != level

    def interactables(self, surface, level=None) -> None:
        ps = self.ps
        z = ps.camera.zoom
        for it in ps.interactables:
            if self._off_band(level, it.pos):
                continue
            sx, sy = ps.camera.world_to_screen(it.pos)
            done = it.used or it.state == "done"
            col = (90, 90, 100) if done else it.colour
            pygame.draw.circle(surface, col, (int(sx), int(sy)),
                               round(it.radius * z), 0 if done else 3)
            pygame.draw.circle(surface, (240, 245, 255), (int(sx), int(sy)), round(4 * z))
            if it.kind == "elite_arena" and it.state == "active":
                pygame.draw.circle(surface, (255, 120, 120), (int(sx), int(sy)),
                                   round((it.radius + 120) * z), 1)

    def hazards(self, surface, level=None) -> None:
        ps = self.ps
        z = ps.camera.zoom
        for hz in ps.hazards:
            if self._off_band(level, hz.pos):
                continue
            sx, sy = ps.camera.world_to_screen(hz.pos)
            frac = max(0.0, hz.life / hz.max_life)
            rr = max(1, round(hz.radius * z))
            # The disc states the area; the ring states its exact edge. Both
            # are what a player reads, so the art below never replaces them --
            # the fill is only kept faint enough to stop competing with it.
            surf = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*hz.color, int(_HAZARD_FILL_ALPHA * frac
                                                     + _HAZARD_FILL_FLOOR)),
                               (rr, rr), rr)
            surface.blit(surf, (sx - rr, sy - rr))
            self._hazard_sprite(surface, hz, sx, sy, z)
            pygame.draw.circle(surface, hz.color, (int(sx), int(sy)), rr, 2)

    def _hazard_sprite(self, surface, hz, sx: float, sy: float, z: float) -> None:
        """The pool's flair, if it has a rig: the strip played once at its
        own speed so it *ends* as the pool does, which reads as the blast
        going off rather than as the pool simmering. Silent for a pool with
        no rig, and for the whole of its life before the strip is due."""
        if not hz.sprite:
            return
        assets = self.ps.game.assets
        n = assets.frame_count(hz.sprite, "loop")
        if not n:
            return
        fps = assets.fps(hz.sprite, "loop")
        span = n / fps                       # 10 frames at 14 fps == 0.71 s
        left = hz.life                       # seconds until the pool expires
        if left > span:
            return                           # not yet: the pool is still simmering
        i = min(n - 1, max(0, int((span - left) * fps)))
        base = assets.scale_for(hz.sprite) or (round(hz.radius * 2), round(hz.radius * 2))
        size = (max(1, round(base[0] * z)), max(1, round(base[1] * z)))
        frames = assets.frames(hz.sprite, "loop", size=size)
        if not frames:
            return
        frame = frames[min(i, len(frames) - 1)]
        surface.blit(frame, frame.get_rect(center=(int(sx), int(sy))))

    def one_summon(self, surface, s) -> None:
        sx, sy = self.ps.camera.world_to_screen(s.pos)
        draw_summon(surface, sx, sy, s, self._draw_ctx(), default="disc")

    def gems(self, surface, level=None) -> None:
        ps = self.ps
        z = ps.camera.zoom
        assets = ps.game.assets

        for gem in ps.gems:
            if self._off_band(level, gem.pos):
                continue
            sx, sy = ps.camera.world_to_screen(gem.pos)
            rig = _ORB_RIGS.get(gem.tier, "xp_orb_small")
            base_size = assets.scale_for(rig) or (8, 8)
            size = (
                max(1, round(base_size[0] * z)),
                max(1, round(base_size[1] * z)),
            )

            orb = assets.image(rig, size=size)

            if orb is not None:
                surface.blit(
                    orb,
                    orb.get_rect(center=(int(sx), int(sy))),
                )
            else:
                pygame.draw.circle(
                    surface,
                    XP_TIER_COLORS.get(gem.tier, (150, 220, 150)),
                    (int(sx), int(sy)),
                    round((3 + gem.tier) * z),
                )

    def explosions(self, surface, level=None) -> None:
        ps = self.ps
        z = ps.camera.zoom
        for ex in ps._explosions:
            if self._off_band(level, ex["pos"]):
                continue
            frac = ex["t"] / ex["dur"]
            sx, sy = ps.camera.world_to_screen(ex["pos"])
            pygame.draw.circle(surface, (255, 180, 90),
                               (int(sx), int(sy)), int(ex["radius"] * frac * z), 3)

    def trail_fx(self, surface, level=None) -> None:
        """Projectile dust trails -- each `[Animator, pos, size, tint, fade]`
        entry blits the current burst frame (tinted), optionally alpha-ramped
        over its life. Anchored in world space; the bolt draws over it."""
        ps = self.ps
        z = ps.camera.zoom
        a = ps.game.assets
        for anim, pos, (w, h), tint, fade in ps._trail_fx:
            if self._off_band(level, pos):
                continue
            size = (max(1, round(w * z)), max(1, round(h * z)))
            fr = a.frame(anim.rig, anim.anim, anim.index, size=size, tint=tint)
            if fr is None:
                continue
            if fade:
                fps = max(1e-3, a.fps(anim.rig, anim.anim))
                total = max(1, a.frame_count(anim.rig, anim.anim)) / fps
                fr = fr.copy()                       # don't touch the shared cache
                fr.set_alpha(max(0, int(255 * (1.0 - anim.t / total))))
            sx, sy = ps.camera.world_to_screen(pos)
            surface.blit(fr, fr.get_rect(center=(int(sx), int(sy))))

    # --- characters (depth layer) --------------------------------
    def one_enemy(self, surface, e) -> None:
        ps = self.ps
        z = ps.camera.zoom
        sx, sy = ps.camera.world_to_screen(e.pos)
        er = e.radius * z

        sprited = e.anim is not None
        if sprited:
            self.enemy_sprite(surface, e)
        else:
            colour = (255, 255, 255) if e.hit_flash > 0 else e.color
            for sid, tint in _STATUS_TINT.items():
                if sid in e.status:
                    colour = tint
                    break
            pygame.draw.circle(surface, colour, (int(sx), int(sy)), round(er))

        # Thin state rings at the collider edge -- always for the primitive
        # fallback (the only cue with no art); for a sprited enemy only when
        # config.SHOW_ENEMY_STATE_RINGS is on (else it just reads as a collider).
        if not sprited or config.SHOW_ENEMY_STATE_RINGS:
            for sid, tint in _STATUS_TINT.items():
                if sid in e.status:
                    pygame.draw.circle(surface, tint, (int(sx), int(sy)),
                                       round(er) + 2, 2)
                    break
            if e.is_elite:
                pygame.draw.circle(surface, (255, 220, 120), (int(sx), int(sy)),
                                   round(er) + 3, 2)
            if e.shield_hp > 0:
                pygame.draw.circle(surface, (150, 200, 255), (int(sx), int(sy)),
                                   round(er) + 5, 1)

        if e.telegraphing and "slam_radius" in e.cfg:  # AoE danger zone only
            r = e.cfg["slam_radius"]
            pygame.draw.circle(surface, (255, 90, 90), (int(sx), int(sy)),
                               round(r * z), 2)

    def death_fx(self, surface, fx) -> None:
        ps = self.ps
        anim, pos, facing, scale, radius = fx
        z = ps.camera.zoom
        scale *= z
        assets = ps.game.assets
        bw, bh = assets.scale_for("dead")
        size = (max(1, round(bw * scale)), max(1, round(bh * scale)))
        frame = anim.frame(size=size,
                           flip=(facing < 0 and assets.face("dead") == "right"))
        if frame is None:
            return
        ax, ay = assets.anchor("dead")
        sx, sy = ps.camera.world_to_screen(pos)
        drop = self.sprite_drop(radius)     # match the sprite this poof replaced
        self._blit_character(
            surface, frame, (sx - ax * scale, sy - ay * scale + drop), pos.y)

    def enemy_sprite(self, surface, e) -> None:
        ps = self.ps
        z = ps.camera.zoom
        assets = ps.game.assets
        rig = e.anim.rig
        flip = e._facing < 0 and assets.face(rig) == "right"
        bw, bh = assets.scale_for(rig)
        frame = e.anim.frame(size=(max(1, round(bw * z)), max(1, round(bh * z))),
                             flip=flip)
        sx, sy = ps.camera.world_to_screen(e.pos)
        if frame is None:                        # sprite file missing -> primitive
            pygame.draw.circle(surface, e.color, (int(sx), int(sy)),
                               round(e.radius * z))
            return
        if e._hurt_t > 0.0:
            frame = hit_tinted(frame)           # red flash, no pop to a circle
        ax, ay = assets.anchor(rig)
        self._blit_character(
            surface, frame,
            (sx - ax * z, sy - ay * z + self.sprite_drop(e.radius)), e.pos.y)

    def boss(self, surface) -> None:
        ps = self.ps
        b = ps.boss
        if b is None or not b.alive:
            return
        z = ps.camera.zoom
        sx, sy = ps.camera.world_to_screen(b.pos)
        br = b.radius * z
        assets = ps.game.assets
        frame = None
        if b.anim is not None:
            rig = b.anim.rig
            bw, bh = assets.scale_for(rig)
            frame = b.anim.frame(size=(max(1, round(bw * z)), max(1, round(bh * z))),
                                 flip=(b._facing < 0 and assets.face(rig) == "right"))
        if frame is not None:
            if b._hurt_t > 0.0:
                frame = hit_tinted(frame)
            ax, ay = assets.anchor(rig)
            self._blit_character(
                surface, frame,
                (sx - ax * z, sy - ay * z + self.sprite_drop(b.radius)), b.pos.y)
        else:
            colour = (255, 255, 255) if b.hit_flash > 0 else b.color
            pygame.draw.circle(surface, colour, (int(sx), int(sy)), round(br))
            pygame.draw.circle(surface, (255, 210, 210), (int(sx), int(sy)),
                               round(br), 3)
        if b.phase == "telegraph":
            pid = b.pattern.get("id")
            frac = b.telegraph_fraction
            if pid == "radial_barrage":
                pygame.draw.circle(surface, (255, 140, 140), (int(sx), int(sy)),
                                   round((40 + 220 * frac) * z), 2)
            elif pid == "charge":
                d = ps.player.pos - b.pos
                if d.length_squared() > 1:
                    d = d.normalize() * 900
                    ex, ey = ps.camera.world_to_screen(b.pos + d)
                    pygame.draw.line(surface, (255, 120, 120), (sx, sy), (ex, ey), 3)
            elif pid == "summon_brood":
                pygame.draw.circle(surface, (150, 220, 160), (int(sx), int(sy)),
                                   round(br + 20 * frac * z), 2)

    def player(self, surface) -> None:
        ps = self.ps
        if not ps.player.alive:
            return                              # the death poof (_death_fx) stands in
        z = ps.camera.zoom
        sx, sy = ps.camera.world_to_screen(ps.player.pos)
        pr = ps.player.radius * z

        frame = self.hero_sprite_frame()
        if frame is not None:
            # `anchor` is the pixel in the final sprite that sits on the world
            # position (bottom-centre-ish -- the art is bottom-heavy); the drop
            # then seats it below the collider centre (config.SPRITE_ANCHOR_DROP).
            ax, ay = ps.game.assets.anchor(ps._hero_anim.rig)
            if ps.player._hurt_t > 0.0:
                frame = hit_tinted(frame)
            self._blit_character(
                surface, frame,
                (sx - ax * z, sy - ay * z + self.sprite_drop(ps.player.radius)),
                ps.player.pos.y)
            if ps.player.invulnerable:
                pygame.draw.circle(surface, (255, 120, 120), (sx, sy),
                                   round(pr + 4 * z), width=2)
        else:
            body = (255, 120, 120) if ps.player.invulnerable else ps._hero_color
            pygame.draw.circle(surface, body, (sx, sy), round(pr))
            pygame.draw.circle(surface, config.COLOR_PLAYER_OUTLINE, (sx, sy),
                               round(pr), width=2)

    def hero_sprite_frame(self):
        ps = self.ps
        if ps._hero_anim is None:
            return None
        assets = ps.game.assets
        rig = ps._hero_anim.rig
        flip = ps.player._facing < 0 and assets.face(rig) == "right"
        z = ps.camera.zoom
        bw, bh = assets.scale_for(rig)
        return ps._hero_anim.frame(
            size=(max(1, round(bw * z)), max(1, round(bh * z))), flip=flip)

    # --- projectiles / summons (per-family draw in the sub-packages) ---
    def _draw_ctx(self) -> DrawCtx:
        ps = self.ps
        return DrawCtx(ps.game.assets, ps.stats["time"], ps.camera.zoom)

    def player_projectiles(self, surface, level=None) -> None:
        cam, ctx = self.ps.camera, self._draw_ctx()
        for p in self.ps.projectiles:
            if self._off_band(level, p.pos):
                continue
            sx, sy = cam.world_to_screen(p.pos)
            draw_projectile(surface, sx, sy, p, ctx, default="bolt")

    def hostile_projectiles(self, surface) -> None:
        cam, ctx = self.ps.camera, self._draw_ctx()
        for p in self.ps.hostiles:
            sx, sy = cam.world_to_screen(p.pos)
            draw_projectile(surface, sx, sy, p, ctx, default="arrow")

    # --- dev overlay -------------------------------------------
    def spawn_point_overlay(self, surface) -> None:
        """Dev-mode: every spawn point and resource anchor the generator
        decided, read straight off the layout. Enemy points are diamonds
        (bright for the large class, dim for small-only), resource anchors
        squares, each with its floor number. Toggle with F8 or the dev
        menu's 'Spawn points' row. Same shape as `collider_overlay`."""
        ps = self.ps
        if not (ps.dev_mode and ps._dev_show_spawn_points):
            return
        layout = ps.game_map.layout
        if layout is None:
            return
        cam = ps.camera
        z = cam.zoom
        view = cam.visible_rect().inflate(200, 200)
        font = fonts.mono(10)
        half = max(3, round(_SPAWN_MARK_PX * z))

        def label(sx, sy, text, col):
            surface.blit(font.render(text, True, col), (sx + half + 2, sy - 6))

        placement = ps.spawn.master.placement
        now = ps.stats["time"]
        for p in layout.spawn_points:
            if not view.collidepoint(p.x, p.y):
                continue
            sx, sy = cam.world_to_screen(p.pos)
            sx, sy = int(sx), int(sy)
            col = (config.COLOR_DEBUG_SPAWN if p.clearance == "large"
                   else config.COLOR_DEBUG_SPAWN_SMALL)
            if placement.on_cooldown(p, now):        # just used: dimmed
                col = tuple(c // 3 for c in col)
            pygame.draw.polygon(surface, col, ((sx, sy - half), (sx + half, sy),
                                               (sx, sy + half), (sx - half, sy)), 2)
            label(sx, sy, str(p.floor), col)
        for p in layout.resource_points:
            if not view.collidepoint(p.x, p.y):
                continue
            sx, sy = cam.world_to_screen(p.pos)
            sx, sy = int(sx), int(sy)
            col = config.COLOR_DEBUG_RESOURCE
            pygame.draw.rect(surface, col,
                             pygame.Rect(sx - half, sy - half, 2 * half, 2 * half), 2)
            label(sx, sy, f"{p.floor} {p.kind[0]}", col)

    def collider_overlay(self, surface) -> None:
        """Dev-mode: every true circular collider / hitbox in one pass, read
        straight off the fields the physics uses. Toggle with F7 or the dev
        menu's 'Collision shapes' row."""
        ps = self.ps
        if not (ps.dev_mode and ps._dev_show_colliders):
            return
        cam = ps.camera
        z = cam.zoom
        view = cam.visible_rect().inflate(200, 200)

        def ring(pos, r, col, w=2):
            sx, sy = cam.world_to_screen(pos)
            pygame.draw.circle(surface, col, (int(sx), int(sy)),
                               max(1, round(r * z)), w)

        ring(ps.player.pos, ps.player.radius, config.COLOR_DEBUG)
        ring(ps.player.pos, ps.player.pickup_radius, config.COLOR_DEBUG_SOFT, 1)
        for e in ps.enemies:
            if view.collidepoint(e.pos.x, e.pos.y):
                ring(e.pos, e.radius, config.COLOR_DEBUG)
        if ps.boss is not None and ps.boss.alive:
            ring(ps.boss.pos, ps.boss.radius, config.COLOR_DEBUG)
        for o in ps.game_map.obstacles:
            if view.collidepoint(o.pos.x, o.pos.y):
                ring(o.pos, o.radius, config.COLOR_DEBUG)
        for p in ps.projectiles:
            ring(p.pos, p.radius, config.COLOR_DEBUG_HIT, 1)
        for p in ps.hostiles:
            ring(p.pos, p.radius, config.COLOR_DEBUG_HIT, 1)
        # Melee swing rings -- one-shot contact volumes, same style as the
        # projectile hitboxes above (they used to draw unconditionally).
        for hb in ps.melee_hitboxes:
            if view.collidepoint(hb.pos.x, hb.pos.y):
                ring(hb.pos, hb.radius, config.COLOR_DEBUG_HIT, 1)

        # CB-2 reach rings: the gate that decides fire-vs-idle. One ring per
        # equipped weapon at the hero (summon weapons have no ring -- `_reach`
        # is `inf` -- so they are skipped); one leash ring per live summon,
        # hero-centred for the wolf and planted-spot-centred for the totem,
        # matching `Summon._acquire_target`.
        area_mult = ps.player.stats.get("area_multiplier", 1.0)
        for w in ps.player.weapons:
            r = w._reach(area_mult)
            if math.isfinite(r):
                ring(ps.player.pos, r, config.COLOR_DEBUG_REACH, 1)
        for s in ps.summons:
            if not getattr(s, "active", False) or not math.isfinite(s.reach):
                continue
            center = ps.player.pos if s.kind == "wolf" else s.pos
            ring(center, s.reach, config.COLOR_DEBUG_REACH, 1)

        # CB-3 physics: a `weight` tag by every mobile body, and its live
        # `_knock` (bump + hit impulse) drawn as a short blue line while it is
        # being shoved -- so `BUMP_GAIN` / `HIT_KNOCK_GAIN` can be tuned by eye.
        wf = fonts.mono(10)

        def wtag(pos, weight, rad):
            sx, sy = cam.world_to_screen(pos)
            txt = "wINF" if math.isinf(weight) else f"w{weight:g}"
            surface.blit(wf.render(txt, True, config.COLOR_DEBUG_REACH),
                         (int(sx + rad * z) + 2, int(sy) - 6))

        def knock_vec(pos, kn):
            if kn.length_squared() <= 1.0:
                return
            sx, sy = cam.world_to_screen(pos)
            pygame.draw.line(
                surface, config.COLOR_DEBUG_KNOCK, (int(sx), int(sy)),
                (int(sx + kn.x * _KNOCK_VEC_SCALE * z),
                 int(sy + kn.y * _KNOCK_VEC_SCALE * z)), 2)

        wtag(ps.player.pos, ps.player.weight, ps.player.radius)
        knock_vec(ps.player.pos, ps.player._knock)
        for e in ps.enemies:
            if view.collidepoint(e.pos.x, e.pos.y):
                wtag(e.pos, e.weight, e.radius)
                knock_vec(e.pos, e._knock)
        if ps.boss is not None and ps.boss.alive:
            wtag(ps.boss.pos, ps.boss.weight, ps.boss.radius)
