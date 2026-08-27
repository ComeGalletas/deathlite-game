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

if TYPE_CHECKING:  # avoid a runtime import cycle game <-> state
    from game.game import Game


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

    def __init__(self, game: "Game") -> None:
        self.game = game

    def enter(self, **kwargs) -> None:  # noqa: D401 - hook
        """Called when this state becomes active (pushed or switched to)."""

    def exit(self) -> None:
        """Called when this state is removed from the stack."""

    def handle_event(self, event: pygame.event.Event) -> None:
        """One pygame event. Called only for the top-of-stack state."""

    def update(self, dt: float) -> None:
        """Advance simulation by dt seconds."""

    def draw(self, surface: pygame.Surface) -> None:
        """Render this state onto surface."""


class StateMachine:
    def __init__(self, game: "Game") -> None:
        self.game = game
        self._stack: list[State] = []

    # --- stack operations -------------------------------------------------
    @property
    def current(self) -> State | None:
        return self._stack[-1] if self._stack else None

    def push(self, state: State, **enter_kwargs) -> None:
        self._stack.append(state)
        state.enter(**enter_kwargs)

    def pop(self) -> None:
        if self._stack:
            self._stack.pop().exit()

    def change(self, state: State, **enter_kwargs) -> None:
        """Replace the whole stack with a single new state."""
        while self._stack:
            self._stack.pop().exit()
        self.push(state, **enter_kwargs)

    def is_empty(self) -> bool:
        return not self._stack

    # --- main-loop entry points ---------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if self._stack:
            self._stack[-1].handle_event(event)

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
        for state in self._stack[first:]:
            state.draw(surface)
