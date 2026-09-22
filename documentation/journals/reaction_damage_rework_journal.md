# Reaction damage rework — execution journal

## Requirement (owner, 2026-09-22)

- **Objective:** Rework how elemental reactions deal damage, so a reaction is
  paid from the two damage sources that produced it rather than from the single
  hit that triggered it.
- **Details:** Wind reactions pay 30 % of both values, to the enemy the
  reaction fired on and to everything the tornado hits, and spread their own
  element's aura to those bodies. Overload pays 50 % of the higher and 30 % of
  the lower; Superconduct 40 % of the higher and 30 % of the lower, spreading
  three Ice stacks and the Ice aura to the closest enemies; Frostburn 70 % of
  the lower and 20 % of the higher, plus 50 % of the higher split into three
  ticks one second apart.
- **Constraint:** No reaction deals less than 3 points of damage. Confirm the
  reading before building.

### Why this was asked for

A review of the shipped system (this session, before the request) measured six
independent ways a reaction lands for nothing. The three that this rework
addresses directly:

* **The Wind reactions deal exactly 0 to the enemy they fire on.** `WindArea`
  seeds its `hit_ids` with its own anchor (`combat/elements/area.py:50`) and
  ThunderWind's strike excludes `id(target)`, so the body the reaction label
  pops over takes nothing. Because resolver step 5 also suppresses the incoming
  element's own initial effect, triggering a Wind reaction on an isolated enemy
  was a net damage **loss**.
* **Everything scaled off the triggering hit alone.** `DamageSpec.resolve` reads
  `ctx.hit_damage`, which is the weapon damage of the hit that landed the
  *second* element. The weapon that placed the aura contributed nothing, so a
  Hammer-primed Overload triggered by an Ember Ring orbiter paid Ember Ring
  money (0.30 × 6 = 1.8).
* **Small numbers rounded to a visible 0.** `int(round(amount))` in
  `ui/damage_numbers.py:150` printed `0` for any piece under 0.5, which at the
  6–7 damage weapons covered burn ticks, chain hits, wind areas and ThunderWind
  strikes.

The new model fixes all three at once: both interacting hits contribute, the
carrier is always paid, and a floor stops the result reading as zero.

---

## Confirmed decisions (owner, 2026-09-22)

Two rounds of questions. `A` is the hit that **placed the aura**, `B` is the hit
that **triggered the reaction**; both are weapon damage before mitigation.

| # | Question | Decision |
|---|---|---|
| 1 | A spread aura landing on a different aura | **Chains** — it fires a further reaction |
| 2 | Frostburn's third term | `0.50 × max(A,B)`, split into 3 ticks (configurable), one per second |
| 3 | Overload's shockwave / Superconduct's spread | Every enemy reached takes the **same** number as the carrier |
| 4 | The 3-point floor | **Carrier only**; bystanders take the raw figure |
| 5 | The Wind reactions' existing payloads | **Kept**, the aura spread is added on top |
| 6 | What damage value a spread aura carries | The **reaction damage that enemy just took** |
| 7 | Cascade depth cap | **None** — bounded only by the existing per-frame budget |
| 8 | Superconduct's spread shape | **Keep the existing jump tree** |

### The resulting formulas

| reaction | carrier and every enemy reached |
|---|---|
| FireWind / IceWind / ThunderWind | `0.30 × (A + B)` |
| Overload | `0.50 × max(A,B) + 0.30 × min(A,B)` |
| Superconduct | `0.40 × max(A,B) + 0.30 × min(A,B)` |
| Frostburn | `0.70 × min(A,B) + 0.20 × max(A,B)` immediate, **plus** `0.50 × max(A,B)` over 3 ticks at 1 s |

Floored at **3** on the carrier only. Every coefficient, the tick count and the
tick interval are data in `data/weapons/reactions.json`, per the project's
`data-driven-no-code-defaults` rule.

### What each reaction spreads

* **FireWind** — its existing burn payload, **plus** the Fire aura.
* **IceWind** — its existing 2 ice stacks, **plus** the Ice aura.
* **ThunderWind** — its existing flat strike, **plus** the Thunder aura.
* **Superconduct** — 3 ice stacks and the Ice aura to every enemy the jump tree
  reaches, which now also take the reaction's damage (they previously took only
  a slow).
* **Overload** and **Frostburn** spread no aura.

---

## Consequences worth stating before building

