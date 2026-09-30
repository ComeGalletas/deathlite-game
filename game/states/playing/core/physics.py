"""Unit bumping for PLAYING (CB-3).

`BumpResolver.resolve(dt)` runs once per frame at the end of `_phase_update`,
after every body has moved. Any two overlapping mobile bodies -- enemy/enemy,
enemy/boss, hero/enemy, hero/boss -- shove each other apart with a
weight-split impulse from `combat.knockback.knock_split`. Nothing is moved
directly; each body just gets an `apply_knockback` call, and integrates it on
its own next `update` (`_knock`, decayed by `config.BUMP_DECAY`).

The soft `Separation` steering component (entities/ai) still does the cheap
work of keeping crowds loosely apart; this pass is the harder kick when bodies
genuinely interpenetrate -- a spawn on top of another, a charger tunnelling in,
a swarm herded against a wall.

The shove repeats every frame an overlap lasts, so it is a rate, and the pass
takes the frame's `dt` (ENT-019). On a frame shorter than the tuned one
(`tuned_dt`, 16 ms: the loop's frame at the 62 fps cap), `bump_scale(dt)`
sizes its share so a held overlap is shoved at the tuned speed a second
exactly, and a crowd comes apart in about the tuned time (within the bounds
`tests/playing/test_bump_rate.py` holds). On the tuned frame and any longer
one it is exactly 1.0 and the pass is what CB-3/H tuned, bit for bit (the
owner's call: slow frames keep their shove).

Read-only w.r.t. `PlayingState` apart from the `_knock` it induces:
`ps.enemies`, `ps.boss`, `ps.player`.
"""
from __future__ import annotations

import math

from combat.elements import ice as ice_rules
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

# The early drop in `resolve` computes the pair's distance in Python floats;
# `_bump` computes it through `Vector2`. Those are the same IEEE operations,
# but a pair within a billionth of either limit is left to `_bump` to
# decide, so the two can never disagree about a pair that matters.
_MARGIN_OUT = 1.0 + 1e-9
_COINCIDENT = 1e-9 * (1.0 - 1e-9)     # `_bump`'s coincident limit, a billionth under


def tuned_dt() -> float:
    """The frame CB-3/H tuned the bump on, in seconds (ENT-019).

    The loop's clock ticks in whole milliseconds (`Game._step`), so a cap
    of `BUMP_REFERENCE_FPS` (62) is a 16 ms frame, not 1/62 s: that is the
    frame the desktop actually ran, and still runs, at its cap."""
    return math.floor(1000.0 / config.BUMP_REFERENCE_FPS) / 1000.0


def bump_scale(dt: float) -> float:
    """This frame's share of the bump, as a multiple of the tuned one
    (ENT-019, `journals/bump_frame_rate_journal.md`).

    A pair held at the same overlap is handed `J` a frame and its knock
    decays by `BUMP_DECAY ** dt` a frame, so the knock settles at
    `J / (1 - BUMP_DECAY ** dt)`: that is the speed it is shoved at, and
    its distance a game-second. Sizing `J` by `1 - BUMP_DECAY ** dt` keeps
    both what they are on the tuned frame, at every shorter frame, exactly
    and not only as `dt` shrinks (`dt x 62` is 3 % weak at 144 Hz).

    It only ever scales down (owner, ENT-019.D5). The tuned frame and every
    longer one return exactly 1.0, so the shove there is the tuned one bit
    for bit: scaled up, a long frame hands a stiff pair (troll against
    bumblebee) its whole share at the overlap it started with, and flings
    the light one up to twice as far at 20 fps. Just under the tuned frame
    the share meets 1.0 continuously. A knock that never decayed
    (`BUMP_DECAY` 1.0) is the limit, `dt` over the tuned frame. A frame of
    no time, or a nonsense one (negative, NaN), shoves nothing.
    """
    ref_dt = tuned_dt()
    if dt >= ref_dt:
        return 1.0
    if not dt > 0.0:
        return 0.0
    decay = config.BUMP_DECAY
    if decay == 1.0:
        return dt / ref_dt
    return (1.0 - decay ** dt) / (1.0 - decay ** ref_dt)


def _pad(population) -> float:
    """The broad-phase pad for this frame: the largest collider present,
    never more than `_QUERY_PAD`.

    A body touching `a` has its centre within `a.radius + b.radius` of `a`,
    so a pad of the largest radius already reaches every body that can
    touch it. The grid's query covers whole cells, so a smaller pad returns
    a sub-block of the same cells in the same order, and every pair that
    matters in the same order (RND-008.5). It is capped at the old pad so
    a body bigger than that, such as a boss, is found exactly as before.
    Only the living count: a dead body is skipped on both sides of a pair.
    """
    biggest = max((b.radius for b in population if getattr(b, "alive", True)),
                  default=0.0)
    return min(_QUERY_PAD, float(biggest))


