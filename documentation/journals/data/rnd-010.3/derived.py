"""Every figure the RND-010.3 results quote, from the raw outputs here:
`python derived.py`, from anywhere.

Sitting 5 is the source of every comparison: it ran the quiet draw and the
fight, the caches' replay and the wash_lru timing in one sitting at one
commit. The other sittings are printed as context only.

0. The sittings: commit, start and end, the CPU load before each step.
1. The leads (sitting 1, `draw_leads`): each piece of an enemy's draw by
   milliseconds a frame, at 150 and 250, and the sums the results quote.
2. The variants: sitting 1's three CPU variants (quiet), and sitting 5's
   `wash_lru` (fighting): each one's median saving and interval, the
   verdict; for sitting 5 also the mean, its interval and the tails.
3. The fight against the quiet draw, sitting 5 (quiet a, fight a, fight b,
   quiet b): every layer's p50 on each side and what the fight adds, the
   mean of the two fights over the mean of the two quiet runs, largest
   first; and the headline rows. Then other sittings' runs as context.
4. The caches, sitting 5: misses a frame today and with an LRU, how often
   today's cache empties, the bytes held, the costs of a miss, a hit and
   an emptying, and the saving each LRU predicts against the measured one.
5. The appendix probes: sitting 1's `gc_probe`; sitting 5's `blit_floor`
   with the screen fill taken out, per sprite.
"""
import json
import re
from pathlib import Path

D = Path(__file__).parent
COUNTS = (150, 250)


def text(name: str) -> str:
    return (D / name).read_text(encoding="utf-8", errors="replace")


def layers(t: str) -> dict:
    rows = {m.group(1): float(m.group(2)) for m in re.finditer(
        r"^    ([a-z_/]+)\s+([\d.]+) /\s+[\d.]+ /\s+[\d.]+\s+[\d.]+ %\s+[\d.]+$", t, re.MULTILINE)}
    # Every line of the table must parse: a row the pattern misses would
    # otherwise vanish from every run alike, with no "no row" notice.
    table = t.split("draw by layer", 1)[1].split("    (all layers)", 1)[0]
    lines = [ln for ln in table.splitlines()[1:] if ln.startswith("    ") and ln.strip()]
    assert len(lines) == len(rows), f"{len(lines)} layer lines, {len(rows)} parsed"
    rows["(all layers)"] = float(re.search(r"^    \(all layers\)\s+([\d.]+)", t, re.MULTILINE).group(1))
    return rows


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


mean = lambda v: sum(v) / len(v)

print("== 0. the sittings ==")
for n in (1, 2, 3, 4, 5):
    meta = text(f"r{n}_meta.txt")
    start = re.search(r"commit (\w+)\s+started (\S+ \S+)", meta)
    end = re.search(r"finished (\S+)", meta).group(1)
    loads = re.findall(r"=== (.+?)\s+cpu load (\d+)%", meta)
    print(f"sitting {n}: commit {start.group(1)}, {start.group(2)} to {end}; load before each step "
          + ", ".join(f"{k} {v}%" for k, v in loads))

print("\n== 1. the leads, sitting 1 (draw_leads, on screen, no fight) ==")
for n in COUNTS:
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
    def pick(*names, rows=rows):
        return sum(float(us) * float(c) for n_, us, c, _m, _s in rows if n_ in names) / 1000
    print(f"    every other piece of one_enemy, summed: "
          f"{sum(float(us) * float(c) for _n, us, c, _m, _s in rest) / 1000:.2f} ms a frame, "
          f"{sum(float(s) for *_r, s in rest):.1f} % of the whole")
    print(f"    the scene's per-enemy steps, summed: "
          f"{pick('scene: cull test', 'scene: terrace lookup', 'scene: lambda', 'scene: forwarder'):.2f}"
          f" ms a frame; the lambda and the forwarder alone: "
          f"{pick('scene: lambda', 'scene: forwarder'):.2f} ms")

print("\n== 2. the variants ==")
VARIANT = (r"  (\w+): draw p50 off ([\d.]+) ms, on ([\d.]+) ms \((\d+) frames each\).*?p50 ([+\-\d.]+) ms.*?\n"
           r"    the median saving lies in ([+\-\d.]+) to ([+\-\d.]+) ms")
verdict = lambda lo, hi: "faster" if float(hi) < 0 else "slower" if float(lo) > 0 else "unresolved"
for n in COUNTS:
    for m in re.finditer(VARIANT, text(f"r1_variants_{n}.txt")):
        name, off, on, frames, med, lo, hi = m.groups()
        print(f"sitting 1, quiet {n}: {name:18s} off {off} on {on} ({frames} frames a side)  "
              f"p50 diff median {med}, interval {lo} to {hi} -> {verdict(lo, hi)}")
