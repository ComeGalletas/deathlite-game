# XP curve journal

The hero's level curve lives in `progression/experience.py`. Everything that
grants or displays XP (`LevelTracker`, the HUD bar, the dev "fill the bar" key,
the level-up screen) reads `xp_for_level(level)`, so the curve is changed in one
place and no call site carries a copy of a number.

## 2026-09-22 -- remove the L21-25 discount and flatten from level 10

### The requirement, as stated

> remove the discounts for lvls 21 - 25. Make the curve flatter starting from
> lvl 10, ie. reduce next required exp by at least 15%, more if needed.

### Confirmed reading

1. The `LATE_LEVEL` / `LATE_CUT` / `LATE_RAMP` block goes away entirely. Nothing
   special happens at level 21 or at level 26 any more.
2. Levels 1-9 keep the costs they ship today: 3, 5, 9, 15, 21, 28, 36, 46, 56.
3. From level 10 onwards every level costs at least 15 % less than the value
   shipping before this change. That floor is measured against the *shipped*
   numbers, which for L21-25 were already carrying the late discount -- so
   meeting the floor there means taking about 36 % off the undiscounted
   quadratic. This is the "more if needed" clause.
4. "Flatter" is read as a smaller growth rate, not merely the same curve shifted
   down: the level-to-level increment must grow more slowly than it does today.

### Why the L21-25 discount was worth removing

The 25 % late cut phased in over five levels while the underlying quadratic was
only growing about 9 % a level, so the discount nearly cancelled the ramp. The
cost still rose, but the *increment* collapsed from +22 XP at level 20 to +3 XP
at level 25 and then snapped back to +22 at level 26. Levels 21-25 all cost a
near-identical 253-278 XP, and level 26 was where a long run suddenly felt like
it had slowed down -- the opposite of what the flattening was for.

### The proposal

Keep the existing quadratic for the early game and, at a knee of level 10,
freeze the quadratic term at its knee value and let it resume with a smaller
coefficient. A flat cut multiplies the result.

```
n = level - 1,  KNEE_N = 9

level <  10   cost = int(0.60 * (5 + 4n + 0.9 n^2))
level >= 10   cost = int(0.60 * FLAT * (5 + 4n + 0.9*81 + QUAD_FLAT*(n^2 - 81)))
```

`FLAT = 0.84` is the deepest flat cut that keeps the curve strictly increasing
across the seam: at 0.82 level 10 costs the same 56 XP as level 9 and
`test_strictly_increasing` no longer describes the curve.

`QUAD_FLAT` is the knob for how much flatter the late game gets. Two depths were
costed:

| | `QUAD_FLAT = 0.55` | `QUAD_FLAT = 0.50` |
|---|---|---|
| cut at L10 | 16 % | 16 % |
| cut at L15 | 30 % | 32 % |
| cut at L20 | 36 % | 39 % |
| cut at L25 | 19 % | 24 % |
| cut at L40 | 25 % | 30 % |
| increments L11-L40 | +7 .. +24 | +7 .. +21 |
| XP to reach L20 | 1337 (was 1840) | 1302 (was 1840) |
| XP to reach L30 | 3681 (was 4910) | 3512 (was 4910) |
| XP to reach L40 | 7861 (was 10402) | 7412 (was 10402) |

Both are strictly increasing at every level and neither has a trough.

### The decision the request left open, and the seam

The depth (`QUAD_FLAT`) is the open decision -- the request set a floor of 15 %
and left the ceiling to judgement.

The level 9 -> 10 step becomes +1 XP (56 -> 57). This is forced by the
requirement rather than chosen: level 9 is fixed at 56 by item 2 and level 10 is
capped at 0.85 x 68 = 57.8 by item 3, so any curve meeting the floor makes those
two levels the same length. It is one flat spot in place of the five-level
trough being removed. Easing a small cut into levels 8-9 would smooth it, but
that touches levels the request asked to leave alone, so it is not proposed.

### Tests

`tests/progression/test_experience.py` describes the curve by property, not by
pinned values (`test_strictly_increasing`, `test_level_one_is_cheapest_and_positive`),
so it keeps applying. A test is added for the two properties this change is
about: no level from 10 on costs more than 85 % of its previous value, and the
increment sequence never falls (which is what forbids a trough ever coming back).

### The decision taken

`QUAD_FLAT = 0.55`, the moderate depth: 16 % off at the knee, deepening to 36 %
at level 20 and holding around 25 % at level 40. A full 40-level run costs
7861 XP instead of 10402.

### The shipped curve

| L | XP | vs before | step | L | XP | vs before | step |
|---|---|---|---|---|---|---|---|
| 1 | 3 | -- | -- | 21 | 168 | -34 % | +13 |
| 5 | 21 | -- | +6 | 22 | 181 | -31 % | +13 |
| 9 | 56 | -- | +10 | 23 | 195 | -28 % | +14 |
| 10 | 57 | -16 % | +1 | 24 | 209 | -24 % | +14 |
| 11 | 64 | -21 % | +7 | 25 | 224 | -19 % | +15 |
| 12 | 72 | -23 % | +8 | 26 | 240 | -20 % | +16 |
| 15 | 99 | -30 % | +10 | 30 | 308 | -22 % | +18 |
| 18 | 131 | -34 % | +11 | 35 | 405 | -24 % | +20 |
| 20 | 155 | -36 % | +13 | 40 | 517 | -25 % | +24 |

Cumulative: 680 XP to reach L15 (was 838), 1337 to L20 (was 1840), 3681 to L30
(was 4910), 7861 to L40 (was 10402).

### Progress

- [x] Rewrite `progression/experience.py` -- `LATE_LEVEL` / `LATE_CUT` /
      `LATE_RAMP` and `_late_factor` deleted, `KNEE_LEVEL` / `KNEE_CUT` /
      `QUAD_FLAT` added.
- [x] Add the two curve-shape tests: `test_no_trough_in_the_increments` and
      `test_knee_cuts_at_least_fifteen_percent`.
- [x] Run the suite.

### A note on the trough test

`test_no_trough_in_the_increments` cannot simply assert that each increment is
at least the previous one. Truncating the cost to an int makes neighbouring
increments jitter by 1 on a rising trend (levels 40-42 step +24, +23, +25), so
the test bounds the jitter at 1 and checks the trend over a five-level window
instead. Both guards were run against the removed curve and both fire at levels
21-25, which is the shape the test exists to forbid.
