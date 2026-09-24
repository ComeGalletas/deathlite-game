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

*(DOC-003: #12 is tracked as **CMB-008** — closed 2026-09-23 by measurement, design §13 R51.)*

#12 is worth keeping open for a reason the original audit could not have had:
`MAX_PARTICLES` is 1200 and `MAX_DAMAGE_NUMBERS` 200, and the M9 pass measured
the system at roughly thirty times a real build's load — but that was before
the R38 cascade. A cascade puts more reactions in a frame than M9 ever saw,
each with its own flash, label and stream of numbers.

- [x] CMB-007.3 — Record the owner's answers; one question left

---

## CMB-008 — Requirement (owner, 2026-09-22)

- **Objective:** Measure whether the particle and damage-number pools hold
  under a dense reaction cascade, and close design §13 question 12 with the
  numbers.
- **Details:** `MAX_PARTICLES` 1200 and `MAX_DAMAGE_NUMBERS` 200
  (`game/config.py`). The M9 stress pass predates the R38 cascade, which puts
  more reactions per frame on screen, each with its own flash, label and
  stream of numbers.
- **Constraint:** Measure first. A cap or budget changes only if the
  measurement says so, and that change is the owner's call.

## CMB-008 — Confirmed reading

- **Reactions are already rationed.** `global.max_reactions_per_frame` is 8
  (`data/weapons/elements.json`); the rest wait a frame
  (`combat/elements/resolve.py`, `stats.deferred_now` / `deferred_total`,
  `pending`). A cascade shows up as a backlog, not as one unbounded frame.
- **Particles degrade gracefully.** Elements draw from their own per-frame
  and per-element allowance (`visual/elements/budget.py`); when it runs out
  auras keep their rings and stop shedding, and `refused` is counted.
- ~~**Damage numbers do not.** … Nothing rations elemental numbers against
  weapon numbers. This is the likely weak point.~~ **Corrected while
  building CMB-008.1 (2026-09-23):** they are rationed. `ui/damage_numbers.py`
  refuses a `low_priority` number once the pool is 75 % full
  (`_LOW_PRIORITY_FULL`), and `RunWorld.deal` sends every elemental number
  as low priority, so the top quarter stays for weapon numbers. What the
  reservation does *not* cover is the reaction **label**
  (`add_label`, not low priority), which a cascade produces one per
  reacting body — that became the thing to watch.
- `tools/benchmarks/spawn_stress.py --elements` (with `--element-rate`)
  already primes every enemy and reports auras, reactions, deferred, held,
  the particle budget and the damage-number peak against its cap. It does
  not stage a cascade on purpose.
- **CMB-008.D1 — What "holds" means.** Frame time within budget (p99 under
  16.7 ms with `--render`); the deferred backlog drains rather than grows;
  no weapon damage number dropped. All three reported, each against the M9
  figures.
  *Revised on the measurement (2026-09-23):* headless, `--render` draws
  through SDL's dummy driver in software ("no fast renderer available"),
  and draw alone is 18 ms at p50 with **no elements at all** — so
  "update + draw under 16.7 ms" cannot be judged here. The frame criterion
  becomes the *update* time and the draw time **against a no-element
  control of the same crowd**, which is what M9 compared too.

## CMB-008 — Plan

Add a cascade scenario to the stress tool, measure it and a real
cascade-heavy build on the DPS bench, write the table here, and only then
decide on a fix. The likely fix, if one is needed, is an elemental
allowance for damage numbers modelled on the particle budget, with its
limits in data. CMB-009.2's counters (Thunder jump nodes, active Wind areas)
make the report fuller but are not a prerequisite.

## CMB-008 — Tasks

- [x] CMB-008.1 — `spawn_stress --cascade`: a dense crowd primed with two elements so reactions chain; report frame p50/p99, reactions run/deferred per frame and the backlog trend, particles refused, damage-number peak and drops
- ~~CMB-008.2 — Measure a cascade-heavy build on the DPS bench for realistic load~~ dropped: the bench measures one dummy with nothing beside it, so no aura can spread and nothing can cascade. The realistic-cadence case is scenario C below — the three infused weapons at their own rate, no pumped hits.
- [x] CMB-008.3 — Record the table against M9 (elemental journal, M9 *What it costs*)
- ~~CMB-008.4 — Only if D1 fails: an elemental damage-number allowance, limits in data, with a test that a weapon's number survives a full pool~~ dropped: D1 holds (see the table), and the allowance it describes already exists (`_LOW_PRIORITY_FULL`, the corrected reading above).
- [x] CMB-008.5 — Close design §13 question 12 with the result; index to done

## CMB-008 — Results

**Branch:** `claude/cmb-008-cascade-limits`, cut from
`claude/cmb-009-elemental-extras` so the measurement has CMB-009's
counters and reaction log (owner, 2026-09-23: continue with CMB-008).

### CMB-008.1 — The staged cascade

`tools/benchmarks/spawn_stress.py` gained three things, none of which
change the game:

- `--cascade`: after the warm-up, the live crowd is packed into a 220 px
  disc round the hero and primed with the four elements in turn, so
  neighbours hold different auras and any aura a reaction spreads sets off
  the next reaction. Staged *after* the 60 warm-up frames: the first try
  staged it before, the burst spent itself in the warm-up (74 reactions,
  the number pool at 200/200) and the measured window saw only the
  aftermath — 9 reactions, none cascading.
- `Instruments`: per-frame reactions and backlog, the particles the element
  budget refused, the damage-number pool's size; a large `ReactionLog` on
  the resolver for the depth histogram; and the pool's `add` /
  `add_label` wrapped to count what each priority asked for and what was
  refused.
- `--pack`: the same packed crowd with no elements at all — the control.

### CMB-008.3 — The measurement (2026-09-23)

Seed 35, LOD 2, 100 live asked, 400 dormant, 600 frames after a 60-frame
warm-up, `--render` on every run; `python -m tools.benchmarks.spawn_stress`
with the flags shown. Times in ms. The master keeps spawning while a run
goes, so the live count at the end differs by scenario (in brackets).

| scenario | update p50 / p99 / max | draw p50 (in view) | reactions/frame p99 · at cap 8 | backlog max · last ¼ | depth | particles refused | numbers peak · dropped weapon / label / element |
|---|---|---|---|---|---|---|---|
| A `--render`, no elements (133) | 5.43 / 7.58 / 11.45 | 18.34 (32) | — | — | — | — | — |
| B `--elements` — M9's primed crowd (125) | 5.03 / 7.45 / 11.71 | 17.83 (29) | — | — | — | 0 | 163 · — |
| **F `--pack`, no elements — the control** (168) | **8.14 / 14.19 / 20.84** | 18.17 (117) | — | — | — | — | — |
| **C `--cascade`, weapons only** (150) | **7.64 / 12.28 / 25.62** | 20.30 (107) | 3 · 4 / 600 | 16 · 0.0 | d1 25, d2 18, d3 9 | 0 | 186 · 0/75, 0/98, 186/825 |
| D `--cascade --element-rate 20` (96) | 6.76 / 10.96 / 14.44 | 23.43 (93) | 8 · 10 / 600 | 6 · 0.0 | up to d5 | 0 | 191 · 0/62, 0/719, 19,771/20,583 |
| E `--cascade --element-rate 60` (96) | 7.06 / 10.39 / 12.69 | 22.79 (91) | 8 · 34 / 600 | 33 · 0.0 | up to d3 | 0 | 196 · 0/62, 0/751, 49,334/50,115 |

What it says, against D1:

- **Frame time — the cascade costs nothing measurable.** The packed crowd
  with *no elements* (F) costs more update time than the staged cascade
  (C): what rose against A is crowding — ~110 bodies inside a 220 px disc,
  colliding and pathing — not reactions. C's one 25.6 ms frame is the
  opening burst (a crowd of primed auras all reacting at once), which the
  budget spread over the next frames. Draw moves with bodies in view, not
  with elements (C 20.3 at 107 in view against F 18.2 at 117). Against M9,
  whose runs had update p50 5.8–6.4 ms, A and B sit in the same band.
- **The backlog drains.** Its last quarter averages 0.0 in every run; the
  worst is 33 held at 60 pumped hits a frame, and the cap of 8 was reached
  on at most 34 frames of 600.
- **No weapon number and no reaction label was dropped** in any run. The
  pool peaked at 196/200; everything refused was a low-priority element
  number yielding the reserved quarter, which is the design working. At
  realistic cadence (C) that is 186 of 825.
- **Particles never pressed:** the element budget used at most 7 of its 90
  a frame and refused nothing; the shared pool stayed under 300 of 1200.
- **Cascades are shallow.** The deepest chain was five reactions, at 20
  pumped hits a frame; at realistic cadence, three. The aura lock and the
  per-frame budget are enough of a brake — no depth cap is called for
  (R47 stands).

### CMB-008.5 — Closed

Design §13 question 12 is closed as **R51**: the limits hold and
`MAX_PARTICLES` 1200 / `MAX_DAMAGE_NUMBERS` 200 stay. "Still open" in §13
now reads *None*. No game code changed in CMB-008 — only the stress
harness — so no test tier covers it; the harness itself was exercised by
the seven runs above.
