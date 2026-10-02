"""The owner's frame trace figures the journal quotes. The trace lives in
the main checkout's ignored traces/ folder; pass another path to read a
copy."""
import csv
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else \
    "D:/Documentos/Work/pygame/deathlite-game/traces/frames-20260930-141150-52172.csv"
with open(PATH, newline="") as f:
    rows = list(csv.DictReader(f))
play = [r for r in rows if r["state"] == "PlayingState" and r["shown"] == "PlayingState"
        and r["opened"] == "0" and r["live"]]
loose = [r for r in rows if r["state"] == "PlayingState" and r["live"]]
for name, rs in (("play (state == shown, opened 0)", play), ("state only", loose)):
    big = [r for r in rs if int(r["live"]) >= 225]
    clock = sorted(float(r["run_time"]) for r in big)
    print(name, "225+:", len(big), " over 250:", sum(int(r["live"]) > 250 for r in big),
          " max", max(int(r["live"]) for r in big), " run clock", clock[0], "to", clock[-1])
def pct(vals, q):
    """tools/benchmarks/stats.py's rule: index round(q * (n - 1)), half to even."""
    vals = sorted(vals)
    return vals[min(len(vals) - 1, round(q * (len(vals) - 1)))]


big = [int(r["in_view"]) for r in play if int(r["live"]) >= 150]
print(f"play frames with 150+ alive: {len(big)}  in view p50 {pct(big, 0.5)} p99 {pct(big, 0.99)} "
      f"max {max(big)}  with 200+ in view: {sum(v >= 200 for v in big)}")
# The trace's own draw time by enemies in view, beside the harness's
# packed crowd (147, 178 and 224 in view, no fight).
print("the trace's draw_ms by enemies in view (play frames):")
for lo, hi in ((0, 30), (30, 60), (60, 90), (90, 120), (120, 150), (150, 180)):
    band = [r for r in play if r["in_view"] and lo <= int(r["in_view"]) < hi]
    if band:
        print(f"  {lo:3d} to {hi - 1:3d} in view: {len(band):5d} frames, draw p50 "
              f"{pct([float(r['draw_ms']) for r in band], 0.5):.2f} ms, p90 "
              f"{pct([float(r['draw_ms']) for r in band], 0.9):.2f}; particles p50 "
              f"{pct([int(r['particles']) for r in band], 0.5)}, damage numbers p50 "
              f"{pct([int(r['numbers']) for r in band], 0.5)}")
# Matched to the harness's quiet runs (sitting 7: 10.14 ms bare at 147 in
# view, 11.01 and 11.09 at 178): play frames within 7 in view of each.
HARNESS = ((147, (10.14,)), (178, (11.01, 11.09)))
for view, bares in HARNESS:
    band = [float(r["draw_ms"]) for r in play if r["in_view"] and abs(int(r["in_view"]) - view) <= 7]
    p50 = pct(band, 0.5)
    print(f"  {view - 7} to {view + 7} in view: {len(band)} frames, draw p50 {p50:.2f} ms; above the "
          f"harness's bare {', '.join(f'{b:.2f}' for b in bares)} by "
          + ", ".join(f"{p50 - b:.2f}" for b in bares) + " ms")
