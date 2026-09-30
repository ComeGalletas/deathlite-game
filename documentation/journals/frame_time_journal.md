# Gameplay frame time: journal

**ID:** RND-008 · **System:** rendering (+ SYS, ENT, CMB) · **Type:**
performance · **Status:** done (2026-09-29; RND-008.4 short of its
target and accepted in D7, re-checked in RND-008.8) ·
**Branch:** ComeGalletas/rnd-008-frame-time-9ec11fc6 (its own worktree, cut
from `origin/main` at `5176c0c`, owner 2026-09-28)

---

## RND-008: Requirement (owner, 2026-09-28)

- **Objective:** Bring gameplay frame time back inside the frame budget,
  working from the reviewed performance findings and their corrected todo
  list.
- **Details:**
  - The source is `GAMEPLAY_PERFORMANCE_FINDINGS.md`, an untracked report
    in the shared checkout. It was reviewed on 2026-09-28 against the code
    and re-measured on the Windows renderer. The review is the
    "Confirmed reading" below. The report itself is kept verbatim in the
    appendix, so this journal is the one place that holds both.
  - The todo list is ordered by measured payoff, not by the report's
    order.
- **Constraint:**
  - **Confirm the plan before any code change** (owner, 2026-09-28).
  - Gameplay does not change. Pixel output does not change, except where a
    task says so and the owner agrees.
  - The window-scaling rules hold: the camera zoom and the covered world
    area stay as they are at every size.
  - **The render stays at native resolution** (owner, 2026-09-28).
    Lowering the resolution or `config.RENDER_MAX_HEIGHT` is not
    considered at all as a way to meet the budget (RND-008.D4).
  - No timing assertion goes into the suite, because it would be flaky.
    Timings live in this journal. The tests pin behaviour that timing
    depends on, such as "no font is built after the first frame".
  - `game/fonts.py` keeps its no-module-cache rule: a module-level cache
    hands back `Font` objects across a `pygame.quit()` / `init()` cycle and
    segfaults the suite. Any cache belongs to the object that draws, as
    `ui/damage_numbers.py` already does.
  - numpy and `coverage` stay test tools only.

## RND-008: Confirmed reading (review of the report, 2026-09-28)

Measured on Windows 11 with the SDL `windows` driver, vsync on, and the
saved 2560 × 1080 windowed 21:9 display. `RENDER_SCALE` is 1.2 and the
effective zoom 1.797. Seed 35, 240 timed frames after a 60-frame warm-up,
the same as the report. How each number was taken is under "Method".

### What holds

- **The report's numbers reproduce.** Same seed, same workloads, identical
  live and in-view counts, and timings within about 10 %:

  | Workload | Live / in view (report → rerun) | Update p50 (report → rerun) | Draw p50 / p90 / p99 (report → rerun) |
  |---|---|---|---|
  | 60 packed | 79 / 64 → 79 / 64 | 5.76 → 5.22 ms | 24.77 / 27.04 / 39.65 → 23.52 / 26.14 / 36.79 ms |
  | 100 packed | 131 / 103 → 131 / 103 | 8.98 → 7.76 ms | 27.21 / 30.51 / 41.70 → 24.67 / 27.01 / 36.05 ms |
  | 100 packed, three infused weapons | 119 / 102 → 119 / 102 | 9.78 → 7.86 ms | 33.61 / 38.60 / 57.01 → 28.79 / 32.45 / 50.87 ms |

- **Bump scaling reproduces.** The measurement used a separate script
  (dummy driver, master frozen, positions fixed, the harness's `--pack`
  crowd), timing `BumpResolver.resolve` alone:

  | Seated | Bump p50 / p90 / p99 (rerun) | Report |
  |---|---|---|
  | 18 | 0.093 / 0.108 / 0.118 ms | 0.124 / 0.145 / 0.184 ms (20) |
  | 58 | 1.047 / 1.713 / 3.075 ms | 0.870 / 0.967 / 1.072 ms (60) |
  | 95 | 1.907 / 2.137 / 2.466 ms | 2.065 / 2.347 / 2.918 ms (100) |
  | 144 | 4.102 / 4.984 / 5.400 ms | 4.562 / 5.059 / 5.734 ms (150) |

- **Hero jitter does inflate update time, at small crowds.** Update p50
  with the hero jittered versus standing still: 3.18 / 0.95 ms at about 20
  enemies and 7.05 / 3.49 ms at about 60. At 95 and 144 enemies there is no
  difference (9.53 / 9.24 ms and 13.14 / 13.03 ms). The stationary runs
  also ended with more enemies, which makes that comparison conservative.
- **The frozen master still admits bodies.** With `m.frozen = True` kept
  through timing, 58 enemies grew to 67 and then 76 over 480 frames.
  Committed arrivals and enemy summons pass the `frozen` gate
  (`spawn/master.py` `update`), as the report says.

### What the report gets wrong

1. **Draw time is not driven by resolution. It is the tutorial hints.**
   - `game/states/playing/visual/hints.py` `draw` costs about **16 ms a
     frame**:
     - It calls `fonts.body(WORD_PX)` every frame (`hints.py:88`), and
       `keycap.draw_keycap` calls `fonts.body(...)` again for every cap
       (`ui/keycap.py:191`). Each call builds a new `Font` from the
       variable TTF, with a `Path.exists` stat each time.
     - A new `Font` starts with an empty glyph cache, so `Font.render`
       costs about **1.4 ms a call**, ten calls a frame.
   - The harness never lets the hint clear. It jitters the hero ±24 px,
     but the Move stage ends at `HINT_MOVE_DISTANCE` = 96 px
     (`game/config.py:1098`). So the Move hint is up for every measured
     frame of every report run.
   - Profile, hints on, 22 live and 7 in view, 120 frames under cProfile:
     `ps.draw` took 3.129 s in all (26 ms a frame). Of that,
     `hints.draw` took 1.918 s (16.0 ms a frame): 1,200
     `Font.render` calls took 1.684 s, and 600 `fonts._load` calls with
     600 `nt.stat` took 0.170 s. The whole world pass took 1.17 s
     (9.7 ms a frame).
   - The same scenes with the hints dismissed (`ps.hints.dismiss()`),
     2560 × 1080:

     | Workload | Hints | Update p50 | Draw p50 / p90 / p99 | Update + draw p50 / p90 | Frames over 16.13 ms |
     |---|---|---|---|---|---|
     | 60 packed | off | 5.04 ms | 8.81 / 10.88 / 23.74 ms | **13.81** / 16.87 ms | 28 / 240 |
     | 100 packed | off | 8.70 ms | 11.48 / 13.80 / 26.24 ms | 20.39 / 24.29 ms | 232 / 240 |
     | 100 packed, infused | off | 7.82 ms | 15.83 / 20.09 / 41.11 ms | 23.61 / 31.25 ms | 240 / 240 |
     | 100 packed (control) | on | 9.97 ms | 28.91 / 30.89 / 39.83 ms | 38.86 / 42.52 ms | 240 / 240 |

   - In real play the hints are on screen for the opening seconds of
     **every** run (owner rule: they are an Options toggle, not a
     first-run flag): until the hero walks 96 px, then up to
     `HINT_ATTACK_SECONDS` = 5 s, plus a 0.4 s fade. During the fade
     `hints.py:93` allocates a full-surface `SRCALPHA` buffer every frame:
     2560 × 1080 × 4 bytes, about 11 MB a frame.
   - The same per-frame font build runs whenever the floating interact
     key is shown (`game/states/playing/visual/key_marker.py:203`), which
     calls `draw_keycap` with no font. That is a steady cost near any
     chest, building or NPC, not only at run start.
2. **Lowering the render scale buys about 3 to 4 ms, not the budget.**
   The existing knob is `config.RENDER_MAX_HEIGHT` (`game/config.py:49`),
   which the report does not mention. Draw p50 with the packed crowd:

   | Render surface | Zoom | Hints on, 7 in view | Hints on, 64 in view | Hints off, 103 in view |
   |---|---|---|---|---|
   | 2560 × 1080 | 1.797 | 21.29 ms | 23.12 ms | 11.48 ms |
   | 2133 × 900 | 1.500 | 20.28 ms | 22.10 ms | (not run) |
   | 1707 × 720 | 1.203 | 18.31 ms | 19.82 ms | 7.74 ms |

   A 720-line render has 44 % of the pixels and saves 3.0 ms with the
   hints on and 3.7 ms with them off. Even with the hints off, 100 packed
   at 720 lines is still over budget: update + draw p50 16.97 ms, and 154
   of 240 frames over. These numbers stay as the record of the review
   only. The owner ruled resolution out as a lever (RND-008.D4), so
   nothing is planned on them.
3. **The aura-ring cache targets a path the shipped game barely uses.**
   All four elements have an authored aura rig (`aura_rig` in
   `data/weapons/element_visuals.json`, lines 148, 163, 178 and 193). So
   `layers._aura` blits the cached sprite frame, and the fallback `_ring`
   is only drawn for the locked slot. `_ring` does not appear in the
   hints-off infused profile at all, and `_aura` took 0.208 s over 200
   frames. The report's prototype measured the fallback path in the dummy
   renderer.
