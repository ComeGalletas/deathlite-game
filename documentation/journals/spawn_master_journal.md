# Spawn master — journal

Evidence for the phases of `documentation/plans/spawn_master_todo.md`, against the
design in `documentation/spawn_master_design.md`. One entry per phase:
what landed, what was measured, what was decided on the way, what was left.

---

## S1 — Spawn points at generation (2026-09-03)

**Status: done.** Spawn points and resource anchors are decided as the last
stage of `generate_world_steps`, after the scatter and the unseal repair,
and read back off the layout by the run. Nothing consumes them yet beyond
the dev overlay; S3 wires placement.

### What landed

- `config.SPAWN_POINTS_PER_FLOOR = 10`, snapshotted into `GenSettings` as
  `spawn_points_per_floor`. The count is **per terrace of each island**.
- `world/layout.py`: `SpawnPoint(room_id, floor, x, y, clearance, tags)`
  and `ResourcePoint(room_id, floor, x, y, kind)` as `NamedTuple`s, and
  `WorldLayout.spawn_points` / `resource_points`. Records live in the data
  model because `generate_world` produces them; the `spawn/` package holds
  the read side.
- `world/gen/spawnpoints.py`: the stage. One island per yield
  (`"spawn points N of M"` on the loading screen). Candidates are ground
  cell centres passing the six filters of the design (ground, terrace
  margin, obstacle gap, bridge-mouth keep-clear, clear discs, lattice
  passability), each reused from the scatter / inset / nav modules rather
  than re-derived. Per terrace, farthest-point sampling picks the target
  count: seed at the candidate nearest the terrace centroid, then take the
  candidate farthest from everything kept. Large-class candidates first,
  small-only ones top up, and a floor under three retries at the bare
  terrace margin.
- `world/gen/tuning.py`: the geometry constants (`_SPAWN_*`, `_RESOURCE_*`).
- `spawn/points.py`: `PointIndex` (by island, by `(island, floor)`,
  resource anchors by island, `in_rooms`).
- `world/gen/validate.py`: every point stands on plain ground of the island
  and floor it names.
- Dev overlay: `_dev_show_spawn_points` on `PlayingState`, F8
  (`DEBUG_KEYS["toggle_spawn_vis"]`), a "Spawn points" row in the dev menu,
  `WorldRenderer.spawn_point_overlay` beside the collider pass. Diamonds
  for enemy points (bright large class, dim small-only), squares for
  resource anchors, each labelled with its floor (anchors also with the
  first letter of their kind). Three colours in `config`.
- Tests: `tests/world/test_spawn_points.py` (16) over the four cached
  seeds; two dev-mode tests for the row and the key.

### Measured

| | seed 35 | seed 7 |
|---|---|---|
| stage cost | 0.40 s | 0.41 s |
| of which the widest-class `NavGrid` | ~0.11 s | |
| enemy points | 200 (20 floors x 10) | 205 (21 floors, one short) |
| resource anchors | 72 | 72 |
| `large` / `small` | 200 / 0 | 204 / 1 |

The one short floor (seed 7, island 4, floor 2) seats 5 of 10: a small top
terrace. Left short by design; logged at INFO.

Generation went from 1.7 s to 2.1 s per world. The stage is one loading
step of ~0.35 s before its first yield (the lattice) and then a few tens of
milliseconds per island. The lattice is the third built per run (unseal
builds a bare one, the loading screen builds the `NavField` pair after the
bake); sharing them is on the S7 list.

### Decided on the way

- **Candidates are cell centres, no jitter.** The design left it open; a
  centre is deterministic without spending RNG and the run adds its own
  offsets when it rings followers around a leader (S3).
- **Points are admitted at the small class too.** The design's rule 6
  tested only the widest body. On the four seeds that gave every floor its
  ten anyway, but a cramped upper terrace would have been starved, so the
  stage fills from large-class candidates first and tops up with small-only
  ones, recording which in `clearance`. The placement rule in S3 reads it.
- **`edge` means water, not a wall.** The first cut tested against
  `room.cells` and tagged 193 of 200 points as edge, because every terrace
  rim counted. It now tests the grid for the sea (no cell) or a lake.
- **The layout digest moved; the geometry did not.** `world/digest.py`
  walks every field of the model, so two new lists on `WorldLayout` change
  the four pinned layout digests (re-pinned with
  `python -m tools.verification.world_digest --write`). The bake and frame digests are
  unchanged, and `test_the_knob_changes_the_count_and_nothing_else` pins
  that the islands, bridges and obstacles digest identically with the knob
  at 10 and at 4: the stage's only RNG is private, keyed by seed and
  island, and spent on the resource kind alone.
- **Resource anchors are per island, not per floor** (`8`), since nothing
  reads them yet and the knob the user asked for is the enemy one.
- **The stage is a declared reader of the inset field.**
  `test_inset.PhaseTests` fences who may read the terrace margin; the
  stage is added to the fence on purpose, because a spawn point has to
  keep the same margin a body does, asked of the same field.

### Suite

878 tests, all green after the fence above was widened (the only failure
the change caused). Full run 6 min 7 s on this machine.

### Left for later

- Sharing one lattice between unseal, this stage and the run's `NavField`
  (S7).
- The `arena` tag from the design is not emitted: elite arenas are retired
  in the current brief. The `boss` tag covers the boss island.
- Point cooldown dimming in the overlay arrives with placement (S3).

---

## S2 — Tables to data (2026-09-03)

**Status: done.** The phase schedule is data, the director lives in the
`spawn/` package, and a replay proves the move changed nothing.

### What landed

- `data/spawn_tables.json`: `phases` (the old `_PHASES` literal, number for
  number), `elites` (default `elite`, rare `brute` at 0.15), `groups`
  (templates for S3: leader, follower spans, optional clearance and tag
  preference), `difficulty` (per-level overrides, empty today), `residents`
  (S4) and `pacing` (S6) with the design's numbers, awaiting consumers.
- `spawn/tables.py`: `SpawnTables` -- shape checks, enemy-id checks,
  `phase_at(fraction, difficulty)`, `phases(difficulty)` (a level's own
  list replaces the shared one), `group(name)`, `enemy_ids()`.
- `game/content.py` loads the file and checks every enemy id against
  `enemies.json`; a bad table is a `ContentError` at boot.
- `spawn/budget.py`: `SpawnDirector`, moved from `world/spawning.py`. Same
  public surface plus `tables=` (defaults to the loaded content) and
  `roll_elite()`. `world/spawning.py` keeps `ring_point_outside_view` and
  re-exports the director; `PlayingState` imports from `spawn.budget`.
- Tests: `tests/spawn/test_tables.py` (13), `tests/spawn/test_budget.py`
  (the director tests moved from `tests/world/test_spawning.py`, plus the
  sequence replay and two new ones), `tests/world/test_spawning.py`
  reduced to the ring-point tests.

### The proof

`tests/spawn/director_sequence.json` was written by the **old** module,
before it was touched: a scripted 600 s run at 30 Hz under
`random.Random(11)`, two kills every twenty frames, the boss marked
in-line, on each of the three difficulties (1417 / 1275 / 1158 spawns).
`test_the_tables_reproduce_the_old_literal_draw_for_draw` replays the same
script through the new director and compares the lists whole. The elite
roll kept its exact form (`random() < rare_chance` -> rare) rather than
becoming a weighted `choices`, which would have spent the same draw with
the opposite mapping and moved every sequence.

### Decided on the way

- **The four difficulty factors stay in `config.DIFFICULTIES`.** The design
  said so; the table's `difficulty` section carries only what is *not* a
  factor -- a level's own phase list -- and today carries nothing.
- **Phases keep `types`, not `groups`.** Behaviour-preserving means the
  director still draws single enemy ids; S3 switches the rows to group
  weights when placement can put a pack on one point.
- **`residents` and `pacing` ship now with no reader.** They are the
  design's numbers, in the file the design says they live in, so S4 and S6
  add code rather than data. Nothing validates them yet beyond JSON shape.

