"""GAME_OVER: run summary after the player dies.

Milestone 1 stub. Full stat readout (survival time, level, kills, damage,
build summary) is fleshed out in Milestone 5.
"""
from __future__ import annotations

import pygame

from game import config
from game.state import State


class GameOverState(State):
    def enter(self, *, stats: dict | None = None, **kwargs) -> None:
        self.stats = stats or {}
        self._title_font = pygame.font.SysFont("georgia", 56, bold=True)
        self._font = pygame.font.SysFont("georgia", 24)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            from game.states.character_select_state import CharacterSelectState
            self.game.state_machine.change(CharacterSelectState(self.game))
        elif event.key == pygame.K_s:
            from game.states.meta_state import MetaState
            self.game.state_machine.change(MetaState(self.game))
        elif event.key == pygame.K_ESCAPE:
            from game.states.menu_state import MenuState
            self.game.state_machine.change(MenuState(self.game))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((22, 10, 12))
        cx = config.SCREEN_WIDTH // 2
        title = self._title_font.render("You Died", True, (230, 90, 90))
        surface.blit(title, title.get_rect(center=(cx, 200)))

        build = ", ".join(f"{n} Lv{l}" for n, l in self.stats.get("weapons", [])) or "-"
        blessings = sum(self.stats.get("blessings", {}).values())
        t = max(1e-6, self.stats.get("time", 0))
        lines = [
            f"Hero       {self.stats.get('character', '-')}",
            f"Survived   {self.stats.get('time', 0):.1f} s",
            f"Level      {self.stats.get('level', 1)}",
            f"Kills      {self.stats.get('kills', 0)}   ({self.stats.get('kills', 0) / t * 60:.0f}/min)",
            f"Damage     {self.stats.get('damage_dealt', 0):.0f}   ({self.stats.get('damage_dealt', 0) / t:.0f} dps)",
            f"Salvage    {self.stats.get('currency', 0)}  (banked)",
            f"Blessings  {blessings}",
            f"Loot       {len(self.stats.get('dropped_items', []))} item(s) to the stash",
            f"Build      {build}",
        ]
        for i, line in enumerate(lines):
            text = self._font.render(line, True, config.COLOR_TEXT)
            surface.blit(text, text.get_rect(center=(cx, 286 + i * 30)))

        hint = self._font.render("ENTER new run    -    S Sanctuary    -    ESC menu",
                                 True, config.COLOR_TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(cx, 286 + len(lines) * 30 + 26)))
