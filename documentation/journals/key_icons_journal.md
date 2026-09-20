# Key icons — drawing keyboard keys as pixel-art keycaps

The interaction prompt says `E  Shrine - gain a blessing` in plain text. This
journal turns that leading `E` into a drawn keycap, and lays the ground for
every other place the game will need to show a key.

---

## Requirement (owner, 2026-09-19)

> "review the assets folder and unused asset folder for sprite resources
> that we can use to show keyboard keys ingame with pixel art."

then, after the survey and mockup:

> "the key label needs to move when the keyicon is not selected."

and

> "fix the mockup with the per-state offsets. prepare a todo list to add
> these key icons to the ingame and first as the interaction key for the
> game elements, opening a box, using the forge and sanctuary heal areas
> and any possible future interactions."

## The survey

There is **no purpose-made keyboard art** anywhere in `assets/`, the
untracked `assets/unused/`, or the Super Pixel Effects Gigapack (its
"Symbols" folder is animated effect text: `WOW!`, `RANK S`, warning signs).

But the Tiny Swords UI pack already ships a keycap family, labelled as
buttons:

| Asset | Size | Reads as |
|---|---|---|
| `assets/ui/buttons/blue.png` (tracked, **unused** — not in `ui_sprites.json`) | 64×64 | raised cap: bevelled face + dark skirt |
| `assets/unused/ui/buttons/blue_pressed.png` | 64×64 | the same cap pressed: skirt gone, face 4 px lower |
| `assets/unused/ui/buttons/red.png` + `red_pressed.png` | 64×64 | the red pair |
| `assets/unused/ui/buttons/grey.png`, `gold.png` | 64×64 | neutral / highlight caps, **down position only** (no skirt, no raised variant) |
| `assets/ui/buttons/*_wide.png` (already wired) | 192×64 | 3:1 caps for `SPACE` / `SHIFT` / `TAB` |
| `assets/unused/ui/icons/*.png` | 64×64 | glyph overlays: `1 2 3 + − × ⚙ 🔊 🛒 🔓` — **no letters** |
| `assets/unused/ui/banners/parchment.png` | 64×64 | flat square, no bevel — weaker |
| `assets/ui/base/02.png` | 256×160 | thin hollow frames — too faint for a key |

So a keycap is **cap art + a Fredoka letter drawn on the face**, which is
exactly how every other button in the game gets its label
(`ui/widgets.py`). Text on the light caps is black
(`config.COLOR_ON_BUTTON`), per the standing rule for button text.

### The per-state offset (the owner's correction)

Measured down the centre column of each cap:

| Cap | Face fill rows | Face centre `y` |
|---|---|---|
| `blue.png` / `red.png` — raised, idle | 7–41 | **24** |
| `blue_pressed.png` / `red_pressed.png` | 11–45 | **28** |
| `grey.png` / `gold.png` | 11–45 | **28** |

The raised face sits 4 px higher than the pressed one, so the label has to
ride the face: centred at `y=24` on the idle cap and `y=28` on the pressed
cap. The first mockup used one offset for both and the letter looked like it
slid inside the key; the second mockup (delivered 2026-09-19) uses the
per-state centres and the E pair shows a real press. `ui/widgets.py` already
does this for the wide buttons (`PRESSED_DY = 4`).

## Confirmed reading

* **"the interaction key for the game elements"** — the `E` prompt drawn by
  `PlayingRenderer.feedback_overlays` (`game/states/playing/visual/rendering.py`
  ~L153) for whatever `ps.locations.nearby()` or `ps.chest_manager.nearby()`
  returns.
* **"opening a box"** — chests: `ChestManager.prompt()` in
  `game/states/playing/core/chests.py` returns `"E  {Rarity} chest - open it"`.
* **"using the forge and sanctuary heal areas"** — `Interactable` kinds
  `forge` and `fountain`, whose prompt strings live in `entities/interactable.py`
  `KINDS`, alongside `shrine`, `treasure`, `altar`, `merchant`.
* **"any possible future interactions"** — anything that goes through the
  same `Interactable` / prompt path gets the cap for free: the key glyph is
  drawn by the renderer from the bound key, not baked into each prompt
  string. Prompt strings therefore **drop their leading `"E  "`**.
* The key itself is hard-coded as `pygame.K_e` in `PlayingState.handle_event`
  (`core/state.py` ~L316). It becomes `config.KEY_INTERACT` so the drawn cap
  and the handled key can never disagree, and a future rebinding shows the
  right letter.

Decisions the request left open, taken here (say if you want them changed):

1. **Colour** — the interaction cap is **blue** (the game's primary button
   colour) because blue is the only neutral-reading colour with both a raised
   and a pressed frame. Grey/gold stay in reserve for reference listings
   (options / pause controls list) where no press feedback is needed.
2. **Pressed feedback** — the cap shows its pressed frame while
   `KEY_INTERACT` is physically held (`pygame.key.get_pressed()`), which is
   the same "baked press" the menu buttons use. No timer, no animation.
