"""A model of the browser loop's pacing: a capped `clock.tick` against the
page's `requestAnimationFrame` (BLD-003).

This models what a `clock.tick(fps)` cap adds on top of a loop the display
already paces, display by display, so the trade-off in
`journals/web_frame_time_journal.md` can be regenerated rather than copied:

    python -m tools.benchmarks.raf_pacing                     # the journal's table
    python -m tools.benchmarks.raf_pacing --hz 60,144 --work 8

It is a model, not a measurement. What it assumes:

* **The tick is pygame-ce's `clock_tick_base`** (`src_c/time.c`): the
  frame's length is `int(1000 / fps)` whole ms (16 at 60), the wait is that
  less the whole ms since the last tick on SDL's integer clock, and the
  wait is `SDL_Delay`. Without Asyncify (unconfirmed for pygbag's
  runtime), `SDL_Delay` spins the page's thread for that long; that time
  is reported as `spin`.
* **One step per refresh**, because pygbag resumes `Game.run_async` after
  `await asyncio.sleep(0)` from its `requestAnimationFrame` stepper
  (measured in Chrome, BLD-003.6: steps land on whole refreshes, and the
  capped menu ran the 62.5 fps this model predicts). A step (tick, then
  `work` ms of update and draw) that ends between two refreshes resumes on
  the next one; a step longer than a period skips the refreshes it overran.
* **No noise.** Refreshes are exact and the work is constant.
* **Phase.** Where the refreshes fall against SDL's whole-ms clock moves
  the spin a little (not the fps), so `table` sweeps `PHASES` offsets
  across one ms and reports the spin's range.
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass

# The rows `web_frame_time_journal.md` prints.
DISPLAYS_HZ = (60, 75, 90, 120, 144, 165)
WORK_MS = (5.0, 12.0)
# Refresh offsets against SDL's ms clock, as fractions of one ms. Only the
# offset within a millisecond matters: a whole-ms shift moves every floor
# alike.
PHASES = tuple(i / 20 for i in range(20))


@dataclass(frozen=True)
class Pacing:
    fps: float          # steps a second, steady state
    spin_ms: float      # ms a step spends waiting inside the tick


@dataclass(frozen=True)
class Row:
    hz: float
    work_ms: float
    capped_fps: float
    spin_lo: float      # the capped spin's range over PHASES
    spin_hi: float
    uncapped_fps: float


def simulate(hz: float, work_ms: float, cap_fps: int | None,
             steps: int = 6000, phase_ms: float = 0.0) -> Pacing:
    """Steady-state pacing of a loop stepped once per refresh of an `hz`
    display, doing `work_ms` a step, with `clock.tick(cap_fps)` at the top
    of each step (`None`: `tick()` with no cap). The refreshes fall at
    `phase_ms + k * period` on SDL's clock. The first half of the steps is
    warm-up and not counted."""
    period = 1000.0 / hz
    frame_ms = int(1000.0 / cap_fps) if cap_fps else 0
    t = phase_ms                  # real time, ms; the first refresh
    last_tick: int | None = None  # SDL's integer clock at the last tick
    starts: list[float] = []
    spins: list[float] = []
    for _ in range(steps):
        starts.append(t)
        spin = 0.0
        if frame_ms and last_tick is not None:
            delay = frame_ms - (math.floor(t) - last_tick)
            if delay > 0:
                spin = float(delay)
                t += spin
        last_tick = math.floor(t)
        spins.append(spin)
        t += work_ms
        t = phase_ms + math.ceil((t - phase_ms) / period - 1e-9) * period
    half = steps // 2
    span = starts[-1] - starts[half]
    return Pacing(fps=1000.0 * (steps - 1 - half) / span,
                  spin_ms=sum(spins[half:]) / (steps - half))


def row(hz: float, work_ms: float, cap_fps: int = 60) -> Row:
    """One display and work: the capped fps and spin range over `PHASES`,
    and the uncapped fps (which no phase moves)."""
    capped = [simulate(hz, work_ms, cap_fps, phase_ms=p) for p in PHASES]
    spins = [c.spin_ms for c in capped]
    return Row(hz, work_ms, capped[0].fps, min(spins), max(spins),
               simulate(hz, work_ms, None).fps)


def table(displays=DISPLAYS_HZ, works=WORK_MS, cap_fps: int = 60) -> list[Row]:
    return [row(hz, w, cap_fps) for hz in displays for w in works]


def markdown(rows) -> str:
    out = ["| Display | Work | Capped fps (spin ms / frame) | Uncapped fps |",
           "|---|---|---|---|"]
    for r in rows:
        spin = (f"{r.spin_lo:.1f}" if round(r.spin_lo, 1) == round(r.spin_hi, 1)
                else f"{r.spin_lo:.1f}-{r.spin_hi:.1f}")
        out.append(f"| {r.hz:g} Hz | {r.work_ms:g} ms | {r.capped_fps:.1f} ({spin}) "
                   f"| {r.uncapped_fps:.1f} |")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--hz", default=",".join(map(str, DISPLAYS_HZ)),
                    help="comma-separated display refresh rates")
    ap.add_argument("--work", default=",".join(f"{w:g}" for w in WORK_MS),
                    help="comma-separated ms of update + draw a step")
    ap.add_argument("--cap", type=int, default=60, help="the tick's fps cap")
    args = ap.parse_args(argv)
    hz = [float(x) for x in args.hz.split(",")]
    work = [float(x) for x in args.work.split(",")]
    print(markdown(table(hz, work, args.cap)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
