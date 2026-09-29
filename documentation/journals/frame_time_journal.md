# Gameplay frame time: journal

**ID:** RND-008 · **System:** rendering (+ SYS, ENT, CMB) · **Type:**
performance · **Status:** in progress (plan confirmed by the owner,
2026-09-28) ·
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
    within 1 ms of the hints-off figure (28.91 → about 11.5 ms). The
    hints' own cost drops from about 16 ms to under 1 ms.
- **RND-008.4: The elemental draw.**
  - Walk the bodies once per frame, bucket them by terrace level, and
    hand each band its bucket. Today each of the three band passes tests
    every body and particle with `off_band`.
  - Cache the `_shape` status marks per (shape, size, colour, alpha).
  - Cache plain damage-number glyphs, as the outlined ones already are.
  - Tests: pixel-identical frames for a primed crowd across terrace
    bands, and the same draw order (auras under bodies, reactions on
    top).
  - Outcome: the infused-minus-packed draw gap at 2560 × 1080 (15.83 −
    11.48 = 4.35 ms p50) halved or better.
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

## RND-008: Tasks

- [x] RND-008.1: This journal, with the reviewed findings and the report; the index row
- [ ] RND-008.2: Harness: hints off by default, master frozen through timing, one budget, `--bump`; re-baseline
- [ ] RND-008.3: No font built during a run's draw (hints, keycaps, interact key); cached word and label surfaces; a block-sized fade buffer; the `fonts._load` sweep test
- [ ] RND-008.4: Elemental draw: bodies bucketed by band once a frame; cached status-mark shapes; cached plain damage-number glyphs
- [ ] RND-008.5: Update re-measured with a stationary hero and frozen master; the bump decision, and the cheap wins if taken
- [x] ~~RND-008.6: Render-scale comparison~~: dropped, D4 (the resolution stays native)
- [ ] RND-008.7: Results, before and after; index to done

## RND-008: Method

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