3. **Size** — the cap is drawn at **32 design px** (`scale.px(32)`): 64 → 32
   is an exact ×0.5 nearest-neighbour step so the pixel grid stays clean, and
   32 px sits well beside the 20 px prompt font. The label is Fredoka at
   ~18 design px on the face. Under `RENDER_SCALE` both go through `ui.scale`.
4. **Layout** — cap and text are laid out as one group (cap, 10 px gap, text)
   and the *group* is centred where the text alone was centred
   (`h - scale.px(96)`), so the prompt does not shift left or right. The
   unaffordable-merchant tint stays on the text only; the cap never tints.
5. **Fallback** — with no art (empty `assets/`, the plain fallback), the
   renderer draws the letter in the prompt font where the cap would be, so
   the screen still says `E  Shrine - ...` as it does today.

## Proposal

New module (one concern per module, per the project's sub-package habit):

```
ui/keycap.py
    FACE_Y = {"raised": 24, "pressed": 28}       # native 64 px cap
    CAP_PX = 32                                   # design px on screen
    KEYCAP_SHEETS = {"blue": ("keycap_blue", "keycap_blue_pressed"), ...}
    label_for(keycode) -> str                     # "E", "SPACE", "TAB", "↑"...
    draw_keycap(surface, assets, center, label, *, state="raised",
                colour="blue", size=CAP_PX, font=None) -> pygame.Rect
    draw_key_prompt(surface, assets, center, keycode, text, *,
                    pressed=False, text_colour=..., font=...) -> pygame.Rect
```

`draw_keycap` blits the cap via `assets.image(rig, size=...)` (a whole
image, not a 9-slice — the cap is a fixed square) and centres the label at
`FACE_Y[state] * size / 64`. `draw_key_prompt` composes cap + gap + text as
one centred group and is the only thing `feedback_overlays` calls.

Data and art:

* `data/ui/ui_sprites.json` gains `keycap_blue` → `ui/buttons/blue.png`
  (already tracked) and `keycap_blue_pressed` → `ui/buttons/blue_pressed.png`
  (copied in from `assets/unused/ui/buttons/`). Wide caps reuse the wired
  `btn_blue_wide` / `btn_blue_wide_pressed` rigs when a wide key is first
  needed — not part of this pass.
* `assets/CREDITS.md` needs no change: it is Tiny Swords art.

Code:

* `game/config.py`: `KEY_INTERACT: int = 101   # K_e`, next to
  `KEY_TOGGLE_AUTO_ATTACK`.
* `core/state.py`: `elif event.key == config.KEY_INTERACT:`.
* `entities/interactable.py` `KINDS` and `chests.py` `prompt()`: strip the
  `"E  "` prefix; the strings become `"Shrine - gain a blessing"`,
  `"{Rarity} chest - open it"`, etc.
* `visual/rendering.py` `feedback_overlays`: both prompt branches call
  `keycap.draw_key_prompt(box, assets, (w // 2, h - scale.px(96)),
  config.KEY_INTERACT, text, pressed=held, text_colour=col,
  font=ps._prompt_font)`.
* The transient notice above the prompt sits at `h - 124`; with a 32 px cap
  centred at `h - 96` the cap spans `h-112 … h-80`, and the 20 px notice
  spans roughly `h-134 … h-114` — clear, but only just. If it reads crowded
  in the screenshot, lift the notice to `h - 130`.

Tests (`tests/screens/test_keycap.py`, dummy SDL like `test_widgets.py`):

* the two rigs load and `draw_keycap` returns a rect of `size × size`;
* the label rect centre is `FACE_Y["raised"]/2` for the idle cap and
  `FACE_Y["pressed"]/2` for the pressed cap at `CAP_PX = 32` — i.e. the label
  moves 2 px with the face; scaled the same under `RENDER_SCALE = 1.6`;
* `draw_key_prompt` centres the *group* on the given point (the text alone
  is right of centre, the cap left of it);
* with `Assets()` on an empty tree the fallback draws the letter and returns
  a rect that still keeps the text at the same x as the art path;
* `label_for(pygame.K_e) == "E"`, `label_for(pygame.K_SPACE) == "SPACE"`.

Existing tests to touch: `tests/playing/test_chest_open.py:130` only checks
`"Epic" in prompt` — unaffected; `tests/playing/test_interactables.py` posts
`K_e` directly — switch it to `config.KEY_INTERACT`.

## Todo

Pass 1 — the interaction prompt (chests, forge, sanctuary, shrine, altar,
merchant, and anything added later through `Interactable`):

- [x] 1. Copy `assets/unused/ui/buttons/blue_pressed.png` into
      `assets/ui/buttons/` and register `keycap_blue` / `keycap_blue_pressed`
      in `data/ui/ui_sprites.json` (the square `blue.png` is already tracked).
- [x] 2. Add `config.KEY_INTERACT` and use it in `PlayingState.handle_event`
      in place of the literal `pygame.K_e`.
- [x] 3. Write `ui/keycap.py`: `FACE_Y`, `label_for`, `draw_keycap` (per-state
      label offset, art + flat fallback), `draw_key_prompt` (cap + text as one
      centred group).
- [x] 4. Strip the `"E  "` prefix from the `KINDS` prompts in
      `entities/interactable.py` and from `ChestManager.prompt`.
- [x] 5. Route both prompt branches of `feedback_overlays` through
      `draw_key_prompt`, passing `pressed=` from `pygame.key.get_pressed()`.
- [x] 6. `tests/screens/test_keycap.py` (offsets per state, group centring,
      fallback, labels); point `test_interactables.py` at `KEY_INTERACT`.
- [x] 7. Run the suite; boot a pinned-seed run, stand on a chest and on the
      sanctuary, deliver screenshots of the idle and held-E prompts; check
      the notice/prompt spacing at the forge.
- [ ] 8. Log results here (test counts, screenshots, anything deferred).

Later passes (not started; listed so the module is shaped for them):

- [ ] Pause menu / Options: a "Controls" block listing move, aim, attack,
      interact, auto-attack toggle and TAB with grey reference caps, driven
      by `config.KEY_LAYOUTS` so it follows the chosen layout.
- [ ] Wide caps (`SPACE`, `SHIFT`, `TAB`) via the wired `btn_*_wide` rigs.
- [ ] Mouse-button glyphs beside the caps for click-to-attack, once a
      mouse sprite is chosen (`assets/ui/pointers/arrow.png` is the cursor,
      not a button glyph).
- [ ] Tutorial / first-run hints ("W A S D to move") over the hero at run
      start, reusing `draw_keycap` in the world layer.

## Progress

* 2026-09-19 — survey done, first mockup delivered, corrected to per-state
  label offsets, second mockup delivered, this journal written.
* 2026-09-19 — pass 1 built, items 1–7:
  * `assets/ui/buttons/blue_pressed.png` brought in beside the square
    `blue.png`; rigs `keycap_blue` / `keycap_blue_pressed` (64×64) in
    `data/ui/ui_sprites.json`.
  * `config.KEY_INTERACT = 101` (`K_e`), used by `PlayingState.handle_event`.
  * `ui/keycap.py`: `FACE_Y`, `label_for`, `cap_rect`, `label_center`,
    `draw_keycap`, `draw_key_prompt`. `cap_rect` places the frame so the
    *raised* face centre lands on the given point; the pressed frame is
    drawn in the same rect (the press is baked into the art) and only the
    label moves, `round(4 · size/64)` px — 2 px at the 32 px cap, 3 px at
    `RENDER_SCALE = 1.6`.
  * Prompt strings in `entities/interactable.py` and `ChestManager.prompt`
    lost their `"E  "` prefix; `feedback_overlays` routes both branches
    through a new `_key_prompt`, with `pressed` from a module-level
    `_interact_held()` that reads `pygame.key.get_pressed()` and answers
    False when the keyboard cannot be read (headless suite).
  * `tests/screens/test_keycap.py`: 14 tests — labels, cap geometry, the
    per-state label shift at scale 1 and 1.6, sheet selection, both frames
    loading at cap size, art landing on the surface, black label on the
    art, prompt-colour letter without it, the prompt group centred on its
    point, and the words keeping their place with and without the art.
    `Font.render` cannot be patched on the type, so a small spy font records
    the colour instead. `test_chest_open.py` posts `config.KEY_INTERACT`.
  * Screenshots delivered from a seed-1234 run: the chest prompt idle and
    with E held (2× crops), the sanctuary prompt in the full frame, plus
    forge and shrine renders checked. The notice line above the prompt was
    not crowded in the forge frame; the `h - 130` lift was not needed.
  * Suite: the targeted set (keycap, chest open, interactables, widgets)
    66 passed. The one failure in the default run,
    `tests/entities/ai/test_imp.py::RigTests::test_the_editor_source_is_not_shipped`,
    is pre-existing and unrelated: it looks for `assets/unused/enemies/imp/Imp.aseprite`,
    and the untracked `assets/unused/` tree exists only in the main checkout,
    not in a worktree. With it deselected the default suite is **2595
    passed**, 634 subtests, 12:42.

---

## Pass 2 — the cap floats over the element (owner, 2026-09-19)

> "move the keycap to interact, in this case 'E' on top of the element to
> interact with when getting close to it. this means that only one key
> should be available at a time and only for the closer element to the
> player. the comment at the bottom goes away"

Decisions, answered the same day:

1. The prompt words are gone with the bar: no merchant price ("there is no
   proper merchant functionality yet, for now thats irrelevant") and no
   chest rarity in the prompt. **The notice after opening a chest stays** —
   that is `ps.notice("Rare chest: 40 gold, ...")` at `h - 124`, which was
   never part of the prompt and is untouched.
2. `Interactable.prompt`, the `prompt` column of `KINDS` and
   `ChestManager.prompt` are **removed**, not left as dead text.

### Confirmed reading

* One keycap, drawn in **world space** above the single closest usable
  element (interactable not `used`, chest not `opened`) within reach; it
  follows the element under camera movement and shake, appears on entering
  range and vanishes on leaving or once the element is used.
* The bottom-centre `[E]  words` prompt is removed entirely
  (`feedback_overlays` no longer draws it; `_key_prompt` goes).
* The cap keeps the held-E pressed frame, and stays 32 design px on screen
  — an interface element at a world position, not zoomed with the world.
* "Closest" is a new rule: `locations.nearby()` returned the *first*
  interactable in range in list order, and the E handler gave locations
  priority over chests by fiat. Both the cap and the E handler now use one
  `nearest_interaction()` that ranks interactables and chests together by
  distance, so the key shown is always the key that fires.
* The cap is drawn after the whole world (end of the world block in
  `PlayingState.draw`, inside the shake offset, before the HUD) so the hero
  standing on a chest never covers it.
* "On top": a per-kind lift above `pos`, scaled by zoom — chest art is 28 px
  anchored on its baseline; shrine / altar / merchant are rings of `radius`;
  the sanctuary (192 px heal effect) and the forge (baked obstacle) get
  hand-tuned lifts, checked in the screenshots. Table `KEY_LIFT` in the
  drawing module.
* Nothing else is open: the notice line keeps its place at `h - 124`; the
  no-art fallback draws the letter at the same world spot; an element on
  another terrace within reach behaves as it does today (distance only).

### Proposal

* `game/states/playing/core/interactions.py` (or on `LocationManager`):
  `nearest_interaction() -> (kind_tag, obj) | None` over `ps.interactables`
  and `ps.chests`, min squared distance among those in range and unused.
  `handle_event` E → activate that one; `activate_nearby` in both managers
  becomes `activate(obj)`.
* `ui/keycap.py`: unchanged API; `draw_key_prompt` is deleted with its
  callers (nothing else uses it).
* `game/states/playing/visual/key_marker.py`: `KEY_LIFT` by kind,
  `draw(surface, ps)` — screen point from `camera.world_to_screen(pos)`
  minus `lift · zoom`, `keycap.draw_keycap` with `pressed=_interact_held()`.
* `entities/interactable.py`: `KINDS` → `(radius, colour)`; drop `prompt`
  from `__slots__`. `chests.py`: drop `prompt()`.
* Tests: `test_keycap.py` loses the four `draw_key_prompt` tests; new
  `tests/playing/test_key_marker.py` — closest wins across both lists, one
  cap at most, none when out of range or after use, the cap sits above the
  element's screen point by the kind's lift, E fires the marked element.
  `test_chest_open.py`: the `"Epic" in prompt` line and
  `test_a_special_location_still_wins_the_key` are replaced by a
  closest-wins case.

### Todo

- [x] 1. `nearest_interaction()`; E handler and both `activate_*` paths on it.
- [x] 2. Remove the prompt strings and `ChestManager.prompt`.
- [x] 3. `visual/key_marker.py` with `KEY_LIFT`; draw it at the end of the
      world block; delete `_key_prompt` and the bottom prompt.
- [x] 4. Tests as above; run the suite.
- [x] 5. Screenshots: chest, sanctuary, forge, shrine, idle and held.
- [ ] 6. Log results here.

### Results (2026-09-19)

* `game/states/playing/core/interactions.py`: `usable`, `nearest` (one
  rule over `ps.interactables` and `ps.chests`, locations ranked first so
  a tie keeps the old order), `kind_of`, `activate`. `SpecialLocations`
  gained `use(it)`; `activate_nearby` on both managers stays for the chest
  tests that call it directly. `handle_event` fires `interactions.nearest`.
* `game/states/playing/visual/key_marker.py`: `KEY_LIFT` (chest 26, rings
  26 / treasure 24, fountain 40, forge 56 world px), `CLEAR_PX = 4`,
  `interact_held`, `anchor`, `draw`. Called at the end of the world block
  in `PlayingState.draw`, inside the shake offset.
* Removed: the bottom prompt and `_key_prompt` / `_interact_held` in
  `rendering.py`, `keycap.draw_key_prompt` and `GAP_PX`, `Interactable.prompt`
  and the `prompt` column of `KINDS`, `ChestManager.prompt`.
* Tests: `tests/playing/test_key_marker.py` (12) — nothing in reach,
  closest wins across lists, used / opened skipped, tie to the location,
  E fires the marked element then the next, `kind_of`; no cap without an
  element, one cap over the closest, the cap's bottom `CLEAR_PX` above the
  art top, the cap follows the element not the hero, held E → pressed
  frame, a whole `PlayingState.draw` reaches the marker once.
  `test_keycap.py` down to 12; `test_chest_open.py` lost the prompt test
  and its ordering test now pins the tie rule. Focused set: 63 passed.
* Screenshots delivered: chest idle / held, forge, shrine (2× crops) and
  the full sanctuary frame with E held. The sanctuary's only art is the
  `fx_heal` leaf loop (paint region 98×128 in a 192 frame, anchored at
  y=140), so at some frames the cap appears to float over open grass —
  that is the sanctuary prop's look, not the cap's placement; lift 40
  keeps it inside the heal disc without climbing the whole leaf column.
* Full suite (imp editor-source test deselected, pre-existing): **2604 passed, 9 deselected, 63 warnings, 634 subtests passed in 762.00s (0:12:42)**.

---

## Pass 3 — anchoring to the art (owner, 2026-09-19)

> "1. blue chest has the keycap slightly to the left of its top center.
> review the size and rendering of all chests to make it as similar as
> possible dimensions wise. 2. review the current forge center as well.
> 3. the sanctuary is fine, however try searching in the unused assets if
> theres a better effect to change"

### What the measurements say

**Chests.** Horizontally the cap is within ±1.5 px of every chest's ink
centre; the residue is rounding (the chest blits at `int(sx - ax·z)`, the
cap at `round(sx)`) plus the cap's own bevel, lit top-left and shaded
bottom-right, which makes its mass read a touch left. Vertically is the
real inconsistency: the tiers draw at `scale` 28 / 30 / 32 / 34 (common →
epic) and their ink tops sit 29 / 34 / 39 / 32 screen px above `pos` at
zoom 1.5, while `KEY_LIFT["chest"]` is one value (26 → 39 px). So the cap
clears the rare chest by 4 px but floats 14 px over a common one and 11 px
over an epic. The art itself is 28 px wide in every tier (32 px frame),
24 / 26 / 27 / 21 px tall — the epic is squat by design of its sheet.

**Forge.** The interactable and the obstacle share one position, and the
cap hangs at the rig's anchor x (118 of 256). The chimney — the highest
ink, row 64 — peaks at x 144, and the top quarter of the ink centres at
x 136: the bellows widen the assembly to the left, so the anchor is the
assembly's centre, not the furnace's. At render scale 0.6 and zoom 1.5 the
cap is 16–23 screen px left of the chimney.

**Sanctuary.** Reserve candidates in the Gigapack, green "large" variants
(15 fps, individual frames under `PNG/`): `spell_heal_001` (16 fr, heart
burst), `spell_heal_002` (36 fr, rising green crosses), `spell_heal_003`
(42 fr, cross burst), `spell_buff_001` (arrows — a buff, not a heal),
`status_sparkling_001` (24 fr, idle sparkles), `round_light_burst_001`,
`round_sparkle_burst_001/003` (one-shot bursts). Contact sheet delivered.

### Confirmed reading and proposal

1. **Anchor to the drawn art, not a table.** The marker reads the element's
   rig: for a chest, the frame's ink box at the drawn scale — cap centred on
   the ink's centre x, bottom `CLEAR_PX` above the ink top, computed from
   the same `int(sx - ax·z)` blit origin the chest painter uses so the two
   round identically. For the forge, the same from the `forge` rig's frame
   at its render scale, with the cap over the **highest ink column** (the
   chimney) rather than the anchor. `KEY_LIFT` shrinks to the fallback for
   elements with no art (the rings, and any missing sheet).
2. **One drawn size for the four chests**: `scale` 32 for every tier (the
   rare's), so all four are 28 px of ink wide; heights stay the sheet's
   (24 / 26 / 27 / 21). Assumption to confirm: the 28→34 rarity growth was
   never a recorded decision, so it goes.
3. **Sanctuary effect**: recommended `spell_heal_002_large_green` as the
   idle loop (rising crosses, the leaf palette, loops cleanly) with
   `status_sparkling_001` as the quieter alternative; the bursts are
   one-shots and do not suit a standing prop. Needs the pack's licence
   read before shipping and a CREDITS entry (untiedgames). Choice pending.

### Todo

- [x] 1. `key_marker.anchor` reads the rig (chest ink box; forge highest
      column); `KEY_LIFT` becomes the no-art fallback; tests for both.
- [x] 2. Chest `scale` → 32 for all tiers; check the potion lift and the
      chest tests that pin sizes.
- [x] 3. Sanctuary: on the owner's pick, cut the strip into `assets/`, rig
      it as `fx_heal`, credit it, screenshot.
- [x] 4. Screenshots of all three, suite, results here.

### Results (2026-09-19)

* Owner's picks: items 1 and 2 as proposed; `spell_heal_002` for the
  sanctuary.
* `key_marker.art_box(ps, obj)` returns the element's painted screen rect
  and the column the cap hangs on. A **chest** is measured from its closed
  frame at the drawn size, from the same truncated blit origin
  `rendering.chests` uses; the column is the ink box's centre (the
  uncommon chest's vine pokes above the lid 5 px off-centre, so the
  "highest column" rule was wrong for chests). The **forge** comes from the
  bake's own `gm._art_rects` / `gm._decos` for the obstacle standing on
  the interactable's point, and the column is the centre of its highest
  ink row — the chimney, 18 screen px right of the anchor at zoom 1.5.
  Rings and the sanctuary keep `KEY_LIFT`. The bake fills `_decos` on the
  first frame, so the forge falls back to the table until then (one
  frame); the test draws a frame before measuring.
* All four chests draw at `scale` 32 / anchor (16, 30)
  (`data/loot/prop_sprites.json`); `test_the_drawn_size_grows_with_the_tier`
  became `test_every_tier_draws_at_one_size`. The potion lift (16, "the
  open box's mouth") was tuned against ~30 px of art and still fits.
* Sanctuary: `tools/asset_pipeline/cut_heal_effect.py` writes the 36×128
  strip from the Gigapack's `spell_heal_002_large_green` frames (found in
  the main checkout's `assets/unused/` from a worktree via
  `git rev-parse --git-common-dir`), archiving the old leaf strip as
  `assets/unused/effects/heal_leaves_2026-09.png`. Rig `fx_heal`: frame
  128, anchor (64, 64) — the burst's origin on the spot, not the union's
  bottom, so the crosses rise *from* the sanctuary — paint (31, 0, 66, 95),
  36 frames at 15 fps. CREDITS: the Gigapack row now says what it is used
  for and carries the pack's own attribution line.
* Tests: `test_key_marker.py` 15 (chest lid for every tier, forge chimney,
  ring fallback); focused set 36 passed with the village paint-box test
  agreeing with the new strip. Contact sheets delivered: chests, forge,
  sanctuary across its loop.
* Full suite (imp editor-source test deselected, pre-existing): **2606 passed**, 9 deselected, 638 subtests, 13:43.

---

## Pass 4 — the pause menu's Controls block (owner, 2026-09-19)

> "confirm and propose the pause menu controls block"

### Confirmed reading

The first of the journal's "later passes": the pause menu shows the run's
bindings as keycaps -- a reference listing, not a prompt -- so a player who
forgot a key finds it without leaving the run. It follows the **chosen key
layout** (the Key layout row on the same screen swaps WASD and the
arrows), and it says what the run actually handles: move, aim (held),
attack (left click), interact (`KEY_INTERACT`), auto-attack toggle
(`KEY_TOGGLE_AUTO_ATTACK`), the build screen (TAB) and pause (ESC). Menu
keys (ENTER, the hint line's Up / Down) are not in it -- the hint line
already says them.

Decisions taken (say if you want them changed):

1. **Grey caps.** Pass 1 reserved blue for "press this now"; a listing is
   grey. The grey sheet only exists in the down position, so both of its
   states are one frame at the pressed face height; the block never shows
   a press.
2. **Words take the wide cap.** `TAB`, `ESC` and `CLICK` do not fit a
   32 px square; the 192×64 wide sheets drawn at 96×32 (an exact ×0.5, like
   the square) carry them. Any label longer than one character is wide.
3. **Arrows are drawn, not typed.** `Font.metrics` answers for ↑ ← ↓ →
   but neither bundled face has the glyphs -- they render as boxes -- so
   `keycap.draw_arrow` paints a pixel arrow (head + shaft, 12 design px)
   in the label ink, and the arrows layout reads as four small caps.
4. **The mouse is a wide cap that says `CLICK`.** There is no mouse
   glyph in the art; a labelled cap keeps the row in the same family as
   the others until one is cut (the "mouse glyph" later pass).
5. **Placement**: a column to the right of the buttons, left edge 340
   design px right of centre (the buttons end at +280), top level with the
   first button's top; heading "Controls" in the title face, rows on a
   44 px step, labels in the body face at 20 px. On a 21:9 render the box
   is centred and the column stays beside the buttons.

### Proposal

* `ui/keycap.py`: caps get a **colour** (`blue` | `grey`) and a **wide**
  form; `KEYCAPS` maps colour → state → (square rig, wide rig, face y).
  `cap_rect` / `label_center` / `draw_keycap` take `colour=` and `wide=`;
  `is_wide(label)`; `label_for` maps the arrow keys to arrow glyphs.
  `FACE_Y` stays the blue table the marker and its tests use.
* Art: `assets/ui/buttons/grey.png`, `grey_wide.png` brought in from
  `unused/`; rigs `keycap_grey`, `keycap_grey_wide`, and the already
  tracked wide blue pair as `keycap_blue_wide[_pressed]`.
* `ui/controls_block.py`: `rows(game)` from the layout and the bindings;
  `cluster_width`; `draw(surface, assets, topleft, game, ...)` → rect.
* `paused_state.py`: draws the block after the buttons at
  `(cx + 340, _ROW_TOP - 32)` with its own two fonts.
* Tests: `tests/screens/test_controls_block.py` (rows per layout, fixed
  rows from the bindings, wide words, grey frames, every row draws grey
  caps, the sheets load) and one pause test (the block is drawn once,
  right of every button, inside the screen).

### Todo

- [x] 1. `keycap.py` colours and wide caps; grey art and rigs.
- [x] 2. `ui/controls_block.py` and the pause hook.
- [x] 3. Tests; suite.
- [x] 4. Screenshots of the pause menu in both layouts; results here.

### Results (2026-09-19)

* Built as proposed. `ui/keycap.py` now carries `KEYCAPS` (colour → state
  → square rig, wide rig, face y), `is_wide`, `face_y`, `draw_arrow`; the
  marker's blue path is untouched (`FACE_Y` still the blue table).
* The first render showed the arrows as boxes: `Font.metrics` answers for
  the arrow code points but neither bundled face draws them. Arrows are
  now painted glyphs (head + shaft, 12 design px, label ink).
* `ui/controls_block.py`: seven rows; the Move / Aim clusters re-label
  from `config.KEY_LAYOUTS[game.key_layout]`, verified in both layouts.
* Pause menu: the block at `(cx + 340, 298)` design px, heading in the
  title face, rows on a 44 px step. Screenshots delivered for both layouts.
* Tests: `tests/screens/test_controls_block.py` 12 (rows per layout, fixed
  rows from the bindings, wide words, grey frames and face height, every
  row draws grey caps, the sheets load, an arrow is drawn not typed) and
  `test_the_controls_block_sits_right_of_the_buttons` in `test_pause.py`.
  Focused set (block, pause, keycap, marker): 49 + 37 passed.
* Full suite (imp editor-source test deselected, pre-existing): **2619 passed**, 9 deselected, 638 subtests, 14:42.

---

## Pass 5 — first-run movement hints, and the mouse glyph (owner, 2026-09-19)

> "prepare the first run movement hints and what glyph for the mouse
> would you use?"

### The mouse glyph

There is no mouse or cursor art in the tracked tree or the reserve:
`assets/ui/pointers/` holds only the cursor arrow, `unused/ui/pointers/`
the selection brackets, `unused/ui/icons/` cart / close / settings / sound
/ plus / minus / 1 2 3 / unlock, and the Gigapack's Symbols folder has no
cursor, hand or click. Three ways to show "click":

1. **The game's own cursor on a square cap** (recommended): the arrow the
   player is already pointing with (`ui/pointers/arrow.png`, 64 px, the
   shipped Tiny Swords cursor), cropped to its ink and drawn at ~18 design
   px on the grey / blue square cap where a letter would go. Shipped art,
   square like every other key, and it is literally the thing they click
   with.
2. A code-drawn mini mouse (rounded outline, split top, left button
   filled), like the arrows are drawn -- honest but a new shape in a game
   whose UI is otherwise all pack art.
3. Keep the wide `CLICK` word (what ships today).

Proposal: (1), as `keycap.MOUSE` -- a label constant the cap draws as the
cursor glyph, the way `ARROWS` are drawn -- used by the Controls block in
place of `CLICK` and by the attack hint below.

### What "first-run movement hints" means

The save has no run counter (`SaveData` holds currency, unlocks, meta,
best / records, stash, settings, heroes), so "first run" is a flag of its
own: `settings["hints_done"]`, set once the hints have run their course.
Until then every run opens with the hints; in the browser build (no save)
that is every run, which is right for a page a stranger opens.

Two hints, one after the other, each a cluster of **blue** caps -- these
are "press this now" prompts, and blue has the pressed frame, so each cap
**sinks while its key is actually held**, which is the teaching:

1. **Move** — the layout's four move keys as a keyboard-shaped cluster
   (W above, A S D below, or the four arrows) with the word "Move" beside
   it, floating above the hero's head and following them. Done once the
   hero has travelled 96 world px (three tiles) from the spawn.
2. **Attack** — after Move: the mouse cap ("Attack") beside the aim
   arrows ("Aim"), same place. Done on the first attack the player aims
   (a click, or an aim key held), or after 8 s -- auto attack is on by
   default, so the hero may already be fighting.

There is no Interact hint: the floating `E` over a chest is already that.
The block goes away for good when both are done (`hints_done`), or at
once on ESC → the pause menu, which lists everything anyway.

Placement: like the key marker, anchored to the **hero's drawn art** --
the sprite frame's ink top from `renderer.hero_sprite_frame()` and its
anchor -- the cluster's bottom 6 px above it, so it clears the helmet on
every hero. Drawn after the world, inside the shake offset, before the
HUD. It fades over its last 0.4 s rather than vanishing.

### Proposal

* `game/states/playing/core/hints.py`: `FirstRunHints(ps)` — `stage`
  (`"move"` / `"attack"` / `None`), `spawn`, `timer`, `update(dt)` with
  the completion checks, `dismiss()`; sets `game.save.settings["hints_done"]`
  and saves. `config.FIRST_RUN_HINTS = True` master switch; the dev menu
  gets a "Replay hints" row that clears the flag.
* `game/states/playing/visual/hints.py`: `draw(surface, ps)` — the
  cluster layout, `keycap.draw_keycap(..., colour="blue",
  state="pressed" if held else "raised")` per key, the word in the body
  face with the shadowed style the notice uses, alpha over the fade.
* `ui/keycap.py`: `MOUSE` label drawn as the cursor glyph.
* `ui/controls_block.py`: Attack row uses `keycap.MOUSE`.
* Tests: `tests/playing/test_first_run_hints.py` — a fresh save shows
  Move; travelling 96 px moves on to Attack; a click or a held aim key
  completes it; the timeout completes it; the flag persists and the next
  run shows nothing; ESC dismisses; the cluster sits above the hero's
  art; a held move key draws its cap pressed. `test_controls_block.py`:
  the Attack row is the mouse glyph, square not wide.

### Change of rule (owner, 2026-09-19)

> "change the hints behavior to show for every run, however add an option
> to the options menu to turn off tutorials and control this visibility
> there"

So: no `hints_done` flag, no first-run gating, no dev-menu replay row.
**Every run opens with the hints**; the player switches them off with a
**Tutorials** row in Options (`settings["tutorials"]`, on by default,
persisted like the other settings, shown in the in-run Options too). A
hint still ends early within a run once its action is done -- that is the
per-run courtesy, not persistence. The mouse glyph: option 1 (the cursor
arrow on a square cap), no objection raised.

### Todo

- [x] 1. `keycap.MOUSE` (cursor glyph on a cap); Controls block uses it.
- [x] 2. `core/hints.py` stage machine; `config.TUTORIAL_HINTS`;
      `settings["tutorials"]`, `game.tutorials` / `set_tutorials`.
- [x] 3. `visual/hints.py` drawing, hooked after the key marker.
- [x] 4. Options "Tutorials" row (replaces the dev-menu replay row).
- [x] 5. Tests; suite; screenshots of both hints; results here.

### Results (2026-09-19)

* `ui/keycap.py`: `MOUSE` label drawn as the game's cursor
  (`config.UI_CURSOR_IMAGE` cropped to its ink, 20 design px tall on the
  cap), cached per size; `MOUSE_WORD = "CLICK"` when the file is missing;
  `is_wide` keeps it square. The Controls block's Attack row uses it.
* `game/states/playing/core/hints.py`: `RunHints` -- `stage` (`move` →
  `attack` → None), `spawn`, `t`, `fading` (the finished clusters and the
  seconds left), `update`, `dismiss`, `clusters(stage)` (the keyboard-shaped
  cluster: up over left / down / right, from the layout), `keycodes_for`,
  `held` (keys and the left button, False headless). Built at the end of
  `PlayingState.enter` (it reads the hero's spawn), ticked after
  `_phase_input` so it sees this frame's `_aim`, dismissed on ESC.
* `game/states/playing/visual/hints.py`: `hero_top` (the sprite's ink top
  from the same anchor / drop maths the hero painter uses), `layout`, `draw`
  -- blue caps, pressed while held, the word shadowed in the body face at
  18 px; a fading stage is drawn on a full-size SRCALPHA layer with
  `set_alpha`, the next stage waits for it. Drawn right after the key
  marker.
* Config: `TUTORIAL_HINTS`, `HINT_MOVE_DISTANCE = 96`,
  `HINT_ATTACK_SECONDS = 8`, `HINT_FADE = 0.4`. Save: `settings["tutorials"]`
  defaults True. Options: row "Tutorials" after Key layout, ENTER / Left /
  Right / click toggle it; ten rows now, so `_ROW_TOP, _ROW_STEP` went from
  200 / 74 to 180 / 68 to keep the last row clear of the hint line.
* Tests: `tests/playing/test_run_hints.py` 19 -- opens on Move, arrows
  layout, Tutorials off / build switch off show nothing, three tiles moves
  on (and starts the fade), an aimed attack finishes Attack (auto-aim does
  not), the timeout, the fade running out, ESC dismisses, the whole update
  ticks it, held keys / mouse read through; the setting persists and
  defaults on; the Options row toggles and persists and is in the in-run
  rows; four blue caps over the hero (bottom `CLEAR_PX` above the art top,
  centred), the hero top is above the collider, a held key sinks its cap,
  the Attack stage shows mouse + arrows, a fading stage is translucent then
  gone, a whole frame reaches the hints. `test_controls_block.py` +2 (the
  mouse cap draws the cursor; says CLICK without the file);
  `test_options.py` renamed to ten rows; `test_key_marker.py`'s whole-frame
  test dismisses the hints first. Focused set: 157 passed.
* Screenshots delivered: the six hint states and the Options screen.
* Full suite (imp editor-source test deselected, pre-existing): **2640 passed**, 9 deselected, 638 subtests, 11:44.
