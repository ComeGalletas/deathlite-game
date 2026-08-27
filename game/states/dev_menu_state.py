"""DEV MENU: the developer-mode overlay (D2+).

Opened from a dev run with the backtick / tilde key. Freezes the run beneath it
(`draw_below` keeps it visible, `update_below=False` stops it advancing). Every
action operates on the `PlayingState` passed in as `playing`.

Pages:
  root       -- toggles + Reset / Exit / Close, and links into the sub-pages
  enemies    -- (D3) pick an enemy id; ENTER spawns one next to the hero
  blessings  -- (D4) pick a blessing; ENTER grants a stack to the hero

Any page longer than `MAX_VISIBLE` scrolls: the visible window follows the
selection and "N more" markers show what's clipped, so the panel never outgrows
the screen no matter how much content is added. Items are a placeholder (D5).
"""
from __future__ import annotations

import random

import pygame

from game.content import get_content
from game.state import State

MAX_VISIBLE = 12          # rows shown at once before the list scrolls

_ROOT_ROWS = ("unlimited_hp", "no_attack", "spawn", "blessings", "items",
              "reset", "exit", "close")

_LABELS = {
    "unlimited_hp": "Unlimited HP",
    "no_attack":    "Stop attacking",
    "spawn":        "Spawn enemy...",
    "blessings":    "Blessings...",
    "items":        "Items...",
    "reset":        "Reset run",
    "exit":         "Exit to main menu",
    "close":        "Close",
}
_HEADINGS = {"root": "DEV MENU", "enemies": "SPAWN ENEMY",
             "blessings": "GRANT BLESSING"}
_NAV = {"root": "Up/Down move   ENTER select   ESC / ` close",
        "enemies": "Up/Down   ENTER spawn   ESC back",
        "blessings": "Up/Down   ENTER grant   ESC back"}

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
        self._enemy_ids = sorted(get_content().enemies)
        self._spawn_counts: dict[str, int] = {}
        lib = getattr(playing, "blessing_lib", None)
        self._blessing_ids = sorted(
            lib.by_id, key=lambda b: (lib.by_id[b].source, lib.by_id[b].name)
        ) if lib is not None else []
        self._title_font = pygame.font.SysFont("consolas", 28, bold=True)
        self._row_font = pygame.font.SysFont("consolas", 22)
        self._hint_font = pygame.font.SysFont("consolas", 15)

    def _rows(self) -> tuple | list:
        return {"root": _ROOT_ROWS, "enemies": self._enemy_ids,
                "blessings": self._blessing_ids}[self.page]

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
        elif rid == "spawn":
            self._goto("enemies")
        elif rid == "blessings":
            self._goto("blessings")
        elif rid == "reset":
            p._restart_dev_run()               # replaces the whole stack
        elif rid == "exit":
            from game.states.menu_state import MenuState
            self.game.state_machine.change(MenuState(self.game))
        elif rid == "close":
            self.game.state_machine.pop()
        else:                                   # items -> D5
            self._status = "(coming soon)"

    def _spawn(self, enemy_id: str) -> None:
        p = self._playing
        if p is None:
            return
        offset = pygame.Vector2(120, 0).rotate(random.uniform(0.0, 360.0))
        p._spawn_enemy(enemy_id, at=p.player.pos + offset)
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

    def _row_label(self, rid: str) -> str:
        p = self._playing
        if self.page == "enemies":
            n = self._spawn_counts.get(rid, 0)
            return f"{rid}   (x{n})" if n else rid
        if self.page == "blessings":
            b = p.blessing_lib.by_id[rid]
            owned = p.player.blessings.get(rid, 0)
            tag = f"   x{owned}" if owned else ""
            return f"{b.source[0].upper()}-{b.name}{tag}"
        label = _LABELS[rid]
        if rid == "unlimited_hp" and p is not None:
            label += "   [ON]" if p._dev_unlimited_hp else "   [  ]"
        elif rid == "no_attack" and p is not None:
            label += "   [ON]" if p._dev_no_attack else "   [  ]"
        return label
