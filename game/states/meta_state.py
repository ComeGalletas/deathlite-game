"""SANCTUARY (meta screen, spec 4.6): spend Salvage on persistent upgrades and
manage the item stash between runs. Every change is saved immediately.

Two panels, switch with TAB:
  * Upgrades -- Up/Down select, ENTER buy
  * Stash    -- Up/Down select, ENTER equip into its slot, U unequip that slot

The mouse drives the same cursor (structure review, B): hovering a row
selects it -- and its panel -- and a click does what ENTER does. The rows
are registered while drawing, keyed `(panel, row)`.
"""
from __future__ import annotations

import pygame

from game import config, fonts
from game.state import State
from ui import scale
from ui.menu_nav import MenuNav
from progression.items import Item
from progression.meta import buy

_RARITY_COLOR = {
    "common": (180, 180, 185), "uncommon": (110, 200, 120),
    "rare": (90, 160, 240), "epic": (190, 120, 240), "legendary": (240, 180, 80),
}


class MetaState(State):
    music = "menu"
    def enter(self, **kwargs) -> None:
        self.save = self.game.save
        self.catalog = self.game.meta_catalog
        self.panel = 0                      # 0 = upgrades, 1 = stash
        self.sel = [0, 0]
        self._title = fonts.heading(40)
        self._h = fonts.heading(22)
        self._f = fonts.mono(18)
        self._small = fonts.body(15)
        # Clamped, not wrapped: two lists, each ends where it ends.
        self._nav = MenuNav(wrap=False)
        self._mouse = self._nav.mouse

    # --- input ------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        verb = self._nav.event(event, index=self.sel[self.panel],
                               count=self._count(self.panel))
        if verb is None:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    self.panel ^= 1
                elif event.key == pygame.K_u and self.panel == 1:
                    self._unequip_selected()
                self._clamp_sel()
            return
        what, v = verb
        if what == "back":
            from game.states.menu_state import MenuState
            self.game.state_machine.change(MenuState(self.game))
            return
        if what in ("move", "activate"):
            if isinstance(v, tuple):           # a registered row: (panel, i)
                self.panel, i = v
            else:
                i = v
            self.sel[self.panel] = i
            if what == "activate":
                self._activate()
        self._clamp_sel()

    def _upgrade_ids(self) -> list[str]:
        return list(self.game.content.meta_upgrades.keys())

    def _count(self, panel: int) -> int:
        return len(self._upgrade_ids()) if panel == 0 else max(1, len(self.save.stash))

    def _clamp_sel(self) -> None:
        self.sel[0] = max(0, min(self.sel[0], self._count(0) - 1))
        self.sel[1] = max(0, min(self.sel[1], self._count(1) - 1))

    def _activate(self) -> None:
        if self.panel == 0:
            uid = self._upgrade_ids()[self.sel[0]]
            if buy(self.catalog, self.save, uid):
                self.game.persist()
        elif self.save.stash:
            item = Item.from_dict(self.save.stash[self.sel[1]])
            self.save.equipped[item.slot] = item.item_id
            self.game.persist()

    def _unequip_selected(self) -> None:
        if not self.save.stash:
            return
        item = Item.from_dict(self.save.stash[self.sel[1]])
        if self.save.equipped.get(item.slot) == item.item_id:
            self.save.equipped[item.slot] = None
            self.game.persist()

    # --- render ---------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(config.COLOR_BG)
        w = surface.get_width()
        S = scale.px
        title = self._title.render("Sanctuary", True, config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(midtop=(w // 2, S(28))))
        salvage = self._h.render(f"Salvage: {self.save.currency}", True, config.COLOR_TEXT)
        surface.blit(salvage, salvage.get_rect(midtop=(w // 2, S(78))))

        self._mouse.hits.clear()             # the panels re-register their rows
        self._draw_upgrades(surface, x=S(70), active=self.panel == 0)
        self._draw_stash(surface, x=w // 2 + S(30), active=self.panel == 1)

        hint = self._small.render(
            "TAB switch panel   -   Up/Down select   -   ENTER buy/equip   -   "
            "U unequip   -   ESC back", True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(midbottom=(w // 2, surface.get_height() - S(18))))

    def _draw_upgrades(self, surface, x, active) -> None:
        S = scale.px
        y = S(130)
        head = self._h.render("Upgrades" + (" <" if active else ""), True,
                              config.COLOR_TEXT if active else config.COLOR_TEXT_DIM)
        surface.blit(head, (x, y))
        y += S(40)
        for i, uid in enumerate(self._upgrade_ids()):
            d = self.game.content.meta_upgrades[uid]
            lvl = self.save.meta.get(uid, 0)
            mx = self.catalog.max_level(uid)
            maxed = lvl >= mx
            cost = "MAX" if maxed else str(self.catalog.cost(uid, lvl))
            afford = (not maxed) and self.save.currency >= self.catalog.cost(uid, lvl)
            colour = config.COLOR_ACCENT if (active and i == self.sel[0]) else (
                config.COLOR_TEXT if afford else config.COLOR_TEXT_DIM)
            surface.blit(self._f.render(
                f"{d['name']:<14} {lvl}/{mx}   {cost:>4}", True, colour), (x, y))
            surface.blit(self._small.render(d["desc"], True, config.COLOR_TEXT_DIM),
                         (x + S(16), y + S(20)))
            # The row and its description line, one band each, touching.
            self._mouse.hits.add(pygame.Rect(x - S(8), y - S(4), S(440), S(46)), (0, i))
            y += S(46)

    def _draw_stash(self, surface, x, active) -> None:
        S = scale.px
        y = S(130)
        head = self._h.render("Stash" + (" <" if active else ""), True,
                              config.COLOR_TEXT if active else config.COLOR_TEXT_DIM)
        surface.blit(head, (x, y))
        y += S(34)
        for slot in ("weapon", "armor", "accessory"):
            eid = self.save.equipped.get(slot)
            name = "-"
            if eid:
                match = next((it for it in self.save.stash if it["item_id"] == eid), None)
                if match:
                    name = match["name"]
            surface.blit(self._small.render(f"{slot:<10} {name}", True,
                                            (150, 200, 255)), (x, y))
            y += S(20)
        y += S(10)

        if not self.save.stash:
            surface.blit(self._f.render("(no items yet - beat elites / the boss)",
                                        True, config.COLOR_TEXT_DIM), (x, y))
            return
        for i, raw in enumerate(self.save.stash[:12]):
            it = Item.from_dict(raw)
            equipped = self.save.equipped.get(it.slot) == it.item_id
            base = _RARITY_COLOR.get(it.rarity, config.COLOR_TEXT)
            colour = config.COLOR_ACCENT if (active and i == self.sel[1]) else base
            tag = " *" if equipped else ""
            surface.blit(self._f.render(f"{it.short()}{tag}", True, colour), (x, y))
            self._mouse.hits.add(pygame.Rect(x - S(8), y, S(520), S(24)), (1, i))
            y += S(24)
