# Combat balance journal

Design + checklist log for combat‑model and tuning changes. Same role for
combat that `assets_journal.md` plays for art. Newest work first.

Cross‑refs: `BUG_JOURNAL.md` (defects), `../documentation/COMBAT_CALCS.md` (the
authoritative damage walkthrough).

---

## CB‑1 · Rework incoming damage to per‑hit "bites"

**Status:** **DONE** 2026-08-27 (all 8 decisions taken as recommended). Resolves
`BUG_JOURNAL.md` #1. Not committed. Verification at the end of this entry.

### Why

`BUG_JOURNAL.md` #1: `Player.take_damage` subtracts **flat armor per call**, but
contact and hazard damage call it **every frame** with a `dt`‑sized slice
(`dps · dt`). Any `armor ≥ slice` — i.e. always — zeroes the slice, so a hero
with any armor (Aegis has `armor: 4`) is immune to body contact, hazard pools,
and any per‑frame continuous damage. The recent `FPS 60 → 120` change makes the
slice half as big and the bug strictly worse; the rework removes the frame‑rate
dependency entirely because bites are timed in seconds, not frames.

### Design (confirmed)

- **`Player.take_damage` is unchanged.** It already does
  `dealt = max(0, amount · bulwark − armor)` — "armor subtracts a fixed amount
  from the final hit." The whole rework is at the *call sites*.
- **Discrete paths unchanged.** Hostile projectiles and explosions already call
  `take_damage` once per hit; armor already applies correctly. No change, no
  data change.
- **Contact and hazard become timed bites.** Instead of `take_damage(rate · dt)`
  every frame, deal `take_damage(rate · T)` once every `T` seconds of exposure,
  where `T` is that attack's tick interval.
  - `rate · T` (chunk) keeps pre‑armor DPS equal to `rate` (`rate·T / T = rate`).
  - Armor now bites a meaningful chunk once per `T`, not a sliver 120×/s.
- **`T` is per‑attack**, defaulting to a global `config.INCOMING_TICK_INTERVAL`:
  - hazards: `Hazard.tick_interval` (from `hazard_tick` in data, else the default)
  - contact: `Enemy.contact_interval` / `Boss.contact_interval` (from
    `contact_interval` in data, else the default)
- **Data compensation:** `contact_damage` and hazard `dps` each **+5** so the
  post‑armor result lands near the original intent.

### Formulas

```
discrete hit (projectile / explosion):
    dealt = max(0, hit_damage · bulwark − armor)                 # unchanged

contact bite (once per T_contact per enemy):
    T_contact = enemy.contact_interval or config.INCOMING_TICK_INTERVAL
    pre_armor = enemy.contact_damage · T_contact
    dealt     = max(0, pre_armor · bulwark − armor)

hazard bite (once per T_hazard per hazard):
    T_hazard  = hazard.tick_interval or config.INCOMING_TICK_INTERVAL
    pre_armor = hazard.dps · T_hazard
    dealt     = max(0, pre_armor · bulwark − armor)

effective DPS (armored hero) = dealt / T
```

**Floor condition** — a bite must beat armor or that attack goes back to doing
nothing vs an armored hero (re‑introducing the bug for that one attack):

```
rate · T · bulwark  >  armor        →     T  >  armor / (rate · bulwark)
```

Rule of thumb: keep `rate · T ≥ ~20` (a healthy multiple of the ~4–12 armor
range in this game).

**"Same total damage, faster"** — scale `rate → k·rate`, `duration → duration/k`,
`T → T/k`. Total raw (`rate·duration`), bite size (`rate·T`) and bite count
(`duration/T`) are all unchanged; the same bites just arrive `k×` faster.
Effective DPS is `k×`, effective total is identical for every hero.
Example (k = 2 off the warlock pool): `dps 23 → 46`, `duration 3.5 → 1.75`,
`tick 0.5 → 0.25` — Aegis takes the same ~52 total, in half the time.

---

## Checklist

### A · Config
- [x] `game/config.py`: add `INCOMING_TICK_INTERVAL: float = 0.5` — the
      **default** bite spacing for contact and hazard; individual attacks may
      override it.

### B · `Player.take_damage` — confirm, don't change
- [x] Verify `entities/player.py — Player.take_damage` stays exactly
      `dealt = max(0.0, amount * incoming_damage_multiplier() - stats["armor"])`.
- [x] Confirm hostile‑projectile (`_resolve_hostile_hits`) and explosion
      (`_explosion`) paths are untouched — they are already per‑hit.

### C · Contact damage → timed bites
- [x] `entities/enemy.py`: add `self.contact_cd = 0.0` in `Enemy.__init__`;
      decrement each frame in `Enemy.update` (`self.contact_cd = max(0.0,
      self.contact_cd - dt)`).
