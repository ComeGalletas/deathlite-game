"""LEVEL_UP: overlay that pauses the run and presents 3 weighted upgrade
choices (spec 3.5). Pushed by PlayingState when a level-up is pending; pops
itself once a choice is applied.

Mouse (journal: "Mouse support in menus and UI"): hovering a card selects
it, one click (press and release on the same card) picks it -- a mis-pick
here is cheap and the keyboard already picks with a single key. The pick
lands on the *release*, so the run underneath, which polls the held button
every frame, never sees the click as an attack (and `PlayingState` disarms
the mouse while this overlay is up regardless).
"""
from __future__ import annotations

import pygame

from game import locale
from game.state import State
from ui import scale
from progression.upgrades import apply_choice
from ui import forge_rail
from ui.forge_rail import ForgeRail
from ui.level_up import CARD_GAP, CARD_W, CARD_W_NARROW, LevelUpPanel, number_keys
from ui.menu_nav import MenuNav
from ui.mouse import MouseNav

_RAIL_GAP = 30          # design px between the rail and the first card
_EDGE = 20              # the least margin the rail keeps from the surface's edge


class LevelUpState(State):
    draw_below = True      # show the frozen battlefield behind the panel
    update_below = False   # ...frozen: no simulation while choosing

    def enter(self, *, player, choices=(), on_done=None, title=None,
              cancelable=False, weapon_rows=None, offers_for=None,
              rail_heading=None, hint=None, hint_key=None, **kwargs) -> None:
        self.player = player
        self.on_done = on_done
        # P3: the Forge reuses this overlay with its own title, and lets the
        # player walk away (ESC) without choosing.
        self.title = title
        self.cancelable = cancelable
        self.selected = 0
        self.panel = LevelUpPanel()
        # The cards run left to right; 1 / 2 / 3 pick directly; ESC is read
        # below only when the screen is cancelable (ui/menu_nav.py).
        self._nav = MenuNav(MouseNav(self.panel.hits), axis="h", numbers=True)
        self._mouse = self._nav.mouse             # the panel records the cards

        # Change request 6: the Forge adds a weapon picker down the left, and
        # the cards follow whichever weapon is selected. Without these two the
        # overlay is exactly the level-up screen it has always been -- same
        # card width, no rail, no extra keys.
        self.weapon_rows = list(weapon_rows or ())
        self.offers_for = offers_for
        # M7: the Monastery reuses the rail for elements, so the heading
        # is the caller's; left out it is the Forge's own.
        self.rail_heading = rail_heading or forge_rail.DEFAULT_HEADING
        # The keys line under the cards. It names what the screen
        # actually does, so a caller that is not the Forge (the
        # Monastery, M7) says so rather than offering to forge.
        self._hint_arg = hint             # a caller's own hint, else the default at draw
        # Or its locale key: filled, when drawn, with the number keys the
        # cards on screen answer to ("1/2/3/4" for the Monastery's four).
        self._hint_key = hint_key
        self.rail = ForgeRail() if self.weapon_rows else None
        self._rail_mouse = MouseNav(self.rail.hits) if self.rail else None
        self.weapon_sel = next((i for i, r in enumerate(self.weapon_rows) if r[1]), 0)
        self.choices = list(choices) if choices else self._offers()

    def _default_hint(self) -> str | None:
        if self.weapon_rows:
            return locale.t("level_up.hint_rows", keys=number_keys(len(self.choices)))
        if self.cancelable:
            return locale.t("level_up.hint_leave", keys=number_keys(len(self.choices)))
        return None

    @property
    def hint(self) -> str | None:
        """The caller's hint, else the default, read when drawn so it is in
        the language in use (UI-014.7) and names the cards' own number keys
        (UI-014.11: "1/2/3" over four cards)."""
        if self._hint_key:
            return locale.t(self._hint_key, keys=number_keys(len(self.choices)))
        return self._hint_arg or self._default_hint()

    @property
    def card_width(self) -> int:
        return CARD_W_NARROW if self.rail is not None else CARD_W

    def card_layout(self, width: int) -> tuple[float, int]:
        """`(card width in design px, shift right in native px)` on a
        `width`-wide surface. Without a rail, the level-up layout, the cards
        narrowed only when they would not fit between the margins (the buff
        building's four weapons at the 1280 web profile ran off both edges).
        With one, the narrow cards stay centred while the rail fits left of
        them; when it would not (four cards, or three at the 1280 web
        profile, where it ran off the left edge), the cards narrow until rail
        and cards fit between the margins, and shift right until the rail
        clears the left one (UI-014.11)."""
        S = scale.px
        n = max(1, len(self.choices))
        gap, margin = S(CARD_GAP), S(_EDGE)
        rail = S(forge_rail.WIDTH) + S(_RAIL_GAP) if self.rail is not None else 0
        fit = (width - 2 * margin - rail - (n - 1) * gap) // n
        card_w = float(self.card_width)
        if S(card_w) > fit:
            card_w = float(fit // scale.factor())
        total = n * S(card_w) + (n - 1) * gap
        return card_w, max(0, margin + rail - (width - total) // 2)

    def _offers(self) -> list:
        """The cards for the selected weapon (Forge only)."""
        if self.offers_for is None or not self.weapon_rows:
            return []
        return list(self.offers_for(self.weapon_rows[self.weapon_sel][0]))

    def _select_weapon(self, index: int) -> None:
        """Move the picker. Only a row the Forge can act on is selectable, so
        stepping past an ineligible weapon skips it rather than landing on a
        dead row with no cards behind it."""
        usable = [i for i, r in enumerate(self.weapon_rows) if r[1]]
        if not usable or index not in usable:
            return
        if index == self.weapon_sel:
            return
        self.weapon_sel = index
        self.choices = self._offers()
        self.selected = 0

    def _step_weapon(self, delta: int) -> None:
        usable = [i for i, r in enumerate(self.weapon_rows) if r[1]]
        if not usable:
            return
        here = usable.index(self.weapon_sel) if self.weapon_sel in usable else 0
        self._select_weapon(usable[(here + delta) % len(usable)])

    def handle_event(self, event: pygame.event.Event) -> None:
        # The rail is read first: with no weapon selected there are no cards,
        # and the picker still has to work.
        if self._rail_mouse is not None:
            act = self._rail_mouse.event(event)
            if act is not None:
                self._select_weapon(act[1])
                return
        if not self.choices and self.rail is None:
            return
        verb = self._nav.event(event, index=self.selected, count=len(self.choices))
        if verb is None:
            return
        what, v = verb
        if what == "back":
            if self.cancelable:
                self.game.state_machine.pop()
            return
        if what == "axis":                         # Up / Down: the weapon picker
            if self.rail is not None:
                self._step_weapon(v)
            return
        if not self.choices:
            return
        if what == "move":
            self.selected = v
        elif what == "activate":
            self.selected = v
            self._pick(v)
        elif what == "number":
            self._pick(v)

    def _pick(self, index: int) -> None:
        upgrade = self.choices[index]
        apply_choice(self.player, upgrade)
        if self.on_done is not None:
            self.on_done(upgrade)
        self.game.state_machine.pop()

    def draw_backdrop(self, surface: pygame.Surface) -> None:
        self.panel.draw_dim(surface)         # the whole surface, margins included

    def draw(self, surface: pygame.Surface) -> None:
        hint = self.hint
        card_w, shift = self.card_layout(surface.get_width())
        self.panel.draw(surface, self.choices, self.selected,
                        assets=self.game.assets, pressed=self._mouse.pressed_on,
                        title=self.title, hint=hint, card_w=card_w, x_shift=shift,
                        dim=False)
        if self.rail is None:
            return
        # The rail sits just left of the cards rather than at a fixed x, so it
        # stays beside them at 1600 and at the 1280 web profile instead of
        # drifting into the corner on the wider one.
        first = self.panel.hits.rect_of(0)
        # No cards (a weapon with no Forgings left): a quarter in, or as far
        # in as the rail needs to clear the edge.
        right = (first.left - scale.px(_RAIL_GAP)) if first is not None \
            else max(surface.get_width() // 4, scale.px(_EDGE + forge_rail.WIDTH))
        top = first.top if first is not None else scale.px(300)
        self.rail.draw(surface, self.weapon_rows, self.weapon_sel,
                       assets=self.game.assets, right=right, top=top,
                       heading=self.rail_heading)
