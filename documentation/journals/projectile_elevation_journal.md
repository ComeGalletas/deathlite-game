# Projectiles climb stairs — journal

**ID:** CMB-010 · **System:** CMB (+ WLD) · **Type:** feature · **Status:** done (PR open) ·
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
  flight, head onto the terrace) lets it through; an illegal one (cliff face,
  plateau flank, the side of a flight) stops the shot as before. The floor
  rises when the climb lands on **ground**: a shot on the flight itself is
  still climbing, like a body on the stairs, so a turn off the stairs into the
  face beside them stays a wall. A shot fired *from* a flight leaves from its
  low end (`standing_level`). Lower ground never lowers the floor, so a shot
  that climbed, or was fired from high ground, still crosses a gap onto
  another terrace of the same height, as it did before (owner answer 1).
- **CMB-010.D2: A bouncing shot moves like a walking body.** Any projectile
  with `bounces_left > 0` is judged by `GameMap.is_walkable(pos, radius,
  frm=before, path=False, obstacles=False)` -- the floor test, the terrace
  margin, the radius probes -- with the move's steps walked exactly through
  `can_step` (D4) rather than by `path_ok`'s half-tile samples
  (`shot_terrain.body_blocks`). Two differences from a body, both because it
  is a projectile: it passes the props that do not block projectiles (a
  bush, a scarecrow), as a plain shot does, and meets the ones that do in
  `bounce`'s own obstacle test; and a ball already overhanging the water
  (centre on floor, radius over the edge) may roll on its centre until it is
  clear of it -- "cannot enter, may leave", as the collider treats the
  terrace margin. Anything a body could not cross
  is a wall to it, up **or down**: a cliff, a plateau flank or back edge with
  no stone in it, a shoreline, the sea. So a pinball fired on a terrace stays
  on it unless it rolls down the stairs, and one fired below climbs only by the
  stairs (owner answer 2). Its floor follows the ground it rolls on. The rule
  keys on `bounces_left`, never on the pinball's style or source, so any spawn
  passing `bounces=N` gets it.

  *On the ground or in flight* (`Projectile.landed`). A ball whose centre
  starts on floor is on the ground (a bridge mouth or a shoreline with its
  radius over the water included), and once on the ground it stays there:
  the body rule only ever moves it where its centre stays on floor. A ball whose
  centre starts off the floor -- fired by a flyer from over the sea, a lake or
  a cliff face -- is in flight until its whole body is over ground
  (`shot_terrain.on_ground`, through `GameMap.on_floor`: the centre and the
  radius probes, no margin, no obstacle). In flight it is walled by the edge
  of the world like a flyer and, when it carries a floor, by ground of any
  other level anywhere along its move (`lands_off_floor`, walked tile by
  tile like everything else): it comes down only on its own floor, which
  over a face or a lake is the terrace that terrain belongs to. A ball with
  no floor (fired from over the sea) comes down on whatever ground it
  reaches, as a plain shot from over the sea is stopped by nothing. A rock
  reflects it in flight as on the ground, and its seat is checked by the
  same wall test as its moves.

  *Sub-steps* (`TransientFx.roll`, D11). A bouncing shot's frame is walked
  again in pieces of at most 4 px, `bounce` judging each, so a ball meets a
  wall where it touches it and the same throw bounces the same way at any
  frame rate. A reflection whose very next step is walled too (a rock and a
  cliff closer than a step, the inside of a corner) sends the ball straight
  back the way it came, which was clear a step ago.
- **CMB-010.D3: Enemy shots follow the same rules** (owner answer 3). The
  hostile pool also gains the bounce branch, so a hostile shot with
  `bounces=N` bounces too; none has it today.
- **CMB-010.D4: The path is walked, not the endpoint** (owner answer 4). A
  shot's frame move is walked tile by tile in the order the segment crosses
  them (an Amanatides-Woo traversal, `shot_terrain._crossings`), each crossing
  one orthogonal step, so a fast shot cannot skip a stair foot, clip a tile
  corner or tunnel through a one-tile face. Plain and bouncing shots both use
  it. Only a segment through an exact tile corner (within 1e-9 of the move)
  steps diagonally, and an axis stops at the end tile, so a move ending on a
  boundary never overshoots. Half-tile sampling, as `GameMap.path_ok` does,
  was the first version; the critic showed a sample can jump a corner and a
  diagonal `can_step` accepts either detour (D7). A blocked shot is seated
  against the wall, half a pixel inside the last tile it was legally on: the
  impact touches the face, and what the shot spawns (a bomb's blast and
  bomblets) starts on ground it may stand on -- never inside the wall, on the
  plateau beyond, or on a neighbour across a corner. The start tile is judged
  on every move, so a shot standing above its floor (placed there without
  climbing) stops where it is.
