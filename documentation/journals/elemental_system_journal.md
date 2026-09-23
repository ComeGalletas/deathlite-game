# Elemental system journal

**Legacy ID:** CMB-005 · **Systems:** CMB, RND · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

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
- [x] Owner confirms the "one application per window" reading of time mode *(DOC-003: confirmed by the owner 2026-09-22; the code already works this way, `take_element_window`)*
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
*(DOC-003: this plan was replaced by the "M3 Base elements — built" section above; its boxes are marked `[-]` so only open work reads `[ ]`.)*

- [-] `fire.py`: hit damage, Fire aura, bound Burn (refresh, no stacking).
- [-] `ice.py`: Ice aura, bound Slow stacks, Freeze at X stacks (stacks reset,
      aura stays), freeze immunity window, frozen enemies still knocked back
      (already true), optional frozen contact damage through
      `BumpResolver._bump` using the bite formula, once per enemy per
      knockback instance, no knockback transfer.
- [-] `thunder.py`: breadth-first branching jumps with `targetsPerJump`,
      `jumps`, `maxRange`, `maxTargets`, `falloff`; per-node rule (no aura /
      Thunder aura → damage + aura + spread; other aura → reaction only, stop;
      locked → damage only, spread); visited set per chain.
- [-] `systems/collision.py`: `nearest_n(x, y, n, radius, exclude)` on the
      grid (`heapq.nsmallest` over `query_circle`), used by Thunder,
      Superconduct and ThunderWind.
- [-] `wind.py` + `WindArea` pooled component on `Run` (follows the inflicted
      enemy, ~1 s, 10 Hz contact checks, once per enemy per instance, radial
      knockback via `knock_split`, `maxActiveWindAreas` cap, payload
      callable). Damage goes straight to `take_damage` (never back into the
      element entry).
- [-] `combat.py` hook: after the base hit, `elements.resolve(proj, enemy)`
      when the projectile carries an element.
- [-] Placeholder visuals: tint per element, a ring for the Wind area, a line
      per jump.
- [-] Tests: the §11 Thunder and Wind checks with seeded stubs from
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
*(DOC-003: this plan was replaced by the "M4 Reactions — built" section above; its boxes are marked `[-]` so only open work reads `[ ]`.)*

- [-] `reactions/frostburn.py` (status + lock for its duration),
      `reactions/overload.py` (target damage + shockwave damage and radial
      knockback, `maxKnockbackSpeed` clamp on `_knock`),
      `reactions/superconduct.py` (target damage + Slow-only spread with
      `thunder.jumps + bonusJumps`, `bonusJumps ≥ 1`).
- [-] Secondary hits never apply auras; reaction depth 1 enforced by *(DOC-003: retired later by the R38 cascade, CMB-006)*
      construction (reactions call `take_damage`, not the element entry).
- [-] Tests: both trigger directions, variant values, lock lengths, secondary
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
*(DOC-003: this plan was replaced by the "M5 Wind reactions — built" section above; its boxes are marked `[-]` so only open work reads `[ ]`.)*

