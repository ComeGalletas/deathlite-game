# Hero-select sprite preview — execution journal

**Legacy ID:** UI-002 · **Systems:** UI · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

## Requirement (owner, 2026-09-12)

Review the character-sprite preview on the character-select screen and change
the sprites so they **match the in-game size of each hero**. Confirm the
approach before writing code.

---

## Review of what shipped before this change

`CharacterSelectState._draw_preview` scaled every hero into one hand-tuned box:

```python
_PREVIEW_PX = 130                       # box height, same for all heroes
_PREVIEW_W  = _PREVIEW_PX + 30          # box width, same for all heroes
_PREVIEW_ADJUST = {"nihil": (24, 0), "kestrel": (-18, 0)}   # per-hero fudge
frame = self._preview.frame(size=(_PREVIEW_W + dw, _PREVIEW_PX + dh))
```

`Assets.frame(size=…)` is a hard `pygame.transform.scale`, not a fit, so the
cropped art was **stretched** into that box. Two things were wrong:

**1. Aspect ratio.** In-game, `RenderPipeline.hero_sprite_frame` draws each rig
at its authored `scale` from `data/character_sprites.json` (times the camera
zoom), and that `scale` preserves the rig's `content` crop ratio. The preview
box did not:

| hero | in-game `scale` | in-game aspect | old preview box | old aspect | error |
|---|---|---|---|---|---|
| Aegis | 46×43 | 1.07 | 160×130 | 1.23 | 15% too wide |
| Kestrel | 37×38 | 0.97 | 142×130 | 1.09 | 12% too wide |
| Nihil | 56×33 | 1.70 | 184×130 | 1.42 | 17% too narrow |

Nihil was the worst case: a wide, low sprite squeezed upright.

**2. Relative size.** All three previewed at exactly 130 px tall, while in-game
their heights are 43 / 38 / 33 — Kestrel is 12% shorter than Aegis and Nihil
23% shorter. The select screen gave no hint of that.

The per-hero `_PREVIEW_ADJUST` table was a symptom: it existed only to hide the
distortion the fixed box created.

---

## Confirmed decisions (owner, 2026-09-12)

* **Size — each hero's own in-game `scale` × 3.0.** One shared multiplier, no
  per-hero table; aspect ratios and relative heights then come straight from
  the game data. 3.0 is exactly 2× `config.CAMERA_ZOOM` (1.5), so a preview is
  the in-game sprite at double size. Results: Aegis 138×129, Kestrel 111×114,
  Nihil 168×99 — the tallest still fits the 130 px band, so the difficulty
  ribbon, the Begin button and the instruction block do not move.
* **Alignment — feet on one shared ground line.** Each sprite is placed by its
  rig `anchor` (the same feet point `RenderPipeline.anchor_for` uses in-game),
  so short Nihil reads as short instead of floating. The baseline is fixed for
  all heroes, so arrowing between cards does not make the ground move.

Rejected: drawing at the literal in-game on-screen size (`scale` × 1.5) left
the band half empty; ×4 would have pushed the whole lower block down ~45 px.

---

## Implementation

`game/states/character_select_state.py`:

* `_PREVIEW_W` and `_PREVIEW_ADJUST` deleted. `_PREVIEW_PX` stays as the height
  of the band the layout reserves between the cards and the ribbon.
* `_PREVIEW_ZOOM = 3.0` added.
* `_preview_baseline()` computes the shared ground line once per screen: it
  takes the largest above-feet extent (`anchor_y × zoom`) and the largest
  below-feet extent (`(scale_y − anchor_y) × zoom`) across every hero rig and
  centres that group in the band. Driven by the data, so a new hero or a
  re-authored `scale` moves the line automatically.
* `_draw_preview` sizes the frame as `scale × _PREVIEW_ZOOM` and places it by
  `midbottom = (cx, baseline + below_feet)`.

Tests: `tests/rendering/test_hero_select_preview.py` pins the aspect ratio
against `Assets.scale_for`, the relative heights, and the shared baseline.

## Status

* 2026-09-12 — reviewed, decisions confirmed, implemented, tests added.

---

## Follow-up: the instruction block's pixel height (2026-09-12)

`tests/rendering/test_menu.py::CharacterSelectInstructionsTests::test_content_comes_from_config`
was failing `743 != 742`. `_draw_instructions` opens its block at
`y = top - 20` and then steps by `self._instr.get_linesize()`, which is
**21** for that face — so the literal 20 was standing in for a line height it
does not equal, and the whole block (plus the hint the caller anchors under
`instr_bottom`) sat one pixel low. The commit that introduced it,
"Hero select: instruction rows start one line higher", meant *one line*, not
twenty pixels.

Fixed by measuring instead of guessing: `y = top - line_h`. With two notes
the block now returns exactly `top + 2 × line_h`, which is what the test
derives from the font.

The owner's constraint was explicit — "don't change the order of the
instructions just the pixel height" — and nothing else moved: the same loop
still draws the free notes first and the key-bindings row last, and the
function still returns the y of that last line. Verified at 1280x720:
`_draw_instructions(surface, 640, 500)` returns 542 = `500 + 2 × 21`.

`tests/rendering/test_menu.py`: 84 passed.
