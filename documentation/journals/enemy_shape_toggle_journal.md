# Enemy shapes toggle — journal

**ID:** RND-013 · **System:** rendering (+ SYS dev tools) · **Type:** feature ·
**Status:** done · **Branch:** claude/rnd-013-enemy-shape-toggle (the
session's own worktree, `.claude/worktrees/enemy-asset-shape-toggle-9a7dea`)

A developer-menu switch that draws every enemy as a plain shape instead of its
sprite. The developer menu itself is SYS-002 (`dev_mode_journal.md`, which
points here from its "Later additions").

---

## RND-013 — Requirement (owner, 2026-10-07)

- **Objective:** Add a dev-menu toggle that swaps enemies between their loaded
  sprite art and generic shapes.
- **Details:** A row in the developer menu, on and off like the other dev
  switches.
- **Constraint:** Enemies only. Nothing else in the game changes how it is
  drawn. Confirm the reading first.

## RND-013 — Confirmed reading

What the code already does:

- Every enemy declares a sprite rig (`data/enemies/enemies.json` `sprite`), so
  `Enemy.anim` is an `Animator` for all of them
  (`tests/render/test_enemy_sprite.py: test_every_enemy_has_an_animator`).
- `WorldRenderer.one_enemy` (`game/states/playing/visual/rendering.py`) already
  has a primitive branch for a rig-less enemy: a filled circle the size of the
  collider in the data `color`, white during the hit flash, tinted by a status
  (burn, chill, shock, stun, mark) or else by the held aura, with thin rings at
  the collider edge for status, elite and shield. `WorldRenderer.boss` has the
  same kind of branch (circle plus a pale ring). Today that branch is reached
  only when a rig has no art, which no shipped enemy hits.
- The animators are visual only: `Enemy.update` ticks `anim`, and nothing in
  gameplay (AI, attacks, hits, the spawn master) reads a frame or an animation
  state. Drawing a shape instead of a frame cannot change a run.
- The developer menu (`game/states/dev_menu_state.py`) keeps its switches on
  `DevFlags` (`game/states/playing/devtools/dev_flags.py`), reached through
  `PlayingState._dev_*` properties; every switch is off on a fresh or reset
  dev run.

Decisions the request left open:

- **RND-013.D1 — What counts as an enemy.** Every body in `run.enemies` (the
  training dummy is one of them) and the boss. Not the hero, NPCs, summons,
  projectiles (enemy arrows and bolts included), pickups, terrain, or effects.
- **RND-013.D2 — The shape is the existing primitive fallback.** No new
  drawing code for the body: the toggle routes a sprited enemy into the branch
  a rig-less one already takes, so the shape carries the same cues (hit flash,
  status, aura colour, elite and shield rings). The `mark` brackets are drawn
  round the sprite's box, so with no sprite the mark shows as its raspberry
  ring, as it does for a rig-less body. The boss gets its own existing circle
  and ring.
- **RND-013.D3 — Draw-only and live.** The art stays loaded and the animators
  keep ticking, so turning the switch off shows the right frame at once. While
  it is on, no enemy frame is fetched, scaled, tinted, washed or shaded.
- **RND-013.D4 — What hangs off the body follows the shape.** The enemy HP bar
  hangs from the top of the circle instead of the sprite's ink, and the spawn
  burst wraps the collider, as both already do for a rig-less body. The burst,
  the death poof, telegraph rings, cast markers and elemental markers keep
  their art: they are effects, not enemies (D1).
- **RND-013.D5 — Dev runs only, off by default.** The flag lives on `DevFlags`
  beside the others, so a fresh or reset dev run starts with sprites, and a
  regular run draws sprites whatever the flag holds. Menu only: no F-key (the
  request names the dev menu).
- **RND-013.D6 — Found by the cold review: what the circle still owed the
  sprite.** Three cues the old fallback never had, settled here:
  - *The ghost.* A sprite behind a tree crown or a roof shows through it at
    the data's ghost alpha; the circle did not, so a debug view meant to show
    the crowd hid part of it. The circle is now queued for the ghost pass as
    a cached disc (`WorldRenderer.record_disc`), the boss's too.
  - *The mark.* The circle took the raspberry tint and ring whenever `mark`
    was held; the brackets show only while a held weapon reads the mark
    (RND-007). The circle now follows the same rule
    (`WorldRenderer.status_tint`). This also reaches the rig-less fallback,
    which no shipped enemy takes.
  - *The tree shade.* Not applied to the circle: a shade over a flat debug
    disc says nothing, and the shaded copy is the per-frame cost the switch
    takes away. Recorded, not changed.
  The boss's circle keeps the cues it always had (hit flash, pale ring); its
  status and mark show on the sprite only.

## RND-013 — Plan

- `DevFlags.enemy_shapes` and the `PlayingState._dev_enemy_shapes` property.
- `WorldRenderer.enemy_shapes()`: true only in a dev run with the flag on.
  `one_enemy`, `boss` and `spawn_fx_geometry` treat the body as rig-less while
  it is true; `health_bars.sprite_top` hangs the bar from the collider.
- Dev menu: an "Enemy shapes" row after "Collision shapes", `[ON]` / `[  ]`
  like the other switches, with a status line.
- Tests (`tests/render/test_enemy_shapes.py`, plus the dev-menu row in
  `tests/flows/test_dev_mode.py`): the row flips the flag; with it on, an enemy
  and the boss draw a circle and fetch no frame; the HP bar and the spawn burst
  use the collider; a regular run ignores the flag; turning it off brings the
  sprite back.
- Screenshot: the same dev-run frame with the switch off and on.

## RND-013 — Tasks

- [x] RND-013.1 — Journal, index row
- [x] RND-013.2 — The flag and the shape path in the renderer (enemies, boss,
  HP bar, spawn burst), with tests → `d48cea5`
- [x] RND-013.3 — The dev-menu row, with tests → `1baa2bf`
- [x] RND-013.4 — Screenshots, results
- [x] RND-013.5 — The cold review's findings: the ghost and the mark on the
  circle (D6), two tests that did not test what they named, the boss test on
  its own run, docstring and line-length nits → `10ed9d9`
- [x] RND-013.6 — The task hashes after the rebase, and the re-run on the new
  main

## RND-013 — Results

**Tests.** `tests/render/test_enemy_shapes.py` (13, `integration` tier):
off by default; every enemy id draws its collider circle and fetches no
frame; the data colour at the collider; the hit flash and the elite ring;
the HP bar off the circle; the spawn burst round the collider; the ghost of
a circle; the mark only while it matters; turning it off brings the sprite
back; the whole frame draws headless; the boss on its own run; a regular run
ignores the flag; a pinned run played 180 frames with it off and on ends
identical (enemies, animator frames, hero, clock, kills). In
`tests/flows/test_dev_mode.py`: the row flips the flag, shows its state, and
the whole frame then draws the circle; a reset run starts with sprites.

Proof the tests bite: against the renderer without the switch, the six
feature tests fail and the five invariants (off by default, regular run,
draw-only, turn-off, headless frame) pass; against the pre-review renderer,
the ghost and mark tests fail.

Lanes run (medium, DOC-008.D3: the tests covering the task):
`tests/render tests/devtools tests/flows/test_dev_mode.py`, 1057 passed,
0 failed, 768 subtests. The first run of the two directories caught one
miss: the new module boots a run and had to be registered in the
`integration` tier (`tests/devtools/test_tier_audit.py`), done in RND-013.2.
The `sweep` tier was not run (not asked). No eval applies: this is a
debug-view switch with no rate to measure.

**Measured outcome.** The enemy draw alone (`one_enemy` over every body),
212 enemies on the pinned dev world, median of 60 frames, best of three:
sprites 2.25 ms, shapes 0.78 ms (0.61 ms before the ghost recording of
RND-013.5). A scratch measurement, not a benchmark: it shows the switch takes
the sprite fetch, scale, tint, wash and shade out of the frame, which is what
it is for.

**Screenshots** (headless, delivered in the session, not committed): the same
dev-run frame with the switch off and on, and the menu with the row on.

**Cold review.** One critic pass (medium). Its findings: two tests that did
not test what they named, the boss test leaking state into a shared run, the
lost ghost, the mark rule, and three nits. All fixed in RND-013.5 or recorded
as D6.

After the rebase onto main (RND-010.5, the F1 overlay, came in beside the
same dev tooling): `test_enemy_shapes.py`, `test_tier_audit.py`,
`test_dev_mode.py`, `test_enemy_sprite.py`, `test_mark_overlay.py`,
`test_spawn_fx.py`, `test_enemy_hp_bar.py` re-run, 193 passed, 0 failed.

**Deferred.** None.