- [-] FireWind (standalone Burn payload), IceWind (Slow stacks payload, can
      freeze), ThunderWind (area + nearest-N strike through the reacting
      enemy, N floored at Thunder's reach).
- [-] Tests: payload application, N closest by absolute distance, caps.

### M6 Weapon element
*(DOC-003: this plan was replaced by the "M6 Weapon element — built" section below; its boxes are marked `[-]` so only open work reads `[ ]`.)*

- [-] `Weapon.element: ElementId = None` runtime field on every weapon,
      summons included; `element_application` block (`mode` + `interval` or
      `window`) added to every `weapons.json` entry and validated like
      `category` (a taxonomy of two modes in code, the numbers in data).
- [-] Attack mode: decided in `_begin_attack`, the flag stamped on every
      projectile of that attack (`element` slot on `Projectile`, cleared in
      `reset`); Split Arrow children inherit it.
- [-] Time mode: a `next_element_at` timestamp on the `Weapon`, checked at *(DOC-003: shipped as planned: `Weapon._next_element_at`, `take_element_window`)*
      hit time in the resolver for any projectile whose `weapon_id` names a
      time-mode weapon (orbiters, Pinball, summon bites and bolts, crater
      ticks all covered by the same test).
- [-] `element_interval` / `element_window` as `weapon_bonus` fields so *(DOC-003: shipped as `element_interval` and `element_window_mult` bonus fields (`combat/weapons/core.py`))*
      blessings can change them.
- [-] Dev menu: a "Weapon elements" page (set / change / remove the element *(DOC-003: shipped as an "Infuse weapons…" row in the dev menu, not its own page)*
      of each held weapon, edit its interval) following the four-edit pattern
      in `dev_menu_state.py`.
- [-] Run-status Build pane shows the infusion; `weapon_visuals.json` gets an
      element tint hook so element-carrying shots look different.
- [-] Tests: interval 0/1/N patterns across projectile counts and pierces,
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
*(DOC-003: this plan was replaced by the "M7 Acquisition — built" section below; its boxes are marked `[-]` so only open work reads `[ ]`.)*

- [-] `Run.unlocked_elements: set` and `snapshot_summary["unlocked_elements"]`.
- [-] Elemental buff buildings: `buildings.json` `elements` block (chance,
      weights); roll at placement; after the buff, the weapon rail overlay
      (Forge template) assigns the element and adds it to the set.
- [-] Monastery: interactable on the village monastery obstacle, element
      cards (all four) then the weapon rail, `used` after one pick, key
      marker and requirements message when the hero holds no infusable
      weapon.
- [-] Run summary: an "Elements" line in the run column; game-over per-weapon
      rows unchanged (element damage is credited to its source weapon's
      total; the per-effect split is shown in the run-status and dev views).
- [-] Tests: Monastery offers four, spent after one, assigns one element to
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
*(DOC-003: this plan was replaced by the "M8 Visual system — built" section below; its boxes are marked `[-]` so only open work reads `[ ]`.)*

- [-] `game/states/playing/visual/elements/`: `profiles.py`
      (`ElementVisualProfile` per element: tint, particle preset, rigs),
      `component.py` (`ElementVisualComponent` for enemies, buildings,
      weapons), `aura_layer.py` (tint + marker; lock state visible),
      `status_layer.py`, `wind_ring.py`, `jump_arc.py` (pooled), reaction
      blends.
- [-] Wire the parked `fire_aura` sheet and the `thunder_aura` rig; cut Ice
      and Wind equivalents from the reserve art.
- [-] Particle LOD: per-element cap and a global element budget under
      `MAX_PARTICLES`, counted on the F1 overlay.
- [-] Screenshot grid of every aura, status, lock and reaction on a crowded
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

> **Superseded by M10, 2026-09-21.** The owner's rule is the opposite: where
> a sprite is wired the circle does not draw at all, and the marker goes with
> it. The reasoning above was sound about the *art* and wrong about the
> remedy. One sparse sheet is a reason to find better art, not a reason to
> prop it up with a procedural shape underneath -- and M10 found it, four
> whole shapes with their own silhouettes. The ring and the marker stay in
> the code as the fallback for an empty `assets/`, and the **locked** slot
> keeps its circle because it has no sprite, which is also what keeps
> "primed" and "cannot be primed" one glance apart.

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

## M10 Authored art for the elements and the reactions (CONFIRMED)

Requested and confirmed 2026-09-21. The owner asked for a survey of the
unused art for sprite effects that could carry the elements and the
reactions, and set four rules:

1. **Where an element has a sprite wired, the circle indicator does not
   draw.** The sprite is the whole indicator. The small element marker
   above the head goes with it -- confirmed explicitly; the four distinct
   shapes do the job the marker was doing.
2. **Reactions need a sprite effect too**, and it removes the circle in the
   same way.
3. **Element effects draw behind the enemy sprites** -- lower priority than
   the bodies they are attached to. **Reaction effects draw on top of
   everything else**, and stay brief so that sitting above the whole scene
   does not disrupt play.
4. **Each sprite is cut into its own file** rather than read out of the
   parent multi-row sheet at run time, under `assets/effects/elements/`
   and `assets/effects/reactions/`.

### What the reserve actually holds

Two packs, both already licensed, bundled and credited by this project.

**`assets/unused/unordered-effects`** -- 180 sheets, 64 px frames, laid out
as N columns by **9 rows, where the rows are nine colour variants of the
same animation**. This is the pack the magic rod's arcane circle, thunder
ball and thunder aura were already cut from, so `weapon_sprites.json`
already knows the shape of the wiring (`grid: [N, 9]` plus a `row`). The
nine rows are, in order: red/orange, violet, cyan, green, yellow/tan,
white, grey-purple, red, indigo. Every element's colour is in there, which
means **no recolouring script is needed** -- unlike the Grave Totem's bolt,
which had to be recoloured because a multiply tint cannot turn orange blue.

This is the pack to build on. It is deep in exactly the shapes an aura
wants: rings, spirals, vortices, radial bursts and rosettes.

**`assets/unused/Super Pixel Effects Gigapack`** -- the Fire, Lightning,
Fantasy Spells, Explosions, Impacts and Magic Bursts categories, in two
sizes and six to eight hues. Richer art, but almost all of it is a
**one-shot burst**: `fire_looping_001` is the only piece in the pack that
is authored to loop, and it is already in use as Fire's burn status. That
makes the Gigapack a good source for *reaction* bursts and for the freeze,
and a poor one for auras, which have to hold for three or four seconds.

### The picks

Shortlisted from the contact sheets, then **re-judged frame by frame**,
which changed four of them. A single frame at an effect's peak is enough to
shortlist and not enough to choose: an aura has to read across its whole
loop, and two of the first picks turned out to be a squiggle for most of
theirs.

One distinct **shape** per element rather than one shape in four hues -- an
element has to be readable without relying on colour (design 8, colourblind
proposal), and once the ring and the marker go the sprite is the only thing
carrying that.

| Element | Source | Row | Frames | Shape |
|---|---|---|---|---|
| Fire | `unordered-effects` Part 12/586 | 0 coral | 14 | a ring that grows flame tongues outward |
| Ice | Part 13/623 | 2 blue | 13 | a crystal that forms, then opens into a diamond outline |
| Thunder | Part 14/652 | 5 grey, remapped | 16 | a radial spiked discharge |
| Wind | Part 1/26 | 3 green | 14 | concentric rings turning -- the only pick that rotates |

| Reaction | Source | Row | Frames | Shape |
|---|---|---|---|---|
| Frostburn | Part 4/186 | 1 magenta | 12 | a violet sphere of motes, where fire and ice blend |
| Overload | Part 14/674 | 0 coral | 18 | a hexagonal detonation, the biggest of the six |
| Superconduct | Part 9/446 | 2 blue | 10 | an orbiting star coming apart |
| FireWind | Part 15/711 | 0 coral | 20 | one swirl in three colours: the three wind |
| IceWind | Part 15/711 | 2 blue | 20 | reactions *are* the same mechanic with |
| ThunderWind | Part 15/711 | 5 remapped | 20 | different payloads, and should read that way |

Plus the Gigapack's `spell_ice_001` (large blue, 40 frames) for the
**freeze** status: a block of ice that forms and shatters, which is what
freeze has always wanted to look like and what no procedural bracket over
the head was going to give it.

#### Thunder had no row

The pack's nine rows are coral, magenta, blue, green, brown, grey, mauve,
crimson and purple. There is no yellow one. Row 0's *highlight* is yellow
(`#fcf08d`) but its body is coral, and Fire wants that row -- two elements
cannot share a palette when the sprite is the only indicator left.

So Thunder takes the neutral **grey** row and is remapped. A grey ramp maps
onto a coloured one exactly, which is the whole reason it is the row to
take; recolouring the coral row instead would be the mistake
`recolour_totem_fire.py` was written to avoid.

Getting the ramp right took three passes, all of them visible in the
script's comments:

1. A per-channel multiply by a yellow triple. The grey row's commonest
   pixel is `#6f6f6f`, so everything scaled into **olive**.
2. A two-point gradient to a near-white light end with a gamma lifting the
   midtones. This source is thin strokes and most of its pixels are already
   light, so lifting them put everything at the light end: **cream**.
3. A two-point gradient between *saturated* ends with the gamma near 1 --
   `(140, 95, 10)` to `(250, 220, 40)`, gamma 0.8. Bright yellow with amber
   shading, and unmistakably not Fire's coral.

### What changes in code

Small, and mostly deletion.

- `visual/elements/layers.py:_aura` draws the ring, then the rig over it,
  then the marker. Rule 1 inverts that: **rig present, nothing else**. The
  ring and the marker stay for an element with no rig, which after this
  milestone means none of them -- but the fallback is what keeps the game
  playable with an empty `assets/`, so it stays wired, not deleted.
- The **locked** ring stays exactly as it is. "Cannot be primed" has no
  sprite, so by rule 1 it keeps its circle, which is also what makes locked
  and primed one glance apart.
- `visual/elements/transient.py:Flash` is the procedural reaction blast
  today. Rule 2 gives each reaction an optional rig; where one is wired the
  Flash does not draw at all, and the sprite plays in its place on the same
  pooled transient list with the same cap.
- `element_visuals.json` grows a `reactions` block beside `elements`, and
  each element's `aura_rig` stops being null.
- The status marks above the head (burn, chill, freeze) are a different
  layer and are not touched, except that freeze gains its `spell_ice_001`
  rig.

### What this reverses

M8 drew the ring for **every** element and layered the rig on top, on the
grounds that Thunder's authored sheet was sparse lightning that did not
read as "primed". That reasoning does not survive the new art: these are
whole shapes, not accents. The M8 note stands as the record of why the
ring was there; this supersedes it.

### The layer split

Today every elemental visual is one pass, `element_fx.draw`, immediately
after `_draw_world` and therefore above every character. Rule 3 splits it
in two by **meaning** rather than by module: a persistent state goes
behind, a momentary event goes in front.

```
_draw_world                      banded per terrace:
  for each level:                  ground band
    draw_ground_band                 flat effects  <-- auras, tornadoes,
    draw_flat_effects                                  arcs, status marks,
    <sprites of that band>                             shed particles
element_fx.draw_reactions        <-- reaction bursts, above everything
_draw_hostile_projectiles
particles / damage numbers
dev overlays, key marker, hints
--- HUD
```

The persistent half has to join the banded pass, which means it needs a
level per body the way `actor_items` already computes one (`scene.band`).
The reaction half stays a single late pass and moves *after* the
projectiles, the particles and the damage numbers, which is what "on top of
everything else" means in this paint order.

Status marks (burn, chill, freeze) go behind with the rest, per the rule.
They sit above the head, so a body standing behind can now occlude them; if
that reads badly in the milestone screenshot it is worth raising then
rather than pre-emptying the rule now.

### Cost

Nothing new per frame: a blit replaces a ring draw plus a marker draw, so
the aura layer gets *cheaper*. The sheets are 64 px and one `Animator` per
element is already shared across every aura of that element, so a hundred
burning enemies remain a hundred blits of one frame.

### Todo

**A. Cut the art** -- done. `tools/asset_pipeline/cut_element_effects.py`

- [x] A1. Reads the source packs and writes one single-row strip per
      effect. No run-time read touches a parent sheet or a `row` index.
      The reserve is a `--reserve` flag rather than a constant, because
      `assets/unused/` is gitignored and so a git *worktree* -- which is how
      this was built -- does not have one; the packs then live in the main
      checkout beside it.
- [x] A2. `assets/effects/elements/`: `fire.png`, `ice.png`, `thunder.png`,
      `wind.png`, `freeze.png`. Named by element, not by source, so nothing
      collides with the magic rod's own `thunder_aura.png`.
- [x] A3. `assets/effects/reactions/`: all six.
- [x] A4. Each strip trimmed on the **union** of its row's content, never
      per frame -- per-frame boxes would shrink the file further and put
      the frames out of register, which on a looping aura is a jitter no
      anchoring fixes. The anchor is the original 64 px frame's centre
      carried into the crop, because several of these animations are not
      symmetrical about their own content and drift as they play.
- [x] A5. `assets/CREDITS.md` gains usage entries for both packs. This also
      fixes an older gap: the magic rod's `arcane_circle`, `thunder_ball`
      and `thunder_aura` came from the same pack and had never been listed.

What the cut produced, which is the input to group B:

| file | frames | frame | anchor |
|---|---|---|---|
| `effects/elements/fire.png` | 14 | 64 x 64 | 32, 32 |
| `effects/elements/ice.png` | 13 | 58 x 58 | 29, 29 |
| `effects/elements/thunder.png` | 16 | 62 x 58 | 31, 30 |
| `effects/elements/wind.png` | 14 | 56 x 56 | 28, 28 |
| `effects/elements/freeze.png` | 40 | 87 x 93 | 44, 48 |
| `effects/reactions/frostburn.png` | 12 | 48 x 49 | 24, 25 |
| `effects/reactions/overload.png` | 18 | 64 x 64 | 32, 32 |
| `effects/reactions/superconduct.png` | 10 | 64 x 58 | 32, 29 |
| `effects/reactions/firewind.png` | 20 | 44 x 40 | 22, 21 |
| `effects/reactions/icewind.png` | 20 | 44 x 40 | 22, 21 |
| `effects/reactions/thunderwind.png` | 20 | 44 x 40 | 22, 21 |

**B. Wire the rigs** -- done.

- [x] B1. Eleven rigs in `weapon_sprites.json`. Single-row files, so no
      `grid` and no `row`, which was the point of the cut. The anim is
      named `loop` in all eleven because that is this project's convention
      for a rig's only animation -- `sword_slash_down` and `hammer_impact`
      are one-shots under the same name -- and the `loop` *flag* inside
      says whether it repeats. fps puts each aura's cycle near a second;
      freeze runs 40 frames at 27 fps = 1.48 s so the block shatters on the
      thaw; every reaction is under 0.7 s, because they draw over
      everything.
- [x] B2. `element_visuals.json`: every `aura_rig` filled, a `reactions`
      block, and `status_rig` replaced by a `statuses` block.
- [x] B3. `content.py` validates the new blocks, and a new
      `_check_element_rigs` checks that every rig a name points at is real.

#### `status_rig` had to become `statuses`

It was a field on an *element*, which only ever worked because Fire happened
to own the only authored status. Ice owns both `freeze` and `chill`, so one
field per element cannot hold them. Keying by **status id** instead matches
how `layers._marks` already decides what to draw, and it is the truer shape:
`burn` is shared with the weapon blessings, which have no element behind
them at all and still have to look the same.

`chill` is deliberately absent and falls back to its procedural chevron,
which is why this is a map with gaps rather than a required field.

#### A reaction burst is not an `Animator`

Auras share one clock per element -- a hundred burning enemies are a hundred
blits of one frame, which is the saving M8 was built around. A reaction
cannot work that way: two Overloads half a second apart are two separate
events and each has to start at its own first frame. So `ReactionBurst`
takes the frame by **progress** off the individual flash's age, clamped
rather than wrapped so overshooting the end holds the last frame instead of
snapping back to the first.

#### Rig validation was claimed and never done

`_check_element_visuals`'s docstring said "every named rig real" and the
code never checked it. It could not: the sprite files merge *after*
`element_visuals.json` loads. Now `_check_element_rigs` runs once they have,
and a name that resolves to nothing stops the boot -- which matters more
after M10 than before, because once the sprite is the whole indicator a typo
would leave a primed enemy with nothing drawn on it at all rather than
falling back to a ring.

#### Two M8 tests were replaced

`test_the_authored_rigs_load` asserted that Ice has *no* aura rig and that
Fire's status art hangs off Fire's profile. Both were true of M8 and neither
is true now. They are replaced by tests for what M10 actually promises: all
four elements have authored art, status art is keyed by status, every
reaction has a burst, and a burst is indexed rather than clocked.

`test_one_clock_per_element_not_one_per_aura` broke for a subtler reason
worth recording: it advanced the clock by exactly one second, and Thunder's
new rig is 16 frames at 16 fps, so it landed back on frame 0 and the test
asserted that a working clock was broken. It now advances by a third of a
second.

**C. Rules 1 and 2: the sprite is the indicator** -- done.

- [x] C1. `layers._aura` draws the rig and **nothing else** where one
      resolves; the ring and the marker are the `else` branch.
- [x] C2. The locked ring is untouched.
- [x] C3. `Flash` plays the authored burst where the reaction has one, and
      falls back to the blend of its two elements where it does not.
- [x] C4. `markers.py` kept: it is still the fallback, and the chill
      chevron is drawn from it.
- [x] C5 (added). Freeze stopped being a bracket over the head and became
      the authored block over the body.
- [x] C6 (added, requested mid-group). A primed body is tinted toward its
      element.

#### The aura sprite needed a scale knob and an aspect

The old code scaled the rig into a **square** `radius * 2.6` box. That was
harmless when the one rig was a 64 px square sheet; the cut trimmed each
strip to its own content, so the frames are now 56x56, 58x58, 62x58 and
64x64, and squeezing them into a square turns a ring into an ellipse.
`aura_size` keeps the art's aspect and `aura.rig_scale` in the data says how
wide the sprite is against the body's diameter. There is a test for the
aspect, because it is the kind of thing that looks almost right.

#### The flash stopped being told when to expire

`add_flash` took an `until`, and the combat layer worked it out by importing
`FLASH_SECONDS` **from the renderer** -- reaching across the seam to ask a
drawing module how long its own effect lasted. It now takes `started`, and
the visual adapter looks the duration up in `element_visuals.json` with the
rest of the presentation tuning. That is also what made the authored bursts
possible at all: they run 0.42 s to 0.67 s and the old constant was 0.3 s,
so every one of them would have been cut off mid-play.

#### Freeze holds formed and shatters at the end

The 40-frame block forms, holds and shatters. Playing it properly would mean
knowing when each body froze, and nothing records that -- `StatusState` keeps
a remaining time, not an original duration, and the freeze length is both
tunable and modifiable. So the block holds at its formed frame for as long as
the freeze runs and plays the shatter over the last 0.45 s, which is the part
that has to line up. The formation frames are skipped. Giving them their
proper run would mean putting a timestamp on the combat-side state for a
rendering detail, and that trade did not look worth it.

#### The aura tint (requested mid-group)

The aura sprite says *what* an enemy is primed with. It does not say *which*
enemies are primed, which is the question a player actually asks while
picking a target in a crowd -- a ring around one body does not survive being
scanned at speed. So a primed body now wears its element's colour.

Slight, per the request: the sprite's own detail has to stay easily
readable. A straight multiply by a saturated colour crushes every channel
the tint is low in -- a bone-white skeleton under Ice would go navy -- so the
element's colour is first lifted 45% toward white, then multiplied, then laid
back over the original at 40%. The result shifts hue with every pixel of
shading still there.

Two things it deliberately does not do. It does not beat the **damage
flash**: a hit is the more urgent thing to see and it is over in a quarter of
a second, so the tint is the `else` branch. And on the primitive fallback
(an enemy with no sprite) it does not beat a **status** colour, which is
already carrying information there.

Cached by `(id(frame), element)` the way `hit_tinted` is cached by frame
identity: the animation frames are the asset cache's own objects, so the
same one comes back for every frame of an aura's several seconds, and
copying it per enemy per frame would be the expensive way to do this.

`_AURA_TINT_ALPHA` (102 of 255) and `_AURA_TINT_LIFT` (0.45) are the two
knobs. At gameplay zoom over this game's pale skeletons the effect is very
subtle; it is clear side by side.

**Settled 2026-09-21 at 102.** The strength was put to the owner with the
same crowd rendered at 102, 150 and 190 -- at gameplay zoom, with the
weapons removed so the hit flash could not mask it -- and they chose to
keep 102. So "slight" in the original request meant slight: closest to the
sprites' own palette, and you have to be looking for it to see which
enemies are primed. Do not raise it without asking.

**D. Rule 3: the layer split** -- done.

- [x] D1. `elements/__init__.py` splits into `begin_frame(run)`,
      `draw_under(surface, run, level)` and `draw_reactions(surface, run)`.
      The old single-pass `draw` stays as the unbanded path, which is what
      the headless tests and any still of a lone body want.
- [x] D2. `scene.draw_flat_effects` calls `draw_under` per level, last of
      the flat effects so an aura sits directly under the sprites standing
      on the same band.
- [x] D3. `PlayingState.draw` calls `draw_reactions` after the hostile
      projectiles, the particles and the damage numbers.
- [x] D4. `begin_frame` is called once, from `PlayingState.draw` before
      `_draw_world`.

#### The split cuts across the pooled transient list

Arcs and flashes share one capped list. They do **not** share a layer:
Thunder's jump is a state of the field and bands with the terrain, while a
reaction's burst is an event and rides over everything. Each class carries
an `OVER` flag and `draw_transient` takes one side at a time. The whole list
is walked either way -- it is capped at `MAX_EFFECTS` and keeping two lists
in step through the sweep would cost more than the scan.

#### `off_band` is the rule the rest of the world already used

`WorldRenderer._off_band` has always been how a flat effect decides whether
it belongs to the band being painted, including its `level is None` escape
meaning "draw it wherever it is". The elemental painters take the same rule
rather than inventing one, and the same escape is what lets the headless
tests keep drawing fake runs that have no map at all.

#### D4 was the trap worth writing down

`begin_frame` resets the particle budget and the aura counter, and
`draw_under` now runs **once per terrace**. Left where it was, each band
would have been handed the whole particle budget and the counter would have
reported only the last band's auras. There is a test for both.

#### What is still procedural, deliberately

The Wind tornado's ring and the aura's shed particles. The tornado is the
Wind *area* -- a separate object from the aura indicator the owner's rule
is about -- and the particles belong to the run's own particle pool, which
draws in its own layer. Both are visible in the milestone screenshot as the
pale circles over the crowd. Worth a decision later; not what was asked
for here.

**E. Tests** -- done.

- [x] E1/E2. A rig present means no ring and no marker; no rig means both;
      locked always rings; a reaction with a burst draws the sprite and not
      the Flash, and without one falls back to the blend. Plus a test that
      an aura sprite keeps the art's aspect, because that is the kind of
      thing that looks *almost* right.
- [x] E3. `tests/render/test_element_layers.py` (new): the under-pass runs
      before any body is painted, a reaction paints after every body, the
      frame begins exactly once however many bands there are, and the aura
      counter sums the bands instead of showing only the last.
- [x] E4. Content validation refuses a missing reaction, a reaction missing
      a field, a non-positive `seconds` or `size`, a missing block, a rig
      name that resolves to nothing, and a rig with no `loop` animation.

Both order tests originally **skipped** when the pinned seed happened to
leave no enemy in view, which made them decorations. They now seat a body
beside the hero through `tests.nearby.spots_near`: what the spawn master
happened to place is not the subject.

**F. Close out** -- done.

- [x] F1. The M8 note that put the ring under every element now carries a
      superseded banner saying why the reasoning does not survive the new
      art.
- [x] F2. Screenshot delivered: sixteen primed bodies with two reactions
      going off over them. Zoomed, every aura is visibly *behind* the
      skeleton wearing it -- fire's flame tongues, ice's crystals,
      thunder's spikes and wind's rings all fan out from behind the body --
      while the two coral FireWind bursts cover the ones they are on.
- [x] F3. Full suite.

## M11 Elemental feedback (DONE)

Requested and confirmed 2026-09-21, built the same day. Three things, all about the
player being able to read what the elemental system is doing to a crowd.

1. The aura's shed particles draw **behind** the bodies, like everything
   else the elements put on a body.
2. Damage numbers last a bit longer and take the colour of the element that
   dealt them. **Only the element's own damage is coloured** -- the
   weapon's own number stays as it is (owner's call, asked and answered).
