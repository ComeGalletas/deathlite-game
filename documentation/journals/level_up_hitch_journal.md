# The level-up hitch: journal

**ID:** UI-018 · **System:** UI · **Type:** performance ·
**Status:** planned · **Branch:** ComeGalletas/crowd-draw-levelup-9ec11fc6
(from `main`, owner, 2026-09-30; shared with RND-010)

---

## UI-018: Requirement (owner, 2026-09-30)

- **Objective:** Take the hitch out of every level-up: the frame that opens
  the cards should fit the 60 fps budget (16.67 ms).
- **Details:**
  - The owner's first real-play trace (SYS-010, 557 s) counted apart the 47
    play frames that opened the level-up cards, since their draw is the
    cards' first. All 47 were over budget, all draw-bound.
  - It happens on every level-up, not only the first: each one pushes a new
    `LevelUpState` (`game/states/playing/core/rewards.py:195-209`).
- **Constraint:**
  - The cards look the same: the opening frame and a steady frame are
    byte-identical old against new (`pygame.image.tobytes`).
  - No `Font` outlives a `pygame.quit()`: `game/fonts.py` keeps no cache
    on purpose, so any font kept goes through `ui/text.py`'s `cached_font`,
    which is cleared on quit, or an owner of the same kind.
  - A candidate is timed old against new before it is built.

## UI-018: What the cards do today (read from the code, 2026-09-30)

Leads, not findings, until UI-018.2 times them.

- **Cold fonts on every level-up.** `LevelUpState.enter`
  (`game/states/level_up_state.py:34-69`) builds a new `LevelUpPanel`, whose
  `__init__` (`ui/level_up.py:84-89`) opens four new `Font`s from the TTF
  files (`heading(40)`, `heading(24)`, `body(18)`, `body(16)`). Their glyph
  caches start empty, and a first render on a fresh font costs about
  1.4 ms a call (`ui/text_cache.py`'s note). So the opening frame renders
  every string on cold fonts.
- **Everything is rendered again every frame** (`LevelUpPanel.draw`,
  `ui/level_up.py:121-197`): the title, and per card the `#i` badge, the
  name through `shadowed()` (two renders and a new surface, uncached,
  `ui/text.py:126-139`), the rarity, the wrapped description (`wrap()`
  measures word by word), each description line, the category line, and
  the hint. The 9-slice card art is cached (`ui/panels.py`).
- **The dim layer** (`LevelUpPanel.draw_dim`, `ui/level_up.py:111-119`) is a
  new full-surface SRCALPHA surface, filled and blitted every frame.
- **The frozen world is redrawn under the cards every frame**
  (`draw_below`, `game/state.py:206-221`). That is the steady frames' cost,
  not the opening frame's; it is noted here and left alone unless UI-018.2
  shows it matters, because the world under the cards still animates
  through the terrain clock and a snapshot would change pixels.

## UI-018: Plan

- **UI-018.2: Measure the opening frame.** A headless probe on seed 35
  forces a real level-up through `_step` and times the frame that opens
  the cards and the steady frames after it, split into the fonts' creation,
  the text renders, the dim layer and the world underneath. Recorded here.
- **UI-018.3: Warm fonts and cached text.** Build the panel's fonts through
  `cached_font` (warm across level-ups, cleared on quit), and render each
  card's texts once per panel instead of every frame; the dim layer is kept
  per surface size. Each change timed old against new first (UI-018.2's
  probe), then built.
- **UI-018.4: Tests.** Byte-identical opening and steady frames, old against
  new; a second level-up builds no `Font` (`fonts._load` not called), in
  the manner of `tests/playing/test_frame_fonts.py`; the existing
  `tests/screens/test_level_up.py` green; a mutation check.
- **UI-018.5: Results.** The probe before and after; then, from the owner's
  next `--trace` run, the report's counted-apart line.
- **Outcome:** in the owner's trace, the counted-apart line's "work over
  budget 47" falls to 0 (or as near as the world under the cards allows,
  said with the number).

## UI-018: Tasks

- [x] UI-018.1: This journal, the plan and the index row
- [ ] UI-018.2: The opening frame measured, split by part
- [ ] UI-018.3: Warm fonts, text rendered once per panel, the dim layer kept
- [ ] UI-018.4: Byte-identity and no-new-font tests, the level-up screen tests green, a mutation check
- [ ] UI-018.5: Results: the probe before and after, and the owner's re-trace
