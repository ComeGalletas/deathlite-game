"""The bump-rate bench: does the crowd bump separate bodies by the same
amount per game-second at any frame rate?

ENT-019. The bump pass (`game/states/playing/core/physics.py`) shoves every
overlapping pair once a frame, and each body integrates the shove in its own
`update` and decays it by `BUMP_DECAY ** dt`. This bench steps the same
start for the same game time at several frame rates and compares:

* **the crowd**: the spawn-stress harness's packed crowd (`spawn_stress.build`
  and `cascade_setup` with nothing primed), `--live` bodies packed into
  `--pack` px round where the hero stood. Their AI is made inert and the
  hero is parked out of reach, so the bump alone moves them. Reported: the
  time until the crowd's total overlap is down to half, a quarter and a
  tenth, and the overlap left at fixed times.
* **two pairs**, set `PAIR_DEPTH` px inside their push radius on open ground:
  two bodies of one kind ("equal"), and the heaviest against the lightest in
  the run ("lopsided", where the weight gap amplifies the shove and the
  pass is stiffest). Reported: their distance at fixed times and the peak
  knock.

The steps are the game's own: every enemy's real `Enemy.update`, then
`BumpResolver.resolve`, as `PlayingState._phase_update` orders them.

    python -m tools.benchmarks.bump_rate
    python -m tools.benchmarks.bump_rate --rates 30 62 144 --seconds 1
    python -m tools.benchmarks.bump_rate --markdown       # the journal's tables

Headless and deterministic: the same arguments print the same table. The
tables land in `journals/bump_frame_rate_journal.md`;
`tests/playing/test_bump_rate.py` runs the bench's cases.
"""
from __future__ import annotations

import argparse
import os
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

RATES = (20, 30, 45, 62, 144, 165)
SEED = 35
LIVE = 60
PACK = 70.0            # px: the disc round the hero the crowd is packed into
PAIR_DEPTH = 12.0      # px a pair starts inside its push radius
CHECKPOINTS = (0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0)
FRACTIONS = (0.5, 0.25, 0.1)   # of the starting overlap, for the crowd's times


class _Inert:
    """A behaviour that stands still: the bench measures the bump, not the
    AI's steering (whose own `Separation` would muddy it)."""

    def tick(self, enemy, *_ctx) -> None:
        enemy.vel.update(0, 0)


