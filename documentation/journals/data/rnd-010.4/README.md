# RND-010.4 raw measurements

The outputs behind the RND-010.4 results in
[`crowd_draw_journal.md`](../../crowd_draw_journal.md), kept as printed.
Every figure those results quote is printed by `derived.py` from these
files.

One sitting, on the owner's machine on 2026-10-07 (10:48 to 10:57), on
screen (`SDL_VIDEODRIVER=windows`) with the owner's save's display block
(2560x1080 windowed, 21:9), seed 35, packed round the hero. The owner had
said the machine would be free; `s1_meta.txt` lists, by name, every
process with a window at the start and the end, and no game is among
them.

| Files | What |
|---|---|
| `s1_fight_<count>_<side>_<round>.txt` | `spawn_stress --pack --layers --elements --frames 600` at 150 / 300, 200 / 400 and 250 / 600: the hero fighting. `before` is `main` at `2c6865a`, `after` this branch at `f4f0079` (the wash cache an LRU of 1536). Rounds in ABBA order at each count: before a, after a, after b, before b |
| `s1_quiet_<count>_<side>_<round>.txt` | The same without `--elements`: no enemy is primed, so nothing is washed, a control |
| `s1_caches_250_after.txt` | `sprite_caches` at 250 on the branch: the game's cap now prints as 1536 |
| `s1_meta.txt`, `sitting1.sh` | The sitting's log (the two commits, the display block, the CPU load before each step, the processes) and the script that ran it, as run |

The script switches the worktree between the two commits for each run,
with `git switch --detach`, and back to the branch when it ends. To run
it again: from the repo root, with a clean tree and `save.json` in
place, `bash documentation/journals/data/rnd-010.4/sitting1.sh OUT_DIR
<before sha> <after sha>`, in bash on Windows (it calls `powershell` for
the load and the process lists).

`python derived.py`, from anywhere, prints each run's headline and the
change after against before at each count, the layer rows that move
most, the cache replay's key lines and the load before each step.
