"""Whether the run's draw may show held input (RND-010.D6).

Two things the run draws read the keyboard or mouse as they are drawn: the
interact keycap's pressed look (`key_marker.py`) and the opening hints'
pressed keycaps (`hints.py`). Under an overlay the run is frozen, and under
the level-up, pause and TAB screens its frame is drawn once and kept
(`State.freeze_backdrop`); a key held on that one frame (the E that opened
the Forge) would stay pressed in the kept frame until the overlay closed. So
held input shows only while no overlay covers the run: under any overlay the
caps are drawn raised, kept frame or not, and a kept frame matches a full
redraw.
"""
from __future__ import annotations


def run_on_top(ps) -> bool:
    """False only when another state sits above `ps` on the stack. A run
    drawn on its own (no state machine, or not on its stack, as tests draw
    it) is treated as on top."""
    machine = getattr(getattr(ps, "game", None), "state_machine", None)
    covered = getattr(machine, "is_covered", None)
    return covered is None or not covered(ps)
