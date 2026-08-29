"""The PLAYING state, split into focused sub-systems.

`PlayingState` (in `state.py`) is a thin coordinator: it owns the frame
pipeline, the draw-layer order, event routing, and the wiring between the
sub-system modules alongside it. See `journals/playing_state_refactor.md`.
"""
from game.states.playing.state import PlayingState

__all__ = ["PlayingState"]
