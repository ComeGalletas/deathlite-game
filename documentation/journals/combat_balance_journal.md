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
---

## CB-2 - Every weapon has a reach ring - weapon categories

**Status:** in progress. All 6 decisions resolved with the user (2026-08-29).
Checklist **A**-**F** done (data, `combat/weapons.py`, `entities/summon.py`,
spawn plumbing, dev overlay, tests -- suite 597 -> 618, green). Only **G**
(balance playtest, needs a human) is left. Design + checklist below.

### Why

Weapons fire on cooldown regardless of the battlefield -- `soul_scythe` swings
its reaping *arc* into empty grass when the nearest foe is 400 px away; Kestrel
plinks a lone straggler across the map. Every weapon should need a target
**inside a reach ring** to trigger; with nothing in range the hero (and the
summons) drop to idle. Formalising the rule needs a weapon **category** so it
branches cleanly instead of abusing `tags`.

### Weapon categories

New required `category` field in `data/weapons.json`:

| category | weapons | behaviour |
|--|--|--|
| `projectile` | arcane_bolt, frost_shards, thunder_orb | trigger on an enemy in reach; then fire toward the nearest enemy **within reach** and the shot flies on past the ring as today |
| `melee` | soul_scythe | trigger on an enemy in reach; reach == the cone's own tip distance (below) |
| `summon` | grave_totem, spirit_wolf | weapon still spawns on cooldown; the *summon* has its own reach ring and idles when it is empty (the wolf's `idle` strip -- WA3 -- exists for this) |
| `orbit` | ember_ring | its own category (aura spells are separate); reach behaviour -- decision 6 |
| `spell` | *(none yet)* | reserved for aura-type spells; unused by any current weapon |

`Weapon.category` reads the field; a fallback infers it from `special_effect`
(`cone`->melee, `summon`->summon, `orbit`->orbit, else projectile) for defs that
omit it.

### Reach

`Weapon._reach(area_multiplier)`:

* **melee** -> `self._area(area_multiplier)` exactly -- the distance from the
  hero to the tip of the cone in the current functionality (decision 1). No
  `reach` field on melee defs; it tracks the cone.
* **everything else** -> `(float(def["reach"]) + self.bonus["area"]) *
  area_multiplier` -- an explicit, required `reach` field.

Reach scales with `area_multiplier` **and** `bonus["area"]` for every category
(decision 2), so any blessing / affix that grows weapon area also widens the
reach ring (and for melee the ring and the cone grow together).

### Trigger + aim (projectile / melee)

`_fire`: `reach_eff = self._reach(ctx.area_multiplier)`;
`in_reach = [e for e in ctx.enemies if (e.pos - ctx.origin).length_squared()
<= reach_eff ** 2]`. If `in_reach` is empty -> `return False` (no fire; the
existing `self._cd = 0.1` path polls ~10x/s and swings the instant a foe steps
in). Otherwise aim with `targeting.aim_direction(mode, origin, in_reach,
fallback)` and fire unchanged. Decision 4: the trigger is a cheap "anything in
the ring" test, not a global nearest search; the aim then picks the nearest
*within* the ring. **Consequence:** gated weapons no longer fire into open space
-- `aim_direction`'s `fallback_dir` branch is now effectively dead for them.

### Summons (leash ring)

The summon weapon passes its reach to `Summon.reset(reach=...)` -- new
`summon_reach` field on the def, defaulting to `summon_attack_range` when omitted
(so `grave_totem`'s 360 keeps working). In `entities/summon.py`:

* Target selection filters to enemies within `reach` of **`ctx.player_pos`**
  (the totem uses its own `pos`, which equals the anchor). No in-ring enemy ->
  `vel = 0`, no bite, `_anim_name()` returns `idle` (the SLEEP strip).
* Wolf leash: if `(self.pos - ctx.player_pos).length() > reach`, steer back
  toward `player_pos` instead of the target, so a fleeing enemy cannot drag it
  out of the ring.
* `_BITE_ANIM_S` / `_side` logic unchanged; `idle` slots in ahead of
  `run_{side}` when there is no leashed target.

### Hero attack animation (decision 5)

**No `_phase_combat` change.** The attack anim already keys on `fired and weapon
is main`, and every hero's main weapon now gates on reach:

* **Aegis** -- main `soul_scythe` (melee): `attack` plays only while an enemy is
  in reach; otherwise `walk` / `idle`.
* **Kestrel** -- main `frost_shards` (projectile): `attack` plays when the shards
  fire, which now also needs a foe in reach.
* **Nihil** -- main `arcane_bolt` (projectile): same.

The idle<->attack switch is automatic for all three; the anim tracks the
character's own main weapon by category, exactly as intended.

### Decisions (resolved)

1. **melee reach = cone tip distance** = `_area(area_mult)`. Confirmed.
2. **reach scales with area** (`area_multiplier` + `bonus["area"]`), every
   category, so weapon-area blessings extend it. Confirmed.
3. **`orbit` is its own category** (ember_ring); aura spells will be a separate
   `spell` category. Confirmed.
4. **all weapons gate on reach**; the trigger is a proximity test (not a global
   nearest search); projectiles then fire toward the nearest in-ring enemy and
   the shot travels on; summons get a leash ring and idle when it is empty.
   Confirmed.
5. **attack anim stays main-weapon-linked**; no code change, it now idles
   correctly per hero because every category gates on reach. Confirmed.
6. **`orbit` gates too.** Confirmed. `_maintain_orbit` keeps the orbiters alive
   only while an enemy is within `reach`; with the ring empty they fade (the
   hero "lowers" the Ember Ring).

### Checklist

#### A - Data (`data/weapons.json`) -- DONE (2026-08-29)
- [x] `category` on all 7 defs per the table (`projectile` x3, `melee` x1,
      `summon` x2, `orbit` x1).
- [x] `reach` (world px) on every non-melee def -- `arcane_bolt` / `frost_shards`
      `400`, `thunder_orb` `440` (slow orb, longer lead), `ember_ring` `reach`
      `140` (~1.5x its `orbit_radius 96`), `summon_reach` `360` on `grave_totem`
      (== its `summon_attack_range`, so no behaviour change) and `280` on
      `spirit_wolf`. `soul_scythe` gets **no** `reach` (tracks `area 74`).
- JSON re-validates; full suite still green (597 tests). Nothing else reads
  `category` / `reach` yet -- checklist B wires it in.

#### B - `combat/weapons.py` -- DONE (2026-08-29)
- [x] `Weapon.category` property -- reads the field, `_CATEGORY_BY_SPECIAL`
      maps a legacy def (`cone`->melee, `summon`->summon, `orbit`->orbit, else
      projectile).
- [x] `Weapon._reach(area_multiplier)` -- `_area(mult)` for melee; else
      `(def["reach"] + bonus["area"]) * mult`. A non-melee def with **no**
      `reach` key returns `inf` (fires exactly as pre-CB-2) -- this is the case
      for the two `summon` weapons, whose own `_fire` is never reached anyway.
- [x] `_within_reach(enemies, origin, reach)` staticmethod -- squared scan,
      returns the in-ring list.
- [x] `_fire`: builds `in_reach`; empty -> `return False` (caller polls via
      `_cd = 0.1`); else `aim_direction(mode, origin, in_reach, fallback)` so
      the shot aims at the nearest foe *within* the ring and flies on past it.
- [x] `_maintain_orbit` (decision 6): `desired = 0` when the ring is empty, so
      the existing trim loop drops the orbiters; they re-form evenly spaced the
      moment a target returns.
- [x] `_maintain_summons`: computes
      `reach = def.get("summon_reach", def.get("summon_attack_range", 320)) *
      ctx.area_multiplier` and passes it to `ctx.spawn_summon(...)`.
- Pulled forward from C (inseparable from passing `reach`): `Summon.__slots__`
  gained `reach`, `Summon.reset(..., reach=float("inf"))` stores it. **No**
  behaviour change on the summon side yet -- the wolf leash / `idle` / in-ring
  target filter are still C.
- Existing tests adjusted for the gate (not new F coverage): `test_weapons_special.py`
  -- the 3 `OrbitTests` and the `ConeTests` scythe case now keep an enemy inside
  the ring. Full suite green (597).

#### C - `entities/summon.py` -- DONE (2026-08-29)
- [x] `__slots__` += `reach`; `reset(..., reach=float("inf"))` stores it.
      *(done with B -- inseparable from `_maintain_summons` passing it.)*
- [x] `_acquire_target(ctx)`: nearest enemy that also sits inside the leash
      ring. Ring centre is `ctx.player_pos` for the wolf, `self.pos` for the
      planted totem (it defends its own spot even after the hero walks off).
      `reach == inf` -> no ring, every enemy a candidate (pre-CB-2 behaviour).
      No in-ring enemy -> `target is None` -> `vel = 0`.
- [x] Wolf leash in `_chase`: `(self.pos - ctx.player_pos).length() > reach` ->
      abandon the chase, `_steer` home, so a fleeing enemy can't drag the wolf
      across the map. `_steer` factored out (shared by chase + leash-home).
- [x] `_anim_name(target)`: returns `idle` (the SLEEP strip) only when
      `target is None` **and** the wolf is standing still -- never between bites
      (target still present there) and never while running home (`vel != 0`).

#### D - Spawn plumbing -- DONE (2026-08-29, no code change needed)
- [x] `PlayingState._spawn_summon` already forwards `**kw` -> `Summon.reset`, so
      the `reach` from `_maintain_summons` flows through untouched.
- [x] Direct `Summon.reset(...)` calls in `tests/combat/test_summons.py` omit
      `reach` -> it defaults to `inf` (no leash), so the existing basic-fire /
      basic-chase / expiry tests are unaffected. Dedicated leash + `idle`
      coverage is checklist F.

#### E - Dev overlay -- DONE (2026-08-29)
- [x] `WorldRenderer.collider_overlay` (F7 / dev menu "Collision shapes") now
      also draws the CB-2 reach rings in a new amber `config.COLOR_DEBUG_REACH`:
      one ring per equipped weapon at `player.pos` (`w._reach(area_multiplier)`,
      `inf` skipped -- so the two summon weapons draw nothing); one leash ring
      per live summon -- hero-centred for the wolf, planted-spot-centred for the
      totem, matching `Summon._acquire_target`. Rings honour camera zoom via the
      existing `ring()` helper. Verified headless: hero moved away from a planted
      totem keeps the weapon ring on the hero and the totem ring on the totem.

#### F - Tests -- DONE (2026-08-29)
New module **`tests/combat/test_weapons_reach.py`** (17 cases) + 4 cases added to
**`tests/combat/test_summons.py::SummonBehaviourTests`**. Also (in B) the 4
existing `test_weapons_special.py` cases were adjusted to keep an enemy in the
ring. Full suite 597 -> 618, green.
- [x] every `weapons.json` def has a `category` in the allowed set;
      `Weapon.category` matches the expected value per weapon; the
      `special_effect` fallback is correct once the field is removed.
- [x] `_reach`: `soul_scythe` == `_area(mult)` and grows with `area_multiplier`
      + `bonus["area"]`; a projectile == `(reach + bonus["area"]) * mult`; a
      non-melee def with no `reach` field == `inf`; both `summon` weapons ==
      `inf` (their `_fire` never gates).
- [x] melee gate: `soul_scythe` fires at `reach - 1`, not at `reach + 1`;
      `self._cd` stays <= 0.11 (polling) while gated.
- [x] projectile gate: an out-of-ring foe never triggers `frost_shards`; with
      `targeting_mode` forced to `random`, 50 fires only ever aim at the
      in-ring foe (proves `_fire` filters the candidate list, not just the
      trigger).
- [x] area scaling: a foe just outside `reach` triggers once
      `ctx.area_multiplier = 1.5`; and again via `bonus["area"]`.
- [x] orbit gate (decision 6): no orbiters while the ring is empty; they form
      when a foe enters the 140 ring and drop when it leaves.
- [x] summon leash: wolf whose only foe is outside `reach` of `player_pos` ->
      never moves, `vel == 0`, no bite, `_acquire_target` is `None`,
      `_anim_name(None) == "idle"`; foe inside -> chases + bites; wolf dragged
      past `reach` -> steers home (`vel.x < 0`, `run_left`, not `idle`); totem
      keeps zapping a foe by its base even with the hero 5000 px away.
- [x] regression: `arcane_bolt` cadence (fire / cool / fire ~1.1s) and dead-on
      aim unchanged; `frost_shards` still fans 3, all toward the target.

#### G - Balance / playtest
- [ ] The whole game is now "no target -> no attack". Verify it still feels
      active (swarms mean reach is hit almost always) and that a lone far enemy
      correctly makes the hero idle.
- [ ] Tune the projectile `reach` values -- too short = dead time between packs,
      too long = never idles. Start ~400, adjust in a playtest.
- [ ] Melee: `soul_scythe` reaches exactly its cone; confirm it does not feel
      shorter than the visible arc. `cooldown 1.0` may want a small cut to offset
      gated downtime.
- [ ] Note whether a `+reach` blessing / affix is worth adding (area blessings
      already do it indirectly via decision 2).

### Touch list
`data/weapons.json`, `combat/weapons.py` (`category`, `_reach`, `_within_reach`,
`_fire` gate, `_maintain_summons` reach), `entities/summon.py` (`reach`, leash,
`idle`), `game/states/playing/rendering.py` (`collider_overlay` rings),
`tests/combat/test_weapons.py`, `tests/combat/test_summons.py`, this journal.
**No** new deps. **Nothing** committed.

---

## CB-3 - Unit bumping + weight-based knockback

**Status:** COMPLETE (2026-08-29). All of A-H done. Unit bumping + weight-based
knockback are live: every mobile body carries a `weight`, overlapping bodies
shove each other, and weapon hits push their target -- bumps and hits share the
one `knock_split` formula. `_PEN_CAP_FRAC` tuned to 0.6 in the H pass; a hand
playtest for feel is still worthwhile but nothing blocks. Suite 620 -> 647.
**Nothing committed.**

### Why

Today enemies pass through each other and through the hero -- the only "contact"
is `enemy_contact` dealing a bite. Crowds telescope into a single point; a tank
and a swarm-bug feel identical to stand next to. Projectile knockback exists
(`proj.knockback` -> `enemy.apply_knockback`) but it is a flat per-weapon scalar
with no sense of the target's mass. We want the start of a physics layer:
**weights** on every body + weapon, and a shared knockback function so a bump and
a hit read the same way -- the bigger the weight gap, the bigger the shove. The
per-weapon `knockback` field is **removed**; a weapon's `weight` is now the only
knockback input (decision 4).

### The model

**Weight** (float, arbitrary units) on every mobile body and every weapon:

| carrier | source | rough feel (tune later) |
|--|--|--|
| enemy | `weight` in `data/enemies.json`, fallback = `radius / 2` | swarm/fast light, chaser mid, tank/elite/brute heavy |
| hero | `config.PLAYER_WEIGHT` (later: a `weight` stat so items can shift it) | heavy enough that a swarm barely moves them |
| boss | `Boss.weight = inf` | already immovable (`apply_knockback` no-op); only shoves others |
| weapon | `weight` in `data/weapons.json`, **separate from the wielder** | `soul_scythe` heavy; `arcane/frost/thunder/ember` light-plus ("spells weigh a bit more"); `grave_totem` bolt **very** small; `spirit_wolf` **0** (a spirit -> no knockback) |

**Shared knockback split** -- new pure module `combat/knockback.py`:

```
knock_split(w_src, w_tgt, base) -> (push_src, push_tgt)
    total    = base * (1 + DIFF_GAIN * |w_src - w_tgt| / (w_src + w_tgt))
    push_tgt = total * w_src / (w_src + w_tgt)      # target moves per the SOURCE's share
    push_src = total * w_tgt / (w_src + w_tgt)      # source recoils per the TARGET's share
```

* the `DIFF_GAIN` term is the "bigger difference -> bigger knockback" rule.
* callers pick `base`: a **bump** uses `BUMP_GAIN * penetration_px`; a **hit**
  uses `HIT_KNOCK_GAIN * w_src` (the weapon weight *is* the hit strength, then
  the split + `DIFF_GAIN` shape it against the target's mass). So a spirit-wolf
  hit (`w_src == 0`) has `base == 0` -> nothing happens.
* a featherweight into a titan: `push_tgt` tiny, `push_src` ~= `total` (it
  bounces itself); `w_tgt == inf` (boss) -> `push_tgt == 0`, `push_src == total`.
  These `0` / `inf` cases are explicit branches, not IEEE arithmetic (see B).

**Unit bump pass** -- new `game/states/playing/physics.py::BumpResolver`, called
from `_phase_update` after the enemy / boss / summon updates:

* grid of `_targetables()`; for each enemy, neighbours within `r_a + r_b`; for
  each overlapping unordered pair `pen = (r_a + r_b) - dist`; if `pen > 0`,
  `base = BUMP_GAIN * pen`, `knock_split(w_a, w_b, base)`, then
  `a.apply_knockback(a.pos - b.pos, push_a)` / `b.apply_knockback(..., push_b)`.
* hero vs each overlapping enemy: same split; the enemy takes `apply_knockback`,
  the hero accumulates into a new `Player._knock`.
* the soft `Separation` steering component stays -- it stops most overlaps ever
  forming; the bump impulse is the harder kick when bodies do interpenetrate
  (spawns, chargers, being herded into a wall).

**Hero knockback plumbing** -- `Player._knock: Vector2`,
`Player.apply_knockback(dir, strength)`, and in `Player.update`
`target = pos + move*dt + _knock*dt` routed through `world.resolve_movement`
(so shoves slide along walls), `_knock *= pow(BUMP_DECAY, dt)` then zeroed under
a threshold -- mirrors `Enemy.update`.

**Weapon-hit knockback** -- rework `combat.py::projectile_hits`:

* `Projectile.knockback` slot / `reset` kwarg is **renamed** to
  `src_weight: float = 0.0` (the wielder-independent weapon weight the hit
  carries). Old callers passing `knockback=` move to `src_weight=`.
* on hit: `_, push_tgt = knock_split(proj.src_weight, enemy.weight,
  HIT_KNOCK_GAIN * proj.src_weight)`;
  `enemy.apply_knockback(enemy.pos - proj.pos, push_tgt)`. Guarded by
  `if proj.src_weight:` so a weight-0 hit does nothing. Hits push only the
  target (no recoil onto the hero) for this first slice.
* `Weapon` passes `src_weight = float(def.get("weight", 0.0))` when it spawns
  projectiles / orbiters. **Start with `soul_scythe`**: wire its weight,
  playtest the feel, then fan the field out to the other weapons.
* `entities/summon.py`: the wolf bite spawns with `src_weight = 0`; the totem
  bolt with a **very small** `src_weight` (~1).

**Elite resist** -- fold the current `Enemy.apply_knockback` `is_elite *= 0.35`
special-case into a simply-heavier `weight` and delete the branch (one rule, not
two). Flagged as a deliberate behaviour change.

### Decisions (locked 2026-08-29)

1. **Bump = impulse into `_knock`** (bump with follow-through; keeps the soft
   `Separation` steering) rather than a hard positional de-overlap. **Yes.**
2. **The hero is shoved by enemy bumps**, with `PLAYER_WEIGHT` tuned so a swarm
   barely registers and a brute / charger noticeably pushes. **Yes.**
3. **Formula** as written above -- `total = base*(1 + k*|Dw|/Sw)`, split by the
   *other* body's weight share, `w_src=0 -> 0`, boss `= inf`. **Yes.**
4. **Remove the per-weapon `knockback` field entirely; `weight` replaces it.**
   Hit strength is `HIT_KNOCK_GAIN * weapon.weight`, then `knock_split` shapes
   it against the target. No separate scalar.
5. **Enemy `weight`: explicit field, fallback `= radius / 2`** when a def omits
   it.
6. **Delete the elite `*0.35` knockback special-case**, express it as weight.
   **Yes.**
7. **Hits push only the target** this slice -- no recoil onto the hero or a
   melee lunge-back. **Yes** (revisit later).
8. **Totem bolt** gets a **very small** `src_weight` (~1) -- a barely-there
   nudge, not zero. Wolf bite stays 0.

### Checklist

#### A - Data + constants -- DONE (2026-08-29)
- [x] `weight` on every `data/enemies.json` def: swarm 3 / fast 5 / teleporter 6
      / ranged 6 / chaser 7 / warlock 7 / exploder 8 / shielded 8 / charger 8 /
      summoner 10 / tank 14 / elite 30 / brute 80. Light types sit at ~radius/2;
      `elite` / `brute` carry the folded `*0.35` resist (decision 6) as extra
      mass.
- [x] **Removed** `knockback` from all 7 `data/weapons.json` defs; added
      `weight`: `soul_scythe` 30, `arcane_bolt` 7, `frost_shards` / `thunder_orb`
      6, `ember_ring` 8, `grave_totem` 1, `spirit_wolf` 0.
- [x] `config.py` -- new "Physics: bumping & knockback (CB-3)" block:
      `PLAYER_WEIGHT 40`, `BUMP_GAIN 12`, `BUMP_DIFF_GAIN 2.0`,
      `BUMP_DECAY 0.001` (the curve enemies already used), `HIT_KNOCK_GAIN 2.5`
      (calibrated so `soul_scythe` vs a `chaser` lands near the old `140`).
- Nothing reads `weight` yet -- `Weapon` still does `def.get("knockback", 0.0)`
      so projectile knockback is **inert** until E rewires it. Suite green (620).

#### B - `combat/knockback.py` (new) -- DONE (2026-08-29)
- [x] pure `knock_split(w_src, w_tgt, base, *, diff_gain=None) ->
      (push_src, push_tgt)`. `diff_gain` defaults to `config.BUMP_DIFF_GAIN`
      (kw-only override lets tests pin it). Imports only `math` + `game.config`;
      no pygame.
- [x] explicit edge branches (no IEEE `inf/inf`): `base <= 0` or `w_src <= 0`
      -> `(0, 0)`; `w_src` & `w_tgt` both `inf` -> `(0, 0)`; `w_tgt == inf` ->
      `(base*(1+diff_gain), 0)`; `w_src == inf` -> `(0, base*(1+diff_gain))`;
      `w_src + w_tgt == 0` -> `(0, 0)`.
- [x] `tests/combat/test_knockback.py` (13 cases): symmetry, `sum == total`,
      gap raises the total, featherweight recoils more / heavyweight shoves
      more, the `0` / `-ve` / `inf` guards, `diff_gain` default tracks config,
      no nan/inf leak. Suite 620 -> 633, green.
- Sanity (real weights): `soul_scythe` hit -> swarm 180 / chaser 136 / tank 88
      / brute 39 px/s (was a flat 140); `arcane_bolt` / `ember_ring` ~9-12
      ("very slightly"); `spirit_wolf` 0. Bump @ 12 px pen: swarm<->hero shoves
      the hero only +27 px/s, brute<->hero +160.
- **Tuning note for D/H:** the bump base is `BUMP_GAIN * pen` applied *every
      frame the pair overlaps*; with `_knock` decay ~0.89/frame that reaches an
      equilibrium ~6x the per-frame add if bodies stay interpenetrated. Rely on
      `Separation` steering to keep overlaps shallow/brief; if crowds still
      "boil", drop `BUMP_GAIN` (12 is a first guess) or make the bump a
      one-shot on overlap onset in D.

#### C - Bodies carry weight -- DONE (2026-08-29)
- [x] `Enemy.weight = float(definition.get("weight", self.radius / 2.0))`.
      `apply_knockback` lost the `if self.is_elite: strength *= 0.35` branch
      (decision 6 -- resistance is now `weight` + `knock_split`). `Enemy.update`
      decay switched from the literal `pow(0.001, dt)` to
      `pow(config.BUMP_DECAY, dt)` (same value, one source of truth).
- [x] `Boss.weight = float("inf")`; `apply_knockback` stays a no-op (double
      guard -- `knock_split` already returns `0` for an `inf` target).
- [x] `Player.weight = float(config.PLAYER_WEIGHT)`, `Player._knock`,
      `Player.apply_knockback(dir, strength)`, and `Player.update` now
      integrates `(_move_dir*move_speed + _knock)*dt` through
      `world.resolve_movement` then decays `_knock` by `pow(config.BUMP_DECAY,
      dt)` (zeroed under length 1) -- mirrors `Enemy`.
- Sanity: chaser `weight 7` (data) / a def without the key -> `radius/2`; boss
      `inf`, shrugs off `apply_knockback`; a 200 px/s impulse moves an enemy
      ~30 px over 1 s then fades; a 160 px/s impulse shoves the hero ~24 px.
      Suite still green (633) -- `_knock` is `(0,0)` in every existing path so
      movement is byte-identical until D starts feeding it.

#### D - `game/states/playing/physics.py` (new `BumpResolver`) -- DONE (2026-08-29)
- [x] enemy<->enemy + enemy<->boss: a **private** `SpatialGrid` (not `ps.grid`
      -- self-contained, no interaction with `_phase_combat`), rebuilt each
      call from `enemies (+ boss)`; unordered-pair dedup by `id`; precise
      overlap test -> `pen`; `knock_split(a.weight, b.weight, BUMP_GAIN * pen)`
      -> `a.apply_knockback(a.pos - b.pos, push_a)` / `b` the mirror.
- [x] hero<->enemy / hero<->boss: same `_bump`, so the hero's `_knock` and the
      enemy's both take a share; the boss's `inf` weight zeroes its side.
- [x] `pen` clamped to `rr * _PEN_CAP_FRAC` (0.75) so a charger tunnelling in
      one frame can't generate an absurd impulse.
- [x] wired into `PlayingState._phase_update` as `self.bump.resolve()`, right
      after the enemy / boss `update` loop and before `fx.update_projectiles`.
      `self.bump = BumpResolver(self)` built next to `self.combat`.
- Sanity (dev `_dev_no_attack`, headless): 4 swarm + 1 brute stacked on a point
      spread from ~10 px to ~160 px mean separation over 40 frames and settle;
      a lone chaser pressing the hero nudges it ~9 px / s (gentle "leaning on
      you"); a swarm bug spawned *exactly* on a brute peaks near ~900-1000 px/s
      for ~2 frames before decaying -- worst case, tune in H (drop `BUMP_GAIN`
      and/or tighten `_PEN_CAP_FRAC`, or make the bump one-shot). Suite green
      (633).

#### E - Weapon-hit knockback -- DONE (2026-08-29)
- [x] `Projectile.knockback` -> `src_weight` (slot, `__init__`, `reset` kwarg,
      default `0.0`).
- [x] `combat.py::projectile_hits`: `if proj.src_weight:` ->
      `_, push = knock_split(proj.src_weight, enemy.weight,
      config.HIT_KNOCK_GAIN * proj.src_weight)` then
      `enemy.apply_knockback(enemy.pos - proj.pos, push)` -- target only
      (decision 7). Added `from combat.knockback import knock_split` +
      `from game import config`.
- [x] `combat/weapons.py`: one shared `src_weight = float(def.get("weight",
      0.0))` read in `_fire`, passed by the cone branch, the fan branch, and
      `_maintain_orbit`. Wired the **whole roster** in one pass -- the read is
      shared, "soul_scythe first" only mattered for the playtest gate (H), and
      the per-weapon `weight` values already landed in A.
- [x] `entities/summon.py`: wolf bite `src_weight=0` (spirit -> nothing); totem
      bolt `src_weight=1`.
- [x] `tests/combat/test_weapons.py`: dropped the dead `"knockback"` key.
- Isolated sanity (resolver expression, no bump contamination): `soul_scythe`
      hit -> swarm 180 / chaser 136 / tank 88 / elite 38 / brute 39;
      `arcane_bolt` / `frost_shards` / `thunder_orb` 3-22 ("very slightly");
      `ember_ring` 5-28; `grave_totem` bolt 0.1-1.2; `spirit_wolf` bite **0.0**
      everywhere. `elite` at 38 ~= the old `140 * 0.35 = 49`, so the folded
      resist lands close. Suite green (633). NB: a *full-game* measurement mixes
      this with D's bump-knock when the enemy also touches the hero -- clean
      coverage lives in G at the resolver level.

#### F - Dev overlay -- DONE (2026-08-29)
- [x] `WorldRenderer.collider_overlay` (F7) gained a CB-3 block: a `wN` /
      `wINF` tag (mono 10, amber) just right of every mobile body's collider --
      hero, in-view enemies, boss -- and each body's live `_knock` drawn as a
      short blue line (`config.COLOR_DEBUG_KNOCK`, length `_knock * 0.15 * zoom`)
      whenever it is actually being shoved (`length_squared > 1`).
- [x] `config.COLOR_DEBUG_KNOCK = (120, 200, 255)`.
- Skipped the transient "bump flash" -- the persistent `_knock` line already
      shows which bodies are being pushed and how hard, which is what the H
      tuning pass needs. Verified headless: a stacked skirmish draws 5 knock
      vectors (52-285 screen px) + a tag per body, no errors; suite green (633).

#### G - Tests -- DONE (2026-08-29)
- [x] `knock_split`: `tests/combat/test_knockback.py` (13 cases, step B).
- [x] `tests/combat/test_bump.py` (14 cases) -- a `Body` stub with the
      `apply_knockback` / `_knock` contract drives `BumpResolver` directly:
  - enemy pair: equal weights -> symmetric opposite impulses; a swarm (w3)
        into a tank (w14) -> bug's `_knock` > 3x the tank's; no touch -> no
        impulse; coincident bodies skipped (no nan); a dead enemy neither
        shoves nor is shoved; `pen` clamp verified (95% overlap == cap overlap).
  - hero: a swarm bump barely nudges the hero while a brute bump shoves it >3x
        harder; the enemy always out-travels the hero in a bump; the boss
        (`weight inf`) shoves the hero and takes nothing back.
  - hit knockback (mirrors `CombatResolver.projectile_hits`): a heavy weapon
        shoves a light enemy more than a heavy one; a light projectile knocks
        < 1/5 of the scythe; a `weight 0` spirit bite -> `0.0`; an `inf`
        target -> `0.0`.
- [x] regression: full suite green (647); CB-2 reach tests, projectile
      cadence/aim tests, and the headless smoke all still pass unchanged.

#### H - Balance playtest -- DONE (2026-08-29, headless analysis; a human pass is still worthwhile)
- [x] **Normal fight** (director-driven, 40 s, weapons on, hero idle): 28
      kills, fight resolves normally. Enemy `_knock` while active: median
      **90**, p90 **139**, max **144** px/s (enemy speeds 45-190 -> a readable
      nudge, not a launch). Hero `_knock`: median **6**, max **25** px/s vs a
      260 move speed -- **the hero is barely shoved in real play**, which was
      the bar for decision 2.
- [x] **soul_scythe vs a tank stream**: tank `_knock` median **46** (== its
      45 move speed, so it is held in place while scythed), transient spikes to
      ~450 from hit+bump stacking on a frame, decays at once. Reads as a shove.
- [x] **Pathological** (6 bodies spawned on one *exact* point): peaks ~1800-2000
      px/s for a few frames. Tuned `_PEN_CAP_FRAC` 0.75 -> **0.6**: the pile now
      settles (`_knock` < 60) in **~0.6 s** (was ~1.7 s) and ends ~200 px apart
      (was ~500), with zero effect on shallow everyday overlaps. The spike
      itself is accumulation across many pairs in one frame, not one deep bump;
      it does not occur in director-driven play (spawns are spread).
- `BUMP_GAIN 12`, `BUMP_DIFF_GAIN 2.0`, `HIT_KNOCK_GAIN 2.5`, `BUMP_DECAY
      0.001` all validated by the normal-fight numbers -- **kept**.
- **Left for a human:** does it *feel* right in the hand (juice vs. annoyance),
      especially being pressed into a warlock hazard by a crowd. **Future
      refinement if the frame-spike ever bites:** cap per-body `_knock`
      magnitude per frame, or make the bump one-shot on overlap onset.

### Touch list (as built)
`data/enemies.json` (`weight` x13), `data/weapons.json` (`knockback` removed,
`weight` added x7), `game/config.py` (physics block + `COLOR_DEBUG_KNOCK`),
`combat/knockback.py` (**new**), `combat/weapons.py` (`_fire` / `_maintain_orbit`
pass `src_weight`), `entities/enemy.py` (`weight`, drop elite damp,
`BUMP_DECAY`), `entities/boss.py` (`weight = inf`), `entities/player.py`
(`weight`, `_knock`, `apply_knockback`, `update` integration),
`entities/projectile.py` (`knockback` -> `src_weight`), `entities/summon.py`
(wolf bite 0 / totem bolt 1), `game/states/playing/physics.py` (**new**
`BumpResolver`, `_PEN_CAP_FRAC` 0.6 after H), `game/states/playing/state.py`
(build + call `self.bump` in `_phase_update`), `game/states/playing/combat.py`
(`projectile_hits` -> `knock_split`), `game/states/playing/rendering.py`
(`collider_overlay` weight tags + `_knock` vectors).
Tests: `tests/combat/test_knockback.py` (**new**, 13),
`tests/combat/test_bump.py` (**new**, 14), `tests/combat/test_weapons.py`
(dead key dropped).
**No** new deps. **Nothing** committed.

---

## CB-4 · Melee-swing hitbox: dev-only render + a readable telegraph

**Status:** **DONE** 2026-08-30 (Part 1 shipped; Part 2 code + chaser metadata
shipped, sprite-fps trim still open — see follow-ups). Not committed.

### Why

`entities/melee_hitbox.py` `MeleeHitbox` — the small front-facing circle a
`path_chase_attack` enemy drops on its `telegraph -> attack` transition, which
deals `contact_damage` once on first overlap — was:

1. **drawn every frame** as a solid red ring (`WorldRenderer.melee_hitboxes`,
   called from `PlayingState.draw`), unlike every other collider, which only
   shows in the F7 / dev-menu "Collision shapes" overlay; and
2. landing after only **0.15 s** of wind-up (`attack_telegraph` default), too
   fast to read and step out of.

### What changed

**Part 1 — render like every other collider.**
- Removed `self.renderer.melee_hitboxes(surface)` from `PlayingState.draw`.
- Deleted `WorldRenderer.melee_hitboxes`.
- `WorldRenderer.collider_overlay` now draws each live `ps.melee_hitboxes`
  entry with the shared `ring()` helper, view-culled, in
  `config.COLOR_DEBUG_HIT` at width 1 — the same style as projectile hitboxes
  (a one-shot contact volume). Gated behind `ps.dev_mode and
  ps._dev_show_colliders` like the rest of that pass.

**Part 2 — a ~25 % longer, readable swing.**
- Module-level tuning constants at the top of
  `entities/ai/behaviors/simple.py` (globals, **not** `game/config` yet):
  `MELEE_REACT_SCALE = 1.25`, `MELEE_ATTACK_TELEGRAPH = 0.15 * scale`
  (0.1875 s), `MELEE_ATTACK_ACTIVE = 0.35 * scale` (0.4375 s),
  `MELEE_ATTACK_RECOVER = 0.15`, `MELEE_ATTACK_COOLDOWN = 0.6`. `recover` /
  `cooldown` are unchanged, so attack *cadence* barely shifts — only the
  readable wind-up and the hitbox lifetime grow.
- `build_path_chase_attack` reads each value as
  `cfg.get("attack_<key>", MELEE_ATTACK_<KEY>)` — a per-enemy
  `data/enemies.json` key wins, a missing key **falls back to the module
  constant**.
- The chaser ("Husk", the only `path_chase_attack` enemy) carries the explicit
  metadata `"attack_telegraph": 0.1875, "attack_active": 0.4375` so its tuning
  is visible in data; any future melee enemy without the keys inherits the
  slowed defaults.

Because `telegraph_cycle`'s transitions are `after(seconds)`, the timing change
is exact and deterministic.

### Verification

- Full suite **714 green**. `tests/ai/test_ai_behaviors_fsm.py` asserts state
  names / rooted-ness with its own explicit cfg, not the `path_chase_attack`
  defaults; `tests/core/test_dev_mode.py` (F7 toggle) and
  `tests/rendering/test_depth_sort.py::test_render_pipeline_order` unaffected.
- `python -c "from entities.ai.behaviors import simple"` →
  `MELEE_ATTACK_TELEGRAPH 0.1875`, `MELEE_ATTACK_ACTIVE 0.4375`.

### Follow-ups (not blocking)

- **Sprite sync:** the `skull` `attack` strip (7 frames @ 14 fps = 0.5 s) now
  finishes ~0.19 s before the swing ends and holds its last frame. Cut its
  `attack.fps` in `data/sprites.json` to ~11 so one swing spans the stretched
  `telegraph + active` (~0.625 s). Same for any future `path_chase_attack` rig.
- If more systems need it, promote `MELEE_REACT_SCALE` to `game/config.py` and
  fold it into the difficulty multipliers.

---

## CB-5 · Manual aim, mouse attacks and the auto-attack toggle

**Status:** **DONE** 2026-09-04 (groups A–F shipped the same day; the dev-mode
aim-line overlay is a separate `dev_mode_journal.md` entry). Not committed.
Verification at the end of this entry.

### Why

Every attack is auto-aimed. `combat/targeting.py — aim_direction` picks the
nearest (or a random) enemy for each weapon, `FireContext.fallback_dir`
(`_last_move_dir`) is only consulted when that returns `None`, and the CB-2
reach ring silences a weapon whose ring is empty before aim is ever computed.
There is no mouse handling anywhere in the game, and the sprite's `_facing`
follows horizontal *movement* only. The user wants the hero to attack where
the player points, with auto-aim as the fallback.

### Requirements (confirmed)

Aim priority, highest first:

1. **Left click** — attack in the direction of the cursor. Works with auto
   attack on or off; while on, it takes over from auto-aim. A tap fires once;
   holding keeps attacking at the weapon's normal cooldown.
2. **Held aim key** — attack that way for as long as it is held, auto attack
   on or off. Beats auto-aim whenever any aim key is down.
3. **Auto-aim** — only with auto attack on and neither of the above active.
   Unchanged behaviour: nearest enemy, reach ring gates firing.
4. **Nothing** — auto attack off, no click, no aim key: the hero does not
   attack.

Controls:

- `Q` toggles auto attack. **On by default.** No HUD element; the player
  reads the state from the hero's behaviour.
- Aim keys are the arrow keys; movement is WASD. A **layout swap** option
  (arrows move, WASD aims) lives in the Options screen *and* the pause menu,
  persisted in `save.settings`.
- The mouse cursor is inert unless clicked. Auto-aim never follows it.

Per weapon:

- **Melee** (`soul_scythe`): the cone is swung in the aim direction.
- **Ranged / magic** (`arcane_bolt`, `frost_shards`, `thunder_orb`): the shot
  goes in the aim direction. Multishot fans around it as now.
- **Orbit** (`ember_ring`) and **summons** (`grave_totem`, `spirit_wolf`) have
  no direction and take no aim. With auto attack off they keep working
  (they are not "attacks" in the swing sense).
- **Orbit ring while clicking.** CB-2 decision 6 forms the orbiters only
  while an enemy is inside the reach ring. New condition: they also form
  while **left click is held** (a manual mouse attack). The ring is spinning
  when the player is actively attacking, empty ring or not. A held aim key
  does *not* raise them — click only.

Fire-time target pick for a manual attack (the "tracking"):

- No projectile homes today; what reads as tracking is the nearest pick at
  fire time. So: at the instant a manual attack fires, gather enemies inside a
  cone around the aim direction, out to the weapon's reach; if any, aim at the
  **closest**; otherwise fire straight along the aim. Chain lightning then
  chains as normal (`chain_to_next` is a post-hit re-target, untouched).
- **Manual attacks can whiff.** The reach-ring gate applies to auto-aim only;
  a manual attack always fires (with the attack animation) even into empty
  space.

Facing: while a manual aim is active the sprite faces the aim; otherwise it
follows movement as now.

Click and aim key at the same time: click wins.

### Design notes

- `aim_direction` stays the single resolution point. A manual aim reaches it
  as a **new targeting source**, not as `fallback_dir`: the cone-filtered
  enemy list + the aim vector as the fallback. `fallback_dir` is then the only
  thing auto-aim needs and the dead "fire into open space" branch goes away.
- The cone half-angle for the fire-time pick is one global
  `config.MANUAL_AIM_ASSIST_DEG` (start ~25°); a weapon may override it with
  an optional `aim_assist_deg` in `data/weapons.json`. Per the data-driven
  rule, no per-weapon value default in code beyond the global.
- Input lives in one small module (`game/states/playing/aim.py`) that turns
  the frame's key state + mouse into an `AimInput(direction: Vector2 | None,
  source: "mouse"|"keys"|None, fire: bool)`. `PlayingState._phase_input`
  reads it; `_phase_combat` hands it to `FireContext`. Nothing else touches
  pygame's mouse.
- `Weapon.update` gains a "forced fire" path: with a manual aim present and
  the cooldown ready, `_fire` skips the ring gate. Summons ignore the aim
  entirely; orbit ignores its *direction* but reads `aim.source == "mouse"`
  (a held click) as "ring wanted" in `_maintain_orbit`, alongside the
  existing enemy-in-reach test. Auto attack off + no manual aim → straight/chain/cone weapons
  hold (their cooldown still ticks down so the first manual attack is
  instant).
- Key layouts are two named pairs (`move`, `aim`) of raw SDL keycodes in
  `game/config.py` (the same raw-int convention as `_LEFT_KEYS` in
  `entities/player.py` and `DEBUG_KEYS`, for pygbag). `Player.input_vector`
  takes the key tuple set instead of hard-coding it.
- The pause menu's **`Q` = quit to menu** clashes in spirit with `Q` = toggle
  auto attack (a run-long habit followed by ESC → Q loses the run). The plan
  first said "move it to `M`", but `M` is the global mute key, consumed in
  `Game._process_input` before any state sees it. So the pause screen became
  a **cursor menu** (Resume / Key layout / Quit to menu; ENTER picks) with no
  single-letter quit at all; `Q` does nothing there.
- Mouse → world is `Camera.screen_to_world`; screen-shake offsets the camera
  only inside `draw`, so `camera.pos` is un-shaken during input.
- **A tap is one volley, not one projectile.** The queued click is spent on
  the frame *any* directional weapon fires from it (`_phase_combat` calls
  `consume_tap()`); a weapon still mid-cooldown on that frame does not get
  its own later shot. Multishot fires its full fan from the one tap.
- **Only a *held* click raises the orbit ring** (`FireContext.click_held`:
  source `"mouse"` and `held`). A tap is a single attack and leaves the ring
  down; so does a held aim key.

### Checklist

#### A · Config + settings — done 2026-09-04
- [x] `game/config.py`: `AUTO_ATTACK_DEFAULT = True`; `MANUAL_AIM_ASSIST_DEG`
      (25°); `KEY_LAYOUTS = {"wasd_move", "arrows_move"}` as raw SDL keycode
      tuples for `move` / `aim` in each of the four directions (the swapped
      layout is the exact mirror); `KEY_TOGGLE_AUTO_ATTACK` (K_q);
      `DEFAULT_KEY_LAYOUT`; `KEY_LAYOUT_LABELS` for the option rows.
- [x] `game/save.py`: `settings["key_layout"]` (default `"wasd_move"`),
      coerced against a local mirror of the layout names (the module stays
      dependency-free, like `_RECORD_DIFFICULTIES`); junk or a missing key
      reads as the default.
- [x] `game/game.py`: `Game.key_layout` (name, never an unknown one),
      `Game.keys` (the layout's `move` / `aim` tuples), `set_key_layout`
      (persists at once) and `cycle_key_layout` (the toggle the pause /
      options rows will call).
- [x] Tests: `tests/core/test_save.py` (+2: default + round-trip, junk
      fallback), new `tests/core/test_controls.py` (+9: keycodes pinned
      against `pygame.K_*`, move / aim disjoint per layout, mirror, labels;
      `Game` accessors, persist, refusal, cycle wrap, junk-in-save).

#### B · Aim input — done 2026-09-04
- [x] New module `game/states/playing/aim.py`: `AimInput(direction, source,
      held, tap)` (frozen dataclass; `active`, `wants_fire`, `none()`),
      `mouse_direction` (cursor → world through the camera; a cursor on the
      hero falls back to the last move direction, then +x) and
      `read_aim(pressed, mouse_buttons, mouse_pos, camera, origin, aim_keys,
      fallback, tap_pending)`. A held click *or a queued tap* wins outright
      (source `"mouse"`); otherwise a held aim key (source `"keys"`,
      `held=True`); otherwise `AimInput.none()`.
- [x] `entities/player.py`: `input_vector(pressed, keyset)` reads one
      direction table from `config.KEY_LAYOUTS` (the old merged WASD+arrows
      constants are gone); `handle_input(pressed, move_keys)`;
      `face(direction)` sets `_facing` from the aim's x sign (a vertical aim
      keeps it) and raises `_face_override`, which `update()` honours once
      instead of the movement rule, then clears.
- [x] `PlayingState`: `auto_attack` (from `config.AUTO_ATTACK_DEFAULT`),
      `_aim`, `_tap_pending` in `_init_run`. `_phase_input` walks with
      `game.keys["move"]`, keeps `_last_move_dir`, builds the frame's
      `AimInput` with `game.keys["aim"]` and faces the hero when it is
      active. `consume_tap()` clears the queue — **group C calls it** on the
      frame a directional weapon fires from the tap.
- [x] `PlayingState.handle_event`: left `MOUSEBUTTONDOWN` queues the tap
      (other buttons ignored); `config.KEY_TOGGLE_AUTO_ATTACK` flips
      `auto_attack`. Mouse events no longer fall out of the early return.
- [x] Tests: `tests/characters/test_movement.py` updated for the keyset
      argument (arrows no longer walk under the default layout; the swap is
      checked); new `tests/combat/test_manual_aim.py` — `ReadAimTests` (+12:
      ladder, tap, swap, cursor-on-hero fallback, camera zoom, inert cursor),
      `FacingOverrideTests` (+2), `ManualAimStateTests` (+6, one shared
      headless run: `Q` toggle, tap queue until `consume_tap`, frame aim,
      facing, run-camera click, layout-driven movement).

#### C · Targeting + weapons — done 2026-09-04
- [x] `combat/targeting.py`: `enemies_in_cone(origin, direction, enemies,
      half_angle, reach)` (an enemy on the origin counts as inside);
      `aim_direction` unchanged in signature.
- [x] `combat/weapons.py`: `FireContext.aim` and `auto_attack`, plus the
      `manual_fire` / `click_held` properties the weapon reads. In `update`:
      orbit / summon paths first, unchanged; then cooldown; then manual aim →
      `_fire(ctx, forced=True)` and restart the cooldown; else auto attack
      off → hold with `_cd = 0.0` so the next manual attack is instant; else
      the CB-2 auto path exactly as before.
- [x] `Weapon._fire(ctx, forced)`: forced skips the reach-ring return,
      filters `ctx.enemies` through `enemies_in_cone` with
      `_assist_half_angle()` (`aim_assist_deg` in the weapon's data, else
      `config.MANUAL_AIM_ASSIST_DEG`) and the weapon's reach, then
      `aim_direction(mode, origin, in_cone, fallback=aim.direction)`; the
      melee cone gets the *raw* aim. Multishot spread and chain params ride
      the resulting direction untouched.
- [x] `data/weapons.json`: `aim_assist_deg` is read as an optional override;
      no weapon sets it (the global applies). Documented with the aim
      section in `combat_calculations.md` (group F).
- [x] `Weapon._maintain_orbit`: `desired = 0` only when the reach ring is
      empty **and** `not ctx.click_held`. Respacing / trimming unchanged.
- [x] `PlayingState._phase_combat`: passes `aim=self._aim,
      auto_attack=self.auto_attack`; spends the tap on the frame any weapon
      fires from it. The whiff plays the attack animation (forced fire
      returns `True` from the main weapon).
- [x] Tests (`tests/combat/test_manual_aim.py`, +23): `ConeTests` (angle,
      reach, on-origin), `WeaponAimTests` (forced fire vs empty ring, closest-
      in-cone homing, empty cone → straight, nearest-but-outside ignored,
      per-weapon `aim_assist_deg`, melee raw-aim cone, melee whiff, auto-off
      hold keeps `_cd == 0` and the first tap is instant and a full volley,
      auto-off + held key fires, multishot centred on the aim, chain opens
      along the aim, summons ignore the aim), `OrbitOnClickTests` (held click
      raises with an empty ring, release drops, held key / tap alone do not,
      enemy in reach still does), `TapConsumptionTests` (one shared run: a
      tap fires once and animates the whiff, waits out a cooldown then fires
      once, auto-off + no aim never fires). Whole `tests/combat`: 157 green.

#### D · Pause + options — done 2026-09-04
- [x] `game/states/paused_state.py`: a cursor menu — Resume, Key layout
      (ENTER or Left / Right cycle; shows the `config.KEY_LAYOUT_LABELS`
      text), Quit to menu (ENTER on the row). ESC / P still resume from any
      row. `Q` does nothing here; there is no single-key quit (see the design
      note on `M`).
- [x] `game/states/options_state.py`: `key_layout` row between Mute and
      Sanctuary; ENTER or Left / Right cycle via `Game.cycle_key_layout`
      (persists at once); the row shows the layout label; the footer hint
      reads "Left / Right adjust".
- [x] Controls text: `README.md` controls table (WASD, arrows = aim, left
      click, `Q`, the pause rows) and the "weapons attack automatically"
      paragraph now describe manual aim and the toggle.
- [x] Tests: new `tests/rendering/test_pause.py` (+8, one shared paused run:
      ESC / P resume, the Resume row, `Q` inert, wrap, layout row cycles and
      persists, Left / Right inert off the row, draw, Quit row → menu);
      `tests/rendering/test_options.py` `KeyLayoutRowTests` (+4: ENTER
      cycles + persists, Left / Right on the row only, reload into a fresh
      `Game`, draw); `tests/core/test_dev_mode.py` pause-quit path walks to
      the Quit row instead of pressing `Q`.

#### E · Tests — done 2026-09-04 (audit of A–D plus the gaps)
- [x] `tests/combat/test_manual_aim.py` (52): `read_aim` priority ladder
      (click > keys > none; layout swap); cone pick chooses the closest
      inside the cone and falls back to the raw aim when empty; forced fire
      ignores the reach ring; auto-attack-off + no aim → no projectile while
      orbit (`test_auto_attack_off_does_not_lower_the_ring`) and summons
      still run; tap fires once, hold keeps firing
      (`HoldKeepsFiringTests`: one volley per cooldown, click and key at the
      same cadence, and the pin that an *unconsumed* tap keeps firing — the
      run must spend it); orbiters form with an empty reach ring while click
      is held and drop on release (held key / tap alone do not).
      `FullFrameTests` (+5) drive real mocked snapshots through
      `PlayingState.update`: `Q` off + held arrow attacks that way; auto off
      + enemy in reach stays silent over 30 frames; a held arrow beats
      auto-aim on an enemy and faces the hero; a click tap fires once at the
      cursor and is spent; the swapped layout aims with WASD and does not
      walk.
- [x] `tests/characters/test_movement.py`: `input_vector` with both layouts.
- [x] `tests/core` / `tests/rendering`: save round-trip for `key_layout`
      (`test_save.py`, `test_controls.py`); the pause Quit row quits and `Q`
      does not (`test_pause.py`).

#### F · Docs — done 2026-09-04
- [x] `documentation/combat_calculations.md`: §1c's `FireContext` snippet now
      shows `aim` / `auto_attack` and the tap spend; new **§1c·i · Aim
      resolution** — the `read_aim` priority ladder, the tap queue, the
      `Weapon.update` branch order, `_fire(forced=True)` with the assist
      cone (`aim_assist_deg` else `config.MANUAL_AIM_ASSIST_DEG`), melee raw
      aim, whiffs, orbit-on-click, facing.
- [x] This entry: status DONE, verification below.

### Verification (CB-5)

- Full default suite after group C: **1101 passed, 1 skipped** (from 1078
  before CB-5). **Final run after groups D–F: 1122 passed, 1 skipped**, exit
  0 (10:54). Every addition is a CB-5 test.
- `tests/combat/test_manual_aim.py` — 52; `tests/core/test_controls.py` —
  9; `tests/rendering/test_pause.py` — 8; `tests/rendering/test_options.py`
  `KeyLayoutRowTests` — 4; `tests/core/test_save.py` — +2;
  `tests/characters/test_movement.py` reworked for the keyset argument.
- Whole `tests/combat`: 157 → 166 with group E. `tests/core/test_smoke.py`
  walks ESC → pause → ESC → resume through the new menu.
- Behavioural pins worth knowing: a held key fires one volley per cooldown
  with the first shot instant; auto off leaves `_cd == 0` so the first manual
  attack after any wait is instant; a tap is spent by the run, not the
  weapon (an unconsumed tap keeps firing at the weapon level — pinned on
  purpose).

### Open follow-ups (not blocking)

- An aim line is **dev-mode only**, behind its own dev-menu toggle. Planned
  in `dev_mode_journal.md` ("Aim line" entry), not here; nothing about it
  ships to normal gameplay.
- Gamepad right-stick aim would slot into `read_aim` as a third source.
