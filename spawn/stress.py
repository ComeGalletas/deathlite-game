"""The crowd stress harness: how long does a frame take with the spawn
master's worst plausible population?

Spawn master S7. Builds a real dev run, seats `--live` enemies in the
active zone through the master's own placement, banks `--dormant` records
in the other islands, then runs `--frames` frames of `PlayingState.update`
with the hero jittering (so the flow field's drift trigger fires as it
would in play) and reports the update time's p50 / p90 / p99 / max.

    python -m spawn.stress                         # 100 live, 400 dormant, 1200 frames
    python -m spawn.stress --live 200 --lod 2      # a heavier crowd, half-rate LOD
    python -m spawn.stress --profile               # cProfile's top entries too

Headless: the dummy SDL drivers are set before pygame is imported, so
this runs anywhere the tests do. Numbers land in
`journals/spawn_master_journal.md`, not in a test -- a timing assertion
in the suite would only ever be flaky.
"""
from __future__ import annotations

import argparse
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _percentile(sorted_vals: list, q: float) -> float:
    if not sorted_vals:
        return 0.0
    i = min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1))))
    return sorted_vals[i]


def build(seed: int, live: int, dormant: int, elapsed: float, lod: int):
    """A dev run at `elapsed` seconds with the population asked for."""
    import pygame
    from game import config
    from game.game import Game
    from game.states.loading_state import LoadingState
    from spawn.population import DormantEnemy
    from tests.boot import settle

    game = Game()
    game.state_machine.change(LoadingState(game), seed=seed, dev=True)
    ps = settle(game)
    ps.player.invulnerable = True
    ps._dev_no_attack = True                     # the crowd survives the run
    ps.stats["time"] = elapsed
    m = ps.spawn.master
    m.frozen = True                              # the population is ours to set
    m.update(0.0)                                # settle the zone
    config.ENEMY_LOD_SKIP = lod
    ids = list(ps.content.spawn_tables.phase_at(0.5)["types"])
    # Live bodies, seated on the zone's own spawn points with a spread.
    # They used to go through `m.spawn_at` with no position, which is
    # placement's job -- and placement's 3 s point cooldown meant a tight
    # loop got a few dozen bodies and refusals after that, so the harness
    # silently measured a third of the crowd it was asked for. Placement
    # has its own tests; this is a population builder.
    import random as _random
    rng = _random.Random(seed)
    pts = ps.game_map.layout.spawn_points
    zone = [p for p in pts if p.room_id in m.active] or list(pts)
    i = 0
    while len(ps.enemies) < live and i < live * 20:
        p = zone[i % len(zone)]
        eid = ids[i % len(ids)]
        i += 1
        spot = pygame.Vector2(p.x + rng.uniform(-60, 60), p.y + rng.uniform(-60, 60))
        if ps.game_map.is_walkable(spot, ps.content.enemy(eid)["radius"]):
            m.spawn_at(eid, spot, owner="stress")
    # Dormant records: banked directly, spread over the other islands.
    lay = ps.game_map.layout
    others = [r for r in lay.rooms if r.id not in m.active] or lay.rooms
    for k in range(dormant):
        room = others[k % len(others)]
        c = room.center
        rec = DormantEnemy(ids[k % len(ids)], c.x + (k % 7) * 40, c.y + (k // 7 % 5) * 40,
                           10.0, 10.0, 0.0, 90.0, owner="stress", room_id=room.id)
        m.population.dormant.setdefault(room.id, []).append(rec)
    m.frozen = False
    return game, ps


def run(ps, frames: int, jitter: float = 24.0, dt: float = 1 / 60) -> list:
    """Frame times in milliseconds for `frames` updates with the hero
    jittering by up to `jitter` px each frame."""
    import random
    import pygame
    rng = random.Random(1)
    home = pygame.Vector2(ps.player.pos)
    times = []
    for _ in range(frames):
        ps.player.pos.update(home.x + rng.uniform(-jitter, jitter),
                             home.y + rng.uniform(-jitter, jitter))
        t0 = time.perf_counter()
        ps.update(dt)
        times.append((time.perf_counter() - t0) * 1000.0)
    return times


def report(times: list, ps) -> str:
    s = sorted(times)
    m = ps.spawn.master
    return (f"frames {len(s)}: p50 {_percentile(s, 0.5):.2f}  p90 {_percentile(s, 0.9):.2f}  "
            f"p99 {_percentile(s, 0.99):.2f}  max {s[-1]:.2f} ms  |  live {len(ps.enemies)} "
            f"dormant {m.population.total_dormant} recycled {m.recycled}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=35)
    ap.add_argument("--live", type=int, default=100)
    ap.add_argument("--dormant", type=int, default=400)
    ap.add_argument("--frames", type=int, default=1200)
    ap.add_argument("--elapsed", type=float, default=300.0)
    ap.add_argument("--lod", type=int, default=None,
                    help="behaviour tick divisor for out-of-aggro, off-view enemies "
                         "(default: config.ENEMY_LOD_SKIP)")
    ap.add_argument("--profile", action="store_true")
    args = ap.parse_args(argv)
    from game import config
    lod = args.lod if args.lod is not None else config.ENEMY_LOD_SKIP
    game, ps = build(args.seed, args.live, args.dormant, args.elapsed, lod)
    run(ps, 60)                                      # warm the caches
    if args.profile:
        import cProfile
        import pstats
        prof = cProfile.Profile()
        prof.enable()
        times = run(ps, args.frames)
        prof.disable()
        print(report(times, ps))
        pstats.Stats(prof).sort_stats("cumulative").print_stats(28)
    else:
        times = run(ps, args.frames)
        print(f"seed {args.seed} lod {lod}  " + report(times, ps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