class Bench:
    """One booted run, its crowd packed and made inert, and the starting
    positions every trial is reset to."""

    def __init__(self, seed: int = SEED, live: int = LIVE, pack: float = PACK,
                 save_path: str | None = None) -> None:
        import pygame
        from game import config
        from tools.benchmarks import spawn_stress as S

        self.seed = seed
        if save_path is None:
            save_path = os.path.join(tempfile.mkdtemp(), "save.json")
        # The LOD knob is left as it is: the bench steps enemies itself.
        self.game, self.ps = S.build(seed, live, 0, 300.0, config.ENEMY_LOD_SKIP,
                                     save_path=save_path)
        S.cascade_setup(self.ps, radius=pack, prime=False)
        self.home = pygame.Vector2(self.ps.player.pos)
        # Out of every enemy's reach: only enemy pairs are met.
        self.ps.player.pos.update(self.home.x + S._HERO_OFFSIDE,
                                  self.home.y + S._HERO_OFFSIDE)
        for e in self.ps.enemies:
            e._behavior = _Inert()
        self.crowd = list(self.ps.enemies)
        self.start = [pygame.Vector2(e.pos) for e in self.crowd]

    # --- stepping ------------------------------------------------------
    def _reset(self, bodies, spots) -> None:
        for e, p in zip(bodies, spots):
            e.pos.update(p)
            e._knock.update(0, 0)
            e.vel.update(0, 0)

    def step(self, dt: float) -> None:
        """One frame of what moves a body: every enemy's update, then the
        bump pass, in `PlayingState._phase_update`'s order."""
        ps = self.ps
        ctx = ps._enemy_context(dt)
        for e in ps.run.enemies:
            e.update(ctx)
        ps.bump.resolve()

    def _run(self, hz: float, seconds: float, measure) -> list:
        """`[(t, measure())]` from t = 0, one entry a frame."""
        dt = 1.0 / hz
        out = [(0.0, measure())]
        for k in range(round(seconds * hz)):
            self.step(dt)
            out.append(((k + 1) * dt, measure()))
        return out

    # --- the crowd -----------------------------------------------------
    def overlap(self) -> float:
        """The crowd's total overlap, px: over every enemy pair, how far
        inside their push radius (`CROWD_PUSH_RADIUS_FRAC` of the summed
        colliders, the reach the pass shoves at) they are."""
        from game import config

        frac = config.CROWD_PUSH_RADIUS_FRAC
        live = [e for e in self.ps.run.enemies if e.alive]
        total = 0.0
        for i, a in enumerate(live):
            ax, ay, ar = a.pos.x, a.pos.y, a.radius
            for b in live[i + 1:]:
                reach = frac * (ar + b.radius)
                dx, dy = ax - b.pos.x, ay - b.pos.y
                d2 = dx * dx + dy * dy
                if d2 < reach * reach:
                    total += reach - d2 ** 0.5
        return total

    def crowd_trial(self, hz: float, seconds: float = 2.0) -> list:
        """The packed crowd from its start, `[(t, overlap)]`."""
        self._reset(self.crowd, self.start)
        return self._run(hz, seconds, self.overlap)

    # --- the pairs -----------------------------------------------------
    def pair(self, kind: str) -> tuple:
        """Two bodies of the run: "equal" is the first two of one kind,
        "lopsided" the heaviest against the lightest."""
        crowd = self.crowd
        if kind == "equal":
            for i, a in enumerate(crowd):
                for b in crowd[i + 1:]:
                    if a.enemy_id == b.enemy_id:
                        return a, b
            raise LookupError("no two bodies of one kind in the crowd")
        if kind == "lopsided":
            return (max(crowd, key=lambda e: e.weight),
                    min(crowd, key=lambda e: e.weight))
        raise ValueError(kind)

    def pair_trial(self, kind: str, hz: float, seconds: float = 1.0) -> tuple:
        """The pair from `PAIR_DEPTH` px inside its push radius, alone on
        the field. Returns `([(t, distance)], peak knock of the first)`."""
        import pygame
        from game import config

        a, b = self.pair(kind)
        reach = config.CROWD_PUSH_RADIUS_FRAC * (a.radius + b.radius)
        spots = [pygame.Vector2(self.home),
                 self.home + pygame.Vector2(reach - PAIR_DEPTH, 0.0)]
        enemies = self.ps.run.enemies
        field = list(enemies)
        enemies[:] = [a, b]
        peak = [0.0]

        def measure():
            peak[0] = max(peak[0], a._knock.length(), b._knock.length())
            return a.pos.distance_to(b.pos)
        try:
            self._reset((a, b), spots)
            series = self._run(hz, seconds, measure)
        finally:
            enemies[:] = field
            self._reset(self.crowd, self.start)
        return series, peak[0]


# --- reading a series ----------------------------------------------------
def at(series: list, t: float) -> float:
    """The series at time `t`, linear between the frames either side (the
    rates do not share frame times)."""
    for (t0, v0), (t1, v1) in zip(series, series[1:]):
        if t1 >= t - 1e-12:
            return v0 + (t - t0) / (t1 - t0) * (v1 - v0)
    return series[-1][1]


def time_to(series: list, fraction: float) -> float | None:
    """When the series first falls to `fraction` of its start, linear
    between frames; `None` if it never does."""
    goal = series[0][1] * fraction
    for (t0, v0), (t1, v1) in zip(series, series[1:]):
        if v1 <= goal:
            return t1 if v0 == v1 else t0 + (v0 - goal) / (v0 - v1) * (t1 - t0)
    return None


# --- the table -----------------------------------------------------------
def _fmt(v, width: int = 7, digits: int = 3) -> str:
    return f"{'never':>{width}}" if v is None else f"{v:{width}.{digits}f}"


