"""Every derived figure the journal quotes, from the raw sitting files.

Sitting 7 (`bb92e30`) prints the groups as each frame's sum; sittings 4 to
6 do not, so for them (and, to compare, for sitting 7 too) the terrain and
the crowd's part are sums of their rows' p50s.
"""
import re
from pathlib import Path

D = Path(__file__).parent
TERRAIN = ("ground", "water", "scenery", "scenery_list")
CROWD = ("enemies", "enemies/shade", "ghost", "world")
SITTINGS = (("s4", (150, 250)), ("s5", (150, 200, 250)), ("s6", (150, 200, 250)),
            ("s7", (150, 200, 250)))
# A sitting 7 run whose terrain (each frame's sum, p50) is above this ran
# in a slow patch: the terrain is the same work in every run, and sitting
# 7's other runs and sitting 4's all put it at 6.25 to 6.54 ms.
SLOW_TERRAIN = 7.0


def row(t, name):
    m = re.search(rf"^    {re.escape(name)}\s+([\d.]+) /.*?([\d.]+)$", t, re.MULTILINE)
    return float(m.group(1)), float(m.group(2))


def group(t, name):
    m = re.search(rf"^    \({re.escape(name)}\)\s+([\d.]+) /\s+([\d.]+)", t, re.MULTILINE)
    return float(m.group(1)) if m else None


def run(prefix, n, x):
    t = (D / f"{prefix}_{n}{x}.txt").read_text(encoding="utf-8", errors="replace")
    bare = float(re.search(r"without the timers: draw p50 ([\d.]+)", t).group(1))
    terrain = sum(row(t, r)[0] for r in TERRAIN)
    crowd = sum(row(t, r)[0] for r in CROWD)
    enemies, calls = row(t, "enemies")
    tc = re.search(r"timers add ([+\-\d.]+) ms at p50, ([\d.]+) timed calls a frame, ([\d.]+) us", t)
    return {"bare": bare, "terrain": terrain, "crowd": crowd, "ratio": crowd / terrain,
            "g_terrain": group(t, "terrain"), "g_crowd": group(t, "crowd"),
            "g_ratio": group(t, "crowd / terrain"), "us": 1000 * enemies / calls,
            "added": float(tc.group(1)), "per_call": float(tc.group(3))}


def span(vals, fmt=".2f"):
    return f"{min(vals):{fmt}} to {max(vals):{fmt}}"


R = {(p, n, x): run(p, n, x) for p, sizes in SITTINGS for n in sizes for x in "ab"}
S7 = {(n, x): R["s7", n, x] for n in (150, 200, 250) for x in "ab"}
quiet = {k: v for k, v in S7.items() if v["g_terrain"] <= SLOW_TERRAIN}
slow = sorted(k for k in S7 if k not in quiet)
print("sitting 7 slow-patch runs:", slow, " terrains",
      [S7[k]["g_terrain"] for k in slow], " quiet terrains", span([v["g_terrain"] for v in quiet.values()]))
print()
print("== sitting 7, each frame's sum (p50) ==")
for n in (150, 200, 250):
    q = [v for (m, _), v in quiet.items() if m == n]
    a = [v for (m, _), v in S7.items() if m == n]
    print(f"{n}: quiet runs {len(q)}: terrain {span([v['g_terrain'] for v in q])}, crowd "
          f"{span([v['g_crowd'] for v in q])}, bare {span([v['bare'] for v in q])} "
          f"({span([100 * v['bare'] / 16.67 for v in q], '.0f')} % of budget), us/enemy "
          f"{span([v['us'] for v in q], '.1f')}; all runs ratio {span([v['g_ratio'] for v in a], '.3f')}")
qc = {n: [v["g_crowd"] for (m, _), v in quiet.items() if m == n] for n in (150, 200, 250)}
print(f"quiet crowd growth 147 to 224 in view: {max(qc[250]) / min(qc[150]):.2f} to "
      f"{min(qc[250]) / max(qc[150]):.2f} times")