1. **The "secondary hits never apply auras" invariant is retired.** It is
   currently enforced by construction (`combat/elements/reactions/base.py`
   docstring, design §5.3) and is what guaranteed reaction depth exactly 1.
   Decision 1 replaces it deliberately. The brakes that remain are the existing
   ones: the per-enemy aura lock (`reaction_aura_cooldown`, 1.0 s), the
   per-frame reaction budget (`max_reactions_per_frame`, 8) and its deferral
   queue.
2. **Cascades decay in value but not in reach.** Decision 6 means each
   generation's auras carry the (smaller) damage the previous generation dealt,
   so the numbers shrink; decision 7 means nothing stops the *spread* except
   running out of differently-primed enemies. The carrier floor of 3 means a
   cascade's damage never reaches zero. This combination was put to the owner
   with the blow-up risk stated and chosen knowingly; if it proves too wild in
   play the cheapest lever is a depth cap, not a coefficient change.
3. **`ElementalState` has to remember the aura's damage.** It stores
   `source_weapon` today (`combat/elements/aura.py:39`) but not the hit's value,
   so a `source_damage` field is required before `A` exists at all.
4. **`reactions.json`'s damage keys change shape.** The current `damage`,
   `shockwave_damage`, `burn_tick` and `strike_damage` fracs are all fractions
   of one hit. They are replaced by the coefficient pairs above; radii,
   knockback, durations, slow percents and target caps are untouched.
5. **The `triggered_by` directional-override mechanism still applies** — the
   formulas are symmetric in A and B by construction, but a reaction may still
   tune per incoming element through the existing block.

---

## How it was built

### The two-source value in the schema language

A reaction's damage is one new field kind, `pair()`, beside the existing
`dmg()` (`combat/elements/schema.py`). It validates `{"high": x, "low": y}`,
bakes to a `PairSpec` and resolves as `high × max(A,B) + low × min(A,B)`.

Deliberately **symmetric**: which of the two hits placed the aura and which
triggered the reaction is bookkeeping, and a value that read them in a fixed
order would pay differently depending on which weapon happened to fire second.
`test_the_order_of_the_two_hits_does_not_change_the_figure` pins it.

One shape covers all six because a reaction that pays the same share of both —
the Wind three, at 30 % of each — simply sets the two coefficients equal, and
`high × max + low × min` collapses to `0.30 × (A + B)`. No second field kind
and no branch.

Its leaf paths are `damage.high` and `damage.low`, so the existing modifier
layer and the per-enemy profile overrides address either coefficient without
knowing the kind exists. `deep_merge` had to learn that a full pair replaces
wholesale rather than merging, or a `triggered_by` override naming one
coefficient would have silently carried the base's other one.

### Where `A` comes from

`ElementalState` gained `source_damage` beside the `source_weapon` it already
tracked. Three decisions fell out of it:

* a **refresh takes the larger**, not the latest. A refresh is the same aura
  being kept alive, and letting a cheap fast weapon overwrite a heavy one would
  have let it quietly defuse a reaction the player set up — which is the exact
  failure the rework was for.
* `consume_aura` clears it with the rest of the slot.
* an aura carrying **no** damage falls back to the triggering hit
  (`HitContext.sources`), so a reaction is never paid as if one of its halves
  were free.

`ElementalResolver.apply` reads the slot *before* anything can consume it and
hands the value to the context.

### The floor

`global.reaction_min_damage` in `elements.json`, one number for all six rather
than six copies, applied through `HitContext.floored`. Each reaction calls it
exactly once, on its own carrier — which is what makes "carrier only"
enforceable by reading the code rather than by a convention.

### The cascade

`ElementalResolver.spread_aura` is the new seam. It is deliberately the
ordinary `apply`, so a spread aura landing on a different one runs the full
reaction path. It exists as a named method rather than a bare call because it
is the one place a depth cap would go if play asks for one.

The three Wind reactions collapsed into one shared helper,
`reactions/base.py::wind_reaction`: one figure paid to the carrier, the same
figure carried by the tornado, and each contact primed with the reaction's
element on top of that reaction's own payload. `WindArea` had to start passing
the **live** clock and its own damage figure to the payload — it outlives the
context that built it by up to its whole duration, so the reaction's stale
`now` would have set auras that expired before they were written.

