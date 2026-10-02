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
  ranks what is inside them. The breakdown's parts must add up to the
  whole draw, pinned by a test.
- **RND-010.3: Time the candidates, old against new, without wrappers.**
  For each lead above that the breakdown puts in the top of the enemy
  cost, time a throwaway version of the change first, and record the
  result in this journal whether it wins or not.
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
marks, banners, hurt flash and buff tint are the
`feedback` row, and
the scenery's list building its own `scenery_list` row. The set of layers
is pinned by a test. Every other frame is drawn without the timers
(`Alternate`), the young garbage collected after every frame, bare or
timed, with no timer on; the draw and update + draw lines are the bare
frames', and the report states what the timers added against them, per
timed call, measured in place. Two probes on the tool's own error,
`python -m tools.benchmarks.layer_probes bias` and `nested`, build the same
scene (`tools/benchmarks/layer_probes.py`).

The harness also changed around it:

- **The crowd asked for.** It says when the director's cap refused part of
  the crowd: the cap is 100 + 5 per 20 s of run clock on normal, up to the
  live cap of 250, so a crowd of N needs `--elapsed (N - 100) * 4`. (Before
  this, a first 200 and 250 run here silently measured a crowd of 159 to
  175; seen in those runs' output, which was not kept.)
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
prints all of these, so a run on another save shows it at once. Seed 35,
400 dormant records (the default), the crowd packed round a hero standing
still but for the harness's 24 px jitter, 600 frames (300 timed, 300
bare, alternating), the boss held back. Each run, from the repo root in
bash (Git Bash on Windows):

    SDL_VIDEODRIVER=windows python -m tools.benchmarks.spawn_stress --live N --elapsed E --pack --layers --frames 600

with N 150 at E 300, 200 at 400 and 250 at 600, in that order, twice
(rounds a and b). The probes, on the same scenes, at 150 / 300 and
250 / 600:

    SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes bias --live N --elapsed E
    SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes nested --live N --elapsed E

(`bias`: 16 blocks of 40 plain frames and 80 layered, the order
alternating; `nested`: 400 frames, 100 of each kind; the defaults.) In
PowerShell, set the driver first, `$env:SDL_VIDEODRIVER = "windows"`, then
the same commands without the prefix. Without the driver the harness
draws headless into the dummy driver's surface, which is not the cost on
screen.

Three sittings count, and none ran on a quiet machine:

- **Sitting 6 (2026-10-02, 12:24 to 12:30), commit `da7ab7e`**: the runs
  and both probes. The sitting's log records the CPU load before each run
  (43 % to 80 %, rising through it) and the top processes by CPU time at
  its start and end: a game (`deadlock`) gained 1,223 s of CPU time over
  the six minutes, three to four cores' worth.
