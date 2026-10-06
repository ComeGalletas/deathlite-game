# Crowd performance — findings and the plan to hold 60 fps at 200 enemies

> Read-only review, 2026-10-03. Serves RND-010 (`../journals/crowd_draw_journal.md`),
> whose step RND-010.2 (4.0 below) is done; the work resumes at 4.1, as
> RND-010.3 and after. RND-010.3 (done, 2026-10-06) measured the leads on
> the owner's machine. Where its numbers revise this review they are
> written into the row as **measured** in RND-010.3: §3.4 and the new
> step 4.13 (in a fight the wash cache thrashes; first in the order), 4.2,
> 4.3, 4.4, 5.1 and the sum of gains under the table. Two more, here: the
> per-enemy lambda and forwarder the paragraph below names cost 0.01 to
> 0.03 ms a frame each, and the ghost `copy()` 0.01 ms (two shaded
> bodies); and the blit floor on the owner's screen is 2.53 ms for 200
> with a shadow and a bar, not 5.5 (§2.3 is the review's container). The
> journal's "RND-010.3: Results" has the figures and the order for
> RND-010.4 onward. Nothing in the code was
> changed by the review. Measured facts are marked **measured** with the
> machine they came from; everything else is read from the code and cites
> `file:line` on `main` at `6384fa3`.
>
> **Requirement (owner):** a stable 60 fps at all times, with over 200
> enemies on screen, animated, with distance and element checks. Budget is
> `BUDGET_MS` = 16.67 ms per frame (`systems/frame_trace.py`, SYS-012).

**In one paragraph.** The game does not hold the budget at 200 enemies and
the owner's own trace says so: about 44 fps above 100 enemies in view and
about 30 fps above 220 (`../journals/crowd_draw_journal.md:21-31`). Pygame's
blitter is not the limit: blitting 200 sprites with a shadow and a health
bar each costs 4.3 ms at 1600x900 and 5.5 ms at 2560x1080 (**measured**,
section 2). The frame is lost in Python work around those blits (a lambda,
a forwarder, a shade walk and a `copy()` per enemy), in Python per-enemy
update work (about 25 to 45 µs per enemy), in two near-quadratic
enemy-to-enemy passes, in a pure-Python flow-field fill that costs 2 to
3 ms on most frames, and in a fixed 5.4 ms of terrain per frame before any
enemy is drawn. Exact fixes (sections 4 and 5) get a stable 60 at about
150 alive with 50 to 80 in view, which is the common shape of a run. 200
in view at 60 fps is not reachable in CPython with one Python object per
enemy per frame doing this much work; that needs section 6's decision.

---

## 1. How to reproduce every number here

Everything runs headless from the repo; no display is needed. Install
`pygame` (the review used pygame-ce 2.5.8 on Python 3.11; the project
targets pygame 2.x on 3.12, numbers differ a little, shapes do not).

```bash
# the crowd stress harness: update + draw, p50/p90/p99, frames over budget
python -m tools.benchmarks.spawn_stress --live 100 --dormant 0 --frames 600 --render
python -m tools.benchmarks.spawn_stress --live 200 --dormant 0 --frames 600 --render
python -m tools.benchmarks.spawn_stress --live 200 --dormant 0 --frames 600 --render --pack   # ~158 in view
python -m tools.benchmarks.spawn_stress --live 200 --dormant 0 --frames 300 --pack --profile  # cProfile, update only
# real play on the owner's machine: per-frame CSV, then the report by crowd size
python main.py --trace
python -m tools.benchmarks.trace_report
```

`--live 200` seats about 175 (the cap, placement and the despawn ring take
the rest); read the `crowd` line the harness prints, never the flag.
Timings compare only within one sitting on one machine
(`../journals/frame_time_journal.md`, "Method"). cProfile inflates
cheap Python calls two to three times; use it for shares, never for
milliseconds (ENT-018.3).

The two probes written for this review are in appendix A. They are not
in the repo yet; the first task below puts them under `tools/benchmarks/`.

## 2. What was measured

### 2.1 The owner's real-play trace (owner's machine, 2560x1080, SYS-010)

From `../journals/crowd_draw_journal.md:21-31`. 557 s of play. Of 5,553
frames over budget, 5,525 were draw-bound and 28 update-bound.

| Enemies alive | Frames | Work p50 / p90 | Over budget | In view p50 |
|---|---|---|---|---|
| 0 to 24 | 3,776 | 9.30 / 12.15 ms | 0.6 % | 1 |
| 50 to 99 | 4,172 | 12.53 / 15.63 ms | 4.7 % | 32 |
| 100 to 149 | 4,889 | 14.64 / 18.25 ms | 23.6 % | 54 |
| 150+ | 4,557 | 21.23 / 26.44 ms | 90.8 % | 90 |

Worst seconds: 225 to 250 alive, work 25.5 to 29.9 ms. No spikes beyond
that, so the problem is steady-state cost, not pauses.

### 2.2 The harness in the review's container (headless 1600x900, a shared CPU slower than the owner's)

**measured**, seed 35, hero jittering, hints off, director frozen.

| Crowd | In view p50 | Update p50 | Draw p50 | Frame p50 | Over 16.67 ms |
|---|---|---|---|---|---|
| 107 live, spread | 28 | 6.0 ms | 5.9 ms | 11.9 ms | 15 / 600 |
| 175 live, spread | 47 | 8.6 ms | 8.3 ms | 16.9 ms | 342 / 600 |
| 175 live, `--pack` | 158 | 15.4 ms | 9.8 ms | 25.2 ms | 600 / 600 |

The container showed 40 to 80 ms spikes that the owner's trace does not;
they are the shared CPU, not the game. Do not chase them.

### 2.3 The floor: what pygame itself costs (appendix A.1, **measured**, same container)

| Work | 1600x900 | 2560x1080 |
|---|---|---|
| 200 sprites (112 px, alpha), one blit each | 3.85 ms | 5.07 ms |
| 200 sprites + shadow + health bar (600 blits) | 4.33 ms | 5.53 ms |
| 300 sprites + shadow + health bar (900 blits) | 5.30 ms | 7.27 ms |
| full-surface fill | 0.32 ms | 0.62 ms |
| pure-Python stand-in: 200 enemies x 12 neighbour checks, attribute reads, one hypot | 0.60 ms | |

So three blits per enemy for 200 enemies is about a quarter of the budget.
The rest of the draw's 9.8 ms at 158 in view is Python around the blits
and the fixed terrain cost.

### 2.4 Update shares at 158 in view (cProfile, `--pack --profile`, shares only)

| Part | Share of update | Where |
|---|---|---|
| `Enemy.update` | 51 % | `entities/enemy.py:172` |
| of which the behaviour machine | 30 % | `entities/ai/machine.py:100` |
| of which `Separation` | 12 % | `entities/ai/components/crowd.py:32` |
| of which the movement probe | 14 % | `world/map.py:356` → `is_walkable` `world/map.py:274` |
| bump pass | 30 % | `game/states/playing/core/physics.py:119` |
| flow-field fill | 14 % | `world/nav/field.py:167` |

21,000 `getattr` calls per frame (6.3 M in 300 frames) sit under the
forwarders and the component dicts.

### 2.5 Garbage collector (appendix A.2, **measured**)

62,000 tracked objects after load. In 600 frames: 106 gen-0 collections
(8 ms in all), 9 gen-1 (1.2 ms), **one gen-2 of 12.8 ms**. With
`gc.freeze()` after load and a gen-2 threshold of 1000 the gen-2 pause is
gone and nothing else changes. The spikes in 2.2 were not collections.

## 3. Where the time goes (read from the code)

### 3.1 Per visible enemy, draw

Sprites, flips and scales are cached once per `(rig, anim, size, flip,
tint)` (`game/assets.py:103-157`); frames are shared, not copied; the
animators hold one float each (`systems/animation.py:11-45`). That part
is right. The cost is around the blit:

- A lambda per enemy per frame (`game/states/playing/visual/scene.py:127-129`),
  then a generated forwarder costing two `getattr` per call
  (`game/states/playing/core/state.py:776-784`), then three to six
  `world_to_screen` calls (`visual/rendering.py:605`, `:174`,
  `health_bars.py:146`, `status_marks.py:100`, `elements/layers.py:93,118`).
- The tree-shade walk for every enemy (`world/terrain/render.py:365-416`):
  a shaded body costs two fills and three or more blits into scratch
  surfaces, then a `drawn.copy()` every frame for the ghost queue whether
  or not the ghost pass uses it (`visual/rendering.py:147`). A shaded
  body's ghost is copied and filled again (`render.py:500-503, 543-544`).
- Per-terrace re-filtering and sorting of the whole drawable list, once
  per terrace level (`scene.py:60-73`); `banded_scenery` rebuilt every
  frame with a `level_at` and a lambda per visible decor
  (`render.py:203-232`); `draw_ground_band` re-sorts per level
  (`render.py:161-163, 183-187`).
- `camera.visible_rect()` allocates a new Rect per call and is called by
  actors, elements, gems, chests, potions, hostiles, water and every
  ground band (`systems/camera.py:80-84`).
- New SRCALPHA surfaces per frame: fallback rings and locked bodies
  (`visual/elements/layers.py:132-148`), the chill mark (`layers.py:248-257`),
  markers (`elements/markers.py:47-53`), hazards (`rendering.py:377-383`),
  jump arcs, reaction rings and Wind areas (`elements/transient.py:259-312`).
- Mark brackets `copy()` + `set_alpha` every frame while fading
  (`status_marks.py:127-130`); fading trails the same (`rendering.py:590-594`).
- Particles (cap 1200) and damage numbers (cap 200) drawn with no view
  culling (`systems/particles.py:100-109`, `ui/damage_numbers.py:190-213`).
- Fixed per frame on the owner's machine: ground bands 3.4 ms
  (`../journals/frame_time_journal.md:734`, RND-009 found them at the
  alpha blitter's floor), water about 2 ms. Together a third of the
  budget before any enemy.

### 3.2 Per enemy, update

- `Enemy.update` (`entities/enemy.py:172-227`): a status closure per
  frame (`:188`), four Vector2 temporaries for the move (`:190-191`),
  `pow(config.BUMP_DECAY, dt)` per enemy (`:193`), `is_stunned()` and
  `speed_multiplier()` each a pass over the status dict
  (`combat/status.py:208, 217`).
- Behaviour machine (`entities/ai/machine.py:100-118`): a new `Steering`
  per tick, `acc.resolve` two Vector2s, `Steering.add` copies twice per
  call (`entities/ai/steering.py:21-24`), dict slot lookups per component,
  a scan of all transitions every tick. `SeekTarget` copies the direction
  twice and `lerp`s (`components/seek.py:41-59`); `direction_at` allocates
  a Vector2 per downhill neighbour (`world/nav/field.py:262-309`).
- `Separation` (`components/crowd.py:32-60`): a 9-cell grid query, float
  early drop (ENT-018.2), then a Vector2 per pushing neighbour. It reads
  `run.grid`, which was built in the previous frame's combat phase
  (`core/state.py:495`), so it is one frame stale.
- `AvoidObstacles` (`crowd.py:72-84`) has no float early drop: a Vector2
  subtraction and a sqrt per obstacle candidate.
- Movement probe (`world/map.py:274-331`): five `_point_ok` floor probes,
  each a linear scan over rooms (`world/rules/floor.py:23-31`), plus
  `inset_at`, `path_ok` and the obstacle distances. A blocked move adds
  two slide probes and a sorted eight-direction hop. ENT-018 tried a
  floor index and measured it slower; try again only with a different
  structure.
- Bump pass (`core/physics.py:119-200`): its own grid, rebuilt per frame
  (`:117, :129`); each enemy queries `radius + pad` (pad up to 72, usually
  3x3 cells); a `seen` set of id pairs for touching pairs; float `d2`
  before any Vector2 (RND-008.5). Bump alone on the owner's machine:
  0.26 ms at 58, 0.64 at 95, 1.38 at 144 packed, about N^1.8.
- Flow field (`world/nav/field.py:167-246`): a pure-Python bucketed
  Dijkstra over about 160k cells, sliced at `ENEMY_NAV_FILL_BUDGET` =
  1600 relaxations per frame (`game/config.py:541`), re-aimed every 0.4 s
  per class or at once on a two-cell hero drift
  (`core/navigation.py:40-65`). Fixed 1.9 to 3.3 ms on the owner's machine
  (`../journals/frame_time_journal.md`, RND-008.5) on about 80 % of frames
  while the hero moves. Does not scale with N; it is a standing tax.

### 3.3 Per frame, O(N) work that is pure waste

- `dev.report_debug` runs every frame with the F1 overlay hidden
  (`core/state.py:394`): an O(N) `active_auras` scan
  (`devtools/dev_flags.py:116`, `combat/elements/resolve.py:468`) and
  about 20 f-strings.
- Two full grid rebuilds per frame: bump's (`physics.py:117`) and
  `run.grid` (`core/state.py:495`).
- `targetables()` copies the enemy list whenever the boss is alive
  (`core/run.py:124`), in `FireContext`, `projectile_hits`
  (`core/combat.py:57`) and `update_summons` (`core/effects.py:123`).
  `near = near + [run.boss]` allocates a list per projectile
  (`combat.py:58-114`).
- Summon targeting is brute force over all enemies with a Vector2 per
  enemy, per summon, per frame (`entities/summon.py:155-164`). Weapon
  `_within_reach` (`combat/weapons/core.py:445-457`) and `chain_to_next`
  (`core/combat.py:343-356`) are brute force with a sqrt per enemy.
- `shed.update` builds an in-view list over all enemies every frame
  (`visual/elements/shed.py:41`, `layers.py:43-53`).
- The watchdog builds `{id(e) for e in live}` every frame
  (`spawn/watchdog.py:93-96`).
- `hibernate` (every 0.5 s) builds a `SimpleNamespace` per enemy
  (`core/spawning.py:169`) and `enemies.remove` per slept body
  (`:177`), O(N) each.
- The tick LOD (`core/state.py:435-452`) pads the view by 96 px per side
  where `config.py:849-852` says 192, because `Rect.inflate` splits its
  argument; and the skip phase is keyed to the list index, which shifts
  on every cull.

### 3.4 What is already right

Cached sprite transforms; cached tint, wash, ghost, burn-scale and
health-bar surfaces (but see 4.13: in a fight at 250 the wash and tint
caches are too small and empty themselves whole, **measured** in
RND-010.3); a spatial grid for bump, separation, projectiles,
contact, elements, tree shadows and obstacle art; actor culling at 320 px;
elemental bands sorted once per frame (RND-008.4); constant-alpha veils
(RND-012); a frozen backdrop under pause; off-screen tick LOD; the sliced
flow field; object pools for projectiles, gems, potions and summons;
element reaction and particle budgets. Presenting the frame is cheap:
`flip` 0.2 to 0.6 ms (`../journals/frame_trace_journal.md:131-135, 404`).

## 4. The plan: exact fixes first (no gameplay change, pixels identical)

Each task ships as RND-010.n or a new ENT ID, one PR each, with the
harness before and after in one sitting at 150, 200 and 250 `--pack`, the
whole-frame byte-identity check at 150 and 250 packed (built on
`tests/render/test_elemental_draw_cost.py`'s frame, as RND-010 requires),
and the existing render tests green. Expected gains are estimates against
the owner's machine; the measured number replaces them in the journal.

**Order of work, largest first.** Measure (4.0) before cutting, then draw
tasks (the owner's trace is draw-bound) interleaved with the update
tasks whose packed share is largest.

| # | Task | Where | Expected | Done when |
|---|---|---|---|---|
| 4.0 | **RND-010.2: the draw by layer in the harness.** Add a per-layer breakdown of `PlayingState.draw` to `spawn_stress.py --render`: terrain bands, water, enemies (with shade split out), other actors, ghost pass, elemental layers, particles, damage numbers, the rest. Parts must sum to the whole, pinned by a test. Put appendix A's two probes under `tools/benchmarks/` (`blit_floor.py`, `gc_probe.py`) while there. | `tools/benchmarks/spawn_stress.py:359-402` | ranks 4.1 to 4.8 by milliseconds | the table at 150, 200, 250 packed is in `crowd_draw_journal.md`: **done** (RND-010.2; the two appendix probes moved under `tools/benchmarks/` in RND-010.3.2) |
| 4.1 | **Stop `report_debug` when the overlay is hidden.** Compute the debug lines only when F1 is on. | `core/state.py:394`, `devtools/dev_flags.py:116` | 0.2 to 0.5 ms | `test_dev_flags` style test: no `active_auras` call with the overlay off |
| 4.2 | **GC: freeze after load, raise the gen-2 threshold.** `gc.collect(); gc.freeze()` once the run is built (after `LoadingState` hands over), `gc.set_threshold(700, 10, 1000)`. Un-freeze is not needed; frozen objects are the world and the assets. | `game/states/loading_state.py` hand-over, or `Game` | removes a 13 ms pause every ~10 s; **measured** in RND-010.3 on the owner's machine: one gen-2 of 8.6 ms in 600 frames, none frozen, but the frozen run's tail was worse (p99 38.51 against 33.74 ms; the two runs one after the other, not interleaved), so the gain is not shown yet | appendix A.2 shows zero gen-2 in 600 frames |
| 4.3 | **One drawable list per frame.** Build `(level, depth, draw)` once, bucket by level in one pass, sort each bucket once; cache `visible_rect()` per frame on the renderer; replace the per-enemy lambda plus forwarder with a bound method. | `visual/scene.py:37-152`, `core/state.py:755-784`, `systems/camera.py:80` | 0.5 to 1 ms at 150 in view; **measured** in RND-010.3 on the owner's machine: the per-enemy steps it removes are 0.09 ms at 150 and 0.16 at 250, and the bucketed list's variant shows no saving | pixel-identical frame; `test_depth_sort`, `test_render_cull` green |
| 4.4 | **Shade and ghost without per-frame copies.** Skip the shade walk when the body's cell block holds no shadow (one index lookup, already available); record the shaded scratch into a per-frame arena instead of `drawn.copy()`; cache the shaded ghost per `(frame id, shade key)` with a bounded cache like `_ghost_of`. | `visual/rendering.py:136-147`, `world/terrain/render.py:365-416, 500-550` | 1 to 2 ms at 150 in view, more under trees; **measured** in RND-010.3 in the packed scene (few trees): the shade walk 0.27 ms at 150 and 0.41 at 250, the ghost copy 0.01 ms (two shaded bodies) | pixel-identical; `test_ghost`, `test_enemy_sprite` green |
| 4.5 | **No SRCALPHA allocation per frame.** Bounded caches keyed by `(radius, colour, alpha)` for `_ring`, `_shape`, markers, hazards and the transient effects; the RND-008 appendix measured the ring cache at 0.30 → 0.20 ms per 100 rings. | `visual/elements/layers.py:132-148, 248-257`, `elements/markers.py:47-53`, `rendering.py:377-383`, `elements/transient.py:259-312` | 0.5 to 1.5 ms in an elemental fight | pixel-identical; `test_element_layers` green |
| 4.6 | **Cull particles and damage numbers to the view**, and stop `copy()`+`set_alpha` per frame for fading marks and trails (cache per alpha step of 1/16). | `systems/particles.py:100-109`, `ui/damage_numbers.py:190-213`, `status_marks.py:127-130`, `rendering.py:590-594` | 0.3 to 1 ms at 1200 particles | pixel-identical inside the view |
| 4.7 | **One grid rebuild per frame.** Bump builds its grid from post-move positions and changes only `_knock`; make `run.grid` that grid (check `buffs.update`'s Pinball throws, which move bodies between bump and combat; if they do, rebuild only the moved bodies' cells). Then `Separation` is no longer a frame stale. | `core/physics.py:117, 129`, `core/state.py:495` | 0.3 to 0.6 ms at 200 | `test_enemy_bump`, `test_enemy_nav`, element spread tests green; a test that the two grids answer the same query |
| 4.8 | **Bump by cell pairs.** Iterate occupied cells, test each cell against itself and its four forward neighbours, so each pair is visited once and the `seen` set goes away. Same contacts, same order of resolution per pair (sort the pair list by `(id(a), id(b))` if the current order is observable in a replay test). | `core/physics.py:144-165` | bump 1.38 → about 0.8 ms at 144 packed | `tools/benchmarks/spawn_stress.py --pack --bump` before/after; `tests/flows/test_run_determinism.py` green |
| 4.9 | **Enemy update constants.** `pow(BUMP_DECAY, dt)` once per frame; the status callback bound once per enemy, not a closure per frame; `Steering.add` one copy; `AvoidObstacles` float early drop like `Separation`; `AggroSense` range squared once. | `entities/enemy.py:188-193`, `entities/ai/steering.py:21`, `components/crowd.py:72-84`, `components/aggro.py:69` | 0.5 ms at 100, 1 ms at 200 (ENT-018's own estimate) | `test_enemy_ai*`, `test_enemy_update*` green, replay determinism green |
| 4.10 | **Brute-force scans to the grid.** Summons (`in_ring`), `_within_reach`, `chain_to_next` through `run.grid.query_circle` / `nearest`. | `entities/summon.py:155-164`, `combat/weapons/core.py:445-457`, `core/combat.py:343-356` | 0.2 to 0.8 ms with summons out | same targets chosen (test with a seeded crowd) |
| 4.11 | **`hibernate` and the watchdog.** Build the survivors list once instead of `remove` per body; one `SimpleNamespace` per tick; the watchdog keeps a dict keyed by `id` updated on spawn and cull instead of a set per frame. | `core/spawning.py:169-177`, `spawn/watchdog.py:93-96` | removes 0.5 s hitches at big sleeps | `test_population*`, `test_watchdog*` green |
| 4.12 | **LOD pad and phase.** `inflate(2*pad, 2*pad)` so the pad is what the config says; phase the skip by a per-enemy counter, not the list index. | `core/state.py:435-452`, `game/config.py:849-852` | small; correctness | a test that an enemy at pad−1 px ticks every frame |
| 4.13 | **A wash cache that holds a fight.** `element_fx.washed` as an LRU (1536, the one timed, or 1024; the memory is RND-010.D2, the owner's) in place of a dict that empties itself whole at 512; `hit_tinted` the same at 256 only if the owner wants the two alike (0.10 ms predicted). Added by RND-010.3, first in the order. | `visual/elements/__init__.py:199-246`, `visual/rendering.py:53-74` | **measured** at 250 in the saturated fight: 0.65 to 1.61 ms a frame (`wash_lru`, 1536), 1.90 ms predicted by the replay, the worst frame's misses 137 → 3, at most 80.6 MB held against 28.2 | pixel-identical; `test_element_colours`, `test_render_cull` green; `sprite_caches` replay before and after |

Sum of expected gains: about 5 to 8 ms per frame at 150 in view on the
owner's machine, which takes the trace's 100 to 149 row (14.6 ms p50)
comfortably under budget and the 150+ row (21.2 ms) to about the budget.
Not to 200 in view. RND-010.3's measurements put the draw tasks' share of
that well lower: 4.3 removes 0.09 ms of per-enemy steps at 150, 4.4's shade
walk is 0.27 ms in the packed scene, and 4.13 (not in the review) is a
fight's alone; the sum is not re-estimated until each task is measured
before and after.

## 5. Second stage: data-oriented hot loops, still Python, still exact

Only after section 4 is measured. Each is a bigger change with a design
note in the journal before building.

| # | Task | Why | Expected |
|---|---|---|---|
| 5.1 | **Batch body blits with `Surface.blits`.** For unshaded, untinted bodies (the common case), collect `(frame, dest)` pairs per terrace and call `screen.blits(pairs, doreturn=False)` once. Shaded or tinted bodies stay on the slow path. | removes the Python call per blit, which is most of the gap between 2.3's floor and the measured draw | 1 to 2 ms at 150 in view; **measured** in RND-010.3: every sprite blit at 150 costs 0.99 ms in all (7.36 µs each, in isolation), and `blit_floor` puts 200 at 2.25 ms on the owner's screen, so the batch can save only part of that |
| 5.2 | **Flow field off the frame path.** Options, measure each: (a) a coarser fill grid (64 px cells, 4x fewer cells) sampled with the existing bilinear `direction_at`; (b) fill only the reachable disc round the hero (the despawn ring is 1400 px, the fill walks the whole island); (c) a longer interval with the two-cell drift kept. `NAV_FILL_MAX_COST` already exists for (b). | a fixed 2 to 3 ms on 80 % of frames | 1.5 to 2.5 ms |
| 5.3 | **Movement probe with fewer floor scans.** Cache `room_of` per enemy per frame (five probes land in one room almost always), probe once and reuse; ENT-018's rejected index was per-probe, this is per-body. | 14 % of packed update | 0.5 to 1 ms at 200 |
| 5.4 | **Behaviour machine without per-tick allocation.** `Steering` reused per enemy; transitions checked only for the current state's list (already so?) with predicates that read floats, not Vector2s; `heading` stored as two floats. | 30 % of packed update | 1 to 2 ms at 200 |

With 4 and 5 done, 200 in view on the owner's machine is estimated at
about 18 to 20 ms. Still over. Section 6 is where that goes.

## 6. The decision for the owner: 200 on screen at 60

Three ways to clear the last row, all with a cost that is not performance
work:

1. **A draw LOD or a view cap.** Past about 150 bodies in view, skip the
   shade and ghost for the farthest, or let the spawn master hold bodies
   dormant until the in-view count drops. Changes the picture or the
   crowd; RND-010's constraint forbids it by default, so it is an owner
   decision. Cheapest by far.
2. **A compiled hot core.** The bump pass, the flow-field fill and the
   per-enemy steering as a small C extension or Cython module, with the
   Python objects left as they are. Buys 10 to 30x on those three; breaks
   the "vanilla, no build step" rule, needs a wheel per platform and the
   web build loses it (pygbag has no C extensions beyond pygame's own).
   numpy is ruled out as a game dependency by `CLAUDE.md`; the owner would
   have to lift that too.
3. **Another language or engine.** Godot (GDScript or C#), LuaJIT with
   LÖVE, or Rust with macroquad make 200 animated bodies trivial. It is a
   rewrite of about 57,000 lines of Python plus 3,500 tests. Not
   recommended to clear one row of the trace table.

The recommendation of the review: do sections 4 and 5, re-trace, then
pick between 6.1 and 6.2 with the measured gap in hand. Do not start 6.3.

## 7. Guardrails for whoever picks this up

- Pixels do not change in sections 4 and 5: whole-frame byte identity at
  150 and 250 packed, old against new (`pygame.image.tobytes`), as RND-008
  did. Gameplay does not change: `tests/flows/test_run_determinism.py`
  and the world digests stay green.
- Time without wrappers, old against new, in one sitting, before
  building (ENT-018.3). cProfile ranks; `perf_counter` decides.
- A change that alters the picture or the crowd goes to the owner as a
  decision (section 6), never in by default.
- `BUDGET_MS` is 16.67 ms (SYS-012). The harness counts frames over it;
  the goal line for each task is that count at 150, 200 and 250 packed.
- No CI, no hooks (`CLAUDE.md` Tests). Numbers go in
  `../journals/crowd_draw_journal.md` (draw) and a new ENT journal
  (update), never in a timing assertion.
- numpy stays out of game code (`CLAUDE.md` Tests).

## Appendix A: the review's probes

Both run headless. They now live under `tools/benchmarks/` (RND-010.3.2), as
`python -m tools.benchmarks.blit_floor` and `python -m tools.benchmarks.gc_probe`;
the ported `gc_probe` seats 200 at a run clock of 400 s, where this copy's
300 s seats 175. The originals stay below as the review ran them.

### A.1 `blit_floor.py`: what pygame alone costs

```python
"""Raw pygame floor: blit N enemy-sized sprites onto the logical surface
with no game logic. The ceiling the draw can be cut toward."""
import os, time
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()

def pct(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]

for (w, h) in [(1600, 900), (2560, 1080)]:
    screen = pygame.display.set_mode((w, h))
    sheet = pygame.image.load("assets/characters/blue/warrior/run.png").convert_alpha()
    fw = sheet.get_height()
    spr = pygame.transform.smoothscale(sheet.subsurface((0, 0, fw, fw)), (112, 112))
    shadow = pygame.Surface((48, 20), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 110), shadow.get_rect())
    bar = pygame.Surface((40, 5)); bar.fill((200, 40, 40))
    import random; random.seed(1)
    for n in (100, 200, 300):
        pos = [(random.random() * w, random.random() * h) for _ in range(n)]
        for extras in (False, True):
            ts = []
            for _ in range(120):
                t0 = time.perf_counter()
                screen.fill((20, 20, 30))
                for (x, y) in pos:
                    sx, sy = int(x) - 56, int(y) - 56
                    if extras: screen.blit(shadow, (sx + 32, sy + 92))
                    screen.blit(spr, (sx, sy))
                    if extras: screen.blit(bar, (sx + 36, sy - 6))
                ts.append((time.perf_counter() - t0) * 1000)
            label = "sprite+shadow+bar" if extras else "sprite only"
            print(f"{w}x{h}  n={n:3d}  {label:18s}  p50 {pct(ts, 50):6.2f}  p90 {pct(ts, 90):6.2f} ms")
```

### A.2 `gc_probe.py`: are the spikes garbage collections?

```python
"""Same crowd as the harness (seed 35, 200 live, hero jittering), update +
draw timed per frame, gc.callbacks marking which frames held a collection
and of which generation; then again with gen-2 effectively off."""
import os, sys, time, gc, random
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.getcwd())
import pygame
from tools.benchmarks.spawn_stress import build, cascade_setup

PACK = "--pack" in sys.argv
events, frame, t0 = [], [0], [0.0]
def cb(phase, info):
    if phase == "start": t0[0] = time.perf_counter()
    else: events.append((frame[0], info["generation"], (time.perf_counter() - t0[0]) * 1000))
gc.callbacks.append(cb)

def pct(xs, p):
    s = sorted(xs); return s[min(len(s) - 1, int(p / 100 * len(s)))]

def measure(label, frames=600):
    game, ps = build(35, 200, 0, 300.0, 2, save_path="/tmp/gc_probe_save.json")
    if PACK: cascade_setup(ps, prime=False)
    rng = random.Random(1); home = pygame.Vector2(ps.player.pos)
    surface = pygame.display.get_surface()
    for _ in range(60):
        ps.player.pos.update(home.x + rng.uniform(-24, 24), home.y + rng.uniform(-24, 24))
        ps.update(1 / 60); ps.draw(surface)
    events.clear(); tot = []
    for i in range(frames):
        frame[0] = i
        ps.player.pos.update(home.x + rng.uniform(-24, 24), home.y + rng.uniform(-24, 24))
        t = time.perf_counter(); ps.update(1 / 60); ps.draw(surface); tot.append((time.perf_counter() - t) * 1000)
    gens, ms = [0, 0, 0], [0.0, 0.0, 0.0]
    for _, g, m in events: gens[g] += 1; ms[g] += m
    print(f"{label}: live {len(ps.enemies)} p50 {pct(tot, 50):.2f} p99 {pct(tot, 99):.2f} max {max(tot):.2f} ms"
          f" | gc gen0/1/2 {gens} ms {[round(x, 1) for x in ms]} | tracked {len(gc.get_objects())}")

measure("default gc")
gc.collect(); gc.freeze(); gc.set_threshold(700, 10, 1000)
measure("gc.freeze() + gen-2 threshold 1000")
```
