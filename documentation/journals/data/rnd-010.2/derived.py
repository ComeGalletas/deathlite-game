"""Every derived figure the journal quotes, from the raw sitting files."""
import re
from pathlib import Path

D = Path(__file__).parent
TERRAIN = ("ground", "water", "scenery", "scenery_list")
CROWD = ("enemies", "enemies/shade", "ghost", "world")


def row(t, name):
    m = re.search(rf"^    {re.escape(name)}\s+([\d.]+) /.*?([\d.]+)$", t, re.MULTILINE)
    return float(m.group(1)), float(m.group(2))


def run(prefix, n, x):
    t = (D / f"{prefix}_{n}{x}.txt").read_text(encoding="utf-8", errors="replace")
    bare = float(re.search(r"without the timers: draw p50 ([\d.]+)", t).group(1))
    terrain = sum(row(t, r)[0] for r in TERRAIN)
    crowd = sum(row(t, r)[0] for r in CROWD)
    enemies, calls = row(t, "enemies")
    tc = re.search(r"timers add ([+\-\d.]+) ms at p50, ([\d.]+) timed calls a frame, ([\d.]+) us", t)
    return {"bare": bare, "terrain": terrain, "crowd": crowd, "ratio": crowd / terrain,
            "us": 1000 * enemies / calls, "added": float(tc.group(1)), "per_call": float(tc.group(3))}


R = {}
for prefix, sizes in (("s4", (150, 250)), ("s5", (150, 200, 250)), ("s6", (150, 200, 250))):
    for n in sizes:
        for x in "ab":
            R[prefix, n, x] = run(prefix, n, x)
for k, v in R.items():
    print(k, {a: round(b, 3) for a, b in v.items()}, f"{100 * v['bare'] / 16.67:.0f} % of budget")
print()
for n in (150, 200, 250):
    rs = [v["ratio"] for (p, m, _), v in R.items() if m == n]
    print(f"ratio at {n}: {min(rs):.3f} to {max(rs):.3f}, spread {100 * (max(rs) / min(rs) - 1):.1f} %")
for p in ("s4", "s5", "s6"):
    for n in (150, 200, 250):
        if (p, n, "a") in R:
            a, b = R[p, n, "a"], R[p, n, "b"]
            print(p, n, f"a/b bare {100 * (b['bare'] / a['bare'] - 1):+.1f} %  ratio a/b "
                        f"{100 * (b['ratio'] / a['ratio'] - 1):+.1f} %")
g = [R[p, 250, x]["ratio"] / R[p, 150, x]["ratio"] for p in ("s4", "s5", "s6") for x in "ab"]
print("growth 150 to 250 (ratio of ratios):", [round(v, 2) for v in g])
s6t = [R["s6", n, x]["terrain"] for n in (150, 200, 250) for x in "ab"]
print("s6 terrain", [round(v, 2) for v in s6t])
s4t = [R["s4", n, x]["terrain"] for n in (150, 250) for x in "ab"]
est = [R[p, 200, x]["ratio"] * t for p in ("s5", "s6") for x in "ab" for t in (min(s4t), max(s4t))]
print("estimate crowd at 178 on sitting 4's terrain:", round(min(est), 2), "to", round(max(est), 2))
# The nested probe, sitting 6, read from its printouts.
NESTED = {}
for n in (150, 250):
    t = (D / f"s6_nested_{n}.txt").read_text(encoding="utf-8", errors="replace")
    whole = float(re.search(r"nested wrappers add ([+\-\d.]+) ms to the whole", t).group(1))
    m = re.search(r"and ([+\-\d.]+) ms to enemies with its nested rows: ([\d.]+) enemies drawn a "
                  r"frame, ([+\-\d.]+) us an enemy", t)
    NESTED[n] = (float(m.group(1)), whole, float(m.group(2)), float(m.group(3)))
for n, (rows, whole, calls, us) in NESTED.items():
    crowds = [R["s6", n, x]["crowd"] for x in "ab"]
    lo, hi = min(rows, whole), max(rows, whole)
    print(f"nested {n}: rows {rows} whole {whole} ({calls} drawn, {us} us): timed "
          f"{100 * lo / max(crowds):.1f} % to {100 * hi / min(crowds):.1f} %, untimed "
          f"{100 * lo / (max(crowds) - lo):.1f} % to {100 * hi / (min(crowds) - hi):.1f} % of the crowd "
          f"part {min(crowds):.2f} to {max(crowds):.2f}")
own = {p: [R[p, n, x]["us"] - NESTED[n][3] for n in (150, 250) for x in "ab"]
       + [R[p, n, x]["us"] for n in (150, 250) for x in "ab"] for p in ("s4", "s6")}
for p, v in own.items():
    print("own draw", p, round(min(v), 1), "to", round(max(v), 1), "us")
s4b = [R["s4", n, x]["bare"] for n in (150, 250) for x in "ab"]
s6b = {n: [R["s6", n, x]["bare"] for x in "ab"] for n in (150, 250)}
lows = [1 - R["s4", n, x]["bare"] / R["s6", n, y]["bare"] for n in (150, 250) for x in "ab" for y in "ab"]
print("s4 bare lower than s6 by", round(100 * min(lows), 1), "to", round(100 * max(lows), 1), "%")
print("s6 timers added", min(R["s6", n, x]["added"] for n in (150, 200, 250) for x in "ab"), "to",
      max(R["s6", n, x]["added"] for n in (150, 200, 250) for x in "ab"), "per call",
      min(R["s6", n, x]["per_call"] for n in (150, 200, 250) for x in "ab"), "to",
      max(R["s6", n, x]["per_call"] for n in (150, 200, 250) for x in "ab"))
meta = (D / "s6_meta.txt").read_text(encoding="utf-8", errors="replace")
dl = [float(v.replace(",", ".")) for v in re.findall(r"^deadlock\s+([\d,]+)", meta, re.MULTILINE)]
print("deadlock cpu seconds in sitting 6:", round(dl[-1] - dl[0]))
for n in (150, 250):
    t = (D / f"s6_bias_{n}.txt").read_text(encoding="utf-8", errors="replace")
    lo, hi = (float(v) for v in re.search(r"from ([+\-\d.]+) to ([+\-\d.]+)", t).groups())
    print(f"bias {n}: block spread {hi - lo:.2f} ms")
