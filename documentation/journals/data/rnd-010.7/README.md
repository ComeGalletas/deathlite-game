# RND-010.7 raw measurements

The outputs behind the RND-010.7 results in
[`crowd_draw_journal.md`](../../crowd_draw_journal.md), kept as printed.
Every figure those results quote is printed by `derived.py` from these
files (`python derived.py`, from anywhere).

All headless (`SDL_VIDEODRIVER=dummy`) on the owner's machine on
2026-10-08, seed 35, packed round the hero, quiet. The shade walk draws no
pixels for a body under no tree, which is the path the skip changed, so
the dummy driver times it as the screen would.

| Files | What |
|---|---|
| `s1_leads_<count>_<side>_<round>.txt` | Sitting 1 (13:25 to 13:29): `draw_leads --rounds 400` at 150 / 300 and 250 / 600. `before` is `main` at `6069c3a`, `after` the branch at `6e0bd09` (the skip built). ABBA at each count: before a, after a, after b, before b. The subset piece exists on the after side only, named `subset: shade walk, unshaded` then (`subset: walk, unshaded` since RND-010.7.6) |
| `s1_layers_<count>_<side>_<round>.txt` | Sitting 1: `spawn_stress --pack --layers --frames 600`, the same order: the `enemies/shade` row |
| `s1_meta.txt`, `sitting1.sh` | The sitting's log (the two commits, the CPU load before each step) and its script. It switches the tree between the commits, so it ran from a copy outside the repo: `bash sitting1.sh OUT_DIR <main sha> <branch sha>` |
| `shapes_<count>_<round>.txt`, `walk_shapes.py`, `shapes.sh` | Two runs a count (13:41 to 13:42, at `512b983`, each stamped with the CPU load): the unshaded bodies split by whether their index cells are empty, then the walk's shapes timed against the walk in one process each: the walk, the skip as built, a one-cell fast path, an exact skip on a 64 px occupancy grid, and an approximate floor. `bash documentation/journals/data/rnd-010.7/shapes.sh` from the repo root |
