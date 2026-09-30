"""What a frame-time trace of real play says (SYS-010,
`frame_trace_journal.md`).

    python main.py --trace                                  # play; the path is logged
    python -m tools.benchmarks.trace_report traces/frames-....csv
    python -m tools.benchmarks.trace_report                 # the newest trace beside the save

It answers, for the frames spent in play (rows whose update reached the
run's `PlayingState`, the end banner's wait phase included; the pause menu,
the level-up cards, the loading screen and the menus are counted apart, and
so is a play frame that opened an overlay, because its draw is that
overlay's first, SYS-010.D6):

* how many frames' work (update + draw) was over the budget, and whether
  those were update-bound or draw-bound;
* how many frames ran long (period over 1.5 x the budget, 25 ms: half a
  frame late at the 60 fps target), how many of those had work over budget,
  and what took most of
  each one: the update, the draw, the present (`flip`: the upload and the
  vsync wait), the frame cap's wait in `clock.tick`, or the rest of the
  period (the input, the music, the trace's own sample and writes);
* p50 / p90 / p99 / max of the period, of each of those parts and of the
  work;
* the same by crowd size (enemies alive), with how many were in view and
  how many particles were live;
* the worst seconds of each run, by frames over budget.

Each row's `frame_ms` is that frame's own period, and its state is the
deepest one its update reached (`systems/frame_trace.py`, SYS-010.D2 and
D3); `shown` is what it drew last. A long frame that the wait took most
of is the frame cap's sleep overshooting: most often the OS timer being
coarse for a hidden or silent process (SYS-011), or a busy machine; the
report says so when it sees one.

`summarise` is pure and does the arithmetic; `format` prints it. A row that
cannot be read (a trace cut off mid-row, a blank or non-numeric field) is
skipped and counted, never a traceback: a cut or overlong row, a blank
or non-numeric time, a negative number, crowd fields neither all set nor
all blank, or a row the recorder cannot write (timed parts that add up to
more than the period, a count that is not whole, more bodies in view than
alive, an `opened` other than 0 or 1). The recorder never quotes, so a stray quote spoils one row, not
the rest. An empty file, one that is not UTF-8 text a CSV reader can take,
or one whose header lacks a column this report reads, is refused by name.
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

from systems.frame_trace import BUDGET_MS, COLUMNS
from tools.benchmarks.stats import percentile

PLAY = "PlayingState"
LONG = 1.5                      # a frame this many budgets long ran late
CROWDS = ((0, 24), (25, 49), (50, 99), (100, 149), (150, None))
# The parts of a period, in the order a tie between them is settled. `other`
# is what the four timed spans leave: the input, the music, the sample.
PARTS = ("update_ms", "draw_ms", "present_ms", "wait_ms", "other_ms")

# The columns every row must carry as finite numbers; the crowd columns may
# be blank (a frame outside a run), never missing, and all but the run
# clock are whole counts.
_TIMES = ("t", "frame_ms", "update_ms", "draw_ms", "present_ms", "wait_ms")
_COUNTS = ("live", "in_view", "particles", "numbers", "run_time")
_WHOLE = ("live", "in_view", "particles", "numbers")
# The four timed parts are disjoint spans of the period, each written to a
# thousandth of a millisecond: their sum is over it by rounding alone.
_ROUNDING_MS = 0.005


class NotATrace(ValueError):
    """The file is empty, or its header lacks columns this report reads."""


def _number(v: str) -> float:
    x = float(v)
    if not math.isfinite(x) or x < 0.0:
        raise ValueError(v)
    return x


def load(path) -> tuple[list[dict], int]:
    """`(rows, skipped)`: the trace's readable rows, numbers as floats (the
    crowd all None outside a run), and how many rows could not be read.
    Raises `NotATrace` for an empty file, a file that is not UTF-8 CSV, or
    a header that lacks a column."""
    try:
        return _load(path)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise NotATrace(f"it cannot be read as a CSV trace ({type(exc).__name__}: {exc})") from exc


def _load(path) -> tuple[list[dict], int]:
    out, skipped = [], 0
    with open(path, newline="", encoding="utf-8-sig") as f:   # -sig: a BOM an editor added
        # QUOTE_NONE: the recorder never quotes, so a stray quote stays in
        # its own row instead of swallowing every row after it.
        reader = csv.DictReader(f, quoting=csv.QUOTE_NONE)
        if not reader.fieldnames or not any(c.strip() for c in reader.fieldnames):
            empty = not f.read().strip()
            raise NotATrace("the file is empty" if empty else "its first line is not a header")
        missing = [c for c in COLUMNS if c not in reader.fieldnames]
        if missing:
            raise NotATrace(f"its header has no {', '.join(missing)} "
                            "(a trace from an older recorder?)")
        for row in reader:
            try:
                if None in row or None in row.values():     # too many or too few fields
                    raise ValueError("cut")
                if row["opened"] not in ("0", "1"):
                    raise ValueError("opened")
                rec = {"state": row["state"], "shown": row["shown"], "opened": row["opened"] == "1"}
                for k in _TIMES:
                    rec[k] = _number(row[k])
                if sum(rec[k] for k in PARTS[:4]) > rec["frame_ms"] + _ROUNDING_MS:
                    raise ValueError("parts")                 # more than the period holds
                blank = [row[k] == "" for k in _COUNTS]
                if any(blank) and not all(blank):           # a crowd half written
                    raise ValueError("crowd")
                for k in _COUNTS:
                    rec[k] = None if row[k] == "" else _number(row[k])
                if rec["live"] is not None:
                    if any(rec[k] != int(rec[k]) for k in _WHOLE):
                        raise ValueError("count")             # a count that is not whole
                    if rec["in_view"] > rec["live"]:
                        raise ValueError("in view")
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue
            rec["other_ms"] = max(0.0, rec["frame_ms"] - sum(rec[k] for k in PARTS[:4]))
            out.append(rec)
    return out, skipped


def _spread(values: list) -> tuple:
    return tuple(percentile(sorted(values), q) for q in (0.5, 0.9, 0.99)) + (max(values, default=0.0),)


def _median(values: list) -> float:
    return percentile(sorted(values), 0.5)


def cause(r: dict) -> str:
    """The part that took most of a frame's period (the first on a tie)."""
    return max(PARTS, key=lambda k: r[k])


