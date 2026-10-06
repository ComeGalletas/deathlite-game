# Drawing big crowds: journal

**ID:** RND-010 · **System:** rendering · **Type:** performance ·
**Status:** in progress · **Branch:** ComeGalletas/crowd-draw-levelup-9ec11fc6
(from `main`, owner, 2026-09-30; shared with UI-018)

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
- **RND-010.4 and on: build the winners**, one task each, largest first:
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
  used them.
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
  measures (a judgement from those two figures; the leads themselves are
  not timed yet).

## RND-010: Review of 2026-10-03 (read-only)

A review against the owner's requirement (a stable 60 fps with over 200
enemies on screen) measured the harness at 100 and 200 live, spread and
packed, the raw pygame blit floor, and the garbage collector, and ranked
the exact fixes for the draw and the update. Its findings, numbers, the
ranked plan and the owner decision it ends in are in
`../plans/crowd_performance_plan.md`. It was written on `main` while
RND-010.2 ran on its own branch: that plan's step 4.0 is RND-010.2, done
above, except for the plan's two appendix probes (`blit_floor.py`,
`gc_probe.py`), which moved under `tools/benchmarks/` with RND-010.3.2. The work resumes at the plan's 4.1 onward as RND-010.3 and
after, with RND-010.D1's ranking inside the enemies' own draw and the open
item of a fighting scene (above) taken first.

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

## RND-010: Tasks

- [x] RND-010.1: This journal, the plan and the index row
- [x] RND-010.2: The draw by layer in the stress harness, at 150, 200 and 250 packed
- [ ] RND-010.3: The leads inside the enemies' own draw ranked (RND-010.D1), then the candidates timed old against new, the results recorded
  - [x] RND-010.3.1: This plan and the index
  - [x] RND-010.3.2: `blit_floor.py` and `gc_probe.py` under `tools/benchmarks/`, tested
  - [x] RND-010.3.3: The CPU steps' probe: each lead's cost per call and per frame on the live crowd, tested
  - [x] RND-010.3.4: The variant probe: throwaway pixel-identical variants timed against the draw (`rig_frame_cached`, `world_bucketed`, `forwarder_bypassed`), tested; the ghost copy is costed by `draw_leads` and gets a variant only if the sitting puts it near the top
  - [x] RND-010.3.5: Sitting 1: the probes at 150 and 250 packed, and the draw by layer with the hero fighting, raw outputs kept
  - [x] RND-010.3.6: The lead sitting 1's fight found, probed: `sprite_caches.py` (the wash and hit-tint caches replayed on a fight's own requests), the `wash_lru` variant and `draw_variants --elements`, tested
  - [ ] RND-010.3.7: Sitting 2: the caches replayed, `wash_lru` timed and the fight's layers again, at 150 and 250 packed with the hero fighting, raw outputs kept
  - [ ] RND-010.3.8: The ranking and the candidates' results recorded, and the order for RND-010.4 onward
- [ ] RND-010.4: The largest exact win built, pixel-identical and tested (further winners as RND-010.5 onward)
- [ ] RND-010.n: Results: the harness before and after, and the owner's re-trace
