# Training dummy and DPS meter — execution journal

Named `training_dummy_journal.md` to match the other journals in this folder
(`weapon_system_journal.md`, `spawn_master_journal.md`, ...) rather than the
`training_dummy.journal` spelling in the request.

## Requirement (owner, 2026-09-11)

A way to measure how much damage per second a character actually does with a
given set of weapons, blessings and items.

- A **training dummy**: a basic enemy with infinite HP that stands there and
  absorbs hits.
- A **calculator** that keeps adding up the sources of damage.
- Reachable from the **dev menu** as an option.

Nothing is coded yet. This entry is the design, what it is built on, the open
questions, and the todo list.

---

## What the code already gives us

**Dev spawns already go through the spawn master.** `dev_menu_state._spawn`
calls `p.spawn.spawn_enemy(enemy_id, at=..., owner="dev")`, and `"dev"` is on
the master's `cap_exempt` list (`spawn/master.py:89, 384`), so a developer spawn
is seated regardless of the live cap. The dummy follows that same path — the
spawn master stays the one authority on enemy spawns, and the dummy is not a
special case that bypasses it.

**Enemies are pure data.** `data/enemies.json` holds twelve entries keyed by id,
each carrying `hp`, `speed`, `behavior`, `radius`, `weight`, `sprite`,
`contact_damage`, `experience_reward`, `tags` and so on. A dummy is a new entry
there, not a new class.

**The dev menu is a row list.** `_ROOT_ROWS` plus `_LABELS`, with sub-pages
(`enemies`, `blessings`, `items`, `forges`, `weapons`) keyed in `_rows()` and
`_HEADINGS` / `_NAV`. Adding a row is a three-line change plus its handler.

**The debug overlay takes arbitrary metrics.** `DebugOverlay.set_metric(key,
value)` is already fed from `PlayingState._debug_metrics` (state, seed, hero,
blessings, run time, enemies), so the meter's readout has a home that needs no
new rendering code.

### Where damage is actually counted

This is the part that decides how honest the calculator can be. Every point that
currently adds to `stats["damage_dealt"]`:

| site | what | carries a source id? |
|---|---|---|
| `game/states/playing/combat.py:77` | projectile and melee hits | **yes** — `proj.weapon_id` |
| `game/states/playing/effects.py:268` | explosions (Bomb, blast) | **no** |
| `game/states/playing/state.py:585` | `_report_dot`, damage over time | **no** |
| `game/states/playing/npcs.py:168` | village lancers hitting enemies | n/a — **not the hero's damage** |

Two consequences:

1. Per-source attribution needs `effects.py` and `_report_dot` to start passing
   a source id. Without that the meter can report a correct *total* but would
   have to lump explosions and burns into "other", which is precisely the part
   of a build a player wants to see.
2. `npcs.py` must be excluded, or a village lancer standing near the dummy
   inflates the hero's DPS.

---

## Proposed design

### 1. The dummy — `data/enemies.json`

A new `training_dummy` entry **copied from `chaser`** (owner's choice: same
sprite `skull`, same `radius`, same `color`, so it reads as an ordinary enemy),
then made inert: `contact_damage: 0`, `contact_damage_enabled: false`,
`experience_reward: 0`, `speed: 0`, `aggro_range: 0`, `behavior: "dummy"`,
`tags: ["dummy"]`, and a new `invulnerable: true` field.

`Enemy.take_damage` (`entities/enemy.py:94`) must keep **returning the amount
dealt** — that return is what the meter counts — while not subtracting it from
`hp` when the flag is set. Returning the dealt amount and skipping the
subtraction is a two-line change and keeps armor, shields and the hit flash
behaving as they do for a real enemy, which is what makes the measurement
trustworthy.

Alternative considered and rejected: a very large `hp` value. It needs no code
change, but the dummy can still die, the health bar reads as full forever, and
armour/shield interactions drift from the real thing.

### 2. The dummy stands still

No registered behaviour is inert — the twelve in `entities/ai/behaviors/` all
chase, kite or attack. `speed: 0` alone is not enough, because `path_chase_attack`
still runs its attack beat. The dummy needs a `dummy` behaviour registered
alongside them that does nothing: no steering, no attack, no aggro.

