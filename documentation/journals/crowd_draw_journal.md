# Drawing big crowds: journal

**ID:** RND-010 · **System:** rendering · **Type:** performance ·
**Status:** in progress · **Branch:** ComeGalletas/crowd-draw-levelup-9ec11fc6
(from `main`, owner, 2026-09-30; shared with UI-018; RND-010.1 and .2, merged),
then ComeGalletas/rnd-010-3-leads-9ec11fc6 (from `main`, 2026-10-04; RND-010.3),
then claude/rnd-010-4-wash-lru (from `main`, 2026-10-06; RND-010.4; in the
session's worktree, as the owner chose under CLAUDE.md §1.5),
then claude/rnd-010-5-debug-lines (from `main`, 2026-10-07; RND-010.5; in
the same worktree, a task inside the ongoing requirement)

---

## RND-010: Requirement (owner, 2026-09-30)

- **Objective:** Cut the draw time of play frames with big crowds, so that
  play holds the 60 fps budget (16.67 ms, kept by the owner on 2026-09-30)
  further into a run.
- **Details:**
  - The owner's first real-play trace (SYS-010, 557 s, one run on the
    owner's display) says the draw is the problem, not the update: of 5,553
    play frames over budget, 5,525 were draw-bound and 28 update-bound; of
    1,439 long frames, the draw took most of 1,422.
  - It grows with the crowd:

    | Enemies alive | Frames | Work p50 / p90 | Over budget | In view p50 | Particles p50 |
    |---|---|---|---|---|---|
    | 0 to 24 | 3,776 | 9.30 / 12.15 ms | 0.6 % | 1 | 0 |
    | 25 to 49 | 3,063 | 10.02 / 12.79 ms | 1.4 % | 14 | 26 |
    | 50 to 99 | 4,172 | 12.53 / 15.63 ms | 4.7 % | 32 | 38 |
    | 100 to 149 | 4,889 | 14.64 / 18.25 ms | 23.6 % | 54 | 55 |
    | 150+ | 4,557 | 21.23 / 26.44 ms | 90.8 % | 90 | 121 |

    The owner saw about 44 fps with over 100 enemies on screen and about
    30 fps with over 220. The worst seconds of the run held 225 to 250
    alive, with the worst work at 25.5 to 29.9 ms.
  - The owner's read: the enemies are the draw cost, and the terrain stays
    as it is. RND-009 found the ground bands at the alpha blitter's floor
    (3.2 to 4.1 ms at 100 packed), with no exact speed-up, so this work
    goes after what scales with the crowd.
- **Constraint:**
  - Pixels do not change: a whole frame is byte-identical old against new
    (`pygame.image.tobytes`), as in RND-008.
  - Gameplay does not change.
  - The resolution stays native (RND-008.D4); the terrain is left as it is.
  - A candidate is timed without wrappers, old against new, before it is
    built (ENT-018.3's lesson: cProfile inflates cheap Python calls).
  - If the exact changes fall short, the report says by how much, and any
    change that alters the picture (a draw LOD, fewer particles) goes to
    the owner as a decision, never in by default.

## RND-010: What the draw does per enemy today (read from the code, 2026-09-30)

A read of the draw path, to aim the measuring; each item is a lead, not a
finding, until RND-010.2 times it.

- **The list.** `scene.actor_items` (`game/states/playing/visual/scene.py:106-152`)
  culls with `view.collidepoint` (pad `RENDER_ACTOR_CULL_PAD` 320), then
  builds a lambda and looks up a terrace band for each enemy in view.
  `draw_world` (`scene.py:55-76`) re-filters the whole scenery and actor
  lists for every terrace and sorts each: levels × items a frame.
- **One enemy** (`WorldRenderer.one_enemy`, `visual/rendering.py:583-636`),
  reached through a generated forwarder (`core/state.py:755, 770-783`):
  - the frame lookup (`rig_frame`, `rendering.py:138-146`) is a chain of
    dict lookups (`Animator.index` makes three, `scale_for` builds a
    tuple); the scaled strips themselves are cached in `Assets._frames`;
  - `world_to_screen` runs two to four times per enemy;
  - hit flash and elemental wash are cached copies (`hit_tinted`,
    `element_fx.washed`), but `aura_colour` runs for every sprited enemy;
  - the tree-shade walk (`TerrainRenderer.shade_character_frame`,
    `world/terrain/render.py:365-416`) runs for every enemy; a shaded one
    costs three or more blits into scratch surfaces, and then a
    `drawn.copy()` every frame for the ghost queue, whether or not the
    ghost pass uses it (`rendering.py:125-128`);
  - the health bar (cached bar surfaces) for every damaged enemy; the mark
    brackets for marked ones, with a `copy()` and `set_alpha` every frame
    while they fade (`status_marks.py:127-130`).
- **The ghost pass** (`render.py:505-550`): for each drawn body, a walk of
  the obstacle-art index with new `Rect`s per overlap; a shaded body's
  ghost is copied and filled anew every frame (`_ghost_uncached`).
- **The elemental layers** (`elements/layers.py`): a new SRCALPHA surface
  per frame for each aura or mark drawn without authored art (`_ring`,
  `_shape`, `markers.draw`).
- **Particles and damage numbers** are drawn without view culling (up to
  1,200 particles and 200 numbers); particles are one `draw.circle` each.

## RND-010: Plan

- **RND-010.2: Measure the draw by layer.** Give the stress harness
  (`tools/benchmarks/spawn_stress.py`) a per-layer breakdown of
  `PlayingState.draw`: terrain bands, enemies (with the shade), other
  actors, the ghost pass, the elemental layers, particles, damage numbers,
  and the rest. Take it at 150, 200 and 250 packed, seed 35, on the Windows
  renderer at native resolution, where the owner's trace says the frames
  go over. This checks the owner's read that the enemies are the cost, and
  ranks the crowd's layers (the enemies' own draw, the shade, the ghost
  pass, the lists, the elemental layers, the bars and marks). The
  breakdown's parts must add up to the whole draw, pinned by a test.
- **RND-010.3: Rank the leads inside the enemies' own draw, then time the
  candidates, old against new, without wrappers.** First split `enemies`'
  own time among the per-enemy leads above (the rig frame,
  `world_to_screen`, the aura colour, the ghost record's copy), timing
  each lead old against new rather than wrapping it, since a wrapper per
  lead would be a large share of what it measures (RND-010.D1). Then,
  for each lead that comes out on top, time a throwaway version of the
  change first, and record the result in this journal whether it wins or
  not.
- **RND-010.4 and on: build the winners**, one task each, largest first
  (since RND-010.3, the sequence table under its results governs: only
  RND-010.4 is a measured winner, several entries are measured before
  anything is built, and the order weighs size with how often a cost
  occurs):
  each with a whole-frame byte-identity test at 150 and 250 packed (built
  on `tests/render/test_elemental_draw_cost.py`'s frame), the existing
  render tests (`test_render_cull`, `test_ghost`, `test_enemy_sprite`,
  `test_enemy_hp_bar`, `test_element_layers`, `test_depth_sort`,
  `test_mark_brackets`) green, and a mutation check.
- **RND-010.n: Results.** The harness at 150, 200 and 250, before and
  after, in one sitting; then the owner plays a run with `--trace` and the
  150+ row is compared with the one above.
- **Outcome:** in the owner's trace, the 150+ row's frames over budget
  (90.8 %) and work p50 (21.23 ms) fall, and the 100 to 149 row (23.6 %)
  with them.

## RND-010.2: The draw by layer (2026-09-30, measured again 2026-10-02)

**The tool.** `python -m tools.benchmarks.spawn_stress --live N --elapsed E
--pack --layers` (`tools/benchmarks/draw_layers.py`). It wraps each layer's
entry point on the live objects and records the time spent in it less the
layers it calls. A nested layer is named under its nearest named caller,
one level up (`enemies/shade`; three deep, `elemental/particles`). What is
not inside a named layer falls to its caller, so a frame's parts add up to
its whole draw (pinned on a made-up clock). The module's docstring lists
what each such row holds: `draw` the camera shake, `element_fx.begin_frame`
and the dev overlays; `world` the scene's lists and sorts; `flat` the
painters lying on the ground; `player` the hero's buff strips and its
invulnerability ring; `enemies` each enemy's record for the ghost pass and
its frame's elemental wash and hit tint (`boss` and `player` hold their own
hit tint the same way; the wash and the tints cost nothing here, where
nothing is hit or primed, while the record is paid every frame). The buff
marks, banners, hurt flash and buff tint are the `feedback` row, and the
scenery's list building its own `scenery_list` row. The set of layers
is pinned by a test. Every other frame is drawn without the timers
(`Alternate`), the young garbage collected after every frame, bare or
timed, with no timer on; the draw and update + draw lines are the bare
frames', and the report states what the timers added against them, per
timed call, measured in place. Under the rows it prints two groups, the
terrain and the crowd's part, each as the p50 / p90 / mean of its
per-frame sum, and each frame's crowd-over-terrain ratio (`GROUPS`, from
`bb92e30`). Two probes on the tool's own error,
`python -m tools.benchmarks.layer_probes bias` and `nested`, build the same
scene (`tools/benchmarks/layer_probes.py`).

The harness also changed around it:

- **The crowd asked for.** It says when the director's cap refused part of
  the crowd: the cap is 100 + 5 per 20 s of run clock on normal, up to the
  live cap of 250, so a crowd of N needs `--elapsed (N - 100) * 4`. (Before
  this, a first 200 and 250 run here silently measured a crowd of 159 to
  175: the builder's record of those runs' output, which was not kept.)
- **The boss.** It spawns at 95 % of the run, 570 s on normal, so the
  `--elapsed 600` a crowd of 250 needs brought a boss fight into the
  measurement (the second cold critic's finding): the boss, its shade and
  the HUD's boss bar. `build` now holds the boss back unless `--boss` asks
  for it. The display line says which before the frames (`held back`,
  `due now`, `due at N s`) and the harness says it again after timing. In
  the owner's trace, the play frames (state and shown both
  `PlayingState`, no overlay opened, the filter of the 150+ row above)
  with 225 or more alive, 2,118 of them, run from 295 to 376 s of run
  clock, before any boss; 602 of them held more than 250, up to 316.

**How it was taken.** Windows renderer, the source tree's `save.json`
(`game/save.py` `DEFAULT_PATH`, not tracked: the game writes it when the
Options change). The settings that reach the draw are the display ones:
mode windowed, window 2560 × 1080, render 21:9, set with the Options
screen's Display mode row (Windowed) and Resolution row (2560 × 1080; a
21:9 size gives the 21:9 render), which give render scale 1.2 and zoom
1.797; the window always asks for vsync, and every run's display line
prints all of these, so a run on another save shows it at once. In the
save itself that is `"display": {"mode": "windowed", "render": "21:9",
"window": [2560, 1080]}` under `settings`. The Resolution row lists only
sizes that fit the desktop and the window is clamped to it, so the
desktop must be at least 2560 × 1080. Python 3.12.0, pygame 2.5.2, SDL
2.28.3 (every run's first line). In no raw file, the builder's record
(2026-10-02): the owner's primary screen reads 2752 × 1152 to Windows;
the machine is an AMD Ryzen 7 9800X3D with an NVIDIA GeForce RTX 5080 and
31 GB; and the owner's own save in the main checkout, which the game was
played on, holds the same display block. The frame trace does not record
the display, so that is the closest tie between these runs and the
trace. Seed 35,
400 dormant records (the default), the crowd packed round a hero standing
still but for the harness's 24 px jitter, 600 frames (300 timed, 300
bare, alternating), the boss held back. Each run, from the repo root in
bash (Git Bash on Windows):

    SDL_VIDEODRIVER=windows python -m tools.benchmarks.spawn_stress --live N --elapsed E --pack --layers --frames 600

