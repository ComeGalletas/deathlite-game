# Enemy health bar — execution journal

## Requirement (owner, 2026-09-22)

- **Objective:** Draw a health bar above every enemy that is below full HP.
- **Details:** Fixed height on every bar, with its length scaled by the enemy's
  maximum HP so a tanky enemy carries a visibly longer one than a mook, and the
  fill inside reading as the fraction left. The bar appears the moment
  `hp < max_hp` and stays for the rest of that body's life.
- **Constraint:** Bosses are excluded — they already have their own HP bar.

---

## What is already in place

* `run.boss` is a **separate** `Boss` object, not a member of `run.enemies`
  (`game/states/playing/visual/scene.py::actor_items` appends it on its own
  line). Drawing the new bar from the enemy path therefore excludes the boss
  structurally — no tag check, no `isinstance`. The bottom-centre HUD bar it
  already has is `ui/hud.py::_draw_boss`, and it must not gain a second one
  over its head.
* `ui/bars/meters.py::bar(...)` already builds a finished bar Surface from the
  `assets/ui/04.png` hex family at any length and any fraction, cut from
  authored art rather than drawn as rectangles, and returns `None` when the art
  is missing. `framed=False` returns the bare trough + fill (34x5 native art in
  a `width`-wide box, inset 4 px symmetrically) — exactly the slim shape wanted
  over a sprite's head, and the same shape the XP bar uses.
* `Renderer.one_enemy` (`game/states/playing/visual/rendering.py:543`) is the
  single place every enemy is painted, inside its own terrace band. Anything
  added there is occluded by a higher terrace the same way the enemy's head is,
  which is the behaviour wanted.
* The head is computable from per-rig constants, not per-frame ones:
  `assets.scale_for(rig)` and `anchor_for(rig, flip)` give the rig's nominal box
  and feet anchor, so `sy - ay*z + sprite_drop(radius)` is the top of the sprite
  and does not bob when an attack frame is taller than an idle one. For a
  primitive-fallback enemy (no rig) the top is `sy - radius*z`.
* The training dummy is `invulnerable` — its HP never drops, so it never shows a
  bar without a single line of special-casing.

## The HP range the length has to cover

`data/enemies/enemies.json` spans 5 HP (bumblebee) to 290 HP (troll), and the
director multiplies `max_hp` by up to **2.4x** over a run
(`spawn/budget.py::stat_multipliers`), so the live range is roughly **5 – 700**.
Linear px-per-HP is unusable across that: it either makes the bumblebee a
2-pixel nub or the late troll a bar wider than the screen.

**Mapping** — square root, rounded to even native px, clamped:

```
native_w = clamp(MIN_W, 2 * round(REF_W * sqrt(max_hp / REF_HP) / 2), MAX_W)
REF_HP = 20   REF_W = 27   MIN_W = 22   MAX_W = 84
```

The art is drawn at **x1**, so a native px is a screen px (see the size pass
below for how these numbers came down from an earlier x2 set).

| enemy | max HP | bar length |
|---|---|---|
| bumblebee | 5 | 22 (floor) |
| spider | 10 | 22 |
| slingshot gnome | 17 | 24 |
| skull / gnoll | 20 | 28 |
| spear goblin | 42 | 40 |
| minotaur | 55 | 44 |
| hex shaman | 64 | 48 |
| torch goblin | 87 | 56 |
| bear | 125 | 68 |
| turtle | 150 | 74 |
| troll | 290 | 84 (ceiling) |
| troll, late run | 696 | 84 (ceiling) |

Every tier is distinguishable and every bar stays narrower than its own sprite
(skull 84 px wide on screen, troll 148, turtle 225). Rounding to **even** native
px is not cosmetic: it caps the `meters.bar` cache, which keys on
`(width, filled, ...)` and clears wholesale when full — a continuous width
across 60 live enemies would thrash it.

## Decisions taken by default (say the word to flip any of them)

* **Frameless.** `framed=False`: the bare trough + red fill, **5 px tall**, the
  fixed height for every enemy. A framed hex bar is 11 px and reads as chrome
  over a crowd of forty bodies. Flipping to framed is a one-line config change.
* **The troll gets one.** It is tagged `miniboss` but it is an ordinary
  `run.enemies` body with no HUD bar of its own, so it takes the overhead bar
  like everything else. Only the `Boss` class is excluded.
* **HP only.** `shield_hp` keeps its existing collider ring; it does not get a
  second segment in this bar.
* **Enemies only.** Hero summons, villagers and fish-hut boats are out of scope.
* **No fade.** The bar appears and disappears with the condition, instantly.
  A hidden (spawn-veiled) enemy draws no bar, as it draws no sprite.
* **Primitive fallback.** When the hex art is missing, two flat rectangles, the
  same degrade contract `ui/hud.py` keeps.

---

## What was built

### `game/config.py` — the `ENEMY_HP_BAR_*` block

Sits with the HUD knobs, next to the boss bar it is the counterpart of. Names
the three rigs (`bar_hex_frame_grey` for the housing the track is measured
against, the red fill, the shared trough), `FRAMED = False`, `SCALE = 2`, the
four mapping knobs and the gap above the head. The curve's reasoning lives in
the comment beside the knobs rather than only here, so nobody retunes it blind.

### `ui/bars/meters.py` — a public `inset(assets, frame=...)`