3. A reaction pops its **name** out of the enemy it fired on -- "Overload",
   "Frostburn" -- drawn like a damage number, in the two colours of the
   pair that made it, on every enemy a reaction triggers on.

### A. The particles go under -- done

- [x] A1. `Particle` gains an `under` flag; `ParticleSystem.burst` gains
      the keyword, defaulting to today's behaviour so all 23 existing call
      sites are untouched.
- [x] A2. `ParticleSystem.draw(surface, camera, under=None, keep=None)`
      filters on it. `None` means both, which is what a caller with no
      bands passes. `keep` is an optional predicate on position, so the
      banded pass can take only the motes standing on the terrace it is
      painting.
- [x] A3. `elements.draw_under` draws the `under=True` half, banded and
      *first* -- lowest of the elemental layers, because these are motes
      coming off a body and belong beneath even the tornado and the arcs.
      `PlayingState.draw` now asks for `under=False`.
- [x] A4. `layers._shed` passes `under=True`.

Not a second pool, for the reason the proposal gave: another sweep and a
split `MAX_PARTICLES` defeats the point of one shared cap, and the
elemental shed is already capped separately by `ParticleBudget`.

Five tests in `test_element_layers.py`. One of them is for a bug that had
not happened yet and easily could: **a pooled object outlives its last
use**, so a recycled particle that kept a stale `under` would strand an
event burst in the wrong layer. `burst` sets the flag on every acquire and
the test fills the pool with `under` particles, sweeps them, and checks
that the next ordinary burst draws late.