def report(bench: Bench, rates, seconds: float) -> str:
    lines = []
    lines.append(f"seed {bench.seed}, {len(bench.crowd)} bodies packed, "
                 f"AI inert, hero out of reach")
    lines.append("")
    lines.append("crowd: time to " + " / ".join(f"{int(f * 100)} %" for f in FRACTIONS)
                 + " of the starting overlap, then the overlap (px) left at "
                 + ", ".join(f"{t:g}" for t in CHECKPOINTS) + " s")
    for hz in rates:
        s = bench.crowd_trial(hz, seconds)
        times = " ".join(_fmt(time_to(s, f)) for f in FRACTIONS)
        left = " ".join(_fmt(at(s, t), 7, 1) for t in CHECKPOINTS)
        lines.append(f"  {hz:>4} Hz {times}  | start {s[0][1]:7.1f} | {left}")
    for kind in ("equal", "lopsided"):
        a, b = bench.pair(kind)
        lines.append("")
        lines.append(f"pair, {kind}: {a.enemy_id} (r {a.radius:g}, w {a.weight:g}) and "
                     f"{b.enemy_id} (r {b.radius:g}, w {b.weight:g}); distance (px) at "
                     + ", ".join(f"{t:g}" for t in CHECKPOINTS) + " s, then the peak knock")
        for hz in rates:
            s, peak = bench.pair_trial(kind, hz, min(seconds, 1.0))
            dist = " ".join(_fmt(at(s, t), 7, 2) for t in CHECKPOINTS)
            lines.append(f"  {hz:>4} Hz {dist}  | peak {peak:6.1f} px/s")
    return "\n".join(lines)


def _vs(v, ref, digits: int = 3) -> str:
    """`v` and its share of the reference rate's value, for the journal."""
    if v is None:
        return "never"
    return f"{v:.{digits}f} ({100.0 * v / ref:.0f} %)" if ref else f"{v:.{digits}f}"


def markdown(bench: Bench, rates, seconds: float, reference: float = 62) -> str:
    """The journal's tables: the crowd's times and each pair's distance at
    the end of its trial, each beside its share of the `reference` rate's."""
    crowd = {hz: bench.crowd_trial(hz, seconds) for hz in rates}
    ref = crowd.get(reference) or bench.crowd_trial(reference, seconds)
    ref_t = [time_to(ref, f) for f in FRACTIONS]
    head = " | ".join(f"t{int(f * 100)}" for f in FRACTIONS)
    lines = [f"| Rate | {head} |", "|---" * (len(FRACTIONS) + 1) + "|"]
    for hz in rates:
        cells = " | ".join(_vs(time_to(crowd[hz], f), r)
                           for f, r in zip(FRACTIONS, ref_t))
        lines.append(f"| {hz} Hz | {cells} |")
    pair_s = min(seconds, 1.0)
    lines.append("")
    lines.append(f"| Rate | equal: distance at {pair_s:g} s | equal: peak knock "
                 f"| lopsided: distance at {pair_s:g} s | lopsided: peak knock |")
    lines.append("|---|---|---|---|---|")
    refs = {k: bench.pair_trial(k, reference, pair_s) for k in ("equal", "lopsided")}
    for hz in rates:
        cells = []
        for kind in ("equal", "lopsided"):
            s, peak = bench.pair_trial(kind, hz, pair_s)
            rs, rpeak = refs[kind]
            cells += [_vs(s[-1][1], rs[-1][1], 1), _vs(peak, rpeak, 0)]
        lines.append(f"| {hz} Hz | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def parse(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rates", type=float, nargs="+", default=list(RATES),
                    help="frame rates to step at, Hz")
    ap.add_argument("--seconds", type=float, default=2.0,
                    help="game time per crowd trial (pairs run at most 1 s)")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--live", type=int, default=LIVE, help="bodies in the crowd")
    ap.add_argument("--pack", type=float, default=PACK,
                    help="px round the hero the crowd is packed into")
    ap.add_argument("--markdown", action="store_true",
                    help="the journal's tables, each value beside its share "
                         "of the 62 Hz one")
    args = ap.parse_args(argv)
    if args.seconds <= 0.0 or any(r <= 0.0 for r in args.rates):
        ap.error("--seconds and --rates must be positive")
    return args


def main(argv=None) -> int:
    args = parse(argv)
    bench = Bench(args.seed, args.live, args.pack)
    rates = [int(r) if float(r).is_integer() else r for r in args.rates]
    print((markdown if args.markdown else report)(bench, rates, args.seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