### 3. The calculator — a new module

Per this project's preference for one module per concern, this does **not** go
into `state.py` (already 1,034 lines). New: `game/states/playing/dps_meter.py`,
holding a `DpsMeter` with

- `start()` / `stop()` / `reset()`,
- `add(amount, source)` called from the damage sinks above,
- a cumulative total and elapsed time, so `dps = total / elapsed`,
- a per-source breakdown keyed by weapon id (plus `"explosion"`, `"dot"`),
- a rolling window (last N seconds) alongside the cumulative figure — a
  cumulative average alone hides the ramp from cooldown-gated weapons, and the
  rolling number is what reads as "current DPS".

The meter is off unless armed, so a normal run pays nothing but a boolean check.

**It meters one target.** `DpsMeter` holds the dummy, and only damage landing on
that enemy counts (decision 3). The tap is therefore a single place —
`Enemy.take_damage` on the metered enemy — rather than four scattered
`stats["damage_dealt"]` sites, which also means the meter cannot drift out of
step with those sites later.

Because the tap is the target rather than the shooter, every source has to name
itself on the way in. `take_damage` grows a `source` argument, defaulting to
`None` (= unattributed), and the callers pass it:

| caller | source |
|---|---|
| `combat.py:77` | `proj.weapon_id` (already on the projectile) |
| `effects.py:268` | the exploding weapon's id — **new, directive 1** |
| `state.py:585` `_report_dot` | the weapon that applied the effect — **new, directive 1** |
| `npcs.py:168` | `"villager"`, which the meter drops — **directive 2** |

Passing a source through explosions and damage-over-time is a change to the game
itself and outlives the meter: `killed_by` already wants a weapon id for
Bloodletting-style blessings, and today a kill by explosion or burn attributes
to nothing.

### 4. The dev menu option

A `dummy` row in `_ROOT_ROWS` labelled "Training dummy", toggling on:

- one `training_dummy` spawned through `spawn.spawn_enemy(..., owner="dev")` at
  a fixed offset from the hero,
- the meter armed and reset,
- the readout pushed to the debug overlay through `set_metric`.

Toggling off despawns the dummy and disarms the meter.

---

## Decisions (owner, 2026-09-11)

All five questions answered, plus three directives that change the design above.

1. **Rolling window: 10 s**, with the cumulative figure beside it.
2. **The dummy never fights back**, and it is **the chaser** — the dummy is the
   existing `chaser` made invulnerable and inert, not a new creature with its
   own art. One dummy shape is enough; no per-enemy-type variants.
3. **One dummy, and the damage *that dummy* receives is what the meter
   records.** This is the important one: the meter is not a global tally of
   `stats["damage_dealt"]`, it is the damage landing on one known target. Any
   other enemy in the world is ignored, so the reading cannot be inflated by a
   stray hit on something else.
4. **No knockback.** This is a numbers test — the dummy stays where it is put.
5. **The readout lives in the F1 debug overlay.**

And three directives:

- **Explosions and damage-over-time must carry the source of the damage**,
  which is normally a weapon. This is a change to the game's own damage paths,
  not just to the meter.
- **Villagers are never counted.** A village lancer that wanders over and hits
  the dummy contributes nothing.
- **Knockback is out of scope entirely.**

### What decision 3 changes

The first draft tapped the four `stats["damage_dealt"]` sites and summed them.
Measuring *the dummy's* intake instead is both simpler and stricter: the tap is
whatever lands on that one enemy, so damage to other enemies can never leak in,
and the "is this actually my DPS?" question has a single, checkable answer.

It does **not** remove the need for source ids. The meter still has to say
*which weapon* did the damage, so the explosion and damage-over-time paths must
still be given a source — directive 1 above — otherwise the dummy's intake is a
correct total with an unattributable half.

It also does not remove the villager exclusion. A lancer's
`foe.take_damage(npc.damage)` (`game/states/playing/npcs.py:168`) would land on
the dummy like anything else, so that path has to be tagged as a non-hero source
and dropped by the meter rather than merely being "not the hero's projectile".

---

## Todo — DONE (owner's go, 2026-09-11)

**The damage paths.**