### Suite

895 tests, all green on the first full run (8 min 4 s; the suite grew by
17 and the machine was busier than during S1).

---

## S3 — The master, placement and groups (2026-09-03)

**Status: done.** Enemies now enter the run through one facade, land on
the points generation vetted, and arrive as packs.

### What landed

- `spawn/host.py`: the `Host` protocol -- clock, dice, layout, player
  position / floor / view, walkability, room lookup, a fallback point,
  live count, enemy radius, `make_enemy`, a neighbour query, and the bus.
  The master imports nothing from `entities` or `game.states`.
- `spawn/placement.py`: `SpawnRequest` and `Placement`. `candidates()` is
  the six-step filter of the design (zone weight, cooldown, padded view
  and minimum distance, clearance class, no live body within two radii,
  same-floor and preferred-tag weights); `choose()` draws one from the
  host's RNG and marks it used; `ring()` seats followers evenly round the
  leader with one wider retry. Knobs from the new `placement` section of
  `data/spawn_tables.json`.
- `spawn/master.py`: `SpawnMaster.update(dt)` ticks the director and seats
  the pack it emits together; `spawn_at`, `spawn_group`, `set_modifier` /
  `clear_modifier` (`pressure` = the product, scaling the director's
  cadence). An unseatable pack is kept as debt (oldest first, capped at
  20) and retried each tick; past `relax_after` the view rule loosens.
  Every entry point checks `enemy_count_cap` per body, as `spawn_enemy`
  did.
- `game/states/playing/spawning.py`: `PlayingHost` (the protocol over the
  state, and the only place `Enemy` is constructed) and `EnemyControl`
  reduced to forwarders, so `tick_director`, `spawn_enemy`, `summon`,
  `spawn_boss` keep their callers.
- `Events.ENEMY_SPAWNED(enemy_id, owner, room)`; `owner` is `director`,
  `direct`, `summon`, `group`, or whatever a caller passes (`arena`).
- The dev overlay dims a point on cooldown.
- `GameMap.offscreen_spawn_point` is the fallback for a world with no
  points (the one-room test world, or the knob at 0).
- Tests: `tests/spawn/test_placement.py` (12), `test_master.py` (16),
  against `tests/spawn/fakehost.py`.

### Measured

Seed 35, dev run, hero standing still and invulnerable, clock pinned to
the late phases, 90 s at 60 Hz: 138 spawned, 135 live, 0 deferred, no
debt; every leader on a vetted point; live bodies spread over the
player's island and its three neighbours (57 / 43 / 28 / 7). Whole
`PlayingState.update` averaged 13.2 ms/frame with that crowd -- the
number S7 starts from, not a target met.

### Decided on the way

- **The pack is the group.** The design's S3 switched phase rows to group
  weights. That would have moved the S2 sequence pin for no gain: one
  `SpawnDirector.update()` already returns one pack's ids, so the master
  seats *that* together and the tables' `groups` templates serve the
  scripted entry point (`spawn_group`) instead. Rows switch to groups
  when a phase needs a mix the pack roll cannot express.
- **Zone before locality.** Until S4 the rooms in play are the player's
  island and its tree neighbours, all at weight 1; a player off every
  island (a test, a bridge) gets every island with points. S4 replaces
  `SpawnMaster.zone()` with current / heading / grace weights.
- **The master owns the cap and its exceptions.** The first cut kept the
  old rule that the live cap refuses every spawn, arena elites included.
  The user's standing rule is that the spawn master has full control over
  enemy spawning, scripted spawns included, so the tables now carry
  `owners.cap_exempt` (`["arena"]`) and the master seats those whatever
  the count; the arena tags its spawns `owner="arena"` and keys its
  tracking off the enemies actually made rather than `ps.enemies[-1]`.
  The director is never exempt. The enemy summoner's brood and the boss's
  adds (`owner="summon"`) stay under the cap. The hero's own summons (the
  wolf and the totem) are not enemies and never touch the master.
- **A pack's clearance is its widest body.** The request carries the
  largest radius in the pack and needs a `large` point if that exceeds
  the small class, so a tank leading husks does not land on a point only
  a husk fits.
- **The run's RNG stream moved.** Placement draws from the run RNG where
  the old helper drew differently, so a given seed no longer produces
  the same run it did; nothing pinned that, and the director's own
  sequence (its RNG in isolation) is still pinned by S2.
- **A retry never re-queues itself.** The first cut had a failed retry
  queue the pack inside `_place_pack` *and* in the retry loop, so debt
  doubled every tick (1975 packs after 200 ticks in the test written to
  pin the cap of 20). Retries run with `queue=False` and are put back in
  their old place on failure.

### Suite

921 tests. The full run (6 min 54 s) was started before the debt fix
above and failed only on the test that caught it; `tests/spawn` (57)
re-run green after the fix, nothing else touches the debt path.

---

## S4 — Locality and population (2026-09-03)

**Status: done.** Only the islands in play carry live enemies; the rest
are records. Islands seed residents on first visit.

### What landed

- `spawn/locality.py`: `Locality` -- current island (re-read on leaving),
  heading island (best-aligned neighbour, past `align`, held for `dwell`),
  grace island (`grace` seconds after leaving), bridge handling (the far
  end is the heading at once), `active()`, `is_active()`, `weights()`
  (current 1.0, heading `heading_weight`, grace `grace_weight`).
- `spawn/population.py`: `DormantEnemy` (slotted: kind, spot, floor,
  island, hp, max hp, shield, speed, status, owner, timestamps) and
  `Population` -- `hibernate()` every `tick` for out-of-zone, idle,
  non-exempt enemies; `activate()` queues an island's records farthest
  first; `wake_some()` wakes `wake_budget` per frame, moving a blocked
  spot to the nearest free point on its floor and a long-asleep one
  (`scatter_after`) to a random point of its island; a record with
  nowhere to stand stays dormant.
- `spawn/master.py`: the zone comes from the locality when
  `config.SPAWN_LOCALITY` is on (the S3 neighbour zone otherwise); islands
  joining the zone wake their records and, on first visit, seed residents
  (`residents` table: packs rolled off the director's current phase with
  the new `SpawnDirector.roll_pack`, owner `resident`, seated on that
  island only); `ROOM_ACTIVATED(room, woke, seeded)` and
  `ROOM_DORMANT(room, slept)` events; two dev switches, `all_active` and
  `frozen`.
- Two caps: `config.ENEMY_LIVE_CAP = 100` clamps the director's growing
  cap (`SpawnDirector.live_cap`, `None` for the isolated director the S2
  fixture pins); `config.ENEMY_COUNT_HARD_CAP` now bounds live + dormant.
- The Host grew `difficulty`, `player_heading`, `floor_at`, `room`,
  `corridor_at`, `live_enemies`, `owner_of`, `is_pursuing` (the aggro
  slot), `sleep`, `wake`; `make_enemy` takes the owner and stamps it on
  the enemy. All on `PlayingHost`, mirrored in `tests/spawn/fakehost.py`.
- Debug overlay: `zone cur/head/grace` and `population live/dormant/cap/
  debt`. Dev menu: "Activate all rooms" and "Freeze spawns".
- Tables: `locality`, `population`, `owners.never_sleep` (`arena`,
  `boss`).
- Tests: `tests/spawn/test_locality.py` (12), `test_population.py` (15),
  one dev-mode test for the two rows.

### Measured

Seed 35, dev run, clock pinned to the late phases. Twenty seconds on the
start island: 48 live, all on island 0, nothing dormant. Teleport to the
far island: within ten seconds 53 had slept, island 7 was seeded and
carried 31 live, and whole-state update averaged **5.1 ms/frame** (S3's
same scene held 135 live at 13.2 ms). Teleport back: all 53 woke, 60
live on the start island, 35 still dormant elsewhere.

### Decided on the way

- **Pursuers never sleep.** The rule is the aggro timer (`is_aggroed`),
  read through the host, so a chase across a bridge survives the zone
  edge and an enemy that lost interest does not.
