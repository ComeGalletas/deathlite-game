"""Booting a run inside a test.

Pressing ENTER on the hero select no longer lands in `PlayingState`: the
loading screen sits in between and builds the world a slice per frame.
`settle` drives it to the end, so a test that walks the menu into a run keeps
one line where it used to have none.
"""
from __future__ import annotations


def settle(game, limit: int = 5000):
    """Advance the game until the loading screen, if that is where it is,
    has handed over to the run. Returns the current state."""
    from game.states.loading_state import LoadingState
    for _ in range(limit):
        if not isinstance(game.state_machine.current, LoadingState):
            break
        game.state_machine.update(1 / 60)
        game._render()
    return game.state_machine.current
