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
big = sorted(int(r["in_view"]) for r in play if int(r["live"]) >= 150)
pct = lambda q: big[min(len(big) - 1, round(q * (len(big) - 1)))]   # tools/benchmarks/stats.py's rule
print(f"play frames with 150+ alive: {len(big)}  in view p50 {pct(0.5)} p99 {pct(0.99)} max {big[-1]}  "
      f"with 200+ in view: {sum(v >= 200 for v in big)}")
