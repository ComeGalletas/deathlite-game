# The enemies' own update: journal

**ID:** ENT-018 · **System:** entities (+ WLD) · **Type:** performance ·
**Status:** done (2026-09-29; closed at ENT-018.2's exact gain, owner D1) · **Branch:** ComeGalletas/ent-018-enemy-update-9ec11fc6
(the RND-008 worktree, stacked on the RND-008 branch while #39 waits to
merge; owner, 2026-09-29)

---

## ENT-018: Requirement (owner, 2026-09-29)

- **Objective:** Cut the time the enemies' own per-frame update takes, the
  largest item left in the update after RND-008.
- **Details:**
  - RND-008.7 listed it first among what is left: 2.4 to 3.8 ms at 110 to
    170 packed (`frame_time_journal.md`, "What is left").
  - RND-008.8 found the frame at 100 packed still over the 16.67 ms budget
    end to end: 18.4 to 19.1 ms.
  - The owner chose this as the next lever.
- **Constraint:**
  - **The game does not change.** Every enemy's position, velocity, knock
    and state, the gameplay RNG and the pixels stay bit for bit what they
    are. The collision pass in RND-008.5 had the same rule, for the same
    reason: positions are summed floats, and any change of order or
    rounding would be another game.
  - Built stacked on the RND-008 branch, in its worktree, while #39 waits
    to merge (owner).
  - The measurement uses RND-008's harness (`--jitter`, the frozen master,
    one budget). Before and after are taken back to back in one sitting.

## ENT-018: Confirmed reading (2026-09-29)

Measured with light `perf_counter` wrappers (inclusive times, so nested
parts are inside their callers; the wrappers add some cost of their own).
Harness, seed 35, 100 asked, 113 live at the end, packed, dummy driver,
240 frames (`scratchpad/enemy_parts.py`, `walk_parts.py`):

| Part | Time a frame | Calls a frame | Per call |
|---|---|---|---|
| `Enemy.update`, all | 4.65 ms | 103 | 45 µs |
| · the behaviour machine's tick | 2.69 ms | 103 | |
| · · `Separation.tick` (crowding push) | 1.06 ms | 59 | 18 µs |
| · · `SeekTarget.tick` (of which the flow field, 0.39 ms) | 0.59 ms | 73 | |
| · · `AvoidObstacles`, `AggroSense`, `Unstick`, `Cooldown`, steering | 0.45 ms together | | |
| · · the machine's own bookkeeping (the rest) | about 0.5 ms | | |
| · `GameMap.resolve_movement` (the movement probe) | 1.29 ms | 104 | |
| · · `GameMap.is_walkable` | 1.21 ms | 124 | 10 to 14 µs |
| · status, animation, the animation name | 0.20 ms together | | |

Inside the movement probe (`walk_parts.py`, same crowd):

| Part | Calls a frame | Per call |
|---|---|---|
| `_point_ok` (is this point on floor), 5 per probe | 500 | 1.2 µs |
| `inset_at` (how far inside its terrace) | 131 | 2.6 µs |
| the obstacle index's `near` | 97 | 1.6 µs |
| `path_ok` (the step between levels) | 101 | 1.3 µs |

**Two costs, both exact to remove:**

1. **`Separation.tick` allocates a vector for every neighbour candidate.**
   The grid query returns whole cells, so most candidates are beyond the
   push radius. Each one still pays a `Vector2` subtraction and a
   `length_squared` before it is dropped.
   - The fix is RND-008.5's: drop a candidate beyond the radius on float
     arithmetic first, with a billionth of margin inside the original
     limits.
   - The candidates that remain go through the original vector code, in
     the original order, so the push is the same sum.
2. **Every floor lookup scans every island.**
   - `world/rules/floor.py` `room_of` walks `layout.rooms` in order,
     testing each island's bounds and then its cells. `in_corridor` walks
     every bridge.
   - A probe asks five points on floor and one inset, so about 750 island
     scans a frame at 100 packed.
   - The fix is an index built once: per coarse square of the world, the
     islands (and bridges) whose bounds overlap it, **in the original
     order**. The scan then tests only those, with the identical condition.
   - An island outside the square fails the bounds test anyway, so the
     first match, and so the answer, is the same.
   - Only world generation edits cells, bounds or the island list
     (`world/gen/`). The run's `GameMap` is created from the finished
     layout (`loading_state.py:88`), or generates it in its own
     constructor, so an index the collider builds on first use can never
     see a layout still being built.
   - The navigation grid's build keeps calling the rule without the
     index, as now.