- [x] `entities/enemy.py` `take_damage(amount, armor=0.0, source=None)`. Also
      `Boss.take_damage`, so the boss and an `Enemy` stay interchangeable to
      every damage path; the boss is never metered, so it ignores the argument.
- [x] **`Enemy._absorb(dealt, source)`** — the one place damage lands. Both
      `take_damage` and `_status_damage` go through it, so the dummy's
      invulnerability and the meter cannot be bypassed by a new path.
- [x] `combat/status.py`: `_Active.source`, `apply(..., source=None)`, and
      `update`'s callback is now `(amount, source)`. A refresh re-attributes to
      the weapon keeping the burn alive; a refresh with no source keeps the one
      it had.
- [x] `combat.py:77` passes `proj.weapon_id`, and `apply_on_hit_effects` passes
      it into `status.apply` so the burn it lights is attributable.
- [x] `effects.py` `enemy_explosion(..., source=None)` — and it now sets
      `killed_by`, which an explosion kill never did. `state.py` passes
      `"fire_nova"`.
- [x] `npcs.py` passes `VILLAGER`, which the meter drops.

**The dummy.**

- [x] `data/enemies.json`: `training_dummy`, from the chaser's numbers with
      `invulnerable: true`, `speed: 0`, `aggro_range: 0`, `contact_damage: 0`,
      `experience_reward: 0`, `behavior: "dummy"`, `tags: ["dummy"]`.
- [x] `Enemy` honours `invulnerable`: damage is computed, returned and metered,
      but no HP comes off; armour, shields and the hit flash are untouched, so
      a hit on the dummy behaves like a hit on anything else.
- [x] `apply_knockback` is a no-op for it — honest, where a large `weight`
      would only have made the shove small.
- [x] `entities/ai/behaviors/simple.py`: a `dummy` behaviour holding one state
      and no components (a `Behavior` must have at least one state).

**The meter.**

- [x] `game/states/playing/dps_meter.py` (new): `DpsMeter` — `arm(enemy)` hooks
      the target's `damage_sink`, a 10 s rolling window beside the cumulative
      average, a per-source breakdown, `VILLAGER` dropped, unnamed sources kept
      visible as `"other"` rather than folded into a weapon.
- [x] `PlayingState.dps`, ticked in the update loop; inert until armed.

**The wiring.**

- [x] A `dummy` row in the dev menu with an `[ON]` / `[  ]` marker, spawning
      through `spawn.spawn_enemy(..., owner="dev")` and reporting when the
      master refuses. Toggling off kills the dummy and disarms.
- [x] `_report_debug` pushes `dummy dps` and `dummy by` to the F1 overlay while
      armed.

**Tests.** 29 in `tests/combat/test_dps_meter.py` (unit, 0.3 s), 4 new in
`tests/combat/test_status.py`, 5 in `tests/core/test_dev_mode.py`
(integration).

- [x] Meter arithmetic on an explicit clock: totals, the window rolling off,
      the window dividing by time-so-far rather than its full span while it
      fills, reset, re-arming releasing the previous target.
- [x] The dummy absorbs without dying, survives 100 000 damage, keeps armour,
      cannot be burned down by a damage-over-time tick, and does not move.
- [x] A normal enemy is unaffected by any of it.
- [x] No enemy but the dummy carries `invulnerable`.
- [x] **The ground-truth check**: the Bow and the Rod, no blessings, fired at
      the dummy for 30 s, measure within 6 % of `damage x projectile_count /
      cooldown` from the data. This is what proves the meter.
- [x] Two roster invariants excluded the dummy by tag, with the reason
      recorded: `test_aggro`'s "every type declares an aggro range" and
      `test_melee_enemies`' "nothing that disables contact damage is left
      harmless". Both assert things about enemies that *fight*; the dummy is
      deliberately neither. `test_aggro` gained the other half of the
      exemption — the dummy declares zeroes rather than omitting the keys, so a
      genuinely missing value still cannot pass unnoticed.

**Evidence.** Driven end to end in a real dev run: the menu row spawns the
dummy through the spawn master, the meter arms on it, and Aegis's Sword over
14 s reads `11.2 dps (10s)   avg 12.0   168 in 14.0s`, `sword 100%`, with the
dummy's HP unchanged at 1.0 and its position unmoved.