- [x] `entities/boss.py`: add `self.contact_cd = 0.0` in `Boss.__init__`;
      decrement each frame in `Boss.update` (the boss is in the contact list).
- [x] `game/states/playing_state.py — _resolve_enemy_contact`: replace the
      per‑frame `take_damage(enemy.contact_damage * dt)` with: for each
      overlapping target whose `contact_cd <= 0`, deal
      `take_damage(enemy.contact_damage * T_contact)`, then set
      `enemy.contact_cd = T_contact`; publish `PLAYER_DAMAGED` when `taken > 0`.
- [x] Decide the first‑bite behaviour: `contact_cd` starts at 0 so first overlap
      bites immediately (recommended), vs seeding it to `T` so the first bite is
      delayed.

### D · Hazard damage → timed bites
- [x] `entities/hazard.py`: add `_tick_accum` to `__slots__`, init `0.0`.
- [x] `entities/hazard.py`: add
      `due_damage(self, dt) -> float` — accumulates `dt` into `_tick_accum` and,
      each time it reaches `self.tick_interval`, subtracts one interval and
      returns `self.dps * self.tick_interval`; else returns `0.0`. Use a
      `while` (not `if`) so a lag frame can flush multiple ticks.
- [x] `game/states/playing_state.py — _update_hazards`: while the player is
      inside a live hazard, `bite = hz.due_damage(dt)`; if `bite`, call
      `take_damage(bite)` and publish `PLAYER_DAMAGED` on `taken > 0`.
- [x] Reset `hz._tick_accum = 0.0` on the frames the player is **not** inside
      (decision: reset‑on‑exit vs carry partial exposure).

### E · Per‑attack tick interval (hazards)
- [x] `game/config.py`: `INCOMING_TICK_INTERVAL` is the fallback only, not the
      sole value (covered in A — restated here for the hazard path).
- [x] `entities/hazard.py`: `Hazard.__init__` gains
      `tick_interval: float = None`; store
      `self.tick_interval = tick_interval or config.INCOMING_TICK_INTERVAL`
      (add `tick_interval` to `__slots__`). `due_damage` reads `self.tick_interval`.
- [x] `game/states/playing_state.py — _spawn_hazard`: accept and forward an
      optional `tick_interval`.
- [x] `entities/enemy_ai.py — fsm_warlock`: pass
      `c.get("hazard_tick")` into `ctx.spawn_hazard(...)` (None → default).
- [x] `entities/enemy_ai.py — EnemyContext.spawn_hazard`: widen the default
      lambda signature to accept the optional `tick_interval` kwarg.
- [x] `data/enemies.json`: `hazard_tick` is optional on `warlock` (omit for now
      = use the default) and available to any future hazard‑spawning enemy.

### F · Per‑enemy contact interval (optional but plumbed now)
- [x] `entities/enemy.py`: `Enemy.__init__` reads
      `self.contact_interval = float(definition.get("contact_interval",
      config.INCOMING_TICK_INTERVAL))`.
- [x] `entities/boss.py`: `Boss.__init__` reads
      `self.contact_interval = float(definition.get("contact_interval",
      config.INCOMING_TICK_INTERVAL))`.
- [x] `game/states/playing_state.py — _resolve_enemy_contact`: use
      `target.contact_interval` as `T_contact` (falls back to the config default
      via the constructor).
- [x] `data/enemies.json` / `data/bosses.json`: `contact_interval` is an
      optional per‑enemy field — omit it and every enemy uses the default; set
      it to make a fast jabber (`0.25`) or a slow bruiser (`0.9`) feel distinct.
- [x] Decide: ship with the field plumbed but **no data using it yet** (every
      enemy on the default), or tune a couple of enemies in the same pass.

### G · Data — +5 to contact / continuous values
- [x] `data/enemies.json` `contact_damage`:
      chaser 8→13 · fast 6→11 · tank 16→21 · swarm 4→9 · ranged 5→10 ·
      exploder 6→11 · shielded 10→15 · elite 20→25 · summoner 8→13 ·
      brute 24→29 · charger 9→14 · teleporter 7→12 · warlock 6→11.
- [x] `data/enemies.json` `warlock.hazard_dps`: 18 → 23.
- [x] `data/bosses.json` `the_first_hunger.contact_damage`: 26 → 31.
- [x] Decide (with decision 3): also `charger.charge_damage` 26→31 and
      `teleporter.blink_damage` 15→20, or leave the transient attack values.
- [x] **Do NOT touch** `shoot_damage`, `explode_damage`, `slam_damage` — those
      are discrete hits and armor already works on them.

