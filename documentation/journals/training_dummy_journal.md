# Training dummy and DPS meter — execution journal

**Legacy ID:** CMB-003 · **Systems:** CMB, UI · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

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

*(DOC-005, 2026-09-24: "only the Sword measured" is **done** — the sections below measure ten loadouts, then 180 builds. The breakdown line's absolute damage is still **pending**: the overlay shows shares only (`devtools/dps_meter.py`); the bench already reports absolutes)*

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

- [x] `python -m tools.verification.world_digest --write`. The values came back **exactly** to
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

**Todo — done** (ticked by DOC-003, 2026-09-22).

- [x] `game/dps_bench.py`: build the run on `PrebuiltWorld(GameMap(), None)` *(DOC-003: built in `tools/benchmarks/dps_bench.py` (the module moved from `game/`))*
      instead of walking the menu into a generated world. One arena, identical
      for every loadout and every invocation.
- [x] Place the dummy at a fixed offset from the hero and drop the *(DOC-003: the dummy sits 140 px east of the hero; no `place_seed` left)*
      `random.seed(place_seed)` call and the `place_seed` argument with it.
- [x] Keep the freeze and the per-frame cull: an empty arena still gets a
      director.
- [x] Keep the four assertions (hero alive, dummy in the live set, reach, *(DOC-003: hero alive and dummy live still raise; reach became the fixed 16 px standoff; a silent weapon is reported, not raised)*
      no silent weapon) — they are what caught the last three faults.
- [x] Re-measure the ten loadouts and regenerate *(DOC-003: `documentation/dps_calcs/dps_report_2026-09-12.md`; the 2026-09-19 reports state their conditions)*
      `documentation/dps_calcs/dps_report_<date>.md`, noting the new conditions
      and that the previous table carried terrain variance between rows.
- [x] Compare the new spread against the old 1.33x and record the difference: *(DOC-003: recorded above under “What this costs”: the arena scores the same as a generated world, so the terrain added no spread)*
      how much of that spread was the loadout and how much was the ground it
      happened to be measured on.
- [x] A `unit` test that the bench's arena really is empty — no layout, no *(DOC-003: `tests/devtools/test_dps_meter.py::BenchArenaTests`)*
      obstacles — so a future change cannot quietly put a world back under it.

---

## Thirty measurements per level — CONFIRMED (owner, 2026-09-19)

**Requirement (owner).** Review the current training-dummy tests. Run
*several* measurements — around thirty — to get the average, the median and
the overall capability of the player to deal damage **at certain levels**.

### What the bench does today, and what it does not

`tools/benchmarks/dps_bench.py` measures **ten** random loadouts, each *three
random non-summon weapons at level 1 plus three random blessings*, on Aegis,
no items, one 30 s (or 60 s) sample per build, on the empty arena. The report
gives the mean, the min/max spread and the per-weapon contribution.

Three gaps against the new requirement:

1. **Sample size.** Ten rows; the requirement is around thirty.
2. **No median, no distribution.** The report has a mean and the two
   extremes. The median, quartiles and standard deviation are not computed.
3. **No notion of level.** Every row is "three weapons at level 1 + three
   blessings" — a build no player ever holds at any particular level. The
   requirement is the damage a player can deal *at level N*, which means the
   build has to be what N-1 level-up picks actually produce.

### How I read "at certain levels" — assumptions to confirm

- **Level = hero level**, not weapon level. A hero at level N has taken N-1
  level-up cards. The bench would simulate those picks through the real
  offering (`progression.blessings.offer.roll_offering`, seeded), so a level-10
  build is whatever nine cards from the real pool give: weapon grants,
  blessing levels, possibly a summon or a Forge, exactly as the level-up screen
  would offer them.
- **Pick rule.** Each level-up rolls the real three-card offering and takes
  one at random. That measures an *average* player; a "best of three" rule
  would measure a good one. Random is the proposal; both are cheap to add.
- **Level checkpoints.** Proposal: **1, 5, 10, 15, 20, 25** — level 15 is the
  pacing milestone `progression/experience.py` is tuned around, and 25 is
  where the late-game discount is fully in. Thirty builds at each.
- **Everything else held still**, as before: Aegis, the empty arena, 16 px
  standoff, spawns frozen, one sample of 30 s per build. Items from chests,
  potions and meta-upgrades stay out — they are not level-up picks.
- **Summons** were excluded by the earlier brief. If the offering grants one
  it is part of a real level-N build, so the proposal is to let it in and
  report it as its own source, provided its damage carries a source id the
  meter can attribute.

### What would be delivered

- `dps_bench.py` gains `--levels 1,5,10,...` and `--runs 30`, builds each
  loadout by simulated level-ups, and reports per level: mean, **median**,
  min, max, quartiles, standard deviation, plus the per-weapon table.
- A new `documentation/dps_calcs/dps_report_<date>.md` with one table per
  level and a summary across levels, recording the commit measured at (the
  weapons data has moved between reports before).
- Tests: the level-N builder produces exactly N-1 applied picks, all valid
  for the offering; the summary statistics on a known list.

### Decisions (owner, 2026-09-19)

All five points confirmed, with one directive:

1. **Level = hero level**, meaning about N blessings for level N. The bench
   takes N-1 picks, one per level-up from 2 to N; a level-1 build is the
   starter weapon alone.
2. **Random pick among the three offered cards** — with the directive that
   **blessings giving no combat advantage are filtered out** (the owner's
   example: Magnet, which only widens the pickup radius). The rule used: a
   stat blessing stays only if it moves a stat that changes damage dealt —
   `melee_damage`, `ranged_damage`, `damage_multiplier`,
   `attack_speed_multiplier`, `crit_chance` or `luck` (Fortune adds "a touch
   more crit"). Excluded by that rule: vitality, mending, fleet_foot,
   scholar, gold_rush, iron_skin, magnet, shield_arm, shield_wall, nimble.
   Weapon blessings, weapon grants and Forge cards always pass. The filter
   is applied to the candidate pool *before* the weighted roll, so the three
   cards shown are always three damage cards — not a reroll after the fact.
3. **Checkpoints 1, 5, 10, 15, 20, 25**, thirty builds at each.
4. **Aegis, the empty arena, 16 px standoff, 30 s per sample, spawns frozen,
   no items, potions or meta-upgrades.**
5. **Summons are let in**, reported as their own source. Their damage already
   carries the summon weapon's id (`entities/summon.py:191`), so the meter
   attributes it without a code change.

The old "three random weapons at level 1 plus three random blessings" mode is
retired: the level build replaces it rather than sitting beside it, because
that loadout is one no player holds and two report writers would have to be
kept in step. The earlier reports keep their numbers; their `Regenerate with`
lines no longer run as written.

### Done — the report, and the two bugs it found (2026-09-19)

**Built.**

- [x] `tools/benchmarks/dps_bench.py` rewritten around the level build:
      `combat_relevant` / `excluded_blessings` (the filter), `offer_cards`
      (the real weighted roll over the filtered pool), `build_at_level` (N-1
      random picks), `summarise` (mean, median, quartiles, min, max, stdev)
      and `per_weapon`. `--levels 1,5,10,15,20,25 --runs 30 --seconds 30`
      are the defaults; one RNG per level seeded from `seed:level`, so adding
      a level does not move the others. The report records the commit.
- [x] `tests/devtools/test_dps_bench.py` (13): the excluded set is exactly
      the ten listed above; every weapon blessing and the five damage stat
      blessings pass; level 1 is the sword alone; level 12 is eleven picks all
      accounted for (blessing levels + grants + forges) with nothing
      non-combat on the hero; forty offerings never show a non-combat card;
      the same seed gives the same build; a summon is granted within six
      level-15 builds; the statistics on a known list; one 5 s measurement.
- [x] `documentation/dps_calcs/dps_report_2026-09-19.md`: 180 builds, seed
      `919`, 30 s each, about two minutes end to end.

**Results (Aegis, avg dps over 30 s, 30 builds per level).**

| level | mean | median | p25 | p75 | min | max | sd |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 12.5 | 12.5 | 12.5 | 12.5 | 12.5 | 12.5 | 0.0 |
| 5 | 33.5 | 33.5 | 26.6 | 39.5 | 14.0 | 65.2 | 11.4 |
| 10 | 55.0 | 57.0 | 44.2 | 64.6 | 35.1 | 77.8 | 13.1 |
| 15 | 67.6 | 68.1 | 57.8 | 76.4 | 44.3 | 106.5 | 14.0 |
| 20 | 86.3 | 83.4 | 72.1 | 107.6 | 44.4 | 115.6 | 19.9 |
| 25 | 85.0 | 84.7 | 65.6 | 100.8 | 39.4 | 143.4 | 24.0 |

Reading it: the median roughly doubles from level 5 to 10 (one more weapon,
the first blessing levels), then grows about 20 % per five levels to 20 and
flattens at 25 -- by then most builds have their three weapons and the picks
go into fourth and fifth blessing levels, whose deltas are smaller. The
spread widens with level (sd 11 at 5, 24 at 25): what a level-25 hero deals
depends far more on *which* cards fell than what a level-5 hero deals. Level 1
is thirty copies of the same number by construction (the sword alone); it is
kept as the baseline.

**Bug 1 -- Arcane Storm was a machine gun.** The first pass put level-25
build 11 at **1510 dps**, 15x the median, with the Rod at 99 %. The Arcane
Storm forge turns the Rod into four orbiting motes but keeps the Rod's
`pierce: 0`, so each mote was *spent on its first touch*; `_maintain_orbit`
then replanted it at the hero's feet the next frame, where it touched the
dummy again -- 2 787 hits in ten seconds. Ember Ring never showed this only
because its data carries `pierce: 999`. Fix in `entities/projectile.py`:
`Projectile.on_hit` never spends an orbiter (`is_orbiter`); its `rehit_interval`
is what paces it, as the persistence comment in `update` already said.

**Bug 2 -- the Hammer's blow became a mote.** The same row listed the Hammer
as never landing. Projectiles are pooled; the dead motes' objects were
recycled as the Hammer's blow, but the Rod's `_orbiters` list still held them
(`active` was true again), and its per-frame refresh rewrote the blow's
radius to 6 px and its damage to the mote's 5.4. A 65 px blow centred 21 px
from the dummy missed by 0.8 px. Fix in `combat/weapons/core.py`: the
maintainer keeps only objects that are still *this weapon's* orbiters
(`weapon_id` and `orbit_speed`), not merely active ones -- an orbiter retired
by terrain or the dev menu would have recycled the same way.

Tests: `test_weapons_special.py::OrbitTests` (an orbiter is never spent; a
recycled one is not reclaimed) and `test_forge.py::ArcaneStormOnTheDummyTests`
(the forged Rod beside a Hammer on the arena for 5 s: mote hits within
`motes x (5 / rehit + 1)`, and the Hammer lands). Re-measured, build 11 reads
39.4 dps and is the weakest at its level -- see the next point.

**Caveat found, not fixed: orbit weapons are measured at their floor.** With
the hero 16 px from the dummy, motes circling at 120-140 px only brush it:
Ember Ring averages 0.9 dps at level 25 and Arcane Storm 2 %. That is the
geometry the Daggers need, not a reading of the weapon. Recorded in the
report's caveats; a second standoff for orbit builds would be the fix if the
orbit numbers are ever wanted.

Full suite after the changes: `2596 passed, 9 deselected, 63 warnings, 634 subtests passed in 801.33s (0:13:21)` (one pre-existing failure deselected: `test_imp.py::RigTests::test_the_editor_source_is_not_shipped` looks for an `.aseprite` under the untracked `assets/unused/`, which a fresh worktree does not have).

---

## A second pass with weapon damage +20 % — DONE (owner's go, 2026-09-19: weapons only)

**Requirement (owner).** Simulate another suite with 20 % more damage on the
weapons' numbers, and propose how.

### Proposal

**A bench flag, not a data change.** `--damage-scale 1.2` on
`tools/benchmarks/dps_bench.py`. Before the first run boots it multiplies the
`damage` field of every weapon definition in the process-wide content
singleton (so the starter Sword gets it too) and every Forge override that
sets its own `damage` (Arcane Storm's motes, Whirlwind's sweep, Ballista,
Arcane Lance). `data/weapons/weapons.json` and `forges.json` are not edited;
the game the player runs is unchanged until the owner decides to ship the
number.

**What scales and what does not.** `Weapon._damage` is
`definition["damage"] + bonus["damage"]`, then the multipliers (stat
blessings, class multiplier, crit, Overcharge, Executioner). The flag scales
the first term only:

- scaled: every weapon's base damage, summons included (the Wolf's bite and
  the Totem's bolt are the weapon's `damage`), Forge damage overrides;
- untouched: the flat `+damage` a weapon blessing adds (Sharpened Edge +3..17,
  Heavy Draw +5..28, ...), Iron Arm / Keen Eye (percent, so they scale with
  the base anyway), crit and Overcharge (multiplicative, so they scale too).

Reading the owner's words as "the weapons' numbers" points at this. The
alternative — also scaling the blessing adds — is a one-line change to the
same flag and is the second thing to run if the first pass is judged too
conservative.

**Paired with the baseline.** Same seed `919`, same six levels, same thirty
builds per level. The bench's RNG feeds only the picks and the offering does
not read damage, so every one of the 180 builds is *identical* to the
baseline row and only the numbers differ. That makes the comparison paired:
each build's lift is measured against itself, not against a different random
build.

**Prediction, so the result can be checked.** Level 1 lifts by exactly 20 %
(the Sword alone). Higher levels lift by less, because the flat blessing adds
do not scale: a level-25 Sword at 15 + 17 (Sharpened Edge V) goes from 32 to
35, a 9 % lift, not 20. The expected curve is 20 % at level 1 falling towards
10-14 % at 25. If the measured lift is flat 20 % everywhere, the flag is
scaling more than it should; if it is under 5 % anywhere, something is not
scaling.

**Deliverables.**

- [x] `--damage-scale` on the bench (`scale_weapon_damage`), applied once
      per process before the first run boots, recorded in the report title,
      header and `Regenerate with` line.
- [x] `documentation/dps_calcs/dps_report_2026-09-19_damage120.md`, the same
      layout as the baseline, seed `919`.
- [x] The comparison below.
- [x] `tests/devtools/test_dps_bench.py::DamageScaleTests` (3): every weapon
      and every Forge damage override scaled and nothing else, with the
      singleton restored afterwards; `1.0` is a no-op; the Sword alone
      measures exactly 1.2x the baseline.

### Results — baseline vs weapon damage x1.2, the same 180 builds

| level | baseline mean | +20 % mean | lift | baseline median | +20 % median | lift | paired lift median (p25..p75) | min..max lift |
|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 12.5 | 15.0 | +20.0 % | 12.5 | 15.0 | +20.0 % | +20.0 % (+20.0..+20.0) | +20.0..+20.0 % |
| 5 | 33.5 | 39.9 | +19.2 % | 33.5 | 40.2 | +20.0 % | +19.9 % (+18.3..+20.0) | +14.5..+20.2 % |
| 10 | 55.0 | 65.2 | +18.6 % | 57.0 | 68.4 | +20.1 % | +18.9 % (+17.5..+20.0) | +14.7..+20.2 % |
| 15 | 67.6 | 79.7 | +18.0 % | 68.2 | 79.9 | +17.2 % | +18.2 % (+17.5..+18.4) | +15.2..+20.0 % |
| 20 | 86.3 | 100.5 | +16.4 % | 83.4 | 97.5 | +16.9 % | +16.4 % (+15.4..+17.3) | +13.8..+20.0 % |
| 25 | 85.0 | 98.7 | +16.2 % | 84.8 | 99.0 | +16.8 % | +16.1 % (+14.7..+17.2) | +12.7..+20.0 % |

Every one of the 180 builds is the same in both reports (same seed; the RNG
feeds only the picks), so the last two columns are the honest measure: each
build against itself. Lifts of 20.1-20.2 % are rounding of the reports'
one-decimal figures, not a build lifting by more than the scale.

**Reading it.** The prediction held in shape and was too pessimistic in size.
Level 1 lifts by exactly 20 % (the Sword alone). The lift then falls with
level -- 19.9 % median at 5, 18.9 % at 10, 18.2 % at 15, 16.4 % at 20,
16.1 % at 25 -- because the flat `+damage` blessing adds (Sharpened Edge,
Heavy Draw, ...) do not scale and become a larger share of a build's damage
as it takes more of them. The floor is 12.7 % (a level-25 build heavy on flat
adds), never lower, so nothing failed to scale; the predicted 10-14 % at 25
overestimated how much of a late build's damage the flat adds are.

What a +20 % on the weapons' base damage buys, then, is about +16 % at the
levels where the game is decided, and the full +20 % only in the first
minutes. If the aim is a uniform 20 % more damage at every level, the flat
blessing adds have to move with it -- the one-line variant of the same flag,
not run.

---

## Damage-type blessings +25 % — DONE (owner's go, 2026-09-19)

**Requirement (owner).** Revert the weapon +20 % and test with the values of
the damage-type blessings raised by 25 %. Propose which ones.

**On the revert.** The +20 % was a bench flag (`--damage-scale`), never a
data edit; `data/weapons/weapons.json` did not move. This pass runs with the
flag off, so the weapons are the shipped numbers. The flag and its report
stay as a record.

### Which blessings — the proposal

The catalog has 71 blessings. Sorted by what their number *is*:

**A. The number is damage — proposed set, 15 blessings.**

| blessing | effect | levels I..V |
|---|---|---|
| iron_arm | +melee damage, percent | 8 / 16 / 24 / 32 / 40 % |
| keen_eye | +ranged damage, percent | 8 / 16 / 24 / 32 / 40 % |
| sword_sharpened_edge | +damage | 3 / 6 / 9 / 13 / 17 |
| sword_heavy_blade | +damage (with weight and a slower swing) | 6 / 12 / 18 / 24 / 32 |
| hammer_crushing_blow | +damage | 6 / 12 / 18 / 25 / 33 |
| daggers_sharpened_blades | +damage | 2 / 4 / 6 / 8 / 11 |
| bow_heavy_draw | +damage (with a slower draw) | 5 / 10 / 15 / 21 / 28 |
| bomb_explosive_force | +damage | 7 / 14 / 21 / 29 / 38 |
| ember_ring_ember_heat | +damage | 2 / 4 / 6 / 8 / 10 |
| grave_totem_spectral_bolts | +damage | 3 / 6 / 9 / 12 / 15 |
| spirit_wolf_savage_bite | +damage | 4 / 8 / 12 / 16 / 20 |
| twin_daggers_dual_wield | +damage (post-Forge) | 2 / 4 / 6 / 8 / 10 |
| greatsword_cleaver | +damage (post-Forge, with weight) | 8 / 16 / 24 / 32 / 42 |
| ballista_siege_bolt | +damage (post-Forge, with pierce) | 10 / 20 / 30 / 40 / 55 |
| arcane_lance_impale | +damage (post-Forge, with pierce) | 8 / 16 / 24 / 32 / 42 |

Only the damage effect of each is scaled: Heavy Blade's weight and its
slower swing, Siege Bolt's pierce, Cleaver's weight stay as they are. The
percent pair scales the same way (8 % becomes 10 %, 40 % becomes 50 %).

**B. Conditional damage multipliers — not proposed, offered as a second
pass.** Executioner (below 35 % HP), Weak Point, Overcharge (every 5th
cast), Demolitionist, Split Arrow's split damage, and the six synergies
(Blood in the Water, Linebreaker, Demolition, Marked Prey, Crossfire,
Hunter's Mark). These multiply damage under a condition rather than being a
damage number, "+25 %" is ambiguous for a multiplier (1.6x -> 1.75x, scaling
the bonus, or 2.0x, scaling the whole?), and several never fire on the dummy
(Executioner needs a target under 35 % HP; the dummy is always full). Left
out unless the owner wants them in.

**C. Not damage — excluded.** Crit chance (Lucky Strike, Critical Edge),
attack speed and cooldown (Haste, Quick Hands, Rapid Draw, ...), area,
projectile count, pierce, reach, stun, knockback weight, and the ten
non-combat stat blessings the bench already filters out. They change *how
often* or *how many*, not the damage value.

### How

- `--blessing-damage-scale 1.25` on the bench: multiplies the `levels` list
  of the damage effect of each set-A blessing in the in-memory catalog, once
  per process. `apply_blessing` adds the per-level *delta* between
  `levels[N]` and `levels[N-1]`, so scaling the list scales every level's
  total consistently. `data/weapons/blessings.json` is untouched; an `undo`
  restores the catalog for tests.
- Same seed `919`, weapons at baseline: the 180 builds are again identical
  to the baseline rows, so the comparison is paired.
- Prediction: level 1 lifts by 0 % (no blessings). The lift grows with level
  as the flat adds become a larger share of a build -- the mirror image of the
  weapon pass -- and should land in the low single digits at level 5 and
  around 5-8 % at 25, since the weapon pass showed the adds are roughly a
  fifth of a late build's damage (20 % lift on the base gave 16 %).
- Deliverables: the flag, `dps_report_2026-09-19_blessings125.md`, the
  paired comparison here, and tests (exactly the fifteen effects scaled and
  nothing else; `1.0` a no-op; Sharpened Edge V on the Sword alone adds
  1.25x what it did).

### Built

- [x] `--blessing-damage-scale` (`scale_blessing_damage`, `DAMAGE_EFFECT`,
      `damage_blessings`). Catalog records are frozen dataclasses, so each
      touched blessing is rebuilt with `dataclasses.replace` and swapped into
      `catalog.by_id`; `undo` swaps the originals back.
- [x] `documentation/dps_calcs/dps_report_2026-09-19_blessings125.md`, seed
      `919`, weapons at the shipped numbers.
- [x] `tests/devtools/test_dps_bench.py::BlessingDamageScaleTests` (4): the
      set is exactly the fifteen; only the damage effect of each moves (Heavy
      Blade's weight and swing pinned); `1.0` leaves every effect equal;
      Sharpened Edge V on the Sword adds 17 unscaled and 21.25 scaled.

### Results — baseline vs damage blessings x1.25, the same 180 builds

| level | baseline mean | +25 % blessings mean | lift | baseline median | +25 % blessings median | lift | paired lift median (p25..p75) | min..max lift |
|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | 12.5 | 12.5 | +0.0 % | 12.5 | 12.5 | +0.0 % | +0.0 % (+0.0..+0.0) | +0.0..+0.0 % |
| 5 | 33.5 | 34.0 | +1.6 % | 33.5 | 34.3 | +2.2 % | +1.1 % (+0.0..+2.9) | +0.0..+6.8 % |
| 10 | 55.0 | 56.7 | +3.0 % | 57.0 | 58.1 | +2.1 % | +2.6 % (+1.3..+4.3) | +0.0..+7.5 % |
| 15 | 67.6 | 70.6 | +4.5 % | 68.2 | 71.4 | +4.8 % | +4.2 % (+3.4..+5.6) | +1.7..+8.6 % |
| 20 | 86.3 | 92.2 | +6.8 % | 83.4 | 90.0 | +8.0 % | +7.0 % (+5.6..+7.7) | +2.9..+10.9 % |
| 25 | 85.0 | 91.5 | +7.7 % | 84.8 | 89.8 | +5.9 % | +7.6 % (+5.9..+9.3) | +2.0..+13.5 % |

**Reading it.** The prediction held: 0 % at level 1 (no blessings), rising
to a 7.6 % median lift at 25, with the widest build-to-build range there
(+2.0 % for a build that took few damage cards, +13.5 % for one that stacked
them). Set against the weapon pass, the two what-ifs are mirror images:

| | level 5 | level 10 | level 15 | level 20 | level 25 |
|---|---:|---:|---:|---:|---:|
| weapons' base damage x1.2 | +19.9 % | +18.9 % | +18.2 % | +16.4 % | +16.1 % |
| damage blessings x1.25 | +1.1 % | +2.6 % | +4.2 % | +7.0 % | +7.6 % |

Raising the blessings moves the late game and leaves the early game alone;
raising the weapons moves everything, most of all the first minutes. A
+25 % on the blessings is worth about half of what the earlier weapon pass
gave at level 25 and almost nothing before level 10 -- which is the shape to
want if the aim is a steeper power curve rather than a higher one. Neither
is shipped; both are flags on the bench.
