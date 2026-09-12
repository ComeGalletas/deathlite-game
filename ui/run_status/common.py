"""What the run status panes share: the dim layer and panel, the ribbon
tabs, the row primitives, and how a hero stat or a modifier is printed.

Stat formatting lives here rather than in `progression.stats` because it is
presentation: the stat set is a pure number store and has no opinion about
whether `crit_chance` reads as `12%` or `0.12`.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from ui import widgets

ROW_STEP = 26
RIBBON_H = 48
TITLE_DY = -5          # ribbon labels sit above the art's geometric centre (owner, 2026-09-12)
_PANEL_FILL = (10, 8, 14, 215)
_RULE = config.COLOR_WORLD_BORDER
_TAB_SHADE = (0, 0, 0, 120)

# Rarity colours legible on the dark ground (the config ones are inks for the
# light button art).
RARITY_ON_DARK = {"common": config.COLOR_TEXT, "uncommon": (130, 225, 150),
                  "rare": (150, 170, 255), "forge": (255, 185, 90)}

# (stat, label, kind) in display order. `kind` picks the formatter:
#   num   -- a plain number (HP, px/s, px)
#   flat  -- a flat amount shown with its sign
#   pct   -- a fraction shown as a percentage (chances, +gain fractions)
#   mult  -- a multiplier shown as x1.25
STAT_ROWS = (
    ("max_hp", "Max HP", "num"),
    ("move_speed", "Move speed", "num"),
    ("armor", "Armor", "num"),
    ("damage_multiplier", "Damage", "mult"),
    ("melee_damage", "Melee damage", "pctplus"),
    ("ranged_damage", "Ranged damage", "pctplus"),
    ("attack_speed_multiplier", "Attack speed", "mult"),
    ("projectile_speed_multiplier", "Projectile speed", "mult"),
    ("area_multiplier", "Area", "mult"),
    ("crit_chance", "Crit chance", "pct"),
    ("crit_damage", "Crit damage", "pctplus"),
    ("evasion_chance", "Evasion", "pct"),
    ("block_chance", "Block chance", "pct"),
    ("block_strength", "Block strength", "pct"),
    ("pickup_radius", "Pickup radius", "num"),
    ("luck", "Luck", "num"),
    ("xp_gain", "XP gain", "pctplus"),
    ("gold_gain", "Gold gain", "pctplus"),
)
STAT_LABELS = {stat: label for stat, label, _k in STAT_ROWS}


def stat_label(stat: str) -> str:
    return STAT_LABELS.get(stat, stat.replace("_", " ").capitalize())


def fmt_stat(stat: str, value: float) -> str:
    kind = next((k for s, _l, k in STAT_ROWS if s == stat), "num")
    if kind == "mult":
        return f"x{value:.2f}"
    if kind == "pct":
        return f"{value * 100:.0f}%"
    if kind == "pctplus":
        return f"{value * 100:+.0f}%"
    return f"{value:g}"


def fmt_mod(stat: str, op: str | None, value: float) -> str:
    """A modifier as an item or a blessing would state it: `+20 Max HP`,
    `+12% Damage`, `x1.1 Attack speed`."""
    label = stat_label(stat)
    if op == "pct":
        return f"{value * 100:+.0f}% {label}"
    if op == "mult":
        return f"x{1.0 + value:.2f} {label}"
    # flat: chances and multipliers are fractions even when flat
    kind = next((k for s, _l, k in STAT_ROWS if s == stat), "num")
    if kind in ("pct", "pctplus", "mult"):
        return f"{value * 100:+.0f}% {label}"
    # Item rolls are unrounded floats (+3.917 armor); one decimal is what a
    # player can use, and a whole number stays whole.
    return f"{_one_decimal(value)} {label}"


def _one_decimal(value: float) -> str:
    text = f"{value:+.1f}"
    return text[:-2] if text.endswith(".0") else text


class Fonts:
    """The faces the panes share, built once per screen."""

    def __init__(self) -> None:
        self.ribbon = fonts.heading(22)
        self.title = fonts.heading(28)
        self.sub = fonts.heading(20)
        self.row = fonts.body(20)
        self.small = fonts.body(16)


# --- surfaces ----------------------------------------------------------
def draw_dim(surface: pygame.Surface) -> None:
    dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 150))
    surface.blit(dim, (0, 0))


def draw_panel(surface: pygame.Surface, rect: pygame.Rect) -> None:
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill(_PANEL_FILL)
    surface.blit(panel, rect.topleft)
    pygame.draw.rect(surface, _RULE, rect, width=1, border_radius=8)


def draw_tabs(surface, assets, rect: pygame.Rect, labels, active: int,
              font, hits) -> list[pygame.Rect]:
    """Three ribbons across the top edge of `rect`, the active one lit, the
    others shaded. Registers each as `("tab", i)` in `hits`."""
    colours = ("blue", "yellow", "red")
    n = len(labels)
    gap = 24
    w = min(320, (rect.width - 32 - gap * (n - 1)) // n)
    total = n * w + gap * (n - 1)
    x = rect.centerx - total // 2
    rects = []
    for i, label in enumerate(labels):
        r = pygame.Rect(x + i * (w + gap), rect.top - RIBBON_H // 2 + 8, w, RIBBON_H)
        widgets.draw_ribbon(surface, assets, r, None, colour=colours[i % 3])
        text = font.render(label, True, config.COLOR_ON_BUTTON)
        surface.blit(text, text.get_rect(center=(r.centerx, r.centery + TITLE_DY)))
        if i != active:
            shade = pygame.Surface(r.size, pygame.SRCALPHA)
            shade.fill(_TAB_SHADE)
            surface.blit(shade, r.topleft)
        hits.add(r, ("tab", i))
        rects.append(r)
    return rects


# --- rows ------------------------------------------------------------------
def kv(surface, font, area, y, label, value, *, colour=None, label_colour=None) -> int:
    lab = font.render(str(label), True, label_colour or config.COLOR_TEXT_DIM)
    surface.blit(lab, lab.get_rect(midleft=(area.left, y)))
    val = font.render(str(value), True, colour or config.COLOR_TEXT)
    surface.blit(val, val.get_rect(midright=(area.right, y)))
    return y + ROW_STEP


def line(surface, font, area, y, text, *, colour=None, indent: int = 0,
         step: int = ROW_STEP) -> int:
    t = font.render(str(text), True, colour or config.COLOR_TEXT)
    surface.blit(t, t.get_rect(midleft=(area.left + indent, y)))
    return y + step


def subheader(surface, font, area, y, text) -> int:
    y += 6
    t = font.render(text, True, config.COLOR_ACCENT)
    surface.blit(t, t.get_rect(midleft=(area.left, y)))
    pygame.draw.line(surface, _RULE, (area.left, y + 15), (area.right, y + 15))
    return y + ROW_STEP + 4


def rule(surface, area, y) -> int:
    pygame.draw.line(surface, _RULE, (area.left, y - 2), (area.right, y - 2))
    return y + 6


def more(surface, font, area, y, n: int, what: str) -> int:
    if n <= 0:
        return y
    return line(surface, font, area, y, f"+{n} more {what}", colour=config.COLOR_TEXT_DIM)


def fits(area, y, rows: int, step: int = ROW_STEP) -> int:
    """How many of `rows` rows fit between `y` and the area's bottom, leaving
    the last slot for a "+n more" line when they do not all fit."""
    room = max(0, (area.bottom - y) // step + 1)
    return rows if rows <= room else max(0, room - 1)