## ENT-018: Plan

- **ENT-018.2: Separation.** A float early drop in
  `entities/ai/components/crowd.py` `Separation.tick`.
  - Test: every body's push compared bit for bit with the old tick,
    copied verbatim, over random crowds and a seeded fight.
- **ENT-018.3: The floor index.**
  - `world/rules/floor.py`: a `FloorIndex` (square → islands and bridges,
    in order). `room_of`, `in_corridor`, `point_on_floor` and `inset_at`
    take an optional `index`.
  - `GameMap` builds its index on first use and passes it.
  - Test: every answer equal to the unindexed rule over dense samples of
    seed 35's world, points on square edges and in the void included.
- **ENT-018.4: Re-measure**, by part, and decide on the rest (the
  machine's bookkeeping, the flow-field lookup) with the numbers.
- **ENT-018.5: Results:**
  - before and after, one sitting, against the RND-008 tip;
  - a 150-frame fingerprint (pixels, both RNGs) against it;
  - the touched suites.
- Outcome to move: the enemies' own update p50 at about 110 and 165
  packed, and the whole update, measured back to back.

## ENT-018: Tasks

- [x] ENT-018.1: This journal; the index row
- [x] ENT-018.2: Separation drops far candidates on floats first, bit for bit the same
- [x] ~~ENT-018.3: The floor index for the collider's lookups~~: built, exact, measured **slower**, reverted (see Results)
- [x] ENT-018.4: Re-measured by part without wrappers; what is left is spread thin (see Results); the direction is the owner's call
- [x] ~~ENT-018.5: Results, fingerprint, suites~~: folded into the close (D1); ENT-018.2's results and suites are recorded above

## ENT-018: Results

### ENT-018.2: the crowding push

- `entities/ai/components/crowd.py` `Separation.tick` drops a neighbour
  candidate beyond the push radius, or closer than `1e-6` squared, on two
  float products before any vector. `_MARGIN_OUT` and `_NEAR` keep the
  drop a billionth inside the vector test's own limits. The neighbours
  that push go through the original code in the original order.
- `tests/entities/test_enemy_update_exact.py`, with the old tick copied
  verbatim as the oracle, compares every push handed to the steering
  accumulator with `==`:
  - 600 random crowds, each with the actor in its own list, dead bodies,
    coincident points, points at the radius and a hair past the minimum;
  - two neighbours placed on purpose within a billionth of each limit;
  - every enemy of seed 35's packed fight over 40 frames, with the real
    neighbour query (`integration`).
- Mutations (`scratchpad/mutate_e2.py`), all five caught:
  - either margin on the wrong side;
  - a drop that cuts neighbours that push;
  - the neighbours taken in another order;
  - a dead neighbour pushing.
- `tests/entities`: 356 passed. The tier audit passes.
- Its timing is taken with ENT-018.3's, in ENT-018.4.

### ENT-018.3: the floor index, built and reverted

- **Built.** A per-256 px-square index of the islands and bridges, in
  layout order, keyed the way each test reads a point (islands floored,
  bridges truncated like `Rect.collidepoint`, nan and inf handed the whole
  list). `GameMap` built it on first use. It was exact: 7 tests over the
  four pinned worlds, every edge and square boundary, a hand-drawn keying
  layout and the collider's own lookups, and five mutations, all caught.
  `tests/world`, `playing`, `entities` and `flows` gave 1,209 passed.
- **Measured slower.** Old against new in one process, no wrappers, on the
  packed crowd's own probe points (`scratchpad/micro4.py`):
  - the floor lookups at all 475 probe points: 0.170 → 0.226 ms, **+33 %**;
  - the inset lookups at all centres: 0.087 → 0.100 ms, **+15 %**.
- **Why.** Seed 35 has 9 islands and 13 bridges, and the linear scan's
  failing bounds tests are cheaper than keying a point, a method call and
  a dictionary lookup.
  - The plan's reading was wrong. The timing wrappers used for it add
    about half a microsecond per call. That made a floor lookup of
    0.36 µs look like 1.2 µs, and the scans look like the cost.
  - It is the trap RND-008.4 met with cProfile, one level down.
- **Reverted,** with a revert commit, so the history is kept. What was
  learned is the rule now used here: a candidate is timed without
  wrappers, old against new, before it is built.

### ENT-018.4: the enemy update, measured without wrappers

Each part timed in isolation over the whole packed crowd, 95 enemies, one
frame's worth each (`scratchpad/micro_parts.py`, best of 5):

| Part | Time a frame |
|---|---|
| `Enemy.update`, every enemy | **2.31 ms** (24 µs each) |
| · the behaviour machine | 1.12 ms |
| · · `Separation` (after ENT-018.2) | 0.29 ms |
| · · `SeekTarget` | 0.21 ms |
| · · `AggroSense`, `AvoidObstacles`, `Cooldown`, `MaintainRange`, `Unstick`, `Charge` | 0.23 ms together |
| · · the machine's own bookkeeping (the rest) | about 0.39 ms |
| · `GameMap.resolve_movement` | 0.65 ms |
| · · five floor lookups | 0.24 ms |
| · · the inset | 0.12 ms |
| · · the path check | 0.09 ms |
| · · the obstacles | 0.06 ms |
| · `Enemy.update`'s own body (vector math, knock decay, a `pow` per enemy) | about 0.5 ms |
| · status and animation | 0.04 ms |
| the flow-field lookup (inside `SeekTarget` and others) | 0.23 ms |
| the neighbour query (inside `Separation`) | 0.11 ms |

- **ENT-018.2's gain,** old against new over every enemy
  (`micro4.py`): `Separation` 0.618 → 0.469 ms, **−24 %**, about
  0.15 ms a frame at 113 packed.
- **What is left is spread thin.** No part is above 0.65 ms. The exact,
  small changes still open are:
  - a `pow` computed once per frame instead of once per enemy;
  - the machine's dictionary bookkeeping;
  - vectors allocated per step;
  - the floor rule's scan order.
  They come to about 0.5 ms at 100 packed, a fifth of the enemy update.
- **The real-loop question, answered** (`scratchpad/loop_gap.py`, two
  rounds). RND-008.8 recorded the update at 8.5 ms in the real Windows
  loop against 5.2 headless, and listed it as follow-up 8. Timed the four
  ways in one sitting (Windows or dummy driver, drawing between updates
  or not), there is no consistent difference:
  - round 1: 8.69 / 8.55 / 8.32 / 8.15 ms;
  - round 2: 5.75 / 6.50 / 8.29 / 8.06 ms, with Windows the faster.
  - The gap was the machine's load between sittings, not the loop.
  - Follow-up 8 in `frame_time_journal.md` is marked accordingly.
- **The decision is the owner's.** Three directions, with what each buys:
  1. **Finish ENT-018's exact changes:** about 0.5 ms at 100 packed, each
     pinned bit for bit, as ENT-018.2 was.
  2. **Close ENT-018 and turn to the terrain's ground bands:** 3.4 ms of
     the draw, the largest single item left in the frame.
  3. **Do less per enemy:** for example, steer a packed on-screen crowd
     every other frame, as the off-screen LOD already does. This buys
     most (about 1 ms at 100 packed), but it changes how a crowd moves,
     so it is a gameplay decision.

## ENT-018: Decision and close (owner, 2026-09-29)

- **ENT-018.D1:** of the three directions in ENT-018.4, the owner chose to
  close ENT-018 at ENT-018.2's exact gain and turn to the terrain's ground
  bands (the largest single item left in the frame), as a requirement of
  its own.
- **What ENT-018 leaves in the game:** `Separation.tick`'s early drop.
  Bit for bit the same, −24 % on its own part, about 0.15 ms a frame at
  113 packed.
- **What it leaves in the record:**
  - the enemy update measured without wrappers (ENT-018.4);
  - the floor index built, proven exact, measured slower and reverted
    (ENT-018.3);
  - RND-008's follow-up 8 found not to hold.
- **Still open, if wanted later:** about 0.5 ms of exact small changes in
  the enemy update (ENT-018.4), and the crowd LOD for a packed on-screen
  crowd, which would change how crowds move.

