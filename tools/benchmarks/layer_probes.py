"""Two probes on the draw-by-layer tool's own error (RND-010.2,
`crowd_draw_journal.md`, "Its limits").

    SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes bias --live 150 --elapsed 300
    SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes nested --live 250 --elapsed 600

Both build the scene `spawn_stress --pack` times (`packed_scene`: the same
build, the boss held back, the 60-frame warm-up, the crowd packed round
the hero), so their figures sit beside a `--layers` run's.

* `bias`: does the `--layers` headline (its bare frames) report what the
  plain `--render` headline does? Paired blocks over one crowd: `--plain`
  frames of the plain `--render` run and `--layered` frames of
  `--layers`, the plain first in even blocks and second in odd ones
  (ABBA, so `--blocks` is even). The crowd drifts slowly (summons arrive,
  bodies sleep): pairing cancels the drift between blocks, and the
  alternating order cancels a steady drift inside them. It compares the two commands as they
  stand, so the alternation and the garbage collection `--layers` adds
  after every frame are covered together; two effects that cancelled
  would not show. Prints the plain and the bare draw p50 over all blocks
  and the per-block bare minus plain p50: their own p50 (nearest-index,
  `stats.percentile`: the 9th of 16 blocks), their range and how many
  blocks had the bare frames slower. (`da7ab7e` printed that p50 as
  "median".)
* `nested`: what the wrappers nested inside `enemies` (`shade`, `hpbar`,
  `marks`) cost. Frames rotate four ways (`Rotate`): bare, every timer,
  every timer but those three, the root alone. Prints each kind's whole
  draw p50 as `spawn_stress.run` times it (the timers' cost included) and,
  for the two timed kinds, `enemies` with its nested rows and `world`.

Headless without `SDL_VIDEODRIVER=windows`, like the harness: the dummy
driver's surface, not the cost on screen. The prefix above is bash's (Git
Bash on Windows); in PowerShell, `$env:SDL_VIDEODRIVER = "windows"` first.
"""
from __future__ import annotations

import argparse
import gc
import math

from tools.benchmarks import draw_layers as DL
from tools.benchmarks import spawn_stress as S
from tools.benchmarks.stats import percentile

# The wrappers `enemies` opens per enemy drawn.
NESTED = frozenset({"shade", "hpbar", "marks"})
KINDS = ("bare", "all", "no_nested", "root")


def _p50(values) -> float:
    return percentile(sorted(values), 0.5)


def packed_scene(seed: int, live: int, dormant: int, elapsed: float,
                 save_path: str | None = None):
    """`spawn_stress.main`'s `--pack` scene, up to the timing: built, the
    display and any shortfall printed, warmed for 60 drawn frames, the
    crowd packed round the hero. Returns `(game, ps)`. `save_path` as
    `spawn_stress.build` (the tests' fresh save)."""
    from game import config
    game, ps = S.build(seed, live, dormant, elapsed, config.ENEMY_LOD_SKIP, save_path=save_path)
    print(S.display_line(ps))
    short = S.shortfall(ps, live, elapsed)
    if short:
        print(short)
    S.run(ps, 60, render=True)
    S.cascade_setup(ps, prime=False)
    return game, ps


def bias(ps, blocks: int, plain: int, layered: int) -> dict:
    """`blocks` pairs of a plain `--render` run of `plain` frames and a
    `--layers` run of `layered` frames. Returns the plain draws, the bare
    frames' draws, each side's enemies in view and each block's bare minus
    plain p50.

    Every part starts with the hero back on one anchor, where it stood
    when `bias` was called: `spawn_stress.run` jitters round wherever the
    hero is and leaves it at its last jittered spot, with the jitter
    reseeded each call, so part after part would walk the hero (and the
    view) steadily across the map."""
    out = {"plain": [], "bare": [], "plain_view": [], "bare_view": [], "diffs": []}
    anchor = ps.player.pos.copy()

    def plain_part():
        ps.player.pos.update(anchor)
        _t, draws, in_view = S.run(ps, plain, render=True)
        return draws, in_view

    def layered_part():
        ps.player.pos.update(anchor)
        _t, ldraws, lview, alternate = S.layered_run(ps, layered)
        return DL.bare_frames(alternate, ldraws, lview)

    for block in range(blocks):
        # ABBA: plain first in the even blocks, layered first in the odd
        # ones, so a drift inside a block (the crowd grows as summons
        # arrive) falls on each side alike over every two blocks, instead
        # of always against whichever side runs second.
        if block % 2 == 0:
            (draws, view), (bare, bview) = plain_part(), layered_part()
        else:
            bare, bview = layered_part()
            draws, view = plain_part()
        out["plain"] += draws
        out["bare"] += bare
        out["plain_view"] += view
        out["bare_view"] += bview
        out["diffs"].append(_p50(bare) - _p50(draws))
    ps.player.pos.update(anchor)
    return out


