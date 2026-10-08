# RND-010.6 raw measurements

The outputs behind the RND-010.6 results in
[`crowd_draw_journal.md`](../../crowd_draw_journal.md), kept as printed.
Every figure those results quote is printed by `derived.py` from these
files (`python derived.py`, from anywhere).

All on the owner's machine, on screen (`SDL_VIDEODRIVER=windows`) with
the owner's save's display block (2560x1080 windowed, 21:9), seed 35,
packed round the hero. Each `sN_meta.txt` lists the processes with a
window and the load before each step.
- **Sittings 1 to 3**, 2026-10-07 (20:33 to 20:49): the owner had said
  the machine was free of anything heavy. They ran on commits made before
  the branch was rebased onto RND-013: `a5dd5c8`, `c24465b` and `21ed117`,
  which are `2d15351`, `d245315` and `261aeb0` after the rebase (whose
  trees add only RND-013's files).
- **Sitting 4**, 2026-10-08 (11:31 to 11:40): the owner's agent team, on
  another project, ran on the same machine throughout (CPU load 6 to 74 %,
  GPU 0 to 20 % at the steps); the results read its p50s only for the
  rows the change touches.

| Files | What |
|---|---|
| `s1_layers_<count>_<round>.txt` | Sitting 1 (`a5dd5c8`): `spawn_stress --pack --layers --elements --frames 600` at 150 / 300 and 250 / 600, twice: the under-layer split into its passes |
| `s1_leads_<count>.txt` | Sitting 1: `under_leads` at the same counts, a mean over 10 fight frames 30 apart |
| `s1_variants_<count>.txt` | Sitting 1: the four variants. Only `aura_lookup_once` is quoted: the three caching variants emptied their caches in ways that timed their own filling (fixed in RND-010.6.8 and .9) |
| `s2_aura_rle_<count>.txt` | Sitting 2 (`c24465b`): `aura_rle` with its cap raised, still emptied at every undo, so every "on" block started cold. Kept, not quoted |
| `s3_variants_<count>.txt` | Sitting 3 (`21ed117`): `aura_rle`, `shape_cached` and `ring_cached`, their caches warm from block to block. The variants' figures quoted are these |
| `s4_<kind>_<count>_<side>_<round>.txt` | Sitting 4: `main` (before) against this branch with the RLE blit built (after), ABBA, at 150, 200 and 250, fighting and quiet |
| `sN_meta.txt`, `sittingN.sh` | Each sitting's log and the script that ran it, as run (sitting 4's also logs the GPU's use: the owner's agent team ran through it) |
| `keys_<count>.txt`, `bytes_<count>.txt`, `memory_<count>.txt` | Headless counts by `counts.sh` (`aura_keys.py`, `rle_bytes.py`, `rle_memory.py`): the distinct aura frames a fight asks for, run as the variants run it (16 blocks of 40 frames); what the RLE copies hold as pixels after one straight run of 640; and what the same copies, made afresh, add to the process's resident memory before and after they are encoded |

Sittings 1 to 3 ran from the repo root with
`bash documentation/journals/data/rnd-010.6/sittingN.sh documentation/journals/data/rnd-010.6`.
Sitting 4 switches the tree between two commits, and on `main` this
folder does not exist, so it ran from a copy of `sitting4.sh` outside the
repo, writing outside it, and its outputs were copied in after:
`bash sitting4.sh OUT_DIR <main sha> <branch sha>`, in bash on Windows (it
calls `powershell` for the load and the process lists).