4. **The harness unfreezes the master before timing.** `build()` sets
   `m.frozen = False` at `tools/benchmarks/spawn_stress.py:90`, so the
   director seats new companies during every measured frame, on top of the
   leak through the `frozen` gate. That is the larger reason the requested
   counts drift (60 → 79, 100 → 131).
5. **Smaller points:**
   - The summary budgets 16.13 ms (`FPS` = 62), but the table's column
     counts frames over 16.7 ms (`spawn_stress.py:427`). With vsync on a
     60 Hz display, 16.7 ms is the real budget. The two should not be
     mixed.
   - The isolated bump script, the weapon-count script and the aura-cache
     prototype are not in the repo, so those numbers cannot be re-run as
     the report ran them. Bump was reproduced independently. The weapon
     count was not re-run, so its 0.40 ms figure stands unverified.
   - The in-game debug overlay's render timing
     (`game/game.py` `_step`) includes `display.flip()` and so the vsync
     wait. It is not comparable to the harness's draw figure.

### Where the draw time goes with the hints off

cProfile, 100 packed, three infused weapons, 200 frames. cProfile inflates
the totals, so these are shares, not budgets:

- 127,532 `Surface.blit` calls (638 a frame): 2.05 s.
- `elements.draw_under`: 1.465 s. It runs once per terrace band (600
  calls, three a frame), and each run walks every body and particle.
  That comes to 191,196 `transient.off_band` calls, 956 a frame.
- `rendering.one_enemy` (sprite, rig, shade, health bar): 1.60 s.
- `terrain.draw_ground_band`: 0.956 s. This is the part that scales with
  pixels, and so the part the render scale moves.
- `layers._shape` (a new `SRCALPHA` surface for each slowed or frozen
  mark): 11,827 calls, small.
- `damage_numbers.draw`: 0.216 s. Plain numbers re-render their text every
  frame. Outlined ones are cached.

## RND-008: Decisions (confirmed by the owner, 2026-09-28)

- **RND-008.D1: Type `performance`.** The index has no such type yet.
  `bug` fits the hint fonts but not the bump or elemental work. Proposed:
  add `performance`.
- **RND-008.D2: Where the font cache lives.** Proposed: the object that
  draws holds it, keyed by `(role, px, bold)`, and drops it when the
  display is re-opened (`RENDER_SCALE` changes the pixel size). This is
  the `ui/damage_numbers.py` pattern, and it keeps `fonts.py` itself
  cache-free.
- **RND-008.D3: The harness measures play, not the tutorial.** Proposed:
  hints dismissed by default (`--hints` to keep them), the master kept
  frozen through timing (`--live-director` to let it run), one budget
  (16.7 ms, the vsync period, reported next to `1000 / FPS`), and the
  render surface and zoom printed with every run.
- **RND-008.D4: The resolution stays native.** Owner, 2026-09-28:
  changing the render resolution is not considered at all, not as a
  default, not as a knob to measure. The frame time is found in the code.
  RND-008.6 (the render-scale comparison) is dropped, and the harness
  gets no `--max-height` flag.
- **RND-008.D5: The aura-ring cache is dropped.** The fallback is not the
  shipped path (Confirmed reading, item 3).
- **RND-008.D6: Weapon-loop work is deferred.** It was not re-run, and
  every measured cost above it is larger.
- **RND-008.D7: RND-008.4 is accepted at about −20 %** (owner,
  2026-09-29), short of its −50 % target, with a condition: a full test
  at the end of RND-008 checks the elemental fight again alongside
  everything else (RND-008.8).
  - Asked on accepting it: does RND-008.4 lengthen loading? No. The sort
    runs inside each frame's draw, and the two caches fill on first use
    during play. Nothing on the loading path changed.
  - Measured, loading to the run's first frame, seed 35, three runs each,
    alternated: RND-008.3 3.84 to 4.04 s, RND-008.4 3.94 to 4.01 s. The
    first frame took 7.4 to 9.0 ms either way.

## RND-008: Plan

Each task names the number it has to move. "Before" is the rerun above.
"After" is taken with the same command and recorded under Results.

- **RND-008.2: Harness.**
  - `tools/benchmarks/spawn_stress.py`: the D3 flags and output, plus a
    `--bump` mode that times `BumpResolver.resolve` alone (the report's
    isolated test, now in the repo).
  - Re-baseline hints on and off.
  - Outcome: the report's workloads re-run from one command each, with
    the live count held at what was asked for (no drift with the master
    frozen, apart from summons, which are reported).
- **RND-008.3: No font is built while a run draws.**
  - `hints.py` and `keycap.draw_keycap` take their fonts from a cache
    held by their owner (D2).
  - The hint's word surfaces and the cap labels are cached per text,
    colour and size.
  - The fade draws into a block-sized buffer, not a full-surface one.
  - `key_marker.py` passes a cached font.
  - Tests:
    - After a warm-up frame, `PlayingState.draw` on a pinned seed calls
      `fonts._load` zero times: with the Move hint up, during its fade,
      with the Attack hint, and with the interact key shown. This is the
      general check that catches the next per-frame font anywhere in the
      draw path, not only in these three files.
    - The hint block and the interact cap are pixel-identical to the
      current output.
    - A display re-open rebuilds the cache at the new `RENDER_SCALE`.
  - Outcome: at 2560 × 1080 with 100 packed, draw p50 with the hints on
    within 1 ms of the hints-off figure (RND-008.2 baseline: 27.27 →
    about 10.2 ms). The hints' own cost drops from about 17 ms to under
    1 ms.
- **RND-008.4: The elemental draw.**
  - Walk the bodies once per frame, bucket them by terrace level, and
    hand each band its bucket. Today each of the three band passes tests
    every body and particle with `off_band`.
  - Cache the `_shape` status marks per (shape, size, colour, alpha).
    *Dropped: a cached mark differs by an edge pixel in 31 of 60,000
    positions (see Results).*
  - Cache plain damage-number glyphs, as the outlined ones already are.
  - Tests: pixel-identical frames for a primed crowd across terrace
    bands, and the same draw order (auras under bodies, reactions on
    top).
  - Outcome: the infused-minus-packed draw gap at 2560 × 1080 halved or
    better (RND-008.2 baseline: 15.99 − 10.22 = 5.77 ms p50). *Missed:
    about −20 %; see Results.*
- **RND-008.5: Update, re-measured, then decide on bump.**
  - With the harness fixed: stationary versus jittered hero, frozen
    master, 60 / 100 / 150 packed. Take a cProfile of `ps.update`.
  - Cheap bump wins, only if bump is still the largest single item:
    - bound the broad-phase query by the largest radius present instead
      of the fixed 72 px pad (`physics.py` `_QUERY_PAD`);
    - dedupe pairs by index instead of a set of `id()` tuples.
  - Tests: `tests/playing/test_bump.py` unchanged and green, plus a
    pinned case where the resolved knockbacks match the current resolver
    exactly.
  - Outcome: a decision recorded here with its numbers. Bump p50 at 144
    packed down from 4.10 ms if the change is made.
- **RND-008.6: Dropped** (D4). The resolution is not a lever, so there
  is nothing to measure.
- **RND-008.7: Results.** The before and after tables, the index moved to
  done, and a pointer from the untracked report to this journal. Whether
  the root `GAMEPLAY_PERFORMANCE_FINDINGS.md` is deleted is the owner's
  call.
  - *Changed on the way:*
    - The index moves to done in RND-008.8, because D7 put the full test
      after this.
    - The pointer is not written: the report sits untracked in the
      shared checkout, where no session writes (`CLAUDE.md`,
      "Branching"). The journal holds it verbatim, and deleting it is
      left to the owner.

## RND-008: Tasks

- [x] RND-008.1: This journal, with the reviewed findings and the report; the index row
- [x] RND-008.2: Harness: hints off by default, master frozen through timing, one budget, `--bump`; re-baseline
- [x] RND-008.3: No font built during a run's draw (hints, keycaps, interact key, and the pause menu's Controls block); cached word and label surfaces; a block-sized fade buffer; the `fonts._load` sweep test
- [x] RND-008.4: Elemental draw: bodies and motes sorted onto their terraces once a frame; the burn flame scaled once; plain damage-number glyphs kept. The status-mark shape cache was dropped (it changes edge pixels). **Outcome missed: the gap fell about 20 %, the target was 50 %**; accepted by the owner (D7), with the full test in RND-008.8
- [x] RND-008.5: Update re-measured by part (60 / 100 / 150 packed, hero jittered and still, plain and infused); the bump decision; the bump pass about halved, bit for bit the same; `--jitter` on the harness
- [x] ~~RND-008.6: Render-scale comparison~~: dropped, D4 (the resolution stays native)
- [x] RND-008.7: Results, before and after, in one place; the follow-ups found on the way (the index moves to done in RND-008.8)
- [x] RND-008.8: The full test at the end (D7). The whole suite, `sweep` included, on the final branch, and the harness workloads (plain, infused, hints on and off, bump) against the RND-008.1 base in one sitting, with RND-008.4's accepted −20 % re-checked in the elemental fight. Loading time is compared too.