The last test goes through `fx.draw` rather than reading `_shed`, so a
refactor that stops passing the flag is caught rather than a rename.

### B. Damage numbers: longer, and the element's colour -- done

- [x] B1. `DamageNumbers.add` gains `colour`, `life` and `low_priority`.
      All generic: this module does not know what an element is, the same
      way it does not know what a weapon is.
- [x] B2. `tracking.source_of(effect)` returns the `ElementId` or
      `ReactionId` behind an effect id, beside the `_LABELS` table that is
      already keyed the same way. Deliberately not a colour -- that module
      is combat-side and has no business knowing what an element looks
      like.
- [x] B3. `RunWorld.effect_colour` turns that into a colour, giving a
      reaction the **mix of its two elements**, which is what a reaction's
      colour is and what `blend_colours` already builds for its flash. So
      the number, the burst and C's label cannot disagree about what an
      Overload looks like.
- [x] B4. A caller-coloured number is lifted 35 % toward white and drawn
      over a near-black outline, cached per (font, text, colour). Thunder
      `(108, 74, 163)` is too dark to read against the world and Wind
      `(170, 255, 190)` too pale over a green meadow: lifting fixes the
      first, the outline the second, and between them hue carries meaning
      while the outline carries contrast.
- [x] B5. Only elemental damage is coloured and lengthened, at 0.9 s
      against a weapon's 0.6.

#### The flooding risk was real, and shortening was not the fix

The plan said to measure before settling the lifetime, so the stress
harness now reports the floating-number pool's high-water mark.

| Run | peak |
|---|---|
| three infused weapons, 100 live (a realistic build) | 58 / 200 -- 29 % |
| 200 live at 30x the element rate, before the reserve | **200 / 200 -- saturated** |
| the same, after | 153 / 200 -- 76 % |

29 % is comfortable, and 30x is not a load any build reaches. But the
arithmetic of the middle row is reachable without the pump: Fire's burn
ticks once a second per burning body, so 200 burning enemies is 200
numbers a second, and at 0.9 s each that is 180 of the 200 slots from burn
alone. A full pool drops whatever asks next -- and what asks next might be
the **weapon's** number, the one the player is actually reading.

Shortening the elemental lifetime would have traded away the thing the
change was for and still not fixed that case. Reserving does fix it:
`low_priority` refuses a number once the pool is 75 % full, so the last
quarter always belongs to the numbers that are not a stream. The elemental
path passes it; nothing else does.

Fourteen tests in `test_damage_numbers.py`, including that a recycled
number does not keep the last one's colour -- a pooled object outlives its
use, and a stale colour would paint a weapon's number in the last
element's hue.

### C. The reaction label -- done

- [x] C1. `DamageNumber` carries `outline` and `rise`; `DamageNumbers`
      grows `add_label(pos, text, colour, outline, life, lift)`. Same pool,
      same cap, same sweep -- a label *is* a floating number whose text is
      a word, and the class already stored `text` as a string.
- [x] C2. `add_label` on both world adapters.
- [x] C3. One call in `reactions.run`, beside the flash, for the same
      reason the flash is there.
- [x] C4. The text is `tracking.label(reaction.key)`, which the run
      summary already uses, so the two cannot disagree about a name.
- [x] C5. The two colours come from `REACTION_PAIRS` in its order, so
      Overload always reads fire-on-thunder.
- [x] C6. The label starts 16 px above a damage number and rises at 22
      px/s against a number's 38, so the two separate rather than stack.
- [x] C7. 1.1 s, longer than even an elemental number: it is a word and
      has to be read.

#### Two colours, and why not by splitting the word

Fill in the first element's colour, a ring of the second around it, and
near-black outside both. A reaction name is eight or nine characters at
15pt; colouring each half is mush at that size and alternating letters is
worse. A ring keeps the word one readable shape and still states the pair.

The near-black is not a garnish. Frostburn is a strong pair and would read
without it, but **Superconduct is ice blue on thunder purple** -- adjacent
hues, both mid-dark -- and that is the pair the scheme has to survive. With
the dark edge it is legible; without it, it is one muddy word. Checked on
all six rather than argued about.

#### Which of the two leads is its own question

Frostburn ships **blue inside, red outside**, which is the reverse of its
`REACTION_PAIRS` order (owner, 2026-09-21). That order is taxonomy -- it
decides the blend, the art and the tests -- so it is not the thing to flip.
A label is presentation, so the override lives in the presentation file: an
optional `label: {fill, ring}` per reaction in `element_visuals.json`,
naming the two elements rather than setting a boolean anyone has to decode.
Absent, a reaction follows pair order, which the other five do.

`content.py` checks a present one names two *different* elements of that
reaction's own pair: the wrong element would colour the word in a hue with
nothing to do with the reaction, and the same one twice would draw a ring
the colour of its fill, which reads as no ring at all.

#### One label per reaction is one per enemy that reacted

A reaction fires on the body whose aura was consumed. Superconduct's jumps
and Overload's shockwave *touch* other bodies without reacting on them, so
they stay silent, and a label per reaction already means a label on every
enemy a reaction triggers on -- which is what was asked for. There is a
test with three bystanders inside an Overload that asserts exactly one
label, because "every enemy that gets a reaction triggered" could also be
read as every enemy a reaction reaches, and that would be a different
feature.

### D. Tests -- done, with each group

- [x] D1. A particle burst with `under=True` draws in the banded pass and
      not in the late one, the default still draws late, and a **recycled**
      particle does not keep the old layer.
- [x] D2. An elemental damage number carries its element's colour and the
      longer life; a weapon's does not; a recycled number does not keep the
      last colour; every effect id maps to an element or a reaction.
- [x] D3. Every reaction produces exactly one label, with the text the run
      summary uses and both of its pair's colours actually present in the
      rendered glyph.
- [x] D4. The label pool *is* the damage-number pool: at the cap it drops
      labels rather than growing.

Three of these test the same shape of bug from three directions -- a
pooled object outliving its last use. A particle keeping a stale `under`
strands an event burst under the bodies; a number keeping a stale `colour`
paints a weapon's damage in the last element's hue; a number keeping a
stale `outline` draws it as a two-tone word. None had happened. All three
are one missing line away.

### E. Close out -- done

- [x] E1. The stress harness reports the floating-number pool's high-water
      mark, and it is what produced the `low_priority` reserve rather than
      a guessed lifetime. Numbers in B.
- [x] E2. Screenshot delivered: a reacting crowd with the names popping
      out of it, and the six labels rendered side by side.
- [x] E3. Full suite.

#### What is still procedural, and still deliberately

The **Wind tornado's ring**. Its layer was already right -- it bands and
draws under the bodies with everything else in `draw_under` -- and the
remaining question was only whether to give it art. The answer is still
no: the ring is drawn at the area's true radius, 80 to 90 world px, so a
64 px sheet would be upscaled nearly three times against 1x terrain, and
the radius is data-driven and modifiable, so art baked at one size is
wrong as soon as a blessing widens it. If it ever wants art, the shape
that works is a hybrid -- an authored core at 1x inside the procedural
ring.

## M12 Colours in the data, and Thunder goes purple (CONFIRMED)

Requested and confirmed 2026-09-21.

1. **Thunder is purple, `#6C4AA3`.** No more yellow.
2. **A reaction's colour is simply the combination of its two elements**
   (owner, asked and answered), so it stays derived from the pair rather
   than becoming an override -- the pair's element colours are already in
   the JSON, so the combination already is data. What needed re-deciding
   was **Overload's art**, whose pair stopped being two warm colours.
3. The two look-alikes -- the `shock` status tint and the magic rod's own
   `thunder_*` art -- are left alone, confirmed.

And the rule that came with it, which is wider than this milestone: **it is
not acceptable to have discontinued references or appearances.** A
deliberate, commented duplicate of a value is still a duplicate; prose that
states the old value is still wrong; a cut asset with the old value baked
in still has to be recut. The survey below is part of the change, not
follow-up work.

### A. Reaction colours become data -- **dropped, answered instead**

The proposal was an optional `colours` override per reaction in
`element_visuals.json`. The owner's answer made it unnecessary: **a
reaction's colour is simply the combination of its two elements**. The
pair is taxonomy (`REACTION_PAIRS`) and the element colours are already
data, so the combination already *is* data and an override entry would
have been a second way to say the same thing -- exactly the sort of
duplicate this milestone is otherwise removing.

`transient.blend_colours` is unchanged and remains the one place a
reaction palette is built.

What the question actually surfaced was the **art**: Overload and
Superconduct were each a single authored row picked when one of their two
elements was yellow, and neither states its pair any more. See C3 and C4.

### B. Thunder goes purple -- done

- [x] B1. `elements.thunder.colour` is `[108, 74, 163]`.
- [x] B2/C1. `overlays.py` no longer keeps its own copy. It calls
      `aura_colour(key)`, which reads the game's data, with an empty
      `_READABLE` map for the day something genuinely needs a contrast
      nudge -- so a divergence would have to be written down rather than
      drifting. Verified returning `(108, 74, 163)`.