`bar(width=...)` takes the bar's **outer** width, but the enemy bar sizes its
**track** — the part that carries the meaning — so it has to convert. The
difference is 8 native px for this family, and getting it wrong is not cosmetic:
a 22-px outer bar leaves a 14-px track, and a fill shorter than its own two
caps is not drawn at all, so the smallest enemies would have read as *empty*
below 29 % HP instead of 18 %. `inset` makes `track + inset` expressible and
the bug unwritable.

Both bar caches went from 512 entries to 1536 in the same pass. The HUD alone
holds a couple of hundred (one entry per fill position a long bar passes
through) and a crowd of enemies adds one family per distinct track length times
that track's own fill positions. Over the cap the cache is dropped **whole**,
so an undersized cap would have had the HUD's own bars rebuilding mid-fight.

### `game/states/playing/visual/health_bars.py` — the bar

One module, one concern. `native_track(max_hp)` is the mapping above and is
pure, so its floor, its ceiling and its monotonicity are testable without a
window. `draw(surface, renderer, e)` returns immediately at full HP, and
otherwise builds the bar through `ui.bars` and hangs it over the enemy's head.

Two details worth keeping:

* **The head is measured off the idle art, once per rig.** Two obvious answers
  are both wrong. The *live* frame's top bobs: an attack frame is usually
  taller than an idle one, so the bar would jump every time the enemy swung.
  The rig's *declared box* is stable but far too loose — it is sized for the
  tallest pose the rig ever strikes, and the first screenshot showed it: the
  bear, which rears up to swing, floated its bar 40 px clear of its own head
  (its box top is 85 px over the anchor; its idle ink is 51). So `rig_lift`
  measures the idle frame's ink through `key_marker.ink_of` — the helper the
  interact cap already uses to sit on an element's art, thin tips and wisps
  skipped — and caches it per rig. Tight and still. A primitive-fallback enemy
  has no rig and uses its collider; a rig with no idle art to measure falls
  back to its box.
* **A dying enemy keeps a sliver.** `bars.bar` skips a fill shorter than its two
  caps; on the hero's 104-px bar that is the deliberate "no sliver at death",
  but on a 22-px enemy track it would blank the bar for the last fifth of the
  enemy's life — the fifth worth seeing. So a live enemy's fraction is floored
  at the shortest fill the art can build. The hero's bar is untouched.

### `Renderer.one_enemy` — the call

One line at the end of the existing enemy painter, which means the bar is
painted inside the enemy's own terrace band: a higher terrace occludes it
exactly as it occludes the head it sits over. The early return on
`spawn_veiled` already covers it, so an enemy still inside its spawn burst
shows no bar.

## Verification

`tests/render/test_enemy_hp_bar.py`, 13 tests in four groups:

* **`TrackLengthTests`** — the length never shortens as HP rises across the
  whole roster; the floor and the ceiling hold, the ceiling checked against a
  late-run troll (`290 x 2.4`) rather than its sheet value; every length is an
  even number of native px, which is what keeps the cache bounded.
* **`BarArtTests`** — a 5-HP bar and a 290-HP bar are the same height and differ
  in width by exactly the track difference (so the housing is not what grew); an
  enemy at 2 % still draws red; the art is symmetric inside its surface, which
  is what lets `draw` centre the surface and get a centred track.
* **`DrawTests`** — full HP draws literally nothing; 39.5/40 draws something;
  the bar is centred on the enemy and sits clear of its head; a sprited skull
  hangs off its measured art and higher than the collider would put it; the
  measured lift really is tighter than the rig box for the bear, the spear
  goblin and the troll, and an unmeasurable rig falls back to that box;
  on-screen length follows max HP at a fixed height; missing art falls back to
  rectangles of the same height.
* **`BossExclusionTests`** — boots a pinned-seed run, spawns and hurts both a
  skull and the boss, and asserts the boss painter asks for no bar while the
  enemy painter asks for exactly one. It also asserts the structural reason
  (`boss not in run.enemies`), so if that ever changes the test says why it
  broke.

---

## Size pass (owner, 2026-09-22)

> "Is it possible to make the bar smaller as a whole while keeping the length
> the same way?"

Yes, and the lever is one number. The bar is authored pixel art on a whole-pixel
grid, so its scale has to be an integer: x2 and x1 are the only sizes available,
and x1 halves the height from 10 px to 5. The length is independent of that —
it comes out of `native_track`, so the mapping can be retuned to any range
without touching the height, and the rule itself (length from **maximum** HP)
is untouched either way.

Four settings were rendered over the same scene for comparison:

| | art scale | height | lengths | shortest drawable fill |
|---|---|---|---|---|
| **A** (as built) | x2 | 10 px | 28 – 112 px | 29 % |
| **B** | x1 | 5 px | 28 – 112 px | 14 % |
| **C** (chosen) | x1 | 5 px | 22 – 84 px | 18 % |
| **D** | x1 | 5 px | 14 – 56 px | 29 % |

The owner took **C**: half the height, and lengths cut to about three quarters
so the whole bar came down together rather than just flattening.

The last column is why C beat D at the same height. A fill shorter than its own
two authored caps (4 px) cannot be built, so below that fraction the bar shows
its floored minimum nub; the shorter the *shortest* bar, the bigger a slice of
health that nub covers. D's 14-px floor would have kept the current 29 %, while
C's 22-px floor brings it down to 18 %. The ratio depends only on the track in
native px — scaling the art up or down moves both terms — so it is the length
range, not the art scale, that buys the granularity.

`ENEMY_HP_BAR_GAP` doubled from 3 to 6 in the same change: it is measured in
native px and multiplied by the art scale, so doubling it keeps the same 6 px
of air over the enemy's head that the x2 bar had.
