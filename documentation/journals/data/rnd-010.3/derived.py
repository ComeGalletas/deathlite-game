"""Every figure the RND-010.3 results quote, from the raw outputs here:
`python derived.py`, from anywhere.

0. The sittings: commit, start and end, the CPU load before each step.
1. The leads (sitting 1, `draw_leads`): each piece of an enemy's draw by
   milliseconds a frame, at 150 and 250, and the sums the results quote.
2. The variants (sitting 1 quiet, sitting 2 `wash_lru` fighting): each
   one's median saving and its interval, and whether the interval
   excludes zero.
3. The fight against the quiet draw, from sitting 4, where the two ran
   interleaved at one commit (quiet a, fight a, quiet b, fight b): every
   layer's p50 in each pair and what the fight adds, the pairs' mean,
   largest first. Then sittings 1 to 3's fight and quiet headlines for
   context (other sittings, so other conditions).
4. The caches (sitting 3, the miss cost over five passes, the bytes the
   replayed cache held): misses a frame now and with an LRU, how often
   today's cache empties, and the saving each cap predicts at the median
   miss cost. Sitting 2's single-pass costs beside them.
5. The appendix probes (sitting 1).
"""
import re
from pathlib import Path

D = Path(__file__).parent
COUNTS = ((150, 300), (250, 600))


def text(name: str) -> str:
    return (D / name).read_text(encoding="utf-8", errors="replace")


def layers(t: str) -> dict:
    return {m.group(1): float(m.group(2)) for m in re.finditer(
        r"^    ([a-z_/]+)\s+([\d.]+) /\s+[\d.]+ /\s+[\d.]+\s+[\d.]+ %\s+[\d.]+$", t, re.MULTILINE)}


def headline(t: str) -> dict:
    out = {"bare": float(re.search(r"drawn without the timers: draw p50 ([\d.]+)", t).group(1)),
           "view": int(re.search(r"in view p50 (\d+)", t).group(1)),
           "frame": float(re.search(r"update \+ draw\s+p50 ([\d.]+)", t).group(1)),
           "update": float(re.search(r"frames \d+: p50 ([\d.]+)", t).group(1))}
    for g in ("terrain", "crowd"):
        out[g] = float(re.search(rf"^    \({g}\)\s+([\d.]+)", t, re.MULTILINE).group(1))
    aura = re.search(r"auras (\d+)", t)
    live = re.search(r"live (\d+) dormant", t)
    out["auras"] = (int(aura.group(1)), int(live.group(1))) if aura else None
    return out


print("== 0. the sittings ==")
for n in (1, 2, 3, 4):
    meta = text(f"r{n}_meta.txt")
    start = re.search(r"commit (\w+)\s+started (\S+ \S+)", meta)
    end = re.search(r"finished (\S+)", meta).group(1)
    loads = re.findall(r"=== (.+?)\s+cpu load (\d+)%", meta)
    print(f"sitting {n}: commit {start.group(1)}, {start.group(2)} to {end}; load before each step "
          + ", ".join(f"{k} {v}%" for k, v in loads))

print("\n== 1. the leads, sitting 1 (draw_leads, on screen, no fight) ==")
for n, _e in COUNTS:
    t = text(f"r1_leads_{n}.txt")
    head = re.search(r"draw leads: (\d+) alive, (\d+) drawn, (\d+) of them shaded.*?(\d+) rounds", t)
    whole = re.search(r"one_enemy, whole\s+([\d.]+) us a call\s+x\s+([\d.]+)\s+=\s+([\d.]+) ms", t)
    print(f"{n}: {head.group(2)} drawn, {head.group(3)} shaded, {head.group(4)} rounds; one_enemy "
          f"whole {whole.group(1)} us a call, {whole.group(3)} ms a frame")
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
    for n, _e in COUNTS:
        t = text(pattern.format(n=n))
        for m in re.finditer(r"  (\w+): draw p50 off ([\d.]+) ms, on ([\d.]+) ms \((\d+) frames each\).*?"
                             r"p50 ([+\-\d.]+) ms.*?\n"
                             r"    the median saving lies in ([+\-\d.]+) to ([+\-\d.]+) ms", t):
            name, off, on, frames, med, lo, hi = m.groups()
            verdict = ("faster" if float(hi) < 0 else "slower" if float(lo) > 0 else "unresolved")
            print(f"{label} {n}: {name:18s} off {off} on {on} ({frames} frames a side)  median {med}"
                  f"  interval {lo} to {hi}  -> {verdict}")

