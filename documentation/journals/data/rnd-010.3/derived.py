"""Every figure the RND-010.3 results quote, from the raw outputs here and
sitting 7's quiet runs in `../rnd-010.2/`: `python derived.py`.

1. The leads (sitting 1, `draw_leads`): each piece of an enemy's draw by
   milliseconds a frame, at 150 and 250.
2. The variants (sitting 1 quiet, sitting 2 `wash_lru` fighting): each
   one's median saving and its interval, and whether the interval
   excludes zero.
3. The fight against the quiet draw: every layer's p50 in both fight
   rounds (sittings 1 and 2) beside sitting 7's quiet run at the same
   count (150a, 250b: the runs `../rnd-010.2/derived.py` finds outside a
   slow patch), and the difference, largest first.
4. The caches (sitting 2): the misses a frame now and with an LRU, and
   the saving that predicts at the measured miss cost, beside the
   measured one.
5. The appendix probes (sitting 1) and the CPU load before each step.
"""
import re
from pathlib import Path

D = Path(__file__).parent
QUIET = D.parent / "rnd-010.2"
QUIET_RUN = {150: "s7_150a.txt", 250: "s7_250b.txt"}
COUNTS = (150, 250)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def layers(t: str) -> dict:
    return {m.group(1): float(m.group(2)) for m in re.finditer(
        r"^    ([a-z_/]+)\s+([\d.]+) /\s+[\d.]+ /\s+[\d.]+\s+[\d.]+ %\s+[\d.]+$", t, re.MULTILINE)}


def headline(t: str) -> dict:
    out = {"bare": float(re.search(r"drawn without the timers: draw p50 ([\d.]+)", t).group(1)),
           "view": int(re.search(r"in view p50 (\d+)", t).group(1))}
    m = re.search(r"update \+ draw\s+p50 ([\d.]+)", t)
    out["frame"] = float(m.group(1))
    for g in ("terrain", "crowd"):
        out[g] = float(re.search(rf"^    \({g}\)\s+([\d.]+)", t, re.MULTILINE).group(1))
    return out


print("== 1. the leads, sitting 1 (draw_leads, on screen, no fight) ==")
for n in COUNTS:
    t = text(D / f"r1_leads_{n}.txt")
    head = re.search(r"draw leads: (\d+) alive, (\d+) drawn, (\d+) of them shaded", t)
    whole = re.search(r"one_enemy, whole\s+([\d.]+) us a call\s+x\s+([\d.]+)\s+=\s+([\d.]+) ms", t)
    print(f"{n}: {head.group(2)} drawn, {head.group(3)} shaded; one_enemy whole "
          f"{whole.group(1)} us a call, {whole.group(3)} ms a frame")
    rows = re.findall(r"^    ([a-z_ ,:]+?)\s+([\d.]+) us a call\s+x\s+([\d.]+)\s+=\s+([\d.]+) ms a frame"
                      r"(?:\s+([\d.]+) %)?", t, re.MULTILINE)
    for name, us, calls, ms, share in sorted(rows, key=lambda r: -float(r[3])):
        if name.startswith("one_enemy"):
            continue
        print(f"    {name:24s} {float(ms):5.2f} ms a frame  {float(us):5.2f} us x {float(calls):5.1f}"
              + (f"  {share} % of the whole" if share else "  (outside one_enemy)"))
    glue = re.search(r"glue between them\)\s+=\s+([\d.]+) ms", t).group(1)
    print(f"    glue {glue} ms a frame")
    top = ("sprite blit", "shade walk", "rig_frame")
    rest = [r for r in rows if r[4] and r[0] not in top]
    scene = [r for r in rows if r[0].startswith("scene:")]
    print(f"    every other piece of one_enemy, summed: "
          f"{sum(float(us) * float(c) for _n, us, c, _m, _s in rest) / 1000:.2f} ms a frame, "
          f"{sum(float(s) for *_r, s in rest):.1f} % of the whole")
    print(f"    the scene's per-enemy steps, summed: "
          f"{sum(float(us) * float(c) for _n, us, c, _m, _s in scene) / 1000:.2f} ms a frame")

