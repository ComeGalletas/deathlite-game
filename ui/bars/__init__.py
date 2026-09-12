"""HUD bars and badges cut from the `assets/ui/` HUD sheets.

* `slices` -- the one-dimensional 3-slice that rebuilds a 48-px cell at any
  length.
* `meters` -- the HP / XP bars: housing, trough and an exactly-cut fill.
* `medallion` -- the level gem seated in its socket ring.

Every builder returns `None` rather than raising when its art is missing, so
`ui/hud.py` keeps its primitive rectangles as the fallback.

The two public names are bound off the modules rather than imported by name,
because `medallion.medallion` would otherwise shadow its own module here and
leave `medallion.clear_cache` unreachable.
"""
from __future__ import annotations

from ui.bars import medallion as _medallion
from ui.bars import meters as _meters
from ui.bars import slices as _slices

bar = _meters.bar
medallion = _medallion.medallion

__all__ = ["bar", "clear_cache", "medallion"]


def clear_cache() -> None:
    """Test helper: drop every cached bar, slice and medallion."""
    _slices.clear_cache()
    _meters.clear_cache()
    _medallion.clear_cache()
