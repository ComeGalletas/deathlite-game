"""DEV MENU: the developer-mode overlay (D2+).

Opened from a dev run with the backtick / tilde key. Freezes the run beneath it
(`draw_below` keeps it visible, `update_below=False` stops it advancing). Every
action operates on the `PlayingState` passed in as `playing`.

Pages:
  root       -- toggles + Reset / Exit / Close, and links into the sub-pages
  enemies    -- (D3) pick an enemy id; ENTER spawns one next to the hero
  blessings  -- (D4) pick a blessing; ENTER grants a stack to the hero
  items      -- (D5) every weapon + every item base, straight off the loaded
                content; ENTER gives the weapon or dev-equips a rolled item

Any page longer than `MAX_VISIBLE` scrolls: the visible window follows the
selection and "N more" markers show what's clipped, so the panel never outgrows
the screen no matter how much content is added -- every list is built from the
data files, so it grows / shrinks with the content.
"""
from __future__ import annotations

import random

import pygame

from game import config, fonts
from game.content import get_content
from game.state import State

MAX_VISIBLE = 12          # rows shown at once before the list scrolls
# The "Spawn pressure" row cycles the master's `dev_menu` modifier through these.
_PRESSURE_STEPS = (1.0, 2.0, 4.0, 0.0, 0.5)

_ROOT_ROWS = ("unlimited_hp", "no_attack", "no_damage", "colliders", "spawn_points",
              "all_rooms", "freeze", "pressure", "difficulty",
              "spawn", "blessings", "items", "reset", "exit", "close")

_LABELS = {
    "unlimited_hp": "Unlimited HP",
    "no_attack":    "Stop attacking",
    "no_damage":    "Attacks deal 0 damage",
    "colliders":    "Collision shapes",
    "spawn_points": "Spawn points",
    "all_rooms":    "Activate all rooms",
    "freeze":       "Freeze spawns",
    "pressure":     "Spawn pressure",
    "difficulty":   "Difficulty",
    "spawn":        "Spawn enemy...",
    "blessings":    "Blessings...",
    "items":        "Items...",
    "reset":        "Reset run",
    "exit":         "Exit to main menu",
    "close":        "Close",
}
_HEADINGS = {"root": "DEV MENU", "enemies": "SPAWN ENEMY",
             "blessings": "GRANT BLESSING", "items": "GRANT ITEM"}
_NAV = {"root": "Up/Down move   ENTER select   ESC / ` close",
        "enemies": "Up/Down   ENTER spawn   ESC back",
        "blessings": "Up/Down   ENTER grant   ESC back",
        "items": "Up/Down   ENTER grant   ESC back"}

_FG = (235, 240, 245)
_DIM = (165, 172, 182)
_ACCENT = (120, 255, 170)
_PANEL = (12, 14, 20, 236)


