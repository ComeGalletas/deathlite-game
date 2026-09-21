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


def start_run(game, seed=None, keys=(), dev=False):
    """Drive `game` from its menu into a run, and return the `PlayingState`.

    `keys` are extra keys pressed on the hero select before the run begins
    (walking the hero index). `dev` takes the menu's developer-mode row
    instead of the first one.

    `seed` pins the world. The run seed is decided by the loading screen, and
    the hero select starting the run itself leaves it random -- so a test
    whose assertions depend on *which* world it got (where the trees stand,
    which special rooms the layout has, whether a villager is standing in the
    open) hands a seed in here rather than taking what comes. A test that
    only needs *a* run leaves it out.
    """
    import pygame
    from game.states.loading_state import LoadingState
    from game.states.playing.core.state import PlayingState

    def key(k):
        game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))

    if dev:
        key(pygame.K_DOWN)                         # -> "Start new developer mode game"
    key(pygame.K_RETURN)                           # menu -> hero select
    for k in keys:
        key(k)
    if seed is None:
        key(pygame.K_RETURN)                       # hero select -> loading
    else:
        # What `CharacterSelectState._begin` does, plus the seed.
        cs = game.state_machine.current
        game.state_machine.change(LoadingState(game), seed=seed,
                                  character_id=cs.hero_id,
                                  difficulty=cs.difficulty, dev=dev,
                                  main_weapon=cs.main_weapon(cs.hero_id))
    p = settle(game)                               # through the loading screen
    assert isinstance(p, PlayingState), p
    return p