- **Sitting 5 (2026-10-02, 11:40 to 11:45), commit `c53225e`**: the runs.
  `c53225e` and `da7ab7e` time the runs with the same code (no change to
  `draw_layers.py`, `spawn_stress.py` or `stats.py` between them; only
  the probes changed, so sitting 5's probe figures are dropped). The CPU
  load before each run was 39 % to 68 %; a game client was seen in a
  process list just after it, not kept in a file.
- **Sitting 4 (2026-09-30, 20:00), the tool of `b6f7269`**: its output
  matches that commit line for line (the same rows, the villagers', huts'
  and lists' among them; the same printed strings, the after-timing boss
  line among them; the call count printed whole), and the commit, 58
  minutes later, says its figures were taken on the tool as committed.
  `b6f7269` computes every number as the later commits do, except that it
  collected the young garbage only after the timed frames, so each bare
  frame started right after a collection and each timed one did not; the
  `bias` probe never ran on that tool. 150 and 250 only, two runs each. The load was not recorded;
  its bare draws are 5 % to 31 % lower than sitting 6's at the same crowd,
  so it is the quietest record.

**Sitting 6, `da7ab7e`, the boss held back** (layer figures are p50 ms of
each layer's own time over the timed frames, so they carry the timers'
cost; the crowd is the live count at the start and the end of timing, as
the summons arrive):

| Run | Crowd | In view p50 | Bare draw p50 | ground | water | scenery | scenery_list | enemies | enemies/shade | ghost | world | flat | enemies calls a frame |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 150 a | 135 to 175 | 147 | 11.01 ms | 3.88 | 1.43 | 1.24 | 0.23 | 2.36 | 0.48 | 0.57 | 0.56 | 0.31 | 159.3 |
| 150 b | 135 to 175 | 147 | 13.93 ms | 4.75 | 1.80 | 1.64 | 0.36 | 2.98 | 0.59 | 0.76 | 0.73 | 0.37 | 159.3 |
| 200 a | 182 to 200 | 178 | 12.36 ms | 3.97 | 1.50 | 1.28 | 0.24 | 3.05 | 0.68 | 0.73 | 0.66 | 0.36 | 195.5 |
| 200 b | 182 to 200 | 178 | 14.60 ms | 4.45 | 1.75 | 1.49 | 0.34 | 3.54 | 0.73 | 0.85 | 0.79 | 0.39 | 195.5 |
| 250 a | 226 to 250 | 224 | 16.81 ms | 4.78 | 1.84 | 1.65 | 0.36 | 4.69 | 0.99 | 1.20 | 1.01 | 0.45 | 243.9 |
| 250 b | 226 to 250 | 224 | 17.14 ms | 4.84 | 1.92 | 1.65 | 0.37 | 4.84 | 1.02 | 1.18 | 1.06 | 0.48 | 243.9 |

**Sitting 5, `c53225e`** (the same columns; the crowd, in view and calls
a frame are sitting 6's):

| Run | Bare draw p50 | ground | water | scenery | scenery_list | enemies | enemies/shade | ghost | world | flat |
|---|---|---|---|---|---|---|---|---|---|---|
| 150 a | 11.87 ms | 4.13 | 1.54 | 1.36 | 0.24 | 2.46 | 0.48 | 0.61 | 0.57 | 0.31 |
| 150 b | 13.73 ms | 4.74 | 1.79 | 1.61 | 0.35 | 2.96 | 0.59 | 0.73 | 0.70 | 0.37 |
| 200 a | 13.05 ms | 4.17 | 1.53 | 1.35 | 0.24 | 3.14 | 0.68 | 0.74 | 0.67 | 0.35 |
| 200 b | 15.10 ms | 4.77 | 1.76 | 1.61 | 0.34 | 3.72 | 0.79 | 0.88 | 0.81 | 0.40 |
| 250 a | 16.82 ms | 4.82 | 1.83 | 1.66 | 0.34 | 4.72 | 1.03 | 1.14 | 0.97 | 0.45 |
| 250 b | 16.79 ms | 4.82 | 1.80 | 1.64 | 0.35 | 4.69 | 1.01 | 1.14 | 0.93 | 0.42 |

**Sitting 4, `b6f7269`** (the same columns and crowds, 150 and 250 only):

| Run | Bare draw p50 | ground | water | scenery | scenery_list | enemies | enemies/shade | ghost | world | flat |
|---|---|---|---|---|---|---|---|---|---|---|
| 150 a | 10.34 ms | 3.74 | 1.31 | 1.18 | 0.21 | 2.18 | 0.45 | 0.56 | 0.48 | 0.26 |
| 150 b | 10.46 ms | 3.75 | 1.30 | 1.20 | 0.20 | 2.22 | 0.45 | 0.55 | 0.48 | 0.27 |
| 250 a | 12.45 ms | 3.78 | 1.32 | 1.22 | 0.21 | 3.47 | 0.78 | 0.83 | 0.63 | 0.29 |
| 250 b | 11.90 ms | 3.63 | 1.26 | 1.15 | 0.21 | 3.35 | 0.75 | 0.81 | 0.60 | 0.26 |

The smaller rows, sitting 6, 150 then 200 then 250, p50: `projectiles`
(the enemies' shots) 0.05 to 0.06, 0.07 to 0.08, 0.10 (p90 up to 0.24);
`elemental_sort` 0.09 to 0.15, 0.11 to 0.16, 0.21 to 0.22;
`flat/elemental` 0.11 to 0.16, 0.14 to 0.18, 0.25 to 0.26;
`enemies/hpbar` and `enemies/marks` 0.04 to 0.05, 0.05 to 0.07, 0.08 to
0.09; `hud` 0.10 to 0.13; `huts_list` and `villagers_list` 0.01 or less.
Particles, damage numbers and hints are 0.00 at p50 (particles up to 0.12
at p90), since the hero does not attack.

**What it says.**

- **The terrain does not follow the crowd; the crowd's part does.** Call
  the terrain the ground, water, scenery and its list, and the crowd's
  part the enemies, the tree shade over them, the ghost pass and the
  scene's lists and sorts (`world`). The terrain is the same work at
  every crowd, so it also gauges how fast the machine was running; the
  crowd's part over the terrain then reads the crowd's cost with the
  machine's speed taken out. Within a sitting, the two runs of a crowd
  size give ratios within 3.5 % of each other while their bare draws
  differ by up to 26.5 %; across the three sittings the ratio is 0.567 to
  0.592 at 147 in view (a spread of 4.4 %), 0.717 to 0.736 at 178 (2.6 %)
  and 0.874 to 0.923 at 224 (5.5 %). Against the terrain, the crowd's
  part grows 1.53 to 1.60 times from 147 to 224 in view, in every sitting.
  RND-009 put the ground bands at the alpha blitter's floor, and the
  owner keeps the terrain as it is.
- **In milliseconds, on the quietest record (sitting 4, with its garbage
  collection caveat above):** the terrain is 6.44 and 6.45 ms at 147 in
  view and 6.53 and 6.25 ms at 224; the crowd's part 3.67 and 3.70 ms,
  then 5.71 and 5.51 ms, as timed (it includes some of the timers' cost,
  below). At 178 in view sitting 4 has no run; sittings 5 and 6's ratios
  there (0.717 to 0.736) against sitting 4's terrain (6.25 to 6.53 ms) put
  the crowd's part at about 4.5 to 4.8 ms: an estimate across sittings,
  not a measurement. The elemental sort and under-layer, the health bars
  and the marks grow with the crowd too but stay small (0.38 to 0.39 ms
  together at 224 in sitting 4).
- **Per enemy:** the `enemies` row over its calls a frame is 13.7 to
  14.2 µs in sitting 4 and 14.8 to 19.8 µs in sitting 6. Sitting 6's
  `nested` probe puts the nested wrappers at 3.45 µs an enemy at 150 and
  3.12 at 250 (below), without separating how much of that lands in the
  `enemies` row itself. Taking all of it off or none of it, an enemy's
  own draw is 10.2 to 14.2 µs on sitting 4's machine (sitting 6's probe
  applied to sitting 4: an estimate) and 11.4 to 19.8 µs on sitting 6's,
  for what is one sprite blit and a few lookups each.
- **Against the budget:** the bare draw alone, with the hero not attacking
  and no boss, is 10.34 and 10.46 ms at 147 in view (62 % and 63 % of the
  16.67 ms) and 12.45 and 11.90 ms at 224 (75 % and 71 %) in sitting 4,
  before the update. On the busy machines of sittings 5 and 6 it was
  11.01 to 13.93 ms at 147 (66 % to 84 %), 12.36 to 15.10 ms at 178
  (74 % to 91 %) and 16.79 to 17.14 ms at 224 (101 % to 103 %). No
  sitting on the current tool ran on a quiet machine; the quiet figure on
  it is still to be taken (below).

**Its limits, carried into RND-010.3.**

- **The timers' cost.** Against the bare frames the timers added 0.78 to
  1.50 ms a frame in sitting 6 (0.88 to 1.39 µs a timed call, over 741 at
  150, 886 at 200 and 1,080 at 250 calls a frame), 0.83 to 1.58 ms in
  sitting 5 and 0.73 to 1.12 ms in sitting 4. Much of it lands in the
  callers' rows, the crowd's most. Sitting 6's `nested` probe measured
  the part the shade, bar and marks wrappers add, on the same scenes,
  with its own count of enemies drawn: at 150, 0.52 ms to `enemies` with
  its nested rows (3.76 against 3.24 ms; 151.7 drawn a frame, 3.45 µs an
  enemy) and 0.51 ms to the whole draw; at 250, 0.75 ms to the rows (6.07
  against 5.32 ms; 240.9 drawn, 3.12 µs an enemy) and 0.52 ms to the whole
  draw, of every timer's 0.91 and 1.16 ms. At 150 the two measures agree;
  at 250 they do not, which 100 frames a kind on a machine this busy
  cannot settle. The root's timer alone added nothing measurable (14.33
  against 14.29 ms at 150, 17.37 against 17.36 at 250). So the nested
  wrappers alone make the crowd's rows read high by 10 % to 13 % at 150
  (0.51 to 0.52 of 3.97 to 5.06 ms) and less at 250 (0.52 to 0.75
  of 7.89 to 8.10 ms: 6.4 % to 9.5 %), depending on the run and the
  measure; the
  terrain's rows barely at all. Candidates are timed old against new
  without the timers (the constraint above), and this breakdown only aims
  them.
- **The `--layers` headline against the plain `--render` one.** Sitting
  6's `bias` probe put plain and layered blocks side by side over one
  crowd, the order alternating (ABBA) so a drift inside a block falls on
  each side alike. It compares what the two commands report, so it
  covers the alternation and the garbage collection `--layers` adds after
  every frame together; two effects that cancelled would not show. At 150
  the bare frames' draw p50 was 13.31 ms against the plain frames' 13.36
  (640 frames each), and the bare minus plain p50 per block had a median
  of +0.03 ms, from -0.87 to +0.81 (bare slower in 8 of 16). At 250, the
  load sampled at 62 % before it, 16.12 against 16.52, a median of -0.12 ms,
  from -5.12 to +0.58 (7 of 16). The bare frames do not read slower; at
  250 they read 0.40 ms faster over all, inside a block spread of 5.7 ms
  on that machine, so whether they read faster there is not settled. How
  small a difference the probe would miss is not computed.
- **The packed crowd is past what the owner played.** In the owner's
  trace, the play frames with 150 or more alive (4,557) had 90 enemies in
  view at p50, 173 at p99 and 177 at most; none had 200. The harness's
  147 in view at 150 is near that p99, its 178 at 200 at the trace's
  maximum, and its 224 at 250 beyond anything played: the packed runs are
  the worst case of a crowd, not its usual frame.
- **No fight.** The hero does not attack, so there are no particles, damage
  numbers or damaged health bars, where the owner's trace had about 120
  particles at 150+. The combat effects' share is not in these numbers.
- **The crowd drifts.** Bodies fall asleep in the warm-up and summons arrive
  while timing (135 to 175 at `--live 150`), as the harness's crowd line
  reports.
- **No quiet sitting on the current tool.** Sittings 5 and 6 ran beside a
  game; sitting 4 ran an older garbage collection and its load is
  unknown. The ratios hold across all three; the milliseconds do not.
  Taking the commands above again with nothing else running would give
  the quiet milliseconds on the current tool; RND-010.3 does not wait on
  it, since it times each candidate old against new in one sitting,
  alternating.

## RND-010: Tasks

- [x] RND-010.1: This journal, the plan and the index row
- [x] RND-010.2: The draw by layer in the stress harness, at 150, 200 and 250 packed
- [ ] RND-010.3: The candidates timed old against new, the results recorded
- [ ] RND-010.4: The largest exact win built, pixel-identical and tested (further winners as RND-010.5 onward)
- [ ] RND-010.n: Results: the harness before and after, and the owner's re-trace