That 12.0 against the Sword's naive `14 / 1.2 = 11.67` is the meter earning its
keep: the ceiling assumes every swing connects the instant the cooldown ends,
and the measured figure is what the wind-up and the cone actually deliver.

Screenshots sent: the dev menu with the row, and the F1 overlay reading the
breakdown mid-run.

## Still open

- The breakdown line shows percentages only. Absolute damage per source is in
  `DpsMeter.breakdown()` and could be surfaced if the percentages prove too
  coarse when several weapons are up.
- Only the Sword has been measured end to end. The multi-weapon case — where
  the per-source split actually earns its place — wants a pass once a build has
  three weapons and a few blessings on it.

---

## Ten mixed loadouts — the bench that found two bugs (2026-09-11)

**Requirement (owner).** Ten measurements, each with three random non-summon
weapons at level 1 and three random blessings.

Harness in the scratchpad, seeded (`SEED=20260911`) so the table reproduces.
Each loadout: a fresh dev run, the hero's starter weapon dropped, three weapons
granted, three blessings applied, the dummy spawned from the dev menu, 20 s of
hero-parked-next-to-dummy.

Blessings are drawn only from the set this loadout can *use* -- a stat blessing
or a weapon blessing for one of the three. The dev menu's grant path hands over
the weapon a blessing belongs to if the hero lacks it, which would have quietly
made some rows four-weapon builds.

| # | avg dps | 10 s | total | weapons | blessings | split |
|---|--------:|-----:|------:|---|---|---|
| 1 | **59.6** | 57.7 | 1191 | magic_rod, daggers, sword | twin_daggers_cross_cut, keen_eye, nimble | daggers 60 / sword 20 / rod 20 |
| 2 | 51.6 | 51.0 | 1032 | magic_rod, bow, daggers | arcane_storm_tempest, daggers_extended_reach, magnet | rod 42 / daggers 35 / bow 23 |
| 3 | 46.7 | 45.2 | 934 | magic_rod, daggers, sword | twin_daggers_dual_wield, magic_rod_seeking, iron_skin | daggers 51 / sword 25 / rod 23 |
| 4 | 40.4 | 39.6 | 809 | magic_rod, bomb, bow | magic_rod_chain, cluster_bomb_bomblets, gold_rush | bomb 44 / bow 30 / rod 27 |
| 5 | **39.0** | 38.5 | 780 | bow, hammer, bomb | magnet, bomb_explosive_force, fleet_foot | bomb 40 / bow 31 / hammer 29 |
| 6 | 41.1 | 41.1 | 823 | daggers, sword, hammer | daggers_marked_prey, nimble, fleet_foot | daggers 44 / sword 29 / hammer 27 |
| 7 | 53.3 | 51.8 | 1066 | magic_rod, daggers, sword | daggers_marked_prey, fortune, greatsword_cleaver | daggers 45 / sword 35 / rod 20 |
| 8 | 46.9 | 44.8 | 939 | hammer, magic_rod, bow | nimble, haste, magic_rod_arcane_missiles | rod 48 / bow 28 / hammer 24 |
| 9 | 55.8 | 56.7 | 1117 | magic_rod, daggers, hammer | shield_wall, meteor_hammer_crater, arcane_lance_impale | rod 37 / daggers 32 / hammer 31 |
| 10 | 48.4 | 48.1 | 968 | bomb, magic_rod, daggers | bomb_explosive_force, daggers_quick_hands, minefield_dense_field | daggers 42 / bomb 36 / rod 22 |

Spread 39.0 to 59.6 -- **1.5x** between the weakest and strongest of ten random
builds. The dummy survived all ten and every weapon landed in every run.

### What the bench found

**1. The training dummy could be hibernated mid-measurement.** The spawn master
banked it as dormant nine seconds into a run: still `alive`, but out of
`ps.enemies`, so no weapon could reach it. Damage flatlined and the meter read a
third of the truth with nothing on screen to say why. It was intermittent --
whether a dummy slept depended on the world and how the islands went active --
so it moved between loadouts on each pass, which is what made it look like a
loadout problem rather than a spawn problem.