- [x] B3/C2. `thunder.png` and `thunderwind.png` re-cut on a purple ramp,
      `(58, 36, 92)` to `(168, 132, 226)` at gamma 0.8, chosen by eye
      against the two authored alternatives (see below).
- [x] B4. Every remaining statement that Thunder is yellow: the rig
      `_note`s, the CREDITS usage entry, the cut script's docstring, and
      its ramp comment -- rewritten hue-neutral, because the lesson it
      records (why a per-channel multiply fails on the grey row) is true
      of any colour and should outlive this one.

**Why not an authored purple row.** Rows 8 and 1 were rendered beside the
remap. Row 8 is a near-black indigo that disappears against grass; row 1 is
a saturated magenta that would fight Frostburn, which already owns it. The
grey row remaps onto any ramp exactly, which is why it was the row to take
in the first place, so it hits `#6C4AA3` on the nose.

### C. The two reactions whose pair changed -- done

- [x] C3. **Overload** was coral, picked when its pair was fire orange and
      thunder yellow. It is now the grey row remapped **across its own
      pair**: purple in the shadows, a hot orange core. One authored row is
      one colour and a reaction has two elements.
- [x] C4. **Superconduct** got the same treatment on the owner's word --
      purple shadows to an icy highlight. It had been cyan, which read as
      ice alone.
- [x] C5/C6. The `shock` status tint and the magic rod's own `thunder_*`
      art are **left alone**, confirmed. The first is a weapon-blessing
      status that happened to share a hue with the old Thunder and no
      longer does; the second is the rod's own projectile and cast art,
      which an *uninfused* rod still fires. Written down here so neither is
      "fixed" later on the strength of its name.

**The three Wind reactions are deliberately not pair-ramped.** FireWind,
IceWind and ThunderWind are one swirl in three colours because they are the
same mechanic with different payloads, and reading as a family is worth
more there than naming the pair. ThunderWind did change -- from the old
yellow to the new purple -- because that is its payload's colour, not
because it became a pair ramp.

### D. Tests and close out -- done

`tests/render/test_element_colours.py`, 7 tests and 17 subtests.

- [x] D1. The dev inspector's colours match the data, for all four
      elements. Two tests beside it: that `_AURA_COLOURS` has not come
      back at all -- the *shape* the defect took, which a future edit could
      reintroduce while keeping both tables in step today and leaving the
      first test passing -- and that `_READABLE` is still empty, so any
      contrast override has to be written down rather than forked.
- [x] D2. Superseded by dropping A: there is no override to test.
- [x] D3. Screenshots delivered.
- [x] D4. Full suite: 3131 passed, 1 skipped, before the Overload fix
      below; re-run after it.

**The art has to be tested against the data, and nothing was doing it.**
The aura and reaction strips are *cut* assets with a colour baked in.
Changing a number in `element_visuals.json` cannot reach them -- only
re-running the cut script can -- and no other test in the suite looks at a
pixel. So a colour change that forgot the art would have shown up only when
somebody eventually noticed. The new tests compare the strips' **hue** to
the declared colour: hue rather than RGB distance, because the claim being
made is "still the same colour family" and the art is a whole ramp against
one declared point. Measured deltas are 0 to 11 degrees against a 45 degree
threshold, so a retune has four times the headroom and a 150-degree mistake
like yellow-for-purple still cannot pass.

#### It immediately caught a real one

Overload's pair ramp -- authored as "thunder's purple in the shadows,
fire's orange in the core", approved from a screenshot, and shipped --
contained **no purple at all**. Fire sits at 22 degrees and Thunder at 263,
nearly opposite on the wheel, so interpolating between them in RGB runs
through muddy red rather than through either end; and the source row's
darkest pixels only reach about a fifth of the way along the ramp, so the
purple end was never sampled. Measured on the old strip: 0 % of its
coloured pixels anywhere near thunder's hue, against the test's 5 % floor.

The fix is a deeper, more saturated dark end and a gamma above 1 so values
stay low for longer: `(68, 24, 185)` to `(255, 168, 64)` at gamma 1.5. The
strip is now 72 % thunder and 20 % fire -- a violet body with a hot orange
core, which is what was wanted.

Superconduct needed none of this and is 100 % ice / 72 % thunder on the
first try, because ice and thunder are *adjacent* hues: anything between
them is already both. That contrast is the whole lesson. **A pair ramp
works when the pair is adjacent on the colour wheel and has to be forced
when it is not**, and the only way to know which happened is to count.

It is worth saying plainly that the picture looked fine. Two screenshots
were taken of that strip, one of them a deliberate candidate comparison,
and neither showed the problem -- a warm purple-grey reads as "purple
enough" beside an orange core. The measurement disagreed and the
measurement was right.

### Ordering

M12 before M11's part B. M11 planned an outline-and-lift treatment partly
to separate Thunder from the crit gold; purple separates itself, so doing
the colour first means that work is sized against the colours that ship
rather than against one that is about to change.

## Does every island offer an element? (surveyed 2026-09-21)

Asked by the owner. There are two doors into the elemental system: the
village Monastery, and a buff building that rolled elemental at
`elements.chance`. Measured over 60 seeds, excluding villages (whose pass
owns their island) and the boss arena (whose clear disc is the fight):

| | |
|---|---|
| eligible islands | 390 |
| offering an element | 320 (82.1 %) |
| offering none | 70 (17.9 %) |
| villages missing a Monastery | 0 of 60 |

**No, and it cannot hold by construction.** `elements.chance` is 0.4 rolled
independently per building, so an island with two buff buildings has a 36 %
chance of neither rolling elemental and one with three has 21.6 %. What
*does* hold is that every **run** has a door: both villages always carry a
Monastery, so the system is never unreachable. It is per-island coverage
that fails.

The owner's call was to **fix the placement side only** and leave the
chance alone, which is recorded in `buff_buildings_journal.md` rev. 7: the
repair pass was taking back 8.5 % of every buff building placed, because
its Dijkstra priced a building the same as a tree. Pricing them apart took
islands under the minimum from 18 to 8 and islands with none from 1 to 0,
and moved element coverage from 80.5 % to 82.1 %.

The remaining 17.9 % is the 0.4 chance, untouched by request. If it is ever
worth closing, the cheapest lever is to guarantee the *first* buff building
on an island rolls elemental and leave 0.4 for the rest.

#### A measurement error worth remembering

The first survey reported 24.4 % of islands with no element and 18 % below
the buff-building minimum. Both were too high: it counted the boss arena as
an ordinary island. The arena is excluded from the buff scatter by design,
so 40 of the 41 "islands with no buff building" were arenas behaving
correctly, and the real figure was 1. The layout has no `boss_room_id`
attribute -- the check silently read `None` and never excluded anything --
and `room.kind == "boss"` is the test that works.

## M13 An infused weapon looks infused (DONE)

Requested 2026-09-21, **not yet confirmed**. An infused weapon's *attack*
should show its element. Two ways were put: authored sprites that enhance
the effect, or a coloured alpha over the attack's own appearance. The owner
then asked to look in the reserve for something that could *replace* a
melee attack -- a cone for the Sword -- and consider a tint or a coloured
version of it.

### What is element-aware today: almost nothing

One line, `core/effects.py:75`. A projectile's `color` -- the primitive dot
and the dust-trail particles -- is blended toward the element. Every
**authored** attack visual is element-blind: the Sword's slash, the
Daggers' slash and stab, the Hammer's impact, the Bomb's explosion, the
Rod's bolt and arcane circle, the Bow's arrow, the Ember Ring's orbiters
and both summons. An infused Hammer looks exactly like a plain one until
the aura appears on whatever it hit.

### Can the existing art take a tint? Mostly not

Mean saturation of each attack's opaque pixels, which is what decides
whether a multiply tint can work on it:

| rig | mean sat | a multiply tint would |
|---|---|---|
| `thunder_ball` | **0.00** | work perfectly -- it is greyscale |
| `dust_puff` | 0.11 | work |
| `daggers_slash` | 0.12 | work |
| `explosion_small` | 0.50 | dull it |
| `grave_totem` | 0.51 | dull it |
| `spirit_wolf` | 0.57 | muddy it |
| `explosion` | 0.57 | muddy it |
| `hammer_impact` | 0.58 | muddy it |
| `sword_slash_up` | 0.68 | muddy it |
| `totem_bolt_fire` | 0.80 | wreck it |
| `arcane_circle` | 0.90 | wreck it |
| `soul_slash` | 0.91 | wreck it |
| `ember` | 1.00 | wreck it |

**Three of sixteen are neutral enough to multiply.** The Thunder remap's
lesson again: a multiply by a saturated colour crushes every channel the
tint is low in. So "a coloured alpha" cannot mean one `BLEND_RGBA_MULT`
across the board.

### The reserve answers it: for melee, replace the art

The pack's sheets carry **nine colour rows of the same animation**, so a
"coloured version" is not something to compute -- it is already drawn.

Scored all 180 sheets for wide, thin, low-fill shapes and then looked,
because a score cannot tell a sweep from a smear:

| weapon | sheet | shape |
|---|---|---|
| Sword | `Part 11/509` (13f) | three or four curved blades fanned in an arc -- a cone sweep |
| Daggers, slash | `Part 12/578` (11f) | parallel claw streaks, fast and narrow |
| Daggers, stab | `Part 8/395` (9f) | a thin lens driven forward |
| Hammer, slam | `Part 13/615` (14f) | a radial star from the point of impact |

Rendered across the rows a weapon would wear -- the neutral grey for an
uninfused weapon, then the four elements -- all four read and the steel
column reads as plain steel. **So the melee weapons need no tint at all**:
five authored variants each.

