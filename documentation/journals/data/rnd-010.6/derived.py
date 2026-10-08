"""Every figure RND-010.6's results quote, from the raw outputs here:
`python derived.py`, from anywhere.

Sitting 1 (this branch at `a5dd5c8`): at 150 / 300 and 250 / 600 packed
with the hero fighting, the draw by layer twice (`s1_layers_*`), the leads
probe (`s1_leads_*`) and the four variants (`s1_variants_*`). Sittings 2
and 3 timed the variants again after two faults in the variant tool were
fixed (RND-010.6.8, .9); sitting 2's `aura_rle` was still cold in every
block, so only sitting 3's variants are quoted. Sitting 4 is `main`
against the branch with the RLE blit built, ABBA. `keys_*` and `bytes_*`
(`counts.sh`, headless) count the aura frames a fight asks for and what
the RLE copies hold.
"""
import re
from pathlib import Path

D = Path(__file__).parent
COUNTS = (150, 250)
UNDER = ("elemental/auras", "elemental/areas", "elemental/statuses", "elemental/particles",
         "elemental/transient", "flat/elemental")
mean = lambda v: sum(v) / len(v)


def text(name: str) -> str:
    return (D / name).read_text(encoding="utf-8", errors="replace")


def layers(t: str) -> dict:
    """`row -> (p50, mean)` from a `--layers` printout."""
    return {m.group(1): (float(m.group(2)), float(m.group(3))) for m in re.finditer(
        r"^    ([a-z_/]+)\s+([\d.]+) /\s+[\d.]+ /\s+([\d.]+)\s+[\d.]+ %\s+[\d.]+$", t, re.MULTILINE)}


def headline(t: str) -> dict:
    draw = re.search(r"draw   p50 ([\d.]+)\s+p90 ([\d.]+)\s+p99 ([\d.]+)\s+max [\d.]+ ms\s+\|\s+in view "
                     r"p50 (\d+)", t)
    frame = re.search(r"update \+ draw\s+p50 ([\d.]+)\s+p90 [\d.]+\s+p99 ([\d.]+)", t)
    update = re.search(r"frames \d+: p50 ([\d.]+)", t)
    bare = re.search(r"drawn without the timers: draw p50 ([\d.]+)", t)
    return {"bare": float(bare.group(1)), "draw p90": float(draw.group(2)),
            "draw p99": float(draw.group(3)), "view": int(draw.group(4)),
            "frame": float(frame.group(1)), "frame p99": float(frame.group(2)),
            "update": float(update.group(1))}


def leads(t: str) -> dict:
    """`piece -> ms a frame`, and the header's counts."""
    rows = {m.group(1).strip(): float(m.group(2)) for m in re.finditer(
        r"^ {4,6}(?:candidate )?([A-Za-z:,() _]+?)\s+[\d.]+ us an item\s+x\s+[\d.]+\s+=\s+([\d.]+) ms a frame",
        t, re.MULTILINE)}
    rows["(the glue)"] = None
    head = re.search(r"([\d.]+) auras, ([\d.]+) with a status \(([\d.]+) chilled, ([\d.]+) burning\), "
                     r"([\d.]+) tornadoes", t)
    return {"rows": rows, "auras": float(head.group(1)), "tornadoes": float(head.group(5))}


def variants(t: str) -> dict:
    """`name -> (p50 off, p50 on, median p50 change, its interval, mean change, its interval,
    p99 off, p99 on)`."""
    out = {}
    for block in re.split(r"\n(?=  [a-z_]+: draw p50)", t):
        m = re.match(r"\s*([a-z_]+): draw p50 off ([\d.]+) ms, on ([\d.]+) ms .*?p50: p50 ([+-][\d.]+) ms", block)
        if not m:
            continue
        iv = re.search(r"the median saving lies in ([+-][\d.]+) to ([+-][\d.]+) ms", block)
        p99 = re.search(r"p99 off ([\d.]+), on ([\d.]+)", block)
        mean_ = re.search(r"on minus off mean: p50 ([+-][\d.]+) ms; the median lies in ([+-][\d.]+) to "
                          r"([+-][\d.]+) ms", block)
        out[m.group(1)] = (float(m.group(2)), float(m.group(3)), float(m.group(4)),
                           (float(iv.group(1)), float(iv.group(2))), float(mean_.group(1)),
                           (float(mean_.group(2)), float(mean_.group(3))),
                           float(p99.group(1)), float(p99.group(2)))
    return out


print(text("s1_meta.txt").splitlines()[0])
print("\n== sitting 1: the under-layer by pass, the fight, p50 ms (rounds a / b) ==")
for n in COUNTS:
    runs = [layers(text(f"s1_layers_{n}_{r}.txt")) for r in "ab"]
    heads = [headline(text(f"s1_layers_{n}_{r}.txt")) for r in "ab"]
    total = [sum(run[k][0] for k in UNDER) for run in runs]
    print(f"{n}: in view {'/'.join(str(h['view']) for h in heads)}; bare draw "
          f"{' / '.join(f'{h['bare']:.2f}' for h in heads)}")
    for k in UNDER:
        print(f"    {k:22s} {' / '.join(f'{run[k][0]:.2f}' for run in runs)}")
    print(f"    {'the under-layer, summed':22s} {' / '.join(f'{x:.2f}' for x in total)}")