## RND-008: Results

### RND-008.2: the harness

- **What changed** (`tools/benchmarks/spawn_stress.py`):
  - `build(..., hints=False, live_director=False)`. By default the opening
    hints are dismissed, and the master is frozen before the crowd is
    seated, with its in-flight company dropped (`drop_pending`), and stays
    frozen through the timed frames.
  - `--hints` and `--live-director` bring each old behaviour back, so the
    numbers in the spawn master journal can still be re-taken.
  - `BUDGET_MS` is one 60 Hz vsync period (16.67 ms). It counts the frames
    over, and the 62 fps cap is printed beside it (16 ms: pygame truncates 1000 / 62 to
    whole milliseconds, corrected from 16.13 by SYS-010). pygame 2.5
    cannot read the refresh rate, so the value is fixed.
  - Every run prints a display line (surface, driver, vsync, render scale,
    zoom, hints, director, budget). It also prints the crowd at the start
    of timing and what arrived during it, by spawn owner.
  - `--bump` times `BumpResolver.resolve` alone with nothing moving and the
    hero parked out of reach. The impulses a pass adds are put back after
    it, outside the timer, so every pass meets the same crowd. The hero is
    put back at the end. `--bump` refuses `--render`, `--profile` and the
    element flags: it would ignore the first two, and with elements the
    frozen-contact rule deals damage that is not put back.
  - `build(..., save_path=...)`, and `--hints` shows the hints even with the
    Options "Tutorials" row off (flipped in memory while `RunHints` reads
    it, never persisted).
  - `arrivals` keeps the bodies themselves, not bare `id()`s, so a body freed
    during the timing cannot hand its address to a newcomer and hide it.
  - `--frames` below 1 is refused.
  - The two `game/config.py` notes that cite harness measurements now say
    they were taken with the pre-RND-008 defaults, and how to re-take them.
- **What still moves the crowd:**
  - **Enemy summons.** They are behaviour, not the director, and D3 keeps
    them in, reported. At 100 asked they add 11 to 18 bodies over 240
    frames.
  - **The despawn ring.** `build` seats all it is asked for (100 of 100,
    60 of 60). During the 60-frame warm-up the ring puts a few seated
    bodies to sleep (5 of 100, 3 of 60), so timing starts at 95 and 57.
  - Both are printed, so each table row below says what it measured.
- **Cold critic (medium rule).** A separate agent reviewed the diff against
  a frozen rubric and returned FAIL, with five should-fix findings and four
  nits. All were fixed:
  - `--bump` let impulses pile up, so later passes took the frozen-contact
    branch (sliding bodies went from 1 to 74 over 300 passes).
  - The journal blamed walkability for the seating shortfall. It was the
    ring.
  - The tests read the owner's `save.json`, so Tutorials off would have
    broken two and made a third pass without testing anything.
  - The command-line test passed `--hints --live-director` together, so it
    could not see the two swapped.
  - `arrivals` compared bare `id()`s.
  - The nits: the flags `--bump` ignored, `--frames 0`, one blank line,
    and the stale `config.py` notes.
- **Tests:** `tests/devtools/test_spawn_stress.py`, 17 tests (4 subtests).
  Three classes boot a run on seed 35, each on a fresh save
  (`integration`, registered in `tests/conftest.py`). The flag-plumbing and
  budget classes boot nothing (`unit`, 0.04 s).
  - They pin:
    - the hints are dismissed (enabled, not shown);
    - `--hints` shows them with Tutorials off and leaves the setting off;
    - a kept Move hint is still up after 300 frames of the harness's
      jitter;
    - the master stays frozen through 300 timed frames, with no `director`
      arrival;
    - no company is left in flight (one is put in the air on purpose,
      because seed 35 has none at the freeze);
    - a live director does add companies (the control);
    - every bump pass shoves the same bodies by the same total impulse,
      never meets the parked hero, and leaves positions, impulses and the
      hero as found;
    - each flag reaches `build` on its own;
    - `--bump` refuses the four flags, and `--frames 0` is refused;
    - a default `--pack --bump` run prints its display line and passes;
    - the budget count.
  - **Mutation check** (`mutate.py` in the session scratchpad): each
    pre-fix behaviour was put back in turn, and every one failed at least
    one test:

    | Behaviour put back | Tests failed |
    |---|---|
    | the master unfrozen after seating | 4 |
    | the hints kept by default | 3 |
    | the in-flight company kept | 1 |
    | impulses left to pile up between bump passes | 1 |
    | `--hints` silent with Tutorials off | 2 |
    | the two flags swapped on the way to `build` | 2 |
    | `--bump` accepting `--render` | 1 |

    The bare-`id()` arrival bug is fixed but not pinned: it needs CPython
    to reuse a freed address, which no test can arrange reliably.
  - Result: 17 passed in 13.3 s. `tests/devtools` 85 passed (6 subtests)
    in 41.8 s. The suite collects 3,456 of 3,467, with the 11 `sweep`
    deselected.