Thunder is the same exception it has been since M12. No purple row, so its
variant is the grey row remapped, exactly as `thunder.png` and
`thunderwind.png` already are.

### The proposal: replace melee, tint the rest

The two ways the owner put are not alternatives; they are the right answer
for different weapons.

- **Melee -- replace.** Sword, Hammer and Daggers get new art, five
  variants each. Authored colour beats a computed one, which is this
  project's own preference (`authored-tiles-over-procedural-edges`).
- **Everything else -- tint.** The arrow, the Rod's bolt and arcane
  circle, the Bomb's explosion, the orbiters and the two summons all carry
  identity that is theirs rather than the element's, and replacing them is
  a different and much larger job. They take M11's lift-multiply-blend,
  already proven on saturated pixel art here.
- `thunder_ball`, at 0.00 saturation, takes the asset cache's existing
  `tint=` multiply instead: cheaper, already cached per tint, and better on
  greyscale.

**This also settles the alpha-56 rigs by replacing them.**
`sword_slash_down` and `daggers_stab` are drawn at a maximum alpha of 56
where their own up-swings reach 255 -- about a fifth of the opacity. Both
are on the replacement list, so whether that was deliberate stops
mattering.

### The colour values to use

`element_visuals.json` `elements.<key>.colour`, through the accessors that
already exist:

    element_fx.tint(element)              -> the element's RGB
    element_fx.blend(colour, toward, amt) -> what the trail already uses

No new colour data. M12 put the elements' colours in one place and took the
duplicate out of `overlays.py`; this must not add a third. A tint strength
belongs in `element_visuals.json` beside `aura.rig_scale`.

### Todo (M13)

**A. Cut the melee art** -- done

- [x] A1. Twenty strips: four attacks, five variants each.
- [x] A2. `assets/effects/weapons/<weapon>/`, single-row, no `row` index.
- [x] A3. The art they replace archived unmodified in
      `assets/unused/superseded-weapon-fx/`.
- [x] A4. `assets/CREDITS.md` usage entry.

| attack | source | frames | frame | anchor |
|---|---|---|---|---|
| `sword/slash_*` | Part 11/509 | 13 | 62 x 53 | 31, 27 |
| `daggers/slash_*` | Part 12/578 | 11 | 64 x 40 | 32, 20 |
| `daggers/stab_*` | Part 8/395 | 9 | 58 x 27 | 29, 13 |
| `hammer/impact_*` | Part 13/615 | 14 | 63 x 59 | 32, 30 |

#### Every variant carries its suffix, `plain` included

The first cut gave `plain` the bare name -- `slash.png` -- and that landed
straight on top of `daggers/slash.png` and `daggers/stab.png`, which are
tracked files the *current* rigs still read. Both were restored from the
index and the scheme changed: `slash_plain`, `slash_fire`, and so on. The
old art keeps its own names until the wiring moves off it, and none of the
five is named unlike its siblings.

#### What the Daggers were actually showing

`weapon_visuals.json` plays `[daggers_stab]` and keeps `daggers_slash`
under a `_slash_disabled` key. The Sword plays `[sword_slash_down,
sword_slash_up]` in sequence. So of the three melee effects on screen, the
two faint ones -- `slash_down` and `daggers_stab`, both at a maximum alpha
of 56 -- were the Daggers' *only* effect and the Sword's opening frame.
Replacing them is most of the visible gain here, before any element is
involved.

**B. Wire the melee rigs** -- done

- [x] B1. Twenty rigs in `weapon_sprites.json`.
- [x] B2. `elements.variant_rig(assets, base, element)` resolves a base to
      its element's colour, and the slash and slam painters call it. The
      data now names *bases*: `sword_slash`, `daggers_stab`,
      `hammer_impact`.
- [x] B3. Sizes, anchors and timings re-measured.

#### The resolver has to be told, not left to guess

`variant_rig` first tried the obvious thing: look for `base_<element>`, then
`base_plain`, then `base`. That resolved `totem_bolt` + fire to
**`totem_bolt_fire`**, which exists and is the Grave Totem bolt's flame
tail. Name guessing across one flat rig namespace finds things it did not
mean to. It now treats a rig as variant-cut only when its `_plain` exists,
which is the marker that says the family was cut on purpose.

#### The Sword is one strip now, and the Daggers got faster

The Sword played `[sword_slash_down, sword_slash_up]` back to back; the
replacement is a single fanned arc, so the sequence is one entry long. The
machinery is unchanged and still tested, because a sequence weapon's cone
draws no slash of its own and would show nothing if it broke.

The Daggers' new strips came off the cut at 0.32 s and 0.37 s against a
0.1 s hit and a 0.4 s cooldown -- the crescent would still have been on
screen at the next swing. Both are now about 0.2 s.

#### Eleven tests followed the art

They were pinning provenance -- this strip is row 18 of
`Combat-Sheet.png`, that one is row 13, the impact is five frames, the
cells are square, the splash sits eight crop pixels low. All true of the
art M13 replaced and none of it true now. Each was rewritten to what still
holds rather than deleted, and two came out **stronger** for it: the frame
count now has to tile the strip's width *and* match its height, where it
used to assert squareness; and the daggers' upper time bound is now
against the cooldown, which is the thing that actually matters, rather
than 1.5x the hit, which was a statement about a five-frame strip.

The Hammer also needed `content` and `over_circle` copied onto the new
rigs: `slam_fx.impact_size` reads both, and without them the splash lost
its quarter overhang and would have been drawn square.

**C. The rest are recoloured, not tinted** -- done, rebuilt once

The first build tinted them. It was wrong, and the measurement that found
it is the useful part of this section.

- [x] C1. M11's `aura_tinted` moved into `elements.washed(frame, element)`.
      It keeps the one surface it was built and tuned for: a primed enemy's
      body.
- [x] C2. Its strength is a `wash` block in `element_visuals.json`,
      validated in `content.py`. No new colour -- the hue is
      `element_fx.tint`, which M12 made the single source.
- [x] C3. Every effect that keeps its own art is **recoloured offline**,
      four sheets per rig, by
      `tools/asset_pipeline/recolour_element_variants.py`. The painters
      resolve a rig through `variant_rig` and blit it; nothing is computed
      at draw time.
- [x] C4. Dropped, as before: `thunder_ball` needs no special case.

#### Why the tint could not work, at any strength

The wash is a multiply. Multiplying an orange flame by a blue tint cannot
produce blue -- it can only darken toward where the two hues overlap, which
is olive. Rendered at four strengths (lift .45 / alpha 102, .30/150,
.20/190, .10/225), turning it up did not make the orbiter bluer, it made it
muddier. There is no good number between invisible and mud.

It worked on the enemies because it was tuned on them: a bone-white
skeleton is nearly unsaturated, and white times anything is that thing. The
attack art is the opposite -- the orbiter measures 1.00 saturation, the
totem bolt 0.93 -- so the same mechanism had nothing to work with.

#### And why it is done offline

A proper HSV **hue rotation** -- keep value, keep saturation, turn the hue
-- does produce the colours, with every pixel of shading intact. Measured
at **2.4 ms a frame** uncached, in pure Python, per element. That is about
forty times the wash, and the wash's own cache was already sitting at
391 of 512 entries in a 120-enemy fight, so a miss would have been a
visible hitch rather than a rounding error.

So the rotation runs once, in a tool, and the game blits an ordinary
sprite. This is not a new idea here: `recolour_totem_fire.py` made exactly
this argument in 2026-09 for one file ("orange x blue is mud"), and this
generalises it.

| | cost |
|---|---|
| wash, runtime | +0.62 ms draw at 120 enemies, cache 391/512 |
| hue rotation, runtime | ~2.4 ms per frame per element, uncached |
| recoloured offline | nil -- it is a sprite |

Re-measured after the change, the wash's draw delta is within noise
(-0.07 ms across 400 frames) and it is called 51.6 times a frame for
**enemy bodies alone** -- so the attacks were never much of its cost, and
the cache pressure is M10's, not M13's. At 408 of 512 a clear would
recompute about 51 washes in one frame, roughly 0.6 ms, once. Measured and
closed.

#### The source art is expected to change, so nothing is transcribed

The melee variants are cut from a pack that is not in the repo; they are as
fixed as any authored art. These are derived from sheets that **ship**, and
any of them can be redrawn or repointed tomorrow without a word about the
four copies that just went stale.

So the tool is declarative end to end. A family opts in by carrying an
`infused` block in `weapon_sprites.json`; the tool reads the sheets from
that rig's own anims, writes `assets/infused/<rig>_<element>/`, and
regenerates `data/weapons/infused_sprites.json` in full. Changing the art,
the tuning or the rig itself is one re-run:

    python -m tools.asset_pipeline.recolour_element_variants

and a test runs the same tool with `--check`, which rebuilds the whole tree
in memory and fails on any difference -- a changed source, a changed
`infused` block, a hand-edited PNG and an orphaned file all come out as the
same failure.

The six families: `ember`, `bomb`, `explosion`, `explosion_small`,
`grave_totem`, `spirit_wolf`. Twenty-four rigs, forty sheets, 456 KB.

#### The rotation, and what it deliberately does not do

Each sheet is turned by **one** angle, from its own dominant hue (a
saturation-weighted circular mean, so the black outline and the transparent
corner do not vote) onto the element's. Value and alpha are untouched. That
keeps the art's internal colour relationships: a flame whose core is hotter
than its edge still has a core hotter than its edge, in the new colour.

`spread` (0.85 by default) is how much of a pixel's distance from its
family's hue survives, and `sat_floor`, `sat_gain` and `value_gain` are
there for art too grey to rotate. None of the six needed anything but the
default -- the least saturated is the Bomb at 0.44 -- so all six `infused`
blocks are empty, which is the honest state to leave them in.

