# Elemental system journal

## Requirement (2026-09-21)

The owner delivered `ELEMENTAL_SYSTEM_DESIGN.md` (revision 8, kept outside the
repository at `D:\Documentos\Work\pygame\ELEMENTAL_SYSTEM_DESIGN.md`) and asked
for a review of the design against the code base and the documentation, and a
todo list of the changes it needs. No code was touched in this pass; this
entry is the Milestone 0 "Discovery" report the design asks for (§12, item 0)
and the todo list that follows from it.

The design in one paragraph: four elements (Fire, Ice, Thunder, Wind) are
code; JSON only tunes their numbers. Every element-carrying hit leaves an
**aura** on the enemy (one slot) and runs an **initial effect**; a hit of a
different element consumes the aura and fires one of six **reactions**
(Frostburn, Overload, Superconduct, FireWind, IceWind, ThunderWind). Statuses
(Burn, Slow, Freeze, Frostburn) are separate from the aura and never react.
Every reaction locks the enemy's aura slot for a global cooldown. A weapon
holds exactly one element, applied every `elementInterval + 1` attacks;
infusions are run-scoped and come from elemental buff buildings and a
Monastery where the player picks an element and a weapon. Enemies get
per-type resistance profiles; damage is credited per effect and per source
weapon; ~100 enemies with auras must not drop frames.

## Discovery: what the code already has

Everything below was verified in the worktree on 2026-09-21.

### The hit pipeline is already a single entry point

- Every hero damage path lands in `CombatResolver.projectile_hits`
  (`game/states/playing/core/combat.py:50`): straight shots, cones (Sword,
  Daggers), the chain redirect, the Ember Ring orbiters, the Bomb's blast and
  bomblets, the Hammer's slam and Earthshaker shockwave, the Meteor Hammer
  crater (its ticks are hidden one-frame projectiles, `effects.py:435`),
  summon bites and bolts, Split Arrow children, the Pinball buff's ball. The
  design's demand that "every weapon's hit path routes through the same
  elemental entry point" (§7) is therefore one call inserted after
  `enemy.take_damage` at `combat.py:80`.
- Paths that bypass the resolver, and deliberately stay outside the element
  system: `TransientFx.enemy_explosion` (blessing procs, `effects.py:507`),
  Turbo's contact bites (`buffs.py:220`), villager lances (`npcs.py:260`).
- Damage lands in one place, `Enemy._absorb` / `Boss._absorb`
  (`entities/enemy.py:115`, `entities/boss.py:104`), which feeds the run
  ledger and the DPS meter. The smoke test pins `ledger.total ==
  stats["damage_dealt"]`, so every new element damage path must both go
  through `take_damage(..., source=...)` and add to `stats["damage_dealt"]`.
- The per-hit multiplier chain is `damage_multiplier(proj, enemy)`
  (`combat.py:115`): tag bonus, `status.damage_taken_multiplier()`, status
  vulnerability, conditional weapon effects, synergies. Crit is rolled once at
  fire time and frozen on the projectile.

### Statuses: a data-driven framework exists, with names already taken

- `combat/status.py` has `StatusType` rows with families `dot | slow | amp |
  stun | mark`, one update loop, `source` on every active status (so ticks are
  credited to the weapon), refresh-or-stack rules and `max_stacks`.
- Names in use: `burn` (dot, stacks to 5, 0.5 s tick, applied by the Ember
  Ring's Scorch), `chill` (slow, refresh, applied by Chilling Bolts), `bleed`
  (Lacerate), `poison`, `shock`, `stun` (the Hammer; `Enemy.update` zeroes
  `vel` and contact damage while stunned but still integrates `_knock`),
  `mark` (the Rod).
- Timers are per-frame `dt` decrements, and they tolerate the spawn master's
  LOD (an off-screen enemy is ticked with `dt * ENEMY_LOD_SKIP`). The status
  object is the only transient state that survives hibernation
  (`spawn/population.py:77`).
- The generic on-hit hook the six blessings use, `<status>_on_hit_frac /
  _on_hit_potency / _on_hit_duration` (`combat.py:220`), is the precedent for
  "a weapon applies a status credited to itself".

### Knockback, contact damage, bumps

- Weight-split knockback is the only knockback (`combat/knockback.py`,
  `config.HIT_KNOCK_GAIN`, `BUMP_GAIN`, `BUMP_DECAY`); a hit pushes only the
  target (`combat.py:95`); bodies integrate their own `_knock` accumulator.
  There is no radial-shockwave helper: `grid.query_circle` + `knock_split` +
  `apply_knockback` per body is what Overload and the Wind area will use.
  `synergy.pull` is the inward precedent.
- The boss has `weight = inf` and a no-op `apply_knockback`; it is also
  `stun_immune` (class attribute, read only by the Hammer's `apply_stun`).
- Enemy-to-enemy overlap is resolved by `BumpResolver._bump`
  (`core/physics.py:77`), which is where a sliding frozen enemy meets the
  enemies it hits. The contact-damage formula the design says to reuse for
  frozen contact (§4.2) is the bite model: `dps * tick_interval` per interval
  (enemy-to-hero bites in `combat.py:331`, Turbo's enemy bites in
  `buffs.py:198`, hazards in `entities/hazard.py`).

### Weapons

- `Weapon` (`combat/weapons/core.py:123`) is a dataclass over the JSON
  definition with a `bonus` dict (blessings) and an `effects` dict; nothing in
  it names an element. `_begin_attack` already counts attacks (`_shots`, for
  Overcharge) and is called once per attack for straight, cone, bomb and slam
  fire, so `elementInterval` is one modulo test there. Orbit and summon
  weapons never call it.
- Three "attacks" break the design's "all weapons are cooldown-based, one
  firing = one attack" assumption (§6.3, R23): the Ember Ring orbiters re-hit
  every `rehit_interval`, the Meteor Hammer crater ticks, and the Pinball
  ball re-hits while rolling. Each needs a stated rule.
- `weapons.json` has no per-weapon default fallbacks in code
  (`data-driven-no-code-defaults`); an `element_interval` key must be present
  on every entry rather than defaulted to 0.
- Summons are already excluded from Forgings and from the melee/ranged stat
  blessings; whether a summon can be infused is undecided in the design.

### Enemies and enemy data

- `Enemy.cfg` is the raw JSON block; a new optional `elementProfile` key is
  reachable without constructor changes. `enemies.json` entries are not
  validated at load at all; the fail-soft precedent for bad enemy data is
  `spawn/roster.py` (resolve once, log notes, never fatal), which the owner
  set as the rule for enemy/spawn data (`spawn-data-fails-soft-not-at-load`).
- Liveness is the `alive` flag; dead enemies are culled after the combat
  passes, hibernation removes from the list only in the update phase, so an
  `alive` check inside a chain is enough (no generation counter needed).
- `SpatialGrid` (`systems/collision.py`) is rebuilt at the top of the combat
  phase and offers `query_circle` only; there is no nearest-N query anywhere.
- The enemy live cap is 250 (`config.ENEMY_LIVE_CAP`); the stress harness
  `tools/benchmarks/spawn_stress.py` already drives a real run with 100 live
  enemies and reports p50/p90/p99 frame times.

### Buildings and the Monastery

- A building is an `Obstacle` plus an `Interactable` at the same spot; the
  hero walks up and presses the interact key; `Interactable.used` is the
  one-use flag; `SpecialLocations.use` dispatches by kind
  (`locations.py:65`); buff kinds are data in `data/world/buildings.json`,
  validated by `content._check_buildings`, placed 2–5 per combat island by
  `world/gen/buildings.py`.
- The Forge (`locations.py:125`) is the working template for "pick a weapon,
  then pick from cards": it pushes `LevelUpState` with `weapon_rows` (the
  picker rail in `ui/forge_rail.py`) and `offers_for`, cancelable.
- **A "monastery" already exists**: it is the village town hall obstacle
  (`data/world/terrain.json`, five colour skins, art under
  `assets/buildings/<colour>/monastery.png`), one per village, protected by
  the village seating pass and never moved. It has no interaction today.
- The shrine / altar / treasure / merchant facilities are parked, not
  deleted (`SPECIAL_KINDS = ()`); they are not needed here.

### Run state, ledger, screens

- `Run` (`core/run.py`) is rebuilt per run; a new field is automatically
  exposed on `PlayingState` and needs no teardown. That is where
  `unlocked_elements` goes.
- `RunLedger.record(amount, source)` keys by source string. Per-weapon rows
  and "other" rows exist; there is no second dimension for "effect".
  `Rewards.snapshot_summary` feeds `ui/run_summary.py`, whose columns are a
  registry (`_COLUMNS`) with a tight width budget (weapons column min 498 px,
  other rows capped at 2, must fit 1280×720 for the web build).
- The run-status screen (TAB) has a Build pane per weapon with a Forge
  before/after diff; an infusion line fits there.

### Effects, particles, dev mode

- `systems/particles.py` is a pooled circle-particle system capped at
  `MAX_PARTICLES = 1200`; at the cap `burst` silently drops. No LOD, no
  distance cull, no per-source quota. `TransientFx` (`core/effects.py`) owns
  the transient lists; `enemy_explosion` is the nearest thing to a reaction
  blast; the renderer already tints enemy frames (hurt flash).
- Reserve art: a `fire_aura` sheet is cut and parked for a burn ring
  (`assets_journal.md`), and the removed Thunder Orb's `thunder_aura` rig is
  still declared in `data/weapons/weapon_sprites.json`. Status rings are off
  by default on sprited enemies (`config.SHOW_ENEMY_STATE_RINGS`).
- Dev mode: `DevMenuState` is a row list (`_ROOT_ROWS`, pages built from live
  data), `DevFlags` hold the toggles, `report_debug` feeds the F1 overlay by
  `set_metric`, `devtools/overlays.py` holds the world-space overlays. The
  "Attacks deal 0 damage" toggle skips on-hit statuses and must also skip
  element application. There is no JSON hot reload; `Content` is a
  process-wide singleton.

## Confirmed reading and deviations from the design

Where the design's suggested shape and the code base disagree, this is the
reading proposed for the build. Items marked **[DECISION]** need the owner's
answer before that milestone starts.

1. **Statuses ride the existing framework.** New `StatusType` rows rather than
   a parallel `StatusList`: `fire_burn` (dot, refresh), `ice_slow` (slow,
   stacks, potency × stacks — one extension to the slow family), `freeze`
   (stun family, so `is_stunned()` and the no-bite rule apply for free),
   `frostburn` (a dot row plus a slow row applied together, or one compound
   family). Distinct ids keep the blessing statuses (`burn`, `chill`) as
   plain statuses that never bind to an aura. "Bound to aura" is a flag on
   the active entry that the aura's end clears.
2. **Timers.** Statuses keep the frame-decrement clock they have (it already
   handles the LOD and hibernation). Auras and locks use the run clock
   (`stats["time"]`), as `recent_hits` and the ledger do.
3. **No hit queue in the first pass.** Hits are already resolved in one
   deterministic pass per frame, one enemy at a time, so the element
   resolution runs inline at the hit site. `maxReactionsPerFrame` becomes a
   counter on the resolver that defers a reaction to the next frame; a real
   queue is added only if the stress test asks for it.
4. **Python, not C.** Element ids are a small `IntEnum`; the reaction table is
   a 5×5 tuple of baked variant configs; tracking uses dicts keyed by
   `(weapon, effect)` on the ledger, not numeric arrays; visited sets per
   chain are `set` of `id()`. The "no allocations / no strings in the hot
   path" guidance is applied where it matters (no JSON reads, no per-hit
   merging, no per-frame status scans) and not where Python makes it moot.
