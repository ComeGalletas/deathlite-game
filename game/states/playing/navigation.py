"""Enemy flow-field navigation for PLAYING.

`NavCoordinator` drives the shared flow field toward the player (staggered,
round-robin rebuilds) and answers the per-enemy steering queries. The field and
its bookkeeping counters live on `PlayingState` (`_nav`, `_nav_t`, `_nav_rr`,
`_nav_last_ms`, `_nav_rebuilds`, `_obstacle_grid`) -- built in
`PlayingState._init_nav`, read by `_report_debug` and `test_enemy_nav` -- so this
class only mutates them.

Part of the split tracked in `journals/playing_state_refactor.md` (P6).
"""
from __future__ import annotations

import time

import pygame

from game import config


class NavCoordinator:
    # Repath early once the player is this many navigation cells from where the
    # field was last aimed -- keeps the field fresh without an 8 ms rebuild every
    # time the player nudges across a 32 px boundary (which happens ~8x/s).
    _DRIFT_CELLS = 2

    def __init__(self, ps) -> None:
        self.ps = ps

    def update(self, dt: float) -> None:
        """Refresh the flow field toward the player. A large player jump repaths
        every grid at once (rare); the periodic refresh rebuilds one grid per
        tick, round-robin, at `interval / n_grids` spacing -- so each grid still
        refreshes every `ENEMY_NAV_REBUILD_INTERVAL` but only one ~4 ms rebuild
        lands on any frame instead of the ~8 ms both-grids cost."""
        ps = self.ps
        if ps._nav is None:
            return
        ps._nav_t -= dt
        jumped = (ps._nav.target_cell_drift(ps.player.pos) >= self._DRIFT_CELLS)
        if not jumped and ps._nav_t > 0.0:
            return
        t0 = time.perf_counter()
        if jumped:
            ps._nav.rebuild(ps.player.pos)
            ps._nav_t = config.ENEMY_NAV_REBUILD_INTERVAL
        else:
            classes = ps._nav.classes
            ps._nav.rebuild(ps.player.pos,
                            only=classes[ps._nav_rr % len(classes)])
            ps._nav_rr += 1
            ps._nav_t = config.ENEMY_NAV_REBUILD_INTERVAL / len(classes)
        ps._nav_last_ms = (time.perf_counter() - t0) * 1000.0
        ps._nav_rebuilds += 1

    def direction(self, pos, radius) -> pygame.Vector2:
        """Flow-field steering direction toward the player for an enemy of
        `radius` at `pos`; a zero vector means "no route -- fall back to
        straight chase" (`config.ENEMY_PATHFINDING` off, or an unreached cell)."""
        if self.ps._nav is None:
            return pygame.Vector2()
        return self.ps._nav.direction(pos, radius)

    def neighbors(self, pos, radius) -> list:
        return self.ps.grid.query_circle(pos.x, pos.y, radius)

    def obstacles_near(self, pos, radius) -> list:
        if self.ps._obstacle_grid is None:
            return []
        return self.ps._obstacle_grid.query_circle(pos.x, pos.y, radius)
