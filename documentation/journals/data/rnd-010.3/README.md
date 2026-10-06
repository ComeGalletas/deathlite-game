# RND-010.3 raw measurements

The outputs behind the RND-010.3 results in
[`crowd_draw_journal.md`](../../crowd_draw_journal.md), kept as printed.
Every measured figure those results quote is in one of these files or is
printed by `derived.py` from them, except where the results name a
constant or a tool's default.

All five sittings ran on the owner's machine on 2026-10-06, on screen
(`SDL_VIDEODRIVER=windows`), with the owner's save's display block
(2560x1080 windowed, 21:9), at 150 alive (`--elapsed 300`) and 250
(`--elapsed 600`), seed 35, packed round the hero. Each `rN_meta.txt`
holds its sitting's commit, the save's display block, the CPU load
before each step and the top processes by CPU time at the start and the
end.

What else ran: sitting 5's log also lists, by name, every process with a
window at its start and end, and no game is among them. Sittings 1 to 4
logged only the top processes by CPU time, which cannot show that a game
was absent. For those, the builder's own check (not in a file) is that
Final Fantasy XIV and MechaBREAK, the clients seen on this machine
before, were not running before sitting 2. That the machine was not used
during the sittings is the owner's word.

## Sittings

| Files | What | Commit |
|---|---|---|
| `r5_quiet_*`, `r5_fight_*` (150a to 250b) | Sitting 5 (12:54 to 12:59): `spawn_stress --pack --layers --frames 600`, quiet and with `--elements`, in ABBA order (quiet a, fight a, fight b, quiet b) at each count: **the fight's comparison** | `59cd622` |
| `r5_caches_150.txt`, `r5_caches_250.txt` | Sitting 5: `sprite_caches`, the replay, the costs of a miss, a hit and an emptying, and the bytes held: **the caches** | `59cd622` |
| `r5_wash_lru_150.txt`, `r5_wash_lru_250.txt` | Sitting 5: `draw_variants --elements --variants wash_lru`, with the mean and the tails: **the variant** | `59cd622` |
| `r5_blit_floor.txt` | Sitting 5: `blit_floor --sizes 2560x1080 --counts 0,100,200,300`, the screen fill alone at n=0: **the blit floor** | `59cd622` |
| `r1_leads_150.txt`, `r1_leads_250.txt` | Sitting 1 (11:32 to 11:37): `draw_leads`, each piece of an enemy's draw in isolation, no fight: **the leads** | `503da6f` |
| `r1_variants_150.txt`, `r1_variants_250.txt` | Sitting 1: `draw_variants`, the three CPU variants, no fight | `503da6f` |
| `r1_gc.txt` | Sitting 1: `gc_probe --pack` | `503da6f` |
| `r1_fight_*`, `r1_blit_floor.txt` | Sitting 1: a first fight; the blit floor without the fill alone. Context only | `503da6f` |
| `r2_*` | Sitting 2 (11:54 to 11:57): `sprite_caches` as first built (one timing pass, memory as cap times a median request), `wash_lru` (p50 only), a second fight. Context only | `b26eb7e` |
| `r3_*`, `r4_*` | Sittings 3 (12:19 to 12:21) and 4 (12:21 to 12:24): the quiet draw at this branch's code, the caches over passes, the fight and the quiet draw paired but not counterbalanced. Context only | `42782e4` |
| `rN_meta.txt`, `sittingN.sh` | Each sitting's log, and the script that ran it, as run | |

Why five: sitting 1's fight found the lead its tools did not cover (the
wash cache), and sitting 2 ran the tools built for it. Two reviews
followed. The first asked for a baseline at this branch's code (sitting 7
of RND-010.2 ran at `bb92e30`, before RND-011 and RND-012 changed the
draw) and for costs over passes (sittings 3 and 4). The second asked for
one sitting at one commit, in ABBA order, with the variant's mean and
tails and the screen fill apart (sitting 5).

## Scripts

`python derived.py`, from anywhere, prints:
- the sittings' commits and loads;
- the leads ranked, with the sums the results quote;
- each variant's saving and interval with its verdict;
- sitting 5's fight against its quiet runs, layer by layer, naming any
  row a run did not print;
- the caches' misses, memory, costs and the savings they predict;
- the appendix probes, the blit floor per sprite with the fill taken out.

## Taking a sitting again

Each script was committed after the sitting it ran, so check out the
sitting's commit (the table's last column) only after copying the script
out of this branch. For sitting 5, from the repo root, in bash:

```bash
git show HEAD:documentation/journals/data/rnd-010.3/sitting5.sh > /tmp/sitting5.sh
git switch --detach 59cd622
bash /tmp/sitting5.sh /tmp/rnd-010.3-again
git switch -
```

Run it with a clean tree and nothing else running. `save.json` (ignored
by git, so absent in a fresh worktree) must be in the repo root with the
display block the sittings used, which each `rN_meta.txt` records on its
second line: `{'mode': 'windowed', 'render': '21:9', 'window': [2560,
1080]}` under `settings.display`. Another display gives another zoom,
another crowd in view and other numbers.
The output folder may be anywhere outside the tree. The scripts are kept
as run, so the usage lines of the first two name the scratch file they
ran from (`r3_sitting.sh`, `r3_sitting2.sh`); the argument is the same.
Each writes `rN_*.txt`. Rename before copying here, and never overwrite a
file already in this folder.
