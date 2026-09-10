# The First Hunger roams free — todo

The boss and the brood it summons stop caring about terrain entirely: no
obstacles, no elevation, no flow field, no island edge. The boss also
spawns near the hero instead of in the boss room. Companion journal:
`journals/enemy_ai_journal.md` ("The First Hunger flies", 2026-09-03,
whose "may not leave the floor" decision this reverses).

Conventions, as everywhere:

- Tuning lives in data (`data/bosses.json`, `data/enemies.json`) or
  `game/config.py`; no per-entity defaults in code. Taxonomy stays a tag.
- The tag decides. `"flying"` already flips the collider and the boss's
  steering; the same tag flips the enemy steering stack. No second flag.
- Tests use the shared cached worlds (`tests/worlds.py`); no per-test
  world generation.

---

## What is true today (2026-09-10)

- **The boss** `the_first_hunger` (`data/bosses.json`, `giant_bat` rig)
  carries `tags: ["boss", "flying"]`. `Boss.flying` makes the collider
  skip the terrace margin, the elevation rule, the radius probes and
  every obstacle (`GameMap.is_walkable(flying=True)`), and `Boss._seek`
  beelines instead of reading the flow field. **It still may not leave
  the island**: the flying floor is `floor.over_island` (any height-map
  cell) plus the bridges, so the sea is a wall and the boss slides along
  the coast.
- **Its brood.** Pattern `summon_brood` calls `ctx.summon("swarm", pos, 8)`
  -> `Spawner.summon` -> `SpawnMaster.spawn_at(pos ± 40 px, owner="summon")`
  -> `_make`, with no placement check. `swarm` ("Mite", `bumblebee` rig,
  `behavior: "path_chase"`, tags `["swarm"]`) is a **walker**: the
  pursuit stack is flow-field seek + separation + obstacle avoidance +
  unstick, and `Enemy.update` resolves movement with the full walker
  collider. `"flying"` in an enemy's tags does nothing today (recorded as
  "left deliberately" in the journal). A brood dropped where the bat
  hovers over a cliff face or a lake is stuck or wedged.
- **Boss spawn.** `Spawner.spawn_boss` at `config.BOSS_FRACTION` (95 % of
  the run) places it at `boss_arena_point()` = the boss room's centre
  (`layout.boss_id`), wherever the hero is. The "APPROACHES" warning
  (`_boss_warning_t = 2.6`) plays while the boss is typically a whole
  island away.

---

## R1 — The flying floor is the world — done 2026-09-10

- [x] `GameMap.is_walkable(flying=True)`: return whether the point is
      inside the world rect (`0..width`, `0..height`) — nothing else. The
      sea, the cliff walls and the water between islands are all air.
      `resolve_movement` already carries the flag through its slides and
      escape hops; no change there.
- [x] Decide the fate of `floor.over_island` / `GameMap._over_island`:
      the flying rule was their only caller. Delete both unless another
      reader appears; do not leave a rule with no body.
- [x] `tests/ai/test_flying.py`: `test_a_flyer_still_may_not_leave_the_island`
      becomes "a flyer crosses the sea between two islands";
      `test_the_flying_floor_is_the_grid_plus_the_bridges` becomes "the
      flying floor is the world rect" (inside: yes; one px outside: no).
      The obstacle / cliff / lake / seek cases stay as they are.
- [x] Journal: supersede the "what it still may not do: leave the floor"
      paragraph with the new rule and the reason (the boss hunts the
      hero itself, so an unreachable boss is a boss on its way).

## R2 — The brood flies too — done 2026-09-10

- [x] `data/enemies.json -- swarm`: `tags: ["swarm", "flying"]`. Data
      only; any other enemy can opt in the same way later.
- [x] `Enemy.__init__`: `self.flying = "flying" in self.tags` (mirror of
      `Boss`). `Enemy.update`: `ctx.resolve_movement(..., flying=self.flying)`.
- [x] `entities/ai/behaviors/simple.py -- _pursuit_stack(cfg)`: when
      `"flying"` is in `cfg["tags"]`, the stack is `SeekTarget(via="straight")`
      + `Separation` only — no `AvoidObstacles`, no `Unstick` (a body that
      passes through everything is never stuck). `path_chase`, `swarm` and
      `path_chase_attack` all build from it, so one branch covers them.
- [x] Check the melee beat in `path_chase_attack` and the other
      components that call `per.is_walkable` / `per.obstacles_near`
      (`components/crowd.py`) for anything that would still hold a flyer
      back; none expected beyond the two removed above. *Checked:*
      `path_chase_attack` builds its chase from `_pursuit_stack`, and
      `obstacles_near` has one reader, `AvoidObstacles`, which the flying
      stack omits.
