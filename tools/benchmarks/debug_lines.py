"""What the F1 overlay's lines cost a frame (RND-010.5, `crowd_draw_journal.md`).

    python -m tools.benchmarks.debug_lines --live 150 --elapsed 300
    python -m tools.benchmarks.debug_lines --live 250 --elapsed 600 --elements

`PlayingState`'s update fills the F1 overlay's metrics (`dev_flags.report_debug`)
every frame. Since RND-010.5 it does that only while the overlay is shown, so
with F1 off the whole of this cost is what the change removes. The scene is
`layer_probes.packed_scene`'s (`--elements`: the hero fighting, as
`spawn_stress --elements`). `report_debug` is then called `--rounds` times on
it, timed per call, and the median and p90 are printed. `active_auras`, the
one line that walks the whole crowd, is then timed alone the same way, and
its median printed as the part of the whole it accounts for.

A CPU-only cost: no pixels are drawn, so headless is the right place to time
it, and the display driver does not matter.
"""
from __future__ import annotations

import argparse
import statistics
import time

from tools.benchmarks import layer_probes as LP


def per_call(fn, rounds: int) -> list[float]:
    """Microseconds for each of `rounds` calls of `fn`."""
    out = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1e6)
    return out


def measure(ps, rounds: int) -> dict:
    """`report_debug`'s cost on `ps`, and `active_auras`'s alone (the line that
    walks the crowd), in microseconds a call."""
    run = ps.run
    whole = per_call(lambda: ps.dev.report_debug(ps), rounds)
    auras = per_call(lambda: run.elements.active_auras(run.enemies, run.stats["time"]), rounds)
    return {"whole": whole, "auras": auras, "alive": len(run.enemies)}


def report(result: dict) -> str:
    med = lambda v: statistics.median(v)
    return (f"  report_debug: {med(result['whole']):.1f} us a call (p90 "
            f"{sorted(result['whole'])[int(0.9 * (len(result['whole']) - 1))]:.1f}), "
            f"{med(result['whole']) / 1000:.3f} ms a frame; of it active_auras "
            f"{med(result['auras']):.1f} us; {result['alive']} alive, {len(result['whole'])} calls")


def parse(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=35, help="the world's seed")
    ap.add_argument("--live", type=int, required=True,
                    help="as spawn_stress --live; needs --elapsed (N - 100) * 4")
    ap.add_argument("--elapsed", type=float, required=True, help="the run clock in seconds")
    ap.add_argument("--dormant", type=int, default=400, help="enemy records on the other islands")
    ap.add_argument("--elements", action="store_true", help="the hero fighting, as spawn_stress --elements")
    ap.add_argument("--rounds", type=int, default=2000, help="calls timed")
    args = ap.parse_args(argv)
    if args.rounds < 1:
        ap.error("--rounds must be 1 or more")
    return args


def main(argv=None, save_path: str | None = None) -> int:
    args = parse(argv)
    _game, ps = LP.packed_scene(args.seed, args.live, args.dormant, args.elapsed, save_path,
                                elements=args.elements)
    print(report(measure(ps, args.rounds)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