- **Re-baseline.** Windows renderer, 2560 × 1080, render scale 1.2, zoom
  1.797, seed 35, 240 timed frames:

  | Workload | Crowd start → end (arrived) | Update p50 / p90 | Draw p50 / p90 / p99 | Update + draw p50 / p90 | Over 16.67 ms |
  |---|---|---|---|---|---|
  | 60 packed | 57 → 66 (summon 9) | 4.59 / 5.57 ms | 8.17 / 9.95 / 22.01 ms | **12.82** / 15.68 ms | 12 / 240 |
  | 100 packed | 95 → 113 (summon 18) | 7.87 / 12.70 ms | 10.22 / 13.39 / 20.72 ms | 17.86 / 25.80 ms | 167 / 240 |
  | 100 packed, infused | 96 → 107 (summon 11) | 8.34 / 11.29 ms | 15.99 / 21.11 / 38.75 ms | 24.76 / 30.46 ms | 237 / 240 |
  | 100 packed, `--hints` | 95 → 113 (summon 18) | 8.36 / 10.87 ms | 27.27 / 31.55 / 40.66 ms | 35.10 / 42.04 ms | 240 / 240 |
  | 100 packed, `--hints --live-director` (the report's setup) | 103 → 131 (director 10, summon 18) | 7.88 / 9.60 ms | 27.07 / 29.77 / 38.73 ms | 35.40 / 38.70 ms | 240 / 240 |

  - This table was taken before the critic's fixes. It still stands for
    the final code: those fixes touched `bump_times`, the arrival
    bookkeeping done after timing, argument checks, and the Tutorials-off
    branch. None of them runs inside a timed render frame. A second run
    on the final code gave identical crowds (57 → 66, 95 → 113, 96 → 107,
    103 → 131), but timings 20 to 60 % higher with a 242 ms spike. A game
    client and another long-running Python process had the CPU at 57 %
    load, so that run is not used.
  - The last row is the report's setup, and it lands on the report's
    numbers (131 live, draw p50 27.21 ms in the report). So the new
    defaults are the only thing that moved the other rows.
  - On the same crowd, the hints cost **17.05 ms** of draw p50
    (27.27 − 10.22). That is RND-008.3's target.
  - In the infused run the damage-number pool hit its cap (200 / 200).

  Bump alone (`--pack --bump`, dummy driver, 300 passes, final code, **CPU
  under the load above**):

  | Crowd | Bump p50 / p90 / p99 |
  |---|---|
  | 18 | 0.103 / 0.122 / 0.185 ms |
  | 58 | 0.911 / 1.199 / 1.869 ms |
  | 95 | 2.175 / 2.534 / 2.947 ms |
  | 144 | 4.716 / 5.350 / 6.012 ms |

  These are in the range of the review's probe (4.10 ms p50 at 144) and
  the report (4.56 ms at 150). The load makes them an upper bound, not a
  baseline. RND-008.5 takes its before and after back to back in one
  sitting, which is the only comparison this machine supports.

### RND-008.3: no font built while a run draws

- **What changed:**
  - `ui/text_cache.py` (new): `TextCache`. It keeps fonts by role, design
    size, weight and `config.RENDER_SCALE`, and the surfaces rendered from
    them (plain, and `ui.text.shadowed`) by text and colour, bounded at
    256. The object that draws holds it (D2). The role's function is
    looked up on `game/fonts.py` at build time, so a patched face is used.
    `game/fonts.py` is unchanged and still keeps nothing.
  - `PlayingState.text_cache`: made with the HUD, and replaced in
    `on_display_changed`, so a re-opened display gets fonts at its scale.
  - `ui/keycap.py`:
    - `draw_keycap(..., cache=None)`. The label comes from the cache when
      one is given.
    - The font is built only when there is text to render. An arrow or the
      mouse glyph used to build a font it never used, which was four of
      the Attack hint's six per frame.
    - What a cap writes (`_words`), where it goes (`_face`) and how it is
      rendered (`_text`) are now shared by `draw_keycap` and a new
      `footprint`, which returns everything the cap paints. That is the
      frame, grown to take in a written label that runs past it.
  - `game/states/playing/visual/hints.py`:
    - The words and the caps' labels come from the run's cache.
    - A fading stage draws into a buffer covering the block's footprint
      (`extent`), not a new full-screen alpha surface each frame (about
      11 MB at 2560 x 1080).
    - `draw` returns that footprint.
  - `key_marker.py` passes the run's cache for the interact cap.
  - **Also the pause menu.** Its Controls block (`ui/controls_block.py`)
    drew 13 keycaps every paused frame, and each built a font (8 of them
    to render a label). `PausedState` now holds a `TextCache`, made in
    `_build_fonts` (on enter and on a display change), and
    `controls_block.draw` takes `cache=`. It is outside the run's draw,
    but it is the same fix, and the menu is open during play.
- **Fonts built per warm frame** (`scratchpad/font_sweep.py` and
  `pause_sweep.py`, seed 1234, the pause count run in both trees):

  | Scene | Before | After |
  |---|---|---|
  | Move hint | 5 | 0 |
  | Move hint fading | 5 | 0 |
  | Attack hint | 6 | 0 |
  | No hints | 0 | 0 |
  | Interact cap | 1 | 0 |
  | Pause menu, hints dismissed or up | 13 | 0 |

  The pause menu's count is the same with the Move hint up, so the
  frozen run under it is not redrawn while paused.
- **The cold critic caught a clip.**
  - The first version sized the fade buffer from the caps' frames and
    said everything a cap paints lies inside its frame. That is false for
    the mouse cap without the cursor art: it writes `CLICK` (49 px at
    18 px bold) on a 32 px square cap.
  - The fading Attack hint then lost the word's left edge. The critic
    measured 42 to 115 changed pixels at render scales 0.75 to 1.5, on
    the documented degrade path.
  - My identity check had not covered that path, so its "no pixel
    changes" was not supported as first written.
  - Fixed with `keycap.footprint`, and pinned by the tests below. The
    critic's other points were fixed too:
    - the false `extent` docstring;
    - a fade test that could not see the clip;
    - a misleading comment;
    - the font roles bound at import time.
  - A second finding came from the suite, not the critic: the refactor
    looked the cursor glyph up twice per mouse cap, which
    `test_controls_block` pins to once. The lookup now happens once.
- **Pixels do not change.** This was checked against the real `HEAD`
  modules, loaded side by side (`scratchpad/identity.py`), in 570
  comparisons with none differing:
  - 534 at render scale 1.0 and 1.2: caps in every label kind, colour,
    state and two sizes, with art and without, each through a cold and a
    warm cache; the Move hint, with a key held, and the Attack hint; and
    the fade at five points.
  - 36 on the critic's path: no cursor glyph, with and without keycap art,
    at scales 1.0, 1.2 and 1.5, with the Attack hint steady and fading at
    three points, plus the lone mouse cap.
  - Two negative controls (alpha one step apart, a key held on one side
    only) were both flagged, so the comparison sees a real difference.
  - In the suite, the uncached path is the oracle: a cached cap against an
    uncached one, and the block-sized fade against the whole-screen fade
    drawn the old way.
- **Tests:**
  - `tests/screens/test_text_cache.py` (14 tests, `unit`) pins:
    - a font is built once per role, size and weight, and again at another
      render scale;
    - an unknown role is refused;
    - rendered and shadowed text is kept and equals a fresh render, and
      the shadow follows the scale;
    - the store is bounded;
    - a cached cap is pixel-identical to an uncached one, cold and warm, in
      every label kind, colour, state and size, with and without art;
    - a warm cache builds nothing;
    - arrows and the mouse build no font even uncached;
    - a given font still wins;
    - everything `draw_keycap` paints lies inside `footprint`, over every
      label kind, colour, state, size, art and glyph case at scales 1.0
      and 1.5 (448 subtests);
    - the mouse word really is wider than its square cap.
  - `tests/playing/test_frame_fonts.py` (11 tests, `integration`, seed
    1234) pins:
    - a whole `PlayingState.draw` builds no font in a warm frame with the
      Move hint, a held key, a fading stage, the Attack hint, the interact
      cap, and all at once;
    - the control: with the cache replaced, the same frame builds fonts;
    - a warm paused frame builds none;
    - a display re-opened at 1.2 gets a new cache whose first frame builds
      the fonts at 22 px (18 × 1.2), nothing at the old size, and whose
      second frame builds none;
    - the fade is pixel-identical to the whole-screen one, and everything
      painted lies inside the rect `draw` returns. This covers both stages
      at scales 1.0 and 1.5, with the art as shipped, without the cursor
      glyph and without keycap art;
    - the mouse cap without its glyph really does paint past its frame.
  - **Mutation check** (`scratchpad/mutate3.py`): each pre-fix behaviour
    was put back in turn, and all ten were caught:

    | Behaviour put back | Tests failed |
    |---|---|
    | the hint word built from a new font every frame | 6 |
    | the hint caps drawn without the cache | 5 |
    | the fade block measured from the cap frames only (the critic's clip) | 62 |
    | the interact cap drawn without the cache | 2 |
    | the fade buffer drawn without the block offset | 36 |
    | the cache kept across a display re-open | 1 |
    | the font built before the label is known | 10 |
    | the font key without the render scale | 2 |
    | the text key without the render scale | 1 |
    | the pause menu's caps drawn without the cache | 1 |

  - **Suites:**
    - After the critic's fixes, `tests/playing`, `tests/render`,
      `tests/screens` and `tests/devtools` gave 1,422 passed and 1 failed
      (1,074 subtests) in 9 min 49 s. The failure was the double glyph
      lookup above.
    - After fixing that, the tests of every keycap caller passed, 112
      (612 subtests): `test_controls_block`, `test_keycap`,
      `test_text_cache`, `test_frame_fonts`, `test_run_hints`,
      `test_key_marker` and `test_pause`. The identity check and the
      mutation check were re-run on the final code.
- **Measured** on the Windows renderer, 2560 × 1080, 100 packed, seed 35,
  240 frames, on the final code. Before (`HEAD`, from `git archive`) and
  after (this tree) were run in two alternating rounds in one sitting. The
  CPU load swung between 9 and 59 % from other programs, so each round
  is read pairwise:

  | Round | Before, hints on | Before, hints off | After, hints on | After, hints off |
  |---|---|---|---|---|
  | 1 | 22.49 ms | 8.63 ms | 8.65 ms | 10.66 ms |
  | 2 | 29.58 ms | 11.10 ms | 11.16 ms | 9.51 ms |

  - The two hints-off runs in a round do the same work, yet differ by
    2.03 and 1.59 ms. That is this sitting's noise.
  - With the hints on, the new code lands 0.02 and 0.06 ms from the
    hints-off run beside it, and within the noise of the other. Before,
    the hints cost 13.86 and 18.48 ms of draw p50.
  - An earlier sitting at 65 to 91 % load, on the code before the
    critic's fixes, gave the same shape: hints on 0.22 and 0.57 ms above
    hints off, where before they cost 23.27 and 19.97 ms.
  - Target (within 1 ms of hints off): **met**, within the resolution this
    machine gives.
- **Found and handed off:** `tests/playing/test_run_hints.py` and
  `test_key_marker.py` boot a `Game` and a seeded run but are not
  registered in `tests/conftest.py`, so they run in the every-save `unit`
  tier. That is outside RND-008. It was raised as a separate task, which
  the owner started in its own session.

### RND-008.4: the elemental draw

- **What changed:**
  - `elements.bands(run)` sorts the bodies in view and the aura motes onto
    their terraces once a frame. `scene.draw_world` calls it before the
    terrace loop and passes it down through `draw_flat_effects` to
    `draw_under`, which hands each pass its terrace's list.
    - Before, each terrace's pass filtered the whole field with
      `transient.off_band`: every body in view twice (the aura and status
      passes) and every mote once. That was about 820 terrain lookups a
      frame in the harness's packed, primed fight (164,557 calls over 200
      profiled frames).
    - Nothing is kept between frames, so the display re-open's off-screen
      warm-up draw, which skips `begin_frame`, cannot see a stale sort.
  - `layers.in_band` is the filter the passes used to run, in one place.
    `draw_auras` and `draw_statuses` take the band's `bodies`, or filter
    for themselves when called without them (the tests, `level=None`).
    `VIEW_PAD` (140) replaces the two copies of the pad.
  - `ParticleSystem.layer` and `draw(..., only=)`: a terrace draws its own
    motes instead of testing the whole pool.
  - `layers._scaled`: the burn flame's `smoothscale` is kept per source
    surface and size. It is deterministic, so the copy is the same picture.
    The source is held in the entry, as `washed` does, so a recycled id
    cannot be served another surface's copy.
  - `DamageNumbers._plain`: a weapon's plain numbers are rendered once per
    font, text and colour, like the outlined ones already were. The alpha
    is set on the shared glyph right before each blit.
- **The order is gameplay.** `layers._shed` draws on `run.rng` once per
  aura drawn, so the sort keeps `_bodies` order (boss first, then the
  enemy list) inside each terrace, and the terraces are painted in the
  same order.
  - The one thing that adds a mote during the loop is that shed. It bursts
    at the body's own position, whose terrace has already drawn its motes,
    so the mote waits for the next frame on either path. `layers._shed` is
    the only `under=True` emitter in the code.
- **Dropped: caching the status marks' shapes.** `_shape` computes its
  polygon from absolute screen position, then makes it relative. A cached
  copy built at the origin differed by an edge pixel in 31 of 60,000
  random positions (`scratchpad/shape_float.py`), so it would break the
  pixel-identity rubric for about 0.3 ms. Reusing a scratch surface
  instead of allocating one buys nothing either: allocating is as cheap as
  clearing (0.27 against 0.25 µs at 24 px, 2.33 against 2.11 µs at 200 px).
- **Pixels and the game do not change.**
  - `scratchpad/frame_identity.py` fingerprinted 150 consecutive frames of
    the harness's primed fight, update and draw, in `HEAD` and in this tree.
    Each frame recorded its pixels, the run's RNG, the global RNG, and the
    particle, number and aura counts. All 150 were equal on every field.
  - The fingerprint needs the terrain renderer's clock pinned
    (`renderer.clock`). Left on the wall clock, the same tree fingerprinted
    differently in two processes (8 of 150 frames equal), which a first
    comparison mistook for a change.
  - The cold critic repeated the check on its own probe (seeded RNGs,
    `PYTHONHASHSEED=0`, jittered frames): the chained hash matched.
- **Tests:** `tests/render/test_elemental_draw_cost.py`, 13 tests. The
  fight class boots the harness on seed 35 (`integration`); the cache
  classes boot nothing (`unit`). They pin:
  - the fixture covers what the sort must get right: bodies on all three
    terraces, the boss first in its terrace, and a bumblebee hovering
    where the floor under it is not the top of the terrain (the actor pass
    bands a flyer by the top, the elemental passes by the floor);
  - a pass picks exactly what the old per-pass filter picked, written out
    in the test as the oracle, with a body moved out of view (an
    off-screen aura draws nothing but would still shed);
  - each terrace's bodies and motes are exactly what its own pass picks,
    in the same order;
  - the auras shed in the same body order, sorted or not;
  - a frame sorts once (`in_band` called with `None` only), not once per
    terrace;
  - a whole frame is the same picture sorted and unsorted, and stable;
  - the burn mark scales its flame once over two draws, to the same pixels
    as a fresh scale;
  - the kept flame is never served for another surface, and its store is
    bounded;
  - kept number glyphs draw what fresh renders draw, cold and warm, as the
    alphas fall, with two numbers sharing a glyph at different alphas;
  - a glyph is rendered once.
  - `tests/render/test_element_layers.py`: its trace helper forwards the
    new `bands` keyword.
  - **Mutation check** (`scratchpad/mutate4.py`): all seven were caught.

    | Behaviour put back or broken | Tests failed |
    |---|---|
    | the passes filter their own terrace again (the sort ignored) | 1 |
    | the bodies sorted out of order | 6 |
    | a terrace's motes lost | 3 |
    | the bodies sorted without the view | 2 |
    | the burn mark scaling its flame afresh every draw | 1 |
    | a kept flame served for another surface | 1 |
    | a shared glyph taking a number's alpha only the first time | 3 |

  - Suites: `tests/render` + `tests/playing` 797 passed (412 subtests)
    before the critic's fixes, and 798 passed (415 subtests) in 6 min 1 s
    on the final code. The 150-frame fingerprint was re-run on the final
    code too: equal to `HEAD` on every frame.
- **The cold critic** returned FAIL on coverage, not on correctness. It
  confirmed the identity with `HEAD` on its own probe and found no path
  where the sort differs from the per-pass filters. Fixed:
  - the burn cache had no test of its wiring (reverting `_burn_mark` to a
    per-call `smoothscale` passed every test);
  - the fixture stood on two terraces, not three, with no boss and no
    flyer;
  - this journal still planned the shape cache without saying it was
    dropped;
  - the sort ran even in a run with no elemental visuals;
  - a docstring miscounted the old lookups;
  - `_plain` used another cache's cap.
- **Measured.** Windows renderer, 2560 × 1080, 100 packed, seed 35, 240
  frames, `HEAD` (the RND-008.3 commit) and this tree alternating in one
  sitting, CPU load 7 to 32 %.

  Harness draw p50:

  | Round | Before, plain | Before, infused | After, plain | After, infused |
  |---|---|---|---|---|
  | 1 | 7.84 ms | 11.21 ms | 7.83 ms | 10.47 ms |
  | 2 | 7.81 ms | 10.86 ms | 7.68 ms | 11.07 ms |

  Per part (`scratchpad/sections.py`, light `perf_counter` wrappers, mean
  of 240 frames, the same two rounds):

  | Part, infused fight | Before | After |
  |---|---|---|
  | `draw_under`, three terraces (after includes the 0.09 ms sort) | 1.95 / 1.94 ms | 1.44 / 1.47 ms |
  | status marks | 0.74 / 0.75 ms | 0.45 / 0.46 ms |
  | auras | 0.70 / 0.70 ms | 0.51 / 0.52 ms |
  | aura motes | 0.16 / 0.16 ms | 0.05 / 0.05 ms |
  | damage numbers | 0.37 / 0.37 ms | 0.35 / 0.35 ms |
  | whole draw | 11.02 / 11.07 ms | 10.40 / 10.53 ms |
  | whole draw, plain pack | 8.44 / 8.24 ms | 8.49 / 8.13 ms |
  | terrain ground bands, plain pack (untouched) | 3.42 ms | 3.37 ms |
  | `draw_under`, plain pack (after includes the sort) | 0.41 / 0.41 ms | 0.13 / 0.12 ms |

  - **Outcome missed.** By the whole-draw means, the infused-minus-plain
    gap went from 2.58 / 2.83 ms to 1.91 / 2.40 ms, about −20 % against a
    target of −50 %. The saving is real and stable: about 0.5 ms off the
    elemental draw and 0.3 ms off the plain one, which the gap metric
    does not show.
  - **Why the target was wrong.** The 5.77 ms baseline gap was taken
    under heavy CPU load. The plan's hot spots came from cProfile, whose
    per-call overhead inflates exactly the Python-heavy filtering this
    removed. On a quieter machine the gap is about 2.5 to 3 ms.
  - Measured by part, what remains of it (infused minus plain) is:
    - the art that has to be drawn: aura sprites 0.5 ms, status marks and
      freeze blocks 0.45 ms, Wind areas 0.28 ms, jump arcs 0.2 ms;
    - the health bars of damaged enemies, 0.4 ms (already cached, so this
      is their blits);
    - the damage numbers, 0.35 ms;
    - the reaction bursts, 0.15 ms.
  - None of it is filtering any more. No pixel-identical change left in
    the elemental draw is worth more than about 0.2 ms. The next saving
    would have to draw less, which changes the picture, and that is the
    owner's call.
  - The larger costs in the frame lie elsewhere: the terrain's ground
    bands take 3.4 ms of a 10.5 ms draw, and update takes 8 to 10 ms at
    100 packed. That is RND-008.5's ground.

### RND-008.5: the update, and the bump pass

- **Measured by part** (`scratchpad/update_sections.py`, light
  `perf_counter` wrappers, 240 frames, master frozen, dummy driver). The
  harness gained `--jitter PX` (0: the hero stands still) so the hero's
  movement can be taken out.

  | Crowd, run | Update mean | Enemies | Bump | Navigation |
  |---|---|---|---|---|
  | 67, plain, jittered | 5.22 ms | 1.95 | 1.10 | 1.81 |
  | 66, plain, still | 4.84 ms | 2.02 | 1.24 | 1.22 |
  | 113, plain, jittered | 9.00 ms | 3.67 | 2.86 | 1.94 |
  | 112, plain, still | 8.52 ms | 3.81 | 3.04 | 1.16 |
  | 168, plain, jittered | 21.15 ms | 8.18 | 8.72 | 3.30 |
  | 167, plain, still | 15.06 ms | 6.47 | 6.60 | 1.26 |
  | 65, infused, jittered | 4.85 ms | 1.71 | 0.87 | 1.82 |
  | 61, infused, still | 4.47 ms | 1.91 | 0.96 | 1.15 |
  | 100, infused, jittered | 10.16 ms | 4.65 | 3.12 | 1.50 |
  | 112, infused, still | 6.91 ms | 3.06 | 2.14 | 1.15 |
  | 160, infused, jittered | 13.60 ms | 5.65 | 5.24 | 1.91 |
  | 166, infused, still | 13.49 ms | 5.66 | 5.74 | 1.21 |

  - The crowd is the count at the end of timing: summons still arrive
    through a frozen master.
  - Everything else in the update (combat, weapons, particles, numbers,
    spawning, buffs, hazards) was under 0.3 ms together in every run.
  - **Jitter costs navigation 0.6 to 2 ms**, as the first report said: a
    hero moved every frame re-aims the flow field every frame.
  - **The decision (plan item):** bump grows fastest with the crowd. It is
    the largest single item at about 165 and second to the enemies' own
    update below that, so the plan's condition for the cheap wins held.
- **What changed** (`game/states/playing/core/physics.py`):
  - `resolve` drops a pair that does not touch on two float products,
    before any tuple, set or `Vector2`. `_bump` did nothing with such a
    pair (no shove, no frozen contact), so skipping it changes nothing.
  - The pairs that touch go through the same code, in the same order and
    the same way round. This matters because `apply_knockback` sums floats
    into `_knock`, and a float sum depends on its order.
  - The drop keeps a margin of a billionth inside `_bump`'s own limits
    (`_MARGIN_OUT`, `_COINCIDENT`), so the two can never disagree about a
    pair that matters.
  - The broad-phase pad is now the largest living collider, never more
    than the old 72 px (`_pad`):
    - A smaller search covers a sub-block of the same grid cells, in the
      same order, and still reaches every body that can touch.
    - The cap keeps a body bigger than 72 px found exactly as before.
    - With 96 px cells and colliders of 9 to 26 px (bosses 40 and 46), it
      saves the troll's 5 × 5-cell searches. The early drop is most of the
      gain.
- **Bit for bit the same.** The oracle is the old pass, copied verbatim
  into `tests/playing/test_bump_exact.py`. Every `_knock` is compared with
  `==`, as is every frozen-contact exchange and death, in order:
  - 400 random crowds: radii from 9 to 26, weights from 0.5 to 4, a few
    dead bodies, a 46 px boss, a collider bigger than the old pad, bodies
    stacked exactly on each other, and pairs exactly touching;
  - 240 more crowds where frozen contact kills `a` or `b` on every second
    or third exchange: the one state that changes inside a pass;
  - the pad's edge cases, built on purpose:
    - a giant across a cell edge from a small body (an uncapped pad meets
      it from the other side);
    - a troll against the giant (a pad well short misses it);
    - two r 48.25 bodies on the one-cell to two-cell boundary (a pad even
      one px short never meets them);
  - a pair just past `_bump`'s coincident limit;
  - seed 35's harness fight, packed and primed round the hero with the
    boss in it, compared on each of 40 frames as it plays.
  - The dev check (`scratchpad/frames5.sh`, 150 frames of the primed fight
    fingerprinted in `HEAD` and this tree) was equal on every frame for
    pixels, the run's RNG, the global RNG, and the particle, number and
    aura counts.
- **Tests:**
  - `tests/playing/test_bump_exact.py`: 6 tests, 683 subtests. The fight
    class boots a run (`integration`); the crowds boot nothing (`unit`,
    about 1 s). A mismatch reports its first differing knock, exchange or
    death: printing the full diff of hundreds of failing subtests had
    taken minutes.
  - `tests/playing/test_bump.py` (19) unchanged and green.
  - Suites on the final code: `tests/playing` + `tests/devtools` +
    `tests/flows` (which holds the run-determinism checks) 545 passed
    (756 subtests) in 9 min 13 s.
- **Rebased onto TST-006 and TST-007** (merged to `main` meanwhile).
  - Two conflicts, both from additions on both sides: the index's next
    free IDs (RND-009 and TST-008 kept) and `tests/conftest.py`'s
    integration list (both lists kept).
  - TST-006's tier audit (`tools/verification/tier_audit.py`) then
    flagged `FlagPlumbingTests` as needing `integration`. It reads the
    calls statically, and cannot see that the tests replaced `build` with
    a mock.
  - Rather than list fast, pure tests as `integration`, the harness's
    `main` was split: `parse(argv)` (the flags and their refusals) and
    `build_options(args)` (what reaches `build`) are pure, and the flag
    tests use them.
  - The check that `--jitter` reaches the warm-up and the timed frames,
    which needs a real run, moved to the booted `CommandLineTests`.
  - The swapped-flags mutation and both jitter mutations are still caught.
  - **Whole default suite on the rebased branch:** 3,533 passed (2,534
    subtests), 0 failed, in 19 min 49 s. The 11 `sweep` tests are
    deselected, as always; they run in RND-008.8.
  - `tests/devtools/test_spawn_stress.py`: `--jitter` reaches the warm-up
    and the timed frames, and a negative or `nan` jitter is refused.
  - **Mutation check** (`scratchpad/mutate5.py`): all eleven caught, each
    in 2 to 6 s:

    | Behaviour broken | Tests failed |
    |---|---|
    | the pad no longer capped at 72 px | 1 |
    | the pad halved | 2 |
    | the pad one px short (the cell-count boundary) | 1 |
    | pairs no longer deduplicated | 586 |
    | a pair shoved the other way round | 597 |
    | the candidates taken in another order | 468 |
    | the early drop cutting pairs that touch | 513 |
    | the coincident margin on the wrong side | 1 |
    | a dead body met as the second of a pair | 432 |
    | `--jitter` dropped from the warm-up | 3 |
    | `--jitter` dropped from the timed frames | 3 |

- **The cold critic** returned FAIL on the tests, not on the physics. Its
  own probe of 4,000 random worlds found no input where the new pass
  differs: 12,000 comparisons, 1,335,462 exchanges, with kills,
  coordinates down to −100,000, bodies on cell edges, radii of 0 and
  1e-300, and giants of 73 to 150 px. Its findings, all fixed:
  - the `--jitter` test stopped at the warm-up and never reached the timed
    frames;
  - nothing killed a body in the middle of a pass;
  - the pad's cell-count boundary was not pinned (a pad one px short
    passed);
  - the coincident margin was not pinned;
  - the new pass read the size and position of dead bodies, which the old
    one never did. The alive check is back ahead of the distance, and the
    pad counts only the living;
  - `--jitter nan` passed the guard.
