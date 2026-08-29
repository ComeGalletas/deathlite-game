"""Back-compat shim.

`PlayingState` now lives in the `game.states.playing` package
(`game/states/playing/state.py`) as part of the split tracked in
`journals/playing_state_refactor.md`. Import sites may use either path.
"""
from game.states.playing.state import PlayingState

__all__ = ["PlayingState"]