for n in COUNTS:
    t = text(f"r5_wash_lru_{n}.txt")
    name, off, on, frames, med, lo, hi = re.search(VARIANT, t).groups()
    tails = re.search(r"mean off ([\d.]+) ms, on ([\d.]+) ms; p90 off ([\d.]+), on ([\d.]+); "
                      r"p99 off ([\d.]+), on ([\d.]+)", t).groups()
    mm = re.search(r"on minus off mean: p50 ([+\-\d.]+) ms; the median lies in ([+\-\d.]+) to "
                   r"([+\-\d.]+) ms", t).groups()
    print(f"sitting 5, fighting {n}: {name}: p50 off {off} on {on} ({frames} frames a side); "
          f"p50 diff median {med}, interval {lo} to {hi} -> {verdict(lo, hi)}")
    print(f"    mean off {tails[0]} on {tails[1]}; mean diff median {mm[0]}, interval {mm[1]} to {mm[2]}"
          f" -> {verdict(mm[1], mm[2])}; p90 {tails[2]} -> {tails[3]}; p99 {tails[4]} -> {tails[5]}")
    pooled = float(tails[0]) - float(tails[1])
    print(f"    pooled over all 640 frames a side, the mean falls by {pooled:.2f} ms (one figure, no interval)")
    if n == 250:
        caches = text("r5_caches_250.txt")
        wash = re.search(r"wash: .*?\n((?:    cap.*\n)+)    a miss ([\d.]+) us.*?\n    emptying a cache of "
                         r"\d+: ([\d.]+) ms", caches)
        now = re.search(r"cap\s+512: emptied when full\s+([\d.]+) misses a frame, worst\s+\d+, emptied\s+(\d+)",
                        wash.group(1))
        lru = float(re.search(r"cap\s+1536: .*?LRU\s+([\d.]+)", wash.group(1)).group(1))
        miss, empty_ms = float(wash.group(2)), float(wash.group(3))
        predicted = (float(now.group(1)) - lru) * miss / 1000 + int(now.group(2)) * empty_ms / 600
        print(f"    the replay predicts {predicted:.2f} ms saved; against the median per-block mean saving "
              f"{-float(mm[0]):.2f} ({-float(mm[2]):.2f} to {-float(mm[1]):.2f}) the gap is "
              f"{predicted + float(mm[1]):.2f} to {predicted + float(mm[2]):.2f} ms; against the pooled "
              f"{pooled:.2f}, {predicted - pooled:.2f} ms")
        distinct = int(re.search(r"wash: .*?(\d+) distinct frames", caches).group(1))
        fill = distinct * miss / 1000
        print(f"    the variant's LRU starts nearly empty: filling it once with the {distinct} distinct frames "
              f"costs at most {fill:.0f} ms, {fill / int(frames):.2f} ms over the {frames} frames on")
print("context, sitting 2's wash_lru (another sitting and commit):")
for n in COUNTS:
    name, off, on, frames, med, lo, hi = re.search(VARIANT, text(f"r2_wash_lru_{n}.txt")).groups()
    print(f"    {n}: p50 off {off} on {on}; p50 diff median {med}, interval {lo} to {hi} -> {verdict(lo, hi)}")

