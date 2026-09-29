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

from game import config, locale, save as save_mod
from game.assets import get_assets
from game.content import get_content
from game.display import DisplayWindow
from game.events import EventBus, Events
from game.state import StateMachine
from progression.meta import MetaCatalog
from systems.audio import AudioManager
from systems.debug_overlay import DebugOverlay
from systems.music import MusicPlayer
from ui.mouse import install_cursor, system_match_scale

log = logging.getLogger(__name__)


class Game:
    def __init__(self, save_path=None) -> None:
        DisplayWindow.prepare()             # SDL hints: before init
        pygame.init()
        pygame.display.set_caption(config.TITLE)
        self._set_icon()                    # before the window: SDL reads it there
        # Persistent progression (spec 4.7). Load is corruption-tolerant. Read
        # before the window opens: the saved display mode and size shape it.
        self.save_path = save_path or save_mod.DEFAULT_PATH
        self.save = (save_mod.load(self.save_path) if config.SAVE_ENABLED
                     else save_mod.SaveData())
        # The window the fixed 1600x900 frame is scaled into (game/display/).
        self.display = DisplayWindow()
        self.display.restore(self.save.settings)
        self.display.on_before_open = self._before_display_open
        self.display.on_reopened = self._on_display_reopened
        self.screen, self.vsync = self.display.open()
        self.clock = pygame.time.Clock()
        self.running = False

        self.events = EventBus()

        self.content = get_content()
        # Sprite/image cache. Lazy -- no disk read until a draw asks for a frame,
        # and a missing file degrades to primitive drawing (never raises).
        self.assets = get_assets()
        # The arrow from assets/ui/pointers as the hardware cursor; a missing
        # file or a refusing build keeps the system arrow (see ui/mouse.py).
        # A hardware cursor is in screen pixels, so it is measured against
        # the cursor the desktop itself draws -- see `_cursor_scale`.
        self.cursor_installed = install_cursor(self.assets, self._cursor_scale())
        self.display.on_scale_changed = lambda _s: install_cursor(
            self.assets, self._cursor_scale())
        self.meta_catalog = MetaCatalog(self.content.meta_upgrades)

        self.audio = AudioManager(self.events)
        self.audio.muted = bool(self.save.settings.get("muted", False))
        # `settings["volume"]` is the sound-effects level -- the name predates
        # the master and keeps its meaning, so a save written before the mixer
        # existed comes back with its mix intact and the master wide open
        # (journal `audio_mixer_journal.md`, 2026-09-16).
        self.audio.set_volume(self.save.settings.get(
            "volume", config.SFX_VOLUME_DEFAULT))
        # The streamed score shares the device the cue player just opened.
        # Which track plays is not decided here: every state declares it
        # (`State.music`) and `StateMachine` applies the declaration.
        self.music = MusicPlayer(self.audio.backend)
        self.music.set_volume(self.save.settings.get(
            "music_volume", config.MUSIC_VOLUME_DEFAULT))
        self.music.set_muted(self.audio.muted)
        self.set_master_volume(self.save.settings.get(
            "master_volume", config.MASTER_VOLUME_DEFAULT), persist=False)

        # The UI language (UI-014), before any state draws text. The save
        # already replaced an unknown code with the default.
        locale.set_language(self.save.settings.get("language", locale.DEFAULT))

        self.state_machine = StateMachine(self)
        self.debug = DebugOverlay()

        # A finished run banks its rewards into the save file.
        self.events.subscribe(Events.RUN_ENDED, self._on_run_ended)

    # --- lifecycle --------------------------------------------------
    def quit(self) -> None:
        self.running = False

    # --- controls (CB-5) ----------------------------------------------
    @property
    def key_layout(self) -> str:
        """Name of the active `config.KEY_LAYOUTS` entry, from the save."""
        name = self.save.settings.get("key_layout")
        return name if name in config.KEY_LAYOUTS else config.DEFAULT_KEY_LAYOUT

    @property
    def keys(self) -> dict:
        """The active layout's `{"move": {...}, "aim": {...}}` key tuples."""
        return config.KEY_LAYOUTS[self.key_layout]

    def set_key_layout(self, name: str) -> None:
        """Switch layouts and persist at once, like mute / volume."""
        if name not in config.KEY_LAYOUTS:
            raise ValueError(f"unknown key layout: {name!r}")
        self.save.settings["key_layout"] = name
        self.persist()

    def set_master_volume(self, v: float, *, persist: bool = True) -> None:
        """The mixer's master, held by both players so each folds it into the
        level it computes (journal `audio_mixer_journal.md`, 2026-09-16). One
        setter rather than two so the two can never drift apart. `persist` is
        False only while booting, before the save is anything but what was
        just read."""
        self.audio.set_master(v)
        self.music.set_master(self.audio.master)     # the clamped, rounded value
        if persist:
            self.persist()

    @property
    def tutorials(self) -> bool:
        """The Options "Tutorials" row: the run's opening keycap hints."""
        return bool(self.save.settings.get("tutorials", True))

    def set_tutorials(self, on: bool) -> None:
        self.save.settings["tutorials"] = bool(on)
        self.persist()

    # --- language (UI-014) ---------------------------------------------
    @property
    def language(self) -> str:
        """The UI language in use, a `locale.LANGUAGES` code."""
        return locale.language()

    def set_language(self, code: str) -> None:
        """Switch the UI language and persist at once, like the key layout.
        Every screen draws its text each frame, so the change shows on the
        next frame; nothing needs a restart."""
        self.save.settings["language"] = locale.set_language(code)
        self.persist()

    def cycle_language(self, direction: int = 1) -> str:
        """Step to the next (or previous) language in `locale.LANGUAGES`,
        the Options "Language" row. Returns the new code."""
        names = locale.LANGUAGES
        nxt = names[(names.index(self.language) + direction) % len(names)]
        self.set_language(nxt)
        return nxt

    def cycle_key_layout(self) -> str:
        """Advance to the next layout (the pause / options toggle). Returns
        the new name."""
        names = list(config.KEY_LAYOUTS)
        nxt = names[(names.index(self.key_layout) + 1) % len(names)]
        self.set_key_layout(nxt)
        return nxt

    def _cursor_scale(self) -> float:
        """What to draw the arrow at. The desktop's own cursor is the
        measure (owner, 2026-09-16: tied to the render scale it read 20-40 %
        too big on a 1440p desktop), so the size is absolute in screen
        pixels and the same windowed, fullscreen and at either render width.
        Where the platform will not say its cursor size the old rule stands:
        the design scale, times the render scale (the interface's size),
        times what the presenter still adds (1 under native rendering, more
        while a dragged window is being scaled)."""
        matched = system_match_scale(self.assets)
        if matched is not None:
            return matched
        return (float(config.UI_CURSOR_SCALE) * float(config.RENDER_SCALE)
                * float(self.display.scale))

    def _before_display_open(self) -> None:
        """A display re-init (a render-width change in Options) loses the
        caption and the icon; both must be set before the window opens."""
        pygame.display.set_caption(config.TITLE)
        self._set_icon()

    def _on_display_reopened(self, surface) -> None:
        self.screen = surface
        self.vsync = self.display.vsync
        self.debug._font = None                   # rebuilt at the new scale
        self.state_machine.on_display_changed()

    def persist(self) -> None:
        if not config.SAVE_ENABLED:
            return  # session-only build (browser) -- nothing is written to disk
        self.save.settings["muted"] = self.audio.muted
        self.save.settings["volume"] = self.audio.volume          # sound effects
        self.save.settings["music_volume"] = self.music.volume
        self.save.settings["master_volume"] = self.audio.master
        self.save.settings["display"] = self.display.settings()
        self.display.dirty = False
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
        # P5 (design §20): the first boss kill with a hero unlocks that hero's
        # main-weapon choice.
        if victory and stats.get("character_id"):
            self.save.mark_cleared(stats["character_id"])
        self.persist()

    @staticmethod
    def _set_icon() -> bool:
        """Put Aegis on the window and the taskbar. Returns whether it took.

        Loaded straight off disk rather than through `Assets`, because this runs
        *before* the display exists and `convert_alpha` needs one -- and it has
        to run before `set_mode`, which is where SDL picks the icon up. A
        missing or unreadable file leaves pygame's default, the same degrade
        contract as the cursor and the sprites: the game never fails to open
        over decoration.
        """
        from game.assets import ASSETS_DIR
        path = ASSETS_DIR / config.WINDOW_ICON
        try:
            pygame.display.set_icon(pygame.image.load(str(path)))
            return True
        except (pygame.error, OSError) as exc:
            logging.getLogger(__name__).info(
                "window icon unavailable (%s); pygame default", exc)
            return False

    @staticmethod
    def _open_window():
        """The bare display surface (`DisplayWindow.open_surface`): synced
        to the display when `config.VSYNC` asks and the driver allows, the
        plain window otherwise. Kept as the seam `tests/flows/test_window.py`
        pins; the game itself opens through `self.display.open()`."""
        return DisplayWindow.open_surface()

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

        self.music.update(dt)   # advances a track fade; no-op otherwise

        t0 = time.perf_counter()
        self.state_machine.update(dt)
        t1 = time.perf_counter()

        self._render()
        t2 = time.perf_counter()

        self.debug.record_timing((t1 - t0) * 1000.0, (t2 - t1) * 1000.0)

    def _close(self) -> None:
        """A dragged window size is written once, here, not per event."""
        if self.display.dirty:
            self.persist()
        pygame.quit()

    def run(self) -> None:
        """Desktop entry: a plain blocking loop."""
        self._start()
        while self.running:
            self._step()
        self._close()

    async def run_async(self) -> None:
        """Browser (pygbag / emscripten) entry: the same loop, but it yields to
        the host event loop once per frame with `await asyncio.sleep(0)` so the
        page stays responsive. Works on desktop too (`asyncio.run`)."""
        import asyncio

        self._start()
        while self.running:
            self._step()
            await asyncio.sleep(0)
        self._close()

    # --- loop phases ----------------------------------------------
    def _process_input(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            self.display.handle_event(event)      # a drag resize; never consumed
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_m:
                    self.audio.toggle_mute()
                    self.music.set_muted(self.audio.muted)
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
