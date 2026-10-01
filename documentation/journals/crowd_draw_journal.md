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

## RND-010.2: The draw by layer (2026-09-30)

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
hit tint the same way; none of these cost anything here, where nothing is
hit or primed). The buff marks, banners, hurt flash and buff tint are the
`feedback` row, and
the scenery's list building its own `scenery_list` row. The set of layers
is pinned by a test. Every other frame is drawn without the timers
(`Alternate`), their young garbage collected between frames outside any
timed span; the draw and update + draw lines are the bare frames', and the
report states what the timers added against them, per timed call, measured
in place.

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
  the owner's trace, the play frames with 225 or more alive (2,123 of them)
  run from 295 to 376 s of run clock, before any boss; 603 of them held more
  than 250, up to 316.

**How it was taken.** Windows renderer, 2560 × 1080, render scale 1.2,
zoom 1.797, seed 35, the crowd packed round a hero standing still but for
the harness's 24 px jitter, 600 frames (300 timed, 300 bare, alternating).
150 at `--elapsed 300` and 250 at 600 in every sitting; 200 at 400 in
sitting 1 only, with the old tool. Four sittings, each with the tool as it
stood then:

- **Sitting 1:** no `hud` or `feedback` rows (the HUD sat in `draw`, 0.18
  to 0.48 ms), no `scenery_list` row (the scenery's list in `world`), no
  garbage collection between frames, a calibrated per-call cost where the
  measured one is printed now; the boss not held back. Other work ran on
  the machine.
- **Sitting 2:** as sitting 1, but with the `hud` and `feedback` rows and
  the measured timers' cost. What else ran on the machine was not
  recorded.
- **Sitting 3:** as sitting 2, with the garbage collection between frames
  and the boss held back (`boss held back` on the display line).
- **Sitting 4:** the tool as committed: the `scenery_list` row, the boss's
  other states on the display line (`due now`, `due at N s`, `beaten`) and
  its state again after timing.

The rows other than these mean the same in all four.

**Sitting 4, the tool as committed, the boss held back** (the figures the
conclusions rest on):

| Run | In view p50 | Bare draw p50 | ground | water | scenery | scenery_list | enemies | enemies/shade | ghost | world | flat |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 150 a | 147 | 10.34 ms | 3.74 | 1.31 | 1.18 | 0.21 | 2.18 | 0.45 | 0.56 | 0.48 | 0.26 |
| 150 b | 147 | 10.46 ms | 3.75 | 1.30 | 1.20 | 0.20 | 2.22 | 0.45 | 0.55 | 0.48 | 0.27 |
| 250 a | 224 | 12.45 ms | 3.78 | 1.32 | 1.22 | 0.21 | 3.47 | 0.78 | 0.83 | 0.63 | 0.29 |
| 250 b | 224 | 11.90 ms | 3.63 | 1.26 | 1.15 | 0.21 | 3.35 | 0.75 | 0.81 | 0.60 | 0.26 |

**Sittings 1 to 3** (`world` includes the scenery's list; the 250 rows of
sittings 1 and 2 include a boss fight):

| Run | In view p50 | Bare draw p50 | ground | water | scenery | enemies | enemies/shade | ghost | world | flat |
|---|---|---|---|---|---|---|---|---|---|---|
| 1: 150 | 147 | 15.06 ms | 5.14 | 1.95 | 1.72 | 3.27 | 0.65 | 0.80 | 1.18 | 0.44 |
| 1: 200 | 178 | 19.77 ms | 6.00 | 2.36 | 2.06 | 5.02 | 1.13 | 1.21 | 1.54 | 0.56 |
| 1: 250, boss | 225 | 23.23 ms | 6.25 | 2.43 | 2.16 | 6.31 | 1.30 | 1.82 | 1.85 | 0.66 |
| 2: 150 a | 147 | 10.55 ms | 3.83 | 1.35 | 1.26 | 2.21 | 0.46 | 0.60 | 0.70 | 0.29 |
| 2: 150 b | 147 | 13.22 ms | 4.76 | 1.62 | 1.63 | 2.82 | 0.52 | 0.70 | 0.93 | 0.29 |
| 2: 250 a, boss | 225 | 16.56 ms | 4.78 | 1.67 | 1.64 | 4.57 | 0.88 | 1.35 | 1.17 | 0.33 |
| 2: 250 b, boss | 225 | 16.60 ms | 4.52 | 1.70 | 1.49 | 4.50 | 0.86 | 1.33 | 1.20 | 0.39 |
| 3: 150 a | 147 | 9.89 ms | 3.69 | 1.26 | 1.15 | 2.05 | 0.42 | 0.53 | 0.61 | 0.25 |
| 3: 150 b | 147 | 9.82 ms | 3.71 | 1.22 | 1.14 | 2.00 | 0.40 | 0.52 | 0.61 | 0.24 |
| 3: 250 a | 224 | 12.47 ms | 3.92 | 1.37 | 1.22 | 3.35 | 0.74 | 0.83 | 0.84 | 0.29 |
| 3: 250 b | 224 | 11.99 ms | 3.81 | 1.30 | 1.17 | 3.23 | 0.70 | 0.78 | 0.80 | 0.26 |

(Layer figures are p50 ms of each layer's own time, timed frames, so they
carry the timers' cost; see the limits. The sums quoted below add these
p50s; they are not the p50 of a sum. The smaller rows, sitting 4, 150 then
250: `projectiles` (the enemies' shots) 0.05 then 0.07 at p50, 0.12 then
0.17 at p90; `elemental_sort` 0.09 then 0.13 to 0.14; `flat/elemental` 0.09
then 0.13; `enemies/hpbar` and `enemies/marks` 0.04 then 0.06; `hud` 0.09;
`huts_list` and `villagers_list` 0.01 or less. In the boss runs of sittings
1 and 2, `hud` rose to 0.28 to 0.30 with the boss bar; `elemental_sort` and
`flat/elemental` reached 0.19 to 0.31 in sittings 1 and 2's slower runs,
the boss's or not (sitting 1's 200, with no boss, had 0.19 and 0.25). Particles, damage numbers and
hints are under 0.05 ms, since the hero does not attack.)

**What it says.**

- **The absolute times are not steady between sittings; the shape is.**
  Sittings 3 and 4 gave the same bare draw back to back (9.82 to 10.46 ms
  at 150, 11.90 to 12.47 ms at 250); sittings 1 and 2 were 1 % to 53 %
  slower at 150 and moved within a sitting (10.55 then 13.22 ms in
  sitting 2). Other work was running in sitting 1; sitting 2's conditions
  were not recorded. (The 250 runs of sittings 1 and 2 held a boss, so they do
  not compare.)
- **The terrain does not follow the crowd.** In sitting 4 the ground, water,
  scenery and its list take 6.44 and 6.45 ms at 147 in view and 6.53 and
  6.25 ms at 224, while the crowd's part rises about 1.5 times (below).
  RND-009 put the ground bands at the alpha blitter's floor, and the owner
  keeps the terrain as it is.
- **What grows with the crowd is the enemies**, as the owner said: the
  sprites, the tree shade laid over them, the ghost pass and the scene's
  lists and sorts, 3.67 and 3.70 ms at 147 in view and 5.71 and 5.51 ms at
  224 (sitting 4). The elemental sort and under-layer, the health bars and
  the marks grow with it too but stay small (0.38 to 0.39 ms together at
  224).
  `enemies`' own time is 14 µs per enemy drawn at 250 in sitting 4 (13 to
  14 µs in sitting 3, 18 to 26 µs in the boss runs of sittings 1 and 2),
  for what is one sprite blit and a few lookups each; the timers' share is
  in it (below).