with N 150 at E 300, 200 at 400 and 250 at 600, in that order, twice
(rounds a and b; `sitting7.sh` in the data folder runs them all). The
probes build the same scenes, at 150 / 300 and 250 / 600:

    SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes bias --live N --elapsed E
    SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes nested --live N --elapsed E

(`bias`: 16 blocks of 40 plain frames and 80 layered, the order
alternating; `nested`: 400 frames, 100 of each kind; the defaults.) In
PowerShell, set the driver first, `$env:SDL_VIDEODRIVER = "windows"`, then
the same commands without the prefix. Without the driver the harness
draws headless into the dummy driver's surface, which is not the cost on
screen.

Every raw output below is kept in
[`data/rnd-010.2/`](data/rnd-010.2/README.md): each run's and probe's
printout, each sitting's log and the script that ran it, and the scripts
that build the tables and every derived figure from them (`table.py`,
`derived.py`, `trace_figures.py`). Five sittings count. Sittings 1 to 3
(2026-09-30) do not (from here to the end of this paragraph, the
builder's record): they ran uncommitted, earlier versions of the tool
(`b6f7269` is the first commit of it), all without the lists' own rows;
sitting 1 also without the `hud` and `feedback` rows and with a
calibrated rather than a measured timers' cost, sittings 1 and 2 without
garbage collection between frames and with a boss fight in their 250
runs. Their conditions were mostly unrecorded; sittings 1 and 2's outputs
were not kept, and sitting 3's are left out of the data folder with them.

- **Sitting 8 (2026-10-02, 15:53 to 15:55), commit `f26e422`**: the
  `bias` probe alone (`s8_*.txt`, `sitting8.sh`), taken again after the
  fifteenth review found that sitting 7's walked the hero across the map:
  `spawn_stress.run` leaves the hero at its last jittered spot and
  reseeds its jitter each call, so the probe's 32 calls moved it steadily
  (766 px, from the jitter's arithmetic in `derived.py`). `f26e422` puts
  the hero back on one anchor before every part, and prints each side's
  enemies in view. The owner closed the game running before it
  (MechaBREAK, the builder's record); the log (`s8_meta.txt`) records a
  load of 14 % to 21 % and no process in both top lists gaining more than
  37 s (`SignalRgb`), the builder's session 12 s. `NTEGlobalGame`, still
  open as in sitting 7, is only in the end list: it gained at least 1 s,
  with no upper bound.
- **Sitting 7 (2026-10-02, 13:57 to 14:01), commit `bb92e30`**: the runs
  and the `nested` probe (`s7_*.txt`; its `bias` outputs are kept but
  superseded by sitting 8's), the conclusions' source. The owner was
  asked to close their games first (the builder's record; `deadlock`,
  which ran in sitting 6, is in neither of sitting 7's process lists).
  The log (`s7_meta.txt`) records the CPU load before each run, 20 % to
  40 %, and the top eight processes by CPU time at the start and the end.
  Of the processes in both lists, none gained more than 91 s
  (`SignalRgb`); one game process, `NTEGlobalGame`, was still open and
  gained 8 s. The builder's own session (`claude`) is only in the end
  list, so it gained at least 89 s, with no upper bound; it was editing
  files and ran short scripts on the earlier sittings' outputs during the
  sitting (the builder's record), and may be behind the slow patches
  below. `bb92e30` prints the terrain and the crowd's part as
  each frame's sum (the groups below) and the bias probe's every block
  and interval. Two of its runs, 150 b and 250 a, ran in slow patches:
  their terrain, the same work in every run, came to 7.79 and 8.22 ms
  against 6.44 to 6.54 in the other four (`derived.py` sets the line at
  7 ms). The four quiet runs are the quiet record on the current tool.
  Choosing them by their terrain makes their flat terrain no evidence by
  itself; sitting 4, chosen by nothing, is: its terrain is 6.25 to
  6.53 ms (summed) at both its crowds.
- **Sitting 6 (2026-10-02, 12:24 to 12:30), commit `da7ab7e`**: the runs
  (`s6_*.txt`, and its earlier probes, superseded). The log
  (`s6_meta.txt`) records the load, 43 % to 80 %, and a game
  (`deadlock`) that gained 1,223 s of CPU time over the sitting's 301 to
  419 s, keeping 2.9 to 4.1 cores busy on average.
- **Sitting 5 (2026-10-02, 11:40 to 11:45), commit `c53225e`**: the runs
  (`s5_*.txt`), timed by the same code as `da7ab7e` (no change to
  `draw_layers.py`, `spawn_stress.py` or `stats.py` between them). The
  load was 39 % to 68 % (`s5_meta.txt`); a game client was seen in a
  process list just after it (the builder's record, not kept in a file). Its probe outputs ran
  an earlier probe and are not kept.
- **Sitting 4 (2026-09-30, about 20:00, the builder's record from its
  output files' times), the tool of `b6f7269`** (`s4_*.txt`; no log was
  kept): its output matches that commit line for line (the
  same rows, the same printed strings, the call count printed whole), and
  the commit, 58 minutes later, says its figures were taken on the tool
  as committed. `b6f7269` computes every number as the later commits do,
  except that it collected the young garbage only after the timed frames
  (so each bare frame started right after a collection) and printed no
  groups. 150 and 250 only, two runs each. Its terrain rows, from the
  timed frames that version did not favour, sum to 6.25 to 6.53 ms, the
  same as sitting 7's quiet runs (6.36 to 6.46 summed the same way): the
  machine ran at the same speed.

Sittings 4 to 6 print no groups, so for them the terrain and the crowd's
part below are sums of their rows' p50s, which is not the p50 of a sum.
In sitting 7, which prints both, the two are at most 2.5 % apart.

**Sitting 7, `bb92e30`, the boss held back** (layer figures are p50 ms of
each layer's own time over the timed frames, so they carry the timers'
cost; the groups are the p50 of each timed frame's sum; the crowd is the
live count at the start and the end of timing, as the summons arrive):

| Run | Crowd | In view p50 | Bare draw p50 | ground | water | scenery | scenery_list | enemies | enemies/shade | ghost | world | flat | enemies calls a frame | terrain (each frame's sum) | crowd's part (each frame's sum) | crowd / terrain (each frame's) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 150 a | 135 to 175 | 147 | 10.14 ms | 3.76 | 1.30 | 1.17 | 0.20 | 2.06 | 0.41 | 0.54 | 0.45 | 0.24 | 159.3 | 6.49 | 3.52 | 0.543 |
| 150 b, slow | 135 to 175 | 147 | 12.30 ms | 4.31 | 1.56 | 1.50 | 0.30 | 2.65 | 0.51 | 0.64 | 0.58 | 0.31 | 159.3 | 7.79 | 4.49 | 0.580 |
| 200 a | 182 to 200 | 178 | 11.01 ms | 3.77 | 1.31 | 1.17 | 0.21 | 2.60 | 0.55 | 0.64 | 0.52 | 0.26 | 195.5 | 6.51 | 4.36 | 0.670 |
| 200 b | 182 to 200 | 178 | 11.09 ms | 3.74 | 1.31 | 1.19 | 0.21 | 2.70 | 0.59 | 0.68 | 0.53 | 0.27 | 195.5 | 6.54 | 4.58 | 0.711 |
| 250 a, slow | 226 to 250 | 224 | 15.92 ms | 4.66 | 1.67 | 1.60 | 0.34 | 4.51 | 0.91 | 1.14 | 0.89 | 0.37 | 243.9 | 8.22 | 7.51 | 0.913 |
| 250 b | 226 to 250 | 224 | 12.10 ms | 3.69 | 1.28 | 1.18 | 0.21 | 3.31 | 0.73 | 0.81 | 0.62 | 0.29 | 243.9 | 6.44 | 5.52 | 0.863 |

**Sittings 4 to 6**, the same scenes (the full rows are in the raw files;
`python table.py s4`, `s5`, `s6`): bare draw p50, then the terrain and
the crowd's part as sums of p50s, and their ratio.

| Run | Sitting 4 (`b6f7269`) | Sitting 5 (`c53225e`) | Sitting 6 (`da7ab7e`) |
|---|---|---|---|
| 150 a | 10.34 ms; 6.44, 3.67; 0.570 | 11.87 ms; 7.27, 4.12; 0.567 | 11.01 ms; 6.78, 3.97; 0.586 |
| 150 b | 10.46 ms; 6.45, 3.70; 0.574 | 13.73 ms; 8.49, 4.98; 0.587 | 13.93 ms; 8.55, 5.06; 0.592 |
| 200 a | | 13.05 ms; 7.29, 5.23; 0.717 | 12.36 ms; 6.99, 5.12; 0.732 |
| 200 b | | 15.10 ms; 8.48, 6.20; 0.731 | 14.60 ms; 8.03, 5.91; 0.736 |
| 250 a | 12.45 ms; 6.53, 5.71; 0.874 | 16.82 ms; 8.65, 7.86; 0.909 | 16.81 ms; 8.63, 7.89; 0.914 |
| 250 b | 11.90 ms; 6.25, 5.51; 0.882 | 16.79 ms; 8.61, 7.77; 0.902 | 17.14 ms; 8.78, 8.10; 0.923 |

The smaller rows, sitting 7, p50 at 147, 178 and 224 in view (`python
table.py s7`): the elemental sort, the elemental under-layer, the health
bars and the marks together 0.26 to 0.34, 0.29 to 0.32 and 0.39 to 0.57 ms;
`projectiles` (the enemies' shots) 0.05 to 0.09 (p90 up to 0.22); `hud`
0.09 to 0.12; `huts_list` and `villagers_list` 0.01 or less. Particles,
damage numbers and hints are 0.00 at p50 (particles up to 0.11 at p90),
since the hero does not attack.

**What it says.**

- **For a packed crowd without a fight, the enemies are the cost that
  rises with the crowd; the terrain is a larger, flat floor.** Call the
  terrain the ground, water, scenery and its list, and the crowd's part
  the enemies, the tree shade over them, the ghost pass and the scene's
  lists and sorts (`world`). On sitting 7's quiet runs, each frame's
  terrain is 6.44 to 6.54 ms at every crowd, while the crowd's part is
  3.52 ms at 147 in view, 4.36 to 4.58 at 178 and 5.52 at 224: 1.57 times
  from 147 to 224. The terrain is larger at every crowd measured and does
  not grow; the crowd's part does, and so do the small per-enemy rows
  outside it (the elemental sort and under-layer, the bars and the marks,
  together 0.26 ms at 147, 0.29 to 0.32 at 178 and 0.39 at 224 on the
  same quiet runs, and the enemies' shots).
  RND-009 put the ground bands at the alpha blitter's floor, and the
  owner keeps the terrain as it is.
- **In play the draw is higher, and that gap is not measured here.** The
  owner's trace times the draw too (`draw_ms`, play frames, `python
  trace_figures.py`): its p50 is 8.02 ms at 0 to 29 enemies in view, 10.64
  at 30 to 59, 12.11 at 60 to 89, 13.64 at 90 to 119, 13.96 at 120 to 149
  and 13.78 at 150 to 179, while the particles in those frames rise from
  a p50 of 11 to 206 and the damage numbers from 2 to 80. Matched to the
  harness's quiet runs, play frames within 7 of the same count in view
  draw 13.22 ms at 140 to 154 (125 frames) against the harness's 10.14 at
  147, 3.08 ms more, and 15.09 ms at 171 to 185 (89 frames; the trace's
  maximum is 177) against 11.01 and 11.09 at 178, 4.00 to 4.08 ms more.
  That is an estimate across different scenes: the trace's crowd is
  spread over the map, not packed; the hero fights; the terrain on screen
  differs; the machine's state during play is not recorded; and the
  trace's `draw_ms` spans the screen's clear and the debug overlay
  (`Game._render`, `game/game.py`) as well as the state's draw, which the
  harness does not time (their cost is not measured here). Even so, the
  gap is close to the whole crowd's part measured at those counts (3.52
  and 4.36 to 4.58 ms), and the frames it shows in are the ones full of
  particles and damage numbers. So the owner's read holds for the part
  that grows, the crowd's own draw, which this breakdown measured and
  ranked (the terrain stays the larger cost at every count measured); whether the combat effects the crowd brings cost as much is not
  settled by it. It is carried into RND-010.3 as an open item (below).
- **The shape holds on a busy machine too.** The terrain is the same work
  at every crowd, so it gauges how fast the machine was running, and the
  crowd's part over the terrain reads the crowd's cost with most of the
  machine's speed taken out. Two judgements sit in that: the terrain
  (blit-bound) and the crowd (more Python) need not slow alike under
  contention, and the crowd's part as timed carries timer overhead that
  grows with the crowd (below), so the ratio reads somewhat high. Sitting
  7 bounds how far contention moves it: each frame's ratio has a p50 of
  0.543 and 0.580 at 147 in view, 0.670 and 0.711 at 178, 0.863 and 0.913
  at 224; the slow run reads 6.8 % and 5.8 % above the quiet one at 147
  and 224, but the two quiet runs at 178 already differ by 6.1 %, so
  contention and run-to-run spread cannot be told apart, and 6 % to 7 %
  is an upper bound on what contention did. As sums of p50s, over all four sittings, it is 0.538 to
  0.592 at 147 (a spread of 10.0 %), 0.667 to 0.736 at 178 (sittings 5 to
  7, 10.3 %) and 0.860 to 0.923 at 224 (7.3 %). It grows 1.53 to 1.60
  times from 147 to 224 within each of sittings 4 to 6 (sums of p50s)
  and 1.59 times between sitting 7's quiet runs (each frame's ratio);
  sitting 7's a and b pairs, as sums of p50s, give 1.67 and 1.51, each a
  slow run set against a quiet one. Meanwhile the bare draw at the same
  crowd differed by up to 37.4 %, 37.1 % and 44.0 % across all runs of
  sittings 4 to 7, slow patches included
  (largest over smallest, the convention of the spreads above).
- **Per enemy:** the `enemies` row's p50 over its mean calls a frame is
  12.9 to 13.8 µs on sitting 7's quiet runs. The probe puts the nested wrappers at
  2.78 µs an enemy at 150 and 2.66 at 250 (below), without separating how
  much of that lands in the `enemies` row itself; taking all of it off or
  none of it, an enemy's own draw is 10.2 to 13.6 µs at 147 and 224 in
  view, where the probe ran (an estimate), for what is one sprite blit
  and a few lookups each.
- **Against the budget:** the bare draw alone, with the hero not attacking
  and no boss, on sitting 7's quiet runs, is 10.14 ms at 147 in view
  (61 % of the 16.67 ms), 11.01 and 11.09 ms at 178 (66 % and 67 %) and
  12.10 ms at 224 (73 %), before the update. Sitting 4 ran at the same
  speed (its terrain rows, from the timed frames, sum to 6.25 to 6.53 ms
  against the quiet runs' 6.36 to 6.46) and its bare draws agree, 10.34
  to 12.45 ms (62 % to 75 %), though its version's garbage collection may
  have favoured those bare frames. In play the draw is higher (above).
- **What it ranks, and what it does not.** Inside the crowd's part, by
  p50 on sitting 7's quiet runs: `enemies`' own row first (2.06 ms at 147
  in view, 2.60 to 2.70 at 178, 3.31 at 224), then the ghost pass (0.54,
  0.64 to 0.68, 0.81), the tree shade (0.41, 0.55 to 0.59, 0.73) and
  `world` (0.45, 0.52 to 0.53, 0.62) close together, then the elemental
  sort and under-layer, the bars and the marks, small. The top row is not
  split: every per-enemy lead listed above sits inside it, so this says
  the enemies' own draw is where to look, not which lead costs most.
  Ranking those leads is RND-010.3's first step (RND-010.D1).

**Its limits, carried into RND-010.3.**

- **The timers' cost.** Against the bare frames the timers added 0.74 to
  1.40 ms a frame in sitting 7 (0.87 to 1.63 µs a timed call, over 741 at
  150, 886 at 200 and 1,080 at 250 calls a frame). Much of it lands in
  the callers' rows, the crowd's most. Sitting 7's `nested` probe
  measured the part the shade, bar and marks wrappers add, on the same
  scenes, with its own count of enemies drawn: at 150, 0.42 ms to
  `enemies` with its nested rows (2.65 against 2.23 ms; 151.7 drawn a
  frame, 2.78 µs an enemy) and 0.33 ms to the whole draw; at 250, 0.64 ms
  to the rows (4.30 against 3.66 ms; 240.9 drawn, 2.66 µs an enemy) and
  0.65 ms to the whole draw, of every timer's 0.79 and 1.09 ms. The root's
  timer alone added nothing measurable (10.16 against 10.08 ms at 150,
  12.10 against 12.19 at 250), which also shows the probe's resolution:
  p50s over 100 frames a kind move by about 0.1 ms on their own, so at
  150 the rows' 0.42 ms and the whole draw's 0.33 ms (a part larger than
  its whole) agree within it. Set against the quiet runs' crowd's part
  (3.52 ms at 150, 5.52 at 250, each frame's sum as timed), the nested
  wrappers are 9.4 % to 11.9 % of it at 150 and 11.6 % to 11.8 % at 250;
  against that part with the overhead taken off, 10.3 % to 13.5 % and
  13.1 % to 13.3 %. (The probe's own rows, `enemies` with the shade, bars
  and marks, are not quite that set; most of the overhead lands in
  `enemies`, which both share.) Each enemy wrapper's own bookkeeping,
  landing in `world`, comes on top and is not separated; `world` also
  holds the scenery items' wrapper closures (about 72 scenery calls a
  frame) and the scenery's per-terrace filtering, so its row, and the
  close order of the ghost pass, the shade and `world`, carry overhead
  that is not the crowd's. The terrain's rows carry barely any of it. Candidates are timed old against new
  without the timers (the constraint above), and this breakdown only aims
  them.
- **The `--layers` headline against the plain `--render` one.** Sitting
  8's `bias` probe put plain and layered blocks side by side over one
  crowd, the hero on one anchor, the order alternating (ABBA) so a drift
  inside a block falls on each side alike. It compares what the two
  commands report, so it covers the alternation and the garbage
  collection `--layers` adds after every frame together; two effects that
  cancelled would not show. Its crowd is the runs' scene a little later:
  over the probe's 1,920 frames more summons arrive than over a run's
  600, so it had 161 enemies in view at p50 at `--live 150` (the runs:
  147) and 228 to 230 at `--live 250` (the runs: 224). At 150 the bare
  frames' draw p50 was 9.86 ms against the plain frames' 9.91 (640 frames
  each, both 161 in view); the 16 blocks' bare minus plain p50s put the
  median difference between -0.22 and +0.22 ms (a 97.9 % sign-test
  interval, the 4th smallest to the 4th largest of 16). At 250, 11.62
  against 11.62, the median between -0.13 and +0.24 ms. The intervals
  bound the median of the blocks' 40-frame p50 differences and treat the
  blocks as independent; they are not the 300-frame headline's bias
  itself. Taking them as its measure, a judgement: no sign of a bias, and
  any there is sits within about a quarter of a millisecond either way at
  both crowds. (Sitting 7's `bias` outputs, from the walking hero, read
  about 0.5 ms below its runs' bare draws; they are not used.)
- **The packed crowd is past what the owner played.** In the owner's
  trace, the play frames with 150 or more alive (4,557) had 90 enemies in
  view at p50, 173 at p99 and 177 at most; none had 200. The harness's
  147 in view at 150 is near that p99, its 178 at 200 at the trace's
  maximum, and its 224 at 250 beyond anything played: the packed runs are
  the worst case of a crowd, not its usual frame.
- **No fight, and the open item it leaves.** The hero does not attack, so
  there are no particles, damage numbers, hit tints or damaged health
  bars, where the owner's trace has 144 to 206 particles and 59 to 80
  damage numbers at p50 with 120 to 179 enemies in view, and draws 3.08
  to 4.08 ms more than the harness at matched counts (an estimate across
  scenes, above). Open for RND-010.3, for the owner: whether to measure a
  fighting scene before the candidates are chosen, or to take the crowd's
  own draw first as planned. The harness can already stage one:
  `--elements` infuses three weapons and turns the hero's attacks on
  (`spawn_stress.infuse`), and `--element-rate` and `--cascade` add hits
  and chained reactions; `--layers` runs with all three. No sitting here
  used them. (Settled since: RND-010.3 measured the fight, with no answer
  from the owner, as the review recommended. See "RND-010.3: Results".)
- **Taken before RND-011 reached this branch.** Every sitting here ran
  before `main` (RND-011) moved the elemental aura shed out of the draw
  and into the update, on its own seeded stream; the branch took that in
  with the merge of 2026-10-03. In these scenes no enemy is primed, so
  nothing sheds, and the elemental rows are small (on sitting 7's quiet
  run at 224 in view, `elemental_sort` 0.13 ms and `flat/elemental` 0.14
  at p50); the crowd's and the terrain's groups contain neither. The tool's tests now draw
  without holding the shed still, since the draw no longer draws random
  numbers.
- **The crowd drifts.** Bodies fall asleep in the warm-up and summons arrive
  while timing (135 to 175 at `--live 150`), as the harness's crowd line
  reports.
- **Slow patches.** Even in sitting 7, two of six runs ran slow for part
  of their frames; the quiet record rests on one run at 147 and one at
  224 in view (two at 178), each 300 timed and 300 bare frames, and on
  sitting 4 agreeing with them.

## RND-010: Decisions

- **RND-010.D1 (owner, 2026-10-02):** ranking the leads inside the
  enemies' own draw moves from RND-010.2 to RND-010.3, as its first step.
  RND-010.2 ranks the crowd's layers and leaves `enemies`' own row whole.
  The leads in it are timed old against new, not wrapped: an enemy's
  share of the exclusive `enemies` row (its own draw, without the shade,
  bars and marks) is about 10 to 14 µs and a timed call costs about 1 µs
  in place, so a wrapper per lead would be a large share of what it
  measures (a judgement from those two figures; the leads were not timed
  then; RND-010.3 timed them in isolation, and three of them as
  variants, see its results).
- **RND-010.D2 (owner, 2026-10-06): the wash cache is an LRU of 1536.**
  The owner chose the size RND-010.3 timed, not 1024 and not a cap in
  bytes. The tint cache was not part of the choice and stays as it is.
  RND-010.4 builds it. The question as it was put: how much memory the
  sprite caches may hold, which sets RND-010.4's caps. In the replay of
  the saturated fight at 250 (sitting 5), today's wash cache held at most
  28.2 MB. The LRU of 1536, the one timed, held at most 80.6 MB; one of
  1024 held 55.5 MB, for a predicted 1.68 ms saved where 1536 predicts
  1.83 (1024 is not timed). A tint LRU of 256 held 16.5 MB against
  today's 8.5. Those are peaks seen in one seed's fight, not bounds: a
  cap counts copies. The largest frame a regular enemy can be washed in
  at the sittings' zoom is 0.14 MB (bear; bosses are never washed), so
  today's 512 could hold up to 71.9 MB, 1024 up to 143.8 MB and 1536 up
  to 215.8 MB. The tint cache also takes the boss's and the hero's
  frames, up to 0.69 MB, so a tint cap of 256 could hold up to 175.5 MB.
  A cap in bytes is the other way to set it. The ghost cache is in none
  of these: its 128 entries keep their source frames (washed or tinted
  copies included) alive beside their ghosts, up to 175.5 MB whatever the
  caps, so it does not change between the choices here. The web build's memory headroom
  is not measured.

## RND-010: Review of 2026-10-03 (read-only)

A review against the owner's requirement (a stable 60 fps with over 200
enemies on screen) measured the harness at 100 and 200 live, spread and
packed, the raw pygame blit floor, and the garbage collector, and ranked
the exact fixes for the draw and the update. Its findings, numbers, the
ranked plan and the owner decision it ends in are in
`../plans/crowd_performance_plan.md`. It was written on `main` while
RND-010.2 ran on its own branch: that plan's step 4.0 is RND-010.2, done
above, except for the plan's two appendix probes (`blit_floor.py`,
`gc_probe.py`), which moved under `tools/benchmarks/` with RND-010.3.2.
The work was to resume at the plan's 4.1 onward as RND-010.3 and after,
with RND-010.D1's ranking inside the enemies' own draw and the open item
of a fighting scene (above) taken first. RND-010.3 did those two, and
its results set a new order: RND-010.4 is the plan's 4.13, not 4.1. The
whole sequence, 4.1 and the update tasks included, is the table under
the results' "The order for RND-010.4 onward".

## RND-010.3: The leads inside the enemies' own draw (plan, 2026-10-04)

RND-010.2 ranked the crowd's layers and left `enemies`' own row whole
(RND-010.D1): an enemy's own draw is about 10 to 14 µs, and every lead
read from the code sits inside it. Its work is of two kinds, and each is
measured the way it can be without wrappers:

- **CPU steps**, which touch no pixels: the generated forwarder
  (`core/state.py`, `_delegate`), the spawn-veil check, `rig_frame`
  (`rendering.py`), `anchor_for`, `sprite_drop`, `world_to_screen`
  (`systems/camera.py`), `aura_colour`, and in `actor_items` the lambda
  and the terrace lookup per enemy. Each is called in isolation on the
  live packed crowd, with the arguments the frame would give it, many
  times over, and its per-call cost times its calls a frame gives its
  share of the row. Machine speed moves these as it moves everything, so
  they are reported beside the same sitting's own row.
- **Pixel work**: the sprite's blit, and the `drawn.copy()` a shaded body
  pays every frame for the ghost queue (`rendering.py`, `_blit_character`).
  These are timed as throwaway variants of the draw, each one pixel-
  identical to the original (a test compares whole frames), against the
  unmodified draw in alternating blocks on one scene, as the bias probe
  does. The same variant machinery times the candidates the ranking puts
  on top: a variant is the "throwaway version of the change" the plan
  asks for before anything is built.

Also under RND-010.3, the plan's step 4.0 leftovers and the open item:

- `blit_floor.py` and `gc_probe.py` from `crowd_performance_plan.md`'s
  appendix A, under `tools/benchmarks/` with tests (the plan's 4.0);
- one sitting of the draw by layer with the hero fighting
  (`--layers --elements`), at 150 and 250, so the ranking covers the
  combat effects the owner's trace is full of. The owner was asked and
  did not answer before the work began; it is taken as the review
  recommended, and costs one on-screen sitting.

Every sitting keeps its raw outputs under `data/rnd-010.3/`, as
RND-010.2's do.

## RND-010.3: Results (2026-10-06)

Five sittings on the owner's machine, on screen at 2560x1080, at 150 and
250 alive packed, seed 35, with the owner away from the machine (the
owner's word; see the README for what the logs show). The raw
outputs, the scripts as run and `derived.py` are in `data/rnd-010.3/`,
and the README there lists what ran where. `derived.py` prints every
figure below unless it is marked as a constant or a tool's default.

- **Sitting 1** ran the planned probes and a first fight. The fight
  showed a lead none of the probes covered.
- **Sitting 2** probed that lead with a tool built for it.
- **Sittings 3 and 4** answered a first review.
- **Sitting 5** answered a second one. It ran everything the results
  compare, in one sitting at one commit (`59cd622`): the quiet draw and
  the fight in ABBA order (quiet, fight, fight, quiet), so a drift falls
  on both alike; the caches' replay; the `wash_lru` timing; and the blit
  floor.

Every measured comparison below is within sitting 5, except the leads,
the three CPU variants and the collector's default against frozen, which
are sitting 1's alone. Where the order
for RND-010.4 weighs a sitting 1 figure against a sitting 5 one, or the
game's blit against the floor's, it compares orders of magnitude, by
judgement, and says so. The other sittings are context. Their
absolute times moved with the machine's state: sittings 1 and 2's fights
drew 0.6 to 3.0 ms more than sitting 5's at the same counts.

### The fight

`spawn_stress --pack --layers --elements` is the saturated fight, the
worst plausible one by judgement, not an average one. Every enemy is
primed at the start (for 600 s, with a billion HP: constants in
`spawn_stress.infuse`) and three infused weapons fire. By the end, 55 of
150 live (37 %) are still primed, and 176 of 247 (71 %). What makes up
the rest is not measured. `infuse` primes only the crowd present at its
call, and at least 16 and 22 arrived later (those counted while timed;
any that arrived in the warm-up are not counted). Reactions consume
auras and can lock the slot, and the hero's infused hits prime any enemy
with an empty slot, late arrivals included, with auras that expire in
seconds.

The billion HP also shapes the bars, two ways:
- Nothing dies, and a bar shows on any enemy below full health, so every
  enemy hit once keeps its bar for the rest of the run, where in play a
  hurt enemy dies. More bars than play: this leans the bars high.
- A billion HP clamps every bar to its widest (84 px) with its fill near
  full, so every bar is the same cached surface. Play's bars vary in
  width and fill: this leans the bars low.

The net direction is not measured. The damage numbers lean high against
play for another reason: every enemy is primed and three weapons fire,
the saturated scene itself.

The two sides do not hold the same crowd. Both start from 135 alive (at
150) and 225 (at 250), but more arrive in the quiet runs: they end at 175
and 250, the fights at 150 and 247. The quiet runs also have more in view:
147 against 139 at 150, and 224 against 222 at 250. So the quiet side
draws a few more enemies, and what the fight is shown to add is
understated by that much. By sitting 5's own per-enemy costs (the crowd's
group on either side, or the fight's bare draw less its terrain, over
the count in view), the 8 more in view at 150 are worth 0.17 to 0.37 ms,
and the 2 at 250 are worth 0.04 to 0.11 ms.

Sitting 5, p50, two runs a side. The range under "Added" runs from the
lower fight less the higher quiet run to the higher fight less the lower
quiet run:

| | Quiet | Fight | Added |
|---|---|---|---|
| 150: bare draw | 9.02 / 8.86 ms | 12.13 / 12.07 ms | +3.16 (+3.05 to +3.27) |
| 150: update + draw | 16.84 / 16.66 ms | 19.52 / 19.49 ms | +2.75 |
| 250: bare draw | 10.69 / 10.58 ms | 17.51 / 17.45 ms | +6.85 (+6.76 to +6.93) |
| 250: update + draw | 22.90 / 22.77 ms | 29.47 / 29.30 ms | +6.55 |

The update falls a little in every pair (−0.37 to −0.15 ms). A candidate
cause, not measured: the fight holds fewer bodies alive (25 fewer at the
end at 150, 3 at 250). The terrain rises a little in every pair (+0.01 to
+0.15 ms).

What the fight adds, by layer (the fights' mean over the quiet runs'
mean):

| Layer | Added at 150 | Added at 250 |
|---|---|---|
| `flat/elemental` (auras, status marks, areas, motes under the bodies) | +1.36 ms | +2.71 ms |
| `enemies` (an enemy's own draw) | +0.46 ms | +2.12 ms |
| `enemies/hpbar` (bars appear once hurt) | +0.55 ms | +0.51 ms |
| `numbers` (damage numbers) | +0.24 ms | +0.29 ms |
| `elemental/particles` | +0.08 ms | +0.24 ms |
| `ghost` | +0.20 ms | +0.22 ms |

The `(all layers)` row adds +3.30 ms at 150 and +6.82 ms at 250. The
`enemies` row grows from +0.46 to +2.12 ms between 150 and 250, while
the crowd in view grows only from 139 to 222. That is the lead the next
section follows.

### The lead the fight found: the wash cache thrashes

A primed enemy is drawn washed in its element (`element_fx.washed`), and
a hurt one tinted red (`rendering.hit_tinted`). On a miss, `washed` makes
two copies of the frame and keeps one; `hit_tinted` makes one and keeps
it. Each cache is a dict that empties itself whole when full: 512 washed
frames, 128 tinted.

`sprite_caches.py` records every request a fight's draw makes, over 900
frames, and replays them through two policies: the game's, and an LRU.
It reports:
- the misses over frames 300 on;
- the most memory the replayed cache held, each copy's rows times its
  height.

Two tests back it:
- one pins the replay to the game's own `washed` and `hit_tinted`, frame
  by frame;
- one pins its premise: two builds of one scene ask the same of a
  churning cache and of a full one.

| 250 fighting | Misses a frame | Worst frame | Held at most |
|---|---|---|---|
| wash, today (512, emptied when full) | 21.98 | 137 | 28.2 MB |
| wash, LRU 1024 | 2.07 | 11 | 55.5 MB |
| wash, LRU 1536 | 0.31 | 3 | 80.6 MB |
| tint, today (128) | 1.69 | 26 | 8.5 MB |
| tint, LRU 256 | 0.39 | 5 | 16.5 MB |

The fight asks for 159 washed frames a frame. They come from 1,665
distinct ones: (frame, element) pairs, whose make-up is not broken down.
Today's cap holds 0.31 of them. With 21.98 misses a frame, the cache
emptied 26 times in 600 frames, about every 23.

What each operation costs, timed over five passes, each on a fresh cache:

| Operation | Cost |
|---|---|
| a miss | 84.1 µs (80.7 to 102.4) |
| a hit | 0.19 µs |
| emptying a full cache of 512 | 0.07 ms |

From those costs the replay predicts:
- today's wash cache at 250: 1.85 ms a frame, with a worst frame of
  11.5 ms (the emptying itself is 0.003 ms of the 1.85);
- today's tint cache: 0.13 ms.

The prediction assumes every miss costs the same: the median pass's mean
cost a distinct frame, each frame washed once in a pass. The misses fall
more often on some frames than others, and a large frame costs more to
copy than a small one, so the weighting is an assumption, not measured.

Those are the same order as the `enemies` row's +2.12 ms in the fight.
This is a prediction, not a measurement: nothing here times the two
caches inside the frame. The replay's scene also ended with 237 alive,
against the fight's 247, end counts only; the replay averages frames
300 to 900 and the fight its own 600, and the replay's count in view is
not recorded. Fewer bodies wash less, so this likely leans the
prediction low against the `enemies` row.

At 150 the fight asks for 52 a frame from 1,027 distinct frames, and 3.41
of those miss. The replay prices that at 0.28 ms a frame for today's
cache, and at 0.24 ms saved by the LRU of 1536.

Timed as a throwaway variant: `draw_variants --elements --variants
wash_lru`, an LRU of 1536 (`draw_variants.WASH_LRU_CAP`), the tool's
default 16 ABBA blocks of 40 frames (640 frames a side), the hero on one
anchor.

| `wash_lru`, sitting 5 | 150 fighting | 250 fighting |
|---|---|---|
| Draw mean, off / on (pooled, 640 frames a side) | 12.84 / 12.26 ms | 16.82 / 15.54 ms |
| The 16 blocks' mean savings: their median, and its 97.9 % sign-test interval | −0.30, −1.04 to +0.11 ms: not resolved | −1.27, −1.56 to −0.74 ms: **faster** |
| The 16 blocks' p50 savings: their median, and its interval | −0.05, −0.94 to +0.42 ms: not resolved | −0.95, −1.57 to −0.45 ms: **faster** |
| p90, off → on (pooled) | 14.87 → 13.32 ms | 19.61 → 18.08 ms |
| p99, off → on (pooled; one figure a side, no interval) | 19.63 → 18.05 ms | 28.87 → 23.31 ms |

At 250, the intervals exclude zero; it is the only variant so far whose
do. At 150 the saving is not resolved. Sitting 2 measured it at another
commit: at 250 the blocks' median p50 saving was 1.08 ms (interval 0.65
to 1.61), and at 150 again not resolved.

How these are read: a block's figure is its on part's minus its off
part's, so a saving is negative. The "median" of the 16 is
`stats.percentile`'s nearest index, the 9th smallest, not the mean of
the 8th and 9th. The interval is the sign test's 4th to 13th of 16, which
treats the blocks as independent. The pooled rows put all 640 frames of
a side together. From here on, savings are quoted as positive numbers.

The replay predicts 1.83 ms saved at 250. Measured against the median of
the blocks' mean savings (1.27, interval 0.74 to 1.56), the gap is 0.27
to 1.09 ms; against the pooled mean (1.28), it is 0.55 ms. At 150 the
replay predicts 0.24 ms saved. The blocks' median mean saving is 0.30 ms
(interval −0.11 to +1.04), so the gap there is −0.80 to +0.35 ms, which
includes zero: the measurement at 150 is consistent with the prediction.
The pooled mean saving at 150 is 0.58 ms, one figure with no interval.
At 250 the gap is open. Candidates, none of them measured, each with the
way it leans:
- a miss may cost less inside the frame than in the timing loop (the
  prediction too high);
- the variant's LRU begins nearly empty, since only `identical`'s two
  draws filled it, and the replay's LRU figure leaves out its own first
  300 frames. An estimate of that fill: the replay's 1,665 distinct
  frames at the median miss is 140 ms, 0.22 ms over the 640 frames on,
  or 170 ms and 0.27 ms at the slowest pass's miss. The timed run may ask
  for more distinct frames than the replay saw, and an LRU of 1536 never
  holds them all at once. This leans against the variant;
- each cache stands still while the other side runs: the game's through
  every on part, the LRU through every off part, while the fight moves
  on. A cache resuming stale holds frames no longer asked for. For the
  game's cache that means emptying sooner and missing more, which leans
  toward the variant, most at 150, where the game's cache empties only
  about every 150 frames against every 23 at 250. For the LRU it matters
  only where it cannot hold every frame asked for: at 250 (1536 against
  1,665 distinct) its stale entries cost it misses, which leans against
  the variant; at 150 it holds all 1,027;
- the variant's miss swaps in an empty dict for the game's `washed` to
  fill, an allocation the game's miss does not make (against the
  variant), and its hit path, an `OrderedDict` lookup and `move_to_end`,
  is not timed;
- the ghost cache (`TerrainRenderer._ghost_of`, which empties itself at
  128) keys on the washed copy's identity. It serves an unshaded body
  behind obstacle art (a shaded body's ghost is never cached:
  `_blit_character` records it uncacheable). So a washed copy remade is
  a ghost remade too, for such a body, and the LRU spares both. The
  replay counts only the wash, so this leans the measured saving above
  the prediction. The two sides also share that one ghost cache: an on
  part inherits ghosts keyed on the game's copies, useless to the LRU's,
  so its ghosts start cold, which leans against the variant. The net
  direction is not measured;
- the timed blocks cover the fight's frames 0 to 1,280 after the warm-up
  (16 blocks of two 40-frame parts, both the tool's defaults), and the
  replay covers frames 300 to 900, so they average different stretches
  of it. If the primed share falls as the fight goes on (only its two
  ends are known: all primed at the start, 37 % and 71 % at the end),
  the blocks before frame 300 wash more than the replay's frames and
  those after 900 wash less. The net direction is not determined.

The variant gives the same pixels as the game's cache: a hit returns the
held copy, and a miss makes the copy the game would. The sitting's
whole-frame check drew the variant twice, filling its cache and then
drawing from it, and both frames matched the game's byte for byte. The
check's scene did not reach the cap, so no eviction was drawn there; the
unit tests check pixels after one.

### Inside an enemy's own draw (no fight)

`draw_leads` timed each piece in isolation over the drawn crowd, in 200
rounds (sitting 1):

| Piece | At 150 (135 drawn) | At 250 (225 drawn) | Share of `one_enemy` (150 / 250) |
|---|---|---|---|
| `one_enemy`, whole | 13.47 µs, 1.82 ms | 12.95 µs, 2.91 ms | |
| sprite blit | 7.36 µs, 0.99 ms | 7.18 µs, 1.62 ms | 54.6 / 55.5 % |
| shade walk | 1.97 µs, 0.27 ms | 1.83 µs, 0.41 ms | 14.6 / 14.1 % |
| `rig_frame` | 1.43 µs, 0.19 ms | 1.44 µs, 0.32 ms | 10.6 / 11.1 % |
| every other piece, summed | 0.21 ms | 0.34 ms | 11.5 / 11.5 % |
| the glue between them | 0.16 ms | 0.23 ms | |
| the scene's per-enemy steps (cull, terrace, lambda, forwarder) | 0.09 ms | 0.16 ms | outside |

Two biases sit in these figures, neither one quantified:
- each piece ran warm and alone, over and over on the same arguments,
  which is kind to caches and branches, so a piece reads low against its
  cost inside the frame;
- sitting 1 ran at 23 to 48 % CPU load, against 3 to 22 % in sitting 5,
  and its fights drew 1.8 to 1.9 ms more at 150 than sitting 5's (2.9 to
  3.0 at 250), so its
  figures may read high.

The ghost copy, the one per-frame `copy()` the plan named, runs only for
the two shaded bodies in this scene and costs 0.01 ms. It gets no
variant, under the condition RND-010.3.4 set.

How close the sprite blit is to pygame's own floor is not shown here.
`blit_floor` (sitting 5), with the screen fill timed alone (0.37 ms) and
taken out, puts one 112 px sprite at 6.97 to 8.60 µs a blit. The game's
blit is 7.18 to 7.36 µs, but over the crowd's own rigs (the largest a
regular enemy wears is 203x173 px at this zoom), and in sitting 1. The
floor also places its sprites anywhere on the surface, so some are
clipped at the edges, which makes it read low. Different sittings and
different sprites, so the two are of the same order and no more is
claimed.

The three CPU variants (sitting 1, quiet) resolved none:

| Variant | 150: p50 median, interval | 250: p50 median, interval |
|---|---|---|
| `rig_frame_cached` | +0.07, −0.34 to +0.40 ms | −0.17, −0.81 to +0.63 ms |
| `world_bucketed` | −0.05, −1.73 to +2.19 ms | −0.01, −0.89 to +0.29 ms |
| `forwarder_bypassed` | −0.61, −2.85 to +1.61 ms | +0.18, −0.45 to +0.57 ms |

In isolation `rig_frame` costs 0.19 ms a frame at 150 and 0.32 at 250.
The lambda and the forwarder together cost 0.03 ms at 150 and 0.05 at
250.

`world_bucketed` removes `draw_world`'s filtering of the lists for each
terrace, which `draw_leads` does not time. That work lies inside the
`world` and `scenery_list` rows of the layer tool, so its ceiling is not
measured here. Those rows read 0.38 to 0.39 and 0.16 ms quiet at 150 in
sitting 5, a different sitting from the variant's.

### The appendix probes

- `gc_probe --pack` (sitting 1, 200 live, the tool's default 600
  frames):
  - With the default collector it ran one gen-2 collection, of 8.6 ms.
    Frozen, it ran none.
  - The frozen run's tail was worse: p99 38.51 against 33.74 ms, and max
    59.70 against 41.38.
  - The two ran one after the other, not interleaved, so freezing shows
    no gain here yet.
- `blit_floor` at 2560x1080 (sitting 5): the fill alone takes 0.37 ms.
  With the fill:

  | Sprites | Alone | With a shadow and a bar |
  |---|---|---|
  | 100 | 1.23 ms | 1.34 ms |
  | 200 | 1.86 ms | 2.10 ms |
  | 300 | 2.46 ms | 2.75 ms |

### The order for RND-010.4 onward

1. **RND-010.4: the wash cache as an LRU.**
   - It is exact, and helps only where enemies are primed: a fight.
   - It is resolved only at 250 alive in the saturated fight. There, the
     blocks' median mean saving is 1.27 ms (97.9 % interval 0.74 to
     1.56; pooled, 1.28 ms), and the pooled p99 falls from 28.87 to
     23.31 ms (one figure a side, no interval).
   - At 150 alive it is not resolved.
   - `draw_variants` prints no count in view. The fight at the same
     `--live` shows 222 and 139 in view. The owner's trace never shows
     more than 177 (above), so whether it moves the trace's rows is not
     shown.
   - It costs memory. In the replay at 250, the LRU of 1536 (the one
     timed) held up to 80.6 MB, against 28.2 MB for today's cache. An
     LRU of 1024 held 55.5 MB, and the replay predicts 1.68 ms saved for
     it against 1536's 1.83; it is not timed.
   - Neither is a bound. A cap counts copies, not bytes. The largest
     frame a regular enemy can be washed in at this zoom is 0.14 MB
     (bear, 203x173; bosses are never washed). So today's 512 could hold
     up to 71.9 MB, 1024 up to 143.8 MB and 1536 up to 215.8 MB. A cap
     in bytes would bound it directly; that is a design choice for
     RND-010.4.
   - The ghost cache is in none of these figures. Its 128 entries each
     keep a source frame alive beside its ghost, and a source can be a
     washed or tinted copy the caches above have already dropped. That
     is up to 175.5 MB (128 x 2 x 0.69 MB) whatever the caps, so it does
     not change between the choices in D2.
   - The tint cache as an LRU of 256 (16.5 against 8.5 MB held) is
     predicted at 0.10 ms. That is below what a sitting resolves, so it
     goes in only if the owner wants the two caches alike. It also takes
     the boss's and the hero's frames, up to 0.69 MB a copy (pig_rider,
     467x367), so a full 256 could hold up to 175.5 MB.
   - The memory is the owner's call (RND-010.D2, open).
2. **The elemental under-layer in a fight.** It is the largest layer the
   fight adds (+1.36 / +2.71 ms); plan 4.5 covers it.
   - First split `draw_under` (auras, status marks, areas, motes) the
     way RND-010.2 split the draw.
   - Then time the candidates as variants.
3. **The shade walk**: plan 4.4's first half, the skip where no shadow
   falls. In isolation (sitting 1) it is 0.27 / 0.41 ms. Sitting 5's own
   `enemies/shade` row is 0.38 / 0.61 ms quiet and 0.43 / 0.67 ms in the
   fight, against the fight's bars at 0.58 / 0.56 ms (at 150 / 250). By
   size, item 4 as a whole (bars and numbers) is larger at both counts.
   The shade walk ranks above it by judgement alone, on how often it
   runs: in every frame, quiet or not, where the bars and numbers appear
   only once enemies are hurt.
4. **Bars and damage numbers in a fight.** The fight adds +0.55 / +0.51 ms
   of bars and +0.24 / +0.29 ms of damage numbers (at 150 / 250). The
   numbers lean high against play; the bars lean both ways (above).
   - Damage numbers fall under plan 4.6.
   - The bars had no plan task. Plan 4.6 now carries them, to be split
     and timed first.
5. **GC freeze** (plan 4.2): the 8.6 ms spike is real but rare, and the
   one frozen run was no better. Re-time it interleaved before building.
6. **The blit batch** (plan 5.1): what a batch would save, the Python
   call per blit, is not measured, so it comes last among these, by
   judgement.
7. **The CPU variants:** none resolved a saving. By judgement, not by
   measurement, they are not worth building alone.
   - In isolation at 250, `rig_frame` is 0.32 ms, and the lambda and the
     forwarder 0.05 together.
   - The bucketed world's ceiling is not measured (see above).

The order as a whole is a judgement. It weighs the measured sizes above
with how often each cost occurs (every frame, or only in a fight), and
the sizes come from different sittings where noted.

Its scope is the draw RND-010.3 measured, plus the collector (item 5),
which sitting 1 measured on the side. The plan's other tasks were not
measured here: 4.1 (`report_debug`, the plan's next task before this
order), the update tasks 4.7 to 4.12, and 5.2 to 5.4. RND-010.4 is 4.13
because it is the one exact win measured, not because those were
dropped.

**The whole sequence, one task an ID, as proposed (a judgement; the
owner may reorder it). Only RND-010.4 is a measured winner; the
entries marked "measure first" are split and timed before anything is
built:**

| ID | Plan step | What |
|---|---|---|
| RND-010.4 | 4.13 | the wash cache as an LRU, once D2 is settled (done 2026-10-07) |
| RND-010.5 | 4.1 | `report_debug` only with the overlay on (done 2026-10-07: 0.016 to 0.026 ms a frame, 3 to 13 % of the plan's estimate) |
| RND-010.6 | 4.5 | measure first: the elemental under-layer, `draw_under` split, then variants |
| RND-010.7 | 4.4 | the shade walk's skip (its first half; the ghost copy is 0.01 ms here) |
| RND-010.8 | 4.6 | bars (measure first), damage numbers, particles culled and without copies |
| RND-010.9 | 4.2 | measure first: the collector, re-timed interleaved before it is built |
| RND-010.10 to RND-010.15 | 4.7 to 4.12 | the update tasks, one each, in the plan's order |
| RND-010.16 to RND-010.19 | 5.1 to 5.4 | the second stage, one each, the blit batch first |
| RND-010.20 | 4.3 | one drawable list; its ceiling is not measured, only bounded by the `world` and `scenery_list` rows (0.55 / 0.54 ms quiet at 150, 0.66 / 0.68 at 250) |

Item 7's other variants have no place in it. `rig_frame` cached and the
forwarder bypassed are 0.32 and 0.05 ms in isolation at 250, by
judgement not worth building alone. 4.3 goes last, not out: its bound is
of the same order as items 3 and 4, but its variant showed nothing it
could resolve.

Two things the plan for RND-010.3 (above) promised were not done:
- The leads were to be reported beside the same sitting's own `enemies`
  row. Sitting 1 ran no quiet `--layers` run, so they stand alone.
- The sprite blit was to be timed as a throwaway variant. No exact
  variant of a blit exists short of plan 5.1's batch, which is a build,
  not a throwaway, so none was made.

Even with all of this, the saturated fight at 250 stays well over the
budget. In sitting 5 its update and draw take 29.30 to 29.47 ms, and
these fixes reach a few milliseconds of that. Closing the rest is the
plan's §6 decision, which is still the owner's.

## RND-010.4: The wash cache as an LRU of 1536 (plan, 2026-10-06)

The owner settled RND-010.D2 on 2026-10-06: an LRU of 1536, the size
RND-010.3 timed. This is the plan's 4.13 and the first row of RND-010.3's
sequence. The tint cache is not part of it.

- **The change** (`game/states/playing/visual/elements/__init__.py`):
  - `_WASH_CACHE` becomes an `OrderedDict` with `_WASH_CACHE_CAP = 1536`;
  - a hit moves its entry to the newest end;
  - a miss into a full cache drops only the entry used longest ago,
    where the dict it replaces emptied itself whole at 512;
  - an entry found under the key for another frame is replaced in
    place and drops nothing else (the entry keeps its frame alive, so
    this cannot happen while it stands; the check is kept as it was).
- **Exactness:** pixel-identical, since a hit returns the held copy and
  a miss makes the same copy as before. Pinned two ways:
  - in `tests/render/test_element_colours.py`, on the cache's own
    behaviour (the cap, the order of drops, a refresh, a re-wash's
    pixels, a stale entry);
  - in `tests/render/test_elemental_draw_cost.py`'s primed, packed seed
    35 fight, on a whole frame: drawn from a warm cache, an empty one,
    and one of 3 that drops entries while the frame is drawn, the frame
    is one picture byte for byte.
- **The probes follow the game.** They swap the cache for one of its own
  kind, and the replay's test now matches the wash cache against the
  LRU policy and the tint cache against emptying whole.
- **Measured before and after,** as the plan's §4 asks for each task:
  - one on-screen sitting, `main` against this branch, in ABBA order at
    150 and 250 packed with the hero fighting, and quiet at the same
    counts (and then: 200 added, as the plan's §4 names 150, 200 and
    250);
  - `sprite_caches` on this branch, whose header should name the game's
    cap as 1536; it prints both policies at every cap, and the game's
    wash cache is now its LRU column.
  
  The owner asked to be asked before the sitting runs.

## RND-010.4: Results (2026-10-07)

The owner freed the machine for the sitting (2026-10-07, 10:48 to 10:57).
It ran `main` (`2c6865a`, the wash cache emptying whole at 512) against
this branch (`f4f0079`, the LRU of 1536) in one sitting, in ABBA order
(before, after, after, before), at 150, 200 and 250 packed, seed 35. It
ran each count with the hero fighting and then quiet. The raw outputs,
the script and `derived.py`, which prints every figure below, are in
`data/rnd-010.4/`.

With the hero fighting, p50 ms. "Change" is the two afters' mean less
the two befores'; the range runs from the lower after less the higher
before to the higher after less the lower before:

| | Before | After | Change |
|---|---|---|---|
| 250: bare draw | 17.93 / 18.27 | 16.16 / 16.24 | −1.90 (−2.11 to −1.69) |
| 250: `enemies` row | 5.31 / 5.40 | 3.72 / 3.72 | −1.64 (−1.68 to −1.59) |
| 250: update + draw | 30.30 / 30.64 | 28.66 / 28.73 | −1.77 (−1.98 to −1.57) |
| 250: draw p90 | 22.07 / 23.65 | 18.89 / 18.43 | −4.20 (−5.22 to −3.18) |
| 250: draw p99 | 32.36 / 33.14 | 29.95 / 30.17 | −2.69 (−3.19 to −2.19) |
| 200: bare draw | 16.23 / 15.89 | 15.42 / 14.99 | −0.86 (−1.24 to −0.47) |
| 200: `enemies` row | 3.99 / 3.83 | 3.14 / 3.07 | −0.81 (−0.92 to −0.69) |
| 150: bare draw | 14.43 / 15.09 | 14.55 / 15.85 | +0.44 (−0.54 to +1.42): not resolved |
| 150: `enemies` row | 2.81 / 2.93 | 2.69 / 2.92 | −0.07 (−0.24 to +0.11): not resolved |

- **At 250 and 200, every pairing is faster.** The saving sits in the
  `enemies` row, an enemy's own draw, where the washes happen. Every
  other layer moves by 0.06 ms or less (0.03 at 250).
- **The update** does not move at 200 (+0.04 ms, −0.20 to +0.28). At 250
  it is 0.11 ms faster in every pairing (−0.12 to −0.10), although the
  change cannot reach it (it touches only the draw). That is a bias of
  about 0.1 ms toward "after" in the machine or the order, which sits in
  the 250 update + draw figure (−1.77 ms). It is not in the draw's own
  figures.
- **At 250, the two figures sit at the two ends of what RND-010.3
  expected.** The `enemies` row's saving (1.64 ms) lies between that
  throwaway variant's median (1.27) and the replay's prediction (1.83).
  The bare draw's saving (1.90 ms, every pairing 1.69 to 2.11) is at or
  above the prediction.
- **At 150 the change is not resolved,** as RND-010.3 found. These runs
  came first in the sitting, under the highest load readings (59, 44, 28
  and 99 % before their four steps). Their bare draws ran 14.43 to 15.85
  ms, against 12.07 to 12.13 in RND-010.3's sitting 5 at the same count
  (+2.30 to +3.78 ms). The update rose there too (+0.16 to +0.71 ms), so
  these runs read the machine as much as the code.
- **Quiet** (nothing is washed there) moves the bare draw by −0.11 to
  +0.08 ms in every pairing at 250. At 150 and 200 it is slower by a
  resolved hair, +0.04 ms (+0.03 to +0.06) and +0.02 ms (+0.01 to +0.03),
  which no line of the change reaches; it bounds how small a difference
  this sitting can call real.
- **Two biases of the design**, beside ABBA's within each count:
  - the counts ran in one order, 150 then 200 then 250, so the count and
    the time in the sitting go together;
  - every quiet run came after every fight. The quiet runs are not a
    control taken alongside the fights; they show that code with nothing
    washed is unaffected.
- **Frames over the budget stay at 300 of 300** in the fight at every
  count. The fix takes 1.77 ms off an update + draw of about 30 ms at
  250, and the saturated fight stays over the 16.67 ms budget (the plan's
  §6).
- **The replay** (`sprite_caches`, on the branch) asks for the same 1,665
  distinct washed frames and now prints the game's cap as 1536. It prints
  both policies at every cap; the game's wash cache is now its LRU column.
  Its figures are RND-010.3's, since the requests do not depend on the
  cache.

Exactness:
- The whole-frame test (a warm, an empty and a too-small cache draw one
  picture) and the cache's own tests pass.
- Seven mutants of `washed`'s LRU were each caught by a test:
  - a hit that does not refresh;
  - the newest entry dropped;
  - the cache emptied whole, as before;
  - the cap back at 512;
  - a stale entry not removed first;
  - the identity check dropped;
  - a plain dict.

  The first three were caught by
  `test_a_full_cache_drops_only_the_entry_used_longest_ago`, the cap by
  `test_the_cache_is_an_lru_of_1536`, the stale and identity mutants by
  `test_an_entry_under_another_frame_is_replaced_not_served`, and the
  dict by `test_it_is_cached_per_frame_and_element`.
- Tests: the full suite (`python -m pytest`, the default tiers) on
  `f1e502f`: 4,488 passed, 11 deselected (the `sweep` tier, run only when
  asked), none failed.

Memory: the wash cache now holds up to 80.6 MB in the replayed fight at
250, against 28.2 MB before, as D2 accepted.

## RND-010.5: The F1 overlay's lines only while it is shown (plan, 2026-10-07)

The owner asked for RND-010.5 on 2026-10-07, after #71 merged. This is
the plan's 4.1 and the second row of RND-010.3's sequence. Done when: no
`active_auras` call with the overlay off.

What the code did before this change:
- `PlayingState.update` ended with `self.dev.report_debug(self)`
  (`core/state.py:394` then, `:397` now), every frame, F1 or not.
- `report_debug` (`devtools/dev_flags.py:94`) sets about 25 overlay
  metrics. One of them, `auras` (`:116`), is `active_auras`, which walks
  the whole crowd. The rest are counts and f-strings.
- `DebugOverlay.draw` returns at once while hidden, so nothing reads
  those metrics until F1 is pressed.

The change:
- **The gate.** `report_debug` runs only while `game.debug.visible`.
  Pixel-identical while hidden, since a hidden overlay draws nothing;
  while shown, the same lines are filled every frame as before.
- **Hiding drops the lines (RND-010.5.D1).** Without this, the metrics
  set while F1 was last on would stay in the overlay. Shown again while
  the run is not updating (under the pause menu, for one), it would print
  them as if current, for as long as the run stays stopped.
  `DebugOverlay.toggle` now clears them on hide, so the overlay shows
  only FPS and the two timings until the next update refills them. Before
  RND-010.5 the overlay opened under the pause menu showed the last frame
  before the pause; that one frame's lines are what is given up. The
  owner confirmed D1 on 2026-10-07.
- **Tests:**
  - `tests/playing/test_debug_lines.py` on a booted seed-35 run: three
    updates hidden call neither `report_debug` nor `active_auras` and
    leave the overlay empty; three shown call each three times and fill
    the lines (integration tier);
  - `tests/systems/test_debug_overlay.py`: hiding clears the lines,
    showing keeps them;
  - a mutation check of each change.
- **Measured:** `tools/benchmarks/debug_lines.py` times `report_debug`,
  and `active_auras` alone, on the packed scene at 150 and 250, quiet and
  infused. The work is CPU only (no pixels), so it runs headless and
  needs no on-screen sitting. With F1 off, the whole of it is the saving.

## RND-010.5: Results (2026-10-07)

`debug_lines.py` on this branch, seed 35, headless, 2000 calls a run;
p50 and p90 by `tools/benchmarks/stats.percentile`, as every other probe
in this journal. "Infused" is `--elements`: the crowd primed and the
weapons infused, as `spawn_stress --elements`, then frozen while timed,
so it differs from quiet only in how many enemies hold an aura. The raw
outputs are in `data/rnd-010.5/`, and
`tests/devtools/test_debug_lines_probe.py` checks every row and every
figure quoted below against them:

| Scene | Alive | `report_debug`, p50 (p90) | A frame | `active_auras` alone, p50 |
|---|---|---|---|---|
| 150 packed, quiet | 138 | 16.4 µs (p90 16.7) | 0.016 ms | 11.5 µs |
| 150 packed, infused | 138 | 18.1 µs (p90 18.6) | 0.018 ms | 13.2 µs |
| 250 packed, quiet | 226 | 24.6 µs (p90 25.5) | 0.025 ms | 19.6 µs |
| 250 packed, infused | 226 | 26.4 µs (p90 27.2) | 0.026 ms | 21.2 µs |

- **The saving, F1 off:** 0.016 to 0.026 ms a frame, the whole of
  `report_debug`, which no longer runs. The plan's 4.1 estimated 0.2 to
  0.5 ms; the measured cost is 3 to 13 % of that. `active_auras` is
  most of it (11.5 of 16.4 µs at 150 quiet, 21.2 of 26.4 µs at 250
  infused) and grows with the crowd as the plan said; the counts and
  f-strings are the remaining 4.9 to 5.2 µs.
- **Against the frame:** in RND-010.3's sitting 5 the saturated fight at
  250 takes 29.30 to 29.47 ms to update and draw, so 0.026 ms is 0.09 %
  of it. Too small for an on-screen sitting to resolve, which is why
  none was run: the probe times the work removed directly, and the
  booted-run test proves it is removed.
- **F1 on:** unchanged. The same lines are computed every frame.
- **Biases:** the probe calls `report_debug` 2000 times on one frozen
  scene, so the crowd and its auras stay in cache between calls; inside
  a real frame they are colder, and the true cost is likely somewhat
  higher. Not by the factor of ten to the estimate: the walk is a
  `getattr` per enemy and, for an enemy with elemental state, one
  `has_aura` call (`combat/elements/resolve.py:468`).

Exactness. Skipping `report_debug` is exact because it changes no run
state: every call it makes reads (`active_auras` and `has_aura`, the
pool lengths, the element stats, `vis.report()`, the DPS summary,
`enemy_count_cap`, the spawn master's and the nav's counters) and its
only write is the overlay's own metrics.
`tests/flows/test_debug_lines_exact.py` holds that for good: seed 123
played by `run_digest` (720 frames, debug spawns and a level-up) gives
the same digest with the overlay hidden and shown, so a side effect added
to `report_debug` later fails it. The overlay's own pixels are unchanged
too: hidden it draws nothing, and shown it fills the same lines every
frame. The one visible difference is RND-010.5.D1: F1 pressed under a
stopped run (the pause menu, a level-up card, the end banner, where
`update` returns early) shows FPS and the two timings only, until the
run updates again. Refilling the lines on show would have kept the old
behaviour instead, at the cost of a hook from `Game`'s F1 key into the
state; the owner kept D1, clearing on hide (2026-10-07).

Mutation check (scratch scripts, not kept), each mutant caught:
- the gate removed (`if True:`):
  `test_hidden_the_lines_are_never_computed` and
  `test_f1_fills_the_lines_on_the_next_update_and_hides_them_again` fail;
- the clear on hide removed:
  `test_hiding_drops_the_lines_so_none_shows_stale` fails;
- `report_debug` given a side effect (one draw from the run RNG):
  `test_the_run_is_the_same_with_the_overlay_hidden_or_shown` fails on
  the digest.

Tests: the full suite (`python -m pytest`, the default tiers) on
`2cfebc1`, rebased on `main` after SYS-013: 4,501 passed, 11 deselected
(the `sweep` tier, run only when asked), none failed. The new tests are
`tests/playing/test_debug_lines.py`, `tests/flows/test_debug_lines_exact.py`
and `tests/devtools/test_debug_lines_probe.py` (its `MainTests` and the
first two in the integration tier), and one in
`tests/systems/test_debug_overlay.py`. `run_digest --check` still
matches its pin. No eval applies: the saving is measured directly by the
probe, and nothing here is a rate.

## RND-010: Tasks

- [x] RND-010.1: This journal, the plan and the index row
- [x] RND-010.2: The draw by layer in the stress harness, at 150, 200 and 250 packed
- [x] RND-010.3: The leads inside the enemies' own draw ranked (RND-010.D1), then the candidates timed old against new, the results recorded
  - [x] RND-010.3.1: This plan and the index
  - [x] RND-010.3.2: `blit_floor.py` and `gc_probe.py` under `tools/benchmarks/`, tested
  - [x] RND-010.3.3: The CPU steps' probe: each lead's cost per call and per frame on the live crowd, tested
  - [x] RND-010.3.4: The variant probe: throwaway pixel-identical variants timed against the draw (`rig_frame_cached`, `world_bucketed`, `forwarder_bypassed`), tested; the ghost copy is costed by `draw_leads` and gets a variant only if the sitting puts it near the top
  - [x] RND-010.3.5: Sitting 1: the probes at 150 and 250 packed, and the draw by layer with the hero fighting, raw outputs kept
  - [x] RND-010.3.6: The lead sitting 1's fight found, probed: `sprite_caches.py` (the wash and hit-tint caches replayed on a fight's own requests), the `wash_lru` variant and `draw_variants --elements`, tested
  - [x] RND-010.3.7: Sitting 2: the caches replayed, `wash_lru` timed and the fight's layers again, at 150 and 250 packed with the hero fighting, raw outputs kept
  - [x] RND-010.3.8: The ranking and the candidates' results recorded, and the order for RND-010.4 onward
  - [x] RND-010.3.9: The critic's tool findings: the miss cost over passes, the bytes the replayed cache held, both frames with a variant on compared; tested
  - [x] RND-010.3.10: The plan's rows and the journal's open items brought up to RND-010.3's measurements
  - [x] RND-010.3.11: Sittings 3 and 4 (the quiet draw at this branch's code; the fight and the quiet draw interleaved at one commit), and the results rewritten on them
  - [x] RND-010.3.12: The second review's tool findings: the mean and the tails timed, the cost of emptying a cache, the replay copy for copy; tested
  - [x] RND-010.3.13: The plan's 4.2, 4.3 and header, the journal header and the appendix note
  - [x] RND-010.3.14: Sitting 5 (everything compared, in one sitting at one commit, ABBA), and the results rewritten on it
  - [x] RND-010.3.15: The third review's findings: no comparison across sittings, the statistics named as measured, the 150 result and the scope, memory bounds per cap, the plan's stale lines; tested
  - [x] RND-010.3.16: The fourth review's findings: the memory bound over the frames each cache can be asked for (bosses are never washed), the ghost cache's bodies, the order's rule and the plan's promises not kept, the statistics' assumptions; tested
  - [x] RND-010.3.17: The fifth review's findings: the two sides' crowds and the bias they leave, the variant's cold start as a bounded gap candidate, the appendix note's evidence, the plan's order paragraph; the bound's premise and the prediction tested apart
  - [x] RND-010.3.18: The sixth review's findings: the unprimed share's causes unmeasured, the cold start an estimate, the stale-cache bias of ABBA and the leads' biases named with their direction, the order's scope (4.1 and the update tasks keep the plan's order), the plan's diagnosis annotated; the callers of both caches pinned
  - [x] RND-010.3.19: The seventh review's findings: sitting 1's own range, the crowd bias from sitting 5's costs (0.17 to 0.37 ms), the 150 prediction against its measurement, the plan's annotations narrowed to what was timed, one merged task sequence, the ghost cache's memory; tested
  - [x] RND-010.3.20: The eighth review's findings: the ghost remakes as a 150 candidate, the bars given a plan task and their billion-HP bias named, §3.1 narrowed, 4.3 kept last with its bound, sitting 5's own shade row, both sides of the stale-cache bias; D2's figures and every reference to the two caches pinned
  - [x] RND-010.3.21: The ninth review's findings: 150 consistent with its prediction (the gap's interval quoted), the stretch and ghost biases' net direction left open, the shade weighed against item 4 as a whole, the bars' two-way lean, IDs for every row of the sequence; the cap and the cold-start figures pinned
- [x] RND-010.4: The wash cache as an LRU of 1536 (RND-010.D2), pixel-identical and tested (the rest, in the sequence table under the RND-010.3 results, as RND-010.5 onward)
  - [x] RND-010.4.1: RND-010.D2 recorded, this plan and the index
  - [x] RND-010.4.2: `washed`'s cache an LRU of 1536, with its tests (the cache's behaviour; a whole frame from a warm, an empty and a too-small cache)
  - [x] RND-010.4.3: The probes and their tests follow the game's LRU
  - [x] RND-010.4.4: The sitting: `main` against this branch, ABBA, at 150, 200 and 250 packed, fighting and quiet; `sprite_caches` after; raw outputs kept
  - [x] RND-010.4.5: The results, and the plan's 4.13 marked done
  - [x] RND-010.4.6: The cold review's findings: the two savings placed against RND-010.3's two figures, the 250 update bias, the quiet and 150 figures from derived.py, the design's biases, the mutants listed; the probes' docstrings, two tests tightened, every quoted figure pinned
  - [x] RND-010.4.7: The full suite's counts in the results
- [x] RND-010.5: The F1 overlay's lines only while it is shown (plan 4.1), tested and measured
  - [x] RND-010.5.1: This plan and the index
  - [x] RND-010.5.2: `report_debug` gated on the overlay, its lines dropped on hide (RND-010.5.D1); tested, mutation-checked
  - [x] RND-010.5.3: `debug_lines.py` under `tools/benchmarks/`, tested; its outputs at 150 and 250, quiet and fighting, kept
  - [x] RND-010.5.4: The results, and the plan's 4.1 marked done
  - [x] RND-010.5.5: The cold review's findings: the shared percentile and the outputs taken again, every quoted figure pinned, the exactness argued from no run state written and held by a hidden-against-shown run digest, the real F1 path tested, "infused" for `--elements`, the line references, D1's alternative named
  - [x] RND-010.5.6: The full suite's counts in the results; the owner's confirmation of D1
- [ ] RND-010.n: Results: the harness before and after, and the owner's re-trace
