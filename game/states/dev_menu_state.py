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
  forges     -- every Forging in `data/weapons/forges.json`; ENTER forges the owned
                weapon of that id (granting it first if the hero lacks it,
                the blessing-level requirement waived; still one Forge per
                weapon)
  weapons    -- the hero's owned weapon instances (+ "All weapons"); ENTER
                removes one, unwinding its orbiters, summons and the
                weapon-blessing stacks taken on that weapon id

Two root rows are not pages but previews: **Game over screen** and **Victory
screen** push the real results screen over the frozen run with this run's own
snapshot, and ESC there comes back here. Nothing is banked -- see
`_show_end_screen`.

Any page longer than `MAX_VISIBLE` scrolls: the visible window follows the
selection and "N more" markers show what's clipped, so the panel never outgrows
the screen no matter how much content is added -- every list is built from the
data files, so it grows / shrinks with the content.

Mouse (journal: "Mouse support in menus and UI", group E): the rows in the
visible window are click targets -- hover selects, a click activates exactly
as ENTER would on any page; the wheel scrolls the window (the selection is
kept inside it); right click is ESC's twin (back to the root, or close).
"""
from __future__ import annotations

import random

import pygame

from combat.elements.ids import ELEMENTS, ElementId
from game import config, fonts
from game.content import get_content
from game.state import State
from ui import scale
from ui.menu_nav import MenuNav

MAX_VISIBLE = 12          # rows shown at once before the list scrolls

_ROOT_ROWS = ("unlimited_hp", "no_attack", "no_damage", "colliders", "spawn_points",
              "aim_line", "auras", "reaction_log", "all_rooms", "freeze", "difficulty",
              "dummy", "spawn", "blessings", "items", "forges", "remove_weapon",
              "force_aura", "infuse", "game_over", "victory",
              "reset", "exit", "close")

_LABELS = {
    "unlimited_hp": "Unlimited HP",
    "no_attack":    "Stop attacking",
    "no_damage":    "Attacks deal 0 damage",
    "colliders":    "Collision shapes",
    "spawn_points": "Spawn points",
    "aim_line":     "Aim line",
    "auras":        "Aura inspector",
    "reaction_log": "Reaction log",
    "all_rooms":    "Activate all rooms",
    "freeze":       "Freeze spawns",
    "difficulty":   "Difficulty",
    "dummy":        "Training dummy",
    "spawn":        "Spawn enemy...",
    "blessings":    "Blessings...",
    "items":        "Items...",
    "forges":       "Forges...",
    "remove_weapon": "Remove weapon...",
    "force_aura":   "Force aura...",
    "infuse":       "Infuse weapons...",
    "game_over":    "Game over screen",
    "victory":      "Victory screen",
    "reset":        "Reset run",
    "exit":         "Exit to main menu",
    "close":        "Close",
}
_HEADINGS = {"root": "DEV MENU", "enemies": "SPAWN ENEMY",
             "blessings": "GRANT BLESSING", "items": "GRANT ITEM",
             "forges": "FORGE WEAPON", "weapons": "REMOVE WEAPON",
             "elements": "FORCE AURA", "infuse": "INFUSE WEAPON"}
_NAV = {"root": "Up/Down move   ENTER select   ESC / ` close",
        "enemies": "Up/Down   ENTER spawn   ESC back",
        "blessings": "Up/Down   ENTER grant   ESC back",
        "items": "Up/Down   ENTER grant   ESC back",
        "forges": "Up/Down   ENTER forge   ESC back",
        "weapons": "Up/Down   ENTER remove   ESC back",
        "elements": "Up/Down   ENTER apply to the nearest enemy   ESC back",
        "infuse": "Up/Down   ENTER cycle the element   ESC back"}
# The four elements, for the "Force aura" page: applying one drives the
# real resolver, so what the inspector then shows is live state.
_ELEMENT_ROWS = tuple(ELEMENTS)
# The weapons page's rows: the "remove everything" row, one per owned
# weapon instance (its index in `player.weapons`), or the empty marker.
_ROW_ALL = ("all",)
_ROW_NONE = ("none",)

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
        lib = getattr(playing, "blessing_lib", None)       # the P2 catalog
        self._blessing_ids = sorted(
            lib.by_id, key=lambda b: (lib.by_id[b].kind, lib.by_id[b].weapon or "",
                                      lib.by_id[b].name)
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
        # Forges page: every Forging in the data, grouped by weapon.
        self._forge_ids = sorted(
            c.forges, key=lambda f: (c.forges[f]["weapon"], c.forges[f]["name"]))
        self._title_font = fonts.mono(28, bold=True)
        self._row_font = fonts.mono(22)
        self._hint_font = fonts.mono(15)
        # ESC and the backtick both go back; so does the right button. The
        # visible rows are registered in draw() (ui/menu_nav.py).
        self._nav = MenuNav(back_keys=(pygame.K_ESCAPE, pygame.K_BACKQUOTE),
                            right_click_back=True)
        self._mouse = self._nav.mouse

    def _rows(self) -> tuple | list:
        if self.page == "weapons":
            return self._weapon_rows()
        return {"root": _ROOT_ROWS, "enemies": self._enemy_ids,
                "blessings": self._blessing_ids, "items": self._item_rows,
                "forges": self._forge_ids,
                "elements": _ELEMENT_ROWS,
                "infuse": self._infuse_rows()}[self.page]

    def _weapon_rows(self) -> list[tuple]:
        """Rebuilt on every read so the page tracks what the Items / Forges
        pages add and what this page removes."""
        p = self._playing
        n = len(p.player.weapons) if p is not None else 0
        if n == 0:
            return [_ROW_NONE]
        return [_ROW_ALL] + [("weapon", i) for i in range(n)]

    def _goto(self, page: str) -> None:
        self.page = page
        self.sel = 0
        self.scroll = 0
        self._status = ""

    def _clamp_scroll(self) -> None:
        n = len(self._rows())
        window = min(MAX_VISIBLE, n)
        if self.sel < self.scroll:
            self.scroll = self.sel
        elif self.sel >= self.scroll + window:
            self.scroll = self.sel - window + 1
        self.scroll = max(0, min(self.scroll, max(0, n - window)))

    def _scroll_by(self, delta: int) -> None:
        """Wheel: move the window, then pull the selection inside it (the
        keyboard rule is the reverse -- the window follows the selection)."""
        n = len(self._rows())
        window = min(MAX_VISIBLE, n)
        self.scroll = max(0, min(self.scroll + delta, max(0, n - window)))
        self.sel = max(self.scroll, min(self.sel, self.scroll + max(0, window - 1)))

    # --- input ---------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_by(-event.y)          # wheel up (y > 0) shows earlier rows
            return
        verb = self._nav.event(event, index=self.sel, count=len(self._rows()))
        if verb is None:
            return
        what, v = verb
        if what == "move":
            self.sel = v                       # a registered row is always visible
            self._clamp_scroll()               # the window follows the keyboard
        elif what == "activate":
            self.sel = v
            self._clamp_scroll()
            self._activate_selected()
        elif what == "back":
            self._back()

    def _back(self) -> None:
        if self.page != "root":
            self._goto("root")
        else:
            self.game.state_machine.pop()

    def _activate_selected(self) -> None:
        """ENTER / click on the selected row, whatever the page."""
        if self.page == "root":
            self._activate(_ROOT_ROWS[self.sel])
        elif self.page == "enemies":
            self._spawn(self._enemy_ids[self.sel])
        elif self.page == "blessings":
            self._grant(self._blessing_ids[self.sel])
        elif self.page == "items":
            self._give_item(self._item_rows[self.sel])
        elif self.page == "forges":
            self._forge(self._forge_ids[self.sel])
        elif self.page == "weapons":
            self._remove_weapon(self._weapon_rows()[self.sel])
        elif self.page == "elements":
            self._force_aura(_ELEMENT_ROWS[self.sel])
        elif self.page == "infuse":
            self._cycle_infusion(self._infuse_rows()[self.sel])

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
        elif rid == "aim_line":
            p._dev_show_aim = not p._dev_show_aim
            self._status = f"Aim line {'ON' if p._dev_show_aim else 'off'}"
        elif rid == "auras":
            p._dev_show_auras = not p._dev_show_auras
            self._status = f"Aura inspector {'ON' if p._dev_show_auras else 'off'}"
        elif rid == "reaction_log":
            p._dev_show_reaction_log = not p._dev_show_reaction_log
            self._status = f"Reaction log {'ON' if p._dev_show_reaction_log else 'off'}"
        elif rid == "all_rooms":
            m = p.spawn.master
            m.all_active = not m.all_active
            self._status = f"All rooms active {'ON' if m.all_active else 'off'}"
        elif rid == "freeze":
            m = p.spawn.master
            m.frozen = not m.frozen
            self._status = f"Spawns {'FROZEN' if m.frozen else 'running'}"
        elif rid == "difficulty":
            order = config.DIFFICULTY_ORDER
            nxt = order[(order.index(p.difficulty) + 1) % len(order)]
            p._set_difficulty(nxt)
            self._status = f"Difficulty -> {config.DIFFICULTY_LABELS[nxt]}"
        elif rid == "dummy":
            self._toggle_dummy()
        elif rid == "spawn":
            self._goto("enemies")
        elif rid == "blessings":
            self._goto("blessings")
        elif rid == "items":
            self._goto("items")
        elif rid == "forges":
            self._goto("forges")
        elif rid == "remove_weapon":
            self._goto("weapons")
        elif rid == "force_aura":
            self._goto("elements")
        elif rid == "infuse":
            self._goto("infuse")
        elif rid in ("game_over", "victory"):
            self._show_end_screen(rid == "victory")
        elif rid == "reset":
            p._restart_dev_run()               # replaces the whole stack
        elif rid == "exit":
            from game.states.menu_state import MenuState
            self.game.state_machine.change(MenuState(self.game))
        elif rid == "close":
            self.game.state_machine.pop()

    # --- elemental (M2) -------------------------------------------
    def _nearest_enemy(self):
        """The living enemy closest to the hero, or the boss if it is the
        only thing up. What the Force aura page acts on."""
        p = self._playing
        bodies = [e for e in p.enemies if e.alive]
        if p.boss is not None and p.boss.alive:
            bodies.append(p.boss)
        if not bodies:
            return None
        return min(bodies, key=lambda e: (e.pos - p.player.pos).length_squared())

    def _element_label(self, element) -> str:
        """The row, with what the nearest enemy currently holds, so the page
        doubles as a readout while the inspector is off."""
        p = self._playing
        label = element.key.title()
        target = self._nearest_enemy() if p is not None else None
        if target is None:
            return label
        state = getattr(target, "elemental", None)
        if state is None:
            return label
        now = p.stats["time"]
        if state.element(now) == element:
            label += f"   [held {state.remaining(now):.1f}s]"
        elif state.is_locked(now):
            label += f"   (locked {state.lock_remaining(now):.1f}s)"
        return label

    def _infuse_rows(self) -> list:
        """One row per weapon the hero holds, summons included -- every
        weapon can take an element (owner's decision, 2026-09-21)."""
        p = self._playing
        n = len(p.player.weapons) if p is not None else 0
        return [("weapon", i) for i in range(n)] or [_ROW_NONE]

    def _infusion_label(self, row) -> str:
        if row == _ROW_NONE:
            return "(no weapons)"
        w = self._playing.player.weapons[row[1]]
        held = w.element.key if w.infused else "none"
        if w.element_mode == "time":
            pace = f"every {w.element_window:.2g}s"
        elif w.element_interval:
            pace = f"1 attack in {w.element_interval + 1}"
        else:
            pace = "every attack"
        return f"{w.name.ljust(14)} {held.ljust(8)} ({pace})"

    def _cycle_infusion(self, row) -> None:
        """Step a weapon through none -> fire -> ice -> thunder -> wind ->
        none. One row and one key, rather than a second page: the whole
        point is to try pairs quickly."""
        if row == _ROW_NONE:
            self._status = "No weapons to infuse"
            return
        p = self._playing
        w = p.player.weapons[row[1]]
        order = (ElementId.NONE, *ELEMENTS)
        w.element = order[(order.index(w.element) + 1) % len(order)]
        if w.infused:
            p.run.unlocked_elements.add(w.element)
        held = w.element.key if w.infused else "nothing"
        self._status = f"{w.name} carries {held}"

    def _force_aura(self, element) -> None:
        """Apply one element to the nearest enemy through the real resolver,
        so the aura, the lock and any reaction behave exactly as a weapon's
        hit would. Until weapons carry elements (M6) this is the only way to
        drive the system in a running game."""
        p = self._playing
        if p is None:
            return
        target = self._nearest_enemy()
        if target is None:
            self._status = "No enemy to apply it to"
            return
        outcome = p.run.elements.apply(
            target, element, weapon_id="dev", hit_damage=10.0,
            now=p.stats["time"])
        name = getattr(target, "name", element.key)
        self._status = f"{element.key.title()} on {name}: {outcome.name.lower()}"

    def _show_end_screen(self, victory: bool) -> None:
        """Open the real results screen over the frozen dev run, as a preview.

        A dev run can never reach these screens on its own -- `run_end.hand_off`
        diverts it to `restart_dev_run()` before the Victory / GameOver branch --
        so this is the only way to read a résumé without playing a real run out
        to its end. The dict is built by the *same* `_snapshot_summary` a real
        ending uses, off this run's live numbers, so the columns show whatever
        the other pages have granted.

        `hand_off` is deliberately not used: it publishes `RUN_ENDED`, and that
        is what drives `Game._on_run_ended` (salvage bank, best run, item stash,
        `save.mark_cleared`, `persist`). Skipping the publish keeps the preview
        out of the save entirely, and leaves the run's `_ending` flag clear --
        the run is frozen under the screen, not over. `preview=True` is what
        makes the screen's ESC and Main menu button come back here rather than
        change to the main menu; its other two buttons leave as shipped.
        """
        p = self._playing
        if p is None:
            return
        summary = p._snapshot_summary(victory)
        if victory:
            from game.states.victory_state import VictoryState
            state = VictoryState(self.game)
        else:
            from game.states.game_over_state import GameOverState
            state = GameOverState(self.game)
        self._status = ("Victory" if victory else "Game over") + " screen (preview)"
        self.game.state_machine.push(state, stats=summary, preview=True)

    def _toggle_dummy(self) -> None:
        """Spawn one training dummy and meter it, or clear both.

        The dummy goes through the spawn master like every other enemy, rather
        than being dropped into `ps.enemies` behind its back. Its own owner,
        `"dummy"`, is on both the master's `cap_exempt` and `never_sleep`
        lists: the plain `"dev"` owner is cap-exempt but *sleepable*, and a
        hibernated dummy silently leaves `ps.enemies` while still alive, so the
        weapons stop reaching it and the meter flatlines mid-measurement with
        nothing to show it happened. Measured: it slept nine seconds in.
        """
        p = self._playing
        if p is None:
            return
        if p.dps.armed:
            dummy = p.dps.target
            p.dps.disarm()
            dummy.alive = False               # the master reaps it next tick
            self._status = "Training dummy removed"
            return
        offset = pygame.Vector2(140, 0).rotate(random.uniform(0.0, 360.0))
        made = p.spawn.spawn_enemy("training_dummy", at=p.player.pos + offset,
                                   owner="dummy")
        if made is None:
            self._status = "training dummy: the spawn master refused"
            return
        p.dps.arm(made)
        self._status = "Training dummy up -- DPS on the F1 overlay"

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
        from combat.weapons import Weapon
        from progression.blessings import apply_blessing
        b = p.blessing_lib.by_id[bid]
        if p.player.blessings.get(bid, 0) >= b.max_level:
            self._status = f"{b.name}  at max level"
            return
        if b.weapon is not None and p.player.weapon_by_id(b.weapon) is None:
            # Dev convenience: a weapon blessing for a weapon the hero lacks
            # hands the weapon over first.
            p.player.weapons.append(Weapon(b.weapon, p.content.weapon(b.weapon)))
        apply_blessing(p.player, b)
        self._status = f"{b.name}  L{p.player.blessings.get(bid, 0)}"

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

    def _forge(self, fid: str) -> None:
        """Apply a Forging through the real `apply_forge`, so the result is
        exactly what the village Forge / a Forge card produces. Dev
        conveniences: the hero is handed the weapon first when they lack
        it, and the `forge_requires_levels` gate is waived. One Forge per
        weapon still holds: with every owned instance of the id already
        forged, refuse and say so."""
        p = self._playing
        if p is None:
            return
        from combat.weapons import Weapon
        from combat.weapons.forge import apply_forge, get_forges
        fdef = get_forges(p.content).get(fid)
        base_name = p.content.weapon(fdef.weapon).get("name", fdef.weapon)
        owned = [w for w in p.player.weapons if w.weapon_id == fdef.weapon]
        if not owned:
            w = Weapon(fdef.weapon, p.content.weapon(fdef.weapon))
            p.player.weapons.append(w)
            owned = [w]
        target = next((w for w in owned if w.forge is None), None)
        if target is None:
            self._status = f"{base_name} already forged into {owned[0].name}"
            return
        apply_forge(target, fdef)
        self._status = f"{base_name} -> {fdef.name}"

    def _remove_weapon(self, row: tuple) -> None:
        p = self._playing
        if p is None or row == _ROW_NONE:
            return
        if row == _ROW_ALL:
            targets = list(p.player.weapons)
        else:
            targets = [p.player.weapons[row[1]]]
        for w in targets:
            self._retire_weapon(w)
        self._status = (f"removed {len(targets)} weapons" if row == _ROW_ALL
                        else f"removed {targets[0].name}")
        self.sel = min(self.sel, len(self._weapon_rows()) - 1)

    def _retire_weapon(self, w) -> None:
        """Take one weapon instance out of the hero's hands and unwind what
        it owned: persistent projectiles and summons go inactive (their
        systems reap them next frame); once no instance of the id remains,
        the weapon / grant blessing stacks taken on that id are cleared so
        a re-granted weapon starts clean and the offering is not misled.
        Stat blessings, items and equipment modifiers are untouched (weapon
        blessings carry no stat effects -- catalog rule)."""
        p = self._playing
        p.player.weapons.remove(w)
        for o in w._orbiters:
            o.active = False
        w._orbiters.clear()
        w._orbit_count = 0
        for s in w._summons:
            s.active = False
        w._summons.clear()
        if p.player.weapon_by_id(w.weapon_id) is None:
            from progression.blessings import rebuild as rebuild_blessings
            lib = p.blessing_lib
            for bid in list(p.player.blessings):
                b = lib.by_id.get(bid)
                if b is not None and b.kind in ("weapon", "grant") and b.weapon == w.weapon_id:
                    del p.player.blessings[bid]
            rebuild_blessings(p.player, lib)

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

        S = scale.px
        panel = pygame.Rect(0, 0, S(480), S(34 * window + 172))
        panel.center = (w // 2, h // 2)
        card = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(card, _PANEL, card.get_rect(), border_radius=S(12))
        pygame.draw.rect(card, _ACCENT, card.get_rect(), width=max(1, S(2)), border_radius=S(12))
        surface.blit(card, panel.topleft)

        x = panel.left + S(28)
        y = panel.top + S(22)
        surface.blit(self._title_font.render(_HEADINGS[self.page], True, _ACCENT),
                     (x, y))
        y += S(40)

        above = self.scroll
        below = n - (self.scroll + window)
        surface.blit(self._hint_font.render(f"^  {above} more" if above else "",
                                            True, _DIM), (x, y))
        y += S(18)

        hits = self._mouse.hits
        hits.clear()
        for i in range(self.scroll, self.scroll + window):
            selected = i == self.sel
            surface.blit(
                self._row_font.render(("> " if selected else "  ")
                                      + self._row_label(rows[i]),
                                      True, _FG if selected else _DIM), (x, y))
            # The row's band inside the panel, keyed by its absolute index.
            hits.add(pygame.Rect(panel.left + S(16), y - S(3), panel.width - S(32), S(34)), i)
            y += S(34)

        surface.blit(self._hint_font.render(f"v  {below} more" if below > 0 else "",
                                            True, _DIM), (x, y))
        y += S(22)
        if self._status:
            surface.blit(self._hint_font.render(self._status, True, _ACCENT), (x, y))
        y += S(20)
        surface.blit(self._hint_font.render(_NAV[self.page], True, _DIM), (x, y))

    def _row_label(self, rid) -> str:
        p = self._playing
        if self.page == "enemies":
            n = self._spawn_counts.get(rid, 0)
            return f"{rid}   (x{n})" if n else rid
        if self.page == "blessings":
            b = p.blessing_lib.by_id[rid]
            owned = p.player.blessings.get(rid, 0)
            tag = f"   L{owned}" if owned else ""
            head = p.content.weapon(b.weapon)["name"] if b.weapon else "Hero"
            return f"{head}: {b.name}{tag}"
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
        if self.page == "forges":
            f = p.content.forges[rid]
            head = p.content.weapon(f["weapon"]).get("name", f["weapon"])
            carried = any(w.forge == rid for w in p.player.weapons)
            return f"{head}: {f['name']}" + ("   (forged)" if carried else "")
        if self.page == "elements":
            return self._element_label(rid)
        if self.page == "infuse":
            return self._infusion_label(rid)
        if self.page == "weapons":
            if rid == _ROW_NONE:
                return "(no weapons)"
            if rid == _ROW_ALL:
                return f"All weapons   ({len(p.player.weapons)})"
            w = p.player.weapons[rid[1]]
            forged = f"   [{w.name}]" if w.forge else ""
            base = p.content.weapon(w.weapon_id).get("name", w.weapon_id)
            return f"{base}   Lv{w.level}{forged}"
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
        elif rid == "aim_line" and p is not None:
            label += "   [ON]" if p._dev_show_aim else "   [  ]"
        elif rid == "auras" and p is not None:
            label += "   [ON]" if p._dev_show_auras else "   [  ]"
        elif rid == "reaction_log" and p is not None:
            label += "   [ON]" if p._dev_show_reaction_log else "   [  ]"
        elif rid == "all_rooms" and p is not None:
            label += "   [ON]" if p.spawn.master.all_active else "   [  ]"
        elif rid == "freeze" and p is not None:
            label += "   [ON]" if p.spawn.master.frozen else "   [  ]"
        elif rid == "difficulty" and p is not None:
            label += f"   [{config.DIFFICULTY_LABELS[p.difficulty]}]"
        elif rid == "dummy" and p is not None:
            label += "   [ON]" if p.dps.armed else "   [  ]"
        return label
