# Elemental System — Design & Implementation Plan (v3)

> **Status:** Revision 9. The system is **built** (CMB-005) and its reaction damage model was **reworked** (CMB-006, 2026-09-22); this document describes the shipped behaviour, not a plan. Items marked **[PROPOSAL]** are suggested defaults that fill gaps in the brief. Items marked **[OPEN]** need a design decision before implementation. Claude Code must **not** silently pick an answer for an [OPEN] item. Implement the proposal only if it has been confirmed, or ask.
>
> **v2 changes:** all elements leave an aura; aura and status are separate values; the Wind area is a brief ~1 s effect; Thunder uses a branching jump model; range and per-source target caps; aura-slot lock per reaction (Frostburn); dual element is dev/scaffolding only with a strict resolution order; infusions are run-scoped. Resolved items are recorded in §13.
>
> **v3 changes:** a reaction fully replaces the incoming element's initial effect, and reaction values can vary by which element triggered it (directional variants); hits on a locked aura slot apply the initial effect only; Thunder jump targets receive a Thunder aura; "Both" mode on a clean enemy goes straight to the pair reaction; ThunderWind uses one extended jump tree; the weapon set is fixed (survivor-style), so infusions stay on their weapon through upgrades.
>
> **v4 changes:** a Thunder jump into a different aura deals its damage, consumes the aura, triggers the reaction, and does not spread further from that enemy; Overload's shockwave deals damage + knockback (emergent "pinball" behavior is intended); Superconduct spreads Slow only, with more jumps than base Thunder; ThunderWind strikes the N closest enemies (no tree); weapons get an `elementInterval` value; every reaction starts a global aura-slot cooldown on that enemy.
>
> **v5 changes:** dual-element support is removed, so each weapon holds **exactly one** element; Thunder jumps into a different aura trigger the reaction only (no jump damage), consistent with direct hits; locked enemies still receive Burn/Slow as standalone statuses; all weapons are cooldown-based, so one firing = one attack.
>
> **v6 changes:** frozen enemies get knocked back and can optionally deal contact damage; Fire has direct hit damage; buffs apply per element everywhere; the Monastery no longer rolls an element and lets the player pick one element for one weapon; the pool now simply stores the elements unlocked this run.
>
> **v7 changes:** per-enemy-type elemental resistance profiles (bosses override values or toggle effects, but no enemy is fully immune to elements); damage tracking credits damage to the effect/reaction while keeping the source weapon, with a per-weapon summary of element applications; frozen contact hits don't chain; enemies dying mid-resolution are skipped safely.
>
> **v8 changes:** enemy profiles can disable auras (the enemy still takes element damage and statuses but never reacts); source-weapon rules confirmed; the Monastery offers every element and can be used once; unlocked elements are tracked for the run summary.
>
> **v9 changes (CMB-006, 2026-09-22 — reaction damage rework):** a reaction is paid from **both** hits that produced it, not from the one that triggered it, as `high × the larger + low × the smaller`; the same figure lands on the enemy it fired on **and** on every enemy it reaches, raised to a global floor on the carrier alone; the Wind three and Superconduct **prime what they reach with their own element**, which retires §5.3 and §5.4 — a spread aura meeting a different one starts another reaction, uncapped in depth. §5.6's open question about flat versus weapon-scaled damage is closed by the same decision.

---

## 0. How to use this document (instructions for Claude Code)

- **Read the existing codebase first.** Before writing code, locate and summarize: the weapon system, the hit/damage pipeline, the enemy entity/update loop, the existing particle system, buff buildings and spawning, the run lifecycle (start/end of run), the JSON data-loading approach, and developer mode. Adapt every interface below to the project's actual language, engine, and conventions.
- **Work milestone by milestone** (§12). Each milestone should compile, run, and pass its acceptance checks before the next one starts.
- **Elements are code, not data.** Elements are source files implementing a shared interface. JSON only *tunes* numeric values of existing behaviors (§2.3).
- **Performance is a hard requirement.** Target: ~100 enemies on screen with active auras and reactions, with no frame drops attributable to this system (§9).
- Track unresolved questions in §13 and update it as decisions are made.

---

## 1. Glossary

| Term | Meaning |
|---|---|
| **Element** | One of the magical types (Fire, Ice, Thunder, Wind). Defined in code. |
| **Initial effect** | What an element does on hit (damage, chain, wind area...). |
| **Aura** | The single reactable element marker on an enemy. Max one per enemy. Every element leaves one. |
| **Status effect** | A gameplay effect on an enemy (Burn, Slow, Freeze, Frostburn...). Separate from the aura. Several can coexist. Statuses never react. |
| **Bound status** | A base element's status that shares its aura's lifetime (Fire → Burn, Ice → Slow). |
| **Aura lock** | A state where the aura slot cannot receive a new aura. Every reaction starts one (global cooldown). Some reactions extend it (Frostburn). |
| **Element interval** | Weapon value: how many attacks are skipped between element-carrying attacks (0 = every attack). |
| **Reaction** | The effect produced when an enemy with aura A is hit by element B (A ≠ B). Consumes the aura. |
| **Jump** | One step of a Thunder chain. `jumps` is the remaining spread counter (§4.3). |
| **Wind area** | A brief (~1 s) circular "tornado" effect around the enemy hit by Wind. |
| **Source** | One originating hit or reaction. Caps (range, max targets) are counted per source. |
| **Infusion** | An element attached to a weapon slot. Run-scoped buff/blessing. |
| **Unlocked elements** | Run-scoped set of elements the player has obtained this run (no duplicates). |
| **Monastery** | Special building where the player picks any element for one weapon. |

---

## 2. Core Architecture

### Objectives
- A single parent interface that every element implements, with the minimum data required for an element to exist in-game.
- A data layer where JSON can adjust values but never add or remove behavior.
- A clean split between **static** values (resolved at load) and **dynamic** values (changed at runtime by buffs/blessings).

### Tasks
- [x] **2.1 Element identifiers.** Use a compact integer enum (`ElementId: None=0, Fire=1, Ice=2, Thunder=3, Wind=4`). No string lookups in the hot path.
- [x] **2.2 Element interface.** Define a parent interface/abstract class. Suggested shape (adapt to project language):

  ```
  interface Element {
      id: ElementId
      visual: ElementVisualProfile            // §8
      auraDuration: float                     // from config

      applyInitialEffect(target, source, ctx)  // damage, chain, wind area...
      onAuraApplied(target, ctx)               // create/refresh the bound status, if any
      onAuraRefreshed(target, ctx)             // same element hit again
      onAuraEnded(target, reason, ctx)         // reason: Expired | Consumed | Death
  }
  ```