- **Against the budget:** the bare draw alone, with the hero not attacking
  and no boss, is about 10.4 ms at 147 in view and 12.2 ms at 224 in
  sitting 4, about 62 % and 73 % of the 16.67 ms before the update; with
  other work running (sittings 1 and 2) it was 10.5 to 15 ms at 147 and
  19.8 ms at 178. The terrain is about 6.4 ms of it in sitting 4, the
  crowd's part 3.7 to 5.7 ms.

**Its limits, carried into RND-010.3.**

- **The timers' cost.** Against the bare frames they added 0.7 to 1.1 ms a
  frame in sittings 3 and 4 and 0.9 to 2.2 ms in sittings 1 and 2: 0.9 to
  2.0 µs a timed call in place, over about 740 to 1,080 calls. Much of it
  lands in the callers' rows: `enemies` carries its three nested wrappers
  per enemy, estimated (three wrappers × 243 enemies × the measured cost
  per call, not measured on its own) at up to about 1.5 ms at 250 in the
  slow sittings and about half that in sittings 3 and 4; `world` carries each enemy wrapper's own
  bookkeeping and the closures that wrap the items' draw functions, a few
  tenths of a millisecond at 243 enemies by a reviewer's micro-benchmark,
  not reproduced here. So the per-layer rows, and any sum of them, are a
  little high; candidates are timed old against new without the timers
  (the constraint above), and this breakdown only aims them.
- **Whether the alternation moves the bare frames is not settled.** After
  sitting 4, on the Windows renderer (the probe's own log does not record
  the display), four rounds each ran 200 plain `--render` frames and then
  400 layered ones over one crowd that drifted between rounds (150 to 175
  in view): the bare frames' draw p50 against the plain one was 8.53
  against 8.69, 8.75 against 8.30, 8.83 against 8.63, 8.24 against
  8.42 ms, differences of mixed sign within 0.45 ms, while the layered
  runs' update p50 was up to 10 % higher (8.51 against 9.40, 10.94 against
  11.70), as the crowd grew. Sequential runs over a drifting crowd cannot
  separate a bias of that size from the drift; and the young-garbage
  collection between frames, if anything, makes the bare frames a little
  faster than plain ones, not slower. The bare draw is read as the plain
  draw to within about half a millisecond.
- **No fight.** The hero does not attack, so there are no particles, damage
  numbers or damaged health bars, where the owner's trace had about 120
  particles at 150+. The combat effects' share is not in these numbers.
- **The crowd drifts.** Bodies fall asleep in the warm-up and summons arrive
  while timing (135 to 175 at `--live 150`), as the harness's crowd line
  reports.

## RND-010: Tasks

- [x] RND-010.1: This journal, the plan and the index row
- [x] RND-010.2: The draw by layer in the stress harness, at 150 and 250 packed (200 in the first sitting only)
- [ ] RND-010.3: The candidates timed old against new, the results recorded
- [ ] RND-010.4: The largest exact win built, pixel-identical and tested (further winners as RND-010.5 onward)
- [ ] RND-010.n: Results: the harness before and after, and the owner's re-trace
