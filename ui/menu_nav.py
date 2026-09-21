"""Menu navigation: the cursor keys and the mouse, turned into verbs.

Every menu screen used to open `handle_event` with the same twelve lines --
ask `MouseNav` for a hover or a click, set the index, activate on the click;
then on `KEYDOWN` wrap the index on Up / W and Down / S, activate on ENTER /
SPACE, leave on ESC. Ten screens carried a copy (journal:
`structure_review_journal.md`, B). This is the one copy. A screen owns a
`MenuNav`, keeps its own index (so `menu._index`, `pause.sel`,
`lu.selected` stay what the tests read) and hands both to `event`:

    verb = self._nav.event(event, index=self.sel, count=len(rows))

`verb` is one of

    ("move", key)       the cursor lands on `key` -- an index from the
                        keyboard, or whatever the screen registered in its
                        `HitMap` for the rect under the pointer (hover selects)
    ("activate", key)   ENTER / SPACE on the current index, or a click
                        (press and release on one rect) on `key`
    ("axis", -1 | +1)   the cross-axis pair: Left / Right on a vertical
                        list, Up / Down on a horizontal one -- the screen
                        decides (a slider nudges, the pause row cycles the
                        layout, the hero select steps the difficulty)
    ("number", i)       the 1-9 keys, zero-based, only with `numbers=True`
                        and only while `i < count`
    ("back", None)      ESC by default (`back_keys`), and the right mouse
                        button with `right_click_back`

or None for an event that is none of these, which leaves a screen free to
read its own extra keys afterwards (Q / E on the hero select, TAB and U in
the Sanctuary).

Menus take **both** WASD and the arrows for navigation whatever the run's
key layout says (`config.KEY_LAYOUTS` swaps move and aim *in a run*), so
nothing here reads the layout.

The mouse half is `ui.mouse.MouseNav`, unchanged: the screen registers its
rects while it draws and the click lands on the *release* over the rect the
press landed on, which is what keeps an overlay's pick from firing an attack
in the run underneath. `MenuNav.mouse` is that object, so a screen that reads
`pressed_on` / `hover` to paint a sunk or lit button still can.
"""
from __future__ import annotations

from typing import Callable

import pygame

from ui.mouse import MouseNav

BACK_KEYS = (pygame.K_ESCAPE,)
CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_SPACE)
_VERTICAL = ((pygame.K_UP, pygame.K_w), (pygame.K_DOWN, pygame.K_s))
_HORIZONTAL = ((pygame.K_LEFT, pygame.K_a), (pygame.K_RIGHT, pygame.K_d))
_NUMBER_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
                pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9)
BUTTON_RIGHT = 3


class MenuNav:
    def __init__(self, mouse: MouseNav | None = None, *, axis: str = "v",
                 wrap: bool = True, back_keys: tuple = BACK_KEYS,
                 confirm_keys: tuple = CONFIRM_KEYS, numbers: bool = False,
                 right_click_back: bool = False) -> None:
        """`axis` is the list's direction: `"v"` moves on Up / Down and
        reports Left / Right as `("axis", d)`; `"h"` the other way round.
        `wrap` false clamps at the ends instead (the Sanctuary's panels)."""
        if axis not in ("v", "h"):
            raise ValueError(f"axis must be 'v' or 'h', not {axis!r}")
        self.mouse = mouse if mouse is not None else MouseNav()
        self.axis = axis
        self.wrap = bool(wrap)
        self.back_keys = tuple(back_keys)
        self.confirm_keys = tuple(confirm_keys)
        self.numbers = bool(numbers)
        self.right_click_back = bool(right_click_back)

    @property
    def hits(self):
        """The screen's `HitMap` -- register rects here while drawing."""
        return self.mouse.hits

    def step(self, index: int, count: int, direction: int,
             skip: Callable[[int], bool] | None = None) -> int:
        """The index the cursor lands on from `index`, moving `direction`
        (-1 / +1) through `count` rows. Wraps or clamps per `wrap`; rows for
        which `skip(i)` is true are passed over, and if every row that way
        is skipped (or the list is empty) the cursor stays put."""
        if count <= 0:
            return index
        here = index
        for _ in range(count):
            nxt = here + direction
            if self.wrap:
                nxt %= count
            elif nxt < 0 or nxt >= count:
                return index
            if skip is None or not skip(nxt):
                return nxt
            here = nxt
        return index

    def event(self, event: pygame.event.Event, *, index: int = 0,
              count: int = 0, skip: Callable[[int], bool] | None = None):
        """The verb for `event` (see the module docstring), or None."""
        act = self.mouse.event(event)
        if act is not None:
            kind, key = act
            return ("move", key) if kind == "hover" else ("activate", key)
        if (self.right_click_back and event.type == pygame.MOUSEBUTTONDOWN
                and event.button == BUTTON_RIGHT):
            return ("back", None)
        if event.type != pygame.KEYDOWN:
            return None
        k = event.key
        if k in self.back_keys:
            return ("back", None)
        if k in self.confirm_keys:
            return ("activate", index)
        along, across = (_VERTICAL, _HORIZONTAL) if self.axis == "v" else (_HORIZONTAL, _VERTICAL)
        if k in along[0]:
            return ("move", self.step(index, count, -1, skip))
        if k in along[1]:
            return ("move", self.step(index, count, +1, skip))
        if k in across[0]:
            return ("axis", -1)
        if k in across[1]:
            return ("axis", +1)
        if self.numbers and k in _NUMBER_KEYS:
            i = _NUMBER_KEYS.index(k)
            return ("number", i) if i < count else None
        return None