def sign_interval(n: int) -> tuple[int, float] | None:
    """The sign test's interval for a median from `n` paired differences:
    `(k, coverage)`, the interval running from the k-th smallest to the
    k-th largest, with the largest k (so the narrowest interval) that
    still covers at least 95 %. None when `n` is too small for any."""
    k, coverage = None, 0.0
    for j in range(1, n // 2 + 1):
        tail = sum(math.comb(n, i) for i in range(j)) / 2 ** n
        if 1 - 2 * tail < 0.95:
            break
        k, coverage = j, 1 - 2 * tail
    return (k, coverage) if k is not None else None


def format_bias(result: dict) -> str:
    diffs = sorted(result["diffs"])
    slower = sum(1 for d in diffs if d > 0)
    lines = [
        (f"  bias: {len(diffs)} blocks; draw p50 plain {_p50(result['plain']):.2f} ms "
        f"({len(result['plain'])} frames, in view p50 {_p50(result['plain_view'])}), bare "
        f"{_p50(result['bare']):.2f} ms ({len(result['bare'])} frames, in view p50 "
        f"{_p50(result['bare_view'])})"),
        (f"  per block, bare minus plain p50: p50 {_p50(diffs):+.2f} ms, from "
        f"{diffs[0]:+.2f} to {diffs[-1]:+.2f}; bare slower in {slower} of {len(diffs)}"),
        "  each block, sorted: " + " ".join(f"{d:+.2f}" for d in diffs),
    ]
    interval = sign_interval(len(diffs))
    if interval is None:
        lines.append("  too few blocks for a sign-test interval on the median")
    else:
        k, coverage = interval
        lines.append(f"  the median difference lies in {diffs[k - 1]:+.2f} to {diffs[-k]:+.2f} ms "
                     f"({100 * coverage:.1f} % sign-test interval, the {k}th smallest to the "
                     f"{k}th largest)")
    return "\n".join(lines)


class Rotate:
    """`after_draw` for `spawn_stress.run`: the frames rotate through
    `KINDS`, the first bare. After each frame the timer that was on reads
    its frame and comes off, the young garbage is collected with no timer
    on (as `draw_layers.Alternate` does), and the next kind's timer goes
    on. `kinds` is the kind of each frame drawn."""

    def __init__(self, ps) -> None:
        self.ps = ps
        root_only = frozenset(label for label, *_ in DL.LAYERS if label != "draw")
        self.timers = {"all": DL.LayerTimer(), "no_nested": DL.LayerTimer(skip=NESTED),
                       "root": DL.LayerTimer(skip=root_only)}
        self.kinds: list[str] = []
        self._on = None

    def __call__(self) -> None:
        self.kinds.append(KINDS[len(self.kinds) % len(KINDS)])
        if self._on is not None:
            self._on.frame()
            self._on.uninstall()
            self._on = None
        gc.collect(0)
        following = KINDS[len(self.kinds) % len(KINDS)]
        if following != "bare":
            self._on = self.timers[following].install(self.ps)

    def close(self) -> None:
        """Take the timer off, whatever frame the run stopped on."""
        if self._on is not None:
            self._on.uninstall()
            self._on = None


def nested(ps, frames: int) -> dict:
    """`frames` frames rotating through `KINDS`. Returns each kind's whole
    draw times and, for `all` and `no_nested`, each frame's `enemies` with
    its nested rows and its `world`."""
    rotate = Rotate(ps)
    try:
        _t, draws, _v = S.run(ps, frames, render=True, after_draw=rotate)
    finally:
        rotate.close()
    out = {"draw": {k: [d for d, kind in zip(draws, rotate.kinds, strict=True) if kind == k]
                    for k in KINDS}}
    for k in ("all", "no_nested"):
        rows = rotate.timers[k].frames
        out[f"{k}_enemies"] = [sum(v for key, v in f.items()
                                   if key == "enemies" or key.startswith("enemies/")) for f in rows]
        out[f"{k}_world"] = [f.get("world", 0.0) for f in rows]
    out["enemies_calls"] = rotate.timers["all"].calls_per_frame("enemies")
    return out


def format_nested(result: dict) -> str:
    d = {k: _p50(v) for k, v in result["draw"].items()}
    lines = [(f"  nested: whole draw p50 by kind ({len(result['draw']['bare'])} frames each): "
             f"bare {d['bare']:.2f}, all timers {d['all']:.2f}, all but the nested "
             f"{d['no_nested']:.2f}, root alone {d['root']:.2f} ms")]
    for k, name in (("all", "all timers"), ("no_nested", "all but the nested")):
        lines.append(f"    {name:20s} enemies with its nested rows p50 "
                     f"{_p50(result[f'{k}_enemies']):.2f} ms, world {_p50(result[f'{k}_world']):.2f} ms")
    lines.append(f"  the nested wrappers add {d['all'] - d['no_nested']:+.2f} ms to the whole "
                 f"draw, every timer {d['all'] - d['bare']:+.2f} ms, at p50")
    calls = result["enemies_calls"]
    rows = _p50(result["all_enemies"]) - _p50(result["no_nested_enemies"])
    per_enemy = 1000.0 * rows / calls if calls else 0.0
    lines.append(f"  and {rows:+.2f} ms to enemies with its nested rows: {calls:.1f} enemies "
                 f"drawn a frame, {per_enemy:+.2f} us an enemy")
    return "\n".join(lines)


def parse(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="probe", required=True)
    for name, text in (("bias", "paired plain and --layers blocks over one crowd"),
                       ("nested", ("frames rotating bare, all timers, all but the nested, "
                                  "the root alone"))):
        p = sub.add_parser(name, help=text)
        p.add_argument("--seed", type=int, default=35, help="the world's seed")
        p.add_argument("--live", type=int, required=True,
                       help="as spawn_stress --live; needs --elapsed (N - 100) * 4")
        p.add_argument("--elapsed", type=float, required=True,
                       help="the run clock in seconds, as spawn_stress --elapsed")
        p.add_argument("--dormant", type=int, default=400,
                       help="enemy records banked on the other islands, as spawn_stress")
        if name == "bias":
            p.add_argument("--blocks", type=int, default=16,
                           help="pairs of a plain and a layered block, an even number: the order alternates")
            p.add_argument("--plain", type=int, default=40,
                           help="frames of each plain --render block")
            p.add_argument("--layered", type=int, default=80,
                           help="frames of each --layers block, half of them bare")
        else:
            p.add_argument("--frames", type=int, default=400,
                           help="frames in all, rotating bare, all timers, all but the "
                                "nested, the root alone")
    args = ap.parse_args(argv)
    if args.probe == "bias" and (args.blocks < 2 or args.blocks % 2 or args.plain < 1
                                 or args.layered < 2):
        ap.error("bias needs an even --blocks of 2 or more (the order alternates), --plain "
                 "of 1 or more and --layered of 2 or more")
    if args.probe == "nested" and args.frames < len(KINDS):
        ap.error(f"nested needs --frames {len(KINDS)} or more, one of each kind")
    return args


def main(argv=None, save_path: str | None = None) -> int:
    args = parse(argv)
    _game, ps = packed_scene(args.seed, args.live, args.dormant, args.elapsed, save_path)
    if args.probe == "bias":
        print(format_bias(bias(ps, args.blocks, args.plain, args.layered)))
    else:
        print(format_nested(nested(ps, args.frames)))
    print(f"  boss at the end: {S.boss_state(ps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
