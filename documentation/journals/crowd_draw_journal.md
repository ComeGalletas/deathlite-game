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
1.797; the window always asks for
vsync, and every run's display line prints all of these, so a run on
another save shows it at once. Seed 35, 400 dormant records (the
default), the crowd packed round a hero standing still but for the
harness's 24 px jitter, 600 frames (300 timed, 300 bare, alternating),
the boss held back. Each run, from the repo root in bash (Git Bash on
Windows):

    SDL_VIDEODRIVER=windows python -m tools.benchmarks.spawn_stress --live N --elapsed E --pack --layers --frames 600

with N 150 at E 300, 200 at 400 and 250 at 600. (In PowerShell, set the
driver first: `$env:SDL_VIDEODRIVER = "windows"`, then the same command
without the prefix. Without the driver the harness draws headless into
the dummy driver's surface, which is not the cost on screen.) Two
sittings count:

- **Sitting 5 (2026-10-02, 11:40 to 11:45), commit `c53225e`**, the tool
  as committed: 150, 200 and 250 in that order, twice, then the probes
  on the same scenes:

      SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes bias --live N --elapsed E
      SDL_VIDEODRIVER=windows python -m tools.benchmarks.layer_probes nested --live N --elapsed E

  at 150 / 300 and 250 / 600 (`bias`: 16 blocks of 40 plain frames then
  80 layered; `nested`: 400 frames, 100 of each kind; the defaults). The
  machine was busy: the CPU load sampled before each run was 39 to 68 %
  (recorded by the sitting's script), and a process list taken a few
  minutes after it ended, the load still 46 to 58 %, showed a game client
  running. Its absolute times are inflated, and the second round ran
  15.7 % slower than the first at 150 and 200 (the same at 250).
- **Sitting 4 (2026-09-30, 20:00), the tool of `b6f7269`**: its output
  matches that commit line for line (the same rows, the villagers', huts'
  and lists' among them; the same printed strings, the after-timing boss
  line among them; the call count printed whole), and the commit, 58
  minutes later, says its figures were taken on the tool as committed.
  `b6f7269` computes every number as `c53225e` does, except that it
  collected the young garbage only after the timed frames. 150 and 250
  only, two runs each. The load was not recorded; its bare draws are 12 %
  to 29 % lower than sitting 5's at the same crowd, so it is the quieter
  record.

Sittings 1 to 3 (2026-09-30) ran earlier versions of the tool, under
conditions mostly unrecorded; their tables are dropped, and nothing below
rests on them.

**Sitting 5, `c53225e`, the boss held back** (layer figures are p50 ms of
each layer's own time over the timed frames, so they carry the timers'
cost; the crowd is the live count at the start and the end of timing, as
the summons arrive):

| Run | Crowd | In view p50 | Bare draw p50 | ground | water | scenery | scenery_list | enemies | enemies/shade | ghost | world | flat | enemies calls a frame |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 150 a | 135 to 175 | 147 | 11.87 ms | 4.13 | 1.54 | 1.36 | 0.24 | 2.46 | 0.48 | 0.61 | 0.57 | 0.31 | 159.3 |
| 150 b | 135 to 175 | 147 | 13.73 ms | 4.74 | 1.79 | 1.61 | 0.35 | 2.96 | 0.59 | 0.73 | 0.70 | 0.37 | 159.3 |
| 200 a | 182 to 200 | 178 | 13.05 ms | 4.17 | 1.53 | 1.35 | 0.24 | 3.14 | 0.68 | 0.74 | 0.67 | 0.35 | 195.5 |
| 200 b | 182 to 200 | 178 | 15.10 ms | 4.77 | 1.76 | 1.61 | 0.34 | 3.72 | 0.79 | 0.88 | 0.81 | 0.40 | 195.5 |
| 250 a | 226 to 250 | 224 | 16.82 ms | 4.82 | 1.83 | 1.66 | 0.34 | 4.72 | 1.03 | 1.14 | 0.97 | 0.45 | 243.9 |
| 250 b | 226 to 250 | 224 | 16.79 ms | 4.82 | 1.80 | 1.64 | 0.35 | 4.69 | 1.01 | 1.14 | 0.93 | 0.42 | 243.9 |

**Sitting 4** (same columns; the crowd, in view and calls a frame are the
same as sitting 5's at 150 and 250):

| Run | Bare draw p50 | ground | water | scenery | scenery_list | enemies | enemies/shade | ghost | world | flat |
|---|---|---|---|---|---|---|---|---|---|---|
| 150 a | 10.34 ms | 3.74 | 1.31 | 1.18 | 0.21 | 2.18 | 0.45 | 0.56 | 0.48 | 0.26 |
| 150 b | 10.46 ms | 3.75 | 1.30 | 1.20 | 0.20 | 2.22 | 0.45 | 0.55 | 0.48 | 0.27 |
| 250 a | 12.45 ms | 3.78 | 1.32 | 1.22 | 0.21 | 3.47 | 0.78 | 0.83 | 0.63 | 0.29 |
| 250 b | 11.90 ms | 3.63 | 1.26 | 1.15 | 0.21 | 3.35 | 0.75 | 0.81 | 0.60 | 0.26 |

The smaller rows, sitting 5, 150 then 200 then 250, p50: `projectiles`
(the enemies' shots) 0.06, 0.07 to 0.08, 0.10 (p90 up to 0.24);
`elemental_sort` 0.10 to 0.14, 0.11 to 0.17, 0.21; `flat/elemental` 0.11
to 0.14, 0.14 to 0.18, 0.22; `enemies/hpbar` and `enemies/marks` 0.04 to
0.05, 0.05 to 0.07, 0.08 to 0.09; `hud` 0.10 to 0.13; `huts_list` and
`villagers_list` 0.01 or less. Particles, damage numbers and hints are 0.00
at p50 (particles up to 0.13 at p90), since the hero does not attack.

**What it says.**

- **The terrain does not follow the crowd; the crowd's part does.** Call
  the terrain the ground, water, scenery and its list, and the crowd's
  part the enemies, the tree shade over them, the ghost pass and the
  scene's lists and sorts (`world`). The terrain is the same work at every
  crowd, so it also gauges how fast the machine was running; the crowd's
  part over the terrain is then steady within each crowd size whatever the
  load: 0.567 and 0.587 at 147 in view, 0.717 and 0.731 at 178, 0.909 and
  0.902 at 224 (sitting 5), and 0.570 and 0.574 at 147, 0.874 and 0.882 at
  224 in sitting 4. Against the terrain, the crowd's part grows 1.5 to 1.6
  times from 147 to 224 in view. RND-009 put the ground
  bands at the alpha blitter's floor, and the owner keeps the terrain as
  it is.
- **In milliseconds, on the quieter record (sitting 4):** the terrain is
  6.44 and 6.45 ms at 147 in view and 6.53 and 6.25 ms at 224; the crowd's
  part 3.67 and 3.70 ms, then 5.71 and 5.51 ms, as timed (it includes
  some of the timers' cost, below). At 178 in view, sitting 4 has no run;
  sitting 5's 0.717 and 0.731 against sitting 4's terrain of 6.25 to
  6.53 ms put the crowd's part at about 4.5 to 4.8 ms there: an estimate
  across sittings, not a measurement. The
  elemental sort and under-layer, the health bars and the marks grow
  with the crowd too but stay small (0.38 to 0.39 ms together at 224 in
  sitting 4).
- **Per enemy:** the `enemies` row over its calls a frame is 13.7 to
  14.2 µs in sitting 4 and 15.4 to 19.4 µs in sitting 5. The nested
  wrappers add 3.4 µs an enemy at 150 and 3.0 at 250 (sitting 5's probe,
  below), but the probe does not separate how much of that lands in the
  `enemies` row itself. Taking all of it off or none of it, an enemy's
  own draw is 10.3 to 14.2 µs on sitting 4's machine and 12.0 to 19.4 µs
  on sitting 5's busier one: an estimate, for what is one sprite blit and
  a few lookups each.
- **Against the budget:** the bare draw alone, with the hero not attacking
  and no boss, is 10.34 and 10.46 ms at 147 in view (62 % and 63 % of the
  16.67 ms) and 12.45 and 11.90 ms at 224 (75 % and 71 %) in sitting 4,
  before the update. On the busy machine of sitting 5 it was 11.87 to
  13.73 ms at 147 (71 % to 82 %), 13.05 to 15.10 ms at 178 (78 % to 91 %)
  and 16.82 and 16.79 ms at 224 (101 %).

**Its limits, carried into RND-010.3.**

- **The timers' cost.** Against the bare frames the timers added 0.83 to
  1.58 ms a frame in sitting 5 (0.94 to 1.66 µs a timed call, over 741 at
  150, 886 at 200 and 1,080 at 250 calls a frame) and 0.73 to 1.12 ms in
  sitting 4 (0.98 to 1.20 µs a call). Much of it lands in the callers'
  rows, the crowd's most. Sitting 5's `nested` probe measured the part
  the shade, bar and marks wrappers add, on the same scenes: 0.54 ms to
  `enemies` with its nested rows at 150 (3.68 against 3.14 ms; 3.4 µs an
  enemy over 159 calls) and 0.73 ms at 250 (5.41 against 4.68 ms; 3.0 µs
  over 244), and 0.25 and 0.70 ms to the whole draw, of every timer's
  0.92 and 1.10 ms. At 150 the two disagree (the rows grew 0.54 ms, the
  whole frame 0.25), which 100 frames a kind on a busy machine cannot
  settle; at 250 they agree (0.73 and 0.70). The root's timer alone added
  nothing measurable (13.65 against 13.65 ms at 150, 14.94 against 15.08
  at 250). So the nested wrappers alone make the crowd's rows read high
  by about 9 % at 250 (0.70 to 0.73 of 7.77 to 7.86 ms), and by 5 % to
  13 % at 150 depending on which of the two is taken (0.25 to 0.54 of
  4.12 to 4.98 ms); the terrain's rows barely at all. Candidates are timed
  old against new without the timers (the constraint above), and this
  breakdown only aims them.
- **The `--layers` headline matches the plain `--render` one.** Sitting
  5's `bias` probe, on the same scenes, put plain and layered blocks side
  by side over one crowd so its drift cancels in the pairs. It compares
  what the two commands report, so it covers the alternation and the
  garbage collection `--layers` adds after every frame together; two
  effects that cancelled would not show. At 150 the bare
  frames' draw p50 was 13.22 ms against the plain frames' 13.20 (640
  frames each), and the bare minus plain p50 per block had a median of
  -0.05 ms, from -0.44 to +0.80 (bare slower in 7 of 16); at 250, 14.50
  against 14.52, median -0.24 ms, from -3.33 to +1.61 (6 of 16). No bias
  shows: the overall p50s agree within 0.02 ms at both, and the blocks
  split either way about as a coin would. How small a bias the probe
  would miss is not computed; the blocks' spread (1.24 ms at 150, about
  5 ms at 250 on this busy machine) is the scale of what one block can
  see.
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
- **The machine's speed.** Sitting 5 ran beside other work; sitting 4's
  load is unknown. The ratios above hold across both, the milliseconds
  do not; RND-010.3 times each candidate old against new in one sitting,
  alternating, for that reason.

## RND-010: Tasks

- [x] RND-010.1: This journal, the plan and the index row
- [x] RND-010.2: The draw by layer in the stress harness, at 150, 200 and 250 packed
- [ ] RND-010.3: The candidates timed old against new, the results recorded
- [ ] RND-010.4: The largest exact win built, pixel-identical and tested (further winners as RND-010.5 onward)
- [ ] RND-010.n: Results: the harness before and after, and the owner's re-trace
