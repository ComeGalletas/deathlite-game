"""In-run HUD (spec 3.6).

Four things, and deliberately no more (owner, 2026-09-12): the level gem, the
HP bar and the XP bar in the top-left cluster, and the run timer at the top
centre. The kill and gold counters, the trait line, the blessing list and the
weapon list used to crowd the other three corners; they were cut because the
run-status screen (TAB) already shows all of it on demand, in more detail,
without sitting on top of the fight. The boss bar stays -- it appears only
during a boss fight and is combat readability, not a readout -- and it is cut
from the same hex family, framed and half the screen wide.

The HP / XP cluster is drawn from the HUD sheets through `ui/bars/` -- the hex
family of `assets/ui/04.png` for the two bars, `01.png`'s gem for the level
medallion (owner, 2026-09-12; see
`documentation/journals/hud_rework_journal.md`). `_draw_meters` returns False
when those sheets are missing and `_draw_flat_meters` takes over with the
primitive rectangles the HUD drew before, the same degrade contract as
`game/assets.py`.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from game.assets import get_assets
from ui import bars
from ui import text as uitext


class HUD:
    def __init__(self) -> None:
        self._font = fonts.body(18)
        self._big = fonts.heading(22)
        self._lvl = fonts.body(20, bold=True)

    # --- HP / XP cluster (top-left) ------------------------------
    def _draw_meters(self, surface: pygame.Surface, player, stats: dict,
                     xp_fraction: float | None) -> bool:
        """The art cluster: level gem, framed HP bar, bare XP bar under it.
        False when the sheets are missing, so `draw` can fall back."""
        assets = get_assets()
        frac = 0.0 if player.max_hp <= 0 else max(0.0, player.hp / player.max_hp)
        hp = bars.bar(assets, frame=config.HUD_BAR_FRAME,
                      fill=config.HUD_BAR_HP_FILL, empty=config.HUD_BAR_EMPTY,
                      width=config.HUD_BAR_WIDTH, fraction=frac, framed=True,
                      scale=config.HUD_BAR_SCALE)
        if hp is None:
            return False
        xp = None if xp_fraction is None else bars.bar(
            assets, frame=config.HUD_BAR_FRAME, fill=config.HUD_BAR_XP_FILL,
            empty=config.HUD_BAR_EMPTY, width=config.HUD_BAR_WIDTH,
            fraction=xp_fraction, framed=False, scale=config.HUD_BAR_SCALE)
        gem = bars.medallion(assets, socket=config.HUD_GEM_SOCKET,
                             core=config.HUD_GEM_CORE, size=config.HUD_GEM_PX)

        # The gap rides the scale so the cluster keeps its proportions when
        # HUD_BAR_SCALE changes; the bar stack is centred on the medallion.
        gap = 2 * config.HUD_BAR_SCALE
        stack_h = hp.get_height() + (gap + xp.get_height() if xp else 0)
        top, left = config.HUD_LEFT_TOP, 16
        bar_x = left + (gem.get_width() + 8 if gem else 0)
        bar_y = top + max(0, ((gem.get_height() if gem else stack_h) - stack_h) // 2)

        if gem is not None:
            surface.blit(gem, (left, top))
            # Near-black on the bright cyan gem, the same rule as text on the
            # light button art.
            num = self._lvl.render(str(stats.get("level", 1)), True,
                                   config.COLOR_ON_BUTTON)
            surface.blit(num, num.get_rect(center=(
                left + gem.get_width() // 2, top + gem.get_height() // 2)))

        surface.blit(hp, (bar_x, bar_y))
        readout = uitext.shadowed(
            self._font, f"{int(player.hp)} / {int(player.max_hp)}",
            config.COLOR_TEXT, offset=(1, 1))
        surface.blit(readout, readout.get_rect(center=(
            bar_x + hp.get_width() // 2, bar_y + hp.get_height() // 2)))
        if xp is not None:
            surface.blit(xp, (bar_x, bar_y + hp.get_height() + gap))
        return True

    def _draw_flat_meters(self, surface: pygame.Surface, player,
                          xp_fraction: float | None) -> None:
        """Primitive HP / XP rectangles -- the fallback when the HUD sheets in
        `assets/ui/` are missing, so the game stays playable without them."""
        bar_w, bar_h = 260, 20
        x, y = 16, config.HUD_LEFT_TOP
        pygame.draw.rect(surface, (40, 12, 14), (x, y, bar_w, bar_h))
        frac = 0.0 if player.max_hp <= 0 else max(0.0, player.hp / player.max_hp)
        pygame.draw.rect(surface, (210, 70, 70),
                         (x, y, int(bar_w * frac), bar_h))
        pygame.draw.rect(surface, config.COLOR_WORLD_BORDER,
                         (x, y, bar_w, bar_h), width=2)
        hp_text = self._font.render(
            f"{int(player.hp)} / {int(player.max_hp)}", True, config.COLOR_TEXT)
        surface.blit(hp_text, hp_text.get_rect(center=(x + bar_w // 2, y + bar_h // 2)))
        if xp_fraction is not None:
            xy = y + bar_h + 6
            pygame.draw.rect(surface, (14, 20, 40), (x, xy, bar_w, 8))
            pygame.draw.rect(surface, (90, 150, 240),
                             (x, xy, int(bar_w * max(0.0, min(1.0, xp_fraction))), 8))

    # --- boss bar (bottom-centre) --------------------------------
    def _boss_top(self, surface: pygame.Surface, height: int) -> int:
        """Top edge of a boss bar `height` px tall: HUD_BOSS_BOTTOM clear of
        the bottom of the screen, whichever art drew it."""
        return surface.get_height() - config.HUD_BOSS_BOTTOM - height

    def _draw_boss(self, surface: pygame.Surface, boss) -> bool:
        """The boss bar in the same hex family as the hero's, framed and wide.
        False when the sheets are missing, so `draw` can fall back."""
        scale = config.HUD_BAR_SCALE
        # Native width from the screen, so the bar stays half the frame at any
        # resolution and still lands on a whole number of source pixels.
        width = int(surface.get_width() * config.HUD_BOSS_WIDTH) // scale
        bar = bars.bar(get_assets(), frame=config.HUD_BOSS_FRAME,
                       fill=config.HUD_BOSS_FILL, empty=config.HUD_BAR_EMPTY,
                       width=width, fraction=getattr(boss, "hp_fraction", 0.0),
                       framed=True, scale=scale)
        if bar is None:
            return False
        x = (surface.get_width() - bar.get_width()) // 2
        y = self._boss_top(surface, bar.get_height())
        surface.blit(bar, (x, y))
        name = uitext.shadowed(self._big, getattr(boss, "name", ""),
                               config.HUD_BOSS_NAME_COLOR, offset=(2, 2))
        surface.blit(name, name.get_rect(
            midbottom=(surface.get_width() // 2, y - 6)))
        return True

    def _draw_flat_boss(self, surface: pygame.Surface, boss) -> None:
        """The primitive boss rectangle -- the fallback when the sheets are
        missing, so a boss fight stays readable without them."""
        w = surface.get_width()
        bw, bh = int(w * config.HUD_BOSS_WIDTH), 18
        bx, by = (w - bw) // 2, self._boss_top(surface, bh)
        pygame.draw.rect(surface, (30, 8, 12), (bx, by, bw, bh))
        pygame.draw.rect(surface, (220, 60, 80),
                         (bx, by, int(bw * boss.hp_fraction), bh))
        pygame.draw.rect(surface, (255, 210, 210), (bx, by, bw, bh), width=2)
        name = self._font.render(boss.name, True, config.COLOR_TEXT)
        surface.blit(name, name.get_rect(midbottom=(w // 2, by - 4)))

    def draw(self, surface: pygame.Surface, player, stats: dict,
             xp_fraction: float | None = None, boss=None) -> None:
        w = surface.get_width()

        if not self._draw_meters(surface, player, stats, xp_fraction):
            self._draw_flat_meters(surface, player, xp_fraction)

        # --- timer (top-centre) ----------------------------------
        t = int(stats.get("time", 0.0))
        clock_text = self._big.render(f"{t // 60:02d}:{t % 60:02d}", True,
                                      config.COLOR_TEXT)
        surface.blit(clock_text, clock_text.get_rect(midtop=(w // 2, 14)))

        # --- boss bar (bottom-centre) --------------------------
        alive = boss is not None and getattr(boss, "alive", False)
        if alive and not self._draw_boss(surface, boss):
            self._draw_flat_boss(surface, boss)
