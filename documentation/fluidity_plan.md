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

**Proposal.** `GameMap` builds the obstacle grid once (obstacles are
final after the unseal repair and never move) and `is_walkable` queries
it; `blocking_obstacle_hit` (projectiles) reads the same grid. The
playing state's own `_obstacle_grid` then reads `game_map`'s instead of
building a second one. Risk: none that a test would not catch --
`test_pathfinding` and the collider tests pin the answers, and the index
returns a superset of the disc test's candidates.

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

1. **Measure draw.** The stress harness times `update` only; the S7
   journal addendum has one draw measurement. The renderer culls to the
   view, so 100 live costs about what 10 in view cost, but the terrain
   blit cache and the depth sort have not been profiled under a crowd.
   Add `--draw` to `spawn.stress`.
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
