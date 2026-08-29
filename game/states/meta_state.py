"""SANCTUARY (meta screen, spec 4.6): spend Salvage on persistent upgrades and
manage the item stash between runs. Every change is saved immediately.

Two panels, switch with TAB:
  * Upgrades -- Up/Down select, ENTER buy
  * Stash    -- Up/Down select, ENTER equip into its slot, U unequip that slot
"""
from __future__ import annotations

import pygame

from game import config, fonts
from game.state import State
from progression.items import Item
from progression.meta import buy

_RARITY_COLOR = {
    "common": (180, 180, 185), "uncommon": (110, 200, 120),
    "rare": (90, 160, 240), "epic": (190, 120, 240), "legendary": (240, 180, 80),
}


class MetaState(State):
    def enter(self, **kwargs) -> None:
        self.save = self.game.save
        self.catalog = self.game.meta_catalog
        self.panel = 0                      # 0 = upgrades, 1 = stash
        self.sel = [0, 0]
        self._title = fonts.heading(40)
        self._h = fonts.heading(22)
        self._f = fonts.mono(18)
        self._small = fonts.body(15)

    # --- input ------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        k = event.key
        if k == pygame.K_ESCAPE:
            from game.states.menu_state import MenuState
            self.game.state_machine.change(MenuState(self.game))
        elif k == pygame.K_TAB:
            self.panel ^= 1
        elif k in (pygame.K_UP, pygame.K_w):
            self.sel[self.panel] -= 1
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.sel[self.panel] += 1
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate()
        elif k == pygame.K_u and self.panel == 1:
            self._unequip_selected()
        self._clamp_sel()

    def _upgrade_ids(self) -> list[str]:
        return list(self.game.content.meta_upgrades.keys())

    def _clamp_sel(self) -> None:
        n0 = len(self._upgrade_ids())
        n1 = max(1, len(self.save.stash))
        self.sel[0] = max(0, min(self.sel[0], n0 - 1))
        self.sel[1] = max(0, min(self.sel[1], n1 - 1))

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
        title = self._title.render("Sanctuary", True, config.COLOR_ACCENT)
        surface.blit(title, title.get_rect(midtop=(w // 2, 28)))
        salvage = self._h.render(f"Salvage: {self.save.currency}", True, config.COLOR_TEXT)
        surface.blit(salvage, salvage.get_rect(midtop=(w // 2, 78)))

        self._draw_upgrades(surface, x=70, active=self.panel == 0)
        self._draw_stash(surface, x=w // 2 + 30, active=self.panel == 1)

        hint = self._small.render(
            "TAB switch panel   -   Up/Down select   -   ENTER buy/equip   -   "
            "U unequip   -   ESC back", True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(midbottom=(w // 2, surface.get_height() - 18)))

    def _draw_upgrades(self, surface, x, active) -> None:
        y = 130
        head = self._h.render("Upgrades" + (" <" if active else ""), True,
                              config.COLOR_TEXT if active else config.COLOR_TEXT_DIM)
        surface.blit(head, (x, y))
        y += 40
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
                         (x + 16, y + 20))
            y += 46

    def _draw_stash(self, surface, x, active) -> None:
        y = 130
        head = self._h.render("Stash" + (" <" if active else ""), True,
                              config.COLOR_TEXT if active else config.COLOR_TEXT_DIM)
        surface.blit(head, (x, y))
        y += 34
        for slot in ("weapon", "armor", "accessory"):
            eid = self.save.equipped.get(slot)
            name = "-"
            if eid:
                match = next((it for it in self.save.stash if it["item_id"] == eid), None)
                if match:
                    name = match["name"]
            surface.blit(self._small.render(f"{slot:<10} {name}", True,
                                            (150, 200, 255)), (x, y))
            y += 20
        y += 10

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
            y += 24
