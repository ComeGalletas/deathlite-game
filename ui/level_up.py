"""Rendering for the level-up choice screen (spec 3.5 / 3.6).

Pure presentation: given the list of `Upgrade` choices and the highlighted
index, draw three cards. Input handling stays in `LevelUpState`; the panel
only *records* where it painted each card (`hits`, a `ui.mouse.HitMap`) so
the state can answer the mouse without knowing the geometry.

The cards are the pack's 9-slice buttons (`ui.widgets.draw_button`, shape
`panel`): gold for the selected card, the pressed sheet while the mouse
button is held on a card (`pressed`), blue otherwise. Without `assets` the
flat rounded rectangles of old are drawn instead.
"""
from __future__ import annotations

import pygame

from game import config, fonts, locale
from ui import scale, veil, widgets
from ui.mouse import HitMap
from ui.text import cached_font, fit_font, shadowed, wrap

# The cards grew 15 px downwards (owner, 2026-09-04) so the description's
# last line and the tag line sit inside the art's flat centre, not on its
# bottom bevel: the top edge still centres as a 200-tall card did.
_CARD_TOP_H = 200
_CARD_H = 295               # 200 + 15 + 30 (2026-09-04) + 50 (2026-09-11), all downward
_CARD_TEXT_INSET = 19       # description wraps to the card width minus this each side (16 + 3 px)

# The description block is *centred* between the title and the category line
# rather than pinned under the title (owner, 2026-09-11, change request 5
# option B). Of the 345 descriptions the catalog renders, 316 are one or two
# lines, so pinning them to the top of a 295-tall card left them stranded over
# an empty half-card; centring spends the extra 50 px on the text instead. A
# description long enough to fill the band still starts at `_DESC_TOP`, so the
# four-line cards (`bow_crossfire`) are laid out exactly as before.
_DESC_TOP = 92              # top of the band, and where a full-height block starts
_DESC_LINE_H = 24
_DESC_PX = 18                # the description's design font size
_DESC_MIN_PX = 13           # the smallest a long description steps down to (72 %)
_TAG_UP = 39                # the category line's midbottom, up from the card's
_DESC_GAP = 8               # breathing room between the block and the category line
_NAME_PX = 24               # the card title's design font size

# The level-up width, and the narrower one the Forge uses so its weapon rail
# has somewhere to live. Three 260-wide cards and two 40 px gaps come to 860,
# which leaves 370 px a side at 1600: room for the rail (250 + 30). Where the
# cards leave less -- four of them (the Monastery, four weapons), or the 1280
# web profile -- `LevelUpState.card_layout` narrows and shifts them.
CARD_W = 340
CARD_W_NARROW = 260
CARD_GAP = 40               # between two cards


def number_keys(n: int) -> str:
    """The number keys `n` cards answer to, for a hint's `{keys}`: "1/2/3",
    "1/2/3/4" (`ui/menu_nav.py` reads 1 to 9)."""
    return "/".join(str(i + 1) for i in range(max(1, n)))


def category_line(up) -> str:
    """The card's category line, a phrase per card kind in the current
    language (UI-014.7): "Sword Power", "Hero Power", "Melee Weapon Grant",
    "Sword Forge" / "Espada · Poder", "Poder del héroe", "Arma cuerpo a
    cuerpo", "Forja · Espada". Word order is the locale's, which is why the
    tags are not translated one by one. Tags of any other shape are joined,
    each capitalised, as before."""
    tags = tuple(up.tags)
    kind = getattr(up, "kind", None)
    if kind in ("stat", "weapon") and len(tags) == 2:
        who, category = tags
        name = locale.t(f"category.{category}")
        if who == "hero":
            return locale.t("level_up.line.hero", category=name)
        return locale.t("level_up.line.weapon", weapon=who, category=name)
    if kind == "grant" and len(tags) == 3:
        return locale.t("level_up.line.grant",
                        weapon_class=locale.t(f"weapon_class.{tags[0]}"))
    if kind == "forge" and len(tags) == 2:
        return locale.t("level_up.line.forge", weapon=tags[0])
    return " ".join(t[:1].upper() + t[1:] for t in tags)


