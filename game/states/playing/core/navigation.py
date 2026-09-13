"""Enemy flow-field navigation for PLAYING.

`NavCoordinator` keeps the shared flow field aimed at the player and
answers the per-enemy steering queries. The field and its bookkeeping
counters live on `PlayingState` (`_nav`, `_nav_t`, `_nav_rr`,
`_nav_last_ms`, `_nav_rebuilds`, `_obstacle_grid`) -- built in
`PlayingState._init_nav`, read by `_report_debug` and `test_enemy_nav` -- so
this class only mutates them.

A fill is **sliced**: `NavField.begin` starts one and `NavField.step`
advances it for `config.ENEMY_NAV_FILL_BUDGET` seconds a frame, while the
previous field keeps steering until the new one is swapped in. A whole
fill was 15-19 ms on the LD-10 worlds and fired three times a second as
the hero walked -- the game's biggest frame-time spike. The periodic
refresh starts one class per tick, round-robin; a player jump of
`_DRIFT_CELLS` starts every class at once. Either way no frame pays more
than the budget.

Part of the split tracked in `journals/playing_state_refactor.md` (P6).
"""
from __future__ import annotations

import time

import pygame

from game import config


class NavCoordinator:
    # Repath early once the player is this many navigation cells from where the
    # field was last aimed -- keeps the field fresh without a fill every time
    # the player nudges across a 32 px boundary (which happens ~8x/s).
    _DRIFT_CELLS = 2

    def __init__(self, ps) -> None:
        self.ps = ps

    def update(self, dt: float) -> None:
        """Aim a new fill when one is due -- a large player jump starts every
        class at once (rare); the periodic refresh starts one class per tick,
        round-robin, at `interval / n_grids` spacing -- then advance whatever
        is filling by this frame's budget."""
        ps = self.ps
        nav = ps._nav
        if nav is None:
            return
        ps._nav_t -= dt
        jumped = (nav.target_cell_drift(ps.player.pos) >= self._DRIFT_CELLS)
        if jumped:
            nav.begin(ps.player.pos)
            ps._nav_t = config.ENEMY_NAV_REBUILD_INTERVAL
            ps._nav_rebuilds += 1
        elif ps._nav_t <= 0.0:
            classes = nav.classes
            nav.begin(ps.player.pos, only=classes[ps._nav_rr % len(classes)])
            ps._nav_rr += 1
            ps._nav_t = config.ENEMY_NAV_REBUILD_INTERVAL / len(classes)
            ps._nav_rebuilds += 1
        if nav.filling:
            t0 = time.perf_counter()
            nav.step(config.ENEMY_NAV_FILL_BUDGET)
            ps._nav_last_ms = (time.perf_counter() - t0) * 1000.0

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
