"""Unit bumping for PLAYING (CB-3).

`BumpResolver.resolve()` runs once per frame at the end of `_phase_update`,
after every body has moved. Any two overlapping mobile bodies -- enemy/enemy,
enemy/boss, hero/enemy, hero/boss -- shove each other apart with a
weight-split impulse from `combat.knockback.knock_split`. Nothing is moved
directly; each body just gets an `apply_knockback` call, and integrates it on
its own next `update` (`_knock`, decayed by `config.BUMP_DECAY`).

The soft `Separation` steering component (entities/ai) still does the cheap
work of keeping crowds loosely apart; this pass is the harder kick when bodies
genuinely interpenetrate -- a spawn on top of another, a charger tunnelling in,
a swarm herded against a wall.

Read-only w.r.t. `PlayingState` apart from the `_knock` it induces:
`ps.enemies`, `ps.boss`, `ps.player`.
"""
from __future__ import annotations

from combat.knockback import knock_split
from game import config
from systems.collision import SpatialGrid

# Broad-phase query slack. The grid is coarse (GRID_CELL_SIZE) so this only has
# to be in the right ballpark; the precise overlap test in `_bump` does the
# real filtering.
_QUERY_PAD = 72.0

# A fast mover (charger at 660 px/s) can land deep inside another body in one
# frame; clamp the effective penetration so it cannot generate an absurd
# impulse. You cannot meaningfully be more than "mostly on top" anyway. 0.6
# (from 0.75) after the CB-3/H playtest: a stacked pile-up then settles in
# ~0.6 s instead of ~1.7 s, with no effect on shallow everyday overlaps.
_PEN_CAP_FRAC = 0.6


class BumpResolver:
    def __init__(self, ps) -> None:
        self.ps = ps
        self._grid = SpatialGrid()

    def resolve(self) -> None:
        ps = self.ps
        enemies = ps.enemies
        boss = ps.boss if (ps.boss is not None and ps.boss.alive) else None

        population = enemies + [boss] if boss is not None else enemies
        if not population:
            return
        self._grid.rebuild(population)

        # enemy <-> enemy  and  enemy <-> boss
        seen: set[tuple[int, int]] = set()
        for a in enemies:
            if not a.alive:
                continue
            for b in self._grid.query_circle(a.pos.x, a.pos.y,
                                             a.radius + _QUERY_PAD):
                if b is a or not getattr(b, "alive", True):
                    continue
                key = (id(a), id(b)) if id(a) < id(b) else (id(b), id(a))
                if key in seen:
                    continue
                seen.add(key)
                self._bump(a, b)

        # hero <-> enemy / boss
        p = ps.player
        if p.alive:
            for e in self._grid.query_circle(p.pos.x, p.pos.y,
                                             p.radius + _QUERY_PAD):
                if getattr(e, "alive", True):
                    self._bump(p, e)

    def _bump(self, a, b) -> None:
        delta = a.pos - b.pos
        d2 = delta.length_squared()
        rr = a.radius + b.radius
        if d2 >= rr * rr or d2 < 1e-9:
            return                                   # not overlapping / coincident
        pen = min(rr - d2 ** 0.5, rr * _PEN_CAP_FRAC)
        push_a, push_b = knock_split(a.weight, b.weight, config.BUMP_GAIN * pen)
        a.apply_knockback(delta, push_a)             # a shoved away from b
        b.apply_knockback(-delta, push_b)            # b shoved away from a
