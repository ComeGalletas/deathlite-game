"""What the run status panes share: the dim layer and panel, the ribbon
tabs, the row primitives, and how a hero stat or a modifier is printed.

Stat formatting lives here rather than in `progression.stats` because it is
presentation: the stat set is a pure number store and has no opinion about
whether `crit_chance` reads as `12%` or `0.12`.
"""
from __future__ import annotations

import pygame

from game import config, fonts, locale
from ui import text as uitext
from ui import widgets
from ui import scale, veil

ROW_STEP = 26          # design px: every number in this package is, and is
RIBBON_H = 48          # scaled at the point of use with `S` (`ui/scale.px`)
TITLE_DY = -5          # ribbon labels sit above the art's geometric centre (owner, 2026-09-12)


def S(n: float) -> int:
    """`n` design pixels in native pixels (`ui/scale.px`)."""
    return scale.px(n)
_PANEL_FILL = (10, 8, 14, 215)
_RULE = config.COLOR_WORLD_BORDER
# An inactive tab is the ribbon art multiplied down to this fraction of its
# colour -- the same darkening a 120/255 black wash gives, but applied to
# the ribbon's own pixels only, so the shade traces the forked shape rather
# than boxing it (owner, 2026-09-12). Alpha is left alone (255 in the tuple).
_TAB_SHADE_MULT = (135, 135, 135, 255)

# Rarity colours legible on the dark ground (the config ones are inks for the
# light button art).
RARITY_ON_DARK = {"common": config.COLOR_TEXT, "uncommon": (130, 225, 150),
                  "rare": (150, 170, 255), "forge": (255, 185, 90)}

# (stat, kind) in display order; the label is `stat.<id>` in the locale
# files (UI-014.9), read when drawn. `kind` picks the formatter:
#   num   -- a plain number (HP, px/s, px)
#   flat  -- a flat amount shown with its sign
#   pct   -- a fraction shown as a percentage (chances, +gain fractions)
#   mult  -- a multiplier shown as x1.25
#   regen -- HP per tick, printed with the cadence: `1 / 5s` (CB-7)
STAT_ROWS = (
    ("max_hp", "num"),
    ("hp_regen", "regen"),
    ("move_speed", "num"),
    ("armor", "num"),
    ("damage_multiplier", "mult"),
    ("melee_damage", "pctplus"),
    ("ranged_damage", "pctplus"),
    ("attack_speed_multiplier", "mult"),
    ("projectile_speed_multiplier", "mult"),
    ("area_multiplier", "mult"),
    ("crit_chance", "pct"),
    ("crit_damage", "pctplus"),
    ("evasion_chance", "pct"),
    ("block_chance", "pct"),
    ("block_strength", "pct"),
    ("pickup_radius", "num"),
    ("luck", "num"),
    ("xp_gain", "pctplus"),
    ("gold_gain", "pctplus"),
)
_KINDS = dict(STAT_ROWS)


def stat_label(stat: str) -> str:
    """The stat's name in the current language; a stat the table does not
    list shows its id, spaced and capitalised."""
    return locale.name("stat", stat, stat.replace("_", " ").capitalize())


DECIMALS = 2          # a pane number's decimals at most (`short`)


def fmt_stat(stat: str, value: float) -> str:
    """A hero stat as the panes print it, in the language's number style
    (UI-014.10): "x1.25" / "x1,25", "12%" / "12 %", "1 / 5s" / "1 / 5 s"."""
    kind = _KINDS.get(stat, "num")
    d = locale.decimals
    if kind == "mult":
        return locale.unit("mult", d(f"{value:.2f}"))
    if kind == "pct":
        return locale.unit("percent", f"{value * 100:.0f}")
    if kind == "pctplus":
        return locale.unit("percent", f"{value * 100:+.0f}")
    if kind == "regen":
        return f"{d(short(value))} / " + locale.unit(
            "seconds", d(short(config.HP_REGEN_INTERVAL)))
    return d(short(value))


def short(value: float) -> str:
    """A pane's number: at most `DECIMALS` decimals, no trailing zeros --
    "0.8", "0.35", "180" (UI-015: a blessing-scaled cooldown printed as
    "0.8004s", and `:g` wrote a million as "1e+06")."""
    s = f"{value:.{DECIMALS}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def fmt_mod(stat: str, op: str | None, value: float) -> str:
    """A modifier as an item or a blessing would state it: `+20 Max HP`,
    `+12% Damage`, `x1.1 Attack speed`."""
    label = stat_label(stat)
    if op == "pct":
        return f"{locale.unit('percent', f'{value * 100:+.0f}')} {label}"
    if op == "mult":
        return f"{locale.unit('mult', locale.decimals(f'{1.0 + value:.2f}'))} {label}"
    # flat: chances and multipliers are fractions even when flat
    kind = _KINDS.get(stat, "num")
    if kind in ("pct", "pctplus", "mult"):
        return f"{locale.unit('percent', f'{value * 100:+.0f}')} {label}"
    # Item rolls are unrounded floats (+3.917 armor); one decimal is what a
    # player can use, and a whole number stays whole.
    return f"{_one_decimal(value)} {label}"


def _one_decimal(value: float) -> str:
    text = f"{value:+.1f}"
    return locale.decimals(text[:-2] if text.endswith(".0") else text)


