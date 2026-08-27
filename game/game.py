"""Game: owns the window, the fixed pipeline main loop and the state machine.

The loop follows spec section 1.3:

    INPUT -> UPDATE -> COLLISION/COMBAT -> PROGRESSION -> RENDER

UPDATE..PROGRESSION all happen inside `state_machine.update(dt)`; the loop here
is responsible only for timing, global input (quit + debug keys) and blitting.
Everything is delta-time driven; frame count is never used as a clock.
"""
from __future__ import annotations

import logging
import time

import pygame

from game import config, save as save_mod
from game.content import get_content
from game.events import EventBus, Events
from game.state import StateMachine
from progression.meta import MetaCatalog
from systems.audio import AudioManager
from systems.debug_overlay import DebugOverlay

log = logging.getLogger(__name__)


class Game:
    def __init__(self, save_path=None) -> None:
        pygame.init()
        pygame.display.set_caption(config.TITLE)
        self.screen = pygame.display.set_mode(
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = False

        self.events = EventBus()

        # Persistent progression (spec 4.7). Load is corruption-tolerant.
        self.content = get_content()
        self.save_path = save_path or save_mod.DEFAULT_PATH
        self.save = save_mod.load(self.save_path)
        self.meta_catalog = MetaCatalog(self.content.meta_upgrades)

        self.audio = AudioManager(self.events)
        self.audio.muted = bool(self.save.settings.get("muted", False))
        self.audio.volume = float(self.save.settings.get("volume", 0.7))

        self.state_machine = StateMachine(self)
        self.debug = DebugOverlay()

        # Global debug flags the states read.
        self.show_collision = False

        # A finished run banks its rewards into the save file.
        self.events.subscribe(Events.RUN_ENDED, self._on_run_ended)

    # --- lifecycle --------------------------------------------------
    def quit(self) -> None:
        self.running = False

    def persist(self) -> None:
        self.save.settings["muted"] = self.audio.muted
        self.save.settings["volume"] = self.audio.volume
        try:
            save_mod.save(self.save, self.save_path)
        except OSError:
            log.exception("could not write save file")

    def _on_run_ended(self, *, stats: dict, victory: bool) -> None:
        gained = int(stats.get("currency", 0)
                     * self.meta_catalog.salvage_multiplier(self.save.meta))
        self.save.currency += gained
        self.save.record_best(stats)
        for item in stats.get("dropped_items", ()):
            self.save.add_item(item)
        self.persist()

    def run(self) -> None:
        from game.states.menu_state import MenuState
        self.state_machine.change(MenuState(self))

        self.running = True
        while self.running:
            dt = self.clock.tick(config.FPS) / 1000.0
            dt = min(dt, config.MAX_DT)  # clamp -- see config.MAX_DT

            self._process_input()
            if self.state_machine.is_empty():
                self.running = False
                break

            t0 = time.perf_counter()
            self.state_machine.update(dt)
            t1 = time.perf_counter()

            self._render()
            t2 = time.perf_counter()

            self.debug.record_timing((t1 - t0) * 1000.0, (t2 - t1) * 1000.0)

        pygame.quit()

    # --- loop phases ----------------------------------------------
    def _process_input(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_m:
                    self.audio.toggle_mute()
                    self.persist()
                    continue
                if self._handle_debug_key(event.key):
                    continue
            self.state_machine.handle_event(event)

    def _handle_debug_key(self, key: int) -> bool:
        """Return True if the key was a consumed debug binding."""
        keys = config.DEBUG_KEYS
        if key == keys["toggle_overlay"]:
            self.debug.toggle()
            return True
        if key == keys["toggle_collision_vis"]:
            self.show_collision = not self.show_collision
            return True

        # The rest need an active run; delegate to it if present.
        state = self.state_machine.current
        hook = getattr(state, "handle_debug_key", None)
        if hook is not None and hook(key):
            return True
        return False

    def _render(self) -> None:
        self.screen.fill(config.COLOR_BG)
        self.state_machine.draw(self.screen)
        self.debug.draw(self.screen, self.clock)
        pygame.display.flip()