- **Measured.** `HEAD` (the RND-008.4 commit) and this tree, back to back,
  final code.

  Bump alone (`--pack --bump`, 400 passes, two rounds):

  | Crowd | Before p50 | After p50 |
  |---|---|---|
  | 58 | 0.78 / 0.43 ms | 0.26 / 0.34 ms |
  | 95 | 1.95 / 1.08 ms | 0.64 / 0.66 ms |
  | 144 | 2.75 / 2.70 ms | 1.38 / 1.38 ms |

  The whole update (`update_sections.py`, plain pack):

  | Crowd, hero | Before p50 | After p50 | Bump before → after |
  |---|---|---|---|
  | 113, jittered | 5.88 ms | 5.21 ms | 1.90 → 1.03 ms |
  | 112, still | 5.33 ms | 4.51 ms | 2.00 → 1.17 ms |
  | 168, jittered | 9.63 ms | 7.66 ms | 3.89 → 1.90 ms |
  | 167, still | 8.90 ms | 6.66 ms | 3.90 → 1.89 ms |

  - Bump halves at 144 (the plan's measure) and in every update run. The
    update is 0.7 to 2.2 ms faster.
  - The update's other parts in the after runs: the enemies' own update
    2.37 / 2.64 ms at 113 / 112 and 3.77 / 3.77 ms at 168 / 167;
    navigation 1.37 / 0.92 ms at 113 / 112 (jittered / still) and
    1.82 / 0.78 ms at 168 / 167.
  - An earlier sitting under heavier load, with the first version of the
    change, gave the same shape: bump at 144 5.31 / 5.25 → 2.41 / 2.40 ms,
    and update at 112 still 6.31 → 4.35 ms.
  - The machine's load differed between the sittings, so each table is
    read only against itself.
- **What is left in the update.** The enemies' own update (2.4 to 3.8 ms at
  110 to 170) is now the largest item, then bump and navigation. The
  first findings report put the per-enemy cost in the movement probe.
  That is the next lever, and it is not in this plan (see RND-008.7).

