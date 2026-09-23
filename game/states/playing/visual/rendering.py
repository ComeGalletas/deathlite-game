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

from game import config
from ui import scale
from entities.pickup import XP_TIER_COLORS
from game.states.playing.devtools import overlays
from game.states.playing.visual.drawctx import DrawCtx
from game.states.playing.visual.glow import GlowCache
from game.states.playing.visual import health_bars
from game.states.playing.visual.projectiles import draw_projectile
from game.states.playing.visual.summons import draw_summon
from progression import chests as _chests
from progression import potions as _potions
from ui import buff_marks
from ui.text import shadowed

# Re-exported so `PlayingState._draw_cone` (a `test_depth_sort` entry point) and
# `_rendering.draw_cone` keep resolving after the move to the projectiles pkg.
from game.states.playing.visual.projectiles.cone import draw_cone  # noqa: F401


_ORB_RIGS = {0: "xp_orb_small", 1: "xp_orb_medium", 2: "xp_orb_large"}
_GEM_CULL_PAD = 64          # world px past the view a gem (and its glow) still draws
_STATUS_TINT = {"burn": (255, 130, 60), "chill": (140, 210, 255),
                "shock": (255, 230, 120), "stun": (240, 240, 255),
                "mark": (210, 170, 255)}
_HIT_TINT = (150, 30, 30)
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


def aura_colour(run, body):
    """The colour of the aura `body` is holding, or None.

    Read off the run's own visual set rather than imported, which keeps this
    module free of the elements package and works unchanged when a run has
    no visuals at all (the headless tests).
    """
    state = getattr(body, "elemental", None)
    visuals = getattr(run, "element_visuals", None)
    if state is None or visuals is None:
        return None
    element = state.element(run.stats["time"])
    return (element, visuals.tint(element)) if element else None


