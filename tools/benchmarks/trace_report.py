"""What a frame-time trace of real play says (SYS-010,
`frame_trace_journal.md`).

    python main.py --trace                                  # play; the path is logged
    python -m tools.benchmarks.trace_report traces/frames-....csv
    python -m tools.benchmarks.trace_report                 # the newest trace beside the save

It answers, for the frames spent in play (`PlayingState`; the pause menu,
the level-up cards and the menus are counted apart):

* how many frames' work (update + draw) was over the budget, and how many
  frames ran long enough to miss a refresh (period over 1.5 x the budget);
* p50 / p90 / p99 / max of the period, the update, the draw, the present
  and the work;
* the same by crowd size (enemies alive);
* whether the frames over budget were update-bound or draw-bound;
* the worst seconds of the run, by frames over budget.

`summarise` is pure and does the arithmetic; `format` prints it.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from systems.frame_trace import BUDGET_MS

PLAY = "PlayingState"
LONG = 1.5                      # a frame this many budgets long missed a refresh
CROWDS = ((0, 24), (25, 49), (50, 99), (100, 149), (150, None))


def percentile(values: list, q: float) -> float:
    """Nearest-rank percentile of `values` (0.0 for none), as the stress
    harness reports them."""
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def load(path) -> list[dict]:
    """The trace's rows, numbers as floats (or None where blank)."""
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rec = {"state": row["state"]}
            for k, v in row.items():
                if k != "state":
                    rec[k] = float(v) if v != "" else None
            out.append(rec)
    return out


def _spread(values: list) -> tuple:
    return tuple(percentile(values, q) for q in (0.5, 0.9, 0.99)) + (max(values, default=0.0),)


def summarise(rows: list[dict], budget: float = BUDGET_MS) -> dict:
    # A frame just after a state change carries the change in its period
    # (the first frame of a run includes the world's build), so it is left
    # out of the period figures; its own update and draw still count.
    steady = [i == 0 or rows[i - 1]["state"] == r["state"] for i, r in enumerate(rows)]
    play = [r for r in rows if r["state"] == PLAY]
    play_steady = [r for r, ok in zip(rows, steady) if ok and r["state"] == PLAY]
    work = [r["update_ms"] + r["draw_ms"] for r in play]
    over = [r for r, w in zip(play, work) if w > budget]
    s = {
        "budget": budget,
        "frames": len(rows),
        "seconds": rows[-1]["t"] - rows[0]["t"] if len(rows) > 1 else 0.0,
        "states": Counter(r["state"] for r in rows),
        "play": len(play),
        "transitions": len(play) - len(play_steady),
        "over": len(over),
        "long": sum(1 for r in play_steady if r["frame_ms"] > LONG * budget),
        "spread": {"frame_ms": _spread([r["frame_ms"] for r in play_steady]),
                   **{k: _spread([r[k] for r in play])
                      for k in ("update_ms", "draw_ms", "present_ms")}},
        "work": _spread(work),
        "update_bound": sum(1 for r in over if r["update_ms"] >= r["draw_ms"]),
        "draw_bound": sum(1 for r in over if r["update_ms"] < r["draw_ms"]),
    }
    crowds = []
    for lo, hi in CROWDS:
        pick = [(r, w) for r, w in zip(play, work)
                if r["live"] is not None and r["live"] >= lo and (hi is None or r["live"] <= hi)]
        ws = [w for _r, w in pick]
        crowds.append({"lo": lo, "hi": hi, "frames": len(pick),
                       "over": sum(1 for w in ws if w > budget),
                       "work": (percentile(ws, 0.5), percentile(ws, 0.9))})
    s["crowds"] = crowds
    seconds = defaultdict(lambda: {"over": 0, "worst": 0.0, "live": 0})
    for r, w in zip(play, work):
        if r["run_time"] is None:
            continue
        sec = seconds[int(r["run_time"])]
        sec["over"] += w > budget
        sec["worst"] = max(sec["worst"], w)
        sec["live"] = max(sec["live"], int(r["live"] or 0))
    worst = sorted(seconds.items(), key=lambda kv: (-kv[1]["over"], -kv[1]["worst"], kv[0]))
    s["worst_seconds"] = [(k, v) for k, v in worst[:5] if v["over"] > 0]
    return s


def _pct(n: int, d: int) -> str:
    return f"{100.0 * n / d:.1f} %" if d else "-"


def format(s: dict) -> str:
    b = s["budget"]
    lines = [
        f"frames {s['frames']} over {s['seconds']:.1f} s; budget {b:.2f} ms (60 Hz)",
        "  by state: " + ", ".join(f"{k} {v}" for k, v in s["states"].most_common()),
        f"in play ({PLAY}): {s['play']} frames",
    ]
    if not s["play"]:
        lines.append("  no frames in play")
        return "\n".join(lines)
    lines += [
        f"  work (update + draw) over budget: {s['over']} ({_pct(s['over'], s['play'])})",
        f"  long frames (period over {LONG:g} x budget, a missed refresh): "
        f"{s['long']} ({_pct(s['long'], s['play'] - s['transitions'])}; "
        f"{s['transitions']} frame(s) just after a state change left out of the period)",
        "  p50 / p90 / p99 / max ms:",
    ]
    for label, key in (("period", "frame_ms"), ("update", "update_ms"), ("draw", "draw_ms"),
                       ("present", "present_ms")):
        lines.append(f"    {label:8s} " + " / ".join(f"{v:.2f}" for v in s["spread"][key]))
    lines.append("    work     " + " / ".join(f"{v:.2f}" for v in s["work"]))
    lines.append(f"  over budget: update-bound {s['update_bound']}, draw-bound {s['draw_bound']}")
    lines.append("  by crowd (enemies alive): frames, work p50 / p90, over budget")
    for c in s["crowds"]:
        span = f"{c['lo']}+" if c["hi"] is None else f"{c['lo']}-{c['hi']}"
        if c["frames"]:
            lines.append(f"    {span:8s} {c['frames']:7d}  {c['work'][0]:.2f} / {c['work'][1]:.2f}  "
                         f"{c['over']} ({_pct(c['over'], c['frames'])})")
    if s["worst_seconds"]:
        lines.append("  worst seconds of the run (run clock): frames over, worst work, most alive")
        for sec, v in s["worst_seconds"]:
            lines.append(f"    {sec:5d} s   {v['over']:3d}   {v['worst']:.2f} ms   {v['live']}")
    return "\n".join(lines)


def newest(save_path) -> Path | None:
    """The newest trace beside the save, or None."""
    folder = Path(save_path).parent / "traces"
    found = sorted(folder.glob("frames-*.csv"), key=lambda p: p.stat().st_mtime)
    return found[-1] if found else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("trace", nargs="?", help="a trace file (default: the newest beside the save)")
    args = ap.parse_args(argv)
    path = args.trace
    if path is None:
        from game import save
        path = newest(save.DEFAULT_PATH)
        if path is None:
            ap.error("no trace given, and none beside the save: play with `python main.py --trace`")
    print(f"trace: {path}")
    print(format(summarise(load(path))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
