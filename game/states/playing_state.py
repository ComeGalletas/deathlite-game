"""Back-compat shim.

`PlayingState` now lives in the `game.states.playing` package
(`game/states/playing/core/state.py`) as part of the split tracked in
`journals/playing_state_refactor.md`. Import sites may use either path.
"""
from game.states.playing.core.state import PlayingState

__all__ = ["PlayingState"]
