"""Explicit game-state machine (State pattern, spec sections 1.4 & 11).

Design goals:
  * Adding a new state must not require editing the main loop.
  * PAUSED and LEVEL_UP overlay PLAYING without destroying it, so a stack is
    used rather than a single "current state" slot.
  * The main loop only ever talks to `StateMachine`, never to concrete states.
"""
from __future__ import annotations

import enum
from typing import TYPE_CHECKING

import pygame

from game.display import uibox
from ui import veil

if TYPE_CHECKING:  # avoid a runtime import cycle game <-> state
    from game.game import Game


class _MusicInherit:
    """Sentinel for `State.music`: leave whatever track is playing alone."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "MUSIC_INHERIT"


#: Default for `State.music`. Distinct from `None`, which means *silence*.
MUSIC_INHERIT = _MusicInherit()


class GameState(enum.Enum):
    MENU = enum.auto()
    PLAYING = enum.auto()
    LEVEL_UP = enum.auto()
    PAUSED = enum.auto()
    GAME_OVER = enum.auto()
    VICTORY = enum.auto()


class State:
    """Base class. Subclasses override the hooks they care about."""

    # If True, the state directly below this one on the stack is still drawn
    # (used by PAUSED / LEVEL_UP to render the frozen game behind an overlay).
    draw_below: bool = False
    # If True, the state below still receives update(dt). Overlays set False so
    # gameplay is genuinely frozen while paused / choosing an upgrade.
    update_below: bool = False
    # If True (with `draw_below` and not `update_below`), the frozen states
    # below are drawn once and that frame is reused while this overlay is on
    # top (RND-012: the world under the level-up screen was redrawn every
    # frame, 47 ms in Chrome). Opt-in: an overlay whose actions change the
    # run while it is open (the dev menu) or whose freeze comes and goes
    # (the end banner) leaves it False. The wall-clock animations under the
    # overlay (water foam, animated scenery) stop while it is open (owner,
    # RND-012.D1), and the run draws no held input under any overlay
    # (`playing/visual/live_input.py`, RND-012.D6), so the kept frame matches
    # a full redraw. This overlay's own `draw_backdrop` and `draw` still run
    # every frame. Anything the overlay changes that the frame below shows
    # calls `StateMachine.invalidate_backdrop()`.
    freeze_backdrop: bool = False
    # If True, `draw` is handed the centred UI box (`game/display/uibox.py`)
    # rather than the whole render surface, and mouse events reach
    # `handle_event` in box coordinates. Every screen and overlay panel is a
    # box state; the run (`PlayingState`) is not -- its world fills the
    # surface and it draws its own HUD on the box. On a 16:9 render the box
    # is the surface and nothing differs.
    ui_box: bool = True
    # The colour this screen paints on the *whole* render surface before
    # its content goes on the box, or None to leave the main loop's
    # `COLOR_BG` (which is what the Options, hero-select, rankings and
    # Sanctuary screens use anyway). A screen with a background of its own
    # -- the loading screen's black, the end screens' colours, the menu --
    # sets it here, so a 21:9 render's side margins match the screen
    # instead of showing the loop's grey around a 16:9 box (owner,
    # 2026-09-16). Overlays leave it None: they dim in `draw_backdrop`.
    backdrop: tuple[int, int, int] | None = None
    # Which background track plays while this state is on top of the stack
    # (journal `music_tracks_journal.md`, 2026-09-16). One of:
    #   * `MUSIC_INHERIT` (the default) -- leave whatever is playing alone;
    #   * a key of `config.MUSIC_TRACKS` ("menu" / "gameplay");
    #   * `None` -- fade out to silence.
    # `StateMachine` applies it after every push / pop / change, so no state
    # touches the player in `enter()` and the main loop stays untouched --
    # the same arrangement as `backdrop` and `ui_box` above. Inheriting by
    # default is what makes the overlays free: PAUSED, LEVEL_UP, RUN STATUS
    # and the dev menu declare nothing and the run's track keeps playing
    # underneath them. `MusicPlayer.play` is idempotent, so the sibling
    # screens that all declare "menu" never restart it between themselves.
    music: "str | None | _MusicInherit" = MUSIC_INHERIT

    def __init__(self, game: "Game") -> None:
        self.game = game

    @property
    def music_player(self):
        """The game's `MusicPlayer`, or None when there is not one. Read
        defensively because many tests drive a single state with a stub game
        that carries only the few attributes that state touches."""
        return getattr(self.game, "music", None)

    def enter(self, **kwargs) -> None:  # noqa: D401 - hook
        """Called when this state becomes active (pushed or switched to)."""

    def exit(self) -> None:
        """Called when this state is removed from the stack."""

    def handle_event(self, event: pygame.event.Event) -> None:
        """One pygame event. Called only for the top-of-stack state."""

    def update(self, dt: float) -> None:
        """Advance simulation by dt seconds."""

    def on_display_changed(self) -> None:
        """The display was re-opened under this state (an Options change
        from the pause menu: another native size, mode or aspect). Anything
        built for the old surface -- fonts at the old scale, a camera with
        the old view, caches sized to the old span -- is rebuilt here. The
        default is nothing: a screen that builds all of it in `draw` needs
        no more."""

    def draw_backdrop(self, surface: pygame.Surface) -> None:
        """Paint on the *whole* render surface before `draw` gets the box:
        a screen's `backdrop` colour, or the overlays' dim layer, so that
        on a 21:9 render the side margins match too (owner, 2026-09-15 and
        2026-09-16)."""
        if self.backdrop is not None:
            surface.fill(self.backdrop)

    def draw(self, surface: pygame.Surface) -> None:
        """Render this state onto surface."""


class StateMachine:
    def __init__(self, game: "Game") -> None:
        self.game = game
        self._stack: list[State] = []
        # The frozen backdrop (`State.freeze_backdrop`): (key, frame) or None.
        self._frozen: tuple | None = None

    # --- stack operations -------------------------------------------------
    @property
    def current(self) -> State | None:
        return self._stack[-1] if self._stack else None

    def push(self, state: State, **enter_kwargs) -> None:
        self._frozen = None
        self._stack.append(state)
        state.enter(**enter_kwargs)
        self._apply_music()

    def pop(self) -> None:
        self._frozen = None
        if self._stack:
            self._stack.pop().exit()
            self._apply_music()

    def change(self, state: State, **enter_kwargs) -> None:
        """Replace the whole stack with a single new state."""
        self._frozen = None
        while self._stack:
            self._stack.pop().exit()
        self.push(state, **enter_kwargs)

    def is_covered(self, state: State) -> bool:
        """True when `state` is on the stack with another state above it (an
        overlay over the run). A state not on the stack is not covered."""
        return state in self._stack and self._stack[-1] is not state

    def invalidate_backdrop(self) -> None:
        """Redraw the frozen states below the overlay on the next frame: for
        a change the overlay makes that the frame below shows (the pause
        menu's key-layout toggle, which the run's hints spell out)."""
        self._frozen = None

    def _apply_music(self) -> None:
        """Hand the top state's `music` declaration to the player. Walks down
        past states that inherit, so popping a PAUSED overlay restores the
        run's track rather than falling silent -- and because `play` is
        idempotent, that restore is a no-op when nothing was ever swapped."""
        player = getattr(self.game, "music", None)
        if player is None:
            return
        for state in reversed(self._stack):
            if state.music is not MUSIC_INHERIT:
                player.play(state.music)
                return
        # Nothing on the stack has an opinion, so nothing changes. This is
        # load-bearing for the loading screen: it inherits, which is what
        # carries the menu track through world generation even though
        # `change()` cleared the menu off the stack first.

    def is_empty(self) -> bool:
        return not self._stack

    # --- main-loop entry points ---------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self._stack:
            state = self._stack[-1]
            if state.ui_box:
                screen = pygame.display.get_surface()
                if screen is not None:
                    event = uibox.translate_event(event, screen)
            state.handle_event(event)

    def on_display_changed(self) -> None:
        """Every state on the stack, bottom first, so the run under a pause
        overlay rebuilds before the overlay redraws over it."""
        self._frozen = None
        veil.clear()                     # old full-frame fills (RND-012)
        for state in list(self._stack):
            state.on_display_changed()

    def update(self, dt: float) -> None:
        # Walk from the top down; stop once a state says the one below it is
        # frozen. This lets PAUSED sit on top of a non-updating PLAYING.
        for state in reversed(self._stack):
            state.update(dt)
            if not state.update_below:
                break

    def draw(self, surface: pygame.Surface) -> None:
        # Find the lowest state that still needs drawing, then paint upward so
        # overlays land on top of the frozen scene.
        first = len(self._stack) - 1
        while first > 0 and self._stack[first].draw_below:
            first -= 1
        layers = self._stack[first:]
        box = None
        key = self._frozen_key(layers, surface)
        if key is None:
            self._frozen = None
        elif self._frozen is not None and self._frozen[0] == key:
            # The frozen states below, as drawn when the overlay opened.
            surface.blit(self._frozen[1], (0, 0))
            layers = layers[-1:]
        else:
            box = self._paint(layers[:-1], surface, box)
            self._frozen = (key, surface.copy())
            layers = layers[-1:]
        self._paint(layers, surface, box)

    @staticmethod
    def _paint(layers, surface, box):
        """Draw `layers` bottom first; returns the UI box it built, if any."""
        for state in layers:
            state.draw_backdrop(surface)
            if state.ui_box and surface is not None:
                if box is None:
                    box = uibox.box(surface)
                state.draw(box)
            else:
                state.draw(surface)
        return box

    @staticmethod
    def _frozen_key(layers, surface):
        """What the frozen backdrop is valid for, or None when this frame
        cannot use one: the top overlay has to opt in and freeze what it
        draws over, and the target has to be opaque. A blitted copy blends
        differently from drawing directly onto a per-pixel-alpha target
        (offscreen tests and tools), so those are always drawn in full
        (RND-012.D5). The key holds the states below by identity and the
        surface by identity and size, so a new stack, a re-opened display
        or another target redraws."""
        if surface is None or len(layers) < 2:
            return None
        top = layers[-1]
        if not (top.freeze_backdrop and top.draw_below and not top.update_below):
            return None
        if surface.get_masks()[3]:
            return None
        return (tuple(id(s) for s in layers), id(surface), surface.get_size())