class WorldRenderer:
    def __init__(self, ps) -> None:
        self.ps = ps
        self.run = getattr(ps, "run", ps)
        self._glow = GlowCache()      # XP orb glow discs, pre-rendered per size / alpha

    # --- geometry helper --------------------------------------------
    def sprite_drop(self, radius: float) -> float:
        """Downward render offset (screen px) that seats a rig's feet-anchor
        below the collider centre -- see config.SPRITE_ANCHOR_DROP. Render-only."""
        return config.SPRITE_ANCHOR_DROP * radius * self.run.camera.zoom

    def anchor_for(self, rig: str, flip: bool) -> tuple[int, int]:
        """A rig's feet anchor in its (unscaled) frame, mirrored when the
        frame is. The content crops are asymmetric -- a wide swing or thrust
        is kept on the facing side -- so the anchor is off-centre, and a
        mirrored frame has to mirror it too or the body lands `bw - 2*ax`
        px off the collider (42 px for the turtle at zoom 1)."""
        assets = self.ps.game.assets
        ax, ay = assets.anchor(rig)
        if flip:
            bw = (assets.scale_for(rig) or (0, 0))[0]
            ax = bw - ax
        return ax, ay

    def _blit_character(self, surface, frame, dest, character_y: float) -> None:
        r = self.run.game_map.renderer
        drawn = r.shade_character_frame(frame, dest, self.run.camera, character_y)
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
    def feedback_overlays(self, surface: pygame.Surface, box: pygame.Surface | None = None) -> None:
        """The vignette and the hit flash cover the whole render surface;
        the banner and the notice are interface and sit in the
        UI `box` (the surface itself on a 16:9 render)."""
        ps = self.ps
        run = getattr(self, "run", ps)
        w, h = surface.get_size()

        # Low-HP vignette (spec 3.6 player damage feedback) -- pulsing red frame.
        frac = run.player.hp / run.player.max_hp if run.player.max_hp else 1.0
        if frac < 0.3:
            pulse = 60 + int(40 * math.sin(run.stats["time"] * 8))
            vig = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(vig, (180, 20, 20, max(0, pulse)), (0, 0, w, h), 24)
            surface.blit(vig, (0, 0))

        # Brief full-screen red flash on taking a hit.
        if run._hurt_flash_t > 0.0:
            a = int(120 * min(1.0, run._hurt_flash_t / 0.35))
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            flash.fill((200, 30, 30, a))
            surface.blit(flash, (0, 0))

        # A buff's screen-wide tint (journal: buff_buildings_journal.md): the
        # buff's palette as a vertical gradient, light and brief.
        self.buff_tint(surface)
        # ... the timers over the hero (rev. 6: here, not on the HUD), and
        # the buff's flying name above them, all following the hero.
        hero = run.camera.world_to_screen(run.player.pos)
        buff_marks.draw(surface, ps.game.assets, hero, ps.buffs.rows())
        ps.buffs.banners.draw(surface, hero)

        surface = box if box is not None else surface
        w, h = surface.get_size()

        # Boss-incoming warning banner (spec 3.6 "Boss warning").
        if run._boss_warning_t > 0.0:
            blink = (run._boss_warning_t * 4) % 1.0 < 0.6
            if blink:
                text = ps._banner_font.render(
                    f"{run._boss_name} APPROACHES", True, (255, 90, 90))
                surface.blit(text, text.get_rect(center=(w // 2, scale.px(120))))

        # P3: a transient notice (the Forge's answer, a chest's payout),
        # bottom centre.
        if run._notice_t > 0.0 and run._notice_text:
            text = shadowed(ps._prompt_font, run._notice_text, config.COLOR_ACCENT)
            surface.blit(text, text.get_rect(center=(w // 2, h - scale.px(124))))

        # There is no interaction prompt here any more: the interact keycap
        # floats over the element itself, in the world layer
        # (`visual/key_marker.py`, journal: key_icons_journal.md).

    def buff_tint(self, surface: pygame.Surface) -> None:
        tint = self.ps.buffs.tint
        if tint is None:
            return
        left, palette = tint
        fb = self.ps.buffs.feedback
        seconds = float(fb.get("tint_seconds", 0.9))
        peak = int(fb.get("tint_peak_alpha", 55))
        alpha = int(peak * max(0.0, min(1.0, left / seconds)))
        if alpha <= 0:
            return
        w, h = surface.get_size()
        key = (w, h, tuple(palette))
        cached = getattr(self, "_tint_cache", None)
        if cached is None or cached[0] != key:
            # A one-column gradient through the palette, stretched to the
            # frame: built once per activation, faded with `set_alpha`.
            steps = 64
            column = pygame.Surface((1, steps), pygame.SRCALPHA)
            for i in range(steps):
                t = i / (steps - 1) * (len(palette) - 1)
                k, f = int(t), t - int(t)
                a_col = palette[min(k, len(palette) - 1)]
                b_col = palette[min(k + 1, len(palette) - 1)]
                column.set_at((0, i), tuple(int(a_col[c] + (b_col[c] - a_col[c]) * f)
                                            for c in range(3)) + (255,))
            self._tint_cache = cached = (key, pygame.transform.smoothscale(column, (w, h)))
        grad = cached[1]
        grad.set_alpha(alpha)
        surface.blit(grad, (0, 0))

    def hero_fx(self, surface, sx: float, sy: float) -> None:
        """The buff activation effects over the hero (journal:
        buff_buildings_journal.md): each strip plays once, feet-anchored,
        at its own frame rate, drawn right after the hero's sprite."""
        ps = self.ps
        run = getattr(self, "run", ps)
        fx_list = ps.buffs.hero_fx
        if not fx_list:
            return
        a = ps.game.assets
        z = run.camera.zoom
        drop = self.sprite_drop(run.player.radius)
        for rig, age, scale in fx_list:
            meta = a.rig(rig)
            if not meta:
                continue
            k = z * scale                      # the buff's own draw scale
            fw, fh = meta["frame"]
            size = (max(1, round(fw * k)), max(1, round(fh * k)))
            frs = a.frames(rig, "loop", size=size)
            if not frs:
                continue
            fps = a.fps(rig, "loop") or 12.0
            idx = min(len(frs) - 1, int(age * fps))
            ax, ay = a.anchor(rig)
            surface.blit(frs[idx], (round(sx - ax * k), round(sy - ay * k + drop)))

    # --- world props ----------------------------------------------
    def _off_band(self, level, pos) -> bool:
        """Is this flat effect on some other terrace than the band being
        painted? `level is None` means "draw it wherever it is", which is what
        every caller outside the banded world path passes."""
        if level is None:
            return False
        return self.run.game_map.renderer.level_at(pos[0], pos[1]) != level

    def _heal_frames(self, z: float):
        """The sanctuary's looping heal effect at this zoom, or `None`
        without the art (the ring below is then the placeholder)."""
        from game.assets import get_assets
        a = get_assets()
        meta = a.rig("fx_heal")
        if not meta:
            return None
        fw, fh = meta["frame"]
        size = (max(1, round(fw * z)), max(1, round(fh * z)))
        frs = a.frames("fx_heal", "loop", size=size)
        if not frs:
            return None
        ax, ay = a.anchor("fx_heal")
        return frs, a.fps("fx_heal", "loop"), ax * z, ay * z

    def interactables(self, surface, level=None) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        z = run.camera.zoom
        for it in run.interactables:
            if self._off_band(level, it.pos):
                continue
            if it.kind == "forge" and self._forge_skinned():
                continue        # the forge obstacle carries the art
            if ps.buffs.is_buff(it.kind):
                # A buff building: the obstacle draws it. An elemental one
                # gets its element's glow here, under the art (CMB-009.1).
                visuals = getattr(run, "element_visuals", None)
                if visuals is not None and visuals.building_glow is not None:
                    visuals.building_glow.draw(surface, run.camera, it,
                                               visuals.tint, run.stats["time"])
                continue
            if it.kind == "fountain":
                heal = self._heal_frames(z)
                if heal is not None:
                    if it.used:
                        continue        # healed once: the prop is gone
                    frs, fps, ax, ay = heal
                    sx, sy = run.camera.world_to_screen(it.pos)
                    idx = int(run.stats["time"] * fps) % len(frs)
                    surface.blit(frs[idx], (round(sx - ax), round(sy - ay)))
                    continue
            sx, sy = run.camera.world_to_screen(it.pos)
            done = it.used
            col = (90, 90, 100) if done else it.colour
            pygame.draw.circle(surface, col, (int(sx), int(sy)),
                               round(it.radius * z), 0 if done else 3)
            pygame.draw.circle(surface, (240, 245, 255), (int(sx), int(sy)), round(4 * z))

    def _forge_skinned(self) -> bool:
        """Did the bake skin a forge obstacle? Then the interactable draws
        nothing of its own; without the art the ring is the placeholder."""
        cached = getattr(self, "_forge_skin_cache", None)
        gm = self.run.game_map
        key = id(getattr(gm, "_decos", None))
        if cached is None or cached[0] != key:
            decos = getattr(gm, "_decos", {}) or {}
            skinned = any(o.kind == "forge" and i in decos
                          for i, o in enumerate(getattr(gm, "obstacles", ())))
            self._forge_skin_cache = cached = (key, skinned)
        return cached[1]

    def hazards(self, surface, level=None) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        z = run.camera.zoom
        for hz in run.hazards:
            if self._off_band(level, hz.pos):
                continue
            sx, sy = run.camera.world_to_screen(hz.pos)
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
        sx, sy = self.run.camera.world_to_screen(s.pos)
        draw_summon(surface, sx, sy, s, self._draw_ctx(), default="disc")

    def gems(self, surface, level=None) -> None:
        """XP orbs, each over its breathing glow (journal: "Breathing glow
        under the XP orbs"). The glow is blitted first so the orb's colour
        sits on top of it; it breathes on the gem's own `age`, so a field of
        orbs shimmers out of phase and freezes with the run. Cached discs --
        one lookup and one blit per orb. Off-screen gems draw nothing."""
        ps = self.ps
        run = getattr(self, "run", ps)
        z = run.camera.zoom
        assets = ps.game.assets
        view = run.camera.visible_rect().inflate(_GEM_CULL_PAD, _GEM_CULL_PAD)
        glow = self._glow

        for gem in run.gems:
            if self._off_band(level, gem.pos):
                continue
            if not view.collidepoint(gem.pos.x, gem.pos.y):
                continue
            sx, sy = run.camera.world_to_screen(gem.pos)
            rig = _ORB_RIGS.get(gem.tier, "xp_orb_small")
            base_size = assets.scale_for(rig) or (8, 8)
            size = (
                max(1, round(base_size[0] * z)),
                max(1, round(base_size[1] * z)),
            )

            halo = glow.pulsed(base_size[0], z, gem.age)
            if halo is not None:
                surface.blit(halo, halo.get_rect(center=(int(sx), int(sy))))

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

    def chests(self, surface, level=None) -> None:
        """CB-9: the treasure chests the seed seated across the islands.

        One rig per rarity, each a four-frame strip: frame 0 while closed,
        then across the strip as the lid flies open, holding the last frame
        for the rest of the run. The rig's anchor is bottom-centre on the
        chest's baseline, so the box stays put while the lid moves. Missing
        art falls back to a disc in the rarity's colour, like the orbs.
        """
        ps = self.ps
        run = getattr(self, "run", ps)
        z = run.camera.zoom
        assets = ps.game.assets
        table = run.content.chests
        duration = _chests.open_seconds(table)
        view = run.camera.visible_rect().inflate(_GEM_CULL_PAD, _GEM_CULL_PAD)

        for chest in run.chests:
            if self._off_band(level, chest.pos):
                continue
            if not view.collidepoint(chest.pos.x, chest.pos.y):
                continue
            sx, sy = run.camera.world_to_screen(chest.pos)
            rig = _chests.sprite_rig(chest.rarity, table)
            base_size = assets.scale_for(rig) or (30, 30)
            size = (max(1, round(base_size[0] * z)), max(1, round(base_size[1] * z)))
            index = chest.frame_index(assets.frame_count(rig, "open") or 1, duration)
            art = assets.frame(rig, "open", index, size=size)
            if art is not None:
                ax, ay = assets.anchor(rig)
                surface.blit(art, (int(sx - ax * z), int(sy - ay * z)))
                continue
            colour = _chests.colour(chest.rarity, table)
            if chest.opened:
                colour = tuple(c // 2 for c in colour)
            pygame.draw.circle(surface, colour, (int(sx), int(sy)),
                               max(2, round(base_size[0] * 0.4 * z)),
                               0 if chest.opened else 3)

    def potions(self, surface, level=None) -> None:
        """CB-8: dropped health potions, over the same breathing glow the XP
        orbs use so the two drop kinds read as one family. The glow is tinted
        by rarity, and the rig's own `scale` already grows with rarity, so a
        rare potion is legible across the screen. Off-screen potions draw
        nothing; missing art falls back to a disc like the orbs do."""
        ps = self.ps
        run = getattr(self, "run", ps)
        z = run.camera.zoom
        assets = ps.game.assets
        table = run.content.potions
        view = run.camera.visible_rect().inflate(_GEM_CULL_PAD, _GEM_CULL_PAD)

        for potion in run.potions:
            if self._off_band(level, potion.pos):
                continue
            if not view.collidepoint(potion.pos.x, potion.pos.y):
                continue
            sx, sy = run.camera.world_to_screen(potion.pos)
            rig = _potions.sprite_rig(potion.rarity, table)
            base_size = assets.scale_for(rig) or (16, 16)
            size = (max(1, round(base_size[0] * z)), max(1, round(base_size[1] * z)))

            halo = self._glow.pulsed(base_size[0], z, potion.age)
            if halo is not None:
                surface.blit(halo, halo.get_rect(center=(int(sx), int(sy))))

            art = assets.image(rig, size=size)
            if art is not None:
                surface.blit(art, art.get_rect(center=(int(sx), int(sy))))
            else:
                pygame.draw.circle(surface,
                                   _potions.colour(potion.rarity, table),
                                   (int(sx), int(sy)),
                                   max(2, round(base_size[0] * 0.4 * z)))

    def explosions(self, surface, level=None) -> None:
        """Blast visuals: an entry carrying an `anim` (the Bomb's `explosion`
        burst) blits its current frame scaled so the rig's `fireball` width
        spans the blast diameter, centred on the blast; the rest, and any
        burst whose sheet is missing, draw the expanding ring."""
        ps = self.ps
        run = getattr(self, "run", ps)
        z = run.camera.zoom
        for ex in run._explosions:
            if self._off_band(level, ex["pos"]):
                continue
            sx, sy = ps.camera.world_to_screen(ex["pos"])
            anim = ex.get("anim")
            if anim is not None and self._blit_burst(surface, anim, sx, sy,
                                                     ex["radius"] * z,
                                                     ex.get("infusion")):
                continue
            frac = ex["t"] / ex["dur"]
            pygame.draw.circle(surface, (255, 180, 90),
                               (int(sx), int(sy)), int(ex["radius"] * frac * z), 3)

    def _blit_burst(self, surface, anim, sx, sy, radius_px: float,
                    infusion=None) -> bool:
        assets = self.ps.game.assets
        from game.states.playing.visual import elements as element_fx
        # An infused blast detonates in its element's colour (M13). The
        # Animator holds the plain rig and keeps timing the strip; only the
        # sheet the frame is taken from changes, and the variants are
        # frame-for-frame copies of it.
        name = element_fx.variant_rig(assets, anim.rig, infusion)
        rig = assets.rig(name) or {}
        bw, bh = assets.scale_for(name) or (0, 0)
        fireball = float(rig.get("fireball") or bw)
        if not bw or not fireball:
            return False
        k = 2.0 * radius_px / fireball          # rig px -> screen px
        frame = assets.frame(name, anim.anim, anim.index,
                             size=(max(1, round(bw * k)), max(1, round(bh * k))))
        if frame is None:
            return False
        ax, ay = assets.anchor(name)
        surface.blit(frame, (sx - ax * k, sy - ay * k))
        return True

    def trail_fx(self, surface, level=None) -> None:
        """Projectile dust trails -- each `[Animator, pos, size, tint, fade]`
        entry blits the current burst frame (tinted), optionally alpha-ramped
        over its life. Anchored in world space; the bolt draws over it."""
        ps = self.ps
        run = getattr(self, "run", ps)
        z = run.camera.zoom
        a = ps.game.assets
        for anim, pos, (w, h), tint, fade in run._trail_fx:
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
            sx, sy = run.camera.world_to_screen(pos)
            surface.blit(fr, fr.get_rect(center=(int(sx), int(sy))))

    # --- characters (depth layer) --------------------------------
    def one_enemy(self, surface, e) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        if self.spawn_veiled(e):
            return                              # still inside its spawn burst
        z = run.camera.zoom
        sx, sy = run.camera.world_to_screen(e.pos)
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
            else:
                # No status of its own: show the aura instead, so the
                # primitive fallback carries the same information the
                # sprited path does.
                primed = aura_colour(run, e)
                if primed is not None and e.hit_flash <= 0:
                    colour = primed[1]
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

        # Over the head, and only once the enemy has been hurt: its length
        # states the enemy's maximum HP, its fill what is left of it. The boss
        # never reaches here -- it is not one of `run.enemies` -- so it keeps
        # the HUD's own bar and gains no second one.
        health_bars.draw(surface, self, e)

    def death_fx(self, surface, fx) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        anim, pos, facing, scale, radius = fx
        z = run.camera.zoom
        scale *= z
        assets = ps.game.assets
        bw, bh = assets.scale_for("dead")
        size = (max(1, round(bw * scale)), max(1, round(bh * scale)))
        flip = facing < 0 and assets.face("dead") == "right"
        frame = anim.frame(size=size, flip=flip)
        if frame is None:
            return
        ax, ay = self.anchor_for("dead", flip)
        sx, sy = ps.camera.world_to_screen(pos)
        drop = self.sprite_drop(radius)     # match the sprite this poof replaced
        self._blit_character(
            surface, frame, (sx - ax * scale, sy - ay * scale + drop), pos.y)

    # --- the enemy spawn burst ---------------------------------
    _SPAWN_RIG = "enemy_spawn"

    def spawn_veiled(self, body) -> bool:
        """Is `body` still hidden inside its spawn burst? True from its
        spawn until the burst reaches the rig's `reveal_frame` (the ball
        breaking), so the sprite steps out of the burst rather than standing
        under a spark. Render-only: the body itself is live throughout."""
        anim = getattr(body, "_spawn_fx", None)
        if anim is None or anim.finished:
            return False
        rig = self.ps.game.assets.rig(self._SPAWN_RIG) or {}
        return anim.index < int(rig.get("reveal_frame", 0))

    def spawn_fx_geometry(self, body) -> tuple[float, float, float]:
        """Where the burst sits and how wide it is, in screen px:
        `(cx, cy, diameter)`. A sprited body gets the ring round the centre
        of its drawn frame -- the same anchor + drop arithmetic the sprite
        itself uses, so a bottom-anchored body is wrapped at its middle, not
        its feet -- with the diameter `over_sprite` x its larger drawn side.
        A rig-less body gets the collider: its centre, and `over_sprite` x
        its diameter."""
        ps = self.ps
        run = getattr(self, "run", ps)
        assets = ps.game.assets
        z = run.camera.zoom
        sx, sy = run.camera.world_to_screen(body.pos)
        over = float((assets.rig(self._SPAWN_RIG) or {}).get("over_sprite", 1.0))
        anim = getattr(body, "anim", None)
        scale = assets.scale_for(anim.rig) if anim is not None else None
        if scale:
            bw, bh = scale
            flip = getattr(body, "_facing", 1) < 0 and assets.face(anim.rig) == "right"
            ax, ay = self.anchor_for(anim.rig, flip)
            left = sx - ax * z
            top = sy - ay * z + self.sprite_drop(body.radius)
            return (left + bw * z / 2.0, top + bh * z / 2.0, over * max(bw, bh) * z)
        return (sx, sy, over * 2.0 * body.radius * z)

    def spawn_fx(self, surface, fx) -> None:
        """One `[Animator, body]` entry of `ps._spawn_fx`: the current burst
        frame, scaled so the rig's `ring` spans the diameter
        `spawn_fx_geometry` asks for, centred there."""
        anim, body = fx
        assets = self.ps.game.assets
        rig = assets.rig(anim.rig) or {}
        bw, bh = assets.scale_for(anim.rig) or (0, 0)
        ring = float(rig.get("ring") or bw)
        if not bw or not ring:
            return
        cx, cy, diameter = self.spawn_fx_geometry(body)
        k = diameter / ring                     # rig px -> screen px
        frame = anim.frame(size=(max(1, round(bw * k)), max(1, round(bh * k))))
        if frame is None:
            return
        ax, ay = assets.anchor(anim.rig)
        surface.blit(frame, (cx - ax * k, cy - ay * k))

    def enemy_sprite(self, surface, e) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        z = run.camera.zoom
        assets = ps.game.assets
        rig = e.anim.rig
        flip = e._facing < 0 and assets.face(rig) == "right"
        bw, bh = assets.scale_for(rig)
        frame = e.anim.frame(size=(max(1, round(bw * z)), max(1, round(bh * z))),
                             flip=flip)
        sx, sy = run.camera.world_to_screen(e.pos)
        if frame is None:                        # sprite file missing -> primitive
            pygame.draw.circle(surface, e.color, (int(sx), int(sy)),
                               round(e.radius * z))
            return
        if e._hurt_t > 0.0:
            frame = hit_tinted(frame)           # red flash, no pop to a circle
        else:
            # A primed body wears its element, lightly (M10). Not while it is
            # flashing: a hit is the more urgent thing to see and it is over
            # in a quarter of a second.
            primed = aura_colour(run, e)
            if primed is not None:
                from game.states.playing.visual import elements as element_fx
                frame = element_fx.washed(frame, primed[0])
        ax, ay = self.anchor_for(rig, flip)
        self._blit_character(
            surface, frame,
            (sx - ax * z, sy - ay * z + self.sprite_drop(e.radius)), e.pos.y)

    def boss(self, surface) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        b = run.boss
        if b is None or not b.alive or self.spawn_veiled(b):
            return
        z = run.camera.zoom
        sx, sy = run.camera.world_to_screen(b.pos)
        br = b.radius * z
        assets = ps.game.assets
        frame = None
        if b.anim is not None:
            rig = b.anim.rig
            flip = b._facing < 0 and assets.face(rig) == "right"
            bw, bh = assets.scale_for(rig)
            frame = b.anim.frame(size=(max(1, round(bw * z)), max(1, round(bh * z))),
                                 flip=flip)
        if frame is not None:
            if b._hurt_t > 0.0:
                frame = hit_tinted(frame)
            ax, ay = self.anchor_for(rig, flip)
            self._blit_character(
                surface, frame,
                (sx - ax * z, sy - ay * z + self.sprite_drop(b.radius)), b.pos.y)
        else:
            colour = (255, 255, 255) if b.hit_flash > 0 else b.color
            pygame.draw.circle(surface, colour, (int(sx), int(sy)), round(br))
            pygame.draw.circle(surface, (255, 210, 210), (int(sx), int(sy)),
                               round(br), 3)
        if b.phase == "telegraph" and not b.closing:
            pid = b.pattern.get("id")
            frac = b.telegraph_fraction
            if pid == "radial_barrage":
                pygame.draw.circle(surface, (255, 140, 140), (int(sx), int(sy)),
                                   round((40 + 220 * frac) * z), 2)
            elif pid == "charge":
                d = run.player.pos - b.pos
                if d.length_squared() > 1:
                    d = d.normalize() * 900
                    ex, ey = run.camera.world_to_screen(b.pos + d)
                    pygame.draw.line(surface, (255, 120, 120), (sx, sy), (ex, ey), 3)
            elif pid == "summon_brood":
                pygame.draw.circle(surface, (150, 220, 160), (int(sx), int(sy)),
                                   round(br + 20 * frac * z), 2)

    def player(self, surface) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        if not run.player.alive:
            return                              # the death poof (_death_fx) stands in
        z = run.camera.zoom
        sx, sy = run.camera.world_to_screen(run.player.pos)
        pr = run.player.radius * z

        frame = self.hero_sprite_frame()
        if frame is not None:
            # `anchor` is the pixel in the final sprite that sits on the world
            # position (bottom-centre-ish -- the art is bottom-heavy); the drop
            # then seats it below the collider centre (config.SPRITE_ANCHOR_DROP).
            ax, ay = self.anchor_for(ps._hero_anim.rig, self._hero_flip())
            if run.player._hurt_t > 0.0:
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
        self.hero_fx(surface, sx, sy)

    def _hero_flip(self) -> bool:
        ps = self.ps
        run = getattr(self, "run", ps)
        return run.player._facing < 0 and ps.game.assets.face(ps._hero_anim.rig) == "right"

    def hero_sprite_frame(self):
        ps = self.ps
        run = getattr(self, "run", ps)
        if ps._hero_anim is None:
            return None
        rig = ps._hero_anim.rig
        z = run.camera.zoom
        bw, bh = ps.game.assets.scale_for(rig)
        return ps._hero_anim.frame(
            size=(max(1, round(bw * z)), max(1, round(bh * z))),
            flip=self._hero_flip())

    # --- projectiles / summons (per-family draw in the sub-packages) ---
    def _draw_ctx(self) -> DrawCtx:
        ps = self.ps
        run = getattr(self, "run", ps)
        return DrawCtx(ps.game.assets, run.stats["time"], run.camera.zoom)

    def player_projectiles(self, surface, level=None) -> None:
        cam, ctx = self.run.camera, self._draw_ctx()
        for p in self.run.projectiles:
            if self._off_band(level, p.pos):
                continue
            sx, sy = cam.world_to_screen(p.pos)
            draw_projectile(surface, sx, sy, p, ctx, default="bolt")

    def hostile_projectiles(self, surface) -> None:
        """Enemy and boss shots, each over a faint steady glow (journal:
        "Breathing glow under the XP orbs", group D): the same cached disc
        as the orbs at one constant alpha, sized from the shot's collider,
        blitted before the arrow. Off-screen shots draw nothing."""
        cam, ctx = self.run.camera, self._draw_ctx()
        z = cam.zoom
        view = cam.visible_rect().inflate(_GEM_CULL_PAD, _GEM_CULL_PAD)
        cfg = config.HOSTILE_GLOW
        scale, alpha, colour = float(cfg["scale"]), int(cfg["alpha"]), cfg["colour"]
        glow = self._glow
        for p in self.run.hostiles:
            if not view.collidepoint(p.pos.x, p.pos.y):
                continue
            sx, sy = cam.world_to_screen(p.pos)
            if scale > 0.0 and alpha > 0:
                d = max(2, int(round(p.radius * 2 * scale * z)))
                halo = glow.surface(d, alpha, colour)
                if halo is not None:
                    surface.blit(halo, halo.get_rect(center=(int(sx), int(sy))))
            draw_projectile(surface, sx, sy, p, ctx, default="arrow")

    # --- dev overlays -- see devtools/overlays.py --------------
    def spawn_point_overlay(self, surface) -> None:
        overlays.spawn_point_overlay(surface, self.ps)

    def aim_overlay(self, surface) -> None:
        overlays.aim_overlay(surface, self.ps)

    def aura_overlay(self, surface) -> None:
        overlays.aura_overlay(surface, self.ps)

    def reaction_log_overlay(self, surface) -> None:
        overlays.reaction_log_overlay(surface, self.ps)

    def collider_overlay(self, surface) -> None:
        overlays.collider_overlay(surface, self.ps)
