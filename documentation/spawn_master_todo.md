# Spawn Master — todo

Companion to `documentation/spawn_master_design.md`. Phases S1-S8 in the
order they ship; every phase leaves the suite green and the game playable.
Tick items as they land and log evidence (numbers, seeds, what was left
out) in `journals/spawn_master_journal.md`.

Conventions that apply to every item below:

- Tuning values live in data (`data/spawn_tables.json`) or in `config.py`
  snapshotted through `GenSettings`; no per-entity defaults in code.
- New code goes in one-module-per-concern files under `spawn/`; nothing
  under `spawn/` imports `entities` or `game.states`.
- Tests use the shared cached worlds; no per-test world generation.

---

## S1 — Spawn points at generation — done 2026-09-03 (see `journals/spawn_master_journal.md`)

- [x] `config.SPAWN_POINTS_PER_FLOOR = 10`, documented next to the other
      `HEIGHTMAP_*` knobs; `GenSettings.spawn_points_per_floor` mapped in
      `world/gen/settings.py`.
- [x] `SpawnPoint` and `ResourcePoint` records (`room_id, floor, x, y,
      clearance, tags` / `kind`) in `world/layout.py`, the data model
      `generate_world` produces; `spawn/points.py` holds the read side, a
      `PointIndex` grouping them by island and by `(island, floor)` once.
- [x] `WorldLayout.spawn_points` and `WorldLayout.resource_points` fields
      (default empty).
- [x] `world/gen/spawnpoints.py`: candidate walk per room and floor with
      the six filters (ground cell, inset at large clearance, no obstacle,
      outside door / flight keep-outs, away from the interactable centre,
      passable on the large nav class). Reuse `scatter._blocks`,
      `_corridor_doorways`, `_flight_keepouts`, `inset.world_clear` and
      `NavGrid.passable`; do not re-derive any of them.
- [x] Farthest-point selection per floor up to `spawn_points_per_floor`;
      relax the inset margin once for a floor under 3; log the shortfall.
- [x] Tags: `edge`, `bridge`, `upper`, `boss` (no `arena`: elite arenas
      are retired). Boss room emits only `boss` points, outside the arena
      disc; start room points at least 8 tiles from the start centre.
- [x] Resource points: same filter at small clearance, preference for
      cliff-base and prop-adjacent cells, off the bridge-to-bridge line,
      6-10 per room, tagged `chest` / `breakable` / `ambient`.
- [x] Private RNG per room (`Random(seed * 7919 + room.id)`); the stage
      draws nothing from the world stream.
- [x] Hook the stage into `generate_world_steps` after `unseal`, yielding
      `"spawn points N of M"` so the loading screen keeps animating.
- [x] `tests/world/test_spawn_points.py`: the invariants in design section
      12, including "layout digest unchanged" and "a settings override
      changes the per-floor count".
- [x] **Rule: spawn points are visible in dev mode**, the way collision
      circles are. A `_dev_show_spawn_points` flag on `PlayingState`, dev
      mode only, with its own `DEBUG_KEYS` entry and a dev-menu toggle
      beside "Collision shapes" (`dev_menu_state.py`), drawn by a
      `WorldRenderer` pass next to the collider pass (`rendering.py`,
      camera-transformed at `cam.zoom`, in the depth layer above terrain).
      Enemy points as diamonds coloured by clearance (small / large),
      resource points as squares coloured by tag, each with its floor
      number, and the point's cooldown state once S3 lands (dimmed while
      cooling). Off in normal runs; no cost when the flag is off.

## S2 — Tables to data — done 2026-09-03 (see `journals/spawn_master_journal.md`)

- [x] `data/spawn_tables.json` with `phases` copied verbatim from
      `_PHASES`, `groups`, `difficulty` overrides, `residents`, `pacing`.
- [x] `game/content.py` loads it like the other JSON files and validates
      every enemy id against `enemies.json` at boot.
- [x] `spawn/tables.py`: phase lookup by run fraction, group template
      lookup, difficulty override merge.
- [x] `spawn/budget.py`: `SpawnDirector` moved here, reading the tables;
      `world/spawning.py` keeps `ring_point_outside_view` only.
- [x] Sequence test: a scripted 600 s run under a fixed RNG yields the same
      enemy-id sequence before and after the move.
- [x] Old imports (`from world.spawning import SpawnDirector`) keep working
      through a one-line re-export; the director tests moved to
      `tests/spawn/test_budget.py`, the ring-point ones stayed.

## S3 — The master, placement and groups — done 2026-09-03 (see `journals/spawn_master_journal.md`)

- [x] `spawn/__init__.py`: `Host` protocol and `SpawnMaster` facade with
      `update(dt)`, `spawn_group(template, at=None, owner=None)`,
      `spawn_at(enemy_id, pos, owner)`, `set_modifier` / `clear_modifier`.
- [x] `game/states/playing/spawning.py` becomes the adapter: builds the
      Host from `PlayingState`, constructs `Enemy` objects, forwards
      `spawn_boss`, `summon` and the arena's spawns with `owner` set.
- [x] `spawn/placement.py`: `choose(request)` with the six-step filter and
      weighted pick; follower ring placement; point cooldown; deferral with
      spawn debt and the 5 s relaxation.
