# Reaction damage rework — execution journal

**Legacy ID:** CMB-006 · **Systems:** CMB · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

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
* 2026-09-22 — Committed as `8792594` (unprefixed: the DOC-001 ID standard
  landed on this branch after it). The two enemy tuning tweaks that were in
  the tree alongside it went out separately as ENT-012.

---

## CMB-007 — Requirement (owner, 2026-09-22)

- **Objective:** Update `documentation/plans/ELEMENTAL_SYSTEM_DESIGN.md` so it
  describes the behaviour CMB-006 shipped.
- **Details:** The document is the live reference for this system (INDEX maps
  it to CMB-005 and CMB-006), and its §5.3 and §5.4 still asserted the two
  rules the rework retired.
- **Constraint:** None given.

## CMB-007 — Confirmed reading

The document was written as a *plan*, in revisions v2–v8, each recorded as a
"vN changes" line and a decisions log in §13. Six places contradicted the
shipped code:

| where | claimed | now |
|---|---|---|
| §5.1 | Superconduct's spread applies "Slow only (no damage, no aura)" | damage, Ice stacks and the Ice aura |
| §5.3 | secondary hits "never" apply auras | the Wind three and Superconduct prime what they reach |
| §5.4 | "reaction depth is therefore always 1" | uncapped, with three named brakes |
| §5.5 | `shockwaveDamage`, Superconduct `slowPercent`, `tickDamage` | one pair figure, `iceStacks`, `tick` + `ticks` |
| §5.6 | **[OPEN]** flat or weapon-scaled damage | resolved: two sources, `high × max + low × min` |
| §11 | acceptance: "secondary hits never apply auras; depth never exceeds 1" | the spread and cascade checks the suite actually makes |

**CMB-007.D1 — supersede in place, do not delete.** §5.3 and §5.4 keep the
old rule as a marked quotation above the new text. The document's own history
is load-bearing: §13's R2, §11's acceptance list and four "vN changes" lines
were all written against those sentences, and a reader arriving at R2 needs to
find the rule it refers to rather than a gap. The same reasoning kept the v4
history line intact even though it describes superseded behaviour.

**CMB-007.D2 — renumber nothing in §13.** Open questions 1, 2, 3, 7 and 11
are settled and were removed from "Still open", but the rest keep their
numbers and a note says which went and why. Renumbering would break every
existing reference to "open item 7", including ones in `combat/elements/`
docstrings.

## CMB-007 — Plan

Edit in place, no code. Add a v9 line to the header, rewrite §5.1's table,
§5.3, §5.4, §5.5 and §5.6, correct §11's acceptance sentence, mark R2/R18/R19/
R20 in §13 and add R38–R42 plus one new open question for the balance.

## CMB-007 — Tasks

- [x] CMB-007.1 — Rewrite the design document to the shipped behaviour

## CMB-007 — Results

One new open question recorded as §13 item 14: whether the uncapped cascade is
too strong in play, with the bench figures and the intended lever (a depth cap
behind the spread seam, not a coefficient change). The owner is testing the
damage values as shipped.

The document was untracked until this commit, so it enters history at v9.

## CMB-007.2 — The owner's verdict on the cascade (2026-09-22)

The owner played the uncapped cascade and found it good; the damage values
ship as built. §13's item 14 is closed as **R47** and no depth cap is added.
This settles the one balance consequence CMB-006 left open, so the bench
figures in "Measured after the change" are the intended numbers rather than a
deviation to watch.

Asked in the same breath what was still unanswered, which turned up four
questions the **implementation had already answered without anyone recording
it** — open 4, 8, 9 and 10. Two of them (8 and 9) are even cited by number in
`combat/elements/ice.py`'s docstring, so the code knew and the design document
did not. They are now R43–R46. The §13 numbering is still untouched.

- [x] CMB-007.2 — Reconcile §13 against the shipped code and record the
  cascade verdict

## CMB-007.3 — The owner's answers to the remaining questions (2026-09-22)

Four of the five outstanding §13 items are now closed, leaving one.

| # | answer | recorded as |
|---|---|---|
| 5 | Infusion survives upgrades by construction. Level-ups changing the application cadence is possible, unused and not required — kept as a future data option. | R48 |
| 6 | No reaction differs by trigger and none needs to; the `triggered_by` machinery stays so order *could* matter later as a data edit with no code change. | R49 |
| 13 | `reaction_aura_cooldown` stays at **1.0 s**, edited at `data/weapons/elements.json` → `global.reaction_aura_cooldown`. | R50 |
| 12 | **Stays open**, to measure and test. | — |

One correction to the reading behind #5: it is not only the summons that are
rate-limited. Three weapons use a time window — the Grave Totem and Spirit
Wolf at 1.5 s and the **Ember Ring at 1.0 s** — and the Daggers use attack
mode with `interval: 2`, so they apply on every third swing. The other five
are `interval: 0`, every attack. That does not change the answer, but the
Ember Ring being rate-limited matters: it is a re-hitting orbiter, which is
exactly the case the cadence exists for.

#12 is worth keeping open for a reason the original audit could not have had:
`MAX_PARTICLES` is 1200 and `MAX_DAMAGE_NUMBERS` 200, and the M9 pass measured
the system at roughly thirty times a real build's load — but that was before
the R38 cascade. A cascade puts more reactions in a frame than M9 ever saw,
each with its own flash, label and stream of numbers.

- [x] CMB-007.3 — Record the owner's answers; one question left
