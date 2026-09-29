# Projectiles climb stairs — journal

**ID:** CMB-010 · **System:** CMB (+ WLD) · **Type:** feature · **Status:** in progress ·
**Branch:** claude/projectile-collision-priority-aaaf97 (worktree `.claude/worktrees/projectile-collision-priority-aaaf97`)

---

## CMB-010 — Requirement (owner, 2026-09-29)

- **Objective:** Let a projectile reach a higher floor when it gets there
  through a staircase or pathway, the way a walking body does, while keeping
  the existing top-to-bottom rule (a shot fired from high ground still flies
  out over anything lower).
- **Details:** A shot's height is judged against the room layout's walking
  links rather than against raw height differences. Bouncing is a property
  any projectile may carry; only the pinball has it by default. A bouncing
  projectile handles every wall regardless of height: it bounces off any step
  a body could not make, up or down.
- **Constraint:** Confirm the reading before building (done, below). Enemy
  shots follow the same rule. No weapon gains bouncing, and no `bounces`
  field is added to the weapon data (owner, 2026-09-29: "no").

## CMB-010 — Confirmed reading

Before this change (LD-9 D10, `level_design_journal.md`), a shot stamped
`fire_level` at the muzzle and never changed it; `block_on_terrain` killed it
wherever `LevelIndex.top_at` stood above that level. A flight's cells report
their **upper** surface (`world/layout.py`, `Cell.level`), so a shot fired from
the low floor died on the first stair tile: low ground could never reach high
ground, stairs included.

- **CMB-010.D1: A plain shot's floor rises through legal steps and never
  drops.** It starts at the muzzle's height. On every tile change where the
  new tile stands higher than the floor, the shot asks the collider's own step
  rule (`world/rules/steps.py: can_step`). A legal step (stair foot, up the
  flight, head onto the terrace) raises the floor to the new tile's height; an
  illegal one (cliff face, plateau flank, the side of a flight) stops the shot
  as before. Lower ground never lowers the floor, so a shot that climbed, or
  was fired from high ground, still crosses a gap onto another terrace of the
  same height, as it did before (owner answer 1).
- **CMB-010.D2: A bouncing shot moves like a walking body.** Any projectile
  with `bounces_left > 0` is judged by `GameMap.is_walkable(pos, radius,
  frm=before)`: the floor test, the terrace margin and `path_ok`, which walks
  the segment tile by tile through `can_step`. Anything a body could not cross
  is a wall to it, up **or down**: a cliff, a plateau flank or back edge with
  no stone in it, a shoreline, the sea. So a pinball fired on a terrace stays
  on it unless it rolls down the stairs, and one fired below climbs only by the
  stairs (owner answer 2). Its floor follows the ground it rolls on. The rule
  keys on `bounces_left`, never on the pinball's style or source, so any spawn
  passing `bounces=N` gets it.
- **CMB-010.D3: Enemy shots follow the same rules** (owner answer 3). The
  hostile pool also gains the bounce branch, so a hostile shot with
  `bounces=N` bounces too; none has it today.
- **CMB-010.D4: The path is walked, not the endpoint** (owner answer 4). A
  shot's frame move is sampled every half tile, as `GameMap.path_ok` does, so
  a fast shot cannot skip a stair foot or tunnel through a one-tile face. A
  blocked shot is placed at the first sample that failed, which puts the
  impact on the face instead of on the plateau beyond it.
- **CMB-010.D5: Unchanged** (owner answer 5): the open sea and the void
  (`top == NONE`) stop nothing, bridges are level-0 ground, orbiters and
  `no_block` shots are exempt, and `floor == NONE` still opts a plain shot out
  of the rule (the flat test map and hand-built test projectiles).
- **CMB-010.D6: `fire_level` is renamed `floor`.** The value now changes in
  flight, so "the level it was fired from" would be a lie after the first
  staircase. A split child and a bomb's blast inherit the parent's current
  `floor`, which is the floor they are fired from.

## CMB-010 — Plan

- A new module `game/states/playing/core/shot_terrain.py` holds the rule as
  pure functions over the `LevelIndex` and the map: `muzzle_floor`, `travel`
  (the plain rule, D1 and D4) and `body_blocks` (the bouncing rule, D2).
  `world/rules/` cannot hold it: that layer may not import `world.elevation`
  (`tests/world/test_layering.py`), and the rule is runtime-only anyway.
- `TransientFx` keeps `stamp_floor`, `block_on_terrain(proj, before=None)` and
  `bounce` as thin callers; `update_projectiles` passes each shot's
  pre-update position and gives the hostile pool the bounce branch.
- Tests: `tests/playing/test_projectile_elevation.py` gains stair climbing on a
  real pinned world (climb through a flight, blocked from its side, never
  drops, fast-shot tunnelling, impact on the face) and a bouncing section
  (pinball bounces off a flank drop, rolls up and down a flight, a
  non-pinball shot with `bounces=3` behaves the same, a hostile bounces).
- Test lane (medium): `tests/playing/test_projectile_elevation.py`,
  `tests/playing/test_buffs.py`, `tests/entities/ai/test_flying.py`,
  `tests/render/test_projectiles.py`, `tests/render/test_enemy_sprite.py`,
  `tests/render/test_weapon_rigs.py`, `tests/world/test_elevation.py`,
  `tests/world/test_layering.py`, the combat split tests.

## CMB-010 — Tasks

- [x] CMB-010.1 — Open this journal and the index row
- [ ] CMB-010.2 — `shot_terrain.py`: the plain-shot climb rule and the bouncing body rule, with tests on a pinned world
- [ ] CMB-010.3 — Wire it: rename `fire_level` to `floor`, walk each frame's segment, hostile bounce branch, split and blast inherit the floor; existing tests follow
- [ ] CMB-010.4 — Docs: D10 docstrings, `level_design_journal.md` pointer, `world/README.md` if touched, memory; results and close