- [x] Spawn master: `spawn_at(pos)` already seats a summon with no floor
      test. Confirm the LOD tick / dormancy path (`population`,
      `ROOM_DORMANT`) does nothing odd with a live body that is over no
      room — a mite chasing across the sea must not be filed as dormant
      or culled. *Found and fixed:* hibernation skips a body over no room,
      but the **watchdog** recycled one at once (`off_world` / `off_floor`);
      `_judge` now judges a `flying` body by the flying floor.
- [x] `tests/ai/test_flying.py`: enemy cases beside the boss ones — the
      shipped `swarm` flies and the tag is what decides it; a mite passes
      the obstacle that blocks a walker; crosses the cliff; the stack has
      no obstacle avoidance and seeks straight. `tests/ai/test_boss.py`
      `test_summon_pattern_calls_summon` unchanged.

## R3 — Both bodies over air: what else reads the floor — done 2026-09-10

- [x] Rendering: `PlayingState._actor_items` bands each actor by
      `renderer.level_at(x, y)`. Verify what `level_at` answers over the
      sea and over a cliff wall (no floor) and that the boss and the mites
      draw in a sensible band there (they should read as *above* the
      terrain: the top band, or the band of the nearest floor). Fix in
      `_actor_items` if a flyer vanishes or sinks under a terrace edge.
- [x] Combat: the contact bite (`combat.py`) and the hostile barrage
      (`fire_hostile` -> `stamp_fire_level` -> `block_on_terrain`). A boss
      firing from over the sea samples `top_at_point` where there is no
      floor; make sure its bullets are not killed on the first tile they
      cross, and that contact across a level difference (the verticality
      rule) is judged the way you want for a flyer — probably "a flyer
      bites whatever it touches". *Verified, no change:* the bite is
      elevation-blind; a shot stamped over the sea carries `NONE` and is
      exempt from the terrain rule (pinned in `ShotsOverTheSeaTests`).
- [x] The hero's own targeting / auto-attack reach and the projectile
      elevation rule (LD-9 D10) against a boss over the water: a shot from
      the shore at a bat over the sea must still land. Verify, and note
      in the journal either way. *Verified, no change:* targeting has no
      elevation filter; `top_at_point` over the sea is `NONE`, which blocks
      nothing (pinned in `ShotsOverTheSeaTests`).
- [x] `Enemy` knockback: `_knock` steps go through `resolve_movement`
      with the flag, so a shoved mite may cross water; that is fine, just
      note it.

## R4 — The boss spawns beside the hero — done 2026-09-10

- [x] `config.BOSS_SPAWN_DISTANCE` (world px) with a comment: how far from
      the hero the boss appears. Proposed default: just outside the view
      — half the visible diagonal at the current zoom plus a pad — so it
      flies onto the screen during the 2.6 s "APPROACHES" warning instead
      of being a rumour on another island. A `GenSettings` snapshot is not
      needed; this is a run-time knob, not a generation one. *Shipped at
      680 px* (half the diagonal is ~612 px at zoom 1.5 on 1600x900).
- [x] `Spawner.boss_arena_point` -> `boss_spawn_point`: a random angle
      round the hero at that distance, clamped to the world rect. No floor
      test, no room lookup: the boss does not care what is under it.
      Keep the name `boss_arena_point` as a one-line alias only if a test
      or the dev menu reaches for it; otherwise drop it.
- [x] `layout.boss_id` and the `boss`-tagged spawn points stay: the spawn
      master and the world generator still use the boss room for everything
      else. Only the boss's own placement stops reading it.
- [x] Tests: `tests/spawn/` (or `tests/ai/test_boss.py`) — the spawn point
      is `BOSS_SPAWN_DISTANCE` from the hero (± the clamp), inside the
      world rect, and does not depend on where the boss room is; the dev
      key and `_spawn_boss` share the path (`tests/core/test_smoke.py`
      already presses it).
- [x] Journal entry with a measurement: on seed 35, the time from the
      warning to first contact before and after.

## R5 — Docs — done 2026-09-10

- [x] `documentation/spawn_master_design.md` and `level_design.md`: the
      boss room is no longer where the boss appears; say so where the
      arena is described. *`level_design.md` "Roles" says so; the spawn
      master design's only mention is its "before" audit table, left as
      history.*
- [x] `journals/enemy_ai_journal.md`: one entry for R1–R4 with the numbers
      (obstacles passed on the seed, sea crossing, spawn distance).

---

## Decisions — confirmed by the owner 2026-09-10 (all three as proposed)

1. **The sea is air.** "Move wherever" is read as *over the water too*.
   The trade-off: the charge pattern can carry the boss out over the sea
   and the hero cannot follow; it comes back on its own because it seeks
   the hero. If you would rather keep a leash, the alternative is a
   soft one — a flyer may cross the sea but `_seek` adds a pull back
   toward the nearest island when it is more than N px off any floor.
2. **The mites fly by tag**, in data, with the enemy steering stack
   reading the same tag the boss does. Any enemy can be made a flyer
   later by adding the tag.
3. **Spawn distance**: just off-screen at the current zoom, random side.
   If you want it even closer (visible on spawn), the same knob does it.
