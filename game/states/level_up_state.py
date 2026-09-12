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

from game.state import State
from progression.upgrades import apply_choice
from ui.forge_rail import ForgeRail
from ui.level_up import CARD_W, CARD_W_NARROW, LevelUpPanel
from ui.mouse import MouseNav


class LevelUpState(State):
    draw_below = True      # show the frozen battlefield behind the panel
    update_below = False   # ...frozen: no simulation while choosing

    def enter(self, *, player, choices=(), on_done=None, title=None,
              cancelable=False, weapon_rows=None, offers_for=None,
              **kwargs) -> None:
        self.player = player
        self.on_done = on_done
        # P3: the Forge reuses this overlay with its own title, and lets the
        # player walk away (ESC) without choosing.
        self.title = title
        self.cancelable = cancelable
        self.selected = 0
        self.panel = LevelUpPanel()
        self._mouse = MouseNav(self.panel.hits)   # the panel records the cards

        # Change request 6: the Forge adds a weapon picker down the left, and
        # the cards follow whichever weapon is selected. Without these two the
        # overlay is exactly the level-up screen it has always been -- same
        # card width, no rail, no extra keys.
        self.weapon_rows = list(weapon_rows or ())
        self.offers_for = offers_for
        self.rail = ForgeRail() if self.weapon_rows else None
        self._rail_mouse = MouseNav(self.rail.hits) if self.rail else None
        self.weapon_sel = next((i for i, r in enumerate(self.weapon_rows) if r[1]), 0)
        self.choices = list(choices) if choices else self._offers()

    @property
    def card_width(self) -> int:
        return CARD_W_NARROW if self.rail is not None else CARD_W

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
        act = self._mouse.event(event)
        if act is not None:
            kind, i = act
            self.selected = i
            if kind == "click":
                self._pick(i)
            return
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        if key == pygame.K_ESCAPE and self.cancelable:
            self.game.state_machine.pop()
            return
        if self.rail is not None and key in (pygame.K_UP, pygame.K_w):
            self._step_weapon(-1)
            return
        if self.rail is not None and key in (pygame.K_DOWN, pygame.K_s):
            self._step_weapon(1)
            return
        if not self.choices:
            return
        if key in (pygame.K_LEFT, pygame.K_a):
            self.selected = (self.selected - 1) % len(self.choices)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.selected = (self.selected + 1) % len(self.choices)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._pick(self.selected)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            idx = key - pygame.K_1
            if idx < len(self.choices):
                self._pick(idx)

    def _pick(self, index: int) -> None:
        upgrade = self.choices[index]
        apply_choice(self.player, upgrade)
        if self.on_done is not None:
            self.on_done(upgrade)
        self.game.state_machine.pop()

    def draw(self, surface: pygame.Surface) -> None:
        if self.rail is not None:
            hint = ("Up/Down pick the weapon    -    1/2/3 or Left/Right + Enter "
                    "to forge    -    ESC to leave")
        elif self.cancelable:
            hint = "1/2/3 or Left/Right + Enter to pick    -    ESC to leave the Forge"
        else:
            hint = None
        self.panel.draw(surface, self.choices, self.selected,
                        assets=self.game.assets, pressed=self._mouse.pressed_on,
                        title=self.title, hint=hint, card_w=self.card_width)
        if self.rail is None:
            return
        # The rail sits just left of the cards rather than at a fixed x, so it
        # stays beside them at 1600 and at the 1280 web profile instead of
        # drifting into the corner on the wider one.
        first = self.panel.hits.rect_of(0)
        right = (first.left - 30) if first is not None else surface.get_width() // 4
        top = first.top if first is not None else 300
        self.rail.draw(surface, self.weapon_rows, self.weapon_sel,
                       assets=self.game.assets, right=right, top=top)
