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

A new `training_dummy` entry: no contact damage, no experience, `speed: 0`, its
own `tags: ["dummy"]`, and a new `invulnerable: true` field.

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

### 4. The dev menu option

A `dummy` row in `_ROOT_ROWS` labelled "Training dummy", toggling on:

- one `training_dummy` spawned through `spawn.spawn_enemy(..., owner="dev")` at
  a fixed offset from the hero,
- the meter armed and reset,
- the readout pushed to the debug overlay through `set_metric`.

Toggling off despawns the dummy and disarms the meter.

---

## Open questions for the owner

1. **Rolling window length.** 5 s reacts fast but swings wildly with a slow
   weapon like the Hammer; 10 s is steadier. Proposing **10 s** with the
   cumulative figure shown beside it.
2. **Does the dummy fight back?** Proposing **no** — `contact_damage: 0`, so a
   measurement is never cut short by the hero dying. Say if you want a variant
   that hits back for testing survivability.
3. **One dummy or several?** Proposing **one**, because several would make
   area weapons (Bomb, Hammer, Ember Ring) read much higher than single-target
   ones and the number would stop being comparable. A "spawn three" option
   would measure cleave separately, if that is wanted.
4. **Should the dummy take knockback?** Proposing **no** (very high `weight`),
   so it stays in place and the hero keeps hitting it. Otherwise Hammer and
   Bomb push it out of range and under-report.
5. **Where does the readout live?** Proposing the **debug overlay (F1)**, which
   needs no new UI. A dedicated panel would look better but is more work.

---

## Todo — not started, pending the answers above

- [ ] `data/enemies.json`: a `training_dummy` entry — `hp` nominal,
      `invulnerable: true`, `speed: 0`, `contact_damage: 0`,
      `experience_reward: 0`, a high `weight`, `behavior: "dummy"`,
      `tags: ["dummy"]`. No code-side defaults for any of it.
- [ ] `entities/enemy.py`: honour `invulnerable` in `take_damage` — still
      compute and return the dealt amount, skip the `hp` subtraction, leave
      armour / shield / hit-flash behaviour untouched.
- [ ] `entities/ai/behaviors/simple.py`: register a `dummy` behaviour that does
      nothing, so the dummy neither steers nor attacks.
- [ ] `game/states/playing/dps_meter.py` (new): `DpsMeter` — arm / disarm /
      reset, `add(amount, source)`, cumulative total and elapsed, rolling
      window, per-source breakdown.
- [ ] Tap the damage sinks: `combat.py:77` (source `proj.weapon_id`),
      `effects.py:268` and `state.py:585` — both of which need a source id
      threaded through to attribute explosions and damage-over-time. Exclude
      `npcs.py:168` so village lancers never count toward the hero's DPS.
- [ ] `game/states/dev_menu_state.py`: a `dummy` row in `_ROOT_ROWS` and
      `_LABELS`, and a handler that spawns the dummy through
      `spawn.spawn_enemy(..., owner="dev")`, arms the meter, and reports through
      `_status` when the master refuses.
- [ ] `PlayingState._debug_metrics`: push the meter's numbers through
      `set_metric` while it is armed.
- [ ] Tests, `unit` tier where possible:
      - `DpsMeter` arithmetic on a fake clock — totals, elapsed, the rolling
        window, per-source split, reset;
      - `take_damage` on an invulnerable enemy returns the dealt amount and
        leaves `hp` alone, and still respects armour and shields;
      - the `dummy` behaviour moves and attacks nothing;
      - `integration` tier: the dev-menu row spawns exactly one dummy through
        the spawn master and arms the meter.
- [ ] Sanity-check the meter against a hand-computed figure: one weapon, no
      blessings, known cooldown and damage — the measured DPS must match
      `damage / cooldown` within the window's tolerance. This is what proves
      the meter rather than the meter proving itself.
- [ ] Screenshot: the dummy standing in a run with the overlay showing the
      per-source breakdown.
