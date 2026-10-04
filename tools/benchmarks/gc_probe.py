"""Are the frame time's spikes garbage collections? (RND-010.3,
`crowd_performance_plan.md` appendix A.2.)

The stress harness's build (seed 35, the hero jittering; with `--pack`
packed before the 60-frame warm-up, as the appendix did, where the
harness packs after it), update plus draw
timed per frame, with a `gc.callbacks` hook marking which frames held a
collection, of which generation and for how long; then the same with the
run's objects frozen out of the collector (`gc.freeze()`) and the gen-2
threshold raised, the plan's step 4.2.

    python -m tools.benchmarks.gc_probe                      # 200 live, spread
    python -m tools.benchmarks.gc_probe --pack               # packed round the hero
    SDL_VIDEODRIVER=windows python -m tools.benchmarks.gc_probe --pack

Headless by default (in bash; in PowerShell set `$env:SDL_VIDEODRIVER =
"windows"` first). Unlike the appendix, which built 200 at a run clock of
300 s where the director seats 175, the default run clock is 400 s, so
200 are seated; the harness's shortfall line says when fewer were. Each
mode builds its own run. The collector's state (the callback, the
freeze, the thresholds) is put back after each mode, so nothing leaks
into what runs next in the same process.
"""
from __future__ import annotations

import argparse
import gc
import os
import random
import time
from contextlib import contextmanager

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tools.benchmarks import spawn_stress as S
from tools.benchmarks.stats import percentile

# The plan's 4.2: the gen-2 threshold raised once the run is frozen out.
FROZEN_THRESHOLDS = (700, 10, 1000)


@contextmanager
def collections():
    """Records `(frame, generation, ms)` for every collection while open,
    the frame read from `events.frame` (set by the caller). The callback
    comes off on leaving, whatever happens."""
    events: list = []
    events_frame = [0]
    started = [0.0]

    def callback(phase, info):
        if phase == "start":
            started[0] = time.perf_counter()
        else:
            events.append((events_frame[0], info["generation"],
                           (time.perf_counter() - started[0]) * 1000.0))

    gc.callbacks.append(callback)
    try:
        yield events, events_frame
    finally:
        gc.callbacks.remove(callback)


@contextmanager
def frozen():
    """The run's objects out of the collector and the gen-2 threshold
    raised (`FROZEN_THRESHOLDS`); thresholds and the freeze put back on
    leaving."""
    before = gc.get_threshold()
    gc.collect()
    gc.freeze()
    gc.set_threshold(*FROZEN_THRESHOLDS)
    try:
        yield
    finally:
        gc.unfreeze()
        gc.set_threshold(*before)


def measure(ps, frames: int, warm: int = 60, jitter: float = 24.0) -> dict:
    """Update plus draw timed per frame over `frames` frames after `warm`,
    the hero jittering round where it stands. Returns the frame times and
    the collections seen while timing, by generation."""
    import pygame
    rng = random.Random(1)
    home = pygame.Vector2(ps.player.pos)
    surface = pygame.display.get_surface()

    def step():
        ps.player.pos.update(home.x + rng.uniform(-jitter, jitter),
                             home.y + rng.uniform(-jitter, jitter))
        ps.update(1 / 60)
        ps.draw(surface)

    for _ in range(warm):
        step()
    times = []
    with collections() as (events, at):
        for i in range(frames):
            at[0] = i
            t0 = time.perf_counter()
            step()
            times.append((time.perf_counter() - t0) * 1000.0)
    ps.player.pos.update(home)
    counts, ms = [0, 0, 0], [0.0, 0.0, 0.0]
    frames_hit = [set(), set(), set()]
    for f, g, m in events:
        counts[g] += 1
        ms[g] += m
        frames_hit[g].add(f)
    return {"times": times, "counts": counts, "ms": ms, "frames": frames_hit}


def report(label: str, live: int, result: dict) -> str:
    """One line: the frame times, then how many collections of each
    generation ran while timing and their summed ms."""
    s = sorted(result["times"])
    return (f"{label}: live {live}  p50 {percentile(s, 0.5):.2f}  p99 {percentile(s, 0.99):.2f}  "
            f"max {s[-1]:.2f} ms  |  collections gen0/1/2 {result['counts']}, "
            f"summed ms {[round(v, 1) for v in result['ms']]}")


def scene(args, save_path: str | None):
    from game import config
    _game, ps = S.build(args.seed, args.live, 0, args.elapsed, config.ENEMY_LOD_SKIP,
                        save_path=save_path)
    short = S.shortfall(ps, args.live, args.elapsed)
    if short:
        print(short)
    if args.pack:
        S.cascade_setup(ps, prime=False)
    return ps


def parse(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=35)
    ap.add_argument("--live", type=int, default=200, help="as spawn_stress --live")
    ap.add_argument("--elapsed", type=float, default=400.0,
                    help="the run clock; the director's cap is 100 + 5 per 20 s, "
                         "so --live N needs (N - 100) * 4")
    ap.add_argument("--frames", type=int, default=600, help="frames timed per mode")
    ap.add_argument("--pack", action="store_true", help="the crowd packed round the hero")
    args = ap.parse_args(argv)
    if args.frames < 1 or args.live < 1:
        ap.error("--frames and --live must be positive")
    return args


def main(argv=None, save_path: str | None = None) -> int:
    args = parse(argv)
    ps = scene(args, save_path)
    print(report("default collector", len(ps.enemies), measure(ps, args.frames)))
    ps = scene(args, save_path)
    with frozen():
        print(report(f"frozen, thresholds {FROZEN_THRESHOLDS}", len(ps.enemies),
                     measure(ps, args.frames)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