gr = [S7[250, x]["g_ratio"] / S7[150, y]["g_ratio"] for x in "ab" for y in "ab"]
print(f"ratio growth 147 to 224, sitting 7 runs: {span(gr)}")
diff = [abs(v[g] / v[s] - 1) for v in S7.values() for g, s in (("g_terrain", "terrain"), ("g_crowd", "crowd"))]
print(f"sitting 7: each frame's sum against the sum of p50s, at most {100 * max(diff):.1f} % apart")
print(f"sitting 7 timers: added {span([v['added'] for v in S7.values()])} ms, "
      f"{span([v['per_call'] for v in S7.values()])} us a call")
print()
print("== every sitting, sums of p50s ==")
for (p, n, x), v in R.items():
    print(f"{p} {n}{x}: bare {v['bare']:.2f}  terrain {v['terrain']:.2f}  crowd {v['crowd']:.2f}  "
          f"ratio {v['ratio']:.3f}")
for n in (150, 200, 250):
    rs = [v["ratio"] for (p, m, _), v in R.items() if m == n]
    who = sorted({p for (p, m, _) in R if m == n})
    print(f"ratio at {n} over {who}: {span(rs, '.3f')}, spread {100 * (max(rs) / min(rs) - 1):.1f} %")
g = [R[p, 250, x]["ratio"] / R[p, 150, x]["ratio"] for p, _ in SITTINGS for x in "ab"]
print("growth 150 to 250 (ratio of ratios), each sitting's a and b:", [round(v, 2) for v in g])
s4t = [R["s4", n, x]["terrain"] for n in (150, 250) for x in "ab"]
print("sitting 4 terrain (sum of p50s):", span(s4t), " sitting 7 quiet runs (sum of p50s):",
      span([v["terrain"] for v in quiet.values()]))
print()
print("== the probes, sitting 7 ==")
for n in (150, 250):
    t = (D / f"s7_nested_{n}.txt").read_text(encoding="utf-8", errors="replace")
    whole = float(re.search(r"nested wrappers add ([+\-\d.]+) ms to the whole", t).group(1))
    m = re.search(r"and ([+\-\d.]+) ms to enemies with its nested rows: ([\d.]+) enemies drawn a "
                  r"frame, ([+\-\d.]+) us an enemy", t)
    rows, calls, us = float(m.group(1)), float(m.group(2)), float(m.group(3))
    crowds = [S7[n, x]["g_crowd"] for x in "ab" if (n, x) in quiet]
    lo, hi = min(rows, whole), max(rows, whole)
    print(f"nested {n}: rows {rows:+.2f} whole {whole:+.2f} ({calls} drawn, {us} us an enemy); against "
          f"the quiet runs' crowd {span(crowds)}: {100 * lo / max(crowds):.1f} % to "
          f"{100 * hi / min(crowds):.1f} % as timed, {100 * lo / (max(crowds) - lo):.1f} % to "
          f"{100 * hi / (min(crowds) - hi):.1f} % untimed")
    own = [v["us"] - us for (m_, _), v in quiet.items() if m_ == n] + \
          [v["us"] for (m_, _), v in quiet.items() if m_ == n]
    print(f"   own draw per enemy, quiet runs at {n}, all of the {us} us off or none: {span(own, '.1f')}")
    b = (D / f"s7_bias_{n}.txt").read_text(encoding="utf-8", errors="replace")
    print("   bias:", re.search(r"the median difference lies in .*", b).group(0))
print()
print("== the sittings' logs ==")
for p in ("s5", "s6", "s7"):
    meta = (D / f"{p}_meta.txt").read_text(encoding="utf-8", errors="replace")
    loads = [int(v) for v in re.findall(r"cpu load (\d+)%", meta)]
    print(f"{p} cpu load before each run (and at the end, where logged): {span(loads, 'd')} %")
    parts = meta.split("--- top processes by CPU time at the end")
    if len(parts) == 2:
        def cpu(text):
            out = {}
            for name, secs in re.findall(r"^(\S+)\s+([\d,]+)$", text, re.MULTILINE):
                out[name] = max(out.get(name, 0.0), float(secs.replace(",", ".")))
            return out
        start, end = cpu(parts[0]), cpu(parts[1])
        gained = sorted(((end[k] - start[k], k) for k in start.keys() & end.keys()), reverse=True)
        print("   CPU seconds gained over the sitting, top processes in both lists: "
              + ", ".join(f"{k} {d:.0f}" for d, k in gained))
