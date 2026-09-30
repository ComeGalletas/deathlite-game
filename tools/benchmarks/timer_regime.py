"""The frame cap's timer on Windows 11: does a hidden, silent game still
pace on the 1 ms timer?

SYS-011. `Clock.tick` sleeps through `SDL_Delay` (`Sleep()` on Windows),
and SDL asks for a 1 ms timer when it starts. Windows 11 may set that
request aside for a process that owns a window but is neither visible nor
audible; every sleep then rounds to the ~15.6 ms default and `tick(62)`
holds each frame at about 31 ms. `Game.__init__` asks Windows to always
honor the request (`game/display/native.py: honor_timer_resolution`).

This is the eval behind that fix, on the real thing: the real `Game` in a
real window (the windows driver) with no audio device (the dummy audio
driver, so nothing makes it audible), minimized, stepped by its own
`_step` on the menu. Three arms in one process, in this order:

* **managed:** the policy handed back to Windows, as before the fix. The
  control: it shows whether Windows applies the rule on this machine today.
* **honored:** `native.honor_timer_resolution()`, the very call
  `Game.__init__` makes. The fix: it must pace at the tick's own rate.
* **managed again:** handed back once more, so the stretch coming back
  shows the policy, and nothing else, is the switch.

Per arm: the median `SDL_Delay(1)` (the sleep the tick makes) read before
and after the frames, since Windows can change its mind mid-arm, and the
frame period and the tick's own wait, p50 and p90. An arm is in one regime
only when both sleep readings agree. Vsync is off by default, so a
minimized window's present (DWM holds it at ~30 ms, and the coarse timer
stretches that too) does not hide the tick; `--vsync` keeps the game's own
setting, where the tick never waits and the present carries the stretch.

    python -m tools.benchmarks.timer_regime
    python -m tools.benchmarks.timer_regime --seconds 8 --vsync

A window opens for a moment and minimizes itself. Windows only. Exit
status:

* 0: Windows set the request aside in a control arm, and the fix lifted it;
* 1: the fix failed (its call answered False, at startup or in the honored
  arm, or the honored arm did not pace on the 1 ms timer);
* 2: not Windows;
* 3: inconclusive. The honored arm paced right, but Windows applied its
  rule in neither control arm, so nothing showed the fix was needed; run
  it again.

Results: `documentation/journals/timer_resolution_journal.md`.
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import tempfile
import time

FINE_SLEEP_MS = 5.0        # SDL_Delay(1) under this: the 1 ms timer (it reads ~1.5)
COARSE_SLEEP_MS = 10.0     # over this: the ~15.6 ms default (it reads ~15.3)
CAP_PERIOD_MAX_MS = 20.0   # a frame the cap paces: ~16.6 ms; a stretched one ~31
SETTLE_S = 3.0             # after a minimize or a policy change, before measuring:
                           # Windows applies the rule within about a second, but
                           # not always within 1.5 s of the first minimize


class _TimedClock:
    """`Game.clock` with its `tick` timed: the frame cap's own wait."""

    def __init__(self, clock):
        self._clock = clock
        self.waits: list[float] = []

    def tick(self, fps=0):
        t = time.perf_counter()
        out = self._clock.tick(fps)
        self.waits.append((time.perf_counter() - t) * 1000.0)
        return out

    def __getattr__(self, name):
        return getattr(self._clock, name)


