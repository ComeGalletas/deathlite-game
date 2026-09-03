# Spawn master — journal

Evidence for the phases of `documentation/spawn_master_todo.md`, against the
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
  `python -m world.digest --write`). The bake and frame digests are
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

`python -m spawn.stress` (`spawn/stress.py`): a real dev run at 300 s,
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

Two more measurements, on the way to `documentation/fluidity_plan.md`:

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

Item 1 of `documentation/fluidity_plan.md`, done.

`GameMap.is_walkable` and `blocking_obstacle_hit` ended with a scan of
every obstacle in the world. `world/map.py` now carries
`_ObstacleIndex`: the obstacles bucketed by a 128 px world grid, with the
widest radius kept so a probe asks for `radius + reach` and gets a
superset the exact disc test then filters. `GameMap.obstacles` became a
property whose setter rebuilds the index, because the tests assign the
list after construction (`test_obstacles`); obstacles never move once
placed, so nothing else can stale it.

| `python -m spawn.stress`, 100 live | p50 | p90 | p99 |
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

Items 3 and 7 of `documentation/fluidity_plan.md`, done.

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

`python -m spawn.stress`, 100 live, update only:

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
