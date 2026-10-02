# RND-010.2 raw measurements

The outputs behind the RND-010.2 section of
[`crowd_draw_journal.md`](../../crowd_draw_journal.md), kept as printed.
Every measured figure that section quotes is in one of these files or is
computed from them by the scripts below. Three things it states are the
builder's record and in no file: the machine (CPU, GPU, memory), the
desktop size, and that the owner's own save holds the same display block;
it labels them so.

## Sittings

| Files | What | Tool |
|---|---|---|
| `s7_150a.txt` … `s7_250b.txt` | Sitting 7 (2026-10-02, 13:57 to 14:01), the conclusions' source: `spawn_stress --layers` at 150, 200 and 250 packed, rounds a and b, with the group rows | `bb92e30` |
| `s7_bias_150.txt`, `s7_bias_250.txt` | Sitting 7: `layer_probes bias` (ABBA blocks, every block and a sign-test interval) at 150 / 300 and 250 / 600 | `bb92e30` |
| `s7_nested_150.txt`, `s7_nested_250.txt` | Sitting 7: `layer_probes nested` on the same scenes | `bb92e30` |
| `s7_meta.txt`, `sitting7.sh` | Sitting 7's log (the commit, the save's display block, the CPU load before each run, the top processes by CPU time at the start and the end) and the script that ran it, as run | |
| `s6_150a.txt` … `s6_250b.txt` | Sitting 6 (2026-10-02, 12:24 to 12:30): the same runs, a game running | `da7ab7e` |
| `s6_bias_*.txt`, `s6_nested_*.txt` | Sitting 6's probes, superseded by sitting 7's (no block list or interval); the journal does not quote them | `da7ab7e` |
| `s6_meta.txt`, `sitting6.sh` | Sitting 6's log and script | |
| `s5_150a.txt` … `s5_250b.txt` | Sitting 5 (2026-10-02, 11:40 to 11:45): the same runs | `c53225e` (the same run code as `da7ab7e`) |
| `s5_meta.txt`, `sitting5.sh` | Sitting 5's log (no process list) and script | |
| `s4_150a.txt` … `s4_250b.txt` | Sitting 4 (2026-09-30, 20:00): 150 and 250 only; no log was kept | `b6f7269` |

Sitting 5's probe outputs are not kept: they ran an earlier probe (no
ABBA order, no count of its own). Sittings 1 to 3 are not kept either
(see the journal).

## Scripts

Run from this folder:

- `python table.py s7` (or `s6`, `s5`, `s4`): a sitting's runs as the
  journal's table, and for each run the bare draw and its share of the
  budget, the terrain and the crowd's part (as sums of p50s and, for
  sitting 7, as each frame's sum), their ratio, µs per enemy, the timers'
  cost and the smaller rows.
- `python derived.py`: every cross-run figure: which of sitting 7's runs
  ran in a slow patch, the quiet runs' groups, growth and budget shares,
  the ratios over all four sittings and their spreads, the probes'
  shares and per-enemy estimates, and the load and CPU time in each
  sitting's log.
- `python trace_figures.py [trace.csv]`: the owner's frame trace figures
  (the 225+ and 150+ rows). The trace itself is not here: it lives in the
  main checkout's ignored `traces/` folder,
  `traces/frames-20260930-141150-52172.csv`.

The `sitting*.sh` scripts write into the session folder they ran from
(`S=` at their top); to take a sitting again, point `S` at an empty
folder and run one from the repo root, with a clean tree, in bash.