class BumpResolver:
    def __init__(self, ps) -> None:
        self.ps = ps
        self.run = getattr(ps, "run", ps)
        self._grid = SpatialGrid()

    def resolve(self, dt: float) -> None:
        """Shove every overlapping pair apart for a frame of `dt` seconds."""
        ps = self.ps
        run = getattr(self, "run", ps)
        enemies = run.enemies
        boss = run.boss if (run.boss is not None and run.boss.alive) else None

        population = enemies + [boss] if boss is not None else enemies
        if not population:
            return
        self._grid.rebuild(population)
        pad = _pad(population)
        grid = self._grid
        push = config.CROWD_PUSH_RADIUS_FRAC
        scale = bump_scale(dt)

        # enemy <-> enemy  and  enemy <-> boss
        #
        # RND-008.5: a pair that does not touch is dropped on two float
        # products, before any tuple, set or vector: `_bump` does nothing to
        # it (no shove, no frozen contact), so neither does skipping it.
        # The pairs that do touch go through exactly as before, in the same
        # order and the same way round, because the knockbacks they add are
        # summed and a float sum depends on its order.
        seen: set[tuple[int, int]] = set()
        for a in enemies:
            if not a.alive:
                continue
            ax, ay, ar = a.pos.x, a.pos.y, a.radius
            for b in grid.query_circle(ax, ay, ar + pad):
                if b is a or not getattr(b, "alive", True):
                    continue
                bpos = b.pos
                dx, dy = ax - bpos.x, ay - bpos.y
                d2 = dx * dx + dy * dy
                touch = ar + b.radius
                if d2 >= touch * touch * _MARGIN_OUT or d2 < _COINCIDENT:
                    continue                          # `_bump` would return at once
                key = (id(a), id(b)) if id(a) < id(b) else (id(b), id(a))
                if key in seen:
                    continue
                seen.add(key)
                # ENT-016: two enemies push at a fraction of their colliders,
                # so a pack can compress and file across a one-tile deck; the
                # boss still shoulders through at its full radius.
                self._bump(a, b, contact=True, reach=1.0 if b is boss else push,
                           scale=scale)

        # hero <-> enemy / boss
        p = run.player
        if p.alive:
            for e in grid.query_circle(p.pos.x, p.pos.y, p.radius + pad):
                if getattr(e, "alive", True):
                    self._bump(p, e, scale=scale)

    def _bump(self, a, b, contact: bool = False, reach: float = 1.0,
              scale: float = 1.0) -> None:
        """Shove `a` and `b` apart if they are closer than `reach` x their
        summed radii (the push radius; 1.0 is the colliders touching), by
        `scale` x the tuned shove (`bump_scale`; 1.0 is one tuned frame).

        The frozen-contact rule keeps the full colliders whatever the push
        radius: an ice slide clips what it touches, and a crowd allowed to
        compress (ENT-016) must not quietly make ice clip less."""
        delta = a.pos - b.pos
        d2 = delta.length_squared()
        touch = a.radius + b.radius
        if d2 >= touch * touch or d2 < 1e-9:
            return                                   # not overlapping / coincident
        rr = touch * reach
        if d2 < rr * rr:
            pen = min(rr - d2 ** 0.5, rr * _PEN_CAP_FRAC)
            push_a, push_b = knock_split(a.weight, b.weight,
                                          config.BUMP_GAIN * pen * scale)
            a.apply_knockback(delta, push_a)         # a shoved away from b
            b.apply_knockback(-delta, push_b)        # b shoved away from a
        if contact:
            # Only ever between two bodies: a sliding frozen enemy hurts
            # other enemies, never the hero (whose damage path is its
            # own, with evasion, block and armor).
            self._frozen_contact(a, b)

    def _frozen_contact(self, a, b) -> None:
        """A frozen body being shoved damages what it clips (elemental
        system M3). The bump pass is the one place two bodies are known
        to overlap, so the rule lives off this seam; the rule itself is
        the element's, in `combat/elements/ice.py`."""
        run = self.run
        resolver = getattr(run, "elements", None)
        if resolver is None:
            return
        ice_rules.exchange_contact(resolver, a, b, run.stats["time"])