- **On a bridge, nothing sleeps.** An enemy with no island under it is
  skipped by the sweep rather than assigned to either end.
- **Residents are rolled off the current phase**, not the `groups`
  templates: an island entered at minute eight should hold minute-eight
  enemies. Counts by island kind and difficulty from the table; no run-
  fraction scaling beyond what the phase already carries.
- **A free point is a walkable point.** The first cut of the wake
  fallback only checked cooldown and live bodies, so an island whose
  points were all under a hazard could wake a record into the wall; the
  test for "nowhere to stand" caught it and the check now asks the host.
- **The world cap counts the queue.** Records waiting to wake are still
  population; `total_dormant` includes them so the cap cannot be
  overshot on a wake frame.

### Suite (S4)

951 of 952 on the first full run; the one failure was the new dev-menu
test, because "Freeze spawns" stopped the director but not the residents
that "Activate all rooms" seeded a frame later. Frozen now suppresses
resident seeding too (the island is not marked seeded, so it seeds when
next activated unfrozen). Re-run green.

---

## S5 — Watchdog (2026-09-03)

**Status: done.** Bodies that are stuck, embedded or lost are recycled
with their state; the arena's are moved in place.

### What landed

- `spawn/watchdog.py`: `Watchdog.update(host, now)` samples each live
  enemy once per `sample_interval`, staggered by identity, and returns
  `Verdict(enemy, reason, poof)`s. Off floor / off world (not walkable at
  its radius and not on a bridge; no island and no bridge) is immediate;
  stuck needs pursuit intent, movement intent, no attack, more than
  contact range from the player, and `window` samples within one radius.
  A verdict on a visible body is held until it leaves the view or
  `on_screen_wait`, then carries a poof.
- `SpawnMaster.recycle(enemy, reason, poof)`: placement on the same
  island (nearest free point if nothing off screen; the point is asked
  for floor once more, a hazard can sit on one), sleep -> `recycles + 1`
  -> wake, so HP, shield, speed and status survive and nothing is
  granted; `never_sleep` owners are relocated as the same object so the
  arena's id tracking holds; past `max_recycles` the body is dropped and
  logged at WARNING with seed-free coordinates. `ENEMY_RECYCLED(enemy_id,
  reason)`; `recycled` / `discarded` counters; `recycled n` on the
  overlay.
- `DormantEnemy.recycles`; the Host grew `player_radius`,
  `wants_to_move`, `is_attacking`, `poof`, `relocate`.
- Tables: `watchdog` (`sample_interval` 1 s, `window` 4, `on_screen_wait`
  8 s, `max_recycles` 3, `contact_margin` 8).
- Tests: `tests/spawn/test_watchdog.py` (17).

### Measured

Seed 35, dev run, director frozen: one chaser spawned inside a rock off
screen and one 300 px off the world. Within four seconds both were
recycled onto vetted points of the start island, walkable, HP intact.

### Decided on the way

- **Only a chase can be stuck.** The first rule was "wants to move and
  makes no headway", and the smoke run recycled a freshly landed idle
  wanderer a second time: wander pauses for seconds on purpose, so four
  samples inside one radius is normal for it. The rule now also requires
  the aggro timer to be running.
- **Stuck is spread, not displacement.** The window's samples must all
  lie within one radius of the first; a body oscillating in a corner
  fails that, a slow but steady one does not.
- **Hold on screen, poof on release.** An embedded body the player can
  see waits up to eight seconds before it vanishes with the shared death
  poof, so the teleport reads as a thing that happened, not a glitch.
- **The third strike is a log line, not a game event.** A body that
  cannot be seated three times says more about the world than the enemy.

### Suite

969 tests, 968 passed and 1 skipped on the first full run (7 min 20 s).

---

## S6 — Pacing (2026-09-03)

**Status: done.** The cadence follows the condition of the run, inside a
rail, with a dead-band, and the dev menu can push it by hand.

### What landed

- `spawn/pacing.py`: `Pacing.update(dt, now, hp_fraction, live, live_cap)`
  computes five signals in -1..1 (`hp_fraction`, `damage_rate`,
  `kill_rate`, `crowd`, `lull`), takes their weighted mean, maps it to a
  target inside `bounds` (leaning to the upper bound above zero, the
  lower below), holds 1.0 inside `dead_band`, and smooths with an EMA of
  time constant `tau`. Kills, spawns and damage are counted over a
  sliding `window`; `damage_rate_full` is the HP fraction per second that
  reads as -1; `lull_seconds` is a full lull.
- The master: `pressure` = `pacing.value` x the named modifiers'
  product; the director's `dt` is scaled by it. `on_spawn` is fed from
  `_make`; `player_damaged` and `enemy_killed` are subscribed through the
  Host (`subscribe`), with `player_hp_fraction` / `player_max_hp` for the
  health signals. `PlayingHost.close()` drops the subscriptions on
  `PlayingState.exit`.
- Dev menu "Spawn pressure" row cycling a `dev_menu` modifier through
  x1 / x2 / x4 / x0 / x0.5 (x1 clears it); overlay line
  `pressure = pace x mods [signals]`.
- Tables: `pacing` gained `window` 10 s, `lull_seconds` 20 s,
  `damage_rate_full` 0.1, and shape checks (bounds straddle 1, weights
  non-negative).
- Tests: `tests/spawn/test_pacing.py` (13), one dev-mode test.

### Measured

Seed 35, dev run, hero at full health standing still under auto-attack,
clock at 200 s, after 30 s: pressure 1.08 with signals hp +1.00,
damage 0.00, kills -0.94, crowd -0.44, lull +1.00 -- health and quiet
lean it up, the untended crowd and the slow kills hold it near one.
Leaving the run drops the master's two bus handlers.

### Decided on the way

- **Pacing does not move the live cap.** The design let pressure
  multiply it; a strong player would then push the simulation past the
  performance budget the cap exists for. Pressure scales cadence only,
  and the cap stays `config.ENEMY_LIVE_CAP`.
- **The rail bounds the pacing value, not the modifiers.** A dev x4 or
  x0 is a request to see the extreme; the bounds are for the signal.
- **Rates are windows, not EMAs.** Kills, spawns and damage over the
  last ten seconds are counted from timestamps; the one EMA is on the
  output, which is where the smoothing belongs.
- **`kill_rate` is kills per spawn minus one**, clamped: clearing twice
  as fast as the master spawns is +1, killing nothing while it spawns
  is -1, and a quiet stretch with neither is 0.

### Suite

983 tests, 982 passed and 1 skipped on the first full run (6 min 55 s).

---

## S7 — Performance pass (2026-09-03)

**Status: done.** Measured, one lever pulled, two declined with numbers,
the gate removed.

### The harness

`python -m tools.benchmarks.spawn_stress` (`tools/benchmarks/spawn_stress.py`): a real dev run at 300 s,
`--live` enemies seated by the master's own placement in the zone,
`--dormant` records banked in the other islands, `--frames` updates with
the hero jittering by up to 24 px a frame (so the flow field's drift
trigger fires as it would in play), reporting p50 / p90 / p99 / max of
`PlayingState.update`. `--profile` adds cProfile's top entries. It is a
CLI, not a test: a timing assertion in the suite would only ever be
flaky.

### Measured (seed 35, 100 live, 400 dormant, 1200 frames)

| | p50 | p90 | p99 | max |
|---|---|---|---|---|
| LOD 1 (off) | 7.81 | 29.07 | 33.90 | 42.99 ms |
| LOD 2 | 5.81 | 27.69 | 30.73 | 35.62 ms |
| LOD 3 | 5.08 | 27.05 | 30.59 | 40.57 ms |
| **LOD 2, default** | **5.78** | **27.02** | **29.82** | **34.14 ms** |

The profile (600 frames, LOD off) of 8.2 s of update time:

- `GameMap.is_walkable` via `resolve_movement`: 3.6 s, one call per
  enemy per frame at ~88 us. **The per-enemy cost is the movement
  probe**, not the AI (`Behavior.tick` 0.47 s).