#### The look follows the infusion, not the hit that spends it

The screenshot caught the second real bug in M13 C, and it had been there
since A: the Ember Ring, the Grave Totem and the Spirit Wolf came out plain
at **every** element.

They are the three `time`-mode weapons, and `Weapon.attack_element` is
documented as `NONE` for those -- their element is claimed per hit by
`take_element_window` rather than stamped on the spawn -- so the painters,
reading the projectile's stamp, had nothing to read. The Daggers had a
quieter version of it: `interval: 2`, so two swings in three were drawn
plain. Four of nine weapons, and the wash's near-invisibility had hidden
all of it.

`attack_element` is the right rule for damage and the wrong one for paint.
An infused weapon *is* infused the whole time; which particular hit spends
the element is a balance detail, not something the player should have to
read off a sprite. So every spawn now carries a second, cosmetic field:

| field | means | read by |
|---|---|---|
| `element` | what this hit applies | the hit resolver -- unchanged |
| `infusion` | what the weapon is | every painter |

On `Projectile` and on `Summon` (whose `element`, added earlier in M13 and
never read for damage, simply became `infusion`), set on every `reset` so a
pooled object cannot wear the last one's colour. Seven spawn sites pass it.

Seven tests pin it, including the two pool-reset ones and the case that
started this: a time-mode weapon stamps nothing and still looks infused.
One existing test followed the change --
`test_an_infused_sword_draws_its_element` set `element`, which is now the
wrong field -- and gained a sibling that pins the distinction directly: a
swing that applies nothing still draws its colour.

#### Three variants are close to their plain, and that is not a bug

Measured hue distance from each family's own colour:

| family | plain | fire | ice | thunder | wind |
|---|---|---|---|---|---|
| `ember` | 29 | **8** | 175 | 127 | 105 |
| `bomb` | 223 | 163 | **15** | 44 | 85 |
| `explosion` | 39 | 17 | 166 | 136 | 95 |
| `explosion_small` | 36 | 14 | 169 | 133 | 98 |
| `grave_totem` | 196 | 173 | **10** | 68 | 61 |
| `spirit_wolf` | 175 | 153 | 30 | 89 | 40 |

A fire-infused Ember Ring looks almost like a plain one, because a plain
Ember Ring is already fire; an ice-infused Grave Totem looks almost like a
plain one, because the Totem is already a blue flame. Manufacturing a
difference -- a brightness lift on every variant, say -- would push twenty
other sheets away from their source's authored shading to fix three, and
the element is still being said by the aura, the particles and the damage
number. Left alone, and written down so it is a known property rather than
a surprise.

**D. Tests and close out** -- done

- [x] D1. Every melee weapon has all five variants and they all load; every
      infusable rig has all four, with the base's geometry, frame counts and
      timings, and an untouched alpha channel.
- [x] D2. Each variant's mean hue is its element's, within 45 degrees --
      the same measurement M12 put on the aura strips, and worth more here
      because a hue rotation has exactly one way to be wrong and no way to
      look wrong in a thumbnail.
- [x] D3. The wash is cached per (frame, element), not copied per frame;
      and it is no longer on the draw path of anything but an enemy.
- [x] D4. No third copy of an element colour: the tool reads
      `element_visuals.json`, and `variant_rig` refuses to guess a family
      from a name -- `totem_bolt` plus fire is still `totem_bolt`.
- [x] D5. Screenshot per element for the recoloured effects, in play, and
      the full suite: **3190 passed, 1 skipped**, 1000 subtests. The
      screenshot earned its place twice over -- it is what caught the
      `infusion` bug, which no test in the suite was looking for and which
      had been shipping since A.

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
- 2026-09-21: M11 and M12 done. **M12** made Thunder purple and took the
  duplicated colour tables and stale prose out with it -- the dev
  inspector had its own copy of all four element colours and would have
  gone on drawing a yellow Thunder. Its new tests measure the *art*
  against the data, which nothing did before, and immediately caught
  Overload's pair ramp shipping with no purple in it at all: fire and
  thunder are nearly opposite hues and a straight RGB interpolation
  between them runs through mud. Superconduct, whose pair is adjacent, was
  right first time. **M11** finished the feedback: the aura's shed now
  draws under the bodies like the rest of rule 3, elemental damage is
  written in its element's colour and lasts 0.9 s, and a reaction pops its
  name out of the body it fired on in the two colours of its pair. The
  damage-number lifetime turned out to need more than a number -- a
  burning crowd of 200 fills the whole pool on burn ticks alone, and a
  full pool drops whatever asks next, possibly the weapon's own number --
  so elemental numbers yield the last quarter of it instead. Frostburn
  reads blue inside and red outside on the owner's word, through an
  optional label order in the data rather than by flipping the taxonomy.
  Full suite 3162 passed, 1 skipped.

- 2026-09-21: M10 done. The elements and the reactions got authored art,
  and the rules that came with it. Eleven single-row strips cut out of the
  two reserve packs by `cut_element_effects.py`, with Thunder's grey row
  remapped onto a yellow ramp because the pack has no yellow one and Fire
  wanted the row whose highlight is. Where a sprite is wired it is now the
  **whole** indicator: no ring, no marker, and no procedural flash -- which
  reverses M8's reasoning, recorded there with a banner. The locked slot
  keeps its circle, because it has no sprite. Freeze stopped being a
  bracket over the head and became the ice block over the body. The layer
  split landed: the elemental *state* of the field now paints terrace by
  terrace under the bodies it belongs to, and a reaction rides over every
  character and is gone inside 0.7 s. A primed body is also tinted lightly
  toward its element, which answers the question the aura sprite does not
  -- not *what* an enemy is primed with but *which* enemies are. Fifteen
  new tests across two modules, including the order tests that pin the
  split. Screenshot delivered.

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

- 2026-09-22: M13 done. An infused weapon now looks infused, by two
  mechanisms chosen by measurement rather than preference. The **melee**
  attacks are replaced outright -- the reserve pack draws nine colour rows
  of every animation, so the Sword's arc, the Daggers' streaks and thrust
  and the Hammer's star were each cut five times, and two of the five rigs
  they replace were drawn at a maximum alpha of 56 where their siblings
  reach 255, so most of the visible gain arrives before any element does.
  **Everything else** keeps its own art and is hue-rotated offline, four
  sheets per rig, by the new
  `tools/asset_pipeline/recolour_element_variants.py`: the Ember Ring's
  flame, the Bomb and both its explosions, the Grave Totem and the Spirit
  Wolf. That second half was **built twice**. The first build tinted them
  with M11's wash, which is a multiply, and a multiply cannot turn an
  orange flame blue -- rendered at four strengths, turning it up only made
  it muddier. A hue rotation does work and costs ~2.4 ms a frame uncached,
  so it runs in a tool instead and the game blits an ordinary sprite; the
  wash went back to the one surface it was tuned for, a primed enemy's
  body, where its cost is now within noise. Because these sources ship and
  can be redrawn at any time, nothing about them is transcribed: a family
  opts in with an `infused` block, the tool reads that rig's own sheets,
  and a test runs it with `--check` so a replaced sprite cannot silently
  leave four stale copies behind. Three variants land near their plain --
  fire on a flame, ice on a blue totem -- which is written down as a
  measured property rather than papered over. Screenshot delivered: the
  four recoloured effects, plain and four elements, in play.

---

## CMB-009 — Requirement (owner, 2026-09-22)

- **Objective:** Plan the elemental work still missing after CMB-005/006/007.
- **Details:** The remaining dev extras from design §10.3 (hot-reload of the
  element data, a reaction log, spawning a building with a chosen element),
  the two §9.8 profiling counters (Thunder jump nodes per frame, active Wind
  areas), and a faint alpha glow in the element's tint behind an elemental
  buff building, which today shows its element only on use.
- **Constraint:** Planned only, status `proposed`; the plan lives in its own
  file, `documentation/plans/elemental_extras_plan.md`.

## CMB-009 — Plan

See `documentation/plans/elemental_extras_plan.md`: the glow first (the one
player-facing item), then the counters (CMB-008's cascade measurement wants
them), then the three dev tools. Tasks are numbered when it is taken up.

## CMB-009 — Confirmed reading

- **The building.** A buff building that rolled an element carries it on
  `Interactable.element` (`entities/interactable.py`); the obstacle draws
  the building, and `WorldRenderer.interactables` skips buff buildings
  (`visual/rendering.py`), so nothing shows the element. The flat terrace
  pass (`visual/scene.py` → `ren.interactables(surface, level)`) runs before
  the actors, which puts a glow drawn there under the building art — the
  standing order for element effects.
- **The glow helper.** `visual/glow.py::GlowCache` pre-renders a soft disc
  per `(diameter, alpha)`, any colour, and `pulse_alpha` gives an optional
  breath; the element tint is `VisualSet.tint(element)`
  (`visual/elements/profiles.py`).
- **The counters.** F1 already shows auras, reactions per frame, held
  reactions, particles and element fx (`devtools/dev_flags.py`); Thunder
  jump nodes and active Wind areas are not counted anywhere.
- **The dev tools.** The dev menu has Force aura and the infusion row;
  hot-reload, a reaction log and spawn-a-building-with-an-element do not
  exist.
- **CMB-009.D1 — Glow strength is decided on a screenshot.** The first
  build uses a low fixed alpha with a slow, narrow breath; the numbers live
  in `data/world/buildings.json` and the owner tunes them from the
  screenshot.
- **CMB-009.D2 — The Monastery gets no glow.** It rolls no element; the
  player picks one there.

## CMB-009 — Tasks