- [x] **2.3 Config (JSON tuning).**
  - One config file per element, plus one for reactions. JSON exposes only the numeric parameters listed in §4 and §5 (damage, duration, interval, radius, count, intensity, caps, lock flags).
  - Validate on load: reject unknown keys, enforce ranges (e.g., `duration > 0`, `jumps >= 0`, `maxTargets >= 1`), fall back to code defaults with a logged warning.
  - At load, bake JSON into an **immutable config object** per element and reaction. No JSON parsing or dictionary lookups during gameplay.
- [x] **2.4 Runtime modifiers (buffs, blessings, special effects).**
  - Layer modifiers on top of baked config: `effective = (base + flatBonus) × multiplier`.
  - Cache the effective config. Recompute only when a modifier is added or removed (dirty flag), never per hit.
- [x] **2.5 Element registry.** A fixed-size array indexed by `ElementId` holding the element instances and their effective configs.

### Considerations
- Keep element behavior stateless. All per-enemy state lives in the enemy's aura/status data (§3), so one element instance serves all enemies.
- **Modifiers are global per element** *(confirmed)*: a buff to Fire affects all Fire everywhere, on every weapon. Effective configs are cached **per element** (4 cached configs, one dirty flag each), not per weapon.

---

## 3. Aura & Status System

### Rules (confirmed)
- **Every element leaves an aura** on the enemy, on top of its initial effect.
- **Aura and status are separate values.** The aura is only the reactable marker. Statuses carry the gameplay effects.
- **Base element statuses share their aura's duration:** Fire's Burn and Ice's Slow start, refresh, and end with the aura. If the aura is consumed by a reaction, its bound status ends too.
- A reaction consumes the aura.
- **Global reaction cooldown** *(confirmed)*: after any reaction, that enemy's aura slot is locked for `globalReactionAuraCooldown` seconds (one value in a global elemental config JSON). During the lock, elements still deal damage and apply their effects. Only the aura slot is blocked, so no new aura and no new reaction.
- A reaction may lock the slot longer via its own `lockDuration` (Frostburn does). The effective lock is `lockedUntil = now + max(globalReactionAuraCooldown, reaction.lockDuration)`.

### Tasks
- [x] **3.1 Enemy elemental state.** Compact structs on each enemy:

  ```
  AuraState {
      element: ElementId       // None when empty
      expiresAt: float         // absolute game time, not a countdown
      lockedUntil: float       // aura slot locked while now < lockedUntil
      sourceWeapon: WeaponId   // weapon that applied the aura (tracking only, §3.6)
  }

  StatusList {               // small fixed capacity, no allocations
      Burn       { tickDamage, nextTickAt, expiresAt, boundToAura, sourceWeapon }
      Slow       { stacks, percent, expiresAt, boundToAura, sourceWeapon }
      Freeze     { expiresAt, sourceWeapon }
      Frostburn  { tickDamage, slowPercent, nextTickAt, expiresAt, sourceWeapon }
      ...
  }
  ```

  Timestamps are absolute, so expiry is a comparison, not a per-frame decrement. Ice stacks live on the **Slow status**, not the aura, so reactions can apply slow stacks without applying an aura (§5).
- [x] **3.2 Single-element hit resolution.** For each elemental hit with element `E`:
  1. Weapon base damage (existing pipeline).
  2. **Aura slot locked** → apply `E`'s initial effect and effects. No aura, no reaction. *(confirmed)*
     - Fire's Burn and Ice's Slow are normally bound to their aura. On a locked enemy they are applied as **standalone** statuses using the same duration value the aura would have had. Ice stacks still accumulate and can freeze. *(confirmed)*
  3. **Aura = None** → `E` initial effect → set aura `E` → create bound status.
  4. **Aura = E** → `E` initial effect → refresh aura and bound status duration → add stack where applicable (Ice).
  5. **Aura = A ≠ E** → consume aura `A` (its bound status ends) → run reaction `(A, E)` using the variant for trigger `E` (§5.2) → apply the aura lock (§3 rules). **`E`'s initial effect does not apply and `E` leaves no aura.** The reaction fully replaces it. *(confirmed, applies to direct hits and Thunder jumps alike)*