class DevMenuState(State):
    draw_below = True
    update_below = False

    def enter(self, *, playing=None, **kwargs) -> None:
        self._playing = playing
        self.page = "root"
        self.sel = 0
        self.scroll = 0
        self._status = ""
        c = get_content()
        self._enemy_ids = sorted(c.enemies)
        self._spawn_counts: dict[str, int] = {}
        lib = getattr(playing, "blessing_lib", None)
        self._blessing_ids = sorted(
            lib.by_id, key=lambda b: (lib.by_id[b].source, lib.by_id[b].name)
        ) if lib is not None else []

        # Items page: every weapon + every item base, straight off the data.
        # `("weapon", id)` or `("item", slot, base_id)` rows.
        self._weapon_ids = sorted(c.weapons)
        bases = c.items.get("bases", {})
        self._item_rows: list[tuple] = (
            [("weapon", w) for w in self._weapon_ids]
            + [("item", slot, b["id"]) for slot in sorted(bases) for b in bases[slot]]
        )
        self._base_by_id = {b["id"]: b for slot in bases for b in bases[slot]}
        self._item_counts: dict[tuple, int] = {}
        self._dev_item_seed = 0
        self._title_font = fonts.mono(28, bold=True)
        self._row_font = fonts.mono(22)
        self._hint_font = fonts.mono(15)

    def _rows(self) -> tuple | list:
        return {"root": _ROOT_ROWS, "enemies": self._enemy_ids,
                "blessings": self._blessing_ids, "items": self._item_rows}[self.page]

    def _goto(self, page: str) -> None:
        self.page = page
        self.sel = 0
        self.scroll = 0
        self._status = ""

    def _move(self, delta: int) -> None:
        n = len(self._rows())
        if n:
            self.sel = (self.sel + delta) % n
        self._clamp_scroll()

    def _clamp_scroll(self) -> None:
        n = len(self._rows())
        window = min(MAX_VISIBLE, n)
        if self.sel < self.scroll:
            self.scroll = self.sel
        elif self.sel >= self.scroll + window:
            self.scroll = self.sel - window + 1
        self.scroll = max(0, min(self.scroll, max(0, n - window)))

    # --- input ---------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        k = event.key
        if k in (pygame.K_ESCAPE, pygame.K_BACKQUOTE):
            if self.page != "root":
                self._goto("root")
            else:
                self.game.state_machine.pop()
        elif k in (pygame.K_UP, pygame.K_w):
            self._move(-1)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self._move(1)
        elif k in (pygame.K_RETURN, pygame.K_SPACE):
            if self.page == "root":
                self._activate(_ROOT_ROWS[self.sel])
            elif self.page == "enemies":
                self._spawn(self._enemy_ids[self.sel])
            elif self.page == "blessings":
                self._grant(self._blessing_ids[self.sel])
            elif self.page == "items":
                self._give_item(self._item_rows[self.sel])

    def _activate(self, rid: str) -> None:
        p = self._playing
        if p is None:
            return
        if rid == "unlimited_hp":
            p._dev_unlimited_hp = not p._dev_unlimited_hp
            if p._dev_unlimited_hp:
                if not p.player.alive or p.player.hp <= 0:
                    p.player.alive = True
                    p.player.hp = p.player.max_hp
                p._dev_hp_floor = p.player.hp
            self._status = f"Unlimited HP {'ON' if p._dev_unlimited_hp else 'off'}"
        elif rid == "no_attack":
            p._dev_no_attack = not p._dev_no_attack
            self._status = f"Stop attacking {'ON' if p._dev_no_attack else 'off'}"
        elif rid == "no_damage":
            p._dev_no_damage = not p._dev_no_damage
            self._status = f"Attacks deal 0 damage {'ON' if p._dev_no_damage else 'off'}"
        elif rid == "colliders":
            p._dev_show_colliders = not p._dev_show_colliders
            self._status = f"Collision shapes {'ON' if p._dev_show_colliders else 'off'}"
        elif rid == "spawn_points":
            p._dev_show_spawn_points = not p._dev_show_spawn_points
            self._status = f"Spawn points {'ON' if p._dev_show_spawn_points else 'off'}"
        elif rid == "all_rooms":
            m = p.spawn.master
            m.all_active = not m.all_active
            self._status = f"All rooms active {'ON' if m.all_active else 'off'}"
        elif rid == "freeze":
            m = p.spawn.master
            m.frozen = not m.frozen
            self._status = f"Spawns {'FROZEN' if m.frozen else 'running'}"
        elif rid == "pressure":
            m = p.spawn.master
            cur = m.modifiers.get("dev_menu", 1.0)
            nxt = _PRESSURE_STEPS[(_PRESSURE_STEPS.index(cur) + 1) % len(_PRESSURE_STEPS)
                                  if cur in _PRESSURE_STEPS else 0]
            if nxt == 1.0:
                m.clear_modifier("dev_menu")
            else:
                m.set_modifier("dev_menu", nxt)
            self._status = f"Spawn pressure modifier x{nxt:g}"
        elif rid == "difficulty":
            order = config.DIFFICULTY_ORDER
            nxt = order[(order.index(p.difficulty) + 1) % len(order)]
            p._set_difficulty(nxt)
            self._status = f"Difficulty -> {config.DIFFICULTY_LABELS[nxt]}"
        elif rid == "spawn":
            self._goto("enemies")
        elif rid == "blessings":
            self._goto("blessings")
        elif rid == "items":
            self._goto("items")
        elif rid == "reset":
            p._restart_dev_run()               # replaces the whole stack
        elif rid == "exit":
            from game.states.menu_state import MenuState
            self.game.state_machine.change(MenuState(self.game))
        elif rid == "close":
            self.game.state_machine.pop()

    def _spawn(self, enemy_id: str) -> None:
        p = self._playing
        if p is None:
            return
        offset = pygame.Vector2(120, 0).rotate(random.uniform(0.0, 360.0))
        # Owner `dev` is on the spawn master's `cap_exempt` list: a developer
        # piling bodies up for a stress test is not bound by the live cap the
        # director plays under. Count what was actually seated, not attempts.
        made = p.spawn.spawn_enemy(enemy_id, at=p.player.pos + offset, owner="dev")
        if made is None:
            self._status = f"{enemy_id}: the spawn master refused (world cap)"
            return
        self._spawn_counts[enemy_id] = self._spawn_counts.get(enemy_id, 0) + 1
        self._status = f"spawned {self._spawn_counts[enemy_id]} x {enemy_id}"

    def _grant(self, bid: str) -> None:
        p = self._playing
        if p is None:
            return
        from progression.blessings import apply_blessing
        b = p.blessing_lib.by_id[bid]
        apply_blessing(p.player, b)
        self._status = f"{b.name}  x{p.player.blessings.get(bid, 0)}"

    def _give_item(self, row: tuple) -> None:
        p = self._playing
        if p is None:
            return
        if row[0] == "weapon":
            from combat.weapons import Weapon
            wid = row[1]
            wdef = p.content.weapon(wid)
            p.player.weapons.append(Weapon(wid, wdef))
            key = ("weapon", wid)
            label = wdef.get("name", wid)
        else:
            from progression.items import generate_item
            _, slot, bid = row
            self._dev_item_seed += 1
            item = generate_item(
                p.content, seed=p.run_seed * 1000 + self._dev_item_seed,
                item_level=1, luck=p.player.stats["luck"], slot=slot, base_id=bid)
            self._dev_equip(item)
            key = ("item", bid)
            label = item.short()
        self._item_counts[key] = self._item_counts.get(key, 0) + 1
        self._status = f"{label}  (x{self._item_counts[key]})"

    def _dev_equip(self, item) -> None:
        """Mirror `PlayingState._apply_persistent_bonuses`' item handling:
        stat affixes -> layered Modifiers, tag affixes folded via
        rebuild_blessings, HP topped to the new max."""
        p = self._playing
        from progression.stats import Modifier
        from progression.blessings import rebuild as rebuild_blessings
        p.player.equipment.append(item)
        src = f"dev:item:{item.slot}#{len(p.player.equipment)}"
        p.player.add_modifiers(*(Modifier(stat, p._OP_MAP[op], val, src)
                                 for stat, op, val in item.stat_effects()))
        rebuild_blessings(p.player, p.blessing_lib)
        p.player.hp = p.player.max_hp

    # --- render ------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        self._clamp_scroll()                    # tolerate direct `sel` writes
        w, h = surface.get_size()
        rows = self._rows()
        n = len(rows)
        window = min(MAX_VISIBLE, n) or 1

        panel = pygame.Rect(0, 0, 480, 34 * window + 172)
        panel.center = (w // 2, h // 2)
        card = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(card, _PANEL, card.get_rect(), border_radius=12)
        pygame.draw.rect(card, _ACCENT, card.get_rect(), width=2, border_radius=12)
        surface.blit(card, panel.topleft)

        x = panel.left + 28
        y = panel.top + 22
        surface.blit(self._title_font.render(_HEADINGS[self.page], True, _ACCENT),
                     (x, y))
        y += 40

        above = self.scroll
        below = n - (self.scroll + window)
        surface.blit(self._hint_font.render(f"^  {above} more" if above else "",
                                            True, _DIM), (x, y))
        y += 18

        for i in range(self.scroll, self.scroll + window):
            selected = i == self.sel
            surface.blit(
                self._row_font.render(("> " if selected else "  ")
                                      + self._row_label(rows[i]),
                                      True, _FG if selected else _DIM), (x, y))
            y += 34

        surface.blit(self._hint_font.render(f"v  {below} more" if below > 0 else "",
                                            True, _DIM), (x, y))
        y += 22
        if self._status:
            surface.blit(self._hint_font.render(self._status, True, _ACCENT), (x, y))
        y += 20
        surface.blit(self._hint_font.render(_NAV[self.page], True, _DIM), (x, y))

    def _row_label(self, rid) -> str:
        p = self._playing
        if self.page == "enemies":
            n = self._spawn_counts.get(rid, 0)
            return f"{rid}   (x{n})" if n else rid
        if self.page == "blessings":
            b = p.blessing_lib.by_id[rid]
            owned = p.player.blessings.get(rid, 0)
            tag = f"   x{owned}" if owned else ""
            return f"{b.source[0].upper()}-{b.name}{tag}"
        if self.page == "items":
            # plain `weapon` = one of the auto-fire weapons (added to the hand);
            # `[slot]` = an equipment base for that slot (rolled + dev-equipped).
            if rid[0] == "weapon":
                wid = rid[1]
                name = p.content.weapon(wid).get("name", wid) if p else wid
                n = self._item_counts.get(("weapon", wid), 0)
                return f"weapon   {name}" + (f"   x{n}" if n else "")
            _, slot, bid = rid
            name = self._base_by_id.get(bid, {}).get("name", bid)
            n = self._item_counts.get(("item", bid), 0)
            return f"[{slot}]   {name}" + (f"   x{n}" if n else "")
        label = _LABELS[rid]
        if rid == "unlimited_hp" and p is not None:
            label += "   [ON]" if p._dev_unlimited_hp else "   [  ]"
        elif rid == "no_attack" and p is not None:
            label += "   [ON]" if p._dev_no_attack else "   [  ]"
        elif rid == "no_damage" and p is not None:
            label += "   [ON]" if p._dev_no_damage else "   [  ]"
        elif rid == "colliders" and p is not None:
            label += "   [ON]" if p._dev_show_colliders else "   [  ]"
        elif rid == "spawn_points" and p is not None:
            label += "   [ON]" if p._dev_show_spawn_points else "   [  ]"
        elif rid == "all_rooms" and p is not None:
            label += "   [ON]" if p.spawn.master.all_active else "   [  ]"
        elif rid == "freeze" and p is not None:
            label += "   [ON]" if p.spawn.master.frozen else "   [  ]"
        elif rid == "pressure" and p is not None:
            label += f"   [x{p.spawn.master.modifiers.get('dev_menu', 1.0):g}]"
        elif rid == "difficulty" and p is not None:
            label += f"   [{config.DIFFICULTY_LABELS[p.difficulty]}]"
        return label