print("\n== 3. the fight against the quiet draw, sitting 4 (interleaved, one commit; p50 ms) ==")
for n, _e in COUNTS:
    pairs = [(text(f"r4_quiet_{n}{r}.txt"), text(f"r4_fight_{n}{r}.txt")) for r in "ab"]
    print(f"{n}:")
    for r, (q, f) in zip("ab", pairs, strict=True):
        hq, hf = headline(q), headline(f)
        auras = hf["auras"]
        print(f"    pair {r}: in view quiet {hq['view']} fight {hf['view']}; auras at the end "
              f"{auras[0]} of {auras[1]} live ({100 * auras[0] / auras[1]:.0f} %)")
        for key in ("bare", "update", "frame", "terrain", "crowd"):
            print(f"      {key:8s} quiet {hq[key]:6.2f}  fight {hf[key]:6.2f}  added {hf[key] - hq[key]:+6.2f}")
    per = [(layers(q), layers(f)) for q, f in pairs]
    names = set().union(*(set(q) | set(f) for q, f in per)) - {"draw"}
    added = {k: [f.get(k, 0.0) - q.get(k, 0.0) for q, f in per] for k in names}
    print("    layers by what the fight adds, the two pairs' mean (pair a / pair b):")
    for k in sorted(names, key=lambda k: -sum(added[k]))[:12]:
        a, b = added[k]
        print(f"      {k:22s} quiet {per[0][0].get(k, 0):5.2f} / {per[1][0].get(k, 0):5.2f}  "
              f"fight {per[0][1].get(k, 0):5.2f} / {per[1][1].get(k, 0):5.2f}  "
              f"added {(a + b) / 2:+5.2f} ({a:+.2f} / {b:+.2f})")
    totals = [sum(added[k][i] for k in names) for i in (0, 1)]
    print(f"    every layer's added p50, summed: {sum(totals) / 2:+.2f} ({totals[0]:+.2f} / {totals[1]:+.2f})")
    print("    quiet rows world_bucketed's work lies in (pair a / b): "
          + "  ".join(f"{k} {per[0][0][k]:.2f} / {per[1][0][k]:.2f}" for k in ("world", "scenery_list")))
print("context, other sittings (bare draw, terrain):")
for n, _e in COUNTS:
    for name in (f"r1_fight_{n}.txt", f"r2_fight_{n}.txt", f"r3_quiet_{n}a.txt", f"r3_quiet_{n}b.txt",
                 f"r4_quiet_{n}a.txt", f"r4_quiet_{n}b.txt", f"r4_fight_{n}a.txt", f"r4_fight_{n}b.txt"):
        h = headline(text(name))
        print(f"    {name:20s} bare {h['bare']:6.2f}  terrain {h['terrain']:5.2f}  crowd {h['crowd']:5.2f}")
    early = [headline(text(f"r{s}_fight_{n}.txt")) for s in (1, 2)]
    late = [headline(text(f"r4_fight_{n}{r}.txt")) for r in "ab"]
    for key in ("bare", "terrain"):
        gaps = [e[key] - x[key] for e in early for x in late]
        print(f"    {n}: sittings 1 and 2's fight {key} over sitting 4's: {min(gaps):+.2f} to {max(gaps):+.2f}")

print("\n== 4. the caches: misses a frame and the saving they predict ==")
for n, _e in COUNTS:
    t3, t2 = text(f"r3_caches_{n}.txt"), text(f"r2_caches_{n}.txt")
    for cache in ("wash", "tint"):
        block = re.search(rf"  {cache}: (.*?the game's cap (\d+).*?)\n((?:    cap.*\n)+)"
                          rf"    a miss ([\d.]+) us \(([\d.]+) to ([\d.]+)\), a hit ([\d.]+) us "
                          rf"\(([\d.]+) to ([\d.]+)\), over (\d+) passes", t3)
        game_cap = int(block.group(2))
        caps = {int(c): (float(g), int(gw), float(gm), float(lr), int(lw), float(lm))
                for c, g, gw, gm, lr, lw, lm in re.findall(
                    r"cap\s+(\d+): emptied when full\s+([\d.]+) misses a frame, worst\s+(\d+), held at "
                    r"most\s+([\d.]+) MB\s+\|\s+LRU\s+([\d.]+), worst\s+(\d+), held at most\s+([\d.]+) MB",
                    block.group(3))}
        miss = float(block.group(4))
        old = re.search(rf"  {cache}: .*?\n(?:    cap.*\n)+    a miss ([\d.]+) us, a hit ([\d.]+) us", t2)
        now = caps[game_cap]
        print(f"{n} {cache}: {block.group(1)}")
        print(f"    a miss {miss} us ({block.group(5)} to {block.group(6)}), a hit {block.group(7)} us "
              f"({block.group(8)} to {block.group(9)}) over {block.group(10)} passes; sitting 2's one "
              f"pass: a miss {old.group(1)} us, a hit {old.group(2)} us")
        print(f"    today (cap {game_cap}, emptied when full): {now[0]:.2f} misses a frame, so it empties "
              f"about every {game_cap / now[0]:.0f} frames; worst {now[1]}; held at most {now[2]} MB; "
              f"{now[0] * miss / 1000:.2f} ms a frame predicted, worst frame {now[1] * miss / 1000:.2f} ms")
        for cap, (_g, _gw, _gm, lr, lw, lm) in sorted(caps.items()):
            print(f"    LRU {cap:5d}: {lr:.2f} a frame, worst {lw}, held at most {lm} MB; predicts "
                  f"{(now[0] - lr) * miss / 1000:.2f} ms a frame saved")
    w = re.search(r"wash: .*?\n((?:    cap.*\n)+)    a miss ([\d.]+) us", t3)
    tt = re.search(r"tint: .*?\n((?:    cap.*\n)+)    a miss ([\d.]+) us", t3)
    wn = float(re.search(r"cap\s+512: emptied when full\s+([\d.]+)", w.group(1)).group(1))
    tn = float(re.search(r"cap\s+128: emptied when full\s+([\d.]+)", tt.group(1)).group(1))
    print(f"    today's two caches together, predicted: "
          f"{(wn * float(w.group(2)) + tn * float(tt.group(2))) / 1000:.2f} ms a frame")

print("\n== 5. the appendix probes, sitting 1 ==")
print(text("r1_gc.txt").split("\n", 2)[2].strip())
for line in text("r1_blit_floor.txt").splitlines()[2:]:
    print(line)