### H · Tests
- [x] New `tests/test_incoming_damage.py` (or extend
      `tests/test_movement.py::DamageTests`):
  - [x] one contact bite vs armor: `tank` (21), `T` 0.5, Aegis moving
        (no Bulwark), armor 4 → the hero loses
        `max(0, 21·0.5 − 4) = 6.5` per interval, **not 0** — regression for
        `BUG_JOURNAL` #1.
  - [x] Aegis (armor 4) standing on a `tank` for 3 s loses a non‑zero,
        armor‑reduced amount; Kestrel (armor 0) on the same tank loses ~`21·3`.
  - [x] Kestrel in the 23‑dps hazard for 3.5 s loses ≈ `7 · (23·0.5)` ≈ 80
        (was ≈ 63 with dps 18).
  - [x] a single enemy bites at most once per its `contact_interval`, not every
        frame; two enemies bite on independent timers.
  - [x] hazard `tick_interval` override: a hazard built with `tick_interval=0.25`
        fires twice as many bites of half the size vs the default over the same
        exposure.
  - [x] the "same total, faster" transform: `(dps 46, dur 1.75, tick 0.25)`
        deals the same total to a given hero as `(dps 23, dur 3.5, tick 0.5)`.
  - [x] `Player.take_damage` unit tests unchanged and still green.
- [x] Run `test_smoke` / `longrun` — the hero now takes real contact damage;
      confirm it still reaches the boss (or set `invulnerable` / adjust seeding
      in those specific tests if it now dies early).

### I · Docs
- [x] `../documentation/COMBAT_CALCS.md` §2a (sources table + snippets), §2b
      (note the per‑hit cadence), and §5b/§5c (worked examples) — rewrite for
      the bite model; add a short "per‑attack `tick_interval` / `contact_interval`"
      subsection with the floor condition `T > armor / (rate·bulwark)`.
- [x] `BUG_JOURNAL.md` #1 → **Resolved** stamp pointing at CB‑1.
- [x] `journal.md` — one‑paragraph "Combat — incoming damage reworked to
      per‑hit bites" entry pointing here.
- [x] This file (CB‑1) → mark the checklist items done + a short verification
      note (`unittest` count, a windowed sanity run).

---

## Decisions — all taken as recommended

| # | Question | Taken |
|---|----------|-------|
| 1 | Global default `INCOMING_TICK_INTERVAL` value | `0.5 s` |
| 2 | Expose per‑attack overrides as the tuning lever? | Yes — default 0.5, override per hazard (`hazard_tick`) / per enemy (`contact_interval`) |
| 3 | Bump `charge_damage` / `blink_damage` +5 and reset `contact_cd = 0` on FSM `attack` entry? | Yes to both (`enemy_ai._fsm_enter`) |
| 4 | Flat +5 to the data rate, retune later? | Yes — flat +5 |
| 5 | Hazard `_tick_accum` on player exit | Reset (`Hazard.reset_ticks()` from `_update_hazards`) |
| 6 | First contact bite immediate or delayed | Immediate (`contact_cd` starts 0) |
| 7 | `contact_interval` — plumb only, or tune enemies now | Plumbed; no enemy data uses it yet (all on the 0.5 default) |
| 8 | Boss gets `contact_cd` + `contact_interval` + `contact_damage` +5 | Yes to all three (26 → 31) |

## Verification (CB‑1)

- **Suite:** `python -m unittest discover -s tests` → **312 pass** (298 → 312).
  New `tests/test_incoming_damage.py` (14): `Hazard.due_damage` accumulation +
  custom / big‑frame / reset behaviour; `Player.take_damage` unchanged; armored
  Aegis now takes a contact bite (`21·0.5 − 4 = 6.5`, regression for BUG #1);
  ≤ one bite per interval then a second; two enemies bite on independent timers;
  `_fsm_enter("attack")` clears `contact_cd`; hazard total over a pool life ≈
  `dps·duration`; the "same total, faster" transform; `_spawn_hazard` forwards
  `tick_interval`; stepping out of a pool banks nothing.
- **`test_fsm_enemies.py`** stub widened for the 5‑arg `spawn_hazard`; still green.
- **Headless sanity:** Aegis (armor 4), weapons off, 5 chasers sat on the hero
  for 3 s → **160 → 133** HP (pre‑CB‑1: 160 → 160, immune).
- **`longrun.py`** end‑to‑end still reaches `VictoryState`; persistence / meta /
  equipment intact.
- **Data (+5):** `contact_damage` chaser 13 · fast 11 · tank 21 · swarm 9 ·
  ranged 10 · exploder 11 · shielded 15 · elite 25 · summoner 13 · brute 29 ·
  charger 14 · teleporter 12 · warlock 11; `charge_damage` 31; `blink_damage`
  20; `warlock.hazard_dps` 23; boss `contact_damage` 31. `shoot_damage` /
  `explode_damage` / `slam_damage` untouched.
- **Not committed.**