**Ordering inside a contact: aura first, payload second.** Both orders survive
a cascade, because the payloads are written standalone and a reaction the aura
sets off can only end *bound* statuses. But priming a body runs the element's
own `on_applied`, which for Fire is a burn and for Ice a chill — on the very
status rows FireWind and IceWind use — and whoever applies last owns that
row's credit, tick interval and binding. Spreading first leaves FireWind's burn
credited to FireWind and standalone, which is what the run summary needs to
tell it from Fire's own. Getting this backwards silently re-credited
FireWind's damage-over-time to plain `burn`; the test that caught it is
`test_its_ticks_are_credited_to_firewind_not_to_the_spread_auras_burn`.

Superconduct counts rather than adds blind: laying the Ice aura is worth one
stack by itself, so it tops up to `ice_stacks` instead of adding three more and
landing four. Its `slow_percent` was deleted — Ice sizes the slow from the
stack count now, and a second figure there would have been one nothing read.

### Consequences found while building

* **IceWind lands `stacks_per_contact` + 1.** The payload's two stacks plus the
  one the spread Ice aura's own application is worth. The owner kept both
  halves, so both are paid; documented in the module and asserted as such.
* **FireWind's burn and IceWind's slow now outlast their own configured
  durations**, because the spread aura carries a longer-lived status on the
  same row and `StatusState.apply` keeps the longer of the two. Correct: the
  body genuinely holds that aura now.
* **The Wind reactions' kept payloads resolve against `max(A,B)`** rather than
  the triggering hit alone (`HitContext.reference`). The owner kept the payload
  *mechanics*; resolving them against a single hit would have left
  ThunderWind's strike at 0.06 × a 6-damage orbiter, which is one of the
  zero-damage cases this rework exists to remove. Their tuning numbers are
  unchanged.

## Measured after the change

`tools/benchmarks/element_bench.py --pairs --seconds 20 --crowd 10`, seed 35 —
against the same run before the rework:

| pair | element dps before | after | reactions before → after |
|---|---|---|---|
| fire + ice | 7.0 | 10.5 | 6 → 6 |
| fire + thunder | 2.7 | 15.6 | 2 → 2 |
| fire + wind | 10.1 | 48.9 | 10 → 22 |
| ice + thunder | 3.5 | 74.1 | 6 → 9 |
| ice + wind | 7.9 | 41.1 | 10 → 22 |
| thunder + wind | 14.2 | 57.0 | 18 → 22 |

The reaction counts roughly doubling on the Wind pairs is the cascade arriving.
The damage is up far more than the coefficients alone account for, and the
reason is compounding rather than any one number: every enemy reached now takes
the **full** figure instead of a weaker secondary value, the reactions reach
more bodies than they damaged before (Superconduct's tree damaged nobody at
all), and each spread aura adds its own element's hit and status on top.
Superconduct is the outlier at roughly 21× — 12 spread targets each paid in
full — and fire + ice the mildest at 1.5×, because Frostburn still reaches
only its own carrier.

Against the project's yardstick (one weapon blessing level ≈ +15 % output) an
infusion pair is now worth several levels. **This is a tuning question, not a
correctness one** — the formulas are the owner's and the numbers are all data.
The cheapest levers, in order of bluntness: the per-reaction coefficients in
`reactions.json`; a fraction applied to spread targets; a cascade depth cap
behind `spread_aura`.

## Tests

* `tests/combat/test_reaction_cascade.py` — **new**. The three rules the rework
  added across all six reactions: the aura remembering its hit, the
  carrier-only floor, and the cascade including both of its brakes.
* `tests/combat/test_reactions.py` — the depth-1 rule it opened with is
  retired; replaced by "Overload and Frostburn stay terminal", "every reaction
  reads both hits", symmetry, and the floor. Per-reaction assertions moved to
  the pair figures.
* `tests/combat/test_wind_reactions.py` — gained "the enemy it fired on is paid
  too" and "the tornado primes everything it touches"; the payload assertions
  follow the aura-spread interactions above.
* `tests/combat/test_elements_config.py` — a `PairFieldTests` block for the new
  field kind, and the `triggered_by` override tests moved to the pair shape.

## Progress

* 2026-09-22 — Requirement captured, two rounds of clarification answered, spec
  confirmed by the owner.
* 2026-09-22 — Built. Schema field kind, aura source damage, the floor, the
  cascade seam and all six reactions reworked; `FUNCTIONAL_README.md` updated.
  Balance consequences measured and reported above, left untuned pending the
  owner's call.
