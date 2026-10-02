# RND-010.2 raw measurements

The outputs behind the RND-010.2 section of
[`crowd_draw_journal.md`](../../crowd_draw_journal.md), kept as printed.
Every figure that section quotes is in one of these files or is computed
from them by the scripts below.

## Sittings

| Files | What | Tool |
|---|---|---|
| `s6_150a.txt` … `s6_250b.txt` | Sitting 6 (2026-10-02, 12:24 to 12:30): `spawn_stress --layers` at 150, 200 and 250 packed, rounds a and b | `da7ab7e` |
| `s6_bias_150.txt`, `s6_bias_250.txt` | Sitting 6: `layer_probes bias` (ABBA blocks) at 150 / 300 and 250 / 600 | `da7ab7e` |
| `s6_nested_150.txt`, `s6_nested_250.txt` | Sitting 6: `layer_probes nested` on the same scenes | `da7ab7e` |
| `s6_meta.txt` | Sitting 6's log: the commit, the save's display block, the CPU load before each run, the top processes by CPU time at the start and the end | |
| `sitting6.sh` | The script that ran sitting 6, as run | |
| `s5_150a.txt` … `s5_250b.txt` | Sitting 5 (2026-10-02, 11:40 to 11:45): the same runs | `c53225e` (the same run code as `da7ab7e`) |
| `s5_meta.txt`, `sitting5.sh` | Sitting 5's log (no process list) and script | |
| `s4_150a.txt` … `s4_250b.txt` | Sitting 4 (2026-09-30, 20:00): 150 and 250 only; no log was kept | `b6f7269` |

Sitting 5's probe outputs are not kept: they ran an earlier probe (no
ABBA order, no count of its own), and the journal does not use them.
Sittings 1 to 3 are not kept either (see the journal).

## Scripts

Run from this folder:

- `python table.py s6` (or `s5`): a sitting's runs as the journal's
  table, and each run's terrain, crowd part, µs per enemy, timers' cost
  and the smaller rows.
- `python derived.py`: every cross-run figure: the crowd-over-terrain
  ratios and their spreads, the growth from 147 to 224 in view, the
  estimate at 178 in view, the nested wrappers' shares, the per-enemy
  estimates, sitting 4 against sitting 6, the game's CPU time in sitting
  6, the bias probe's block spreads.
- `python trace_figures.py [trace.csv]`: the owner's frame trace figures
  (the 225+ and 150+ rows). The trace itself is not here: it lives in the
  main checkout's ignored `traces/` folder,
  `traces/frames-20260930-141150-52172.csv`.

The two `sitting*.sh` scripts write into the session folder they ran
from (`S=` at their top); to take a sitting again, point `S` at an empty
folder and run them from the repo root with a clean tree.