def opened(rows: list[dict], i: int) -> bool:
    """Did play frame `i` open an overlay: its update changed the top state
    (the recorder's `opened`) and it ended showing something other than the
    run. Its draw is that overlay's first (the level-up cards build theirs
    anew each time), so it is not the run's draw (SYS-010.D6)."""
    return rows[i]["opened"] and rows[i]["shown"] != PLAY


def summarise(rows: list[dict], budget: float = BUDGET_MS) -> dict:
    in_play = [i for i, r in enumerate(rows) if r["state"] == PLAY]
    opening = {i for i in in_play if opened(rows, i)}
    play = [rows[i] for i in in_play if i not in opening]
    work = [r["update_ms"] + r["draw_ms"] for r in play]
    over = [r for r, w in zip(play, work) if w > budget]
    long = [(r, w) for r, w in zip(play, work) if r["frame_ms"] > LONG * budget]
    s = {
        "budget": budget,
        "frames": len(rows),
        "over_all": sum(1 for r in rows if r["update_ms"] + r["draw_ms"] > budget),
        "seconds": rows[-1]["t"] - rows[0]["t"] if len(rows) > 1 else 0.0,
        "states": Counter(r["state"] for r in rows),
        "play": len(play),
        "opened": Counter(rows[i]["shown"] for i in opening),
        "opened_over": sum(1 for i in opening
                           if rows[i]["update_ms"] + rows[i]["draw_ms"] > budget),
        "opened_update_bound": sum(1 for i in opening
                                   if rows[i]["update_ms"] + rows[i]["draw_ms"] > budget
                                   and rows[i]["update_ms"] >= rows[i]["draw_ms"]),
        "over": len(over),
        "long": len(long),
        "long_over": sum(1 for _r, w in long if w > budget),
        "causes": Counter(cause(r) for r, _w in long),
        "spread": {k: _spread([r[k] for r in play]) for k in ("frame_ms",) + PARTS},
        "work": _spread(work),
        "update_bound": sum(1 for r in over if r["update_ms"] >= r["draw_ms"]),
        "draw_bound": sum(1 for r in over if r["update_ms"] < r["draw_ms"]),
    }
    crowds = []
    for lo, hi in CROWDS:
        pick = [(r, w) for r, w in zip(play, work)
                if r["live"] is not None and r["live"] >= lo and (hi is None or r["live"] <= hi)]
        ws = sorted(w for _r, w in pick)
        crowds.append({"lo": lo, "hi": hi, "frames": len(pick),
                       "over": sum(1 for w in ws if w > budget),
                       "work": (percentile(ws, 0.5), percentile(ws, 0.9)),
                       "in_view": _median([r["in_view"] for r, _w in pick]),
                       "particles": _median([r["particles"] for r, _w in pick])})
    s["crowds"] = crowds
    # Seconds of each run, so two runs' seconds never merge. The runs are
    # told apart on every row, not only the play rows: a new run starts
    # when the run clock goes back or after frames outside any run (the
    # menus).
    runs, run_no, last, outside = [], 0, None, True
    for r in rows:
        if r["run_time"] is None:
            outside = True
            runs.append(None)
            continue
        if outside or r["run_time"] < last - 0.5:
            run_no += 1
        outside, last = False, r["run_time"]
        runs.append(run_no)
    seconds = defaultdict(lambda: {"over": 0, "worst": 0.0, "live": 0})
    for i, (r, n) in enumerate(zip(rows, runs)):
        if n is None or r["state"] != PLAY or i in opening:
            continue
        w = r["update_ms"] + r["draw_ms"]
        sec = seconds[(n, int(r["run_time"]))]
        sec["over"] += w > budget
        sec["worst"] = max(sec["worst"], w)
        sec["live"] = max(sec["live"], int(r["live"] or 0))
    s["runs"] = run_no
    worst = sorted(seconds.items(), key=lambda kv: (-kv[1]["over"], -kv[1]["worst"], kv[0]))
    s["worst_seconds"] = [(k, v) for k, v in worst[:5] if v["over"] > 0]
    return s


