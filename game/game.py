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
from game.assets import get_assets
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
        # Sprite/image cache. Lazy -- no disk read until a draw asks for a frame,
        # and a missing file degrades to primitive drawing (never raises).
        self.assets = get_assets()
        self.save_path = save_path or save_mod.DEFAULT_PATH
        self.save = (save_mod.load(self.save_path) if config.SAVE_ENABLED
                     else save_mod.SaveData())
        self.meta_catalog = MetaCatalog(self.content.meta_upgrades)

        self.audio = AudioManager(self.events)
        self.audio.muted = bool(self.save.settings.get("muted", False))
        self.audio.volume = float(self.save.settings.get("volume", 0.7))

        self.state_machine = StateMachine(self)
        self.debug = DebugOverlay()

        # A finished run banks its rewards into the save file.
        self.events.subscribe(Events.RUN_ENDED, self._on_run_ended)

    # --- lifecycle --------------------------------------------------
    def quit(self) -> None:
        self.running = False

    def persist(self) -> None:
        if not config.SAVE_ENABLED:
            return  # session-only build (browser) -- nothing is written to disk
        self.save.settings["muted"] = self.audio.muted
        self.save.settings["volume"] = self.audio.volume
        try:
            save_mod.save(self.save, self.save_path)
        except OSError:
            log.exception("could not write save file")

    def _on_run_ended(self, *, stats: dict, victory: bool, dev: bool = False) -> None:
        if dev:
            return  # developer-mode runs never bank salvage / best / loot or save
        gained = int(stats.get("currency", 0)
                     * self.meta_catalog.salvage_multiplier(self.save.meta))
        self.save.currency += gained
        self.save.record_best(stats, difficulty=stats.get("difficulty", "normal"))
        for item in stats.get("dropped_items", ()):
            self.save.add_item(item)
        self.persist()

    def _start(self) -> None:
        """Push the opening state and arm the loop. Shared by `run` (desktop)
        and `run_async` (browser)."""
        from game.states.menu_state import MenuState
        self.state_machine.change(MenuState(self))
        self.running = True

    def _step(self) -> None:
        """One iteration of the main loop: timing -> input -> update -> render.
        Clears `self.running` when the state stack drains. Identical work for
        both loop drivers so desktop and browser never diverge."""
        dt = self.clock.tick(config.FPS) / 1000.0
        dt = min(dt, config.MAX_DT)  # clamp -- see config.MAX_DT

        self._process_input()
        if self.state_machine.is_empty():
            self.running = False
            return

        t0 = time.perf_counter()
        self.state_machine.update(dt)
        t1 = time.perf_counter()

        self._render()
        t2 = time.perf_counter()

        self.debug.record_timing((t1 - t0) * 1000.0, (t2 - t1) * 1000.0)

    def run(self) -> None:
        """Desktop entry: a plain blocking loop."""
        self._start()
        while self.running:
            self._step()
        pygame.quit()

    async def run_async(self) -> None:
        """Browser (pygbag / emscripten) entry: the same loop, but it yields to
        the host event loop once per frame with `await asyncio.sleep(0)` so the
        page stays responsive. Works on desktop too (`asyncio.run`)."""
        import asyncio

        self._start()
        while self.running:
            self._step()
            await asyncio.sleep(0)
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
        # toggle_collision_vis (F7) is now a dev-run overlay -- delegate it to the
        # PlayingState hook below so it only fires inside a developer run.

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