- [-] **3.3 Tick pass.** Maintain a list of enemies with ticking statuses (Burn, Frostburn). Iterate only that list, at their tick intervals. *(DOC-003: superseded — statuses ride the status framework's own per-frame countdown (elemental journal, M3 notes))*
- [x] **3.4 Cleanup on death.** Clear aura and statuses, return VFX and pending effects to their pools.
  - **Death mid-resolution** *(confirmed)*: if an enemy dies partway through a jump tree, reaction, or Wind area, it is skipped safely. No effect may reference it afterward, and the chain continues from the other nodes. Use a generation/alive check on enemy handles, not raw references.
- [x] **3.5 Enemy elemental profiles (resistances)** *(confirmed)*.
  - **Every enemy can be affected by elements.** There is no full elemental immunity. Bosses and special enemies differ only through **per-enemy-type overrides** of element values or **toggles** for specific effects.
  - Defined in the enemy type's JSON as an optional `elementProfile`. Each entry overrides a specific element/effect value or disables a specific effect. Examples:

    ```json
    "elementProfile": {
      "ice":      { "freeze.stacksRequired": 12, "slow.maxPercent": 20 },
      "freeze":   { "enabled": false },
      "wind":     { "knockbackMultiplier": 0.2 },
      "overload": { "knockbackMultiplier": 0.0 },
      "damageMultiplier": { "fire": 0.8, "thunder": 1.0 }
    }
    ```

  - Allowed keys are a **whitelisted schema** of existing parameters (stack thresholds, durations, slow caps, knockback multipliers, per-element/per-reaction damage multipliers) plus `enabled` toggles for secondary effects (Freeze, Slow, knockback, frozen contact damage).
  - **Aura toggle** *(confirmed)*: `"aura": { "enabled": false }` makes that enemy type **immune to reactions**. This prevents mass reaction chaining on specific enemies and keeps reactions spaced out. The enemy is still affected by every element's **damage and statuses**.
    - Implementation: treat it as a **permanently locked aura slot**. It reuses the locked-slot path from §3.2 step 2 (initial effect and effects apply, Fire/Ice apply standalone Burn/Slow, no aura, no reaction). No new branch is needed.
    - Thunder jumps through such an enemy follow the same rule as a locked node (§4.3).
  - **Bake at load:** each enemy type gets a resolved profile (defaults merged with overrides). Enemies hold a reference to their type's profile, and the element code reads values through it. Enemies without overrides share one default profile. No per-hit merging.
  - Profile values combine with global element modifiers: `effective = elementEffectiveConfig` adjusted by the enemy profile override or multiplier.
- [x] **3.6 Damage & application tracking** *(confirmed)*.
  - Every piece of elemental damage is **credited to the effect that dealt it** (Fire hit, Burn, Thunder jump, Overload, Frostburn, frozen contact...), not to a weapon. Every record still carries its **source weapon**.
  - The run keeps two summaries, both **classified by source weapon**:
    - **Damage:** `damage[weapon][effect]`, so totals can be shown per effect (e.g., "Overload: 12,400") and broken down by the weapon that started it.
    - **Element applications:** `applications[weapon][element]`, counting how many times each weapon applied its element (plus `reactions[weapon][reaction]` counts).
    - **Unlocked elements** *(confirmed)*: the run summary also includes the run's unlocked-element set (§7.3).
  - Implementation: fixed-size numeric arrays indexed by enum IDs (weapon count and effect count are both fixed). Recording is one array increment per damage event. No strings, maps, or allocations in the hot path.
  - **Source rules** *(confirmed)*:
    - Base element damage and its bound status: the weapon that applied it.
    - A reaction and everything it spawns (shockwave, jumps, Wind area, Frostburn ticks): the weapon whose hit **triggered** the reaction (the incoming element).
    - Thunder jump nodes and reactions they trigger: the weapon of the original Thunder hit.
    - Frozen contact damage: credited to the "Frozen contact" effect, with the source weapon being the one whose knockback pushed the frozen enemy.

### Considerations
- Thunder and Wind auras have no bound status. They are pure reactable markers with their own configurable duration.
- **Settled in code** *(open question 8)*: a reaction consuming an Ice aura while the enemy is **frozen** does not end the Freeze. `freeze` is its own status and is never bound to the aura, so the resolver's `end_bound()` leaves it; only the `chill` goes. `combat/elements/ice.py` cites the question by number.

---

## 4. Base Elements

Every value below is a JSON-tunable parameter. Suggested JSON keys are shown. Every element also has `aura.duration`.

### Area caps (applies to every effect that reaches other enemies)
Each source carries `maxRange` (max distance to reach a target) and `maxTargets` (total enemies affected by that source, excluding the originally hit enemy). This covers Thunder chains, Wind areas, the Overload shockwave, Superconduct, and the Wind reactions.

### 4.1 Fire: Burn
- **Initial effect:** direct hit damage `fire.damage` *(confirmed)*, then the Fire aura and its Burn, which deals damage on its own.
- **Aura:** Fire. **Bound status:** Burn, same duration as the aura.

| Param | JSON key |
|---|---|
| Hit damage | `fire.damage` |
| Tick damage | `burn.tickDamage` |
| Tick interval (s) | `burn.tickInterval` (brief: 1 s) |
| Aura / burn duration (s) | `aura.duration` |

- Reapply refreshes the duration and does not stack damage. **[PROPOSAL]**

### 4.2 Ice: Slow → Freeze
- **Aura:** Ice. **Bound status:** Slow, same duration as the aura. Each Ice hit adds a stack to the Slow status.

| Param | JSON key |
|---|---|
| Slow % per stack (Z) | `slow.percentPerStack` |
| Slow cap | `slow.maxPercent` **[PROPOSAL]** |
| Stacks to freeze (X) | `freeze.stacksRequired` |
| Freeze duration (Y) | `freeze.duration` |
| Freeze immunity after thaw | `freeze.immunityDuration` **[PROPOSAL]** |
| Aura / slow duration | `aura.duration` |

- [x] On reaching X stacks: apply Freeze for Y s and reset Slow stacks to 0.
- **Settled in code** *(open question 9)*: the Ice aura remains after a freeze triggers. Freezing touches the stack counter and the statuses, never the aura slot, so it falls out of the implementation rather than needing a branch.
- **Frozen enemies are not immune to knockback** *(confirmed)*. Wind areas and Overload shockwaves push them away like any other enemy. The freeze stops the enemy's own movement, not external knockback. **[PROPOSAL]** Being knocked back does not end the freeze.
- **Addendum: frozen contact damage** *(confirmed, optional)*. A frozen enemy that is knocked back by another source can deal contact damage to enemies it collides with while sliding.
  - Toggle: `freeze.knockbackContactDamage.enabled` (JSON, bool).
  - **The damage calculation already exists in the project.** Claude Code must reuse the existing contact/collision damage logic and not write a new formula. Milestone 0 should locate it.
  - Contact hits deal damage only: no aura, no reaction, **no knockback transfer**, so hit enemies don't chain further *(confirmed)*. **[PROPOSAL]** Each enemy can be hit at most once per knockback instance, and contact only counts while the frozen enemy is being knocked back.

### 4.3 Thunder: Branching Jumps (confirmed model)
- **Initial effect:** damage X to the hit enemy, then spread by jumps. **Aura:** Thunder (marker only).
- **Jump rule:** every Thunder node carries a `jumps` counter.
  - `jumps = 0` → hits the enemy, does not spread.
  - `jumps = N > 0` → hits the enemy, then spreads to the **closest `targetsPerJump` (Y) enemies** within `maxRange`. Each of those becomes a node with `jumps = N − 1`.
  - Example: `jumps = 1, Y = 3` → target + up to 3 neighbors, then the chain ends.
- Resolve breadth-first (one jump level at a time). An enemy is never hit twice by the same chain. The chain stops when `maxTargets` for the source is reached.

| Param | JSON key |
|---|---|
| Damage (X) | `chain.damage` |
| Targets per jump (Y) | `chain.targetsPerJump` |
| Jumps | `chain.jumps` |
| Jump range | `chain.maxRange` |
| Max targets per source | `chain.maxTargets` |
| Damage falloff per jump level | `chain.falloff` (optional, default 1.0) |

- Worst-case target count grows as `Y + Y² + … + Y^jumps`, so `maxTargets` is mandatory.
- **Jump target resolution** *(confirmed)*. Each enemy reached by a jump is resolved by its state:
  - **No aura / Thunder aura:** jump damage → Thunder aura applied or refreshed → spreads further if the node has `jumps > 0`. Thunder spreading auras widely is intended.
  - **Different aura:** **no jump damage** → aura consumed → reaction triggers (e.g., Overload, which deals its own damage) → **this node does not spread further.** Other branches of the tree continue normally. *(confirmed)*
  - **Locked slot:** jump damage only, no aura. The node still spreads normally, behaving like a no-aura node *(confirmed, open question 1)*.
- A single Thunder hit into a crowd with Fire auras can therefore set off many Overloads. This is intended. It is bounded by `chain.maxTargets`, each reaction's own caps, the global reaction cooldown, and the per-frame reaction budget (§9.3).

### 4.4 Wind: Brief Tornado Area (confirmed model)
- **Initial effect:** low damage X to the hit enemy, then spawns a **Wind area**: a tornado-like circular effect around that enemy lasting about 1 s. Enemies inside take the area's damage and are knocked back radially from the center. **Aura:** Wind (marker only).

| Param | JSON key |
|---|---|
| Hit damage (X) | `wind.damage` |
| Area duration (s) | `area.duration` (~1.0) |
| Area radius | `area.radius` (also bounded by `maxRange`) |
| Area contact damage | `area.damage` |
| Knockback (Z) | `area.knockback` |
| Max targets per source | `area.maxTargets` |

- [x] **Wind area is a reusable component** (`WindAreaEffect`) with a swappable **payload**: damage, knockback, and an optional extra effect. The Wind reactions (§5) reuse it with different payloads.
- **[PROPOSAL]** The area follows the inflicted enemy. Each enemy is hit at most once per area instance. The inflicted enemy itself is not knocked back. Contact checks run on spawn and then at a low fixed rate (e.g., 10 Hz) for its lifetime.
- **Settled in code** *(open question 10)*: late entrants **are** hit. `WindArea` follows its anchor and re-queries at `CHECK_HZ` (10 Hz) for its whole life, contacting each body at most once per area instance.

---

## 5. Reactions

### 5.1 Reaction table
Each unordered pair produces **one reaction type** (Fire+Ice is always Frostburn). However, the **triggering element can change its values** (§5.2). The lookup is therefore an ordered table indexed by `(auraElement, incomingElement)`: a flat 5×5 array, O(1). Both cells of a pair point to the same reaction type but to their own baked variant config.

Every reaction's damage is one figure read from **both** source hits (§5.6),
dealt to the enemy it fired on *and* to every enemy it reaches.

| Pair | Name | Effect summary | Spreads | Extra aura lock |
|---|---|---|---|---|
| Fire + Ice | **Frostburn** | Immediate damage, then a burn paid over `ticks` ticks, plus slow Z%. Never freezes. | — | **Yes**, by default for the status duration |
| Fire + Thunder | **Overload** | Damage to the target + a circular shockwave radius Y dealing the **same** damage and knockback Z to nearby enemies. | — | No |
| Ice + Thunder | **Superconduct** | Damage to the target + a jump spread carrying that same damage, Ice stacks and the **Ice aura**, with more jumps than base Thunder. | Ice | No |
| Fire + Wind | **FireWind** | Wind area with fire payload; primes contacts with **Fire**. | Fire | No |
| Ice + Wind | **IceWind** | Wind area with ice payload; primes contacts with **Ice**. | Ice | No |
| Thunder + Wind | **ThunderWind** | Wind area priming contacts with **Thunder**, + a Thunder strike on the N closest enemies to the target. | Thunder | No |

All reactions start the global aura cooldown (§3). Each reaction can additionally have `lockAuraSlot` (bool) and `lockDuration` (s) in JSON. The longer of the two wins. Frostburn defaults to `true` with `lockDuration = status duration`. All others default to `false`.

### 5.2 Directional variants (confirmed)
A reaction's behavior is the same regardless of order, but its **values** can differ depending on which element triggered it (the incoming element). JSON defines base values plus optional per-trigger overrides:

```json
{
  "overload": {
    "damage": 40, "shockwaveRadius": 3.0, "knockback": 6.0, "maxTargets": 12,
    "triggeredBy": {
      "fire":    { "damage": 50 },
      "thunder": { "shockwaveRadius": 4.0 }
    }
  }
}
```

- At load, bake **two configs per reaction** (one per trigger direction) by merging overrides onto the base. No merging at runtime.
- An override may only touch keys that exist in the reaction's base schema (validated).
- Default with no overrides: both directions are identical.
- **Parked** *(owner, 2026-09-22; open question 6)*: **no reaction differs by trigger today, and none needs to.** All six pay the same figure whichever element arrives second, which is also what §5.6's symmetry guarantees.
  - The machinery stays because it costs nothing idle: `triggered_by` is validated, baked per direction and covered by tests, so making order matter later is a **data edit and no code**. A future pass might use it to give a pair a different character depending on which element closed it — a Fire-triggered Overload hitting harder than a Thunder-triggered one, say — without touching `combat/elements/`.

### 5.3 Secondary-hit rule *(rewritten in v9 — CMB-006)*

> **Superseded.** Through v8 this section read: "hits that a reaction delivers
> to *other* enemies apply **statuses and damage only, never auras**, so they
> cannot trigger further reactions." That rule is gone. It is kept here in
> quotation because §5.4, §11 and R2 were all built on it.

What a reaction's secondary hits do now depends on the reaction:

- **Overload** and **Frostburn** spread nothing. Their secondary hits carry
  damage, knockback and statuses, never an aura, so they remain terminal.
- **FireWind**, **IceWind** and **ThunderWind** prime every body their tornado
  contacts with **their own element** — Fire, Ice and Thunder respectively —
  on top of the payload each already applied.
- **Superconduct** primes every body its jump tree reaches with the **Ice**
  aura, alongside the damage and the Ice stacks.

A spread aura is laid through the ordinary resolution path, so landing one on
an enemy that already holds a *different* aura consumes it and runs that pair's
reaction. Every reaction still has its own `maxRange` and `maxTargets`.

> **Note** *(still true)*: base Thunder jumps are *not* reaction hits. They are
> the Thunder element itself, so they apply auras (§4.3).

**Ordering inside one contact:** the aura is spread **first** and the
reaction's own payload is applied **over** it. Priming a body runs that
element's `onApplied`, which for Fire is a burn and for Ice a slow — the same
status rows FireWind and IceWind write — and the last writer owns the row's
credit, tick interval and aura binding. Spreading first is what keeps
FireWind's damage-over-time credited to FireWind and standalone rather than
silently becoming plain Burn bound to the aura that carried it in.

### 5.4 Reaction depth *(rewritten in v9 — CMB-006)*

> **Superseded.** Through v8: "reaction depth is therefore always 1."

A reaction's spread aura can trigger another reaction, which can spread again.
**There is no depth cap** — this was put to the owner with the blow-up risk
stated and chosen deliberately. Three things bound a cascade instead:

1. **The per-enemy aura lock.** A body that has just reacted takes no new aura
   for `globalReactionAuraCooldown`, so a cascade cannot revisit ground it has
   already covered.
2. **The per-frame reaction budget.** `maxReactionsPerFrame` caps how many run
   in one frame and defers the rest to the next, dropping none. This is also
   what caps recursion depth, since a cascade resolves inside the frame budget.
3. **Decaying value.** A spread aura carries the damage that body just took,
   not the original weapon hit, so each generation is paid from a smaller
   figure than the last.

A cascade's *reach* is unbounded; only its value decays. If play shows it is
too wild, the cheapest lever is a depth cap rather than a coefficient change,
and the implementation keeps a single seam for one
(`ElementalResolver.spread_aura`).

### 5.5 Per-reaction parameters (JSON) *(updated in v9)*
All values below can have per-trigger overrides (§5.2). Every `damage` is a
**pair** `{high, low}` resolved against both source hits (§5.6); the other
damage values are plain fractions of the larger source hit.

- **Frostburn:** `damage` (immediate, weighted toward the *smaller* source hit), `tick` (the burn's **total** worth), `ticks` (how many ticks it is divided across), `tickInterval`, `duration` (the slow's), `slowPercent` (Z), `lockAuraSlot`, `lockDuration`.
  - `tick` names what the burn is *worth*, not what one tick of it is, so changing `ticks` redistributes the same damage rather than multiplying it. The burn's own duration is derived as `ticks × tickInterval`, so no second value can drift from it.
  - Spreads nothing; reaches nobody but its own carrier.
- **Overload:** `damage` (paid to the target **and** to everything the shockwave reaches), `shockwaveRadius` (Y), `knockback` (Z), `maxKnockbackSpeed`, `maxRange`, `maxTargets`. There is no separate `shockwaveDamage`: one figure covers both.
  - **Pinball behavior** *(confirmed, intended)*: repeated Overloads (e.g., from a Thunder tree through Fire-aura enemies) bounce enemies around. This emerges from knockback alone. No collision damage between knocked-back enemies; knockback reuses the game's existing movement/physics, and `maxKnockbackSpeed` clamps the accumulated impulse so stacked shockwaves don't fling enemies off-screen or through walls.
  - Spreads nothing.
- **Superconduct:** `damage` (paid to the target **and** to every enemy the tree reaches), `bonusJumps`, `targetsPerJump`, `iceStacks`, `slowDuration`, `maxRange`, `maxTargets`. Uses the §4.3 jump model.
  - Each enemy reached takes the damage, is brought to `iceStacks` Ice stacks through Ice's own model, and is **primed with the Ice aura**. It has no `slowPercent` of its own: Ice sizes the slow from the stack count, so a second figure would be one nothing reads.
  - The stack count is reached by **counting, not adding**: priming a body with Ice runs Ice's `onApplied`, which is worth one stack, so the spread tops up to `iceStacks` rather than adding that many on top.
  - Its jumps must exceed base Thunder's *(confirmed)*: defined as `thunder.chain.jumps + bonusJumps` with `bonusJumps ≥ 1`, so buffs to Thunder's jumps carry over and the "more than Thunder" rule can't be broken by JSON edits.
  - Its stacks **do** add freeze stacks, reversing the v8 proposal — they go through Ice's model, so each body's own profile still decides its threshold.
- **FireWind:** Wind area with `damage` (paid to the carrier and to every contact), `knockback`, and payload: **Burn status** on contacted enemies (`burnTick`, `burnTickInterval`, `burnDuration`), plus the **Fire aura**. Burn here is a standalone status, not bound to an aura.
- **IceWind:** Wind area with `damage`, `knockback`, and payload: **+Y Ice stacks** per contact (`stacksPerContact`, `slowDuration`), plus the **Ice aura**. These stacks can trigger Freeze *(confirmed)*.
  - A contacted body ends on `stacksPerContact + 1` stacks: the payload's, plus the one the spread Ice aura's own application is worth. Both halves are paid deliberately.
- **ThunderWind:** Wind area with contact `damage` and knockback, priming each contact with the **Thunder aura**, plus a Thunder strike delivered **through the reacting enemy** to the **N closest enemies by absolute distance** *(confirmed)*. This is a single nearest-N query, not a jump tree. N should be high.
  - Params: `strikeTargets` (N), `strikeDamage`, `strikeRange`.
  - N is `max(strikeTargets, thunder.chain.targetsPerJump × (thunder.chain.jumps + 1))`, so it's never weaker than a base Thunder spread.
  - The **strike** applies no aura — only the tornado primes. A body inside the strike's range but outside the tornado's radius takes damage and nothing more.

### 5.6 Damage formula *(resolved in v9 — closes open question 11)*

Element damage is a fraction of the hit that carried it. **Reaction** damage is
read from the two hits that produced the reaction:

```
A = the weapon damage of the hit that PLACED the aura
B = the weapon damage of the hit that TRIGGERED the reaction
reactionDamage = high x max(A, B) + low x min(A, B)
```

Four properties are deliberate:

- **Symmetric.** Which of the two placed the aura and which triggered it is
  bookkeeping. A formula that read them in a fixed order would pay differently
  depending on which weapon happened to fire second.
- **One shape for all six.** A reaction that pays the same share of both — the
  Wind three, at 30 % of each — sets `high == low`, and the expression
  collapses to `0.30 × (A + B)`. No second form to maintain.
- **A floor, on the carrier only.** The figure is raised to
  `globalReactionMinDamage` on the enemy whose aura was consumed. Bodies the
  reaction spreads to take the raw figure. Without this, two small hits produced
  a reaction that rounded to a visible `0` in the damage numbers.
- **A fallback.** An aura carrying no damage of its own (a slot filled by
  something with no weapon damage behind it) resolves as if `A == B`, so a
  reaction is never paid as though one of its halves were free.

The aura therefore has to **remember the hit that placed it**. A refresh keeps
the *larger* of the two rather than the latest: a refresh is the same aura being
kept alive, and letting a cheap fast weapon overwrite a heavy one would let it
quietly defuse a reaction the player set up with a slow expensive one.

A spread aura (§5.3) carries the damage its body just took, which is what makes
a cascade decay in value.

---

## 6. Weapon Infusion

### Rules (confirmed)
- Each weapon holds **exactly one** element (or none). There are no dual elements and no element modes.
- A new element on an already-infused weapon replaces the old one (§7).

### Tasks
- [x] **6.1 Weapon element data:** a single `element: ElementId` field (default `None`). No arrays or slot indices, so the one-element rule is enforced by the data type itself.
- [x] **6.2 Hit entry point:** every weapon hit calls the single-element resolution in §3.2 with the weapon's element (if the attack carries it, §6.3).
- [-] **6.3 Element interval** *(confirmed)*: new weapon metadata `elementInterval` (JSON, default `0`). *(DOC-003: superseded — shipped as `element_application`, see the note below)*
  *(DOC-003: as shipped, each weapon's JSON carries `element_application` — attack mode `{"mode": "attack", "interval": N}` applies on every (N+1)th attack, time mode `{"mode": "time", "window": s}` once per window; see `elemental_system_journal.md` M6 and CMB-007.3.)*
  - `0` → every attack carries the element. `1` → every other attack (inflict, skip, inflict...). `N` → one element attack, then N plain attacks.
  - All weapons are cooldown-based: a weapon fires when its internal cooldown finishes, and **one firing = one attack** *(confirmed)*. There are no continuous/ticking weapons.
  - One counter per weapon, advanced once per attack. Every hit produced by that attack (all projectiles, pierces) shares the attack's element flag, stamped on the projectile/hitbox at spawn. No per-hit checks.
  - Plain attacks deal weapon damage only: no initial effect, no aura, no reaction.
  - **Possible, unused** *(owner, 2026-09-22; open question 5)*: a weapon keeps its infusion across upgrades by construction — the element lives on the weapon object and weapons are upgraded, never replaced (R16) — and nothing in `blessings.json` touches the application cadence. Level-ups changing it is supported in principle and **not required**; it is recorded here as something the data could express later rather than as a gap.
- [x] **6.4 Visuals:** the weapon shows its infusion using the shared visual profile (§8). Element-carrying projectiles should look different from plain ones.

---

## 7. Element Acquisition (run-scoped)

### Rules (confirmed)
- Infusions are buffs/blessings obtained mid-run and exist only during that run.
- An infusion is assigned to the weapon chosen at the moment of acquisition.
- Everything (infusions, unlocked elements) is cleared at run end.

### 7.1 Special infused buff buildings
- [x] On spawn, roll whether the building is elemental and which element (weights in JSON).
- [x] On interaction, the player picks one of the 3 equipped weapons. The rolled element is assigned to it, replacing any previous element.

### 7.2 Monastery *(confirmed, redesigned)*
- [x] Works like a special infused buff building, but it **does not roll an element**. Instead, the player **picks an element** from a selection, then **picks one weapon** to infuse.
- [x] The selection offers **every element in the game** (currently 4), regardless of what's unlocked. *(confirmed)*
- [x] **One use per Monastery:** one element, one weapon, then the Monastery is spent. *(confirmed)*

### 7.3 Unlocked elements *(confirmed)*
- [x] Run-scoped **set** of elements the player has obtained this run. No duplicates, so its size can't exceed the element count, and no capacity limit is needed.
- [x] Tracked in code for **summary purposes** *(confirmed)*: it's included in the run summary (§3.6) and shown in dev mode. No gameplay system reads it for now.

### Considerations
- **Fixed weapon set (confirmed).** The game is survivor-style (Vampire Survivors-like): the player's weapons are a constant set that is never swapped. Weapons only gain levels/stronger versions and fire automatically in their own patterns and timings. The infusion therefore lives on the weapon for the whole run.
- **[confirmed, R48]** Weapon upgrades and evolutions keep the weapon's infusion. *(DOC-003: answered by §13 R48)*
- Every weapon's hit path (whatever projectile/hitbox types exist) must route through the same elemental hit entry point (§9.3). Milestone 0 must list every weapon's damage path so none is missed.

---

## 8. Visual System (shared element VFX)

### Objectives
- One standardized way to show any element on enemies, buildings, and weapons. Actors only control position, scale, intensity, and anchor.
- Reuse the existing primitive particle system.
- Every reaction shows both elements interacting.

### Tasks
- [x] **8.1 `ElementVisualProfile` per element:** colors, tint, particle preset (existing particle system), sprite/animation refs, default intensity.
- [-] **8.2 `ElementVisualComponent`** attachable to any actor: `element`, `anchorOffset`, `scale`, `intensity`. Intensity can be driven by Slow stacks. The same component is used for enemies, buildings, and weapons. *(DOC-003: superseded — no generic component; enemies and weapons draw their element directly (`visual/elements/`, `rendering.py`). The building gap is the new box below)*
- [ ] **Elemental buff buildings show their rolled element.** `Interactable.element` is set (M7) but nothing draws it, so the player learns the element only on use. *(DOC-003: found missing)*
- [x] **8.3 Aura vs status visuals.** The aura indicator (reactable marker) and status visuals (burning, slowed, frozen) are distinct layers. The aura must be readable because it's the only in-game indicator. A **locked** aura slot (Frostburn) should also be visually recognizable. **[PROPOSAL]**
- [x] **8.4 Wind area visual:** one tornado ring effect (~1 s, scaled to `area.radius`). The Wind reactions reuse it, tinted/particled with the other element's profile (FireWind, IceWind, ThunderWind).
- [x] **8.5 Reaction visuals:** each reaction uses a dedicated effect or a generated blend of both profiles. Start with blends and add bespoke effects later.
- [x] **8.6 Thunder jumps:** a reusable line/arc effect between nodes, pooled.
- **[PROPOSAL]** Distinguish elements by shape/motion as well as color (colorblind accessibility).

### Considerations
- **Particle budget:** 100 enemies with auras + statuses + areas can overwhelm a primitive particle system. **[PROPOSAL]** Use a cheap tint/outline shader as the baseline aura indicator and add particles up to a global cap (LOD).
- Audit the particle system's limits in Milestone 0.

---

## 9. Performance

### Static vs dynamic values

| Static (resolve at load, bake) | Dynamic (runtime) |
|---|---|
| Element definitions and behaviors | `AuraState` (element, expiry, lock) |
| JSON base values, caps, lock flags | `StatusList` contents |
| Reaction lookup table | In-flight jump trees, active Wind areas |
| Visual profiles, particle presets | Effective config *only when modifiers change* (dirty flag) |
| Enum IDs, spatial grid cell size | Weapon `element`, `elementInterval` counter |

### Tasks
- [-] **9.1 No allocations in the hot path:** pool hit queue entries, jump-tree buffers, Wind areas, VFX instances. *(DOC-003: superseded — Python, not C: only the VFX are pooled (`visual/elements/transient.py`))*
- [x] **9.2 Spatial grid:** uniform grid (or the existing one) for closest-Y queries, radius queries, and area contacts. Closest-Y uses a grid query within `maxRange` plus a partial sort. No O(n²) scans.
- [-] **9.3 Elemental hit queue:** all elemental hits become queue entries processed in a single pass per frame. Each hit is resolved fully (including its reaction) before the next hit on the same enemy. Enforce `maxReactionsPerFrame`, and defer overflow to the next frame rather than dropping it. Process in a stable order (determinism). *(DOC-003: superseded — hits resolve inline, only reactions are deferred (`combat/elements/resolve.py`))*
- [-] **9.4 Visited marking without allocation:** each chain gets an incrementing ID. Enemies store `lastChainId`, so "already hit" is one integer comparison. *(DOC-003: superseded — a chain marks visited enemies in its own `id()` set (`spread.py`))*
- [x] **9.5 Tick only what ticks:** only enemies with ticking statuses are iterated.
- [x] **9.6 Timestamp-based timers** for auras, statuses, locks, and areas.
- [x] **9.7 Low-rate area checks** (e.g., 10 Hz) for Wind areas. Cap simultaneous areas (`maxActiveWindAreas`).
- [ ] **9.8 Profiling counters:** active auras, reactions/frame, jump nodes/frame, active Wind areas, particle count. Visible in dev mode. *(DOC-003: auras, reactions/frame, held reactions, particles and element fx are in the F1 metrics (`devtools/dev_flags.py`); jump nodes/frame and active Wind areas are still missing)*
- [x] **9.9 Hit-rate control.** Survivor-style weapons produce many hits per second (multiple projectiles, piercing, persistent damage areas). Without a limit, every tick of a damage area would reapply or react, cascade Thunder jumps constantly, and spawn a Wind area on every contact.
  - Handled by two confirmed mechanisms, both cheap: the weapon `elementInterval` (§6.3), which is one counter per weapon decided at attack spawn, and the global reaction aura cooldown (§3), which is one timestamp comparison per enemy. No per-enemy-per-weapon cooldown tables are needed.
  - Aura *refreshes* on the same element are not rate-limited, but they are just a timestamp write.

### Considerations
- The cost hot spots are jump trees (branching), Thunder-triggered Overload bursts, nearest-N queries (ThunderWind), area queries, and particles. Per-source `maxTargets` and `maxRange` bound them. Tune those first in the stress test.

---

## 10. Developer Mode

- [x] **10.1 Aura inspector:** toggle a label/icon above every enemy showing aura element, remaining time, lock state, and active statuses with stacks.
- [x] **10.2 Weapon element editor:** set, change, or remove the element of any equipped weapon, and edit its `elementInterval`.
- [ ] **10.3 Extra tools [PROPOSAL]:** *(DOC-003: force aura built (dev menu); hot-reload, reaction log and spawn-building-with-element not built)*
  - Force-apply an aura to the enemy under the cursor.
  - Spawn a buff building with a chosen element, or a Monastery.
  - Reaction log (pair, target, damage, targets reached vs caps).
  - Hot-reload element/reaction JSON.
  - Show Wind area radius and jump range as debug circles.
  - Performance overlay (§9.8).
  - Live view of the damage/application summaries (§3.6) and the resolved elemental profile of the enemy under the cursor (§3.5).

---

## 11. Testing & Acceptance

- [x] **Aura/status:** every element leaves an aura; bound status duration equals aura duration; consuming an aura ends its bound status; same-element hit refreshes both; Ice freezes at exactly X stacks.
- [x] **Reactions:** each pair yields the same reaction type in both orders; per-trigger overrides apply only in their direction; the incoming element (direct hit or Thunder jump) deals no initial effect and leaves no aura on reaction; every reaction locks the aura slot for `max(global cooldown, lockDuration)`; locked enemies still take damage and effects, and Fire/Ice apply standalone Burn/Slow; Overload and Frostburn leave no aura on anything they reach, while the Wind three and Superconduct prime what they reach with their own element and a spread aura meeting a different one starts another reaction (§5.3, §5.4); a reaction's figure is read from both source hits and is identical whichever of the two landed second; the same figure reaches the carrier and every body the reaction touches, floored on the carrier alone; a body that has just reacted refuses a spread aura; a cascade larger than the frame budget defers rather than drops; Superconduct jumps always exceed Thunder jumps; ThunderWind hits exactly the N closest enemies in range.
- [x] **Thunder:** `jumps = 0` hits only the target; `jumps = 1, Y = 3` hits at most 4 enemies; no-aura targets receive a Thunder aura; different-aura targets take no jump damage, react, and stop spreading; no enemy hit twice; `maxTargets` and `maxRange` are respected.
- [x] **Wind:** area lasts `area.duration`; each enemy is hit at most once per area; knockback is radial; reaction payloads apply correctly.
- [x] **Weapons:** `elementInterval` 0/1/N produces the expected inflict/skip pattern, and all hits of one attack share its flag; a weapon can never hold more than one element; a new element replaces the old one. *(DOC-003: done for the shipped `element_application` shape (`tests/combat/test_weapon_infusion.py`))*
- [x] **Run scope:** a Monastery offers all elements and is spent after one use; unlocked elements appear in the run summary; infusions and unlocked elements are cleared at run end; the unlocked set never holds duplicates; the Monastery assigns exactly one chosen element to exactly one weapon; element buffs apply to that element on every weapon.
- [x] **Profiles:** enemies without overrides use the default profile; a boss override (e.g., higher freeze threshold) applies only to that enemy type; a disabled effect never applies while its aura and reactions still work; an enemy with `aura.enabled = false` takes element damage and statuses but never holds an aura or reacts.
- [x] **Tracking:** every elemental damage event is recorded under its effect and source weapon; summed per-effect totals match total elemental damage dealt; application and reaction counts match dev-mode logs; enemies dying mid-chain leave no dangling references.
- [x] **JSON:** validation rejects bad values and unknown keys.
- [x] **Stress test:** 100 enemies with auras, repeated Thunder jumps, Overload, and multiple Wind areas. Record frame time and particle counts per milestone. *(DOC-003: done before the R38 cascade (`spawn_stress --elements`, elemental journal M9); the cascade case is CMB-008)*
- [x] **Visual review:** screenshot grid of every aura, status, lock, and reaction on a crowded screen.

---

## 12. Suggested Milestones

0. **Discovery:** audit the codebase (weapons, hit pipeline, enemies, particles, run lifecycle, JSON loading, dev mode). Report findings and conflicts with this doc.
1. **Core:** ElementId, interface, registry, JSON baking and validation, modifier layer.
2. **Aura & status:** AuraState, StatusList, locks, hit queue with single-element resolution, tick pass, enemy elemental profiles, damage/application tracking, dev-mode inspector.
3. **Base elements:** Fire, Ice, Thunder (jump model), Wind (area component), spatial grid, caps. Placeholder visuals.
4. **Reactions:** lookup table, Frostburn (with lock), Overload, Superconduct.
5. **Wind reactions:** FireWind, IceWind, ThunderWind as Wind-area payloads.
6. **Weapon element:** single-element field, `elementInterval`, dev-mode weapon editor.
7. **Acquisition:** buff building rolls, Monastery element picker, run-scoped unlocked-element set.
8. **Visual system:** shared component, aura/status layers, reaction blends, particle LOD.
9. **Performance pass and stress test**, then balance tuning via JSON.

---

## 13. Open Questions / Decisions Log

### Resolved
| # | Topic | Decision |
|---|---|---|
| R1 | Do all elements leave an aura? | Yes, on top of the initial effect. |
| R2 | Cascade control | ~~Reaction secondary hits apply statuses/damage only, never auras.~~ **Superseded by R38 (v9).** Per-source `maxRange` and `maxTargets` still hold. |
| R3 | Tornado | Brief (~1 s) circular Wind area around the hit enemy. Wind reactions change its damage, knockback, and extra effect. |
| R4 | Aura vs status | Separate values. Base statuses share the aura's duration. Frostburn is a status that locks the aura slot (configurable per reaction). |
| R5 | Elements per weapon | Exactly one. Dual elements and element modes are removed (supersedes the earlier two-slot design). |
| R7 | Thunder spread | Branching jumps: closest Y per jump, counter decreases per level, 0 = no spread. |
| R8 | Wind reaction names | FireWind, IceWind, ThunderWind. |
| R9 | Infusion scope | Run-scoped. Assigned to the weapon equipped at acquisition. |
| R10 | Incoming element on a direct-hit reaction | No initial effect, no aura. It only consumes the aura and starts the reaction. |
| R11 | Directional values | Same reaction type per pair. Values can differ by triggering element (per-trigger JSON overrides). |
| R12 | Hit on locked aura slot | Damage and effects apply; Fire/Ice apply standalone Burn/Slow. No aura, no reaction. |
| R13 | Thunder jump targets | Receive a Thunder aura. Wide aura spread is intended. |
| R16 | Weapon set | Fixed, survivor-style, never swapped. Weapons are upgraded. Infusion stays on the weapon. |
| R17 | Jump into a different aura | No jump damage. Aura consumed, reaction triggers (it deals its own damage). That node stops spreading. |
| R18 | Overload | Target damage + shockwave and knockback to others, no aura. Pinball behavior intended. **v9:** one damage figure covers the target and the shockwave; `shockwaveDamage` is gone. |
| R19 | Superconduct | Target damage. ~~Spread applies Slow only (no damage, no aura).~~ **v9:** the spread carries the same damage, `iceStacks` Ice stacks and the Ice aura. More jumps than base Thunder. |
| R20 | ThunderWind | Thunder strike through the reacting enemy to the N closest enemies (high N). The strike leaves no aura; **v9:** the tornado primes its contacts with Thunder. Replaces the earlier jump-tree version. |
| R21 | Element application rate | Weapon `elementInterval` (0 = every attack). |
| R22 | Post-reaction cooldown | Global aura-slot lock per enemy after any reaction. Effects still apply. |
| R23 | Attack definition | All weapons are cooldown-based. One firing = one attack. |
| R24 | Frozen vs knockback | Frozen enemies still get knocked back. |
| R26 | Fire hit damage | Direct hit damage, then the Fire aura and its Burn. |
| R27 | Modifier scope | Global per element (all weapons). |
| R28 | Monastery | No rolled element. The player picks an element and one weapon. |
| R29 | Pool | Replaced by a run-scoped set of unlocked elements (no duplicates). |
| R30 | Frozen contact chaining | No knockback transfer, so no chains. |
| R31 | Bosses/special enemies | Per-enemy-type elemental profiles: value overrides or effect toggles. Every enemy can be affected by elements. |
| R32 | Damage credit | Credited to the effect/reaction. The source weapon is kept. Summaries of damage and element applications are classified by weapon. |
| R33 | Death mid-resolution | Skipped safely; the chain continues. |
| R34 | Aura toggle | Enemy profiles can disable auras. The enemy is immune to reactions but still takes element damage and statuses. |
| R35 | Source weapon rules | As defined in §3.6. |
| R36 | Monastery | Offers every element. One use. |
| R37 | Unlocked elements | Tracked for the run summary. |
| R25 | Frozen contact damage | Optional toggle: frozen enemies knocked back by another source deal contact damage, using the existing damage calculation. |
| R38 | Reaction spread and cascade depth *(v9, CMB-006)* | The Wind three prime their tornado's contacts with their own element and Superconduct primes its tree with Ice; Overload and Frostburn spread nothing. A spread aura meeting a different one starts another reaction, with **no depth cap** — bounded by the per-enemy aura lock, the per-frame budget, and the decaying value a spread aura carries. Supersedes R2. |
| R39 | Reaction damage sources *(v9, CMB-006)* | `high × max(A, B) + low × min(A, B)`, where A placed the aura and B triggered the reaction. Symmetric. The aura remembers its hit; a refresh keeps the larger. Closes open question 11. |
| R40 | Who a reaction pays *(v9, CMB-006)* | The same figure reaches the enemy it fired on and every enemy it reaches. The Wind three used to pay their carrier nothing at all. |
| R41 | Reaction damage floor *(v9, CMB-006)* | Raised to `globalReactionMinDamage` on the carrier only; spread targets take the raw figure. |
| R43 | Freeze vs a consumed Ice aura *(closes open 8)* | Freeze keeps its own duration. It is its own status and is never bound to the aura, so only the Slow ends with it. |
| R44 | Ice aura after a freeze *(closes open 9)* | It stays until it expires or reacts. Freezing touches the stacks and the statuses, never the slot. |
| R45 | Wind area late entrants *(closes open 10)* | Hit, via the 10 Hz re-query; the area follows its anchor and contacts each body once per instance. |
| R46 | Collision damage between non-frozen bodies *(closes open 4)* | None. Only frozen contact damage exists (R25), with the knockback speed clamp. |
| R47 | Cascade strength in play *(v9, closes open 14)* | The owner played the uncapped cascade on 2026-09-22 and found it good. No depth cap, no coefficient change. The damage values ship as built. |
| R48 | Infusion across weapon upgrades *(closes open 5)* | Kept, by construction: the element lives on the weapon and weapons are upgraded, never replaced (R16). Level-ups changing the application cadence is **possible but unused and not required**; kept as a future data option. |
| R49 | Directional variants in practice *(closes open 6)* | **None today, and none needed.** The `triggered_by` machinery stays available — making order matter later is a data edit with no code change. |
| R50 | `globalReactionAuraCooldown` value *(closes open 13)* | **1.0 s**, as shipped. Edit it at `data/weapons/elements.json` → `global.reaction_aura_cooldown`; it is one of the two brakes on the R38 cascade. |
| R42 | Spread ordering *(v9, CMB-006)* | Inside one contact the aura is spread before the reaction's own payload, so the payload owns its status row's credit and binding rather than the spread element's `onApplied`. |

### Still open

*Settled since v8: 1 (locked node keeps spreading, §4.3), 2 and 3 (Superconduct and ThunderWind reach, §5.5), 7 (IceWind stacks freeze, §5.5), 11 (damage formula, R39), and — reconciled against the shipped code on 2026-09-22 — 4, 8, 9 and 10, which the implementation had answered without the answer ever being written down. 5, 6, 13 and 14 were closed by the owner on 2026-09-22. The numbering of the rest is unchanged so older references still resolve.*

| # | Question | Proposal |
|---|---|---|
| 12 | Existing particle system limits | **Open, to measure and test** (owner, 2026-09-22). `MAX_PARTICLES` 1200 and `MAX_DAMAGE_NUMBERS` 200 in `game/config.py`. The M9 pass measured the element system at ~30x a real build's load without trouble, but that was before the R38 cascade, which is load the original audit never saw: more reactions per frame, each with its own flash, label and stream of numbers. Measure a dense cascade before closing this. |