- **CMB-010.D5: Unchanged** (owner answer 5): the open sea and the void
  (`top == NONE`) stop nothing, bridges are level-0 ground, orbiters and
  `no_block` shots are exempt, and `floor == NONE` still opts a plain shot out
  of the rule (the flat test map and hand-built test projectiles).
- **CMB-010.D6: `fire_level` is renamed `floor`.** The value now changes in
  flight, so "the level it was fired from" would be a lie after the first
  staircase. A split child, a bomb's blast and a cluster bomb's bomblets
  inherit the parent's current `floor`, which is the floor they are fired
  from. Stamping a bomblet's own would read the cliff face a blocked bomb
  stopped on, whose height is the terrace above.
- **CMB-010.D7: What the first critic pass broke** (2026-09-29, fixed in the
  same task): corner clipping under half-tile sampling (99 in 20,000 short
  shots near flights); the floor raised on a flight's first cell, letting a
  shot leave the stairs through their side (68 of 68 on seed 21) or be fired
  sideways off a flight through the face; bomblets stamping the terrace
  height from the face a blocked bomb stopped on; a rock on a terrace rim
  seating a reflected ball a level up or down (now the seat is checked with
  the ball's wall test and, when walled, bisected back toward the ball to a
  legal point -- `TransientFx._toward`, not necessarily the farthest one);
  the bounce
  branch ignoring the orbiter and `no_block` exemptions; `fire_hostile` taking
  no `bounces`. Each has a regression test (`CriticTests`,
  `test_bomblets_are_thrown_from_the_bombs_floor`, `test_an_enemy_shot_can_bounce_too`).
- **CMB-010.D8: What the second critic pass broke** (fixed in the same task):
  a blocked shot seated 0.5 px past a corner into a neighbouring tile, up to
  155 in 7121 corner-biased blocks on higher ground, from which bomblets
  climbed; the start tile unjudged once a move left it; the traversal
  overshooting up to seven tiles when a move ended exactly on a corner going
  the negative way; bouncing shots still clipping corners through `path_ok`
  (3 to 18 in 17,500 moves, frame-rate dependent); the new "back to `before`"
  obstacle seat pinning a ball in a pocket; a hostile bouncing shot fired over
  the sea spending its bounces on the spot. Each has a regression test
  (`TraversalTests`, `BounceRuleTests`, `PocketTests`). After the fixes, on the
  critic's own harnesses: 0 of 200,000 fuzzed segments differ from an exact
  rational traversal; 0 seats off the refused tile in 12,741 blocks; 0 corner
  clips and 0 level changes that do not pass a flight in 106,000 bouncing
  moves over three seeds at 60 and 20 fps; 0 frame-rate verdict differences
  in 4000 shots near flights; pinball wedges 1 against the old code's 6 over
  the same ~10,000 throws. The one left is a ball spawned inside the terrace
  margin beside a rock, which "cannot enter, may leave" legally holds there;
  a real pinball spawns at the hero, who is held to the same margin.
  (The seat and the in-flight rule described here were revised again in D9.)
- **CMB-010.D9: What the third critic pass broke** (fixed in the same task).
  The plain rule, the pinball and every existing `is_walkable` caller held
  (60,000 fuzzed plain shots, 0 differences from an exact traversal or across
  2 to 20 frames; 3,600 pinball throws, 0 illegal steps or level changes).
  Broken: a bouncing shot fired from off the floor counted as grounded the
  frame its *centre* reached floor, with its radius still over the water,
  and spent every bounce there (about 250 in 300 throws at 60 fps); one fired
  from over a face or a lake flew off it and came down a level lower (134 of
  295); bomblets from a bomb seated inside a face all died on their first
  frame; D7's seat wording was stale. Now a ball is grounded only with its
  whole body on floor (`GameMap.on_floor`, extracted from `is_walkable` so
  the collider and the shot share one body of the floor rule), a ball in
  flight lands only on its own floor, a pocket slides the ball along the gap
  before reversing it, and a blocked shot is seated on the legal side of the
  wall. Regression tests: `OffFloorTests`, the reworked
  `test_a_blocked_shot_is_seated_against_the_wall_that_stopped_it`. On the
  critic's harnesses after the fix: the shore-wedge repro rolls on with 5
  bounces left at 3 s; a face or lake launch lands a level lower 0 times of
  295; 5 of 8 bomblets fly, the 3 thrown at the face stop against it. The
  1 to 4 in 300 sea throws still flagged "spent within 12 px of the landing"
  were traced: a ball crossing a strip of ground about 60 px wide from shore
  to shore every quarter second, which is a bounce, not a wedge.