- `NavField.rebuild`: 3.4 s over 97 calls, 15-19 ms per small-class
  fill, 5-6 ms per large. **The p90 is the flow field**, and it does not
  depend on the enemy count at all.
- Everything the spawn master does per frame (`SpawnMaster.update`,
  the watchdog, placement): 0.13 s, under 0.25 ms a frame.
- Both `SpatialGrid` rebuilds together: 0.06 s, 0.1 ms a frame.

### What landed

- **Tick LOD**, `config.ENEMY_LOD_SKIP = 2`: an enemy that is neither
  chasing (aggro timer lapsed) nor inside the view padded by
  `ENEMY_LOD_VIEW_PAD` updates every other frame with a doubled `dt` and
  sits the frames between out entirely. The design had it integrate
  movement every frame and skip only the behaviour tick; the profile
  said that would have saved almost nothing, so the whole frame is
  skipped. p50 down 26 %. `EnemyControl.lod_eligible` decides (it reads
  the aggro slot, which the master's package must not); the loop is in
  `PlayingState._phase_update`. Tests: `tests/core/test_lod.py` (4).
- The `SPAWN_LOCALITY` config gate is gone; `SpawnMaster.use_locality`
  stays as a test switch (default on).

### Declined, with numbers

- **Sharing the `SpatialGrid`** between combat and bump: 0.1 ms a frame
  at 100 live. Not worth a second owner for the grid.
- **Sharing the widest-class `NavGrid`** between unseal, the spawn-point
  stage and the run's `NavField`: three builds of ~0.11 s at load, so
  ~0.2 s of a ~4 s load. Caching it on the layout would also put a
  lattice into the pinned layout digest, which walks every field.
- **Bounding the flow field to the active zone**: tried as an
  experiment (a room mask ANDed into the traversable set). The small
  class went from 16.8 to 13.9 ms because `NAV_FILL_MAX_COST` already
  bounds the fill to about the zone (11.8k cells reached against 10.8k
  masked). Not enough to justify reaching into `world/nav`.

### Left on the table

The flow-field rebuild is now the dominant frame-time event on the
LD-10 worlds: 15-19 ms for the small class, and a player jump rebuilds
both classes on one frame (~22 ms). It is independent of the spawn
master and of the enemy count, and it is what stands between the p50
(5.8 ms) and the p99 (30 ms). The M6 profile that flipped pathfinding
on measured 4 ms per rebuild on the worlds of that day; the islands have
since grown. Two candidates, neither in this plan: stagger the jump
rebuild across two frames the way the periodic one already is
(`test_enemy_nav` pins "a jump rebuilds every grid at once", so it is a
decision), or fill incrementally across frames.

### Suite

987 tests, 986 passed and 1 skipped on the first full run (6 min 42 s).

### Addendum: after the commit (2026-09-03)

Two more measurements, on the way to `documentation/plans/fluidity_plan.md`:

- `GameMap.is_walkable` ends with a linear scan of every obstacle in the
  world (565 on seed 35), and `resolve_movement` calls it up to three
  times a move with five probes each. Monkeypatching the scan to a
  `SpatialGrid` query: 93 us -> 4 us a call, update p50 6.0 -> 1.2 ms at
  100 live. The single biggest lever left, and outside the spawn master;
  proposed there, not done here.
- Draw + flip under the same crowd (15 bodies in view, dummy video
  driver): p50 7.7 ms, p90 8.7 ms, one 62 ms frame as the terrain blit
  cache filled.

---

## Dev-menu spawns and the live cap (2026-09-03)

**Reported:** "Spawn enemy..." in the dev menu stops producing enemies
after a certain amount.

**Cause.** The menu spawned with the default owner `direct`, which the
master holds to the director's cap: 40 bodies at the start of a run,
+5 every 20 s of game time, clamped to `ENEMY_LIVE_CAP` (100). Sixty
menu spawns at t = 0 seated forty; `spawn_at` then answered `None`. The
menu's status line still said "spawned 60 x chaser" because it counted
attempts, not results. The limit moving with the clock is what made it
read as random. The rule predates the master (the old `spawn_enemy`
refused past the same cap); the master only made the refusal explicit
and gave scripted owners a way round it.

**Fix.** Dev spawns are scripted: they carry `owner="dev"`, and `dev`
joins `arena` in `owners.cap_exempt` (`data/spawn_tables.json`), so the
master seats them whatever the live count -- the world cap still holds.
The dev menu and the F2 key pass the owner; the menu counts only what
the master returned and says so when it refuses. `PlayingState._spawn_enemy`
returns the enemy and takes an owner, so the tests can too.
Tests: `test_menu_spawns_are_not_bound_by_the_live_cap` (dev mode) and
the exempt-owner check in `test_master`.

---

## The obstacle index in the collider (2026-09-03)

Item 1 of `documentation/plans/fluidity_plan.md`, done.

`GameMap.is_walkable` and `blocking_obstacle_hit` ended with a scan of
every obstacle in the world. `world/map.py` now carries
`_ObstacleIndex`: the obstacles bucketed by a 128 px world grid, with the
widest radius kept so a probe asks for `radius + reach` and gets a
superset the exact disc test then filters. `GameMap.obstacles` became a
property whose setter rebuilds the index, because the tests assign the
list after construction (`test_obstacles`); obstacles never move once
placed, so nothing else can stale it.

| `python -m tools.benchmarks.spawn_stress`, 100 live | p50 | p90 | p99 |
|---|---|---|---|
| before, LOD 2 | 5.78 | 27.02 | 29.82 ms |
| after, LOD 2 | **1.13** | 24.34 | 30.33 ms |
| after, LOD 1 (off) | 1.19 | 22.78 | 25.45 ms |

The p90 and p99 are the flow-field rebuild and do not move; item 3 of
the plan is what moves them. With the scan gone the tick LOD is worth
0.06 ms a frame; its default is left at 2 for now, but it could go back
to 1 (exact simulation for every body) at no measurable cost, which is
a call for the owner.

Tests: `tests/world/test_obstacle_index.py` (4) -- index against scan on
4,000 random probes per cached seed at every body radius, walkability and
projectile blocking unchanged, assignment rebuilds, bucket edges.

Suite: 990 of 991 on the first full run; the one failure,
`test_no_damage_keeps_the_hero_attacking_but_deals_zero`, did not
reproduce -- the dev-mode file twice in order, the suspect pair, all of
`tests/core`, the earlier directories replayed in front of it, and forty
seeds of the scenario all pass. The dev run's seed is the global RNG, so
it is a rare-seed flake in that test (the hero's shots not reaching a
tank placed 30 px away for three seconds), unrelated to the index. Left
open; if it recurs, pin the test's seed or place the tank on a verified
floor spot.

---

## Render fixes and the sliced flow-field fill (2026-09-03)

Items 3 and 7 of `documentation/plans/fluidity_plan.md`, done.

**Render.** `PlayingState._actor_items` lists only the bodies inside the
view padded by `config.RENDER_ACTOR_CULL_PAD` (enemies, death poofs,
summons; the boss at twice the pad). `TerrainRenderer.shade_character_frame`
asks a 256 px bucket index of the baked tree shadows (`_shadow_index`,
rebuilt only when the baked dict is replaced) for the shadows touching
the frame's footprint, instead of walking all 336 in the world, and
draws through two reused scratch surfaces per frame size instead of
allocating an overlay and a copy per character. `hit_tinted` caches the
tinted copy by the frame object's identity for the hurt window.

**Fill.** `FlowField.begin` starts a fill into a back buffer and
`FlowField.step(budget_s)` advances it, reading the clock every 128
relaxations; `_finish` swaps the buffers, so `cost` -- what the samplers
read -- is always a completed field. `rebuild` is `begin` + `step(None)`
and lands byte-identical results (pinned). `NavField.begin` / `step` /
`filling` do the same per class, sharing one budget in class order, and
record the target cell at `begin` so the drift trigger does not restart
the fill every frame. `NavCoordinator` starts fills where it used to
rebuild and advances them `config.ENEMY_NAV_FILL_BUDGET` (3 ms) a frame.

### Measured

`python -m tools.benchmarks.spawn_stress`, 100 live, update only:

| | p50 | p90 | p99 | max |
|---|---|---|---|---|
| after the obstacle index | 1.13 | 24.34 | 30.33 | 40.78 ms |
| after the sliced fill | 3.94 | 4.35 | 4.87 | 7.93 ms |

The p50 rose because the fill's slices now sit in ordinary frames; the
spike is gone.

The walking-hero probe (update + render, 100 live, 1,200 frames):

| | total p50 | p90 | p99 | max | over 16.7 ms |
|---|---|---|---|---|---|
| before | 16.94 | 23.05 | 58.02 | 63.94 ms | 616 (51 %) |
| after | 5.49 | 8.45 | 9.79 | 20.84 ms | 1 (a 5 ms GC) |

Render p50 14.7 -> 3.6 ms; update p99 41.9 -> 5.1 ms.

### Decided on the way

- **The stagger tests changed meaning, not intent.** They spied on
  `NavField.rebuild`; the coordinator no longer calls it. They spy on
  `begin` now and let a fill land between ticks. "A jump rebuilds every
  grid at once" became "a jump starts every grid's fill at once".
- **A fill abandons its predecessor.** A jump while a periodic fill is
  under way restarts every class; the partial work is dropped rather
  than merged, since the target moved.
- **The budget is per frame, not per class**: two fills in flight share
  the 3 ms in class order, so the small class (the common enemies) lands
  first.

### Suite

1,003 tests, 1,002 passed and 1 skipped on the first full run (5 min 59 s).
The full rerun for the index commit, done before this, came back 991 green,
so the dev-mode flake did not recur.

---

## The vsync flag and the blit-cache warm-up (2026-09-03)

Items 3 and 5 of the frame-consistency list (`fluidity_plan.md` section 8).

**`config.VSYNC`** (default on; the web profile turns it off, pygbag owns
the canvas). `Game._open_window` asks for
`set_mode(size, SCALED | DOUBLEBUF, vsync=1)` and falls back to the plain
window on `pygame.error`, logging why; `Game.vsync` reports which it got.
Under the suite's dummy driver pygame accepts the request with a software
renderer ("no fast renderer available"), so the tests pin the fallback
path by mocking a refusing driver, and the report -- the sync itself can
only be judged on a real display with the F1 overlay.

**The warm-up.** `LoadingState._warm_steps` draws the start view and the
eight views around it (one view span each way) into a scratch surface at
the run's zoom, the centre at three foam phases, one position per loading
step ("warming the view N of 9"). `TerrainRenderer._z_surf` fills
`GameMap._blit_cache` as it draws, and the map is handed to the run with
that cache, so the run's first frames find every scaled surface ready.

### Measured

Seed 35, dev run, dummy driver: the warm-up adds 0.06 s to a 2.4 s
load (nine steps, the slowest 18 ms), and hands the run a cache of 74
scaled surfaces. The run's first five renders: 12.3, 3.4, 3.3, 3.2,
3.3 ms -- against a 62 ms first frame before. The remaining 12 ms on the
very first frame is the HUD's and overlays' own first-use work (font
renders, the vignette surface), not the terrain.

Tests: `tests/core/test_window.py` (5), and
`test_the_view_is_warmed_before_the_run_starts` in `test_loading.py`,
which pins that the run's first draw adds at most three cache entries.

### Suite

1,009 tests, 1,008 passed and 1 skipped on the first full run (6 min 17 s).
The eight warnings are pygame's "no fast renderer available" from the
vsync request under the dummy driver -- the accepted-with-software path,
not a failure.

---

## S9 — Base spawn pressure x5 (2026-09-03)

**Asked:** raise the spawn master's default pressure to five times.

**Done.** `pacing.base` in `data/spawn_tables.json` (5.0), read by
`Pacing.base` (required, no code default), and
`SpawnMaster.pressure = base x pacing value x modifiers`. The director's
interval is divided by the product, so the standing cadence is five
times the tables' schedule before the condition signal (0.6-1.5) and the
dev modifiers (x0.5-x4) move it. The overlay line reads
`pressure 5.56 = base 5 x pace 1.11 x mods -`. Nothing else moved: the
live and world caps, the phase mix, the stat ramp and the pinned director
sequence (which drives the director directly) are as they were.

### Measured

Seed 35, dev run, hero invulnerable and not attacking, 60 s of game time:

| base | spawned by 10 / 20 / 30 / 40 / 50 / 60 s | live cap first full |
|---|---|---|
| 1 | 9 / 18 / 26 / 35 / 43 / 51 | 57.7 s |
| 5 | 21 / 34 / 45 / 45 / 50 / 50 | 29.7 s |

The cadence is five times, but the **cap** is what the player meets: at
the start of a run the director may hold 40 bodies, growing by 5 every
20 s, so at base 5 the crowd is full inside half a minute and the extra
cadence only shows as how fast the gaps left by kills refill. With a
hero who kills, that is the whole point; with one who does not, the two
runs converge on the cap. Raising the crowd itself is
`config.ENEMY_COUNT_BASE` / `ENEMY_COUNT_STEP` (the director's schedule)
and `ENEMY_LIVE_CAP` (the simulation budget), not this knob.

Tests: the pressure tests learned the base; a new one pins that base 5
spawns 3.5-6.5 times what base 1 does over the same window with the cap
out of the way; `test_tables` refuses a base of 0 or a string.

### Suite

1,011 tests, 1,010 passed and 1 skipped (6 min 57 s), after two test
repairs the sprite commit had left behind (`journals/journal.md`).

---

## Base spawn pressure x3 again: 5 -> 15 (2026-09-03)

**Asked:** three times the current default pressure.

**Done**, one number: `pacing.base` 5.0 -> 15.0. The cadence is now
fifteen times the tables' schedule before the condition signal and the
modifiers.

**What it actually changes: almost nothing in a run.** Seed 35, dev, hero
invulnerable and not attacking, 60 s:

| base | spawned by 10 / 20 / 30 / 40 / 50 / 60 s | live cap first full |
|---|---|---|
| 5 | 21 / 34 / 45 / 45 / 50 / 50 | 29.0 s |
| 15 | 23 / 35 / 42 / 45 / 50 / 50 | 33.2 s |

The **live cap** is the binding constraint, not the cadence: 40 bodies at
the start of a run, +5 every 20 s, and it fills within half a minute at
either value. Past that the master spawns only into the gaps kills leave,
so the extra cadence is spent on refill speed alone. (Base 15 filling
marginally *later* is the pacing signal's crowd term pushing back, not a
regression.)

Uncapped, the director does scale: 4.2 enemies/s at base 5, 12.6 at 15,
37.8 at 45 -- but it emits at most **one pack per `update`**, so at 60 Hz
the hard ceiling is one pack a frame, and past roughly base 10 a further
multiplier buys progressively less. Two tests had to learn this: the
modifier test now measures from base 1 (a x2 on top of 15 saturates and
would not show), and the base test pins the 5x ratio at base 5 rather
than at whatever ships.

**To actually see more enemies**, raise the crowd, not the cadence:
`config.ENEMY_COUNT_BASE` (40) and `ENEMY_COUNT_STEP` (5 per 20 s) are
the director's schedule, `ENEMY_LIVE_CAP` (100) is the simulation budget
the S7 profile sized. Say the word and I will measure a raise there.

### Suite

1,022 tests, 1,021 passed and 1 skipped (7 min 7 s).

---

## More enemies on screen: count base 40 -> 100, live cap 100 -> 150 (2026-09-03)

**Asked:** raise the live cap and the count base so more enemies are on
screen -- they spawn constantly and die fast, and the crowd should hold a
roughly constant flow.

**Done.** `config.ENEMY_COUNT_BASE` 40 -> 100 and `ENEMY_LIVE_CAP`
100 -> 150. The director's schedule still grows +5 every 20 s and is
still clamped to the live cap, so a run now starts at 100, reaches 150
about four minutes in, and holds there.

### Measured

A real two-minute dev run (seed 35, hero invulnerable), live bodies at
20 s steps:

| | 20 s | 40 s | 60 s | 80 s | 100 s | 120 s |
|---|---|---|---|---|---|---|
| hero fighting | 33 | 56 | 77 | 94 | 111 | 123 |
| no kills | 35 | 57 | 78 | 103 | 120 | 125 |

Frame time over those 7,200 frames (update + render, dummy driver):
p50 7.4, p90 10.6, p99 11.6 ms fighting, with **4 frames over the 60 fps
budget**. The two curves being so close is the point: the crowd tracks
its ceiling whether or not the player is killing, which is the constant
flow that was asked for.

The **fill rate is placement-bound, not schedule-bound** -- about one
body a second. The zone offers ten points per terrace of the islands in
play, each on a 3 s cooldown, and a spawn must be off screen and 220 px
from the hero; that is what paces the first two minutes, not the count
schedule. Raising the base past 100 would not fill faster.

Where the frame actually runs out, from the harness (which packs every
body into the zone around the hero, so it is the pessimistic case):

| live | total p50 | p90 | p99 | over 16.7 ms |
|---|---|---|---|---|
| 99 | 9.99 | 11.85 | 14.51 | 3 / 600 |
| 146 | 13.35 | 15.39 | 17.75 | 13 / 600 |
| 197 | 15.22 | 17.80 | 23.06 | 126 / 600 |
| 297 | 16.47 | 18.41 | 30.03 | 250 / 600 |

150 is the last value that holds; 200 spends a fifth of its frames over
budget. `ENEMY_COUNT_HARD_CAP` (600, live + dormant) is untouched.

### Fixed on the way

- **The harness was measuring a third of the crowd it was asked for.**
  `stress.build` seated bodies through `m.spawn_at` with no position,
  which is placement's job -- and placement's point cooldown refused most
  of a tight loop, so `--live 300` produced 85. It seats them on the
  zone's own spawn points with a spread now. Placement has its own tests;
  the harness is a population builder.
- **The S2 sequence fixture is now immune to tuning.** The cap enters the
  pack roll (`min(pack, cap - active)`), so raising the count base
  rewrote the pinned sequence and with it the proof that the S2 table
  move was behaviour-preserving. `_scripted_run` pins the two count knobs
  to the values they had when the fixture was recorded.

### Suite

1,022 tests, 1,021 passed and 1 skipped (8 min 2 s).

---

## S10 — camping starved the placement filter (owner, 2026-09-12)

### Requirement

> "check the spawn master behaviour and confirm if the camera of the player
> doesn't move too much, or the player stays too much on a single island,
> the density of spawns gets greatly reduced, in this case the spawns should
> continue even if the camera is showing"

### Confirmed, and the cause was not the obvious one

Measured headless on the shipped world, hero parked, enemies culled every
frame so the live cap could never be the reason a spawn did not happen — what
is left is placement and nothing else:

| | spawns/min | deferred | strict pool empty |
|---|---|---|---|
| camping | 375 | 996 | 90 % of frames |
| patrolling | 567 | 1498 | 92 % of frames |

So the density drop is real: **camping cost about a third of the spawn rate**.
Dissecting one frame of the filter showed why, and it is worth recording
because the intuition ("the camera is in the way") is only a fifth of it:

```
zone: 1 island, 30 spawn points   (149 in the world)
  cooldown (3 s)            24  (80 %)
  inside view + 96 px pad    6  (20 %)
  PASSED                     0
```

A player on one island has a zone of one island. Thirty points, each locked
for 3 s after use, is a hard ceiling of ten seatings a second before any other
rule applies — and the view removes the fifth of them nearest the hero, which
with the hero parked is the *same* fifth every frame. The pool was empty on 9
frames in 10, every pack became debt, the debt queue sat pinned at its cap of
20, and packs past that were dropped without even being counted.

### The relaxation ladder

`Placement.choose` no longer asks one question and gives up. It walks three
rungs and takes the first that offers anything:

| rung | view | keep-away | point cooldown |
|---|---|---|---|
| `OFFSCREEN` | outside view + `view_pad` | `min_distance` (220) | `cooldown` (3 s) |
| `NEAR` | outside the bare view | none | `cooldown` |
| `STARVED` | **not a wall** | `starved_min_distance` (420) | `starved_cooldown` (0.5 s) |

The bottom rung is the owner's call: spawns continue even when the camera can
see them. It addresses both rejection reasons at once — the view stops
excluding points, and the cooldown shortens six-fold, which is the larger half
of the problem. `relax_after` keeps its old meaning: an aged debt request
starts at `NEAR` instead of paying the keep-away twice.

Two things are deliberately **not** relaxed at any rung, because they are
physical rather than aesthetic: a body already standing on a point, and a
large enemy needing a large point. `None` from `choose` now means genuinely
nothing in the zone is usable, and that request still becomes debt.

### What stops an enemy appearing in the hero's lap

On the bottom rung the view is gone, so distance is the only thing left. Two
rules carry it: `starved_min_distance` (420) is a hard floor, and candidates
there are weighted by distance, so the draw leans to the far edge of the
screen. Measured over a camping run:

* 27 % of spawns appear inside the camera view; the rest are still off-screen.
* The closest arrival over the whole run was **478 px** from the hero, median
  623 px. The view's half-diagonal is 612 px, so an on-screen arrival lands in
  the corners and margins, not next to the player.

### Result

| | before | after |
|---|---|---|
| camping, spawns/min | 375 | **1000** |
| patrolling, spawns/min | 567 | **1022** |
| camping, deferred | 996 | 393 |
| patrolling, deferred | 1498 | **1** |

The camping penalty goes from 34 % down to 2 %: standing still no longer buys
the player quiet.

**What this does not change.** The live enemy cap is untouched, so the crowd
ceiling is exactly what it was — this changes how fast the crowd *refills*
after the player clears it, not how large it can get. In a run where the cap
is already saturated (the hero swarmed and not killing) the cap is the limiter
and the ladder changes nothing, which is correct: that ceiling is the
performance budget, not a pacing knob.

### Files

* `data/spawn_tables.json` — `placement.starved_min_distance`,
  `placement.starved_cooldown`, and the note explaining the rung.
* `spawn/placement.py` — the `OFFSCREEN` / `NEAR` / `STARVED` rungs,
  `first_tier`, a tier-aware `on_cooldown` and `candidates`, and a `choose`
  that walks the ladder.
* `tests/spawn/test_placement.py`, `tests/spawn/test_master.py` — three tests
  pinned "a spawn is never on screen" and "an on-screen view refuses the
  spawn", which is the rule that was deliberately changed. They now pin the
  new contract: on-screen is allowed, the keep-away never is, and a quiet zone
  keeps spawning.

### Loose end noticed, not changed

`_MAX_DEBT = 20` in `spawn/master.py` is a module constant, and a pack that
arrives when the queue is full is dropped silently without incrementing
`deferred` — so the old logs understated the loss. The ladder makes the queue
nearly always empty, so it no longer bites, but it is tuning living in code
rather than in `spawn_tables.json`.

## S11 — placement by distance from the player, regardless of the camera (owner, 2026-09-15)

### Requirement

> Change the way the spawn master spawns enemies to do it on a range outside
> of the player so it doesn't spawn on top of them, but regardless of the
> camera. Confirm.

Raised while considering the ultrawide render extent
(`window_scaling_journal.md`): a wider view would have pushed every spawn
further out horizontally, because the ladder's first two rungs are walls
built from the camera's visible rect.

Status: **built** the same day (owner: "start only with the spawn master changes").

### Confirmed reading

Today (`spawn/placement.py`, S10) the ladder is:

| Rung | Rule today | Camera-dependent? |
|---|---|---|
| OFFSCREEN | outside the view inflated by `view_pad` (96) **and** beyond `min_distance` (220) from the hero | yes |
| NEAR | outside the bare view; the keep-away is dropped | yes |
| STARVED | the view is not a wall; keep-away `starved_min_distance` (420), draw weighted by distance | no |

The change: the view stops being an input to placement at every rung. Each
rung becomes a distance band around the hero, so the same request lands the
same way at 16:9, 21:9, or with the camera anywhere. Whether a point is on
screen is no longer a rule; it becomes a consequence of the band, and on a
wider view some arrivals will be visible at the edges, which the owner
accepted with the ultrawide extent.

### Proposal

- **Bands replace the view.** In `data/enemies/spawn_tables.json`
  `placement`: `spawn_min_distance` and `spawn_max_distance` for the strict
  rung; `near_min_distance` for the middle rung (no maximum); the existing
  `starved_min_distance` / `starved_cooldown` for the last. `view_pad` and
  `min_distance` are retired. Suggested starting values, for the owner to
  tune: strict 700–1100 world px (just past the 16:9 half-diagonal of 612
  plus the old pad, so a 16:9 player still sees nothing appear), near ≥ 480,
  starved ≥ 420 as now. Every number stays in the data, none in code.
- **The ladder keeps its shape**: strict → near → starved, `first_tier` by
  debt age unchanged, the physical rules (zone, cooldown, clearance, an
  occupied point) unchanged, the distance weighting on the starved rung
  unchanged. Only the wall changes.
- **`host.visible_rect()` leaves the placement path.** It stays on the
  `SpawnHost` protocol for the watchdog, whose on-screen wait before a poof
  is a visual concern and still needs the camera. `GameMap.offscreen_spawn_point`
  (the no-layout fallback) takes the same band instead of the view.
- **The boss ring is already player-relative** (`BOSS_SPAWN_DISTANCE` = 680
  from the hero) and needs no change; its comment tying the number to the
  16:9 view edge is updated to say the boss may be visible at 21:9.
- **The dev overlay** that colours candidate points by rung keeps working;
  the rung names lose the word "offscreen" (`FAR` / `NEAR` / `STARVED`).
- **Tests** (`tests/spawn/test_placement.py`, `test_master.py`, eight
  references to the view or the rung names): the tests that pin "outside the
  view" are replaced by ones that measure the band — a point inside
  `spawn_min_distance` is never chosen at the strict rung, one beyond
  `spawn_max_distance` is not chosen while nearer ones exist, and moving the
  camera without moving the hero changes nothing.

### Built

- `data/enemies/spawn_tables.json` `placement`: `view_pad` and `min_distance`
  retired; `far_min_distance` 700, `far_max_distance` 1100,
  `near_min_distance` 480 added, with a `_band_comment` saying why. The
  starved knobs are unchanged.
- `spawn/placement.py`: rungs renamed `FAR` / `NEAR` / `STARVED`; each is a
  squared distance band (only the strict rung has a ceiling); the
  `host.visible_rect()` call is gone from the pick. Cooldowns, the physical
  rules, the starved weighting and `choose` are untouched.
- `world/map.py`: `offscreen_spawn_point(camera, rng)` became
  `spawn_point_near(player_pos, rng, min_distance, max_distance)`;
  `world/spawning.py`: `ring_point_outside_view` became `ring_point_around`
  and is now the no-layout branch of that fallback. The run-side host
  (`game/states/playing/core/spawning.py`) passes the hero and the strict
  band from the tables.
- `spawn/host.py`: `visible_rect` stays on the protocol for the watchdog
  only. `spawn/master.py`, `spawn/tables.py`, `world/gen/spawnpoints.py`
  and the boss-ring comment in `game/config.py` no longer describe an
  off-screen rule.

### The ceiling, measured

Before keeping 1100 the band was measured on the four cached test worlds
(`tests/worlds.py`), standing at each island's centre and at each bridge:

| Where the hero stands | Points in 700..1100 |
|---|---|
| An island's centre, its own points | 4 to 15 (islands with points) |
| An island's centre, the neighbour's points | 0 to 1 -- the nearest neighbour point is 930..2500 px away |
| A bridge, both islands' points | 2 to 15 (one bridge in seed 42 has 0) |

So from mid-island the strict rung draws from the hero's own island, and
the neighbour joins as the hero nears the bridge -- "spawn near the player"
by construction. Where the band is empty (the small hub islands carry no
points; one bridge) the NEAR rung, which has no ceiling, takes over.

### Tests

`tests/spawn/test_placement.py`: the "outside the padded view" test became
"the strict rung is a band around the player"; new tests pin that the
camera never moves a spawn (the view moved away, then covering the world:
identical candidates at every rung) and that the ceiling drops at the near
rung. The starved and aged-debt tests lost their view set-up and describe
distances instead. Two filter tests and the upper-preference test in
`test_master.py` stand the fake hero at the bridge, because the fake
islands sit 1300 px apart. `test_no_spawn_lands_on_top_of_the_player` now
looks elsewhere with the camera and asserts the starved keep-away (minus a
follower's ring reach) for every live body. `test_population.py` asserts
the keep-away for residents instead of the padded view.
`tests/spawn/test_spawning.py` tests `ring_point_around` (in band, clamped,
deterministic).

Suite: `tests/spawn` 132 tests OK; full default tiers 2197 passed, 8 sweep
tests deselected (11m44s).

### Progress

- [x] Data knobs and the note in `spawn_tables.json`
- [x] `spawn/placement.py` rungs by distance band
- [x] `world/map.py` fallback
- [x] Boss ring comment
- [x] Tests replaced

---

## S12 — a 45 s ramp, a 250 crowd, elites from the first minute (owner, 2026-09-16)

### Requirement

Raised after a review of the spawn rate over a 10 minute run
(the curve of scheduled demand against the live cap, per difficulty):

> "increase the pacing. lower the 300s requirement to ramp up to 45 seconds
> base for normal. increase the enemy live cap to 250. increase the elite
> chance by a base of 15%, all around, so it starts from 25%. keep everything
> else. confirm"

### What the review found first, because it frames all four items

The director's *scheduled demand* and the *delivered* spawn rate are two
different numbers, about 5x apart:

| | normal | fast | super fast |
|---|---|---|---|
| demand at 0 s | 12.5 /s | 15.6 /s | 18.8 /s |
| demand at 300 s | 50.7 /s | 65.1 /s | 121.6 /s |
| demand before the boss | 85.0 /s | 106.4 /s | 127.2 /s |
| placement ceiling (S10, measured) | ~17 /s | ~17 /s | ~17 /s |

`pacing.base` is 15, so a table interval of "one pack every 1.2 s" is really
one pack every 80 ms. Placement can seat about 17 a second and the live cap
holds the field at 100..150, so **the director has been saturated from the
first second of every run** and the schedule's 7x rise across a run never
reached the player.

That is why the request lands where it does: the knobs that still bite are
the ones this entry moves.

### Confirmed reading

Three of the four items were unambiguous; two were put to the owner and
answered:

- **"increase the pacing"** — the headline for the ramp change below, *not*
  a change to `pacing.base`. Confirmed: `pacing.base` stays 15. Raising it
  would not show on the field while placement is the ceiling.
- **"lower the 300s requirement to ramp up to 45 seconds"** — the **phase
  schedule** is what ramps in 45 s (chosen over the cap ramp and the stat
  ramp). There is no 300 s constant in the code; the 300 s is the review's
  observation that the heavy phase lands at 270 s on normal.
- **"45 seconds base for normal"** — 45 s is the Normal figure, divided by
  `timeline_pace` like `run_duration` is, so fast ramps in 36 s and super
  fast in 30 s.
- **The boss does not move.** The phase schedule is keyed to `run_duration`
  today, and `boss_time()` is `BOSS_FRACTION * run_duration` off the same
  number. Compressing the run to 45 s would arm the boss at 43 s, which is
  plainly not the ask. The two clocks are therefore **decoupled**: a new
  `ramp_seconds` drives the phase schedule and the interval lerp;
  `run_duration` keeps the boss at 570 / 456 / 380 s.
- **elite "+15%, so it starts from 25%"** — did not resolve as stated
  (+15 points on the opening 0% is 15%, not 25%). Owner chose: **floor the
  opening at 25% and add 15 points to the rest**, giving
  0 / 2 / 5 / 10 / 14 -> **25 / 25 / 25 / 25 / 29**.
- **`ENEMY_LIVE_CAP` 150 -> 250.** Taken as stated.

### Concern recorded, and proceeding anyway

250 live is past the wall the S7/S8 profile measured on this machine. From
the 2026-09-03 harness run (the pessimistic case, every body packed into the
zone around the hero):

| live | p50 | p90 | p99 | frames over 16.7 ms |
|---|---|---|---|---|
| 146 | 13.35 | 15.39 | 17.75 | 13 / 600 |
| 197 | 15.22 | 17.80 | 23.06 | 126 / 600 |
| 297 | 16.47 | 18.41 | 30.03 | 250 / 600 |

150 was chosen as "the last value that holds". 250 sits between the 197 and
297 rows, so a crowded frame is expected to miss 60 fps. The owner asked for
250; it is built, and the actual cost is re-measured below rather than
argued about.

### Also worth knowing, not changed ("keep everything else")

Raising `ENEMY_LIVE_CAP` alone does not put 250 bodies on the field. The
director's own ceiling still climbs `ENEMY_COUNT_BASE` (100) by
`ENEMY_COUNT_STEP` (5) every `ENEMY_COUNT_STEP_PERIOD` (20 s), so reaching
250 takes 600 s on normal — the boss arrives at 570 s with the cap at 245.
Fast reaches 250 at 380 s, super fast at 300 s. If the crowd is meant to
ramp on the 45 s clock too, `ENEMY_COUNT_STEP` / `STEP_PERIOD` are the knobs;
left alone here by the owner's "keep everything else".

### Proposal

- `data/enemies/spawn_tables.json`
  - new top-level `ramp_seconds: 45.0`, beside `phases`, with a comment
    saying it is the Normal figure and that the boss is on the other clock.
    It lives in the data, not in `config.py`, because the schedule it scales
    lives here (the project's "no tuning defaults in code" rule).
  - `phases[*].elite` -> 0.25 / 0.25 / 0.25 / 0.25 / 0.29.
- `spawn/tables.py` — read and validate `ramp_seconds` (a number > 0),
  expose it as `SpawnTables.ramp_seconds`, and document it in the section
  list.
- `spawn/budget.py` — `SpawnDirector.ramp_duration = ramp_seconds /
  timeline_pace`, set in `set_difficulty` next to `run_duration`.
  `_phase()` and `_interval()` take their fraction from `ramp_duration`;
  `boss_time()` and `stat_multipliers()` are untouched.
- `game/config.py` — `ENEMY_LIVE_CAP` 150 -> 250, with the frame-budget
  note above kept honest in the comment.
- Tests — the S2 sequence fixture is made immune to this tuning the same way
  it was made immune to the count knobs; the two tests that sample the phase
  schedule at a wall-clock instant are re-pointed at the 45 s ramp; new
  tests pin that the ramp completes at `ramp_seconds` and that the boss does
  **not** move with it.

### Built

- `data/enemies/spawn_tables.json` — `ramp_seconds: 45.0` and a
  `_ramp_comment` saying it is the Normal figure and that the boss keeps its
  own clock; `phases[*].elite` 0 / 2 / 5 / 10 / 14 -> **25 / 25 / 25 / 25 /
  29**, with an `_elite_comment` recording the owner's reading.
- `spawn/tables.py` — `SpawnTables.ramp_seconds`, validated as a number > 0.
  It carries a 600 s fallback so a table literal handed in by a test stays
  constructible; the shipped tables always name it.
- `spawn/budget.py` — `ramp_duration = ramp_seconds / timeline_pace`, set
  beside `run_duration`. A new `_ramp(elapsed)` returns the 0..1 fraction
  that `_phase` and the `_interval` lerp both take. `boss_time()`,
  `stat_multipliers()` and `enemy_count_cap()` are untouched.
- `game/config.py` — `ENEMY_LIVE_CAP` 150 -> **250**, with the frame-budget
  table above copied into the comment so the next reader knows the number
  was chosen over a measured objection, not in ignorance of one.

### Measured after

Phase bands, on the wall clock, and the elite chance that goes with them:

| | ramp | bands at | elite from | boss |
|---|---|---|---|---|
| normal | 45 s | 9 / 20 / 32 / 43 s | 25 % at 0 s, 29 % at 45 s | 570 s |
| fast | 36 s | 7 / 16 / 25 / 34 s | 25 % at 0 s, 29 % at 36 s | 456 s |
| super fast | 30 s | 6 / 14 / 21 / 29 s | 25 % at 0 s, 29 % at 30 s | 380 s |

Scheduled demand (enemies/s, neutral pacing) — it now tops out on the ramp
instead of at the boss:

| | 0 s | 10 s | 30 s | 45 s | 60 s+ |
|---|---|---|---|---|---|
| normal | 12.5 | 23.4 | 52.6 | 84.0 | 119.3 |
| fast | 15.6 | 29.6 | 103.5 | 149.1 | 149.1 |
| super fast | 18.8 | 35.9 | 179.0 | 179.0 | 179.0 |

(The Normal row still climbs between 45 s and 60 s because the *last* band's
interval is the shortest and the lerp reaches it right at the ramp's end.)

Demand was already 5x past what placement can seat before this change, so
these numbers do not mean five times the enemies. What the player actually
gets is the **composition** arriving three quarters of a minute in instead of
five minutes in, elites from the first spawn, and a ceiling that keeps
climbing past 150.

The cap reaches 250 at 600 s (normal) / 380 s (fast) / 300 s (super fast) —
so on Normal the boss arrives with the cap at 245 and the full 250 is never
seen. Flagged above; the count schedule was left alone as asked.

### Tests

`tests/spawn/test_budget.py`:

- The S2 sequence fixture is made immune to this tuning the same way it was
  made immune to the count knobs in 2026-09-03. `_fixture_tables(duration)`
  deep-copies the shipped tables and winds back only `ramp_seconds`
  (to the run length, which is what the schedule used to run on) and the
  five elite chances. The elite chance decides an already-drawn `random()`,
  so restoring it changes which id is appended and never the draw order.
  Everything the proof is about — phase boundaries, weights, intervals, pack
  spans, the cap in the pack roll, the boss — still comes from the JSON.
- `test_only_chasers_in_the_opening_phase` **was wrong after the change and
  is rewritten, not re-pinned**: the opening band carries a 25 % elite slot
  now, so "only chasers" is no longer true of it. It asserts the band's
  composition instead — chaser plus the two elite ids, and nothing else.
- The two tests that sampled the schedule at a wall-clock instant (180 s,
  150 s) now sample a fraction of `ramp_duration`.
- Two new tests: the schedule reaches its last band at `ramp_duration` and
  holds it (interval lerp included), and the ramp compresses with
  `timeline_pace` while `boss_time()` does not follow it — the regression
  the split exists to prevent.

### Progress

- [x] `ramp_seconds` and the elite chances in `spawn_tables.json`
- [x] `spawn/tables.py` reads and validates it
- [x] `spawn/budget.py` ramps the schedule on it, boss on `run_duration`
- [x] `ENEMY_LIVE_CAP` 250
- [x] Tests updated (`tests/spawn` 134 passed)
- [x] Re-measured curve delivered
- [ ] Frame cost at 250 live re-measured with `tools/benchmarks/spawn_stress.py`
      -- not run here; the 150 -> 250 raise is expected to cost frames

### Suite

2,389 passed, 8 sweep tests deselected, 487 subtests passed (12 min 53 s).
`tests/spawn` alone: 134 passed.
