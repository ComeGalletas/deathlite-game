# RND-010.6 raw measurements

The outputs behind the RND-010.6 results in
[`crowd_draw_journal.md`](../../crowd_draw_journal.md), kept as printed.
Every figure those results quote is printed by `derived.py` from these
files (`python derived.py`, from anywhere).

All on the owner's machine on 2026-10-07, on screen
(`SDL_VIDEODRIVER=windows`) with the owner's save's display block
(2560x1080 windowed, 21:9), seed 35, packed round the hero. The owner had
said the machine was free of anything heavy; each `sN_meta.txt` lists the
processes with a window and the CPU load before each step.

| Files | What |
|---|---|
| `s1_layers_<count>_<round>.txt` | Sitting 1 (`a5dd5c8`): `spawn_stress --pack --layers --elements --frames 600` at 150 / 300 and 250 / 600, twice: the under-layer split into its passes |
| `s1_leads_<count>.txt` | Sitting 1: `under_leads` at the same counts, a mean over 10 fight frames 30 apart |
| `s1_variants_<count>.txt` | Sitting 1: the four variants. Only `aura_lookup_once` is quoted: the three caching variants emptied their caches in ways that timed their own filling (fixed in RND-010.6.8 and .9) |
| `s2_aura_rle_<count>.txt` | Sitting 2 (`c24465b`): `aura_rle` with its cap raised, still emptied at every undo, so every "on" block started cold. Kept, not quoted |
| `s3_variants_<count>.txt` | Sitting 3 (`21ed117`): `aura_rle`, `shape_cached` and `ring_cached`, their caches warm from block to block. The variants' figures quoted are these |
| `s4_<kind>_<count>_<side>_<round>.txt` | Sitting 4: `main` (before) against this branch with the RLE blit built (after), ABBA, at 150, 200 and 250, fighting and quiet |
| `sN_meta.txt`, `sittingN.sh` | Each sitting's log and the script that ran it, as run |

Sittings 1 to 3 ran from the repo root with
`bash documentation/journals/data/rnd-010.6/sittingN.sh documentation/journals/data/rnd-010.6`.
Sitting 4 switches the tree between two commits, and on `main` this
folder does not exist, so it ran from a copy of `sitting4.sh` outside the
repo, writing outside it, and its outputs were copied in after:
`bash sitting4.sh OUT_DIR <main sha> <branch sha>`, in bash on Windows (it
calls `powershell` for the load and the process lists).
