"""The small read-only context the per-family draw packages
(`projectiles/`, `summons/`) take: the asset cache, the run clock for animation
timing, and the camera zoom. Screen coordinates are passed positionally.
"""
from __future__ import annotations

from typing import NamedTuple


class DrawCtx(NamedTuple):
    assets: object      # game.assets.Assets
    now: float          # PlayingState.stats["time"] -- animation clock
    zoom: float          # camera zoom