print("\n== sitting 1: the leads, ms a frame (mean over 10 fight frames) ==")
for n in COUNTS:
    lead = leads(text(f"s1_leads_{n}.txt"))
    r = lead["rows"]
    print(f"{n}: {lead['auras']:.1f} auras, {lead['tornadoes']:.1f} tornadoes")
    print(f"    aura blit {r['aura: blit']:.3f}, its RLE copy {r['aura: blit, RLE copy']:.3f}, "
          f"predicted saving {r['aura: blit'] - r['aura: blit, RLE copy']:.3f}")
    look = r["aura: frame lookup"] + r["aura: size"] + r["aura: world_to_screen"] + r["aura: state"]
    print(f"    aura lookups (state, world_to_screen, size, frame) {look:.3f}; frame lookup alone "
          f"{r['aura: frame lookup']:.3f}")
    print(f"    chill surface + polygons {r['chill: new surface'] + r['chill: polygons']:.3f}; "
          f"ring surface + circle {r['ring: new surface'] + r['ring: circle']:.3f}")

print("\n== the variants, the draw p50 per block, on minus off (97.9 % interval) ==")
for sitting, names in (("s1", ("aura_lookup_once",)), ("s3", ("aura_rle", "shape_cached", "ring_cached"))):
    for n in COUNTS:
        v = variants(text(f"{sitting}_variants_{n}.txt"))
        for name in names:
            off, on, d, iv, dm, ivm, p99o, p99n = v[name]
            resolved = "resolved" if iv[1] < 0 else "not resolved"
            resolved_m = "resolved" if ivm[1] < 0 else "not resolved"
            print(f"{sitting} {n} {name:16s} p50 {d:+.2f} ({iv[0]:+.2f} to {iv[1]:+.2f}) {resolved}; "
                  f"mean {dm:+.2f} ({ivm[0]:+.2f} to {ivm[1]:+.2f}) {resolved_m}; "
                  f"p99 {p99o:.2f} -> {p99n:.2f}")
for n in COUNTS:
    for name in ("aura_rle",):
        _o, _n, d, iv, *_ = variants(text(f"s2_aura_rle_{n}.txt"))[name]
        print(f"s2 {n} {name:16s} p50 {d:+.2f} ({iv[0]:+.2f} to {iv[1]:+.2f}): every block cold, not quoted")

if (D / "s4_meta.txt").exists():
    print("\n== sitting 4: after (the RLE blit) against before (main), p50 ms unless named ==")
    print(text("s4_meta.txt").splitlines()[0])

    def compare(before, after):
        d = mean(after) - mean(before)
        return (f"before {' / '.join(f'{x:6.2f}' for x in before)}  after "
                f"{' / '.join(f'{x:6.2f}' for x in after)}  change {d:+6.2f} "
                f"({min(after) - max(before):+.2f} to {max(after) - min(before):+.2f})")

    for kind in ("fight", "quiet"):
        print(f"-- {kind}")
        for n in (150, 200, 250):
            runs = {s: [text(f"s4_{kind}_{n}_{s}_{r}.txt") for r in "ab"] for s in ("before", "after")}
            h = {s: [headline(t) for t in ts] for s, ts in runs.items()}
            print(f"{n}: in view before {'/'.join(str(x['view']) for x in h['before'])}, after "
                  f"{'/'.join(str(x['view']) for x in h['after'])}")
            for key in ("bare", "draw p90", "draw p99", "update", "frame", "frame p99"):
                print(f"    {key:9s} " + compare([x[key] for x in h["before"]], [x[key] for x in h["after"]]))
            lay = {s: [layers(t) for t in ts] for s, ts in runs.items()}
            under = {s: [sum(v[0] for k, v in run.items() if k == "flat/elemental" or k.startswith("elemental/"))
                         for run in lay[s]] for s in lay}
            print(f"    {'under-layer':9s} " + compare(under["before"], under["after"]))

if (D / "s4_meta.txt").exists():
    steps = re.findall(r"cpu load (\d+)%  gpu (\d+) %", text("s4_meta.txt"))
    cpu, gpu = [int(c) for c, _g in steps], [int(g) for _c, g in steps]
    print(f"sitting 4's load at its steps: cpu {min(cpu)} to {max(cpu)} %, gpu {min(gpu)} to {max(gpu)} %")
    p99 = {kind: [headline(text(f"s4_{kind}_{n}_{s}_{r}.txt"))["draw p99"] for n in (150, 200, 250)
                  for s in ("before", "after") for r in "ab"] for kind in ("fight", "quiet")}
    print(f"sitting 4's draw p99s: fight {min(p99['fight']):.2f} to {max(p99['fight']):.2f} ms, "
          f"quiet {min(p99['quiet']):.2f} to {max(p99['quiet']):.2f} ms")

print("\n== the RLE cache: frames asked for, and what the copies hold (headless) ==")
for n in COUNTS:
    keys = re.search(r"distinct aura frames (\d+)", text(f"keys_{n}.txt")).group(1)
    held = re.search(r"(\d+) entries, (\d+) RLE copies, ([\d.]+) MB as pixels \(largest (\d+) kB\); "
                     r"cap (\d+) x largest = ([\d.]+) MB", text(f"bytes_{n}.txt"))
    print(f"{n}: {keys} distinct aura frames over 640 fight frames; after the warm-up and those 640, "
          f"{held.group(1)} copies, {held.group(3)} MB as pixels, largest {held.group(4)} kB, "
          f"cap {held.group(5)} x largest = {held.group(6)} MB")