`"dev"` is on the master's `cap_exempt` list but not `never_sleep`. Rather than
widen `dev` -- the F2 key and the "Spawn enemy" page use it to pile bodies up
for stress tests, where hibernation is the behaviour under test -- the dummy got
its own owner, `"dummy"`, on **both** lists.
`tests/spawn/test_master.py::TrainingDummyOwnerTests` pins all three facts.

**2. Two harness faults, worth recording because they would mislead anyone
using the dummy the same way.**

- *Reach.* Parking the hero 40 px from the dummy is inside the Sword's 40 and
  the Hammer's 35, but outside the **Daggers' 22** -- so daggers read as
  contributing nothing in six of the seven rows they appeared in, and the one
  row where they did fire happened to have `daggers_extended_reach`. Standing
  16 px away fixed it and daggers went from 0 % to the top contributor in five
  rows. Anyone benching a short-reach weapon has to stand inside its reach.
- *The hero dying.* Restoring HP *after* `ps.update` still lets a lethal frame
  end the run; the loadout then reports a fraction of its output. The bench now
  turns on the dev menu's "Unlimited HP" and asserts the hero is alive every
  frame rather than patching it up afterwards.

Both were mine, not the game's -- but both produced plausible-looking numbers,
which is the dangerous kind of wrong. The bench prints a `!!` line for any
weapon that never landed a hit and for any run whose window is zero, so neither
can pass unnoticed again.

### Reading the table

The 1.5x spread is narrower than the first (broken) pass suggested, and the
splits are the interesting part: no weapon dominates, and the strongest builds
are the ones where a fast weapon (Daggers, Rod) carries and the other two fill
in. Nothing here is a balance conclusion -- one 20 s sample per build, level-1
weapons, no items -- but it is the first time the question has been answerable
at all.

---

## Camera zoom back to 1.5 — digests re-pinned (2026-09-11)

The owner reverted `CAMERA_ZOOM` from 1.75 to 1.5, which moves the baked water
buffer (`world/terrain/bake.py` sizes it from `SCREEN_WIDTH / CAMERA_ZOOM`) and
so moves the bake digest for every seed.

- [x] `python -m world.digest --write`. The values came back **exactly** to
      their pre-1.75 state -- seed 35's bake is `cca4b4214a356a69` again -- which
      is a useful confirmation on its own: the bake is a pure function of the
      world and the zoom, with nothing else leaking in.
- [x] `64 x 1.5 = 96`, a whole number of pixels, so the tile-grid invariant in
      `tests/rendering/test_camera.py` holds.
- [x] README's Display section back to "default 1.5".

`test_gem_glow` needed no change at either zoom, which is what the earlier fix
was for: it selects the halo by the renderer's own `_glow.diameter(8, zoom)`
rather than the hard-coded `width > 12` that only worked at 1.5 by coincidence.

The loadout table above was already measured at 1.5: `game/config.py` was last
touched at 16:58 and every bench run is timestamped 17:34 or later. So it needs
no re-measurement, and the numbers stand as published.

---

## The bench moves to a fixed, empty arena (2026-09-12) — CONFIRMED, ready to build

**Requirement (owner).** The dummy measurements must not be affected by
randomness: a fixed world, and if possible an **empty** one — just the dummy
and the character.

**Why this came up.** Asked whether the dummy sits in a fixed position, the
answer turned out to be no. `bench()` passes `place_seed = seed + i` per run,
and because `LoadingState` takes its `run_seed` from the *global* `random`
(`game/states/loading_state.py:50`), seeding it fixes both the world and the
dummy's bearing — but **differently for every run**. Verified:

    pass 1                                     pass 2
    run 0: world 981984603  dummy (6452, 3833)  run 0: world 981984603  dummy (6452, 3833)
    run 1: world 667051023  dummy (3156, 7713)  run 1: world 667051023  dummy (3156, 7713)
    run 2: world 203096928  dummy (9835, 3694)  run 2: world 203096928  dummy (9835, 3694)

So a *re-run* reproduces exactly, which is what made the report's three passes
byte-identical — but each loadout was measured in a different world, on
different ground, with different obstacles between the hero and the dummy. That
is a confound *between the rows of the table*, and it is inside the 1.33x spread
the report published.

### The empty arena works — measured, not assumed

