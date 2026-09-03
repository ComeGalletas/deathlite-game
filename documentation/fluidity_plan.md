# Fluidity — where the frame time goes, and what would move it

> Assessment (2026-09-03), written after spawn master S7. Nothing here is
> implemented. Every number is measured on this machine with
> `python -m spawn.stress` (seed 35, 100 live enemies, 400 dormant) unless
> it says otherwise. The threading question is answered in section 4.

**In one paragraph.** The update loop's per-enemy cost is a linear scan of
every obstacle in the world inside `GameMap.is_walkable`, five times per
enemy per frame; a spatial index takes that call from 93 us to 4 us and
the update p50 from 6.0 ms to 1.2 ms. The spikes are the flow-field
rebuild, 15-19 ms per fill on the LD-10 worlds, which a time-sliced fill
removes without threads. Threads do not help CPU-bound Python under the
GIL and do not exist in the browser build; a worker *process* for the
flow field is the one place parallelism pays, and only on desktop. Do the
index first, the sliced fill second, and measure the draw side before
anything else.

---

## 1. Where a frame goes today

`PlayingState.update` with the tick LOD at its default (2):

| | p50 | p90 | p99 | max |
|---|---|---|---|---|
| update, 100 live | 5.8 | 27.0 | 29.8 | 34.1 ms |
| draw + flip, 100 live (15 in view), dummy video driver | 7.7 | 8.7 | | 62.5 ms |

The draw figure is the software path (`SDL_VIDEODRIVER=dummy`); the one
62 ms frame is the terrain blit cache filling on first sight of a new
band, not a per-frame cost. On a real display the flip waits for vsync
and the blits go through the GPU-backed window surface, so the number is
an upper bound, not a prediction.

The cProfile of 600 frames (LOD off, 8.2 s of update):

| Cost centre | Share | Note |
|---|---|---|
| `GameMap.is_walkable` (via `resolve_movement`) | 44 % | 93 us a call, ~5 calls per enemy per frame |
| `NavField.rebuild` | 42 % | 15-19 ms small class, 5-6 ms large; 97 rebuilds in 600 frames under jitter |
| enemy behaviour (`Behavior.tick`) | 6 % | the AI is cheap |
| bump resolver | 4 % | |
| spawn master, watchdog, placement | 1.6 % | |
| both spatial-grid rebuilds | 0.7 % | |

So the frame is two problems: a per-enemy constant that is far too
large, and a periodic spike that has nothing to do with enemies.

---

## 2. The per-enemy constant: the obstacle scan

`GameMap.is_walkable` ends with

    for o in self.obstacles:          # 565 obstacles on seed 35
        ...

on every call, after the floor and terrace tests. `resolve_movement`
calls it up to three times a move (the move, then each axis slide), and
each call probes five points. The run already holds a static
`SpatialGrid` over the obstacles (`PlayingState._obstacle_grid`, built
once for the AI's avoidance); the collider does not use it.

**Measured** by monkeypatching the scan to query a `SpatialGrid` (pad
64 px, the widest obstacle):

| | per call | update p50 |
|---|---|---|
| linear scan | 93 us | 6.0 ms |
| spatial index | 4 us | 1.2 ms |

**Done (2026-09-03).** `world/map.py` carries `_ObstacleIndex` (128 px
buckets, superset by the widest radius); `GameMap.obstacles` is a
property that rebuilds it on assignment; both scans read it. Stress
scene, 100 live: update p50 5.8 -> 1.1 ms; with the tick LOD off, 1.2 ms
-- the LOD is now worth 0.06 ms and could go back to 1. The playing
state's own `_obstacle_grid` (the AI's avoidance query) still builds its
own `SpatialGrid`; folding it into the map's index is a tidy-up, not a
win.

After this the next per-enemy cost is `_point_ok` -> `room_of`, a
linear walk over the nine island rects per probe (235k calls in the
profile). A chunk-cell lookup (`Room.cell` is the lattice coordinate;
islands do not share cells) makes it one dict read. Smaller win; do it
if the index alone is not enough.

---

## 3. The spike: the flow-field rebuild

`FlowField.rebuild` runs Dial's algorithm in pure Python over every
reachable cell inside `NAV_FILL_MAX_COST`: ~11,800 cells on the small
class at ~1.4 us each. A periodic refresh rebuilds one class per tick
(0.2 s apart); a player jump of two cells rebuilds both on one frame,
~22 ms. Running in play, the hero crosses two cells every ~13 frames, so
the jump path fires several times a second.

Three options, in the order to try them.

**3a. Time-slice the fill.** Give `FlowField` a `step(budget_ms)` that
resumes the bucket loop where it stopped, and double-buffer the cost
array so the *old* field keeps steering until the new one completes.
`NavCoordinator` starts a fill and advances it ~3 ms a frame; a 17 ms
fill lands in six frames. The field lags the player by ~100 ms, which
the two-cell drift trigger already tolerates. Pure Python, works in the
browser, removes the spike entirely. The "jump rebuilds every grid at
once" test in `test_enemy_nav` changes meaning (it becomes "a jump
starts every grid's fill") and is rewritten, not deleted.