5. **Data files.** `data/weapons/elements.json` (the four elements plus the
   global block: `globalReactionAuraCooldown`, `maxReactionsPerFrame`,
   `maxActiveWindAreas`) and `data/weapons/reactions.json` (six reactions
   with `triggeredBy` overrides), instead of one file per element, matching
   the one-file-per-concern layout. Element and reaction config is content:
   a missing or unknown key raises at boot like a bad weapon entry. Enemy
   `elementProfile` overrides are enemy data: resolved once per run,
   fail-soft, logged, never fatal.
6. **Damage scaling (confirmed 2026-09-21, design open item 11).** Element
   and reaction damage values are **fractions of the triggering hit's
   damage** (the existing `_on_hit_frac` convention), so infusions scale
   with the weapon's blessings and the ×1.15-per-level yardstick keeps
   meaning; a per-effect `flat: true` flag switches a value to a flat number.
7. **Element application is per-weapon metadata, and summons are infusable
   (owner's correction, 2026-09-21).** The design's single `elementInterval`
   counter becomes an `element_application` block on every `weapons.json`
   entry, summons included, that says *how* the weapon inflicts its
   element:
   - `{"mode": "attack", "interval": N}` — the attack counter of §6.3:
     `0` every attack, `N` one element attack then N plain ones. Decided in
     `_begin_attack`; every hit of that attack shares the flag, stamped on
     its projectiles at spawn.
   - `{"mode": "time", "window": T}` — one element application per T
     seconds: the first hit the weapon lands after the window has elapsed
     carries the element and restarts the window; every other hit is plain.
     Checked at hit time (one timestamp comparison on the run clock), so
     re-hitting sources — the Ember Ring orbiters, the Pinball ball, summon
     bites and bolts, crater ticks — get a sensible rule without a notion of
     "attack".
   The counter or timestamp lives on the `Weapon`; summons and their
   projectiles reach it through `weapon_id`. Split Arrow children inherit
   their parent's flag. The default mode per weapon is data, not code: the
   Sword, Daggers, Hammer, Bow, Rod and Bomb ship in attack mode, the Ember
   Ring, Grave Totem and Spirit Wolf in time mode.
   *Reading to confirm:* "window of time" is read as **one application per
   window**, not "every hit inside the window carries the element".
8. **The Monastery is the village town hall (confirmed 2026-09-21).** The
   existing `monastery` obstacle (one per village island, so one or two per
   world) gets an interactable and the Forge-style picker: first an element
   card row (all four, always), then the weapon rail; spent after one use.
   This reuses placed art and the protected seating instead of inventing a
   new special island.
9. **Elemental buff buildings grant both (confirmed 2026-09-21).** An
   elemental building still grants its buff, and additionally opens the
   weapon rail for the rolled element (a second overlay after the buff
   feedback). Weights live in `buildings.json` under a new `elements` block.
10. **Modifiers layer (§2.4) is built but has no content.** The Ember / Tide /
    Storm / Grave blessing families were deleted "until the elemental system
    is implemented" and are to return as infusion-layered cards; designing
    those cards is a separate request. The effective-config cache (per
    element, dirty flag) ships with dev-mode editing as its only writer.
11. **Bosses.** With `weight = inf` and a no-op `apply_knockback` the boss
    already ignores every shockwave. Freeze on bosses is decided by the
    profile (`freeze.enabled`) in `bosses.json`, not by the Hammer's
    `stun_immune` flag, which stays what it is.
12. **Aura visuals.** Baseline is a per-element tint of the sprite (the hurt
    tint path) plus a small marker; particles are a second layer under a
    per-element global cap, so 100 auras never exceed `MAX_PARTICLES`.

## Conflicts with existing documentation to resolve in the same work

- `documentation/designs/six_weapon_system_design.md` §16 ("do not design the
  elemental system yet"), §21 (elemental blessings deleted until it exists),
  §22 decision 11 (element affixes removed; they stay removed) need a dated
  supersession note pointing here.
- `documentation/designs/combat_calculations.md` states "there is no
  elemental-resistance layer" and lists the five statuses; both change.
- `README.md` advertises "5 status effects"; the list grows.
- `documentation/plans/weapon_system_plan.md` lists elements as out of scope.
- `tools/gen_weapon_tables.py` must learn any new per-weapon column
  (`element_interval`) or its regeneration drops the hand-written sections.

## Todo list

Ordered by the design's milestones. Each milestone leaves the game playable
and its tests green before the next starts.

### M0 Discovery — done in this entry

- [x] Audit weapons, hit pipeline, enemies, particles, run lifecycle, JSON
      loading, dev mode. Report conflicts (above).
- [x] Owner answered items 6, 7, 8, 9 on 2026-09-21 (recorded above); the
      design's open items 1–13 stand at their proposals unless changed.
- [ ] Owner confirms the "one application per window" reading of time mode
      (item 7).

### M1 Core (`combat/elements/` package) — built 2026-09-21

- [x] `ids.py`: `ElementId` IntEnum (None=0, Fire, Ice, Thunder, Wind) and
      `ReactionId` (Frostburn, Overload, Superconduct, FireWind, IceWind,
      ThunderWind), with `key` names for data and logs. Effect ids for
      tracking move to M2 with the ledger work.
- [x] `schema.py`: the tiny schema language (`Section` of `Field`s; `f`, `i`,
      `b`, `dmg`). Validates (required keys, no unknown keys, ranges, open
      lower bounds, comment keys ignored), bakes to `namedtuple` records,
      names every leaf by a dotted path, `partial` validation for overrides,
      `deep_merge` for variants. A damage value is `{"frac": x}` or
      `{"flat": y}` and bakes to `DamageSpec.resolve(hit_damage)`.
- [x] `config.py`: the taxonomy — `GLOBAL`, one schema per element, one per
      reaction, `REACTION_PAIRS` (which pair produces which reaction is code,
      not data), `check_elements` / `check_reactions` / `variant_data`.
- [x] `data/weapons/elements.json` (global block + four elements) and
      `data/weapons/reactions.json` (six reactions, optional `triggered_by`
      overrides). `game/content.py` loads both after `items.json`; an
      `ElementDataError` becomes a `ContentError` at boot.
- [x] `modifiers.py`: `Modifiers` per element and per reaction, `(base +
      flat) × mult` per leaf path, per-source bookkeeping so a source can be
      removed exactly, one dirty flag each, clamped back into the leaf's
      range and type on rebake.
- [x] `registry.py`: `ElementRegistry` — element objects in a tuple indexed
      by `ElementId`, `config(element)` cached until a modifier changes,
      `reaction(aura, incoming)` on a 5×5 tuple, `reaction_config(reaction,
      trigger)` with both variants baked per reaction, `clear_modifiers()`,
      `get_registry(content)` cached per content object like the catalog.
- [x] `base.py`: `Element` interface (`apply_initial_effect`,
      `on_aura_applied`, `on_aura_refreshed`, `on_aura_ended`) with no-op
      defaults and `AuraEnd` reasons; the registry holds placeholder
      instances until M3 registers the four real classes.
- [x] `tests/combat/test_elements_config.py` (unit tier, 39 tests): ids,
      the schema language, the shipped files, element and reaction
      validation, directional variants, modifiers, the registry.

Key names: the shipped JSON uses the project's snake_case. Design →
data: `globalReactionAuraCooldown` → `global.reaction_aura_cooldown`,
`maxReactionsPerFrame` → `global.max_reactions_per_frame`,
`maxActiveWindAreas` → `global.max_active_wind_areas`, `aura.duration`
unchanged, `fire.damage` → `fire.hit.damage`, `burn.tickDamage` →
`fire.burn.tick`, `burn.tickInterval` → `fire.burn.tick_interval`,
`slow.percentPerStack` → `ice.slow.percent_per_stack`, `slow.maxPercent` →
`ice.slow.max_percent`, `freeze.stacksRequired` →
`ice.freeze.stacks_required`, `freeze.immunityDuration` →
`ice.freeze.immunity_duration`, `freeze.knockbackContactDamage` →
`ice.freeze.contact.{enabled,damage}`, `chain.*` → `thunder.chain.*` with
`targetsPerJump` → `targets_per_jump`, `maxRange` → `max_range`,
`maxTargets` → `max_targets`, `wind.damage` → `wind.hit.damage`, `area.*`
→ `wind.area.*`; reactions: `triggeredBy` → `triggered_by`,
`lockAuraSlot` → `lock_aura_slot`, `lockDuration` → `lock_duration`,
`shockwaveRadius` → `shockwave_radius`, `shockwaveDamage` →
`shockwave_damage`, `bonusJumps` → `bonus_jumps`, `slowPercent` →
`slow_percent`, `slowDuration` → `slow_duration`, `burnTickDamage` →
`burn_tick`, `burnDuration` → `burn_duration` (plus
`burn_tick_interval`), `stacksPerContact` → `stacks_per_contact`,
`strikeTargets` → `strike_targets`, `strikeDamage` → `strike_damage`,
`strikeRange` → `strike_range`. Every damage value is a `frac`/`flat`
object (decision 6). The Wind reactions carry the Wind-area keys
(`duration`, `radius`, `damage`, `knockback`, `max_range`, `max_targets`)
directly. Overload also has `max_knockback_speed` (design §5.5 proposal).

### M2 Aura and status

Three decisions confirmed on 2026-09-21, before the build:

- **Fire and Ice reuse the existing `burn` and `chill` statuses** rather
  than taking elemental ids of their own. I had recommended separate ids so
  that consuming a Fire aura could never cancel a burn the Ember Ring's
  Scorch applied; the owner chose reuse, for fewer statuses on screen. Two
  consequences follow, and both are implemented deliberately:
  - The `bound_to_aura` flag follows the **most recent application**. A
    blessing re-applying `burn` on a Fire-aura'd enemy takes the status
    over, so it survives the aura being consumed. Fire re-applying over a
    Scorch burn likewise binds it. Last applier owns it.
  - **The freeze stack counter lives on the enemy's elemental state, not on
    the `chill` status.** The design puts Ice's stacks on the slow status,
    but `chill` is refresh-only with one stack, and turning it into a
    stacking status would make the Grave Totem's Chilling Bolts start
    freezing enemies. Keeping the counter beside the aura preserves the
    blessing exactly, and reactions that apply slow without an aura
    (IceWind) can still bump it.
- **Freeze is a new status row inside the existing `stun` family**, so the
  no-movement and no-contact-bite rules in `Enemy.update` work unchanged
  and `is_stunned()` covers it. Accepted side effect: the Bomb's
  Demolitionist blessing, which pays extra against stunned targets, pays
  against frozen ones too.
- **Enemy profiles ship as machinery only.** No enemy or boss carries
  overrides yet; every one uses the shared default. Real values are
  authored in M9, once elements deal damage worth tuning against.

Frostburn follows from the reuse decision: it applies `burn` at its own
stronger tick values and `chill` at its slow percent, both standalone
(never aura-bound), for its duration, plus the extended aura lock. It
therefore cannot freeze, since freezing counts Ice applications only.

- [x] `combat/status.py`: a `freeze` row in the `stun` family; a
      `bound_to_aura` flag on active entries that follows the most recent
      application; `end()` / `end_bound()` / `is_bound()` so an aura can take
      its status with it; `set_potency()` (Ice recomputes its slow from the
      stack count, and `apply` only ever raises a potency); `remaining()` for
      the inspector; `apply` returns the new stack count. An entry may also
      name the `effect` its ticks are credited to, and `update` passes it as
      a **third argument only when it is set**, so every existing
      `(amount, source)` tick callback keeps working untouched.
- [x] `aura.py`: `ElementalState` (aura, expiry, lock, source weapon, Ice
      stacks, freeze immunity) on `Enemy` and `Boss`, carried through
      hibernation beside the status object. Auras expire **lazily** by
      timestamp comparison: a bound status is applied with the aura's own
      duration and expires on its own clock at the same instant, so nothing
      scans the enemy list per frame.
- [x] `resolve.py`: the five-step resolution with the locked-slot path
      (`ctx.bound = False`, so Fire and Ice apply standalone statuses), the
      global cooldown and `max(global, lock_duration)`, the per-frame
      reaction budget with deferral, and `alive` checks throughout. The
      resolver owns the binding contract itself (`status.end_bound()` on a
      consumed aura) rather than trusting each element to remember.
- [x] `profiles.py`: the `elementProfile` whitelist (element and reaction
      leaf overrides, damage and knockback multipliers, effect toggles),
      one shared `DEFAULT` for types without overrides, resolved once per
      run, fail-soft and logged. `aura.enabled = false` reuses the
      locked-slot path, so reaction immunity needs no branch of its own.
      The registry bakes per (config, profile) and caches it, so a profile
      costs one dictionary lookup per hit and never a merge.
- [x] `tracking.py` + `RunLedger`: `record(amount, source, effect=None)`
      keeps the per-source totals untouched and files a second dimension in
      `ledger.elements` -- `damage[(weapon, effect)]`,
      `applications[(weapon, element)]`, `reactions[(weapon, reaction)]` --
      so `ledger.total` still equals `stats["damage_dealt"]` and the smoke
      test's pin holds. An application is counted on every path where the
      element landed, including a locked slot and a reaction, so it is the
      count of element-carrying hits.
- [x] `Run.unlocked_elements` (a set, run-scoped by construction) and
      `Run.elements` (the resolver, built by `runtime.build_resolver`).
      `_phase_combat` calls `begin_frame` before any hit resolves.
- [x] Dev tools: an "Aura inspector" toggle drawing each enemy's aura ring,
      its remaining time, the lock, the Ice stacks and every status with its
      stacks (a `*` marks one bound to the aura); a "Force aura..." page
      applying any of the four elements to the nearest enemy **through the
      real resolver**; `auras` and `reactions` lines on the F1 overlay.
- [x] Tests: `tests/combat/test_elements_aura.py` (50, unit) and
      `DevAuraMenuTests` in `tests/flows/test_dev_mode.py` (7, integration).

Deferred to M3, deliberately: the `no_damage` dev toggle skipping element
application. Nothing applies an element at hit time yet, so there is nothing
for it to skip; it goes in with the hit-site wiring.

Element hooks changed shape during the build. `on_aura_applied` and
`on_aura_refreshed` collapsed into one `on_applied(target, ctx)`, because
the resolver already hands over a context and the two flags on it
(`ctx.bound`, `ctx.refreshed`) say everything the two hooks did, including
the locked-slot case that neither of them covered. `apply_initial_effect`
lost its redundant `source` parameter for the same reason.

### M3 Base elements — built 2026-09-21

- [x] `world.py`: the four things an element needs from the running game --
      `deal`, `nearest`, `knock`, `add_area` (plus `add_arc` for the
      placeholder jump lines). `RunWorld` is the real one, `NullWorld`
      records for the tests. Elements never touch `PlayingState`, and
      elemental damage goes through the ordinary `take_damage`, so the
      ledger, the DPS meter, the dummy's invulnerability and
      `stats["damage_dealt"]` all see it.
- [x] `fire.py`: hit damage, then a burn bound to the aura. It reuses the
      existing `burn` row with `add_stack=False` (Fire refreshes, never
      stacks) and its own `tick_interval` from the data, so the Ember Ring's
      Scorch keeps stacking to five on the type's own 0.5 s.
- [x] `ice.py`: no hit damage; a stacking slow recomputed from the stack
      count and capped, a freeze at the threshold that spends the stacks and
      starts an immunity window, and the frozen-contact rule. An enemy that
      cannot be frozen (immune, or profile-disabled) keeps its stacks
      *clamped* at the threshold rather than spending them, so its slow sits
      at full depth instead of sawtoothing.
- [x] `thunder.py`: the breadth-first jump tree with `targets_per_jump`,
      `jumps`, `max_range`, `max_targets` and per-level falloff. Every node
      goes back through the resolver, so a jump obeys the same rules a
      direct hit does; `ctx.chain` is what stops a node branching a tree of
      its own.
- [x] `wind.py` + `area.py`: the `WindArea` component -- follows the enemy
      it formed on, sweeps at 10 Hz rather than per frame, contacts each
      body once, knocks radially, and takes a swappable payload for the
      three Wind reactions in M5. The enemy it formed on is excluded from
      its own area.
- [x] `SpatialGrid.nearest(x, y, count, radius, exclude)`: a grid query plus
      a partial sort (`heapq.nsmallest`), which is what every jump level,
      Superconduct spread and ThunderWind strike will ask.
- [x] `CombatResolver.apply_element`: the single hit-site hook, inside the
      existing `no_dmg` guard so the dev "attacks deal 0 damage" toggle
      silences elements exactly as it silences on-hit statuses (the item M2
      deferred). `Projectile.element` carries the attack's element; nothing
      sets it until M6.
- [x] Frozen contact damage off the bump pass, using the game's existing
      bite formula (`contact_damage x contact_interval`) rather than a new
      one, once per body per slide, credited to whoever shoved the frozen
      enemy and falling back to whoever froze it.
- [x] `visual/element_fx.py`: placeholder aura rings, tornado circles and
      jump arcs, drawn in every run (M8 replaces all of it).
- [x] Tests: `tests/combat/test_elements_base.py` (58) and
      `tests/combat/test_elements_hit.py` (9). `tests/combat/fakes.py` now
      carries a real resolver and a ledger, so the hook can be driven
      without booting a world.

Two behaviours worth knowing, both correct and both surprising the first
time they are seen on screen:

- **A Thunder chain eats the auras it lands on.** A jump into an enemy
  holding a different element consumes it and reacts instead of dealing
  jump damage, and that branch stops. Firing Thunder last into a crowd is
  how the other three elements stay visible in a screenshot.
- **An enemy the weapon hit itself kills never reaches its element.** The
  element resolves after the base damage, and a dead target is skipped, so
  a heavily-infused weapon that one-shots trash leaves no aura on it.

### M3 Base elements (original plan)

- [ ] `fire.py`: hit damage, Fire aura, bound Burn (refresh, no stacking).
- [ ] `ice.py`: Ice aura, bound Slow stacks, Freeze at X stacks (stacks reset,
      aura stays), freeze immunity window, frozen enemies still knocked back
      (already true), optional frozen contact damage through
      `BumpResolver._bump` using the bite formula, once per enemy per
      knockback instance, no knockback transfer.
- [ ] `thunder.py`: breadth-first branching jumps with `targetsPerJump`,
      `jumps`, `maxRange`, `maxTargets`, `falloff`; per-node rule (no aura /
      Thunder aura → damage + aura + spread; other aura → reaction only, stop;
      locked → damage only, spread); visited set per chain.
- [ ] `systems/collision.py`: `nearest_n(x, y, n, radius, exclude)` on the
      grid (`heapq.nsmallest` over `query_circle`), used by Thunder,
      Superconduct and ThunderWind.
- [ ] `wind.py` + `WindArea` pooled component on `Run` (follows the inflicted
      enemy, ~1 s, 10 Hz contact checks, once per enemy per instance, radial
      knockback via `knock_split`, `maxActiveWindAreas` cap, payload
      callable). Damage goes straight to `take_damage` (never back into the
      element entry).
- [ ] `combat.py` hook: after the base hit, `elements.resolve(proj, enemy)`
      when the projectile carries an element.
- [ ] Placeholder visuals: tint per element, a ring for the Wind area, a line
      per jump.
- [ ] Tests: the §11 Thunder and Wind checks with seeded stubs from
      `tests/combat/fakes.py`.

## Ordering review: what an element does when its carrier dies (2026-09-21)

The owner asked, after M3, what happens when a weapon's base damage kills
the enemy that was carrying the element. Today: nothing. `apply_element`
runs after `take_damage` and the resolver bails on a dead target, so the
chain, the tornado and the reaction are all lost with the body.

**The rule the owner chose: outward effects only.** A dead carrier still
fires what reaches *other* enemies -- the chain jumps, the Wind area, and
the reaction with its shockwave or spread. Nothing is written to the body:
no aura, no status, and its share of the direct damage is dropped. The same
rule covers all three places the question arises, listed below. Kill credit
and damage attribution are untouched.

Three sites, all pinned as they are today in
`tests/combat/test_elements_death_order.py` so the change is a deliberate
edit to named assertions:

1. **The weapon's base damage kills.** The element does nothing at all,
   including a reaction the target's existing aura had already earned.
2. **The element's own damage kills.** Wind checks the target survived
   before seating its area, so a lethal Wind hit leaves no tornado. Fire
   has no such check and burns the corpse, which is the inconsistency the
   new rule tidies up.
3. **A Thunder jump kills a node.** That branch ends at the corpse.

### Why it matters, measured

Weapon damage against the shipped enemy HP, on the project's own
x1.15-per-blessing-level curve and the spawn director's x1.0 to x2.4 HP
ramp: an **unupgraded weapon one-shots 21 %** of the eighteen enemy types
at the start of a run, and a **fully upgraded one 46 %** (the Hammer, 67 %).
Killing blows are the common case, not an edge case.

Driving 300 infused hits into a refilled crowd of 24 through the real
resolver, comparing today's rule against the proposed one, counting only
what reached *other* enemies:

| Matchup | Killing blows | Recovered by the new rule |
|---|---|---|
| Unupgraded Sword vs mid-run common | 143 of 300 | 47 % of jumps, 30 % of tornadoes, 45 % of reactions |
| Upgraded Sword vs mid-run common | 144 of 300 (Wind) | 48 % of tornadoes; **every** reaction |
| Upgraded Hammer vs mid-run common | 300 of 300 | **100 % of everything** |
| Upgraded Sword vs run-end elite | 41 of 300 | 10 to 25 % |

The pattern is the problem: the loss scales with the hero's damage, so the
elemental system fades out exactly as a build comes together. Against a
fully upgraded Hammer it stops working entirely on common enemies, while
still working on elites -- which reads as random from the player's seat.
The sharpest single figure is a fully upgraded Sword carrying Thunder into
Fire auras: **0 of 300 reactions fire today**, because the hit that should
set off the Overload kills the enemy holding the Fire aura instead.

### Implemented, 2026-09-21

The resolver no longer refuses a dead target. It computes `carrier_dead` at
entry, puts it on the `HitContext`, and gates only the writes:

- `_land` still calls `apply_initial_effect`, so the chain, the tornado and
  the reaction all run. The element's own damage to the body is dropped
  with no extra code, because the world already refuses damage to a dead
  target.
- Setting or refreshing the aura, and every `on_applied` call, are gated on
  the target being alive. **The test is taken after the initial effect, not
  before it**, so an element whose *own* damage finished the enemy writes
  nothing either -- which is what closed site 2 for Fire as well as Wind.
- A reaction fires as normal. The aura the body was holding is what earned
  it, and the blast is owed to the enemies around it.
- `Wind.apply_initial_effect` lost its aliveness guard; an area anchored to
  a corpse simply stays where the body fell.
- `Thunder.spread` lost its frontier guard: a node the jump killed still
  arcs onward, because the chain needs only where it was standing. Nothing
  ever *targets* a corpse, since `world.nearest` returns the living.
- `begin_frame` no longer drops a deferred reaction whose target died while
  it waited.

New `Outcome.OUTWARD` reports the case, and `ResolverStats.corpse_hits`
counts it for the debug overlay. A hit on a corpse still counts as an
application, because it did something.

Re-measured with the rule live, against the same trials: the unupgraded
Sword recovers 37 % of its jumps, 48 % of its outward damage and 30 % of
its tornadoes; Thunder into Fire auras recovers 44 % of reactions and all
of its jumps; the fully upgraded Hammer on common enemies goes from zero
to 600 jumps and from zero to 9 072 outward damage over 300 hits. The
measurement script was throwaway and not kept; its method is recorded
above.

This supersedes the design's §3.4 reading that a death mid-resolution stops
the chain. The *safety* half of that rule is unchanged and still holds: no
effect dereferences a stale enemy, liveness is checked rather than assumed,
and nothing targets a corpse. What changed is that a dead body is a valid
waypoint rather than a dead end.

Fifteen tests in `tests/combat/test_elements_death_order.py` cover the rule
at all three sites, and four elsewhere were inverted with the reason named
in each assertion: two in the M2 aura tests, one in the element behaviour
tests, one at the hit seam. Full suite: **2977 passed, 1 skipped**.

### M4 Reactions — built 2026-09-21

- [x] `combat/elements/spread.py`: the breadth-first jump tree, extracted
      from Thunder because Superconduct walks the same one. Both differ only
      in what they do on arrival, so the walk is shared and the arriving is
      a callback. Thunder's behaviour is unchanged by the extraction.
- [x] `reactions/base.py`: the `Reaction` interface plus the two rules none
      of them may break, both enforced by construction rather than a flag.
      A reaction calls `ctx.deal` and writes statuses directly and **never
      re-enters the resolver**, so a secondary hit can leave no aura and
      reaction depth is exactly 1. `blast()` is the shared radial hit;
      `status_on()` returns nothing for a dead carrier, which is how the
      death rule reaches reactions.
- [x] `reactions/frostburn.py`: `burn` at its own stronger tick and `chill`
      at its slow percent, both standalone for the reaction's duration, and
      the aura slot held for as long as that lasts. It never freezes, and
      that needs no guard: freezing counts Ice applications, which live on
      the elemental state, which Frostburn does not touch.
- [x] `reactions/overload.py`: direct damage, then a shockwave that damages
      and shoves. The pinball behaviour is emergent -- the shove goes
      through the game's ordinary weight-split knockback -- and
      `max_knockback_speed` clamps the accumulated impulse so stacked
      blasts cannot fling a body off the island.
- [x] `reactions/superconduct.py`: direct damage, then a spread carrying
      **the slow alone**, no damage and no aura. "Further than Thunder" is
      defined rather than authored: the tree runs for
      `thunder.chain.jumps + bonus_jumps`, read off Thunder's live config,
      so a blessing that lengthens Thunder lengthens this too and no edit to
      `reactions.json` can make Superconduct the shorter of the pair. The
      schema's `bonus_jumps >= 1` guarantees the rest.
- [x] `reactions/__init__.py`: the dispatcher `ElementalResolver.reaction_runner`
      is wired to. A reaction id with no entry is simply not run, which is
      how M5's three sit unimplemented without breaking a run that triggers
      them.
- [x] Tests: `tests/combat/test_reactions.py` (32), including one pass
      through the real hit site so the wiring from two infused weapon hits
      to a bystander taking shockwave damage is covered end to end.

One collision worth recording, because it is invisible until it bites:
**Frostburn, Superconduct and Ice all write the same `chill` row.** Ice owns
its depth, recomputing it from its stack count on every application, which
is what lets the slow fall back after a freeze spends the stacks. So the two
reactions only ever *raise* it and never call `set_potency` to lower it, and
a later Ice hit may take the value back over. That is the accepted cost of
the owner's decision to reuse the existing statuses rather than give the
elements their own.

### M4 Reactions (original plan)

- [ ] `reactions/frostburn.py` (status + lock for its duration),
      `reactions/overload.py` (target damage + shockwave damage and radial
      knockback, `maxKnockbackSpeed` clamp on `_knock`),
      `reactions/superconduct.py` (target damage + Slow-only spread with
      `thunder.jumps + bonusJumps`, `bonusJumps ≥ 1`).
- [ ] Secondary hits never apply auras; reaction depth 1 enforced by
      construction (reactions call `take_damage`, not the element entry).
- [ ] Tests: both trigger directions, variant values, lock lengths, secondary
      hits leave no aura, Superconduct jumps exceed Thunder's.

### M5 Wind reactions — built 2026-09-21

All three are the §4.4 Wind area from M3 with a different payload, so the
milestone is mostly payloads plus two correctness fixes the payloads forced
into the open.

- [x] **A secondary effect now asks the recipient's own profile**, not the
      profile of whoever set it off (`HitContext.allows_on`). This was wrong
      from M4 and would have stayed hidden until a boss with a disabled
      effect stood next to a reacting trash mob. A tornado sweeps commons
      and elites together, which is where it would have shown first.
      `blast()`, Superconduct's spread and the Wind area all use it now, and
      the area carries the lookup because it outlives the context that made
      it.
- [x] **Ice's stack model moved into `ice.add_stacks`**, shared with
      IceWind, because the design asks for its stacks to behave exactly like
      Ice's own -- freezing included. Left to itself it also looks the config
      up per body, so each keeps its own freeze threshold.
- [x] `reactions/firewind.py`: the area plus a standalone burn on every
      contact, credited to FireWind rather than Burn so the summary can tell
      the two apart. Standalone matters here: the bodies it lands on are
      bystanders holding auras of their own, which it must not disturb.
- [x] `reactions/icewind.py`: the area plus `stacks_per_contact` Ice stacks
      through `add_stacks`, which answers design open item 7 -- they can
      freeze, because they *are* Ice stacks.
- [x] `reactions/thunderwind.py`: the area plus a flat burst on the N
      closest bodies, a single nearest-N query rather than a jump tree. N is
      floored at what a base Thunder spread would reach
      (`targets_per_jump x (jumps + 1)`), read off Thunder's live config, so
      a buff to Thunder widens this too and it can never be the weaker of
      the pair.
- [x] Tests: `tests/combat/test_wind_reactions.py` (23), including one pass
      through the real hit site.

Three test bugs, all the same shape and worth recording because they will
recur when the Wind reactions are tuned: **priming with Wind seats a plain
tornado of its own before the reaction's**, and **priming with Thunder
spreads auras through its own chain**. A test that counts areas or auras
after a two-hit setup is counting the priming element's work as well as the
reaction's. The fix is to measure the delta across the triggering hit, or to
switch the priming element's own spread off.

### M5 Wind reactions (original plan)

- [ ] FireWind (standalone Burn payload), IceWind (Slow stacks payload, can
      freeze), ThunderWind (area + nearest-N strike through the reacting
      enemy, N floored at Thunder's reach).
- [ ] Tests: payload application, N closest by absolute distance, caps.

### M6 Weapon element

- [ ] `Weapon.element: ElementId = None` runtime field on every weapon,
      summons included; `element_application` block (`mode` + `interval` or
      `window`) added to every `weapons.json` entry and validated like
      `category` (a taxonomy of two modes in code, the numbers in data).
- [ ] Attack mode: decided in `_begin_attack`, the flag stamped on every
      projectile of that attack (`element` slot on `Projectile`, cleared in
      `reset`); Split Arrow children inherit it.
- [ ] Time mode: a `next_element_at` timestamp on the `Weapon`, checked at
      hit time in the resolver for any projectile whose `weapon_id` names a
      time-mode weapon (orbiters, Pinball, summon bites and bolts, crater
      ticks all covered by the same test).
- [ ] `element_interval` / `element_window` as `weapon_bonus` fields so
      blessings can change them.
- [ ] Dev menu: a "Weapon elements" page (set / change / remove the element
      of each held weapon, edit its interval) following the four-edit pattern
      in `dev_menu_state.py`.
- [ ] Run-status Build pane shows the infusion; `weapon_visuals.json` gets an
      element tint hook so element-carrying shots look different.
- [ ] Tests: interval 0/1/N patterns across projectile counts and pierces,
      one element per weapon, replacement.

### M6 Weapon element — built 2026-09-21

This is the milestone that makes elements reachable in normal play: before
it, only the dev menu could put one on an enemy.

- [x] `element_application` on all nine weapons in `weapons.json`, validated
      in `Weapon.__post_init__` beside `category` and `class`. The two mode
      names are the only thing in code; every number is data. The Sword,
      Hammer, Daggers, Bow, Rod and Bomb are attack mode; the Ember Ring and
      the two summons are time mode, because orbiters and summons never fire
      an attack for a counter to count.
- [x] `Weapon.element`, plus `attack_element`, `take_element_window`,
      `element_interval`, `element_window` and `infused`. The attack-mode
      decision is taken once in `_begin_attack`, so one attack's projectiles
      and all their pierces agree and nothing is re-checked per hit.
- [x] Every spawn site of an attack stamps it: straight shots, the melee
      cone, both Forge shockwaves, the Hammer's blow, the thrown bomb.
      Everything derived from a projectile inherits it -- the bomb's blast,
      its cluster bomblets, Split Arrow's children -- because §6.3 says every
      hit an attack produces shares its flag.
- [x] `CombatResolver.element_for`: the stamp when there is one, otherwise
      the weapon's own window. That one method is what makes the re-hitting
      weapons work, and it is also how a summon's bolt finds its element --
      the summon spawns the bolt itself and never sees the weapon, so the
      hit site looks it up by id.
- [x] `element_interval` and `element_window_mult` as `weapon_bonus` fields,
      so a blessing can make a weapon inflict more often.
- [x] Dev menu "Infuse weapons...": one row per held weapon, ENTER cycles
      none to fire to ice to thunder to wind. One key rather than a second
      page, because the point is to try pairs quickly. The row shows the
      element and the cadence.
- [x] The run-status Build pane names the infusion in the element's own
      colour with how often it lands, which is the half of an infusion the
      numbers cannot show.
- [x] An element-carrying shot is tinted toward its element, mixed rather
      than replaced so a Fire-infused arrow still reads as an arrow.
- [x] Tests: `tests/combat/test_weapon_infusion.py` (28) and
      `DevInfuseMenuTests` in `tests/flows/test_dev_mode.py` (5), the last
      of which infuses a weapon through the menu and then lets the run tick
      until something on the field is carrying an aura.

The dev menu's root page finally outgrew its twelve-row window, which broke
a scroll test whose premise ("root: 8 rows") had been stale for several
milestones and was only passing because twenty key presses happened to wrap
back to the top. It now uses a genuinely short page, and a second test
covers the root page as the long page it has become.

Adding a required key to `weapons.json` broke six weapon tests built on a
hand-written definition, which is the validation doing its job: this project
treats a missing required field as bad data rather than defaulting it. The
fixture gained the block.

Starting cadences are placeholders for M9. They aim at roughly one
application a second per weapon: the fast Daggers inflict on one attack in
three, everything else on every attack, and the time-mode weapons every one
to one and a half seconds.

### M7 Acquisition

- [ ] `Run.unlocked_elements: set` and `snapshot_summary["unlocked_elements"]`.
- [ ] Elemental buff buildings: `buildings.json` `elements` block (chance,
      weights); roll at placement; after the buff, the weapon rail overlay
      (Forge template) assigns the element and adds it to the set.
- [ ] Monastery: interactable on the village monastery obstacle, element
      cards (all four) then the weapon rail, `used` after one pick, key
      marker and requirements message when the hero holds no infusable
      weapon.
- [ ] Run summary: an "Elements" line in the run column; game-over per-weapon
      rows unchanged (element damage is credited to its source weapon's
      total; the per-effect split is shown in the run-status and dev views).
- [ ] Tests: Monastery offers four, spent after one, assigns one element to
      one weapon; set never duplicates; a new run starts empty.

### M7 Acquisition — built 2026-09-21

- [x] `core/infusion.py`: the screen both sources share. It reuses the
      Forge's overlay rather than growing one of its own, because that
      overlay is already "pick one of these, then one of those": the
      Monastery puts the four elements on the rail and the weapons on the
      cards, and a source with the element already decided skips the rail.
      Each card says how often that weapon would actually inflict, which is
      the half of an infusion the numbers cannot show.
- [x] **The Monastery is the village town hall**, as decided: the `monastery`
      obstacle the village pass has always placed and nothing has ever used.
      No new building, no change to world generation, and the art is already
      there in five colours. One per village, offering every element
      whatever the run has unlocked, spent only by a completed pick -- ESC
      leaves it standing.
- [x] `core/elemental.py`: which buff buildings roll elemental, from a new
      optional `elements` block in `buildings.json` (validated at boot). The
      roll uses a generator seeded on the world seed **and the building's own
      spot**, not the run's shared stream, so it is stable for a seed without
      shifting every other roll in the run -- which is what would move the
      pinned world digests.
- [x] An elemental building gives **both**: its buff exactly as before, then
      the weapon picker for its element.
- [x] `Run.unlocked_elements` reaches the run summary, with an "Elements"
      line in the run column that says "none" rather than showing a blank.
      The per-weapon damage rows are untouched.
- [x] Tests: `tests/playing/test_infusion_sources.py` (21, integration).

Two things the Forge's screen needed before it could be shared. Its rail
heading was hardcoded to "REFORGE WHICH WEAPON", and its hint line offered
"to forge" whoever opened it -- so the Monastery's screen was telling the
player to forge a weapon. Both are now the caller's, with the Forge's own
wording kept as the default.

### M8 Visual system

- [ ] `game/states/playing/visual/elements/`: `profiles.py`
      (`ElementVisualProfile` per element: tint, particle preset, rigs),
      `component.py` (`ElementVisualComponent` for enemies, buildings,
      weapons), `aura_layer.py` (tint + marker; lock state visible),
      `status_layer.py`, `wind_ring.py`, `jump_arc.py` (pooled), reaction
      blends.
- [ ] Wire the parked `fire_aura` sheet and the `thunder_aura` rig; cut Ice
      and Wind equivalents from the reserve art.
- [ ] Particle LOD: per-element cap and a global element budget under
      `MAX_PARTICLES`, counted on the F1 overlay.
- [ ] Screenshot grid of every aura, status, lock and reaction on a crowded
      screen (milestone deliverable).

### M8 Visual system — built 2026-09-21

`game/states/playing/visual/elements/`, replacing the M3 placeholder
`element_fx.py`:

- [x] `profiles.py`: one `ElementVisualProfile` per element, loaded from a
      new `data/weapons/element_visuals.json` and validated at boot. The
      split is the one this project already uses -- `elements.json` tunes
      the gameplay, this tunes the look, and the resolver never reads it.
      **One animation clock per element, not one per aura**: a hundred
      burning enemies are a hundred blits of the same frame rather than a
      hundred `Animator`s ticking in parallel. Every aura of an element is
      therefore in phase, which is a uniformity worth the saving.
- [x] `markers.py`: a silhouette per element -- flame, shard, bolt, swirl --
      so none of this depends on telling orange from yellow (design §8,
      colourblind proposal). Shapes rather than glyphs, because a
      five-pixel letter is unreadable at this zoom and a five-pixel
      silhouette is not.
- [x] `layers.py`: the aura at a body's edge, the statuses above its head.
      Separate on purpose -- "primed with fire" and "burning" reading as one
      mark would make the whole reaction system guesswork. A locked slot is
      the same ring gone dim and thin.
- [x] `transient.py`: pooled jump arcs (kinked, with a per-arc seed so the
      wobble holds still for its lifetime), reaction flashes, and the
      tornado -- a ring at its true radius plus three arcs turning inside
      it, which is what tells it from every other circle on screen. A Wind
      *reaction*'s area is tinted toward the element it was paired with, so
      one component serves all four.
- [x] Reaction flashes are **blends of their two parents** (§8.5): the
      design's own starting point, and it means all six are distinguishable
      from each other and from either parent without six bespoke effects.
- [x] `budget.py`: elemental particles draw from their own per-frame
      allowance with a smaller per-element share, so a hundred auras cannot
      starve the hit bursts and death poofs of the shared pool. Over budget
      the auras keep their rings and stop shedding, which is the design's
      level-of-detail rather than a visible failure. Reported on the F1
      overlay beside the transient count.
- [x] The parked art is wired: Thunder's `thunder_aura` sheet, and the
      unused `flame_loop` strip cut as a 16-frame rig for the burning
      status (measured off the sheet's own empty columns: 752x75 is sixteen
      47-wide frames).
- [x] Tests: `tests/render/test_element_visuals.py` (23).
- [x] The screenshot grid the milestone asks for, delivered.

**The authored rig goes over the ring, not instead of it.** The first pass
drew Thunder's sheet in place of its ring, and the result was that three
elements announced themselves with a ring and the fourth did not. The sheet
is sparse lightning -- lovely, and not a shape that says "primed". Since an
aura is the only in-game sign of what an enemy will react to, the ring is
now drawn for every element and the art layers on top.

The first pass was also simply too faint over this game's pale stone
terrain. Ring alpha, width and marker size all went up after looking at the
grid, which is what the grid is for.

### M9 Performance and balance

#### What it costs

`spawn_stress.py` grew `--elements` (infuse three weapons and prime every
enemy) and `--element-rate N` (resolve N element-carrying hits a frame
straight through the resolver). The second flag exists because the first one
does not stress anything: three infused weapons on their own cooldowns land
**under two element hits a second** between them, so measuring the weapons
measures the weapons, not the system behind them.

| Run (seed 35, LOD 2) | update p50 |
|---|---|
| 100 live, no elements | 6.01 ms |
| 100 live, infused + every enemy primed | 5.93 ms |
| 100 live, 5 element hits/frame | 6.02 ms |
| 100 live, 20 element hits/frame | 5.77 ms |
| 200 live, no elements | 6.53 ms |
| 200 live, 60 element hits/frame (before tuning) | 7.19 ms |
| 200 live, 60 element hits/frame (after tuning) | **6.37 ms** |

60 element hits a frame is roughly **thirty times** what a real build
produces. At that rate, before the balance pass, the whole system cost about
0.66 ms on top of a 200-enemy frame; after it the difference against the
no-element baseline is inside the noise. The design's hard requirement (no
frame budget regression) is met with a wide margin.

The profile at 150 live / 30 hits per frame says where the time goes, and it
is exactly where the design predicted (11, "jump trees (branching)"):

```
17629/12016  0.605 cum  combat/elements/resolve.py:223(apply)
16878/11401  0.418 cum  combat/elements/resolve.py:290(_land)
 8471/2994   0.297 cum  combat/elements/thunder.py:54(apply_initial_effect)
 3177/3131   0.286 cum  combat/elements/spread.py:18(breadth_first)
      2994   0.268 cum  combat/elements/thunder.py:63(spread)
```

12,016 hits produced 17,629 applications: Thunder's chain adds about 47 %
more work than the hits themselves. It is already bounded -- `jumps` 1 and
`targets_per_jump` 2 make the tree at most two nodes, so `max_targets` 8 is
never reached and lowering it would change nothing. **No cap was changed for
performance.** The two that did change (`max_active_wind_areas` 12 to 6,
Overload's `max_targets` 12 to 6) were changed for balance and for how the
screen reads, and the 0.8 ms they gave back is a side effect.

`reaction_aura_cooldown` (1.0 s) and `max_reactions_per_frame` (8) also stay.
The cooldown is doing visible work -- at high rates the field holds only 7-9
live auras out of 200 bodies, because a reaction consumes an aura and locks
the slot -- and deferral (388 of 2128 reactions at the 30x rate) never
happens at a realistic one.

#### What an infusion is worth

`tools/benchmarks/element_bench.py` is new and answers the question the
placeholders were holding open. It drives a real run: one infused weapon
firing on its own cooldown into a standing crowd of ten, for 20 s, through
the ordinary hit pipeline, and reads the run ledger -- which already splits
damage by effect -- for the elemental share of the weapon's own output.

**The assumption behind the target, which is a judgement and not a
measurement.** The project's yardstick is that one weapon blessing level is
worth about +15 % (`blessing-yardstick-six-per-weapon`). An infusion is a
rarer thing than a blessing level: one Monastery per village, plus the
elemental buff buildings, so one or two in a run. It was sized at **about
+40 %** of the weapon's own damage in a crowd -- a major upgrade, worth
roughly two or three blessing levels, but not a second weapon. Two elements
in a build, which is rarer still and is the only way reactions happen, land
near **+50 %**. These are the numbers playtesting should argue with first.

Before (placeholders) and after, as a share of the weapon's plain dps:

| Element | before | after |
|---|---|---|
| Fire | +85 to +88 % | **+42 to +44 %** |
| Ice | 0 % (control only, by design) | 0 % |
| Thunder | +182 % | **+36 %** |
| Wind | +21 to +72 % | **+16 to +64 %** |

Fire and Thunder are flat across weapons, which is what "a fraction of the
hit" should give. Wind is not, and that is its character rather than a fault:
its tornado applies the element again to everything it catches, so a piercing
Bow gets 32 applications where a narrow melee cone gets 2, and its knockback
pushes a crowd out of a melee arc. Wind rewards weapons that touch many
bodies and punishes the Sword. That is a build decision, left standing.

Thunder was set *below* the others on direct damage on purpose. Its chain
spreads **auras** as well as damage -- 60 applications against Fire's 20 from
the same weapon -- and an aura is what a reaction needs, so Thunder is paid
twice if its direct number matches.

Ice deals no direct damage and was not touched: its payoff is the freeze,
which at 20 applications over 20 s is roughly four freezes and about a third
of the target's time locked down.

Reactions, measured on a two-element build (Rod + Bow, 18 dps plain):

| Pair | before | after |
|---|---|---|
| Fire + Ice (Frostburn) | +39 % | +39 % |
| Fire + Thunder (Overload) | **+162 %** | +58 % |
| Fire + Wind (FireWind) | +58 % | +52 % |
| Ice + Thunder (Superconduct) | +39 % | +39 % |
| Ice + Wind (IceWind) | +36 % | +36 % |
| Thunder + Wind (ThunderWind) | **+298 %** | +66 % |

Three of the six were already in band. Two were not, and both for the same
reason: a reaction that hits a *crowd* was priced as though it hit one body.
Overload's shockwave paid 0.40 of the hit to twelve targets, so one reaction
could deal 5.6x the hit that caused it; ThunderWind's tornado struck six
targets for 0.40 each, every tick of its life. Both were cut on damage *and*
on target count, which keeps the shape of the effect while pricing it.

#### The values that changed

`data/weapons/elements.json`

| Key | was | now |
|---|---|---|
| `fire.hit.damage.frac` | 0.25 | 0.12 |
| `fire.burn.tick.frac` | 0.10 | 0.05 |
| `thunder.chain.damage.frac` | 0.35 | 0.07 |
| `wind.area.damage.frac` | 0.10 | 0.07 |
| `global.max_active_wind_areas` | 12 | 6 |

`data/weapons/reactions.json`

| Key | was | now |
|---|---|---|
| `overload.damage.frac` | 0.80 | 0.30 |
| `overload.shockwave_damage.frac` | 0.40 | 0.10 |
| `overload.max_targets` | 12 | 6 |
| `firewind.damage.frac` | 0.15 | 0.12 |
| `firewind.burn_tick.frac` | 0.10 | 0.07 |
| `thunderwind.damage.frac` | 0.15 | 0.10 |
| `thunderwind.strike_targets` | 6 | 4 |
| `thunderwind.strike_damage.frac` | 0.40 | 0.06 |

The `element_application` cadences in `weapons.json` were measured and left
alone: they already separate the weapons sensibly (the Daggers' every-third
attack keeps a 0.4 s weapon from applying 50 times in 20 s, and the summons'
time windows are the only cadence they can have). The `elements.chance` in
`buildings.json` is a drop rate, not a damage number, and belongs to
playtesting rather than to a bench.

Neither bench asserts anything. A timing assertion would be flaky and a
damage assertion would pin a balance number into the suite, where the next
tuning pass would have to fight it.

#### One thing the bench had to learn

The first version measured the same weapon twice and got a tenth of the
damage the second time. Knockback and the collision separation walk a crowd
outwards over a 20 s run, and after one run the ring had drifted out of a
40 px melee arc. `reset()` now puts every body back on its starting spot with
its velocity and knock impulse cleared. Any future bench that reuses a crowd
across runs needs the same.

#### Documentation

- `six_weapon_system_design.md` 16 carries a superseded banner and 21 a note
  that elements came back as **infusions**, not as blessings, so the Ember /
  Tide / Storm / Grave deletion stands.
- `plans/weapon_system_plan.md` 4 no longer lists elements as out of scope;
  it says instead that they were built afterwards without reopening it.
- `combat_calculations.md` gains elemental damage as a second damage *source*
  (not a multiplier, and still with no resistance layer), and the note that
  the elemental burn and slow reuse `burn` and `chill`.
- `README.md` lists the four infusions and six reactions.
- `FUNCTIONAL_README.md` gains an elements section and `combat/elements/` in
  the layout tree.
- `tools/gen_weapon_tables.py` learned `element_cadence`, so every weapon's
  "Base:" line now ends with how often it inflicts. The generated doc was
  **hand-patched** rather than regenerated: its own drift warning says a
  rerun drops the hand-written sections, and it still would.

## Progress

- 2026-09-21: discovery done, proposal written, no code changed.
- 2026-09-21: owner confirmed the four decisions; summons become infusable
  and `elementInterval` becomes the per-weapon `element_application` block
  (attack mode or time mode). Ready to start M1.
- 2026-09-21: M2 built. The aura slot and its lock on every enemy and the
  boss, the five-step resolution with the reaction budget, enemy profiles,
  the per-effect tracking dimension on the ledger, and the dev inspector
  with its Force-aura page. 57 new tests (50 unit, 7 integration).
  Screenshot of the inspector over a dev run delivered to the owner: four
  elements ringed beside the hero, the Ice enemy showing its stack count,
  the bound statuses marked, and a fifth enemy already reacted and locked.
- 2026-09-21: M3 built. The four elements, the nearest-N grid query, the
  Wind area component, frozen contact damage, the hit-site hook and
  placeholder visuals. 68 new tests (59 element behaviour, 9 hook); full
  suite 2960 passed, 1 skipped. Screenshot delivered showing all four
  firing in a run, including a Thunder chain consuming two auras and a
  freeze outliving its own.

  One real bug was caught while reviewing the diff rather than by a test,
  and now has one: the bump pass shoves the hero as well as the enemies,
  so a frozen enemy sliding into the hero would have called
  `Player.take_damage` with a `source` and an `effect` it does not accept.
  Frozen contact is now restricted to the enemy-versus-enemy half of the
  pass, which is also what the design means -- a sliding enemy hurts other
  enemies, and the hero's own mitigation stays its own.
- 2026-09-21: M4 built. Frostburn, Overload and Superconduct, the shared
  jump tree extracted from Thunder, and the reaction dispatcher wired into
  the run. 32 new tests. Screenshot delivered showing all three firing at
  once: Frostburn holding the slot for four seconds against the others'
  one, an Overload's direct hit and shockwave, and Superconduct's slow
  spreading eight enemies deep without damage. Full suite: 3009 passed,
  1 skipped.
- 2026-09-21: M5 built. FireWind, IceWind and ThunderWind, plus two
  correctness fixes their payloads exposed: a secondary effect now asks the
  recipient's own profile, and Ice's stack model is shared rather than
  copied. All six reactions are now implemented. 23 new tests. Screenshot
  delivered showing the three tornadoes at once with their payloads. Full
  suite: 3032 passed, 1 skipped. Every one of the fourteen effect ids in
  `tracking.py` is now produced by live code.
- 2026-09-21: M6 built. Every weapon carries an element and its own
  application metadata in one of two modes, summons included. 28 new tests.
  Screenshot delivered of three seconds of ordinary play with an infused
  Sword, Bow and Rod: eighteen applications and five reactions with nothing
  forced, which is the first time the system has run itself. 33 new tests;
  full suite 3061 passed, 1 skipped.
- 2026-09-21: M7 built. The Monastery on the village town hall, elemental
  buff buildings that grant both their buff and their element, and the
  unlocked set on the run summary. 21 new tests; full suite 3087 passed,
  1 skipped. Screenshot delivered of the Monastery's picker.
- 2026-09-21: M8 built. The shared visual system replaces the M3
  placeholder: profiles from data, a silhouette per element, separate aura
  and status layers, pooled arcs and blended reaction flashes, the tornado
  with its turning arcs, and a particle budget of its own. The parked
  `thunder_aura` and `flame_loop` art is wired. 23 new tests; full suite
  3110 passed, 1 skipped. The milestone's screenshot grid delivered.
- 2026-09-21: M1 built. `combat/elements/` (ids, schema, config, modifiers,
  registry, base), the two data files, the content-loader hook and 39 unit
  tests. Full default suite: 2836 passed, 1 skipped (17 min). Nothing in the
  game reads the registry yet; M2 wires the aura state and the hit
  resolution.
- 2026-09-21: M9 done, and with it the build. Performance: the elemental
  system costs nothing measurable at any realistic load, and about 0.66 ms
  at thirty times one -- which the two caps cut for balance then gave back.
  No cap was changed for speed. Balance: `tools/benchmarks/element_bench.py`
  is new and measures what an infusion is worth by driving a real fight and
  reading the run ledger, rather than computing it. Every placeholder was
  over-tuned -- Fire +88 %, Thunder +182 %, Overload +162 %, ThunderWind
  +298 % -- and thirteen values across `elements.json` and `reactions.json`
  brought the elements to about +40 % of a weapon's own damage and the
  reactions to a 36-66 % band. The two outlier reactions were both priced as
  if they hit one body when they hit a crowd. Six documents superseded,
  `FUNCTIONAL_README.md` gained an elements section, and
  `tools/gen_weapon_tables.py` learned the element cadence column. Full
  suite: 3110 passed, 1 skipped -- no test moved, which is the right result
  for a tuning pass and confirms nothing in the suite pins a balance number.
  Screenshot delivered: four infusions at once, the Thunder chain's arcs,
  two tornadoes and five of the six reactions inside five seconds of
  ordinary play.
