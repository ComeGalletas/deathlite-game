# The aura shed moves out of the draw: journal

**ID:** RND-011 · **System:** rendering (elemental visuals) · **Type:** bug ·
**Status:** done · **Branch:** ComeGalletas/aura-shed-update-a10d79ed
(owner, 2026-09-30; found by the web draw's critic passes, RND-012.D7 in
`web_draw_journal.md` on `ComeGalletas/web-draw-cheap-5be9212c`)

---

## RND-011: Requirement (owner, 2026-09-30)

- **Objective:** Take the elemental aura's particle shed out of the run's
  draw and into its update, so drawing a frame changes nothing in the run.
- **Details:**
  - Today `game/states/playing/visual/elements/layers.py` `_shed` runs
    inside `_aura`, once per drawn body wearing an aura: it rolls
    `run.rng.random() > rate / 60.0` and may call `run.particles.burst`.
  - Three consequences, measured in RND-012's critic passes: the shed's
    density scales with the draw rate (about 3x denser in the browser,
    host-paced at the display's refresh, e.g. 175 Hz, than at the
    desktop's 62 fps cap); the run's random stream, which gameplay also
    rolls on, is consumed per drawn frame, so gameplay randomness depends
    on how many frames were drawn (SYS-008, `run_determinism_journal.md`);
    and, before RND-012's frozen backdrop, pausing piled aura particles up
    (3 to 142 in 120 paused frames).
  - Tests to pin: the draw leaves `run.rng` and `run.particles` untouched;
    the shed's particles per second are the same at dt 1/30, 1/62 and
    1/175 (statistical, fixed seed); the elemental budget still bounds it.
- **Constraint:** It changes elemental behaviour and the run's random
  sequence, so the owner decides the model before any code (asked
  2026-09-30, answers in RND-011.D1 to D4).

## RND-011: Decisions

- **RND-011.D1 — the shed rolls its own random stream** (owner,
  2026-09-30). One `random.Random(f"{seed}:aura_shed")` per run, on
  `ElementVisuals`, the same string-seed form `fish_huts`, `npcs` and the
  boss pick use. Gameplay's `run.rng` no longer depends on whether an aura
  is in view, and the shed is still the same for the same seed. Any run
  that had an aura in view while it was drawn plays a different random
  sequence from before, once.
- **RND-011.D2 — one chance of `rate * dt` per body per update step**
  (owner, 2026-09-30). No per-body state. The expected count is exact at
  any step length; the whole part of `rate * dt` sheds for certain and
  only the fraction is rolled, so the mean stays `rate * dt` even for a
  step long enough to owe more than one mote (none is today: `MAX_DT` is
  1/20 s and the fastest rate 7/s, so `rate * dt` is at most 0.35). The
  bodies are the ones the draw paints auras on: in view with the 140 px
  pad (`layers.in_band(run, None)`), in `_bodies` order.
- **RND-011.D3 — the budget is scaled to the step** (owner, 2026-09-30).
  `per_frame` 90 and `per_element` 40 in `element_visuals.json` keep their
  values and now read as "per 1/60 s of play": each update step is granted
  `per_frame * 60 * dt`, the fraction carried to the next step, so the cap
  protects the particle pool by the same amount per second at 62 fps and
  at 175 Hz. The keys keep their names (renaming is a data-contract change
  with nothing gained); the `_doc` says what they mean.
- **RND-011.D4 — branch off `main`** (owner, 2026-09-30). RND-012 is still
  in progress on another session's branch. Its
  `tests/flows/test_frozen_backdrop.py::AuraShedTests` documents the
  draw-time shed and its control (`the per-frame redraw piles particles
  up`) turns false with this change. Whichever of RND-012 and RND-011
  lands second updates it as written under *For RND-012* below.
- **RND-011.D5 — no shed under the end banner** (builder, within the
  banner's own rule; confirmed by the owner 2026-09-30).
  `run_end.ending_sequence` stands in for the update while the end banner
  waits, and its contract is "no clock, only what is
  already in flight plays out": it ages the particles but births none. The
  shed now lives in the update, so a primed body stops shedding for the
  banner's wait. Before, the draw kept shedding there at the draw rate.

## RND-011: What the code did, and what changes

Where the shed ran, and what reads it:

| piece | before | after |
|---|---|---|
| `layers._aura` | draws, then `_shed(run, body, profile, budget)` | draws only |
| `layers.draw_auras` | takes the budget, visits bodies in `_bodies` order because the shed rolls `run.rng` | no budget; the order is only the paint order |
| `elements.begin_frame` (draw) | refills the budget, zeroes the aura counter | zeroes the aura counter |
| `ParticleBudget` | `begin_frame()`: whole `per_frame` / `per_element` again | `begin_step(dt)`: `per_* * 60 * dt`, fraction carried |
| the roll | `run.rng.random() > rate / 60` once per draw | `visuals.rng`, chance `rate * dt` once per update step |
| where | inside the terraced world draw | `elements/shed.py` `update(run, dt)`, called from `PlayingState._phase_update` after the particles age |

The mote is born after `run.particles.update(dt)`, so it is drawn at the
body on the frame it is born, full size. Before, a mote shed during a draw
was first painted the next frame, one step old; its layer (`under=True`)
is unchanged.

Nothing else consumed the budget (`grep budget.take`), so scaling it
changes only the shed.

## RND-011: Plan

1. Journal and index (this file).
2. `elements/shed.py`: the update-time shed on the per-run RNG;
   `ParticleBudget.begin_step(dt)`; the draw stops shedding and stops
   refilling the budget; `PlayingState` calls the shed; `ElementVisuals`
   takes the run seed. Tests: the draw leaves `run.rng`, the shed RNG and
   `run.particles` untouched; the shed's mean per second matches `rate` at
   dt 1/30, 1/62 and 1/175; the dt-scaled budget grants `per_frame * 60`
   a second at each of those and still caps a crowd; `run.rng` is
   untouched by the update-time shed. The existing tests that documented
   the draw-time shed are rewritten to the new contract.
3. Docs (`element_visuals.json` `_doc`, the design doc's budget line, this
   journal's results), the critic pass, index to done.

## RND-011: Todo

- [x] RND-011.1 — Journal and index
- [x] RND-011.2 — The shed in the update, on its own RNG, budget scaled to the step (`e9d24cf`)
- [x] RND-011.3 — Docs, critic pass, done
- [x] RND-011.4 — IDs after the rebase: the web-draw work is RND-012 (renamed from RND-010, which PR #55 took); index next-free RND-013
- [x] RND-011.5 — D5 confirmed by the owner: no shed under the end banner
- [x] RND-011.6 — Merge review of the open PRs: the `AuraShedTests` rewrite verified on a combined merge

## RND-011: Results

**What changes in play.** A primed body sheds the same motes a second at
any frame rate (Fire 7, Ice 5, the other two 6, per aura); the browser's
shed is no longer about 2.8x the desktop's. Pausing, the level-up, TAB and
any redraw add nothing and roll nothing. A run with auras on screen plays a
different `run.rng` sequence from before, once (D1); a run without them is
unchanged: `python -m tools.verification.run_digest --check` reads `match`
before and after the change (the scripted seeds never draw an aura), so
`run_digests.json` is not re-pinned. Under the end banner a primed body
stops shedding (D5). The F1 budget line reads the last step's use against
that step's own grant (about 31 at 175 Hz), not against 90.

**Cost.** Measured by the critic in the stress harness: `shed.update` is
about 0.14 ms a step with 100 bodies in view (78 primed), about 1.8 % of
the 7.7 ms update. The draw loses the same rolls.

**Tests.** New: `tests/render/test_aura_shed.py` (20 tests: draw purity
headless and booted, including the budget's whole state; rate per second
per element at dt 1/30, 1/62, 1/175, within 4 % of `rate` on a 5,000 to
7,000-mote sample; the whole part at dt 0.5; both caps biting by the same
amount a second; births equal grants; own stream and its seed; shed once a
step with its `dt`, after the ageing; nothing under the end banner).
Rewritten to the new contract: `BudgetTests` (`begin_step`, a second of
steps at 30, 62 and 175 Hz, nothing banked, the report),
`test_the_shed_asks_for_the_lower_layer`, and in
`test_elemental_draw_cost.py` the shed-order pin became "the world draw
leaves the run as it found it". `BootedRunTests` is listed as
`integration` in `tests/conftest.py`.

Runs: `tests/render tests/flows tests/playing tests/systems tests/devtools
tests/combat tests/screens`: 2,807 passed, 3,961 subtests (22.7 min),
before the critic's fixes. After them, the elemental modules, the tier
audit, `test_spawn_stress`, `test_end_banner` and the stray-English scan:
153 passed, 1 failed, the scan on `game/display/native.py:216`, which is
not in this diff and was fixed on `main` by `d99dcc5` (TST-009.1).

**Critic (one cold pass, frozen 8-item rubric).** FAIL on test pinning,
not on the code: no correctness bug found; rates checked independently
over 5 seeds and dt up to 0.75 (within 2.7 %); 2,000,000 mixed steps
drifted the budget by under half a mote; booted runs drawn never, once or
three times a step ended identical. Its findings and what was done:

| # | finding | done |
|---|---|---|
| 1 | draw purity did not see the budget (a refused `take` or a refill left `spent` at 0) | both purity tests compare the budget's whole state after a real step |
| 2 | D5 (no shed under the end banner) untested | `test_nothing_sheds_under_the_end_banner` |
| 3 | shed-after-ageing untested | `test_a_mote_is_drawn_whole_on_the_step_it_is_born` |
| 4 | F1 line `spent/90` misleading at short steps | `spent/granted`, pinned |
| 5 | "same seed, same motes" overclaimed: a mote's direction, speed and life come from the process-wide `random` in `ParticleSystem.burst` (unchanged, not gameplay) | docstrings say "which bodies, how many" |
| 6 | branch behind `main` (TST-009, SYS-012) | rebased before the PR |
| 7 | bursting the owed count rather than the grant was uncaught | `test_a_body_owed_several_motes_is_given_only_what_is_granted` |

Each fix was checked by mutation: the draw taking from or refilling the
budget, the shed moved before the ageing, a shed added to
`ending_sequence`, `count` for `granted`, and the old report string each
fail a test; restored, all pass.

## For RND-012

`tests/flows/test_frozen_backdrop.py::AuraShedTests` on
`ComeGalletas/web-draw-cheap-5be9212c` asserts, as its control, that
redrawing the run every frame under the pause piles particles up. After
RND-011 the draw sheds nothing at all, so that control fails. When the two
meet, keep the test's first half (60 paused frames: no particles added,
`run.rng` untouched, the kept frame still) and replace the control with:
the per-frame redraw also adds nothing and leaves `run.rng` alone, because
the draw no longer sheds (RND-011). The docstring's first sentence
becomes history: "Before RND-011 the run's draw shed aura particles".

**Verified on a combined merge (2026-09-30).** main `a6ac6c3` + #61 + #60
+ #57 + #55, in that order, in a scratch worktree. The only conflicts are
`INDEX.md` (rows from both sides, next-free the highest per system) and,
between #57 and #60, one hunk in `game/state.py` `StateMachine.__init__`
(keep both: #60's `self.updated`, #57's `self._frozen`). On that tree
`AuraShedTests` fails exactly at the control (`0 not greater than 0`,
`test_frozen_backdrop.py:296`) and passes with this replacement for the
control block (the docstring rewritten as above):

```python
        # A full redraw every frame, as before RND-012, adds nothing either
        # since RND-011: the shed is the update's, never the draw's.
        for _ in range(60):
            sm.invalidate_backdrop()
            sm.draw(screen)
        self.assertEqual(len(run.particles), particles, "a redraw shed particles")
        self.assertEqual(run.rng.getstate(), rng, "a redraw rolled run.rng")
        # The control: these auras do shed, in the update, once the pause
        # is gone.
        sm.pop()
        for _ in range(30):
            ps.update(1 / 62)
        self.assertGreater(len(run.particles.layer(True)), 0, "the auras never shed")
```

It holds only once both are in: on #57 alone the redraw still sheds, so
the change goes with whichever of the two merges second.

With it, the default suite on the combined tree: 4,221 passed, 7,547
subtests (21.8 min), nothing else broken by the four PRs meeting.
