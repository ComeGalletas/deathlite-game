"""Every figure RND-010.7's results quote, from the raw outputs here:
`python derived.py`, from anywhere.

Sitting 1 (headless, ABBA): `main` (before) against the branch with the
skip built (after, `6e0bd09`), at 150 / 300 and 250 / 600 packed, quiet:
`draw_leads` (`s1_leads_*`) and the draw by layer (`s1_layers_*`).
`shapes_<count>_<round>` (`shapes.sh`, `walk_shapes.py`): the unshaded
bodies split by their index cells, and the walk's shapes timed against the
walk in one process each, two runs a count. The sitting's after side calls
the subset `subset: shade walk, unshaded`, its name when it ran.
"""
import re
from pathlib import Path

D = Path(__file__).parent
COUNTS = (150, 250)
mean = lambda v: sum(v) / len(v)


def text(name: str) -> str:
    return (D / name).read_text(encoding="utf-8", errors="replace")


def compare(before, after, unit="", digits=2):
    d = mean(after) - mean(before)
    f = f"{{:.{digits}f}}"
    return (f"before {' / '.join(f.format(x) for x in before)}{unit}  after "
            f"{' / '.join(f.format(x) for x in after)}{unit}  change {d:+.{digits}f} "
            f"({min(after) - max(before):+.{digits}f} to {max(after) - min(before):+.{digits}f})")


print(text("s1_meta.txt").splitlines()[0])
for n in COUNTS:
    print(f"\n== {n}: after (the skip) against before (main) ==")
    leads = {s: [text(f"s1_leads_{n}_{s}_{r}.txt") for r in "ab"] for s in ("before", "after")}
    walk = {s: [float(re.search(r"^    shade walk\s+([\d.]+) us a call", t, re.MULTILINE).group(1)) for t in ts]
            for s, ts in leads.items()}
    head = re.search(r"(\d+) drawn, (\d+) of them shaded", leads["before"][0])
    print(f"    {head.group(1)} drawn, {head.group(2)} of them shaded")
    print("    shade walk, us a call  " + compare(walk["before"], walk["after"]))
    sub = [float(re.search(r"subset: shade walk, unshaded\s+([\d.]+) us a call", t).group(1))
           for t in leads["after"]]
    print(f"    the unshaded alone, after: {' / '.join(f'{x:.2f}' for x in sub)} us a call")
    lay = {s: [text(f"s1_layers_{n}_{s}_{r}.txt") for r in "ab"] for s in ("before", "after")}
    row = {s: [float(re.search(r"^    enemies/shade\s+([\d.]+) /", t, re.MULTILINE).group(1)) for t in ts]
           for s, ts in lay.items()}
    bare = {s: [float(re.search(r"drawn without the timers: draw p50 ([\d.]+)", t).group(1)) for t in ts]
            for s, ts in lay.items()}
    print("    enemies/shade p50 ms   " + compare(row["before"], row["after"]))
    print("    bare draw p50 ms       " + compare(bare["before"], bare["after"]))

print("\n== the walk's shapes, one process each, two runs a count, over the unshaded bodies ==")
for n in COUNTS:
    runs = [text(f"shapes_{n}_{r}.txt") for r in "ab"]
    split = re.search(r"(\d+) unshaded bodies of (\d+) drawn: (\d+) with every index cell empty, "
                      r"(\d+) touching an occupied one; the (\d+) px grid returns early for (\d+)", runs[0])
    assert all(split.group(0) in t for t in runs), "the two runs split the bodies alike"
    print(f"{n}: {split.group(1)} unshaded of {split.group(2)} drawn; {split.group(3)} with every index cell "
          f"empty, {split.group(4)} touching an occupied one; the {split.group(5)} px grid returns early "
          f"for {split.group(6)}")
    us = [{m.group(1): float(m.group(2)) for m in re.finditer(r"^    (\w+)\s+([\d.]+) us a call", t, re.MULTILINE)}
          for t in runs]
    ms = [{m.group(1): float(m.group(2)) for m in re.finditer(r"^    (\w+)\s+[\d.]+ us a call, ([\d.]+) ms a frame",
                                                             t, re.MULTILINE)} for t in runs]
    for name in ("before", "any_skip", "one_cell", "fine", "bare"):
        print(f"    {name:9s} {' / '.join(f'{u[name]:.2f}' for u in us)} us a call")
    room = [m["before"] - m["bare"] for m in ms]
    saved = [m["before"] - m["fine"] for m in ms]
    print(f"    room above the floor {' / '.join(f'{x:.3f}' for x in room)} ms a frame; "
          f"the fine skip saves {' / '.join(f'{x:.3f}' for x in saved)} ms a frame")
