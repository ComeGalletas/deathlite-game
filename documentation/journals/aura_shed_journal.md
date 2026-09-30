# The aura shed moves out of the draw: journal

**ID:** RND-011 · **System:** rendering (elemental visuals) · **Type:** bug ·
**Status:** in progress · **Branch:** ComeGalletas/aura-shed-update-a10d79ed
(owner, 2026-09-30; found by RND-010's critic passes, RND-010.D7 in
`web_draw_journal.md` on `ComeGalletas/web-draw-cheap-5be9212c`)

---

## RND-011: Requirement (owner, 2026-09-30)

- **Objective:** Take the elemental aura's particle shed out of the run's
  draw and into its update, so drawing a frame changes nothing in the run.
- **Details:**
  - Today `game/states/playing/visual/elements/layers.py` `_shed` runs
    inside `_aura`, once per drawn body wearing an aura: it rolls
    `run.rng.random() > rate / 60.0` and may call `run.particles.burst`.
  - Three consequences, measured in RND-010's critic passes: the shed's
    density scales with the draw rate (about 3x denser in the browser,
    host-paced at the display's refresh, e.g. 175 Hz, than at the
    desktop's 62 fps cap); the run's random stream, which gameplay also
    rolls on, is consumed per drawn frame, so gameplay randomness depends
    on how many frames were drawn (SYS-008, `run_determinism_journal.md`);
    and, before RND-010's frozen backdrop, pausing piled aura particles up
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
- **RND-011.D4 — branch off `main`** (owner, 2026-09-30). RND-010 is still
  in progress on another session's branch. Its
  `tests/flows/test_frozen_backdrop.py::AuraShedTests` documents the
  draw-time shed and its control (`the per-frame redraw piles particles
  up`) turns false with this change. Whichever of RND-010 and RND-011
  lands second updates it as written under *For RND-010* below.

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
- [ ] RND-011.2 — The shed in the update, on its own RNG, budget scaled to the step
- [ ] RND-011.3 — Docs, critic pass, done

## For RND-010

`tests/flows/test_frozen_backdrop.py::AuraShedTests` on
`ComeGalletas/web-draw-cheap-5be9212c` asserts, as its control, that
redrawing the run every frame under the pause piles particles up. After
RND-011 the draw sheds nothing at all, so that control fails. When the two
meet, keep the test's first half (60 paused frames: no particles added,
`run.rng` untouched, the kept frame still) and replace the control with:
the per-frame redraw also adds nothing and leaves `run.rng` alone, because
the draw no longer sheds (RND-011). The docstring's first sentence
becomes history: "Before RND-011 the run's draw shed aura particles".