- **CMB-010.D10: What the fourth critic pass broke** (fixed in the same task).
  Held: `GameMap.is_walkable` against HEAD's on 180,000 samples, 0
  differences; the plain rule against an exact reference on 117,000
  segments and across 2 to 25 uneven frames, 0 differences; 7,500 grounded
  bouncing runs at 144/60/20 fps, 0 illegal steps. Broken: at a bridge mouth
  the bridge leniency put a grounded ball's radius over the water, the next
  frame judged it in flight, and it sailed off over the sea (71 of 2160
  bridge-rolling balls; a hero standing at a mouth threw a ball that never
  landed); a rock's seat was not checked for a ball in flight (1 in 364 came
  down a level lower); an in-flight move was judged at its end only (64 of
  54,511 13 px moves cut the corner of other-level ground); the pocket rule
  looked one frame ahead, so walls one to two moves apart still ping-ponged
  (23 pins in 9000 throws at the game's own 62 fps). Now ground is a sticky
  state set at the first frame, the seat and every in-flight move go through
  the same wall test, and the pocket look-ahead is a pixel distance of at
  least one frame's move. Regression tests: `GroundAndFlightTests`,
  `FastPocketTests`, each shown to fail with the old behaviour patched back
  in. On the critic's harnesses after the fix: 0 of 2160 bridge balls over
  the water, the mouth throw 0 of 600 frames over it; 0 of 364 rock-seat
  landings on another level; 0 of 190,000 in-flight moves over other-level
  ground; pins 1 in 9000 throws (HEAD: 82), and that one is a ball spawned in
  a spot with no legal 2 px move in any direction. The grounded fuzz's
  remaining "ungrounded" flags are balls legally at a bridge mouth.
  Performance on the critic's bench: a plain shot's terrain check 2.1 us
  against HEAD's 0.7 us (about 1 ms a frame for 500 shots), a bounce 11.3 us
  against 7.5 us. (The pocket look-ahead described here was replaced by
  sub-steps in D11.)
- **CMB-010.D11: What the fifth critic pass broke** (fixed in the same
  task). Held: `is_walkable` against HEAD's on 1,759,200 samples, 0
  differences; `_crossings` against exact arithmetic on 100,000 segments;
  the plain rule at 144/62/20 fps and jittered frames, 0 differences; 10,157
  seats, all legal; 16,392 grounded bouncing throws (4.1M frames), 0 illegal
  steps. Broken: a plain shot or bomb whose move crossed a face and ended in
  a rock beyond died in the rock, on the plateau, because the obstacle test
  ran before the terrain walk (186 of 47,372 stops at 62 fps; the order
  predates CMB-010 but contradicted D4); the pinball pinned depending on
  frame rate (13 of 72 headings at 20 fps, 0 at 62, at one spot) because a
  blocked ball went back to the frame's start; the D10 pocket rule's axis
  slides locked balls into straight-line pongs between parallel walls; a
  ball landing on a prop that does not block shots was refused every move by
  the body's obstacle test; a ball overhanging the water was refused every
  move by the radius probes; stale names and numbers in this journal.
  Now terrain is judged before obstacles in both pools, bouncing shots are
  sub-stepped (`roll`) with the pocket rule reduced to "straight back", a
  ball passes non-blocking props, and an overhanging ball may roll on its
  centre. Regression tests: `FrameLoopTests` (through `update_projectiles`),
  the reworked `PocketTests` and `FastPocketTests`. On the critic's
  harnesses after the fix: 0 kills past a wall in 47,372 stops; the
  fps-dependent spot 1 of 72 headings at every frame rate (a 10 px cell by a
  rock); 0 pongs in the pen repro; 75 of 75 balls landing on a prop get out;
  491 of 491 overhang throws roll on; 1,008 straight-wall reflections
  mirrored (the 17 others ran past the stretch checked); grounded fuzz
  (2,553 throws, 630,000 frames) 0 illegal steps, 0 off the floor, 0 leaving
  the ground. Flight launches (5,400): 3 flagged "landed on another level"
  are balls that came down on their own floor and, in the same frame,
  stepped onto a staircase's head (`standing_level` reads a flight's low
  end). A bounce costs about 24 us against HEAD's 14 us.

  *Residual, measured against HEAD on the same 9,000 pinball throws near
  rocks at 62 fps:* 27 balls spend every bounce in one tight corner between
  a rock and a wall, the same 27 as HEAD (bounces spent overall: 34.9k
  against HEAD's 34.5k). That is the ball's physics in a corner its body
  barely fits, not something CMB-010 introduced, and it is left as it is.
  Also residual, with no shooter today: of the few spots where a ball's
  body overhangs the water, 3 to 6 in 200 to 250 per world squeeze it
  between a rock and the waterline, where it spends its bounces.
- The obstacles a body cannot walk through but a shot flies over (bushes) still
  reflect a bouncing shot through `is_walkable`, as they did before CMB-010.

## CMB-010 — Plan

- A new module `game/states/playing/core/shot_terrain.py` holds the rule as
  pure functions over the `LevelIndex` and the map: `standing_level`,
  `muzzle_floor`, `travel` (the plain rule, D1 and D4), `steps_clear`,
  `body_blocks`, `on_ground`, `lands_off_floor` and `ground_floor` (the
  bouncing rule, D2). `GameMap` gains `on_floor` (the floor half of
  `is_walkable`) and `is_walkable(path=False, obstacles=False)` opt-outs;
  `Projectile` gains `landed`; `TransientFx` gains `roll`.
  `world/rules/` cannot hold it: that layer may not import `world.elevation`
  (`tests/world/test_layering.py`), and the rule is runtime-only anyway.
- `TransientFx` keeps `stamp_floor`, `block_on_terrain(proj, before=None)` and
  `bounce` as thin callers; `update_projectiles` passes each shot's
  pre-update position and gives the hostile pool the bounce branch.
- Tests: `tests/playing/test_projectile_elevation.py` gains stair climbing on a
  real pinned world (climb through a flight, blocked from its side, never
  drops, fast-shot tunnelling, impact at the face) and a bouncing section
  (pinball bounces off a flank drop, rolls up and down a flight, a
  non-pinball shot with `bounces=3` behaves the same, a hostile bounces),
  then one class per critic round (D7 to D11).
- Test lane (medium): `tests/playing/test_projectile_elevation.py`,
  `tests/playing/test_buffs.py`, `tests/entities/ai/test_flying.py`,
  `tests/render/test_projectiles.py`, `tests/render/test_enemy_sprite.py`,
  `tests/render/test_weapon_rigs.py`, `tests/world/test_elevation.py`,
  `tests/world/test_layering.py`, the combat split tests.

## CMB-010 — Tasks

- [x] CMB-010.1 — Open this journal and the index row
- [x] CMB-010.2 — `shot_terrain.py` (the plain climb rule and the bouncing body rule) wired through `TransientFx`: `fire_level` renamed `floor`, each frame's move walked, the hostile pool's bounce branch, split and blast inherit the floor; new tests on a pinned world, existing tests follow the rename. *(Planned as two tasks; the new tests exercise the module through `TransientFx`, so the rule and its wiring are one commit.)*
- [x] CMB-010.3 — Docs: D10 pointers in `level_design_journal.md`, `world/README.md`, the stale `stamp_fire_level` names in `enemy_ai_journal.md` and `boss_free_roam_todo.md`, memory; results and close

## CMB-010 — Results

- **Tests.** Full suite **3476 passed**, 11 deselected (the opt-in `sweep`
  tier), 1221 subtests; after rebasing onto main (WLD-014's step-rule
  change, ENT-018, RND-008) **3580 passed**, 11 deselected, 3134 subtests. `tests/playing/test_projectile_elevation.py` holds
  44 tests,
  about 9 s; every regression test added after a critic round was shown to
  fail with the old behaviour patched back in.
- **Critic.** Five cold critic rounds (medium triage: one pass was planned;
  each failed, so the loop ran until the findings were down to behaviour
  that predates CMB-010). What each broke and what fixed it is D7 to D11.
  The last round's residual is measured there against HEAD on the same
  throws and is unchanged by this work.
- **Measurable outcome.** A shot fired from low ground now reaches high ground
  through every straight staircase on the pinned world (73 of 73 climbing
  lines on seed 21, frame by frame and in one frame), where before every one
  of them died on the flight's first cell. Bouncing shots change level only
  through a flight (0 exceptions in 106,000 moves; HEAD let a pinball roll
  off plateau flanks). Plain-shot verdicts are the same at 144, 62 and 20
  fps.
- **Cost.** A plain shot's terrain check about 2 us against HEAD's 0.7 us
  (about 1 ms a frame for 500 live shots); a bounce about 24 us against
  14 us, from the sub-steps.
- **Behaviour change beyond the brief, flagged.** A bouncing shot no longer
  bounces off props that do not block projectiles (bushes, scarecrows); a
  plain shot never did (D2).