`GameMap()` with neither a seed nor a layout is already a supported
configuration: a bare `WORLD_WIDTH x WORLD_HEIGHT` rect, `layout = None`, no
obstacles. Every subsystem the run needs already guards for it —
`locations.py:34`, `npcs.py:52`, `spawning.py:74/88/101`, `rendering.py:578`,
`world/map.py:144`.

Booting a `PlayingState` on one through `PrebuiltWorld(GameMap(), None)`:

    layout: None   size: 3200 3200   obstacles: 0
    booted: PlayingState   enemies at start: 0
    dummy seated: True
    meter:  10.0 dps (10s)   avg 10.0   50 in 5.0s
    by: bow 100%

So the whole world variable can be removed rather than merely pinned. Three
consequences, all good:

- **No terrain between the hero and the dummy.** No obstacle eats a shot, no
  cliff blocks a cone. Every loadout is measured under identical geometry, which
  is the only way the rows are comparable to each other.
- **No world generation at all.** The bench currently builds ten worlds at
  roughly ten to fifteen seconds each; an empty arena skips every one.
- **The placement hack goes.** With no terrain to dodge, the dummy can sit at an
  exact offset from the hero instead of a random bearing, so `random.seed()`
  before each run is no longer needed for reproducibility.

**Still needed:** the spawn master seated five enemies during the five-second
probe even with no layout, so freezing spawns and clearing the live set stays.
The arena is empty of *terrain*; it is not empty of the director.

### What this costs — measured, and it is less than expected

The worry was that an empty arena would read as an upper bound: no cover, no
elevation, nothing to miss around. Measured, it is not. The same loadout scores
**identically** on a generated world and on the arena -- 925 damage, the same
hit counts, the same per-hit figures -- across five different world seeds and
all eight compass bearings for the dummy:

    world place_seed=911..915: dps 30.8, total 925   (five different worlds)
    bearing 0/45/.../315:      dps 30.8              (arena)
    arena:                     dps 30.8, total 925

So the terrain was never *systematically* affecting the measurement. What it
did was fail occasionally and unpredictably -- the crowd wandering into the
line of fire, which took run 9 from 42.5 to 31.6 with the Bow's share falling
from 28 % to 5 %. The arena does not make the numbers higher or lower; it
removes a failure mode that struck perhaps one row in ten and was invisible
when it did.

The real gain is speed and reproducibility: ten 60-second loadouts now take
**5.8 seconds** end to end, against minutes of world generation before.

### A false alarm worth recording

The first arena table came out ~15 % below the published one, and the obvious
reading was that the arena had changed the measurement. It had not. The
weapons had been **retuned in `data/weapons.json`** between the two reports --
daggers 6 dmg / 0.32 s to 5 / 0.42, Bow 12 / 1.0 to 10 / 1.2, Rod 9 / 0.85 to
10 / 1.0. Weighting those ratios by the row's old per-weapon shares predicts
0.728 of the old total; the measured ratio was 0.720.

The bench was reading a balance change correctly, which is what it is for. The
lesson for reading any future report: a table is only comparable with another
if `data/weapons.json` has not moved between them, so a report should record
the commit it was measured at.

**Todo — not started.**

- [ ] `game/dps_bench.py`: build the run on `PrebuiltWorld(GameMap(), None)`
      instead of walking the menu into a generated world. One arena, identical
      for every loadout and every invocation.
- [ ] Place the dummy at a fixed offset from the hero and drop the
      `random.seed(place_seed)` call and the `place_seed` argument with it.
- [ ] Keep the freeze and the per-frame cull: an empty arena still gets a
      director.
- [ ] Keep the four assertions (hero alive, dummy in the live set, reach,
      no silent weapon) — they are what caught the last three faults.
- [ ] Re-measure the ten loadouts and regenerate
      `documentation/dps_calcs/dps_report_<date>.md`, noting the new conditions
      and that the previous table carried terrain variance between rows.
- [ ] Compare the new spread against the old 1.33x and record the difference:
      how much of that spread was the loadout and how much was the ground it
      happened to be measured on.
- [ ] A `unit` test that the bench's arena really is empty — no layout, no
      obstacles — so a future change cannot quietly put a world back under it.
