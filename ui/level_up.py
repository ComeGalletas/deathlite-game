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

from game import config, fonts
from ui import widgets
from ui.mouse import HitMap
from ui.text import shadowed, wrap

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
_TAG_UP = 39                # the category line's midbottom, up from the card's
_DESC_GAP = 8               # breathing room between the block and the category line

# The level-up width, and the narrower one the Forge uses so its weapon rail
# has somewhere to live. Three 260-wide cards and two 40 px gaps come to 860,
# which leaves 370 px a side at 1600 and 210 at the 1280 web profile -- enough
# for the rail on both, where the 340 width leaves only 90 on web.
CARD_W = 340
CARD_W_NARROW = 260


class LevelUpPanel:
    def __init__(self) -> None:
        self._title = fonts.heading(40)
        self._name = fonts.heading(24)
        self._desc = fonts.body(18)
        self._hint = fonts.body(16)
        self.hits = HitMap()          # card index -> rect, rebuilt every draw

    def draw(self, surface: pygame.Surface, choices, selected: int, *,
             assets=None, pressed=None, title=None, hint=None,
             card_w: int = CARD_W) -> None:
        """`card_w` narrows the cards so something else can share the screen --
        the Forge's weapon rail (`ui/forge_rail.py`) sits in the margin the
        narrower cards free up. The default is the level-up width and that path
        is unchanged, which `tests/rendering/test_level_up.py` pins."""
        w, h = surface.get_size()
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((8, 6, 16, 200))
        surface.blit(dim, (0, 0))

        title = self._title.render(title or "Level Up  -  choose one", True,
                                   config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(w // 2, 110)))

        n = len(choices)
        card_h = _CARD_H
        gap = 40
        total = n * card_w + (n - 1) * gap
        x0 = (w - total) // 2
        y = h // 2 - _CARD_TOP_H // 2       # the top edge stays where the 200-tall card had it

        self.hits.clear()
        for i, up in enumerate(choices):
            x = x0 + i * (card_w + gap)
            rect = self.hits.add(pygame.Rect(x, y, card_w, card_h), i)
            state = ("pressed" if pressed == i
                     else "hover" if i == selected else "normal")
            widgets.draw_button(surface, assets, rect, None, state=state, shape="panel")
            dy = widgets.PRESSED_DY if state == "pressed" else 0

            # Text on the light card: the name is a title (title face, black);
            # badge, description and tags are the dark grey.
            key_badge = self._name.render(f"#{i + 1}", True, config.COLOR_ON_BUTTON_DIM)
            surface.blit(key_badge, (x + 39, y + 10 + dy))    # 25 px in from the corner (owner)

            name = shadowed(self._name, up.title, config.COLOR_ACCENT)   # gold with a dark drop shadow
            surface.blit(name, name.get_rect(midtop=(rect.centerx, y + 46 + dy)))

            # P2: the rarity, top-right, in its colour (the level is in the
            # title's roman numeral).
            rarity = getattr(up, "rarity", "")
            if rarity:
                r = self._hint.render(rarity.upper(), True,
                                      config.RARITY_COLOURS.get(rarity, config.COLOR_ON_BUTTON_DIM))
                surface.blit(r, r.get_rect(topright=(x + card_w - 24, y + 14 + dy)))

            lines = wrap(self._desc, up.description, card_w - 2 * _CARD_TEXT_INSET)
            band_top = y + _DESC_TOP
            band_bottom = (y + card_h - _TAG_UP
                           - self._hint.get_height() - _DESC_GAP)
            slack = band_bottom - band_top - len(lines) * _DESC_LINE_H
            top = band_top + max(0, slack // 2)      # never above the band's top
            for j, line in enumerate(lines):
                d = self._desc.render(line, True, config.COLOR_ON_BUTTON_DIM)
                surface.blit(d, d.get_rect(
                    midtop=(rect.centerx, top + j * _DESC_LINE_H + dy)))

            if up.tags:
                # The category line: each word capitalised, 25 px up from
                # the bottom bevel (owner, 2026-09-10).
                words = " ".join(t[:1].upper() + t[1:] for t in up.tags)
                tag = self._hint.render(words, True, config.COLOR_ON_BUTTON_DIM)
                surface.blit(tag, tag.get_rect(midbottom=(rect.centerx, y + card_h - 39 + dy)))

        hint = self._hint.render(
            hint or "1/2/3 or Left/Right + Enter to pick    -    or click a card",
            True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(w // 2, y + card_h + 60)))

