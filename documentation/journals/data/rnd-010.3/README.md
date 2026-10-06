# RND-010.3 raw measurements

The outputs behind the RND-010.3 results in
[`crowd_draw_journal.md`](../../crowd_draw_journal.md), kept as printed.
Every measured figure those results quote is in one of these files, or is
computed from them (and from sitting 7's quiet runs in `../rnd-010.2/`) by
`derived.py`. What the results state from the builder's record, in no
file here: the owner's assurance that the machine would not be used
during the sittings, and that no game client was running at their start
(checked in the process list, which is in each sitting's log).

Both sittings ran on the owner's machine on 2026-10-06, on screen
(`SDL_VIDEODRIVER=windows`), with the owner's save's display block
(2560x1080 windowed, 21:9), at 150 alive (`--elapsed 300`) and 250
(`--elapsed 600`), seed 35, packed round the hero.

## Sittings

| Files | What | Tool at |
|---|---|---|
| `r1_leads_150.txt`, `r1_leads_250.txt` | Sitting 1 (11:32 to 11:37): `draw_leads`, each piece of an enemy's draw timed in isolation, no fight | `503da6f` |
| `r1_variants_150.txt`, `r1_variants_250.txt` | Sitting 1: `draw_variants`, `rig_frame_cached`, `world_bucketed` and `forwarder_bypassed` timed ABBA against the draw, no fight | `503da6f` |
| `r1_fight_150.txt`, `r1_fight_250.txt` | Sitting 1: `spawn_stress --pack --layers --elements --frames 600`, the draw by layer with the hero fighting, round 1 | `503da6f` |
| `r1_gc.txt` | Sitting 1: `gc_probe --pack` (200 live, 400 s) | `503da6f` |
| `r1_blit_floor.txt` | Sitting 1: `blit_floor --sizes 2560x1080` | `503da6f` |
| `r1_meta.txt`, `sitting1.sh` | Sitting 1's log (the commit, the save's display block, the CPU load before each step, the top processes by CPU time at the start and the end) and its script | |
| `r2_caches_150.txt`, `r2_caches_250.txt` | Sitting 2 (11:54 to 11:57): `sprite_caches`, the wash and hit-tint caches replayed on a fight's own requests, 900 frames, the first 300 left out | `b26eb7e` |
| `r2_wash_lru_150.txt`, `r2_wash_lru_250.txt` | Sitting 2: `draw_variants --elements --variants wash_lru`, timed ABBA against the draw with the hero fighting | `b26eb7e` |
| `r2_fight_150.txt`, `r2_fight_250.txt` | Sitting 2: the fight's layers again, round 2 | `b26eb7e` |
| `r2_meta.txt`, `sitting2.sh` | Sitting 2's log and its script | |

Sitting 2 exists because sitting 1's fight found the lead (the wash
cache) that its tools did not cover; `b26eb7e` adds the tools it ran.

## Scripts

`python derived.py`, from anywhere: the leads ranked, every variant's
saving and interval with its verdict, the fight against sitting 7's quiet
runs layer by layer, the caches' misses and the saving they predict, the
appendix probes and the load before each step.

To take a sitting again: `bash documentation/journals/data/rnd-010.3/sitting2.sh
OUT_DIR` (or `sitting1.sh`) from the repo root, in bash, with a clean tree,
`save.json` in place and nothing else running. They write `r2_*.txt` (or
`r1_*.txt`) into `OUT_DIR`; rename before copying here, never overwrite
a file already in this folder.