def _pctl(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def _sleep_median_ms(pygame, n: int = 15) -> float:
    samples = []
    for _ in range(n):
        t = time.perf_counter()
        pygame.time.wait(1)
        samples.append((time.perf_counter() - t) * 1000.0)
    return statistics.median(samples)


def _run_for(game, seconds: float) -> list[float]:
    periods = []
    t = time.perf_counter()
    end = t + seconds
    while time.perf_counter() < end:
        game._step()
        now = time.perf_counter()
        periods.append((now - t) * 1000.0)
        t = now
    return periods


def measure_arm(game, pygame, clock: _TimedClock, seconds: float) -> dict:
    """Settle, then step the game for `seconds` and read one arm."""
    _run_for(game, SETTLE_S)
    before = _sleep_median_ms(pygame)
    clock.waits.clear()
    periods = _run_for(game, seconds)
    waits = clock.waits[:len(periods)]
    after = _sleep_median_ms(pygame)
    return {
        "sleep_before": before, "sleep_after": after,
        "regime": regime(before) if regime(before) == regime(after) else "changed mid-arm",
        "frames": len(periods),
        "period_p50": statistics.median(periods), "period_p90": _pctl(periods, 0.9),
        "wait_p50": statistics.median(waits), "wait_p90": _pctl(waits, 0.9),
    }


def regime(sleep_ms: float) -> str:
    if sleep_ms < FINE_SLEEP_MS:
        return "1 ms timer"
    if sleep_ms > COARSE_SLEEP_MS:
        return "coarse (~15.6 ms)"
    return "unclear (a loaded machine?)"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seconds", type=float, default=5.0,
                        help="measured seconds per arm (default 5)")
    parser.add_argument("--vsync", action="store_true",
                        help="keep the game's vsync setting (default: off, to isolate the tick)")
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        print("timer_regime: Windows only (the rule and the policy are Windows 11's)")
        return 2
    # Set here, not at import, so importing this module (its test does) opens
    # no real window in that process.
    os.environ["SDL_VIDEODRIVER"] = "windows"    # a real window: the rule is about windows
    os.environ["SDL_AUDIODRIVER"] = "dummy"      # no audio device: nothing makes it audible

    import pygame

    from game import config
    from game.display import native
    from game.game import Game

    if not args.vsync:
        config.VSYNC = False
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game._start()
    clock = _TimedClock(game.clock)
    game.clock = clock
    print(f"driver={pygame.display.get_driver()} audio=dummy mixer={pygame.mixer.get_init()} "
          f"vsync={game.vsync} fps cap={config.FPS} timer_honored at start={game.timer_honored}")
    _run_for(game, 0.5)
    pygame.display.iconify()

    arms = [("managed", lambda: native._set_throttling(0, 0)),
            ("honored", native.honor_timer_resolution),
            ("managed again", lambda: native._set_throttling(0, 0))]
    results = {}
    for name, set_policy in arms:
        took = set_policy()
        results[name] = r = measure_arm(game, pygame, clock, args.seconds)
        r["policy_taken"] = took
        print(f"  {name:14s} SDL_Delay(1) {r['sleep_before']:5.2f} -> {r['sleep_after']:5.2f} ms "
              f"[{r['regime']}]  "
              f"frames {r['frames']:4d}  period p50 {r['period_p50']:5.2f} p90 {r['period_p90']:5.2f}  "
              f"tick wait p50 {r['wait_p50']:5.2f} p90 {r['wait_p90']:5.2f}", flush=True)
    game._close()

    control, passed, status = judge(results, game.vsync, game.timer_honored)
    honored = results["honored"]
    print(f"control: the rule {control} (whether Windows set the request aside "
          f"for this hidden, silent window; its call, not the game's)")
    print(f"honored: {'PASS' if passed else 'FAIL'} (Game's call took: {game.timer_honored}, "
          f"the arm's: {honored['policy_taken']}; SDL_Delay(1) {honored['sleep_before']:.2f} "
          f"-> {honored['sleep_after']:.2f} ms, frame p50 {honored['period_p50']:.2f} ms)")
    if status == 3:
        print("inconclusive: the fix was not needed this run; run it again")
    return status


def judge(results: dict, vsync: bool, honored_at_start: bool) -> tuple[str, bool, int]:
    """The control arms' verdict, whether the fix holds, and the exit
    status. The fix holds when the game's own call took at startup, the
    honored arm's call took, that arm sleeps on the 1 ms timer at both ends,
    and, with vsync off, its frame keeps the cap's own period. A pass counts
    (0) only when a control arm showed Windows applying its rule, since a
    pass with nothing to lift would hold with the fix deleted (3)."""
    coarse = [results[k]["regime"].startswith("coarse") for k in ("managed", "managed again")]
    control = ("REPRODUCED in both" if all(coarse) else
               "reproduced in one" if any(coarse) else "NOT reproduced")
    honored = results["honored"]
    passed = (honored_at_start and honored["policy_taken"]
              and honored["regime"] == "1 ms timer"
              and (vsync or honored["period_p50"] < CAP_PERIOD_MAX_MS))
    status = 1 if not passed else 0 if any(coarse) else 3
    return control, passed, status


if __name__ == "__main__":
    sys.exit(main())