**3b. A worker process (desktop only).** The fill is pure data -- a
traversable mask, a step mask, a seed, a cost cap in; a cost array out
-- so it can run in a `multiprocessing` worker with the arrays in shared
memory, the main loop polling for completion. Latency of a frame or two
is fine at a 0.4 s refresh. This is the one real use of parallelism in
this codebase (section 4). It does not exist in pygbag, so 3a is needed
anyway as the fallback; 3b is only worth adding if 3a's lag shows.

**3c. Bounding the fill to the active zone.** Tried in S7: 16.8 -> 13.9
ms, because `NAV_FILL_MAX_COST` already bounds the fill to about the
zone. Not worth it on its own.

---

## 4. Multithreading: what it can and cannot do here

- **CPython 3.12 holds the GIL.** Two threads running Python bytecode
  share one core; a flow-field fill on a thread would slow the main
  loop by exactly the time it takes. Threads only pay when the work
  releases the GIL -- C extensions such as numpy on large arrays, file
  and socket I/O. Nothing in the update loop is that.
- **The free-threaded build (3.13t / 3.14) is not an option today**:
  pygame's wheels and pygbag target the GIL build, and the browser has
  no threads at all (`loading_state.py` already notes this).
- **pygame surfaces are main-thread only.** The bake, the blits, the
  flip cannot move off the main thread regardless of the GIL.
- **Processes do pay**, for work that is pure data with a small
  interface: the flow-field fill (3b). World generation is also pure
  data up to the bake, but the loading screen already slices it a step
  per frame and the bake must be on the main thread, so a process there
  buys a smoother loading animation and nothing else.
- **numpy** (installed, 1.26) does not help the fill: Dial's algorithm
  is a priority queue, and an iterative relaxation over shifted arrays
  costs more than the Python loop it would replace (~100 iterations over
  143k cells). It would help a brushfire distance transform, which is
  what `clearance_transform` already is at generation time, not at
  runtime.

**Conclusion.** Threads: no. A process for the flow field: yes, on
desktop, after the sliced fill, if the lag shows. Everything else is
algorithmic.

---

## 5. Smaller items, in order of value

1. **Measure draw** -- done, section 7. Add `--draw` to `spawn.stress` so
   it stays measured.
2. **`room_of` chunk lookup** (section 2, second paragraph).
3. **The bump resolver** is 0.6 ms a frame at 100 live and scales with
   local density, not the count. Fine as it is.
4. **Frame pacing.** `FPS = 120` gives an 8.3 ms budget; with the index
   and the sliced fill the update p99 should sit near 3 ms and draw near
   5, inside the budget with no spikes. A fixed update step with render
   interpolation would then be complexity for nothing; revisit only if
   the numbers say otherwise.

---

## 6. Order

| Step | Effort | Wins | Where |
|---|---|---|---|
| obstacle index in the collider | an hour | update p50 6.0 -> 1.2 ms | `world/map.py` |
| draw measurement | an hour | knowledge | `spawn/stress.py` |
| time-sliced flow-field fill | a day | removes the 15-30 ms spikes | `world/nav/field.py`, `game/states/playing/navigation.py`, `tests/ai/test_enemy_nav.py` |
| `room_of` chunk lookup | an hour | a further cut of the probe | `world/rules/floor.py` |
| worker process for the fill | a day | desktop-only, only if the lag shows | new `world/nav/worker.py` |

---

## 7. Render (measured 2026-09-03)

`game._render()` under the stress scene, dummy video driver, 300
frames after a warm-up: **p50 22.6 ms, p90 25.7 ms** with 56 live and 18
in view; a second run with 43 live measured 8.1 ms. The variance is
which bodies are in view and under trees, and that is the whole story:

| Cost centre | Share of render | Note |
|---|---|---|
| `shade_character_frame` | **74 %** | 15,147 calls in 300 frames; each walks all 336 tree shadows in the world (3.0 M `_z_surf` lookups) |
| every other blit (terrain bands, decor, obstacles, water) | 12 % | 214 blits a frame at ~13 us; sheets are `convert_alpha`'d |
| obstacles, water, ground bands, decor, scenery sort | 6 % | 1.2 + 1.0 + 0.8 + 0.4 + 0.6 ms |
| HUD, overlays, fill, flip | < 2 % | |

Two facts behind the 74 %:

- **The actor pass does not cull.** `PlayingState._actor_items` emits a
  draw for every live enemy; with the spawn master's zone that is up to
  100 bodies a frame of which a dozen are on screen. Each off-screen
  body still fetches its frame and runs the shade pass before blitting
  nothing useful.
- **The shade pass is O(characters x shadows).** For each character it
  scales (cached) and rect-tests every tree shadow in the world, then
  allocates an overlay surface and a frame copy when one intersects.

Measured with monkeypatches on the 43-live scene (baseline 8.1 ms):

| Variant | p50 | p90 |
|---|---|---|
| baseline | 8.10 | 8.87 ms |
| A: cull actors outside the view + 256 px | 5.99 | 6.75 |
| A + B: test only shadows near the view | 4.78 | 5.18 |
| A + C: no character shading at all (the bound) | 3.65 | 4.10 |
| world only, hero as the sole actor | 3.46 | 3.78 |

