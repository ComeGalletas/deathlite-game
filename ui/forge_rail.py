"""The Forge's weapon picker: which weapon the Forgings on offer belong to.

The Forge used to take `eligible[0]` -- the first owned weapon with enough
blessings -- so a player carrying two qualifying weapons could not reforge the
second one at all. This is the list that makes the choice, drawn down the left
of the Forge screen while the cards keep the middle.

It shows **every** non-summon weapon, not just the ones that qualify, because
the three ways a weapon can fail are different and a player needs to see which
one applies:

* enough blessings -- selectable, drawn lit;
* not enough yet -- dimmed, and says how many more it needs;
* already forged -- dimmed, and names what it became.

A summon is never listed: `forge_eligible` rules it out and it can never
qualify, so a row for it would be a permanent dead entry.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from ui import scale
from ui.mouse import HitMap


ROW_H = 62
ROW_GAP = 8
WIDTH = 250
# The Forge's own heading. The Monastery reuses the rail for elements
# and passes its own (M7).
DEFAULT_HEADING = "REFORGE WHICH WEAPON"
_PAD_X = 14

# The lit row reads as a card does: the pack's gold panel for the selected
# weapon, blue for the other selectable ones, and no art at all for a row that
# cannot be chosen -- an unselectable thing should not look like a button.
_TITLE_DY = 8
_SUB_DY = 32


class ForgeRail:
    """Rows of `(item, eligible, note)`; records its own click targets.

    The rows are weapons for the Forge and elements for the Monastery;
    all the rail asks of a row is a `.name`."""

    def __init__(self) -> None:
        self._name = fonts.heading(20)
        self._note = fonts.body(15)
        self._head = fonts.body(16)
        self.hits = HitMap()        # row index -> rect, rebuilt every draw

    def height(self, rows) -> int:
        return len(rows) * scale.px(ROW_H) + max(0, len(rows) - 1) * scale.px(ROW_GAP)

    def draw(self, surface: pygame.Surface, rows, selected: int, *,
             assets=None, right: int, top: int,
             heading: str = DEFAULT_HEADING) -> None:
        """`right` is the rail's right edge -- the caller puts it just left of
        the cards, so the two read as one screen on any resolution rather than
        the rail drifting into the corner on a wide one."""
        from ui import widgets

        self.hits.clear()
        width, row_h, row_gap = scale.px(WIDTH), scale.px(ROW_H), scale.px(ROW_GAP)
        left = right - width
        head = self._head.render(heading, True, config.COLOR_TEXT_DIM)
        surface.blit(head, head.get_rect(midbottom=(left + width // 2, top - scale.px(10))))

        for i, (item, eligible, note) in enumerate(rows):
            y = top + i * (row_h + row_gap)
            rect = pygame.Rect(left, y, width, row_h)
            if eligible:
                # Only a selectable row is a click target, so a click on a
                # weapon that cannot be forged does nothing at all.
                self.hits.add(rect, i)
                state = "hover" if i == selected else "normal"
                widgets.draw_button(surface, assets, rect, None, state=state,
                                    shape="panel")
                # Dark on the light panel art, per the standing rule for text
                # drawn on it -- the cards' gold titles carry a drop shadow to
                # survive the tan, and a short name in a small row does not.
                name_col = config.COLOR_ON_BUTTON
                note_col = config.COLOR_ON_BUTTON_DIM
            else:
                pygame.draw.rect(surface, (26, 24, 36), rect, border_radius=scale.px(10))
                pygame.draw.rect(surface, (54, 52, 70), rect, width=max(1, scale.px(2)),
                                 border_radius=scale.px(10))
                name_col = config.COLOR_TEXT_DIM
                note_col = config.COLOR_TEXT_DIM

            name = self._name.render(item.name, True, name_col)
            surface.blit(name, (left + scale.px(_PAD_X), y + scale.px(_TITLE_DY)))
            sub = self._note.render(note, True, note_col)
            surface.blit(sub, (left + scale.px(_PAD_X), y + scale.px(_SUB_DY)))


def rows_for(weapons, need: int, blessing_levels, forged_name=None):
    """`[(weapon, eligible, note)]` for every non-summon weapon.

    `blessing_levels` and `forged_name` are passed in rather than imported so
    this module stays pure presentation and the test can drive it with fakes.
    """
    out = []
    for w in weapons:
        if getattr(w, "is_summon", False):
            continue
        if getattr(w, "forge", None) is not None:
            name = forged_name(w) if forged_name else str(w.forge)
            out.append((w, False, f"already forged into {name}"))
            continue
        have = blessing_levels(w)
        if have >= need:
            out.append((w, True, f"{have} / {need} blessings"))
        else:
            short = need - have
            plural = "" if short == 1 else "s"
            out.append((w, False, f"{have} / {need} - needs {short} more blessing{plural}"))
    return out
