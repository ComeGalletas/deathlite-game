# The enemies' own update: journal

**ID:** ENT-018 · **System:** entities (+ WLD) · **Type:** performance ·
**Status:** in progress · **Branch:** ComeGalletas/ent-018-enemy-update-9ec11fc6
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
- [ ] ENT-018.3: The floor index for the collider's lookups, bit for bit the same
- [ ] ENT-018.4: Re-measure by part; decide on what is left
- [ ] ENT-018.5: Results, fingerprint, suites

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