So the static world costs ~3.5 ms and everything above that is the
actor pass. In order:

1. **Cull actors to the padded view** in `_actor_items` (enemies, death
   poofs, summons; the boss when off screen). A body outside the view
   plus its widest sprite reach draws nothing. About a quarter of the
   render at 43 live, more at 100.
2. **Index the tree shadows.** Bucket `_tree_shadows` once at bake (they
   are static) in a coarse grid keyed by world cell, and have
   `shade_character_frame` query the character's rect against that
   instead of walking the world. Same result, O(nearby). Together with
   1 this is the 4.8 ms row; a spatial index does slightly better than
   the view prefilter measured because it also skips the on-screen
   shadows that do not touch the character.
3. **Stop allocating per character per frame.** When a shadow does
   intersect, the pass makes a fresh SRCALPHA overlay and a frame copy;
   a scratch overlay reused across characters (cleared per use) and an
   in-place multiply on the copy halve the remaining shade cost. The
   red hit tint (`hit_tinted`) likewise copies the frame every frame of
   the 0.26 s hurt window; a one-entry cache keyed by the frame's id
   makes that one copy per hit.
4. **The static 3.5 ms** is ~200 blits of cached scaled surfaces plus
   the water band and decor. The lever there is fewer, larger blits:
   composite each island's ground bands into one surface per level at
   bake (they are already per-level surfaces per room) and the decor
   that never moves into them, leaving per-frame blits for the
   animated foam and the sprites. That is the renderer refactor's job,
   not a tweak; do it only if the frame is still over budget after 1-3.

None of this touches the update loop; all of it is browser-relevant
twice over, since render there is already 14-20 ms and scales the same
way.

---

## 8. Holding 60 fps on a modern PC (measured 2026-09-03)

A stable 60 means every frame under 16.7 ms of update plus render plus
flip, not a good average. Probed on the stress scene with the hero
**walking** in a slow circle (so enemies come into view and the flow
field's drift trigger fires as it does in play), 1,200 frames, the
obstacle index in, tick LOD 2, a pytest run sharing the machine:

| | total p50 | p90 | p99 | frames over 16.7 ms |
|---|---|---|---|---|
| 100 live | 16.9 | 23.1 | 58.0 ms | **51 %** |
| 30 live (74 by the end, the director kept spawning) | 11.4 | 18.2 | 54.3 ms | 20 % |

Of the frames over budget at 100 live: 59 held a flow-field rebuild
(those frames total ~54 ms), 5 a terrain blit-cache fill, 1 a GC
collection, and **551 were ordinary frames whose render alone was
14-15 ms**. GC is not a factor: 260 collections in 20 s cost 16.5 ms in
all, the worst one 6.7 ms.

So consistency is two things, in this order:

1. **The render median.** With bodies in view the draw is 10-15 ms
   before update is added; section 7's three items (cull actors, index
   the tree shadows, stop the per-character allocations) take it to
   about 5 ms, which leaves ten for everything else. This is what turns
   the 51 % into a few percent.
2. **The rebuild spike.** A frame with a flow-field rebuild costs three
   times the budget and there are three a second while the hero walks.
   Section 3a (the time-sliced fill at ~3 ms a frame) is the only fix
   that removes it rather than thinning it. After 1 and 2 the p99 sits
   under the budget.

Then the pacing itself, which cost reduction does not address:

3. **Sync the flip to the display.** `set_mode` takes no flags and
   `clock.tick(60)` throttles with a 1 ms sleep after the work, so even
   a frame that fits is presented whenever it finishes, not on the
   refresh: a frame that lands at 16.9 ms shows for two refreshes and
   the next for none, which reads as a stutter although the average is
   fine. pygame 2.5 offers `set_mode(..., pygame.SCALED | pygame.DOUBLEBUF,
   vsync=1)`: the flip waits for the refresh and the cadence is the
   monitor's. `SCALED` routes the window through a texture, which costs
   an upload per frame (~1-2 ms at 1600x900) and changes nothing else
   about the blits; the software `flip()` today costs about the same on
   the dummy driver. Try it behind a `config.VSYNC` flag and measure
   with the F1 overlay on the real display, where the current numbers
   come from a dummy driver and say nothing about presentation.
4. **Keep the deferrable work deferrable.** The spawn master already
   spreads its own work (wakes 8 a frame, samples two enemies a frame in
   the watchdog, one spawn pack a tick); the sliced fill puts the nav on
   the same footing. The rule for anything added later: no single frame
   does a job that can be split, and the split has a per-frame budget in
   data.
5. **Warm the blit cache during loading.** Five hitches a run from a
   band's first appearance; a pre-warm pass over the start island during
   the loading screen removes them and costs nothing visible.
6. **`gc.freeze()` after loading**, and a raised generation-0 threshold,
   are a cheap safety net against a future allocation-heavy feature,
   not a fix for anything measured today.

A fixed update step with render interpolation is not on this list: it
decouples simulation from presentation, but with items 1-3 done the
frame fits with margin and the complexity would buy nothing.
