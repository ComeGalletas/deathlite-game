"""In-run HUD (spec 3.6). Milestone 2: HP bar, run timer, kill count, weapon
list. XP bar and level pip are added in Milestone 3, boss bar in Milestone 4.
"""
from __future__ import annotations

import pygame

from game import config


class HUD:
    def __init__(self) -> None:
        self._font = pygame.font.SysFont("georgia", 18)
        self._big = pygame.font.SysFont("georgia", 22, bold=True)

    def draw(self, surface: pygame.Surface, player, stats: dict,
             xp_fraction: float | None = None, boss=None) -> None:
        w = surface.get_width()

        # --- HP bar (top-left) ---------------------------------------
        bar_w, bar_h = 260, 20
        x, y = 16, 16
        pygame.draw.rect(surface, (40, 12, 14), (x, y, bar_w, bar_h))
        frac = 0.0 if player.max_hp <= 0 else max(0.0, player.hp / player.max_hp)
        pygame.draw.rect(surface, (210, 70, 70),
                         (x, y, int(bar_w * frac), bar_h))
        pygame.draw.rect(surface, config.COLOR_WORLD_BORDER,
                         (x, y, bar_w, bar_h), width=2)
        hp_text = self._font.render(
            f"{int(player.hp)} / {int(player.max_hp)}", True, config.COLOR_TEXT)
        surface.blit(hp_text, hp_text.get_rect(center=(x + bar_w // 2, y + bar_h // 2)))

        # --- XP bar just below (M3 fills xp_fraction) --------------
        if xp_fraction is not None:
            xy = y + bar_h + 6
            pygame.draw.rect(surface, (14, 20, 40), (x, xy, bar_w, 8))
            pygame.draw.rect(surface, (90, 150, 240),
                             (x, xy, int(bar_w * max(0.0, min(1.0, xp_fraction))), 8))

        # --- timer (top-centre) ----------------------------------
        t = int(stats.get("time", 0.0))
        clock_text = self._big.render(f"{t // 60:02d}:{t % 60:02d}", True,
                                      config.COLOR_TEXT)
        surface.blit(clock_text, clock_text.get_rect(midtop=(w // 2, 14)))

        # --- level + kills (top-right) --------------------------
        lvl = self._font.render(f"LV {stats.get('level', 1)}", True, config.COLOR_ACCENT)
        kills = self._font.render(f"Kills {stats.get('kills', 0)}", True,
                                  config.COLOR_TEXT_DIM)
        gold = self._font.render(f"Gold {stats.get('gold', 0)}", True, (220, 190, 120))
        surface.blit(lvl, lvl.get_rect(topright=(w - 16, 16)))
        surface.blit(kills, kills.get_rect(topright=(w - 16, 38)))
        surface.blit(gold, gold.get_rect(topright=(w - 16, 60)))

        # --- weapons (bottom-left) -----------------------------
        for i, weapon in enumerate(getattr(player, "weapons", [])):
            label = self._font.render(f"{weapon.name}  Lv{weapon.level}", True,
                                      config.COLOR_TEXT_DIM)
            surface.blit(label, (16, surface.get_height() - 28 - i * 22))

        # --- blessings + trait (right side) --------------------
        y = 88
        trait = getattr(player, "trait", "")
        if trait:
            momentum = getattr(player, "momentum", 0.0)
            extra = f"  x{momentum:.1f}" if trait == "windborne" and momentum else ""
            t = self._font.render(f"Trait: {trait}{extra}", True, (150, 200, 255))
            surface.blit(t, t.get_rect(topright=(w - 16, y)))
            y += 24
        for bid, stacks in list(getattr(player, "blessings", {}).items())[:8]:
            name = bid.split("_", 1)[-1].replace("_", " ").title()
            s = f"{name}" + (f" x{stacks}" if stacks > 1 else "")
            label = self._font.render(s, True, config.COLOR_TEXT_DIM)
            surface.blit(label, label.get_rect(topright=(w - 16, y)))
            y += 20

        # --- boss bar (bottom-centre) --------------------------
        if boss is not None and getattr(boss, "alive", False):
            bw, bh = int(w * 0.5), 18
            bx = (w - bw) // 2
            by = surface.get_height() - 46
            pygame.draw.rect(surface, (30, 8, 12), (bx, by, bw, bh))
            pygame.draw.rect(surface, (220, 60, 80),
                             (bx, by, int(bw * boss.hp_fraction), bh))
            pygame.draw.rect(surface, (255, 210, 210), (bx, by, bw, bh), width=2)
            name = self._font.render(boss.name, True, config.COLOR_TEXT)
            surface.blit(name, name.get_rect(midbottom=(w // 2, by - 4)))