- [x] The director's pack is the group: one `update()` returns the ids of
      one pack and the master seats them together (leader on the point,
      followers ringed). Phase rows keep `types`, and the elite roll stays a
      threshold draw, so the S2 sequence pin still holds; the `groups`
      templates serve `spawn_group()` (dev, arena, S4 residents).
- [x] `GameMap.offscreen_spawn_point` kept only for the `layout is None`
      world; the master routes there when there is no layout.
- [x] Events: `ENEMY_SPAWNED(enemy_id, owner, room)`.
- [x] `tests/spawn/test_placement.py`, `test_master.py` with a fake Host
      (`tests/spawn/fakehost.py`).
- [x] Overlay: a point on cooldown draws dimmed (the S1 rule's last clause).

## S4 — Locality and population — done 2026-09-03 (see `journals/spawn_master_journal.md`)

- [x] `config.SPAWN_LOCALITY = True` gate for one milestone (removed in S7).
- [x] `spawn/locality.py`: current room (cached until the rect is left),
      heading room (alignment threshold + 1 s dwell), grace room (6 s),
      bridge handling (other end is the heading room), `is_active(room_id)`.
- [x] `spawn/population.py`: `DormantEnemy` slotted record; `hibernate()`
      on a 0.5 s tick for out-of-zone enemies with lapsed aggro; `wake()`
      with an N-per-frame budget, farthest-first, walkability check with
      fallback to a free point on the same floor; `scatter_after` re-place.
- [x] Owners `arena` and `boss` never hibernate; `resident` seeding from the
      `residents` table on a room's first activation, all off screen.
- [x] Two caps: `live_cap` (default 100, growth from the existing step
      schedule capped there) and `world_cap` (the old 600); the director
      spawns against `live_cap - live_in_zone`.
- [x] Enemy serialisation lives on the adapter side as `PlayingHost.sleep()`
      / `wake()` (the master never imports `entities`); the record is
      `spawn.population.DormantEnemy`.
- [x] Events: `ROOM_ACTIVATED`, `ROOM_DORMANT`.
- [x] Debug overlay: `zone cur/head/grace`, `live / dormant / cap`.
- [x] Dev menu: "activate all rooms", "freeze spawns".
- [x] `tests/spawn/test_locality.py`, `test_population.py` (round-trip,
      pursuit keeps live, wake budget, owner exemptions, blocked fallback).

## S5 — Watchdog — done 2026-09-03 (see `journals/spawn_master_journal.md`)

- [x] `spawn/watchdog.py`: 1 s staggered sampling (`id % 60`); off-floor
      and no-progress rules; on-screen wait (until off screen or 8 s, then
      a poof); recycle keeps hp / shield / status; per-enemy recycle count
      with removal and a logged generation bug on the third.
- [x] Arena enemies re-positioned as the same object so `arena_ids` holds.
- [x] Event: `ENEMY_RECYCLED(enemy_id, reason)`; overlay `recycled n`.
- [x] `tests/spawn/test_watchdog.py`.

## S6 — Pacing — done 2026-09-03 (see `journals/spawn_master_journal.md`)

- [x] `spawn/pacing.py`: EMA of the weighted signals, dead-band, bounds;
      named modifier stack; all weights and bounds read from the `pacing`
      section of the tables.
- [x] Master subscribes to `PLAYER_DAMAGED` / `ENEMY_KILLED` through the
      Host's bus for the rate signals.
- [x] Dev menu "Spawn pressure" row cycling a `dev_menu` modifier through
      x1 / x2 / x4 / x0 / x0.5; overlay `pressure = pace x mods [signals]`.
- [x] `tests/spawn/test_pacing.py`.

## S7 — Performance pass — done 2026-09-03 (see `journals/spawn_master_journal.md`)

- [x] Stress harness (`python -m spawn.stress`): 100 live in the zone, 400 dormant elsewhere, 1200
      frames, player jitter; record p50 / p90 / p99 in the journal.
- [x] Tick LOD for out-of-aggro, off-view enemies (`config.ENEMY_LOD_SKIP`),
      measured, default 2. Skips whole frames, not just the behaviour tick:
      the profile put the per-enemy cost in the movement probe.
- [x] Share one `SpatialGrid` rebuild per frame -- measured and declined:
      both rebuilds together cost 0.1 ms/frame at 100 live.
- [x] Share one widest-class `NavGrid` -- measured and declined: ~0.2 s of
      a ~4 s load, and caching it on the layout would put a lattice into the
      pinned layout digest.
- [x] Remove the `SPAWN_LOCALITY` gate once the numbers are in.

## S8 — Resource points (future)

- [ ] First consumer (chests, breakables or ambient gems) reads
      `layout.resource_points` instead of searching; tag semantics
      confirmed against what that system needs.

---

## Open questions to settle before S4

- Should residents scale with difficulty only, or also with the run
  fraction at first visit? (Design assumes both.)
- Grace window and dwell time: 6 s and 1 s are guesses; playtest.
- Does a summoner's brood count against `live_cap`? (Design assumes yes,
  spawned through `spawn_at` with `owner="summon"`.)