### RND-008.7: the results in one place, and what is left

Each task measured its own before and after, back to back against the
commit before it, on the machine as it was that hour. The load varied
between sittings, so each row is read only against itself. RND-008.8
measures the whole branch against the RND-008.1 base in one sitting.

| Task | What moved | Before | After | Target | Met |
|---|---|---|---|---|---|
| RND-008.2 | the harness measures play: hints dismissed, director frozen, one budget | the report's 131 live, draw 27.07 ms (hints on) | 95 → 113 live (summons only), draw 10.22 ms (hints off) | the report's numbers reproduce under the old flags | yes (131 live, 27.07 against 27.21 ms) |
| RND-008.3 | draw p50 with the opening hints up, 100 packed, 2560 × 1080 | 13.86 / 18.48 ms over hints off | 0.02 / 0.06 ms over the run beside it | within 1 ms of hints off | **yes** |
| RND-008.3 | fonts built per warm frame (Move, fade, Attack, interact, pause) | 5 / 5 / 6 / 1 / 13 | 0 / 0 / 0 / 0 / 0 | 0 | **yes** |
| RND-008.4 | elemental `draw_under`, infused fight (plain in brackets) | 1.95 ms (0.41) | 1.44 ms (0.13) | the infused-minus-plain gap halved | **no: about −20 %**, accepted (D7) |
| RND-008.5 | bump p50, 144 packed | 2.75 / 2.70 ms | 1.38 / 1.38 ms | lower, bit for bit the same | **yes**, and bit for bit |
| RND-008.5 | update p50, 112 to 168 packed | 5.33 to 9.63 ms | 4.51 to 7.66 ms | recorded with the bump decision | 0.7 to 2.2 ms faster |

