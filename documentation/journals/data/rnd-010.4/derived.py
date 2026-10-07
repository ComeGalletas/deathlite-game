"""Every figure RND-010.4's results quote, from the raw outputs here:
`python derived.py`, from anywhere.

Sitting 1 ran `main` (before) against this branch (after, the wash cache an
LRU of 1536) in one sitting, in ABBA order (before a, after a, after b,
before b) at 150, 200 and 250 alive packed, first with the hero fighting
(`--elements`), then quiet. Printed per kind and count: each run's
headline p50s and tails, and after against before (the two afters' mean
less the two befores' mean, and the range from the lower after less the
higher before to the higher after less the lower before); then the layer
rows that move most; then the load before each step.
"""
import re
from pathlib import Path

D = Path(__file__).parent
COUNTS = (150, 200, 250)
KINDS = ("fight", "quiet")
mean = lambda v: sum(v) / len(v)


def text(name: str) -> str:
    return (D / name).read_text(encoding="utf-8", errors="replace")


def headline(t: str) -> dict:
    draw = re.search(r"draw   p50 ([\d.]+)\s+p90 ([\d.]+)\s+p99 ([\d.]+)\s+max ([\d.]+) ms\s+\|\s+in view "
                     r"p50 (\d+)", t)
    frame = re.search(r"update \+ draw\s+p50 ([\d.]+)\s+p90 ([\d.]+)\s+p99 ([\d.]+)\s+max ([\d.]+) ms\s+\|\s+"
                      r"over 16.67 ms: (\d+) / (\d+)", t)
    update = re.search(r"frames \d+: p50 ([\d.]+)", t)
    bare = re.search(r"drawn without the timers: draw p50 ([\d.]+)", t)
    return {"bare": float(bare.group(1)), "draw p90": float(draw.group(2)),
            "draw p99": float(draw.group(3)), "view": int(draw.group(5)),
            "frame": float(frame.group(1)), "frame p99": float(frame.group(3)),
            "over": int(frame.group(5)), "update": float(update.group(1))}


def layers(t: str) -> dict:
    rows = {m.group(1): (float(m.group(2)), float(m.group(3))) for m in re.finditer(
        r"^    ([a-z_/]+)\s+([\d.]+) /\s+[\d.]+ /\s+([\d.]+)\s+[\d.]+ %\s+[\d.]+$", t, re.MULTILINE)}
    table = t.split("draw by layer", 1)[1].split("    (all layers)", 1)[0]
    lines = [ln for ln in table.splitlines()[1:] if ln.startswith("    ") and ln.strip()]
    assert len(lines) == len(rows), f"{len(lines)} layer lines, {len(rows)} parsed"
    return rows


def compare(before: list, after: list) -> str:
    d = mean(after) - mean(before)
    return (f"before {' / '.join(f'{x:6.2f}' for x in before)}  after "
            f"{' / '.join(f'{x:6.2f}' for x in after)}  change {d:+6.2f} "
            f"({min(after) - max(before):+.2f} to {max(after) - min(before):+.2f})")


meta = text("s1_meta.txt")
print(meta.splitlines()[0])
for kind in KINDS:
    print(f"\n== {kind}: after (the LRU) against before (main), p50 ms unless named ==")
    for n in COUNTS:
        runs = {side: [text(f"s1_{kind}_{n}_{side}_{r}.txt") for r in "ab"] for side in ("before", "after")}
        h = {side: [headline(t) for t in ts] for side, ts in runs.items()}
        print(f"{n}: in view before {'/'.join(str(x['view']) for x in h['before'])}, after "
              f"{'/'.join(str(x['view']) for x in h['after'])}")
        for key in ("bare", "draw p90", "draw p99", "update", "frame", "frame p99"):
            print(f"    {key:9s} " + compare([x[key] for x in h["before"]], [x[key] for x in h["after"]]))
        print(f"    over 16.67 ms (of 300): before {'/'.join(str(x['over']) for x in h['before'])}, after "
              f"{'/'.join(str(x['over']) for x in h['after'])}")
        lay = {side: [layers(t) for t in ts] for side, ts in runs.items()}
        names = set().union(*lay["before"], *lay["after"])
        change = {k: mean([x.get(k, (0, 0))[0] for x in lay["after"]])
                  - mean([x.get(k, (0, 0))[0] for x in lay["before"]]) for k in names}
        for k in sorted(names, key=lambda k: abs(change[k]), reverse=True)[:4]:
            print(f"    layer {k:20s} " + compare([x.get(k, (0, 0))[0] for x in lay["before"]],
                                                  [x.get(k, (0, 0))[0] for x in lay["after"]]))
        others = {k: v for k, v in change.items() if k not in ("enemies", "(all layers)", "draw")}
        top = max(others, key=lambda k: abs(others[k]))
        print(f"    every layer but enemies moves {abs(others[top]):.2f} ms or less (largest: {top})")
        if kind == "fight" and n == 150:
            # Against RND-010.3's sitting 5, the same scene at the same count
            # on the code before this change, a day earlier.
            s5 = [headline((D.parent / "rnd-010.3" / f"r5_fight_150{r}.txt")
                           .read_text(encoding="utf-8"))["bare"] for r in "ab"]
            here = [x["bare"] for x in h["before"] + h["after"]]
            print(f"    150's fight bare draw here {min(here):.2f} to {max(here):.2f}, against RND-010.3's "
                  f"sitting 5 {min(s5):.2f} to {max(s5):.2f}: {min(here) - max(s5):+.2f} to "
                  f"{max(here) - min(s5):+.2f} ms above")

print("\n== the cache replay at 250, on the branch: the wash cache ==")
wash_block = text("s1_caches_250_after.txt").split("  wash: ", 1)[1].split("\n  tint: ", 1)[0]
for line in ("  wash: " + wash_block).splitlines():
    if re.match(r"  wash: |    cap  1536: |    cap   512: ", line):
        print(line)

print("\n== the load before each step ==")
for k, v in re.findall(r"=== (.+?)\s+cpu load (\d+)%", meta):
    print(f"    {k}: {v}%")