TITLE_PX = 28          # a weapon card's title (the Build pane steps it down to fit)


class Fonts:
    """The faces the panes share, built once per screen."""

    def __init__(self) -> None:
        self.ribbon = fonts.heading(22)
        self.title = fonts.heading(TITLE_PX)
        self.sub = fonts.heading(20)
        self.row = fonts.body(20)
        self.small = fonts.body(16)


# --- surfaces ----------------------------------------------------------
def draw_dim(surface: pygame.Surface) -> None:
    veil.veil(surface, (0, 0, 0), 150)            # constant alpha (RND-010)


def draw_panel(surface: pygame.Surface, rect: pygame.Rect) -> None:
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill(_PANEL_FILL)
    surface.blit(panel, rect.topleft)
    pygame.draw.rect(surface, _RULE, rect, width=1, border_radius=S(8))


def draw_tabs(surface, assets, rect: pygame.Rect, labels, active: int,
              font, hits) -> list[pygame.Rect]:
    """Three ribbons across the top edge of `rect`, the active one lit, the
    others shaded. Registers each as `("tab", i)` in `hits`."""
    colours = ("blue", "yellow", "red")
    n = len(labels)
    gap = S(24)
    w = min(S(320), (rect.width - S(32) - gap * (n - 1)) // n)
    total = n * w + gap * (n - 1)
    x = rect.centerx - total // 2
    rects = []
    for i, label in enumerate(labels):
        r = pygame.Rect(x + i * (w + gap), rect.top - S(RIBBON_H) // 2 + S(8), w, S(RIBBON_H))
        surface.blit(tab_surface(assets, r.size, label, colours[i % 3], font,
                                 active=(i == active)), r.topleft)
        hits.add(r, ("tab", i))
        rects.append(r)
    return rects


def tab_surface(assets, size, label: str, colour: str, font, *, active: bool) -> pygame.Surface:
    """One ribbon tab on its own transparent layer: the art (or the flat
    fallback), the label, and -- for an inactive tab -- the whole layer's
    colour multiplied down. Because the multiply keeps each pixel's alpha,
    the transparent surround of the forked ends stays transparent and the
    shade is exactly the ribbon's shape."""
    layer = pygame.Surface(size, pygame.SRCALPHA)
    r = layer.get_rect()
    widgets.draw_ribbon(layer, assets, r, None, colour=colour)
    text = font.render(label, True, config.COLOR_ON_BUTTON)
    layer.blit(text, text.get_rect(center=(r.centerx, r.centery + S(TITLE_DY))))
    if not active:
        layer.fill(_TAB_SHADE_MULT, special_flags=pygame.BLEND_RGBA_MULT)
    return layer


# --- rows ------------------------------------------------------------------
def kv(surface, font, area, y, label, value, *, colour=None, label_colour=None) -> int:
    """A label / value row, the label trimmed if the two would meet.

    Nothing clips at the blit, so a label that outgrows its column draws over
    its own value. There is 169 px of headroom on the tightest row today --
    this is a guard, not a fix for something visible -- but the same primitive
    on the run summary *did* overlap once its columns narrowed, and an item
    name is rolled from affixes rather than authored.
    """
    val = font.render(str(value), True, colour or config.COLOR_TEXT)
    room = area.width - val.get_width() - S(8)
    lab = font.render(uitext.ellipsize(font, str(label), room),
                      True, label_colour or config.COLOR_TEXT_DIM)
    surface.blit(lab, lab.get_rect(midleft=(area.left, y)))
    surface.blit(val, val.get_rect(midright=(area.right, y)))
    return y + S(ROW_STEP)


def line(surface, font, area, y, text, *, colour=None, indent: int = 0,
         step: int = ROW_STEP) -> int:
    """One line, trimmed to what is left of the column after `indent`.
    `indent` and `step` are design px."""
    indent = S(indent)
    t = font.render(uitext.ellipsize(font, str(text), area.width - indent),
                    True, colour or config.COLOR_TEXT)
    surface.blit(t, t.get_rect(midleft=(area.left + indent, y)))
    return y + S(step)


def subheader(surface, font, area, y, text) -> int:
    y += S(6)
    t = font.render(uitext.ellipsize(font, str(text), area.width),
                    True, config.COLOR_ACCENT)
    surface.blit(t, t.get_rect(midleft=(area.left, y)))
    pygame.draw.line(surface, _RULE, (area.left, y + S(15)), (area.right, y + S(15)))
    return y + S(ROW_STEP + 4)


def rule(surface, area, y) -> int:
    pygame.draw.line(surface, _RULE, (area.left, y - S(2)), (area.right, y - S(2)))
    return y + S(6)


def more(surface, font, area, y, n: int, key: str) -> int:
    """The "+n more" line; `key` names its `.one` / `.other` forms ("+1 more
    synergy", "+2 more synergies")."""
    if n <= 0:
        return y
    return line(surface, font, area, y, locale.plural(key, n), colour=config.COLOR_TEXT_DIM)


def fits(area, y, rows: int, step: int = ROW_STEP) -> int:
    """How many of `rows` rows fit between `y` and the area's bottom, leaving
    the last slot for a "+n more" line when they do not all fit."""
    room = max(0, (area.bottom - y) // S(step) + 1)
    return rows if rows <= room else max(0, room - 1)
