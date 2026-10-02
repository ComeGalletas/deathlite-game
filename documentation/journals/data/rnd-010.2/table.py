"""A sitting's runs as the journal's markdown table, plus each run's derived
figures (terrain, crowd part, per-enemy, budget shares), from the raw
outputs only: `python table.py s6` (or s5).
"""
import re
import sys
from pathlib import Path

D = Path(__file__).parent
ROWS = ("ground", "water", "scenery", "scenery_list", "enemies", "enemies/shade", "ghost",
        "world", "flat")
SMALL = ("projectiles", "elemental_sort", "flat/elemental", "enemies/hpbar", "enemies/marks",
         "hud", "huts_list", "villagers_list", "particles", "numbers", "hints", "boss")
BUDGET = 16.67


def row(t, name):
    m = re.search(rf"^    {re.escape(name)}\s+([\d.]+) /\s+([\d.]+) /\s+([\d.]+)\s+[\d.]+ %\s+([\d.]+)$",
                  t, re.MULTILINE)
    return tuple(float(x) for x in m.groups()) if m else (0.0, 0.0, 0.0, 0.0)


print("| Run | Crowd (start to end) | In view p50 | Bare draw p50 | " + " | ".join(ROWS)
      + " | enemies calls a frame |")
print("|" + "---|" * (len(ROWS) + 5))
derived = []
for n in (150, 200, 250):
    for x in "ab":
        t = (D / f"{sys.argv[1]}_{n}{x}.txt").read_text(encoding="utf-8", errors="replace")
        view = int(re.search(r"in view p50 (\d+)", t).group(1))
        bare = re.search(r"drawn without the timers: draw p50 ([\d.]+) ms; the timers add "
                         r"([+\-\d.]+) ms at p50, ([\d.]+) timed calls a frame, ([\d.]+) us", t)
        crowd = re.search(r"crowd\s+(\d+) at the start of timing, (\d+) at the end", t)
        boss = re.search(r"boss at the end of timing: (.+)", t).group(1).strip()
        assert "boss held back" in t and boss == "held back", (n, x, boss)
        assert "asked for" not in t, f"{n}{x}: shortfall"
        v = {r: row(t, r) for r in ROWS}
        print(f"| {n} {x} | {crowd.group(1)} to {crowd.group(2)} | {view} | {float(bare.group(1)):.2f} ms | "
              + " | ".join(f"{v[r][0]:.2f}" for r in ROWS) + f" | {v['enemies'][3]:.1f} |")
        terrain = sum(v[r][0] for r in ("ground", "water", "scenery", "scenery_list"))
        crowd_part = sum(v[r][0] for r in ("enemies", "enemies/shade", "ghost", "world"))
        per_enemy = 1000.0 * v["enemies"][0] / v["enemies"][3]
        small = {r: row(t, r)[:2] for r in SMALL}
        derived.append((f"{n}{x}", view, float(bare.group(1)), terrain, crowd_part, per_enemy,
                        float(bare.group(2)), float(bare.group(3)), float(bare.group(4)),
                        100 * float(bare.group(1)) / BUDGET, small))
print()
for d in derived:
    print(f"{d[0]}: view {d[1]} bare {d[2]:.2f} ({d[9]:.0f} % of budget)  terrain {d[3]:.2f}  "
          f"crowd {d[4]:.2f}  enemies/call {d[5]:.1f} us  timers {d[6]:+.2f} ms over {d[7]:.1f} calls, "
          f"{d[8]:.2f} us a call")
    print("   small p50/p90: " + "  ".join(f"{k} {a:.2f}/{b:.2f}" for k, (a, b) in d[10].items()))
