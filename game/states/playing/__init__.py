"""The PLAYING state, split into focused sub-systems in three groups.

* `core/` -- the simulation: `PlayingState` (`core/state.py`, a thin
  coordinator that owns the frame pipeline, the draw-layer order, event
  routing and the wiring between the others), input, combat, physics,
  navigation, spawning, chests, locations, NPCs, transient effects and the
  run ledger.
* `visual/` -- rendering only, read-only over the state: the world renderer,
  the draw context, glow cache, swing / slash effects and the per-family
  `projectiles/` and `summons/` styles.
* `devtools/` -- developer-only instrumentation (the training-dummy DPS
  meter); nothing here runs in a normal run.

The only `core/` -> `devtools/` link is the coordinator constructing the
meter (`self.dps`); no other core module depends on `devtools/`. See
`journals/playing_state_refactor.md`.
"""
from game.states.playing.core.state import PlayingState

__all__ = ["PlayingState"]
