# Drawing big crowds: journal

**ID:** RND-010 · **System:** rendering · **Type:** performance ·
**Status:** planned · **Branch:** ComeGalletas/crowd-draw-levelup-9ec11fc6
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

## RND-010: Tasks

- [x] RND-010.1: This journal, the plan and the index row
- [ ] RND-010.2: The draw by layer in the stress harness, at 150, 200 and 250 packed
- [ ] RND-010.3: The candidates timed old against new, the results recorded
- [ ] RND-010.4: The largest exact win built, pixel-identical and tested (further winners as RND-010.5 onward)
- [ ] RND-010.n: Results: the harness before and after, and the owner's re-trace