class LevelUpPanel:
    def __init__(self) -> None:
        self._title = fonts.heading(40)
        self._name = fonts.heading(_NAME_PX)
        self._desc = fonts.body(_DESC_PX)
        self._hint = fonts.body(16)
        self.hits = HitMap()          # card index -> rect, rebuilt every draw

    def desc_block(self, text: str, width: int, band_h: int):
        """`(font, lines, line height)` for a card description in a band
        `band_h` native px tall. The panel's own 18 px font when the wrapped
        lines fit, which every English card does; otherwise a step smaller at
        a time, the line height shrinking with it, down to `_DESC_MIN_PX` (UI-014.8:
        a Spanish Forge card on the narrow cards ran into its category
        line)."""
        lines = wrap(self._desc, text, width)
        line_h = scale.px(_DESC_LINE_H)
        if len(lines) * line_h <= band_h:
            return self._desc, lines, line_h
        font = self._desc
        for size in range(_DESC_PX - 1, _DESC_MIN_PX - 1, -1):
            font = cached_font(fonts.body, size)
            lines = wrap(font, text, width)
            line_h = scale.px(_DESC_LINE_H * size / _DESC_PX)
            if len(lines) * line_h <= band_h:
                break
        return font, lines, line_h

    @staticmethod
    def draw_dim(surface: pygame.Surface) -> None:
        """The dark layer under the cards. The state paints it on the whole
        render surface (`draw_backdrop`) so a 21:9 render's side margins
        darken too, then draws the cards on the UI box with `dim=False`."""
        veil.veil(surface, (8, 6, 16), 200)      # constant alpha (RND-010)

    def draw(self, surface: pygame.Surface, choices, selected: int, *,
             assets=None, pressed=None, title=None, hint=None,
             card_w: float = CARD_W, dim: bool = True, x_shift: int = 0) -> None:
        """`card_w` narrows the cards so something else can share the screen --
        the Forge's weapon rail (`ui/forge_rail.py`) sits in the margin the
        narrower cards free up -- and `x_shift` (native px) moves them right
        of centre when that margin is still too small. The defaults are the
        level-up layout and that path is unchanged, which
        `tests/screens/test_level_up.py` pins."""
        w, h = surface.get_size()
        if dim:
            self.draw_dim(surface)

        title = self._title.render(title or locale.t("level_up.title"), True,
                                   config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(w // 2, scale.px(110))))

        n = len(choices)
        card_w = scale.px(card_w)               # design widths in; native px from here on
        card_h = scale.px(_CARD_H)
        gap = scale.px(CARD_GAP)
        total = n * card_w + (n - 1) * gap
        x0 = (w - total) // 2 + x_shift
        y = h // 2 - scale.px(_CARD_TOP_H) // 2   # the top edge stays where the 200-tall card had it

        self.hits.clear()
        for i, up in enumerate(choices):
            x = x0 + i * (card_w + gap)
            rect = self.hits.add(pygame.Rect(x, y, card_w, card_h), i)
            state = ("pressed" if pressed == i
                     else "hover" if i == selected else "normal")
            widgets.draw_button(surface, assets, rect, None, state=state, shape="panel")
            dy = scale.px(widgets.PRESSED_DY) if state == "pressed" else 0

            # Text on the light card: the name is a title (title face, black);
            # badge, description and tags are the dark grey.
            key_badge = self._name.render(f"#{i + 1}", True, config.COLOR_ON_BUTTON_DIM)
            surface.blit(key_badge, (x + scale.px(39), y + scale.px(10) + dy))    # 25 px in from the corner (owner)

            # A title wider than the card steps down in size (UI-014.7:
            # "Nueva arma: Tótem sepulcral"); the English ones all fit.
            room = card_w - 2 * scale.px(_CARD_TEXT_INSET)
            title_font = (self._name if self._name.size(up.title)[0] <= room
                          else fit_font(fonts.heading, _NAME_PX, up.title, room))
            name = shadowed(title_font, up.title, config.COLOR_ACCENT)   # gold with a dark drop shadow
            surface.blit(name, name.get_rect(midtop=(rect.centerx, y + scale.px(46) + dy)))

            # P2: the rarity, top-right, in its colour (the level is in the
            # title's roman numeral).
            rarity = getattr(up, "rarity", "")
            if rarity:
                r = self._hint.render(locale.t(f"rarity.{rarity}").upper(), True,
                                      config.RARITY_COLOURS.get(rarity, config.COLOR_ON_BUTTON_DIM))
                surface.blit(r, r.get_rect(topright=(x + card_w - scale.px(24), y + scale.px(14) + dy)))

            band_top = y + scale.px(_DESC_TOP)
            band_bottom = (y + card_h - scale.px(_TAG_UP)
                           - self._hint.get_height() - scale.px(_DESC_GAP))
            desc, lines, line_h = self.desc_block(up.description, room,
                                                  band_bottom - band_top)
            slack = band_bottom - band_top - len(lines) * line_h
            top = band_top + max(0, slack // 2)      # never above the band's top
            for j, line in enumerate(lines):
                d = desc.render(line, True, config.COLOR_ON_BUTTON_DIM)
                surface.blit(d, d.get_rect(
                    midtop=(rect.centerx, top + j * line_h + dy)))

            if up.tags:
                # The category line, 25 px up from the bottom bevel (owner,
                # 2026-09-10).
                tag = self._hint.render(category_line(up), True, config.COLOR_ON_BUTTON_DIM)
                surface.blit(tag, tag.get_rect(midbottom=(rect.centerx, y + card_h - scale.px(39) + dy)))

        hint = self._hint.render(
            hint or locale.t("level_up.hint_cards", keys=number_keys(n)),
            True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(w // 2, y + card_h + scale.px(60))))