Nothing changed a pixel or the game. RND-008.3 and .4 were
fingerprinted against the code before them (570 cap and hint comparisons,
and 150 frames of a primed fight). RND-008.5 compared every knockback,
frozen exchange and death with the old pass, bit for bit, and the
150-frame fingerprint matched there too.

**The frame after RND-008,** by the numbers taken above. Harness, 100
packed, 2560 × 1080, hints dismissed:
- **Draw:** 8.1 to 8.5 ms in RND-008.4's quiet sitting (10.22 ms under
  RND-008.2's load). The terrain's ground bands take 3.4 ms of it. The
  elemental fight adds 1.9 to 2.4 ms, which is art that has to be drawn.
- **Update:** about 4.5 ms with the hero still, 5.2 ms jittered. The
  enemies' own update is about 2.5 ms of it, bump about 1 ms, and
  navigation 0.9 to 1.4 ms.
- **Combined:** at 100 packed that is inside the 16.67 ms budget. At 150
  to 170 packed the update alone is 6.7 to 7.7 ms, and a crowded
  infused fight is at or over budget. *Corrected by RND-008.8:* this
  added up parts measured in different sittings and drivers, and was
  wrong. Measured end to end on the Windows renderer, 100 packed takes
  18.4 to 19.1 ms of update and draw (p50), still over budget.
- RND-008.8 measures this directly instead of adding it up.

**What is left.** Found on the way, outside RND-008's plan. Each would be
its own requirement:
1. **The enemies' own update** is now the largest item in the update:
   2.4 to 3.8 ms at 110 to 170 packed. The first report put the
   per-enemy cost in the movement probe.
2. **The terrain's ground bands** take 3.4 ms of an 8 to 10 ms draw. Resolution
   is not a lever (D4); the cost has to be found in how the bands are
   drawn.
3. **Navigation with a moving hero** costs 0.6 to 2 ms more than with a
   still one: the flow field is re-aimed as the hero moves.
4. **The elemental art** (aura sprites 0.5 ms, status marks 0.45, Wind
   areas 0.28, damage numbers 0.35 in a primed fight). Any further saving
   draws less, so it changes the picture; the owner's call (D7).
5. **The weapon loop** (D6): not re-measured; every measured cost was
   larger.