print("\n== 3. the fight against the quiet draw, sitting 5 (quiet a, fight a, fight b, quiet b; p50 ms) ==")
for n in COUNTS:
    q = [text(f"r5_quiet_{n}{r}.txt") for r in "ab"]
    f = [text(f"r5_fight_{n}{r}.txt") for r in "ab"]
    hq, hf = [headline(t) for t in q], [headline(t) for t in f]
    auras = hf[0]["auras"]
    print(f"{n}: in view quiet {hq[0]['view']} / {hq[1]['view']}, fight {hf[0]['view']} / {hf[1]['view']}; "
          f"auras at the end of a fight {auras[0]} of {auras[1]} live ({100 * auras[0] / auras[1]:.0f} %)")
    for label, runs in (("quiet", q), ("fight", f)):
        for r, t in zip("ab", runs, strict=True):
            crowd = re.search(r"crowd\s+(\d+) at the start of timing, (\d+) at the end\s+\|\s+arrived: (.*)", t)
            print(f"    crowd {label} {r}: {crowd.group(1)} to {crowd.group(2)} alive, arrived {crowd.group(3)}")
    for key in ("bare", "update", "frame", "terrain", "crowd"):
        a, b = [h[key] for h in hq], [h[key] for h in hf]
        print(f"    {key:8s} quiet {a[0]:6.2f} / {a[1]:6.2f}  fight {b[0]:6.2f} / {b[1]:6.2f}  added "
              f"{mean(b) - mean(a):+6.2f} (from {min(b) - max(a):+.2f} to {max(b) - min(a):+.2f})")
    lq, lf = [layers(t) for t in q], [layers(t) for t in f]
    names = set().union(*lq, *lf)
    # The layer tool prints no row for a layer never called in a run (no
    # death poofs without a fight): such a row counts 0, and is named here.
    for label, runs in (("quiet", lq), ("fight", lf)):
        for r, x in zip("ab", runs, strict=True):
            if names - set(x):
                print(f"    no row in {label} {r} (never called there, counted 0): "
                      + ", ".join(sorted(names - set(x))))
    lq = [{k: x.get(k, 0.0) for k in names} for x in lq]
    lf = [{k: x.get(k, 0.0) for k in names} for x in lf]
    added = {k: mean([x[k] for x in lf]) - mean([x[k] for x in lq]) for k in names}
    print("    layers by what the fight adds (the fights' mean over the quiet runs' mean):")
    for k in sorted(names - {"draw", "(all layers)"}, key=lambda k: -added[k])[:12]:
        print(f"      {k:22s} quiet {lq[0][k]:5.2f} / {lq[1][k]:5.2f}  fight {lf[0][k]:5.2f} / "
              f"{lf[1][k]:5.2f}  added {added[k]:+5.2f}")
    summed = sum(v for k, v in added.items() if k not in ("draw", "(all layers)"))
    print(f"    the layers' added p50s, summed: {summed:+.2f}; the '(all layers)' row's p50, added: "
          f"{added['(all layers)']:+.2f}")
    print("    quiet rows world_bucketed's work lies in (a / b): "
          + "  ".join(f"{k} {lq[0][k]:.2f} / {lq[1][k]:.2f}" for k in ("world", "scenery_list")))
print("context, other sittings' fights and quiet runs (bare draw, terrain):")
for n in COUNTS:
    for name in (f"r1_fight_{n}.txt", f"r2_fight_{n}.txt", f"r4_quiet_{n}a.txt", f"r4_fight_{n}a.txt",
                 f"r4_quiet_{n}b.txt", f"r4_fight_{n}b.txt", f"r3_quiet_{n}a.txt", f"r3_quiet_{n}b.txt"):
        h = headline(text(name))
        print(f"    {name:20s} bare {h['bare']:6.2f}  terrain {h['terrain']:5.2f}")
    early = [headline(text(f"r{s}_fight_{n}.txt"))["bare"] for s in (1, 2)]
    later = [headline(text(f"r5_fight_{n}{r}.txt"))["bare"] for r in "ab"]
    gaps = [e - x for e in early for x in later]
    print(f"    {n}: sittings 1 and 2's fights' bare draw over sitting 5's, every pairing: "
          f"{min(gaps):+.2f} to {max(gaps):+.2f} ms")

print("\n== 4. the caches, sitting 5 ==")
for n in COUNTS:
    t = text(f"r5_caches_{n}.txt")
    for cache in ("wash", "tint"):
        block = re.search(
            rf"  {cache}: (.*?the game's cap (\d+), frames (\d+) to (\d+))\n((?:    cap.*\n)+)"
            rf"    a miss ([\d.]+) us \(([\d.]+) to ([\d.]+)\), a hit ([\d.]+) us \(([\d.]+) to ([\d.]+)\), "
            rf"over (\d+) passes\n    emptying a cache of (\d+): ([\d.]+) ms \(([\d.]+) to ([\d.]+)\)", t)
        g = block.groups()
        game_cap, frames = int(g[1]), int(g[3]) - int(g[2])
        caps = {int(c): (float(a), int(w), int(e), float(gm), float(lr), int(lw), float(lm))
                for c, a, w, e, gm, lr, lw, lm in re.findall(
                    r"cap\s+(\d+): emptied when full\s+([\d.]+) misses a frame, worst\s+(\d+), emptied\s+(\d+) "
                    r"times, held at most\s+([\d.]+) MB\s+\|\s+LRU\s+([\d.]+), worst\s+(\d+), held at most\s+"
                    r"([\d.]+) MB", g[4])}
        miss, empty_ms = float(g[5]), float(g[13])
        now = caps[game_cap]
        today = now[0] * miss / 1000 + now[2] * empty_ms / frames
        distinct = int(re.search(r"(\d+) distinct frames", g[0]).group(1))
        print(f"{n} {cache}: {g[0]}")
        print(f"    today's cap holds {game_cap / distinct:.2f} of the distinct frames")
        print(f"    a miss {miss} us ({g[6]} to {g[7]}), a hit {g[8]} us ({g[9]} to {g[10]}), over {g[11]} "
              f"passes; emptying {g[12]}: {empty_ms} ms ({g[14]} to {g[15]})")
        print(f"    today (cap {game_cap}): {now[0]:.2f} misses a frame, worst {now[1]}, emptied {now[2]} times "
              f"in {frames} frames (about every {frames / now[2]:.0f})" if now[2] else
              f"    today (cap {game_cap}): {now[0]:.2f} misses a frame, worst {now[1]}, never emptied")
        print(f"      held at most {now[3]} MB; predicted {today:.2f} ms a frame (the emptying "
              f"{now[2] * empty_ms / frames:.3f} of it), its worst frame {now[1] * miss / 1000:.2f} ms")
        for cap, (_a, _w, _e, _gm, lr, lw, lm) in sorted(caps.items()):
            print(f"    LRU {cap:5d}: {lr:.2f} a frame, worst {lw}, held at most {lm} MB; predicts "
                  f"{today - lr * miss / 1000:.2f} ms a frame saved")

