# RND-010.3 raw measurements

The outputs behind the RND-010.3 results in
[`crowd_draw_journal.md`](../../crowd_draw_journal.md), kept as printed.
Every measured figure those results quote is in one of these files or is
printed by `derived.py` from them, except where the results name a
tool's default. What the results state from the builder's record, in no
file here: the owner's word that the machine would not be used during
the sittings. That no game client was running at each sitting's start
is in its log's process list.

All four sittings ran on the owner's machine on 2026-10-06, on screen
(`SDL_VIDEODRIVER=windows`), with the owner's save's display block
(2560x1080 windowed, 21:9), at 150 alive (`--elapsed 300`) and 250
(`--elapsed 600`), seed 35, packed round the hero. Each `rN_meta.txt`
holds its sitting's commit, the save's display block, the CPU load
before each step and the top processes by CPU time at the start and the
end.

## Sittings

| Files | What | Commit |
|---|---|---|
| `r1_leads_150.txt`, `r1_leads_250.txt` | Sitting 1 (11:32 to 11:37): `draw_leads`, each piece of an enemy's draw timed in isolation, no fight | `503da6f` |
| `r1_variants_150.txt`, `r1_variants_250.txt` | Sitting 1: `draw_variants`, `rig_frame_cached`, `world_bucketed` and `forwarder_bypassed` timed ABBA against the draw, no fight | `503da6f` |
| `r1_fight_150.txt`, `r1_fight_250.txt` | Sitting 1: `spawn_stress --pack --layers --elements --frames 600`, the draw by layer with the hero fighting; context only | `503da6f` |
| `r1_gc.txt`, `r1_blit_floor.txt` | Sitting 1: `gc_probe --pack`; `blit_floor --sizes 2560x1080` | `503da6f` |
| `r2_caches_150.txt`, `r2_caches_250.txt` | Sitting 2 (11:54 to 11:57): `sprite_caches` as first built (one timing pass, memory as cap times a median request); superseded by `r3_caches_*` | `b26eb7e` |
| `r2_wash_lru_150.txt`, `r2_wash_lru_250.txt` | Sitting 2: `draw_variants --elements --variants wash_lru`, timed ABBA with the hero fighting | `b26eb7e` |
| `r2_fight_150.txt`, `r2_fight_250.txt` | Sitting 2: the fight's layers again; context only | `b26eb7e` |
| `r3_quiet_150a.txt` … `r3_quiet_250b.txt` | Sitting 3 (12:19 to 12:21): `spawn_stress --pack --layers --frames 600`, the quiet draw at this branch's code, rounds a and b | `42782e4` |
| `r3_caches_150.txt`, `r3_caches_250.txt` | Sitting 3: `sprite_caches`, the costs over five passes and the bytes the replayed cache held | `42782e4` |
| `r4_quiet_*`, `r4_fight_*` (150a to 250b) | Sitting 4 (12:21 to 12:24): the quiet draw and the fight interleaved (quiet a, fight a, quiet b, fight b): the comparison the results use | `42782e4` |
| `rN_meta.txt`, `sittingN.sh` | Each sitting's log, and the script that ran it, as run | |

Sitting 2 exists because sitting 1's fight found the lead (the wash
cache) that its tools did not cover; `b26eb7e` adds the tools it ran.
Sittings 3 and 4 answer a review: sitting 7 of RND-010.2 ran at
`bb92e30`, before RND-011 and RND-012 changed the draw, so it is no
baseline for these fights; and fights taken in other sittings than their
quiet runs mix the machine's state into the difference.

## Scripts

`python derived.py`, from anywhere: the sittings' commits and loads, the
leads ranked with the sums the results quote, every variant's saving
and interval with its verdict, sitting 4's fight against its quiet runs
layer by layer, the caches' misses, memory and the savings they predict,
and the appendix probes.

To take a sitting again, check out its commit first (the table's last
column), since the tools changed after each one: `git switch --detach
503da6f`, for instance, then `bash
documentation/journals/data/rnd-010.3/sitting1.sh OUT_DIR` from the repo
root, in bash, with a clean tree, `save.json` in place and nothing else
running. The scripts are kept as run, so the usage line of the first two
names the scratch file they ran from (`r3_sitting.sh`, `r3_sitting2.sh`);
the argument is the same. They write `rN_*.txt` into `OUT_DIR`; rename
before copying here, never overwrite a file already in this folder.