- [x] CMB-009.1 — The element glow behind elemental buff buildings (plan §1), with tests and a screenshot of all four elements
- [x] CMB-009.2 — Thunder jump nodes per frame and active Wind areas in the F1 metrics (plan §2)
- [x] CMB-009.3 — Hot-reload of the element data under a dev key, keeping the old values if validation fails (plan §3)
- [x] CMB-009.4 — Reaction log overlay (plan §3)
- [x] CMB-009.5 — Dev-menu row: spawn a buff building beside the hero with a chosen element (plan §3)

## CMB-009 — Results

**Branch:** `claude/cmb-009-elemental-extras`, cut from
`claude/doc-004-proposal-journals` (which carries this block), owner's
instruction to continue on a new branch as before (2026-09-23).

### CMB-009.1 — The glow

- `visual/elements/building_glow.py::BuildingGlow` over `GlowCache`, owned
  by `ElementVisuals` (`None` when `buildings.json` has no `elements` block,
  since then no building is ever elemental). `WorldRenderer.interactables`
  draws it where it used to skip a buff building outright, so it paints in
  the flat terrace pass, under the building art.
- `data/world/buildings.json` → `elements.glow`: `scale` 3.4 (diameter over
  the building's interaction diameter), `alpha_min` 90, `alpha_max` 130,
  `period` 3.0 s, `steps` 6. `_check_building_glow` (`game/content.py`)
  requires every field, orders the alphas inside 0–255 and refuses a
  non-positive scale.
- **Tuning from the screenshot (D1).** The first values, alpha 40–64 at
  scale 3.0, were close to invisible: only the ice glow read, over grass.
  90–130 at 3.4 reads as a soft wash round the foot of each building and is
  still faint; Thunder's purple is the weakest of the four over olive
  ground. These stay the owner's to tune.
- `tests/render/test_building_glow.py`: 11 tests, 8 subtests — the glow
  takes the element's tint, stays at or under `alpha_max`, reaches past the
  building, is absent on a plain or used building, breathes inside its two
  alphas, and the data check refuses a missing block, a missing field and
  bad alphas.
- **Screenshot:** seed 35, one building per element — fire (vampire),
  ice (magnet) and wind (pinball) as rolled; thunder assigned to a plain
  magnet because no building rolled it on that seed, labelled as such.
- **Tests:** `tests/render` + `tests/playing` + `tests/systems` +
  `tests/combat` — 1448 passed, 461 subtests, 0 skipped (6 min 1 s).

### CMB-009.2 — The counters

- `ResolverStats.jump_nodes_this_frame` / `jump_nodes_total`
  (`combat/elements/resolve.py`), bumped by `Thunder.spread` with the
  number of enemies the chain reached (the struck one not counted) and
  reset in `begin_frame` with the reaction counter.
- F1 metrics (`devtools/dev_flags.py`): "thunder jumps" (per frame and
  total) and "wind areas" (live against `max_active_wind_areas`, 6).
  Read back from a live seed-7 run: `0/frame 0 total` and `0/6`.
- `tests/combat/test_elements_base.py::ThunderTests::test_the_jump_nodes_are_counted_per_frame_and_in_total`.
- **Tests:** `tests/combat` + `tests/flows` + `tests/devtools` — 748
  passed, 132 subtests, 0 skipped (5 min 2 s).

### CMB-009.3 — Hot-reload of the element data

- **F9**, developer runs only like F7/F8 (`config.DEBUG_KEYS
  ["reload_elements"]`, SDL keycode 1073741890, unused before). Routed as
  the other keys are: `Game._handle_debug_key` → `PlayingState` →
  `DevFlags.handle_debug_key`, which shows the result as a run notice
  (2.5 s, or 6 s for a failure so the reason can be read).
- `devtools/element_reload.py::reload_element_data(run)`: re-reads
  `weapons/elements.json` and `weapons/reactions.json` through the content
  loader, validates them with the boot's own checks, and builds a **fresh
  `ElementRegistry`** from them before touching anything — so a file that
  validates but cannot bake fails there too. Only then does the run's
  registry `adopt` it (`combat/elements/registry.py`), and `run.content`
  takes the new dicts.
- **CMB-009.D3 — What a reload keeps.** `adopt` swaps the data (global
  block, element and reaction bases, reaction table) and drops the baked
  caches; it keeps the element objects and the modifier layers, so a buff
  or blessing the run holds applies on top of the new numbers. Not reached:
  a Wind area already on the field keeps its seeded config until it ends,
  and `element_visuals.json` (presentation, not tuning) is not reloaded.
- Docs: the F-key table in `FUNCTIONAL_README.md`, the F1–F9 range in
  `README.md` and the keycode comment in `game/config.py`.
- `tests/devtools/test_element_reload.py`: 8 tests — a changed value
  reaches the live registry and `run.content`; the run's modifiers survive
  and stack on the new data; bad data and an unreadable file keep the old
  values; F9 has its own key, reloads and says so in a developer run, and
  does nothing in a normal one.
- **Tests:** `tests/devtools` + `tests/combat` + `tests/flows` — 756 passed,
  132 subtests, 0 skipped (5 min 8 s).

### CMB-009.4 — The reaction log

- `combat/elements/reaction_log.py`: `ReactionLog`, a fixed ring of
  `LoggedReaction(serial, time, reaction, aura, trigger, damage, depth,
  deferred)`, newest first. Kept in every run (`build_resolver` sets
  `resolver.log`), one append per reaction, so turning the overlay on shows
  what already happened. `config.REACTION_LOG_CAPACITY` 64,
  `REACTION_LOG_LINES` 14 shown.
- The resolver feeds it from `_run_reaction`, the one place a reaction
  runs — at once or a frame late:
  - **damage** is what the reaction dealt through its own context:
    `HitContext.deal` now keeps a running `dealt`, read before and after the
    runner. What a cascade it set off deals is logged on that reaction's
    own line, not added to this one.
  - **depth** (CMB-009.D5) is how many reactions were running when this
    one was triggered — 0 for a weapon's hit, 1 for one set off inside
    another's run (a tornado or Superconduct laying an aura). A held
    reaction carries its depth in `PendingReaction.depth`.
  - **deferred** marks a reaction the per-frame budget held over.
  - Time is run seconds, not a frame number: the resolver has no frame
    counter, and the serial already orders them.
- Overlay: the dev menu's new **"Reaction log"** row (after "Aura
  inspector") toggles `DevFlags.show_reaction_log`; `overlays.
  reaction_log_overlay` draws the newest 14 in a panel down the right
  edge, clear of the HUD. The first draft coloured each line by its aura
  element; Thunder's purple was unreadable on the dark panel, so the text
  is now light with two swatches in front — aura, then trigger.
- `tests/combat/test_reaction_log.py`: 10 tests — pair, damage, serial and
  time logged; a reaction set off inside another is depth 1 and finishes
  first; a reaction's damage excludes its cascade's; a budget-held
  reaction is logged when it runs, flagged; the ring keeps its capacity;
  `clear` empties it; no log records nothing; the overlay's lines flag a
  cascade and a hold; the dev-menu row exists; nothing draws outside a
  developer run.
- **Screenshot:** a seed-7 developer run with six real reactions driven
  through the run's resolver, the panel over the terrain.
- **Tests:** `tests/combat` + `tests/devtools` + `tests/flows` +
  `tests/screens` + `tests/render` + `tests/playing` — 2024 passed, 487
  subtests, 0 skipped (13 min 22 s), then the log, dev-mode and screens
  tests again against the final overlay — 631 passed, 22 subtests.

### CMB-009.5 — Spawn an elemental building

- Dev menu: **"Spawn elemental building..."** (after "Infuse weapons...")
  opens an ELEMENTAL BUILDING page of the four elements; ENTER seats one
  beside the hero and the status line says which.
- `devtools/element_building.py::spawn_elemental_building(ps, element)`
  builds it the way the world does: `world.gen.buildings._seat` for the
  compound (the primary carries the art, the satellites only collide),
  `GameMap.obstacles`' setter so the obstacle index is rebuilt,
  `reskin_obstacle` with the kind's first rig at the bake's size, and an
  `Interactable` carrying the element on the run's list — so using it runs
  the ordinary buff, then the infusion picker for its element.
- The kind takes the buff kinds in turn (`DevFlags.building_turn`), so
  every building can be tried; the spot is the first on rings of 3, 4.5, 6
  and 8 tiles round the hero where every circle of the compound is on
  walkable ground and clear of every obstacle.
- **CMB-009.D4 — What it does not do.** The navigation field is baked at
  run start and is not rebuilt, so enemies do not route round a spawned
  building; they collide with it and slide, as round any obstacle the
  field did not know. The spot search takes any walkable ground, so a
  building can land on another terrace than the hero's. Both are
  acceptable for a dev tool; a run that needs a real one takes a seed.
- `tests/devtools/test_element_building.py` (integration tier, listed in
  `conftest.INTEGRATION`, pinned seed): 7 tests — seated as a compound
  with its art and in the rebuilt index; placed where the spot search said
  and near the hero; carries the chosen element; the kinds come in turn;
  using it runs the buff and opens the element's weapon picker; no room
  says so and adds nothing; the dev-menu page exists.
- **Screenshot:** a seed-7 developer run with one building of each
  element seated by the tool, each with its CMB-009.1 glow.
- **Tests:** `tests/devtools` + `tests/screens` + `test_dev_mode` +
  `test_interactables` + `test_infusion_sources` — 718 passed, 28
  subtests, 0 skipped (6 min 13 s).

**CMB-009 closed** (2026-09-23): all five tasks landed, each in its own
commit. The design document's three open boxes it answered (§8.2's
building visual, §9.8's counters, §10.3's extras) are ticked there.