print("\n== 4b. what a cap can hold at most: the largest frame each cache can be asked for ==")
# A copy is the rig's frame at round(base x zoom) on each side
# (`WorldRenderer.rig_frame`), 4 bytes a pixel at 32 bits; the base sizes
# are each rig's `scale`. Which rigs reach which cache, from the code:
# `washed` has one caller, `enemy_sprite`, so only the rigs regular enemies
# wear (the `sprite` of each entry in data/enemies/enemies.json);
# `hit_tinted` is called for enemies, the boss (`boss`, bosses.json) and
# the hero (`player`; every rig in data/heroes/character_sprites.json, an
# upper bound since that file holds more than the hero).
DATA_DIR = D.parents[3] / "data"
zoom = float(re.search(r"zoom ([\d.]+)", text("r5_fight_250a.txt")).group(1))
load = lambda *p: json.loads(DATA_DIR.joinpath(*p).read_text(encoding="utf-8"))
enemy_rigs, hero_rigs = load("enemies", "enemy_sprites.json"), load("heroes", "character_sprites.json")
worn = {e["sprite"] for e in load("enemies", "enemies.json").values() if e.get("sprite")}
bosses = {b["sprite"] for b in load("enemies", "bosses.json").values() if b.get("sprite")}


def largest(rigs: dict, names) -> tuple:
    sized = [(round(rigs[n]["scale"][0] * zoom), round(rigs[n]["scale"][1] * zoom), n)
             for n in names if n in rigs and rigs[n].get("scale")]
    return max(sized, key=lambda t: t[0] * t[1])


wash = largest(enemy_rigs, worn)
tint = max(largest(enemy_rigs, worn | bosses), largest(hero_rigs, hero_rigs), key=lambda t: t[0] * t[1])
print(f"zoom {zoom}; {len(worn)} rigs worn by regular enemies, {len(bosses)} by bosses")
for label, (w, h, name), caps in (("wash (regular enemies)", wash, (512, 1024, 1536)),
                                  ("tint (enemies, bosses, hero)", tint, (128, 256))):
    one = w * h * 4
    print(f"    {label}: the largest frame is {name}'s, {w}x{h}, {one / 1e6:.2f} MB a copy; full caps: "
          + ", ".join(f"{c} -> {c * one / 1e6:.1f} MB" for c in caps))

print("\n== 5. the appendix probes ==")
print("sitting 1, gc_probe --pack:")
print("    " + text("r1_gc.txt").split("\n", 2)[2].strip().replace("\n", "\n    "))
print("sitting 5, blit_floor at 2560x1080, the screen fill (n=0) taken out:")
rows = re.findall(r"n=\s*(\d+)\s+(sprite only|sprite\+shadow\+bar)\s+p50\s+([\d.]+)", text("r5_blit_floor.txt"))
fill = {kind: float(p) for n_, kind, p in rows if n_ == "0"}
for n_, kind, p in rows:
    if n_ != "0":
        per = (float(p) - fill[kind]) / int(n_) * 1000
        print(f"    n={n_:>3s} {kind:18s} p50 {p} ms, less the fill {fill[kind]:.2f}: {per:.2f} us a sprite")
print("    sitting 1's rows (no n=0): " + "; ".join(
    f"n={a} {b} {c}" for a, b, c in re.findall(r"n=\s*(\d+)\s+(sprite only|sprite\+shadow\+bar)\s+p50\s+([\d.]+)",
                                                text("r1_blit_floor.txt"))))