def _pct(n: int, d: int) -> str:
    return f"{100.0 * n / d:.1f} %" if d else "-"


def format(s: dict) -> str:
    b = s["budget"]
    lines = [
        f"frames {s['frames']} over {s['seconds']:.1f} s; budget {b:.2f} ms (the 60 fps target)",
        "  by state: " + ", ".join(f"{k} {v}" for k, v in s["states"].most_common()),
        f"  every frame: work over budget {s['over_all']} ({_pct(s['over_all'], s['frames'])})",
        f"in play ({PLAY}): {s['play']} frames",
    ]
    if s["opened"]:
        names = ", ".join(f"{k} {v}" for k, v in s["opened"].most_common())
        lines.append(f"  counted apart: {sum(s['opened'].values())} play frame(s) that opened an "
                     f"overlay ({names}); their draw is the overlay's first; "
                     f"work over budget {s['opened_over']}, update-bound "
                     f"{s['opened_update_bound']}, draw-bound "
                     f"{s['opened_over'] - s['opened_update_bound']}")
    if not s["play"]:
        lines.append("  no frames in play")
        return "\n".join(lines)
    lines += [
        (f"  work (update + draw) over budget: {s['over']} ({_pct(s['over'], s['play'])}); "
         f"update-bound {s['update_bound']}, draw-bound {s['draw_bound']}"),
        (f"  long frames (period over {LONG:g} x budget): "
         f"{s['long']} ({_pct(s['long'], s['play'])}); {s['long_over']} with work over budget"),
    ]
    if s["long"]:
        lines.append("    what took most of each: " + ", ".join(
            f"{k[:-3]} {s['causes'].get(k, 0)}" for k in PARTS))
    if s["causes"].get("wait_ms"):
        lines.append("    a long frame the wait took most of is the frame cap's sleep "
                     "overshooting, not the game's work:")
        lines.append("    most often the OS timer being coarse for a hidden or silent "
                     "process (a headless run), or a busy machine")
    lines.append("  p50 / p90 / p99 / max ms:")
    for label, key in (("period", "frame_ms"),) + tuple((k[:-3], k) for k in PARTS):
        lines.append(f"    {label:8s} " + " / ".join(f"{v:.2f}" for v in s["spread"][key]))
    lines.append("    work     " + " / ".join(f"{v:.2f}" for v in s["work"]))
    lines.append("  by crowd (enemies alive): frames, work p50 / p90, over budget, "
                 "in view p50, particles p50")
    for c in s["crowds"]:
        span = f"{c['lo']}+" if c["hi"] is None else f"{c['lo']}-{c['hi']}"
        if c["frames"]:
            lines.append(f"    {span:8s} {c['frames']:7d}  {c['work'][0]:.2f} / {c['work'][1]:.2f}  "
                         f"{c['over']} ({_pct(c['over'], c['frames'])})  "
                         f"{c['in_view']:.0f}  {c['particles']:.0f}")
    if s["worst_seconds"]:
        lines.append(f"  worst seconds ({s['runs']} run(s), run clock): "
                     "frames over, worst work, most alive")
        for (run_no, sec), v in s["worst_seconds"]:
            lines.append(f"    run {run_no} {sec:5d} s   {v['over']:3d}   {v['worst']:.2f} ms   {v['live']}")
    return "\n".join(lines)


def newest(*save_paths) -> Path | None:
    """The newest trace beside any of these saves, or None."""
    found = [f for sp in save_paths
             for f in (Path(sp).parent / "traces").glob("frames-*.csv")]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("trace", nargs="?", help="a trace file (default: the newest beside the save)")
    args = ap.parse_args(argv)
    path = args.trace
    if path is None:
        # Beside the source tree's save, and beside the packaged game's
        # (%LOCALAPPDATA%\DeathliteGame): the newest of either.
        from game import save
        path = newest(save.DEFAULT_PATH, save.user_save_path())
        if path is None:
            ap.error("no trace given, and none beside the save: play with `python main.py --trace`")
    if not Path(path).is_file():
        ap.error(f"no such trace: {path}")
    try:
        rows, skipped = load(path)
    except NotATrace as exc:
        ap.error(f"{path} is not a trace this report reads: {exc}")
    print(f"trace: {path}")
    if skipped:
        print(f"  {skipped} row(s) could not be read and were skipped")
    if not rows:
        print("  no readable frames")
        return 0
    print(format(summarise(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