print("\n== 2. the variants: the median saving, its 97.9 % sign-test interval ==")
for label, pattern in (("sitting 1, quiet", "r1_variants_{n}.txt"),
                       ("sitting 2, fighting", "r2_wash_lru_{n}.txt")):
    for n in COUNTS:
        t = text(D / pattern.format(n=n))
        for m in re.finditer(r"  (\w+): draw p50 off ([\d.]+) ms, on ([\d.]+) ms.*?p50 ([+\-\d.]+) ms.*?\n"
                             r"    the median saving lies in ([+\-\d.]+) to ([+\-\d.]+) ms", t):
            name, off, on, med, lo, hi = m.groups()
            verdict = ("faster" if float(hi) < 0 else "slower" if float(lo) > 0 else "unresolved")
            print(f"{label} {n}: {name:18s} off {off} on {on}  median {med}  interval {lo} to {hi}"
                  f"  -> {verdict}")

print("\n== 3. the fight against the quiet draw (p50 ms) ==")
for n in COUNTS:
    quiet_t = text(QUIET / QUIET_RUN[n])
    quiet, qh = layers(quiet_t), headline(quiet_t)
    fights = [text(D / f"r{s}_fight_{n}.txt") for s in (1, 2)]
    f1, f2 = (layers(t) for t in fights)
    h1, h2 = (headline(t) for t in fights)
    print(f"{n}: in view quiet {qh['view']}, fight {h1['view']} / {h2['view']}")
    for key in ("bare", "frame", "terrain", "crowd"):
        print(f"    {key:8s} quiet {qh[key]:6.2f}  fight {h1[key]:6.2f} / {h2[key]:6.2f}  "
              f"difference {h1[key] - qh[key]:+6.2f} / {h2[key] - qh[key]:+6.2f}")
    names = set(quiet) | set(f1) | set(f2)
    diffs = sorted(names, key=lambda k: -(f1.get(k, 0) + f2.get(k, 0) - 2 * quiet.get(k, 0)))
    print("    layers by the fight's added p50, the two rounds' mean:")
    for k in diffs[:12]:
        q, a, b = quiet.get(k, 0.0), f1.get(k, 0.0), f2.get(k, 0.0)
        print(f"      {k:22s} quiet {q:5.2f}  fight {a:5.2f} / {b:5.2f}  added {(a + b) / 2 - q:+5.2f}")
    added = sum((f1.get(k, 0) + f2.get(k, 0)) / 2 - quiet.get(k, 0) for k in names if k != "draw")
    print(f"    every layer's added p50, summed: {added:+.2f}")

print("\n== 4. the caches, sitting 2: misses a frame and the saving they predict ==")
for n in COUNTS:
    t = text(D / f"r2_caches_{n}.txt")
    for cache in ("wash", "tint"):
        block = re.search(rf"  {cache}: (.*?)\n((?:    cap.*\n)+)    a miss ([\d.]+) us", t)
        caps = {int(c): (float(g), int(gw), float(lr), int(lw)) for c, g, gw, lr, lw in re.findall(
            r"cap\s+(\d+) .*?emptied when full\s+([\d.]+) misses a frame, worst\s+(\d+)\s+\|\s+"
            r"LRU\s+([\d.]+), worst\s+(\d+)", block.group(2))}
        miss = float(block.group(3))
        now = caps[min(caps)]
        print(f"{n} {cache}: {block.group(1)}")
        print(f"    now (cap {min(caps)}): {now[0]:.2f} misses a frame, worst {now[1]}; "
              f"at {miss:.1f} us a miss {now[0] * miss / 1000:.2f} ms a frame, worst frame "
              f"{now[1] * miss / 1000:.2f} ms")
        for cap, (_g, _gw, lr, lw) in sorted(caps.items()):
            print(f"    LRU {cap:5d}: {lr:.2f} a frame, worst {lw}; predicts "
                  f"{(now[0] - lr) * miss / 1000:.2f} ms a frame saved, worst frame {lw * miss / 1000:.2f} ms")

print("\n== 5. the appendix probes, sitting 1 ==")
print(text(D / "r1_gc.txt").split("\n", 2)[2].strip())
for line in text(D / "r1_blit_floor.txt").splitlines()[2:]:
    print(line)
for meta in ("r1_meta.txt", "r2_meta.txt"):
    loads = re.findall(r"=== (.+?)\s+cpu load (\d+)%", text(D / meta))
    print(f"{meta}: load before each step " + ", ".join(f"{k} {v}%" for k, v in loads))