6. **A frame is not a function of the run alone.** The terrain animates
   on the wall clock (`world/terrain/render.py` `seconds`, unless handed a
   `clock`). Two processes then draw the same frame differently, which a
   pixel test across processes has to pin (RND-008.4's fingerprint did).
7. **The in-game debug overlay's render time includes the vsync wait**
   (`game/game.py` `_step` times `display.flip()`), so it is not
   comparable with the harness's draw figure.
8. **The update costs more in the real loop than headless** (found in
   RND-008.8): 8.5 ms at 113 packed with the Windows renderer drawing
   between updates, against 5.2 ms on the dummy driver. The cause was not
   isolated. *Not confirmed (ENT-018.4):* timed four
   ways in one sitting (Windows or dummy driver, drawing between updates or
   not), the update shows no consistent difference. The gap was the
   machine's load between the sittings (`enemy_update_journal.md`).
- Also found, and handed off during RND-008.3: run-booting tests sitting in
  the `unit` tier. The owner ran it as TST-006, now merged. Its tier audit
  shaped the harness's flag tests (RND-008.5).

### RND-008.8: the full test (D7)

The frozen rubric, written before measuring:
1. The whole suite, `sweep` included, has no failure.
2. In one sitting, alternating base and branch, no workload is slower:
   plain pack with hints off and on, infused with hints off, bump alone
   at about 144, and loading.
3. On the branch, hints on draws within noise of hints off.
4. RND-008.4 re-checked: the infused-minus-plain draw gap is lower on the
   branch, reported as a percentage.
5. The whole frame at 100 packed is stated against the budget.

- **The base** is `origin/main` (TST-006 and TST-007 on top of
  `5176c0c`). Its game code is byte-identical to where RND-008 started
  (`git diff 5176c0c origin/main` over the game's packages is empty).
- **The workloads.** The base harness has none of RND-008.2's flags, so
  `scratchpad/final8.py` builds each workload the same way in both trees:
  - seed 35, 100 packed round the hero;
  - the master frozen with its in-flight company dropped;
  - the hints dismissed or kept (forced on if the saved Options have them
    off);
  - 60 warm-up frames, then 240 timed frames of update and draw, jittered
    as the harness does;
  - Windows renderer, 2560 × 1080.

  Bump alone is `bump8.py`: the packed crowd, nothing moving, the impulses
  put back after each pass. Loading is `load_time.py`, loading screen to
  the first frame. Two rounds, base then branch, with the CPU load logged
  before each run (11 to 71 %).
- **Results** (p50; `scratchpad/final8_numbers.py` computes the
  differences):

  | Workload | Base, round 1 / 2 | Branch, round 1 / 2 | Change |
  |---|---|---|---|
  | plain, hints off: update | 9.65 / 9.48 ms | 8.54 / 8.57 ms | −1.11 / −0.91 ms |
  | plain, hints off: draw | 10.95 / 11.00 ms | 10.32 / 10.50 ms | −0.63 / −0.50 ms |
  | plain, hints off: update + draw | 20.56 / 20.57 ms | 18.40 / 19.11 ms | −10.5 / −7.1 % |
  | plain, hints on: draw | 31.76 / 30.80 ms | 10.43 / 10.44 ms | −21.33 / −20.36 ms |
  | plain, hints on: update + draw | 41.52 / 40.33 ms | 18.41 / 18.18 ms | −55.7 / −54.9 % |
  | infused, hints off: update | 8.80 / 8.98 ms | 7.59 / 7.89 ms | −1.21 / −1.09 ms |
  | infused, hints off: draw | 15.48 / 15.51 ms | 14.40 / 14.86 ms | −1.08 / −0.65 ms |
  | infused, hints off: update + draw | 24.29 / 24.50 ms | 22.14 / 22.83 ms | −8.9 / −6.8 % |
  | bump alone, 144 packed | 4.57 / 4.54 ms | 1.91 / 2.39 ms | −58.1 / −47.3 % |
  | loading to the first frame | 2.93 / 3.00 s | 2.92 / 2.87 s | none |
  | the first frame after loading | 22.9 / 21.8 ms | 4.6 / 5.0 ms | −18.3 / −16.8 ms |

  Frames over 16.67 ms, update + draw, of 240: plain hints off 204 / 217
  → 170 / 174; plain hints on 240 / 240 → 174 / 157; infused 240 / 238
  → 232 / 239.
- **Against the rubric:**
  1. **The whole suite with `sweep`:** 3,544 passed (2,534 subtests), 0 failed, 0 deselected, in 25 min 22 s: the 3,533 of the default suite and the 11 `sweep` tests. **Met.**
  2. **Nothing is slower:** every workload is faster in both rounds.
     Loading is unchanged. The first frame after loading is 17 to 18 ms
     faster, because the opening hints no longer build their fonts on it
     (RND-008.3). **Met.**
  3. **Hints on against hints off, branch:** +0.11 / −0.06 ms of draw (the
     base: +20.81 / +19.80 ms). **Met.**
  4. **RND-008.4 re-checked:** the infused-minus-plain draw gap went from
     4.53 / 4.51 ms to 4.08 / 4.36 ms, **−9.9 / −3.3 %**.
     - That is lower, as the rubric asks, but short of the −20 % accepted
       in D7, which came from RND-008.4's part-by-part means.
     - Measured here by the whole draw's p50, the elemental fight's draw
       is 0.65 to 1.08 ms faster, and the plain draw is also 0.50 to
       0.63 ms faster from the same change. The gap subtracts the second
       from the first, so it shows less than either.
     - What the owner accepted as −20 % reads as −3 to −10 % in the gap
       measured this way, or as −0.65 to −1.08 ms of the elemental
       fight's draw. **Reported to the owner.**
  5. **The whole frame at 100 packed:** 18.40 / 19.11 ms (p50) with hints
     off, against 20.56 / 20.57 on the base. **Still over the 16.67 ms
     budget**, 170 / 174 frames of 240.
     - With the opening hints up it is 18.41 / 18.18 against 41.52 /
       40.33: the largest win, felt in the first seconds of every run.
     - RND-008.7's statement that 100 packed fits the budget was wrong,
       and is marked corrected there.
- **Found here, and added to what is left:** with the Windows renderer
  drawing between updates, the update measures 8.5 ms at 113 packed,
  against 5.2 ms in RND-008.5's dummy-driver runs of the same crowd. The
  cause was not isolated. The draw may evict the update's data from the
  caches between frames, but that is a guess, not a measurement. It
  matters because the update budget is spent in the real loop, not the
  headless one.

## RND-008: Method

**Timings are only compared within one sitting.** On 2026-09-28 the same
code ran 20 to 60 % slower when other programs loaded the CPU, with the
crowd identical. So every before-and-after in this journal is taken back
to back, and the display line and a note of the machine's load go with
it.

Every run: seed 35, `--dormant 0`, a 60-frame warm-up, then 240 timed
frames. Windows runs set `SDL_VIDEODRIVER=windows` and opened the saved
2560 × 1080 window. `save.json` was byte-identical before and after.

- Report reproduction:
  `SDL_VIDEODRIVER=windows python -m tools.benchmarks.spawn_stress --render --frames 240 --dormant 0 --live 60 --pack`,
  then `--live 100 --pack` and `--live 100 --pack --elements`.
- The render-scale, hints-off, profile and bump numbers came from four
  scratch probes built on the harness's own `build` / `infuse` /
  `cascade_setup` / `run`. Each set `config.RENDER_MAX_HEIGHT` before the
  display opened, called `ps.hints.dismiss()` where the table says "off",
  and wrapped `ps.draw` or `ps.bump.resolve` in `time.perf_counter` or
  cProfile. RND-008.2 moves what they did into the harness's own flags, so
  every number here can be re-taken from the repo, except the
  render-height runs, which D4 retires.

---

## Appendix: the report as reviewed

Copied verbatim from the untracked `GAMEPLAY_PERFORMANCE_FINDINGS.md` in
the shared checkout on 2026-09-28, with its headings moved down two
levels. Read it with the "Confirmed reading" above: its draw figures
include the tutorial hints.

### Gameplay Performance Findings

#### Summary

The largest measured cost is rendering at the tested 2560x1080 native surface. In Windows SDL stress runs, draw time alone exceeded the game's 62 FPS frame budget (about 16.13 ms) at both 60 and 100 requested packed enemies. Enemy updates and crowd separation add measurable cost as populations grow. Three standard weapon slots were a smaller update cost than enemy count and rendering in the tested workload.

These are stress measurements, not typical-play averages. Desktop benchmark counts drifted because the spawn master's frozen state does not stop committed arrivals or enemy summons. The benchmark measures drawing before `display.flip()`, so it does not include presentation or vsync wait.

#### Measured Results

##### Windows SDL renderer

Preflight reported SDL driver `windows`, vsync enabled, scaled-window support enabled, and a 2560x1080 display surface. Each stress run measured 240 frames. Timings are milliseconds.

| Stress workload | Live at end | Visible p50 | Update p50 / p90 / p99 | Draw p50 / p90 / p99 | Update + draw p50 / p90 / p99 | Frames over 16.7 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 60 requested, packed, no elemental load | 79 | 64 | 5.76 / 6.84 / 8.21 | 24.77 / 27.04 / 39.65 | 30.40 / 33.34 / 44.76 | 240 / 240 |
| 100 requested, packed, no elemental load | 131 | 103 | 8.98 / 10.73 / 12.36 | 27.21 / 30.51 / 41.70 | 36.35 / 40.09 / 50.68 | 240 / 240 |
| 100 requested, packed, three infused weapons | 119 | 102 | 9.78 / 11.31 / 14.64 | 33.61 / 38.60 / 57.01 | 43.41 / 48.12 / 66.61 | 240 / 240 |

The first two cases show that drawing the high-resolution scene is already over budget without elemental effects. The infused case is slower, but its population differs, so it is not a clean measurement of elemental rendering overhead on the Windows renderer.

##### Enemy and bump scaling

An isolated bump test held enemy positions fixed, moved the hero out of range, and disabled frozen-contact callbacks. It measured the grid rebuild and enemy-enemy bump pass only.

| Requested / seated packed enemies | Bump p50 / p90 / p99 |
| --- | ---: |
| 20 / 20 | 0.124 / 0.145 / 0.184 ms |
| 60 / 60 | 0.870 / 0.967 / 1.072 ms |
| 100 / 100 | 2.065 / 2.347 / 2.918 ms |
| 150 / 150 | 4.562 / 5.059 / 5.734 ms |
| 200 requested / 175 seated | 5.563 / 6.289 / 7.120 ms |

The 175-enemy sample had a 36.081 ms maximum outlier; its median and p90 better represent the repeated pass. Seating stopped at 175 because the run's live cap prevented all 200 requested enemies from spawning. This packed, stationary test is intentionally harsher than ordinary spacing.

In update profiling at 60 enemies, `Enemy.update`, `BumpResolver.resolve`, and `NavCoordinator.update` were among the largest costs. The stress harness jitters the hero, which increases navigation rebuild activity; this biases its update cost upward compared with a stationary hero.

##### Weapon count

At 60 stable enemies over 300 frames, the standard weapon slot comparison was:

| Weapons | Update p50 / p90 / p99 | Damage dealt during sample |
| ---: | ---: | ---: |
| 1 | 4.76 / 5.79 / 7.47 ms | 421.6 |
| 2 | 5.12 / 6.36 / 7.25 ms | 1181.3 |
| 3 | 5.16 / 6.34 / 7.39 ms | 1788.8 |

In this workload, moving from one to three weapons changed update p50 by 0.40 ms. This does not cover every weapon type, summon slot, blessing combination, or projectile-heavy build, but it makes weapon slot count a lower priority than rendering and dense-crowd work based on current evidence.

#### Optimization Experiment

The elemental fallback ring renderer in `game/states/playing/visual/elements/layers.py` creates an alpha surface for each fallback ring draw. An in-memory bounded-cache prototype produced pixel-identical output for three representative inputs.

- A warmed batch of 100 rings improved p50 / p90 / p99 from 0.299 / 0.379 / 0.463 ms to 0.199 / 0.262 / 0.314 ms.
- In dummy-render whole-scene checks with 60 active aura rings, p50 improved from 14.013 to 12.929 ms, while p90 changed from 16.320 to 17.086 ms.
- With 100 active aura rings, p50 / p90 improved from 18.041 / 20.090 ms to 15.411 / 17.315 ms.
- The scene prototypes retained about 96-121 KB of cached surfaces; the separate 100-input microbenchmark retained about 510 KB.

The microbenchmark improvement is clear, but the scene-level result varied. These were dummy-render experiments, not Windows-renderer results. Keep the cache bounded and validate with paired real-render runs before treating it as a broad gameplay improvement.

#### Recommendations

1. **Measure lower render scales first.** Rendering is the largest measured cost, and even the no-element Windows runs exceed the frame budget in draw alone. Compare fixed logical surface sizes at identical scene load, then weigh performance against image sharpness before changing defaults.
2. **Evaluate aura caching on the real renderer.** Use identical visible enemy counts, aura states, resolution, and camera position. Compare p50/p90 draw time and check for pixel equivalence. The current prototype justifies this experiment, not an assumption that it will solve the overall budget miss.
3. **Measure bumping in a representative live scene.** The isolated dense-crowd cost reaches several milliseconds at 150-175 packed enemies. Confirm how often comparable crowds occur in play before redesigning neighbor queries or collision handling.
4. **Recheck update hotspots after controlling hero movement and population.** Navigation rebuilds and summon/spawn activity should be separated from the baseline enemy-update workload. Visible enemies update every frame, so off-screen LOD does not reduce the cost of a packed on-screen fight.
5. **Defer weapon-loop optimization unless a different workload identifies it.** The standard one-to-three slot comparison showed a relatively small median update increase; test projectile-heavy and summon-heavy builds separately if those are suspected bottlenecks.

#### Method and Caveats

- Gameplay stress runs used seed 35 and `tools/benchmarks/spawn_stress.py`; controlled variants warmed up before timing.
- Dummy SDL timings are useful for comparisons inside that environment, but they are not desktop GPU timings.
- Windows SDL draw timings use the actual scaled display surface, but stop before `display.flip()` and do not include vsync waiting.
- The stress harness can add enemies after setup through committed spawn arrivals and enemy summons. Report actual live and in-view counts rather than comparing only requested `--live` values.
- The measurements identify optimization targets; they do not establish player-session averages or performance on other display sizes and hardware.
