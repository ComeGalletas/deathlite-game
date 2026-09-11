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

## Todo — ready to build (owner's go on all five, 2026-09-11)

**The damage paths first**, because the meter is only as honest as its sources.

- [ ] `entities/enemy.py` `take_damage(amount, armor=0.0)` grows a `source`
      argument (default `None` = unattributed). It changes nothing for existing
      callers and is what every tap below hangs off.
- [ ] `game/states/playing/effects.py:268`: explosions pass the exploding
      weapon's id. The Bomb's blast currently attributes to nothing, so this
      also fixes `killed_by` for an explosion kill.
- [ ] `game/states/playing/state.py:585` `_report_dot`: damage over time passes
      the weapon that applied the effect.
- [ ] `game/states/playing/combat.py:77`: pass the `proj.weapon_id` it already
      holds.
- [ ] `game/states/playing/npcs.py:168`: village lancers pass `"villager"`, a
      source the meter drops — villagers are never part of the number.

**Then the dummy.**

- [ ] `data/enemies.json`: a `training_dummy` entry copied from `chaser` (same
      `sprite`, `radius`, `color`) then made inert — `invulnerable: true`,
      `speed: 0`, `aggro_range: 0`, `contact_damage: 0`,
      `contact_damage_enabled: false`, `experience_reward: 0`,
      `behavior: "dummy"`, `tags: ["dummy"]`. No code-side defaults for any of
      it.
- [ ] `entities/enemy.py`: honour `invulnerable` — still compute and **return**
      the dealt amount (that return is what the meter counts), skip the `hp`
      subtraction, leave armour, shields and the hit flash exactly as they are
      so the measurement reflects a real hit.
- [ ] Knockback: the dummy ignores it. `apply_knockback` is a no-op for an
      invulnerable enemy, which is simpler and more honest than a huge `weight`
      that merely makes the push small.
- [ ] `entities/ai/behaviors/simple.py`: register a `dummy` behaviour that does
      nothing — no steering, no attack, no aggro. None of the twelve existing
      behaviours is inert, and `speed: 0` alone still runs an attack beat.

**Then the meter.**

- [ ] `game/states/playing/dps_meter.py` (new module — this does not go into the
      1,034-line `state.py`): `DpsMeter` holding the metered enemy, with
      `arm(enemy)` / `disarm()` / `reset()`, `record(amount, source)`, elapsed
      time, a cumulative total, a **10 s** rolling window, and a per-source
      breakdown keyed by weapon id. Sources named `"villager"` are dropped.
- [ ] Only damage landing on the armed enemy is recorded, so a stray hit on any
      other enemy can never inflate the reading.

**Then the wiring.**

- [ ] `game/states/dev_menu_state.py`: a `dummy` row in `_ROOT_ROWS` and
      `_LABELS` ("Training dummy"), toggling on — spawn one `training_dummy`
      through `spawn.spawn_enemy(..., owner="dev")` at a fixed offset, arm the
      meter on it, and report through `_status` when the master refuses.
      Toggling off despawns it and disarms.
- [ ] `PlayingState._debug_metrics`: push the meter's numbers through
      `set_metric` while armed, so the readout rides the existing F1 overlay.

**Tests.**

- [ ] `unit`: `DpsMeter` arithmetic on a fake clock — total, elapsed, the 10 s
      window rolling off old samples, the per-source split, `"villager"`
      dropped, reset.
- [ ] `unit`: `take_damage` on an invulnerable enemy returns the dealt amount
      and leaves `hp` alone, still respecting armour and shields; and knockback
      does not move it.
- [ ] `unit`: the `dummy` behaviour moves nothing and attacks nothing.
- [ ] `unit`: an explosion and a damage-over-time tick both arrive at
      `take_damage` carrying their weapon id.
- [ ] `integration`: the dev-menu row spawns exactly one dummy through the
      spawn master and arms the meter on it.
- [ ] **The check that proves the meter rather than the meter proving itself**:
      one weapon, no blessings, known `damage` and `cooldown` from the data —
      the measured DPS must match `damage / cooldown` within the window's
      tolerance.

**Close-out.**

- [ ] Screenshot: the dummy in a run with the F1 overlay showing the per-source
      breakdown.
- [ ] Record the evidence here and close the entry.
