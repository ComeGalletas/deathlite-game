# Sprite Functionality

This document explains how PNG files become displayed sprites in the game. The system is shared by heroes, enemies, obstacles, terrain decorations, projectiles, and menu artwork.

## Overview

The sprite pipeline has four layers:

1. JSON metadata identifies a sprite rig, its PNG files, frame dimensions, animation timing, crop rectangle, display scale, anchor, and facing direction.
2. `game.assets.Assets` loads PNG files lazily, converts them into Pygame surfaces with alpha, slices animation strips, applies optional transformations, and caches the results.
3. `systems.animation.Animator` tracks elapsed animation time and selects the current frame. It does not load files or draw anything.
4. Gameplay draw methods convert world coordinates to screen coordinates and blit the selected surface, or use a primitive fallback when the sprite is unavailable.

The main implementation files are:

- `game/content.py`: loads JSON data from `data/`.
- `game/assets.py`: loads, slices, transforms, and caches PNG surfaces.
- `systems/animation.py`: advances animation time and selects frame indexes.
- `data/character_sprites.json`, `data/enemy_sprites.json`,
  `data/weapon_sprites.json`, `data/prop_sprites.json`: sprite rig metadata,
  split by domain and merged into one namespace by `game/content.py`. A rig
  shared by two domains (e.g. `dead`) is copied verbatim into both files.
- `data/terrain.json`: terrain and decoration rig metadata.
- `game/states/playing_state.py`: creates animators and draws gameplay sprites.
- `entities/enemy.py`: creates enemy animators and changes enemy animation states.

## Metadata and Sprite Rigs

A rig is a named metadata entry. For example, `hero_aegis` in `data/character_sprites.json` contains:

```json
"hero_aegis": {
  "frame": [192, 192],
  "content": [43, 44, 120, 112],
  "scale": [46, 43],
  "anchor": [22, 35],
  "face": "right",
  "anims": {
    "idle": {
      "file": "characters/blue/warrior/idle.png",
      "frames": 8,
      "fps": 8,
      "loop": true
    }
  }
}
```

The fields mean:

- `frame`: source frame width and height. The loader expects the PNG to be a horizontal strip whose width is `frame_width * frame_count` and whose height is `frame_height`.
- `content`: optional crop rectangle inside every source frame, expressed as `[x, y, width, height]`. It removes transparent margins supplied by the art pack.
- `scale`: optional final display size passed to Pygame scaling.
- `anchor`: pixel coordinate in the final displayed frame that is placed at the entity's world position. This is normally near the character's feet or ground contact point.
- `face`: the art's default facing direction. Gameplay can horizontally flip the frame when the entity faces the opposite way.
- `anims`: animation names mapped to PNG files and timing settings.
- `frames`: number of frames declared in the strip.
- `fps`: animation playback rate.
- `loop`: whether the animation wraps around or stops at its last frame.

Terrain decoration rigs use the same asset API. Their metadata is merged into the sprite namespace by `Assets.meta`, so character rigs and terrain rigs follow the same loading rules.

## Content Loading

`game/content.py` loads all JSON files through `get_content()`. The content object exposes `sprites` and `terrain` dictionaries. JSON is loaded once and cached in a process-wide singleton.

`game.assets.get_assets()` provides a separate process-wide `Assets` singleton. Its metadata is loaded lazily. When first accessed, it combines:

```python
self._meta = {**c.sprites, **c.terrain.get("rigs", {})}
```

This gives `Assets` one common lookup path for gameplay and terrain rigs.

## PNG Loading

The low-level PNG load happens in `Assets._load_image()` in `game/assets.py`.

```python
full = ASSETS_DIR / rel_path
self._sheets[rel_path] = pygame.image.load(str(full)).convert_alpha()
```

`ASSETS_DIR` points to the repository's `assets/` directory. The relative path comes from JSON metadata, for example `characters/blue/warrior/idle.png`.

Important behavior:

- Files are loaded only on first request.
- Loaded surfaces are stored in `_sheets`, keyed by relative path.
- `convert_alpha()` prepares the image for fast display while preserving transparency.
- Missing files and Pygame image errors return `None` instead of crashing gameplay.
- Each missing path is logged only once through `_warned`.
- Later callers receive the cached surface or cached `None` result.

A display must already exist before this operation because `convert_alpha()` depends on the initialized Pygame display. This is why gameplay and menu code request assets during rendering or after game initialization rather than importing PNGs at module load time.

## Animation Strip Slicing

Animated rigs are built by `Assets._build_frames()` and requested through `Assets.frames()` or `Assets.frame()`.

For each frame index `i`, the loader calculates:

```python
rect = pygame.Rect(i * fw, 0, fw, fh)
```

This means frames are laid out horizontally in the PNG. The loader stops if the declared rectangle falls outside the PNG, which prevents an out-of-range subsurface error. A valid frame is then:

1. Taken as a subsurface of the loaded sheet.
2. Cropped using the rig's `content` rectangle, if present.
3. Copied into its own surface.
4. Horizontally flipped if requested.
5. Scaled to the requested size if one was supplied.
6. Stored in the returned frame list.

The copy step is important because the final frame should not remain tied to the parent PNG surface through a subsurface view.

The loader uses `pygame.transform.scale()` for sprite scaling. This is a nearest-neighbor style scale suitable for the project's pixel-art sprites.

The complete transformed frame list is cached using:

```python
(rig, anim, size, flip)
```

As a result, slicing, cropping, flipping, and scaling are performed once for each unique request, not once per rendered frame.

## Selecting the Current Animation Frame

`Animator` in `systems/animation.py` owns only animation state:

- `rig`: which metadata rig is being used.
- `anim`: current animation name such as `idle`, `walk`, `hurt`, or `death`.
- `t`: elapsed time in the current animation.

Gameplay advances the timer with:

```python
animator.update(dt)
```

The frame index is calculated from elapsed time and FPS:

```python
raw = int(self.t * self.assets.fps(self.rig, self.anim))
```

For looping animations:

```python
index = raw % frame_count
```

For one-shot animations:

```python
index = min(raw, frame_count - 1)
```

Therefore a looping walk animation wraps back to frame zero, while a death animation remains on its final frame after it finishes. `Animator.finished` reports when a non-looping animation has reached its end.

Changing animation names resets time only when the name changes, or when `play(..., restart=True)` is used. This prevents an idle or walk animation from restarting every update tick.

## Player Sprite Flow

`PlayingState.enter()` reads the selected character's `sprite` field from `data/characters.json` and creates an animator:

```python
hero_rig = cdef.get("sprite")
self._hero_anim = Animator(self.game.assets, hero_rig) if hero_rig else None
```

The player animation state is selected by gameplay code and advanced with `dt`. During rendering, `_hero_sprite_frame()`:

1. Gets the current rig.
2. Checks the player's facing direction.
3. Horizontally flips the frame when the metadata's default facing and current facing differ.
4. Requests the configured display scale from `Assets.scale_for()`.
5. Gets the current frame from `Animator.frame()`.

`_draw_player()` then obtains the rig anchor and blits the frame at:

```python
(sx - anchor_x, sy - anchor_y)
```

Here, `(sx, sy)` is the player's world position converted through the camera. The anchor makes the art's ground-contact point stay aligned with the player's gameplay position even when the visible sprite is much larger than its collision circle.

If there is no player rig, or if loading the rig fails, the player is drawn as a colored Pygame circle instead.

## Enemy Sprite Flow

An enemy receives an animator only if its definition in `data/enemies.json` contains a `sprite` rig:

```python
rig = definition.get("sprite")
self.anim = Animator(get_assets(), rig) if rig else None
```

During `Enemy.update()`:

- A dead enemy selects `death`.
- A recently damaged enemy selects `hurt`.
- A moving enemy selects `walk`.
- A stationary enemy selects `idle`.
- Facing is updated from the enemy's horizontal relationship to the player.
- The animator timer advances by `dt`.

`PlayingState._draw_enemy_sprite()` requests the current frame with the configured scale and optional horizontal flip, obtains the anchor, and blits it relative to the enemy's screen position.

Enemies without a usable rig fall back to a primitive colored circle. Sprited enemies that die are moved to the render-only `_dying` list so their death animation can finish before the object disappears.

## Terrain and Obstacle Decoration Sprites

Terrain decoration rigs are declared in `data/terrain.json` rather than the `*_sprites.json` files. They still use `Assets.frames()` and the same rig concepts.

Examples include:

- `deco_tree_1` through `deco_tree_4`.
- `deco_bush_1` through `deco_bush_4`.
- `deco_rock_1` through `deco_rock_4`.
- Water rocks and the duck.
- Terrain foam.

`world/map.py` resolves these frames when it builds the map's visual caches. It stores pre-scaled frame lists and anchors for later rendering. Animated decorations calculate their current frame from Pygame time and then blit using their world position and anchor.

Obstacle decoration is separate from obstacle gameplay collision:

- The obstacle has a circular gameplay radius.
- The decoration rig is selected by obstacle kind and cosmetic variant.
- The source footprint controls how the sprite is scaled visually.
- The final sprite is anchored to the obstacle's world position.
- A missing rig or missing PNG falls back to a primitive circle.

## Projectiles and Rotated Images

Animated strips are not used for the arrow projectile. The arrow is a single-image rig in `data/weapon_sprites.json`:

```json
"arrow": {
  "file": "projectiles/arrow.png",
  "frame": [32, 32],
  "content": [6, 12, 21, 9],
  "scale": [30, 13],
  "anchor": [15, 6]
}
```

`Assets.image()` loads and optionally crops, flips, scales, or tints this single PNG. The result is cached in `_frames` using:

```python
("<image>", rig, size, flip, tint)
```

Enemy and boss projectile rendering calls `Assets.rotated()`. Rotation is quantized into eight-degree buckets:

```python
bucket = round(degrees / ROTATION_BUCKET_DEG) * ROTATION_BUCKET_DEG
```

The rotated surface is cached by rig, size, tint, and bucket. This prevents a new transformed surface from being created for every projectile on every frame.

If the arrow file cannot be loaded, projectile rendering falls back to a colored circle.

## Menu and Standalone Images

`Assets.picture()` handles whole PNG files that are not sprite strips, such as the menu title image. It loads through the same `_load_image()` path and optionally uses `pygame.transform.smoothscale()` for UI artwork. The scaled result is cached by path and requested size.

## Draw Order and Coordinates

The camera stores its top-left position in world coordinates. Sprite draw code converts an entity position with:

```python
sx, sy = camera.world_to_screen(entity.pos)
```

The final blit uses the anchor so that the sprite's designated ground-contact pixel matches the entity position.

In the active gameplay renderer, the broad order is:

1. Terrain and water.
2. Water scenery and ground effects.
3. Room decorations.
4. Interactables, hazards, pickups, and explosions.
5. A Y-sorted layer containing obstacles and characters.
6. Projectiles, particles, and damage numbers.
7. HUD and screen overlays.

The Y-sorted layer uses each object's ground-contact world Y coordinate. Objects with a larger Y are drawn later and appear in front of objects above them. This is why anchored trees, enemies, and characters can overlap naturally.

## Fallback Behavior

The system is intentionally tolerant of incomplete art content:

- Missing or unreadable PNG: `None` from `Assets._load_image()`.
- Missing rig or animation: `None` from frame lookup.
- Character or enemy with no valid frame: primitive circle rendering.
- Arrow with no valid PNG: primitive projectile circle.
- Missing terrain tile: terrain renderer uses its configured flat fallback.

The fallback policy means content errors are visible but do not normally terminate a run.

## Caching Summary

There are three relevant cache levels:

| Cache | Key | Stores |
|---|---|---|
| `_sheets` | Relative PNG path | Loaded source PNG surface or `None` |
| `_frames` for animation | Rig, animation, size, flip | Sliced, cropped, flipped, scaled frame list |
| `_frames` for images | Marker, rig, size, flip, tint | Cropped, transformed single-image surface |
| `_rot` | Rig, size, tint, rotation bucket | Rotated projectile surface |

`reset_assets()` clears the process-wide asset singleton and is used by tests to isolate cache behavior.

## Validation and Test Coverage

The existing tests cover the main loader contract:

- Sprite metadata rigs exist.
- Declared PNG files exist.
- Strip dimensions match frame metadata.
- Every declared frame can be sliced.
- Content cropping produces the expected dimensions.
- Requested scaling produces the expected dimensions.
- Looping animations wrap.
- One-shot animations clamp to the final frame.
- Frame lists and transformations are cached.
- Horizontal flipping produces a distinct cached result.
- Missing rigs and files return `None`.
- Missing files log only once.
- Single-image loading, scaling, tinting, and rotation are cached.
- Anchor, facing, frame-count, FPS, and loop metadata are read correctly.
- Enemy animation state changes and render-only death animation behavior work.

The most important content authoring invariant is that every animated PNG must be a horizontal strip whose dimensions agree with its rig metadata. If that invariant is broken, the loader may stop early when it reaches a frame rectangle outside the source PNG.

## Practical Content-Authoring Checklist

When adding a new animated sprite:

1. Place the PNG under `assets/`.
2. Add a rig entry to the matching `data/*_sprites.json` file (or `data/terrain.json`).
3. Set the correct source `frame` dimensions.
4. Set the exact horizontal `frames` count.
5. Set `fps` and `loop` behavior.
6. Add `content` if the source has large transparent margins.
7. Set the final `scale` for gameplay readability.
8. Set an anchor at the intended ground-contact point.
9. Set `face` if gameplay should flip the sprite.
10. Connect the rig to the relevant character, enemy, obstacle, or decoration definition.
11. Run the asset and animation tests.

No code changes are required for a new asset that fits an existing consumer and rig format. New animation behavior, draw layering, or special transformations may require Python changes.

## Seeing Characters Behind Obstacles (proposed and implemented, 2026-09-03)

> Implemented the same day as written, as laid out below; the journal
> entry with the measurements is in `journals/journal.md`. Originally: The hero and the enemies vanish behind a tree
> crown, a house or a pillar the moment their ground-contact Y sorts below
> the obstacle's, because the depth pass paints the obstacle's art over
> them. The ask: keep them visible through the obstacle as a translucent
> silhouette, and only there -- a character in the open is drawn as today.

### What the effect is

Two things could be made translucent, and they read very differently:

- **The obstacle** goes see-through where it covers a character. Common in
  top-down games, but it changes the prop's look every time someone walks
  past it, the canopy flickers as bodies cross it, and a tree that four
  enemies are walking behind becomes a ghost of itself.
- **The character** is drawn again *through* the obstacle at reduced alpha.
  The obstacle stays as painted, the covered part of the body shows as a
  tinted silhouette on top of it, and the uncovered part is unchanged.

The second is what the ask describes ("an alpha transparency to
characters ... when going behind obstacles only"), and it is the cheaper
one: nothing about the obstacle draw changes, and only the covered
characters get a second, clipped blit.

### Where it plugs in

`PlayingState._draw_world` paints the world one terrace band at a time:
the ground, the flat effects, then the band's depth-sorted items (obstacle
skins, decor, tree shades and the characters standing on that terrace) in
ground-contact-Y order. A character is hidden when an obstacle whose Y is
greater than the character's (drawn later) has art that covers the
character's frame.

Every character blit already goes through one place,
`WorldRenderer._blit_character(surface, frame, dest, character_y)` (which
is also where the tree shades are applied). The proposal adds one record
there and one pass afterwards:

1. **Record.** `_blit_character` appends `(frame, dest, character_y)` to a
   per-frame list on the renderer. That is the exact surface and screen
   position just drawn -- shaded, tinted, flipped -- so the ghost matches
   the body pixel for pixel. The list is cleared at the top of
   `_draw_world`.
2. **Ghost pass.** At the end of `_draw_world`, after every band, one
   pass walks the recorded characters, finds the obstacle art that covers
   each one and sorts in front of it, and blits the frame again at the
   ghost alpha, **clipped to the covering art's rectangle** so the
   uncovered part of the body is not drawn twice.

The pass runs after all bands rather than per band on purpose: a
character on a low terrace is also covered by an obstacle standing on the
terrace above (painted in a later band), and one pass at the end sees
both.

### Finding the occluders cheaply

The obstacle skins are static once baked (`obstacle_skins.py` fills
`GameMap._decos[i] = (ax, ay, fps, frames, phase)`), so their art
rectangles in world space are known at bake: anchor-relative, from the
frame size and the same `sprite_drop` seat `_draw_one_obstacle` uses.
Bucket them in a coarse world grid exactly as the tree shadows are
(`TerrainRenderer._shadow_index`, 256 px cells), keyed by obstacle index,
and query the character's world footprint. This is the same shape as the
shade index and costs the same: a handful of rectangle tests per drawn
character, no per-frame allocation.

For each candidate obstacle `i` with position `o`:

- it occludes only if `o.pos.y > character_y` (it was painted after the
  body) -- the ordering rule the depth pass already uses, so a character
  standing in *front* of a tree is never ghosted through its trunk;
- its screen art rect (from the index, transformed by the camera the way
  `_draw_one_obstacle` does) must intersect the character's frame rect;
- its kind must be in the data's list -- trees, houses, rocks and pillars
  cover bodies; signs and scarecrows are too thin to hide anyone and
  should not ghost.

Animated skins (the routine trees) change frame but not rectangle, so the
index needs no per-frame update.

### The ghost blit

A ghost is the character's frame with its alpha scaled. Do not call
`set_alpha` on the animation frame: it is the asset cache's own object and
every other user would inherit the alpha. Make a copy with the alpha
multiplied in (`BLEND_RGBA_MULT` with `(255, 255, 255, alpha)` on an
SRCALPHA copy, so the silhouette's own edges stay soft) and cache it by
`id(frame)` the way `hit_tinted` caches the red flash: a 0.26 s hurt
window is a few frames, and a walk cycle is a handful, so the cache stays
small and the copy is made once per frame object.

Then, per covering obstacle:

    surface.set_clip(art_rect.clip(frame_rect))
    surface.blit(ghost, dest)
    surface.set_clip(None)

Two obstacles covering one body give two clipped blits; they can overlap
where the obstacles overlap, which double-ghosts a sliver -- acceptable,
or union the rects first if it shows. The tint of the ghost is a data
choice: plain alpha reads as "the same body, through the leaves"; a light
colour wash (blend the ghost toward the hero's accent colour, or a fixed
outline colour for enemies) reads as an X-ray. Start with plain alpha.

### Data

One block in `data/terrain.json` under `obstacle_decor`, since it is a
property of the obstacle art:

    "ghost": {
      "alpha": 110,
      "kinds": ["tree", "house", "rock", "pillar"]
    }

`alpha` 0 switches the pass off. Per the project's rule there is no
default in code: a missing block means no ghosting.

Who gets ghosted: the hero, the enemies, the boss and the death poofs all
go through `_blit_character`, so all of them, for free. The hero's own
summons draw through `draw_summon`, not `_blit_character`; leave them out
unless it shows in play.

### Cost

Per drawn character: one index query (a few dict reads) and up to a
couple of rectangle tests. Per covered character: one cached copy the
first time its frame is seen and one clipped blit per covering obstacle.
The render pass today is ~3.5 ms for the world plus ~0.1 ms per body in
view (after the culling and shade-index work in `fluidity_plan.md`
section 7); this adds well under a millisecond with a crowd under the
trees and nothing when no one is covered.

### Tests

- A character behind a tree (Y below the tree's, frame under its crown)
  produces exactly one extra blit, clipped to the crown's rectangle; the
  pixels of the body outside the crown are unchanged.
- A character in front of the same tree (Y above) produces none.
- A character under a sign produces none (kind not listed).
- The ghost is the shaded / tinted frame, not the raw one (a hurt enemy
  ghosts red).
- `alpha` 0 in the data disables the pass; a missing block disables it.
- The frame digest (`tests/world/test_digest.py`) is unaffected: the digest
  frame has no characters.

### Order of work

1. Bake the obstacle art index next to the tree-shadow index
   (`obstacle_skins.py` knows every rectangle it draws).
2. Record character blits in `_blit_character`; the ghost pass at the end
   of `_draw_world`.
3. The cached alpha copy, the data block, the kind filter.
4. Tests, then a screenshot with the hero under a crown for the journal.

About a day.

## The Warlock's Spell Art (checked, proposed, then built -- 2026-09-03)

> Built the same day; what shipped differs from the proposal where the
> owner steered it, and the differences are recorded at the end. Asked: how the warlock renders its attack, how
> the circle indicator is drawn, and what it would take to use
> `hex_shaman_explosion_spell` as the attack's animation.

### What renders today, in three parts

**1. The caster animates already.** `warlock` wears the `hex_shaman` rig,
and `Enemy._anim_name()` returns `"attack"` for the whole
`telegraph` + `attack` window (`Enemy._attacking`). Traced in a run: the
warlock leaves `chase` at t = 3.20 s, enters `telegraph`, and plays
`enemies/hex_shaman/attack.png` -- 10 frames at 14 fps, 0.714 s -- against
a `cast_telegraph` of 0.8 s. The strip very nearly fills the wind-up, so
nothing needs doing to the caster itself.

**2. The pool is drawn procedurally -- there is no art in it at all.**
`WorldRenderer.hazards` is the whole indicator:

    frac = hz.life / hz.max_life
    rr   = hz.radius * zoom
    disc  = circle(hz.color + alpha(70 * frac + 20), rr)   # translucent fill
    ring  = circle(hz.color, rr, width=2)                  # hard edge

`hz.color` defaults to `(200, 90, 220)` -- `Hazard` takes a `color`
argument and `TransientFx.spawn_hazard` never passes one, so every pool in
the game is the same purple. The fill fades as the pool expires; the ring
does not. It is drawn in the flat-effects layer, filtered per terrace
band, so it sits under the characters standing on its own floor.

`Hazard.__slots__` is `pos, radius, dps, life, max_life, color,
tick_interval, _tick_accum`. **There is no sprite, animator or frame index
anywhere on it**, and `spawn_hazard(pos, radius, dps, duration,
tick_interval)` has nowhere to pass one.

**3. The wind-up shows nothing on the ground.** The only telegraph
indicator in the enemy painter is

    if e.telegraphing and "slam_radius" in e.cfg:      # rendering.py:261

which is the brute's slam. The warlock's key is `hazard_radius`, so the
condition is false and **nothing marks where the pool will land** during
the 0.8 s wind-up. Worse for reading it: the landing spot is snapshotted
from the player's position at wind-up *start* (`fsm_warlock`'s
`on_windup_start`), so the player who walks away is already safe and the
player who stands still gets no warning. The caster's own animation is the
only cue, and it is on the caster, not on the ground.

### The art that exists

| file | size | frames | referenced by |
|---|---|---|---|
| `hex_shaman/attack.png` | 1920x192 | 10 @ 192 | the `hex_shaman` rig |
| `hex_shaman/hex_shaman_explosion_spell.png` | 1920x192 | 10 @ 192 | **nothing** |
| `hex_shaman/explosion.png` | 1152x128 | 9 @ 128 | nothing |
| `hex_shaman/projectile.png` | 384x128 | 3 @ 128 | nothing |
| `hex_shaman/hex_shaman_transformation_spell.png` | -- | -- | nothing |

The spell sheet is laid out exactly like the shaman's own attack strip,
so it needs no special slicing. One number is a happy accident worth
keeping: `hazard_radius` is 92, so the damage circle is **184 px** across,
and a spell frame is **192 px**. Drawn at its native size the art lands
within 4 % of the circle it is meant to represent.

### Proposal

Give the hazard an optional rig and let the renderer animate it. Three
small pieces, in the project's usual order (data -> entity -> painter).

**1. A rig entry** in `data/enemy_sprites.json`, alongside `hex_shaman`:

    "hex_shaman_explosion_spell": {
      "frame": [192, 192],
      "anchor": [96, 96],          // centre: a pool is placed by its middle
      "scale": [184, 184],         // == 2 * hazard_radius
      "anims": { "loop": { "file": "enemies/hex_shaman/hex_shaman_explosion_spell.png",
                           "frames": 10, "fps": 14, "loop": false } }
    }

`anchor` at the centre rather than at the feet, because a hazard is placed
by its centre, not seated on the ground like a character. `scale` is the
damage diameter, so the art can never disagree with the circle: if
`hazard_radius` is retuned, this follows it (and a test should pin that
the two agree).

**2. One data key and one parameter.** `data/enemies.json` `warlock`
gains `"hazard_sprite": "hex_shaman_explosion_spell"`; `fsm_warlock`
passes it in the `haz` tuple it already builds; `spawn_hazard` and
`Hazard.__init__` take a `sprite=None`; `Hazard.__slots__` gains
`sprite` and `spawned_at`. No per-entity default in code -- a hazard with
no `hazard_sprite` keeps today's bare circle, which is what the boss's own
pools should keep unless someone gives them art too.

**3. The painter.** `WorldRenderer.hazards` picks the frame from the
pool's age rather than an `Animator`, the way the obstacle skins do
(`_draw_one_obstacle` indexes `frames[(seconds * fps + phase) % len]`):
the hazard is not an actor and does not need per-instance animation
state. Roughly

    age   = hz.max_life - hz.life
    i     = min(len(frames) - 1, int(age * fps))   # one-shot: hold the last
    blit(frames[i], centred on hz.pos, scaled by zoom)

then the existing ring on top.

### The three decisions this needs

- **One-shot or looping.** The strip is 10 frames at 14 fps = 0.71 s; the
  pool lives 3.5 s. An explosion reads as a one-shot, so the proposal
  holds the final frame for the remaining 2.8 s. If the last frame is not
  a stable "lingering" pose, the alternatives are to loop the whole strip
  (reads as a pulsing pool) or to loop a tail slice (frames 6-9, say).
  **Look at the sheet before choosing**; this is an art question, not a
  code one.
- **Does the art replace the ring or join it?** Keep the ring. The filled
  disc can go -- the art is the fill now -- but the hard 2 px edge is the
  only thing that states the damage radius exactly, and a player standing
  one pixel outside a soft explosion needs to know they are safe. I would
  drop the translucent disc, keep the ring, and let the ring keep
  `hz.color`.
- **The fade.** The disc currently fades with `life`, which is the only
  cue that a pool is about to expire. A held final frame does not fade. I
  would fade the sprite's alpha over the last ~0.5 s so the pool still
  announces its own end.

### Worth doing at the same time, separately

**The wind-up should mark the ground.** The same rig, drawn at the
snapshotted `cast_at` during the `telegraph` state at low alpha and
growing, would turn an invisible 0.8 s into a readable one, and it needs
no new art. That is a gameplay change rather than a rendering one, so it
belongs in its own pass with its own before/after -- but it is the thing
that would most improve the fight, more than the pool's own art.

### Effort

The three pieces above are perhaps two hours, most of it in the painter,
plus tests: the rig loads and slices to 10 frames, `scale` equals
`2 * hazard_radius`, a hazard with no `hazard_sprite` still draws the bare
circle, and the frame index is clamped at the end of the strip rather
than wrapping. The frame digest is unaffected -- it draws no hazards.

### What shipped, and where it differs from the proposal above

The owner set the rules: **the ring stays untouched** as the reference for
the attack's true range; **the disc stays too, fainter**, so the area is
still readable without competing; **the art is flair only**; and it plays
**in the pool's last 0.7 s** rather than across its whole life, so it reads
as the blast going off rather than as the pool simmering.

That last point is the one real departure from the proposal, and it is
better. Stretching 10 frames over 3.5 s would have been 2.9 fps -- a
slideshow. Played at its own 14 fps against the tail of the pool, the
strip runs at the speed it was drawn for and lands its final frame exactly
as the pool expires.

| piece | what |
|---|---|
| `data/enemy_sprites.json` | rig `hex_shaman_explosion_spell`: 10 frames of 192, `content` `[34, 13, 130, 138]`, `anchor` centre, `scale` `[184, 184]` |
| `data/enemies.json` | `warlock.hazard_sprite` names the rig |
| `entities/hazard.py` | `Hazard.sprite`, carried, never read by the damage path |
| `melee.py` / `effects.py` / `context.py` | `hazard_sprite` threaded from the cast to the pool |
| `rendering.py` | `_hazard_sprite`, and the fill alpha halved to `35 * life_fraction + 10` |

Two numbers worth keeping honest. **`scale` is `2 * hazard_radius`**, so
the flair can never disagree with the circle a player is reading; a test
pins the two together, and retuning the radius moves the art with it.
**`content` crops the sheet's transparent margin** -- the ink is 130x138
inside a 192 frame, so without the crop the burst drew at about two thirds
of the ring and read as a smaller, weaker explosion than the area it
represents. Measured from the sheet, not guessed.

The frame is picked from the pool's remaining life rather than an
`Animator`, the way obstacle skins are: a hazard is not an actor and does
not need per-instance animation state. The index is clamped, not wrapped,
so a pool that outlives its strip holds the last frame instead of
restarting.

### Still open

The 0.8 s wind-up still marks nothing on the ground -- the telegraph ring
in `one_enemy` is gated on `slam_radius`, which only the brute has. The
owner has said the wind-up flag would help and that it belongs before the
disc appears. Not built here; it is a gameplay change with its own
before/after, and it wants the same rig drawn at the snapshotted `cast_at`
during the `telegraph` state.

## The UI sheets: buttons, ribbons and the slicer (2026-09-04)

The menus draw their chrome from the Tiny Swords UI pack under
`assets/ui/`. Every file there carries a lowercase name that says what the
picture is (the rename and its full map are in `journals/journal.md`, "UI
asset rename"); the pieces the game uses are listed in `data/ui_sprites.json`
as plain rigs (`file` + `frame`, no `anims`), so the code never names a file.

### The 64-px grid

The pack is authored on 64-px tiles:

| Sheet | Size | Tiles | Cut as |
|---|---|---|---|
| `buttons/<colour>.png`, `icons/*`, `ribbons/<colour>_tab_*` | `64x64` | 1x1 | plainly scaled |
| `buttons/<colour>_wide[_pressed].png`, `ribbons/<colour>_ribbon.png`, `banners/parchment_wide.png` | `192x64` | 3x1 | **3-slice**: two caps kept, the middle stretched |
| `buttons/<colour>_panel[_pressed].png`, `banners/parchment_panel.png` | `192x192` | 3x3 | **9-slice**: four corners kept, edges stretched one way, the centre both |

The `_pressed` sheets are the same button drawn 4 px lower with the top
bevel removed -- the press is baked into the art. So a pressed button is an
image swap plus a 4-px shift of whatever sits on it (`ui.widgets.PRESSED_DY`),
never a computed offset. Only blue and red have pressed art; a pressed gold
button shows its base colour's pressed sheet.

The transparent margins around the ink (7 px left / right, 8 px below on a
button) are part of the look and are kept: the rigs declare the full frame,
no `content` crop.

### The slicer -- `ui.panels.slice(assets, rig, size, tile=64)`

Cuts one sheet on its grid and rebuilds it at `size`:

1. **Grid.** An axis with three tiles is sliced; one tile is scaled whole.
2. **Pre-scale.** A sliced axis needs two tiles of room (its caps), a plain
   axis one. If the target is smaller than that on either axis the *whole
   sheet* is scaled first by one shared factor
   (`min(1, w / need_w, h / need_h)`), so a short button keeps its
   proportions instead of squashing its caps. At the native 64 px the
   factor is 1 and nothing is resampled.
3. **Compose.** Caps / corners are copied 1:1 (post pre-scale); the
   middle cells are stretched to what is left. Nearest-neighbour throughout
   -- pixel art.
4. **Cache** per `(rig, size, tile)`, cleared by `panels.clear_cache()`.
   `None` for a missing rig or a non-positive size.

`three_slice_h` (the start-menu parchment scroll) is the older builder: it
composes a bar from three *separate* rig images and stays for that panel.

### The widgets -- `ui/widgets.py`

`draw_button(surface, assets, rect, label, *, state, shape, variant, font)`
paints one button and returns the label's rect (or `None` with no label, so
a caller can lay its own content on the art):

| | `normal` | `hover` | `pressed` |
|---|---|---|---|
| `shape="wide"`, `variant="primary"` | `btn_blue_wide` | `btn_gold_wide` | `btn_blue_wide_pressed` |
| `shape="wide"`, `variant="danger"` | `btn_red_wide` | `btn_gold_wide` | `btn_red_wide_pressed` |
| `shape="panel"`, `variant="primary"` | `btn_blue_panel` | `btn_gold_panel` | `btn_blue_panel_pressed` |

`hover` is the one highlighted look -- the cursor over a button, the
keyboard cursor on a row, the selected hero or card. `danger` is for
leaving actions (Exit, Quit to menu). `draw_ribbon(surface, assets, rect,
label, *, colour, font)` paints `ribbon_<colour>` (`blue` / `yellow` /
`red`) with the label centred.

Both fall back to the flat rounded rectangle the screens drew before the art
when the sheet is missing or `assets` is `None`, so an empty `assets/` still
plays.

### Who draws what

| Screen | Element | Shape | State source |
|---|---|---|---|
| Start menu | each option, `64` tall on a 72-px step | wide | selected row → hover; `MouseNav.pressed_on` → pressed; Exit → danger |
| Hero select | Begin, `256x64` | wide | `MouseNav.hover` → hover; `pressed_on` → pressed |
| Hero select | hero cards, `340x340` | panel | selected hero → hover; **armed** (first click landed) or held → pressed -- the card sinks to say "click again to begin" |
| Hero select | difficulty, `64` tall | ribbon | colour from `config.DIFFICULTY_RIBBON` (blue / yellow / red); the ribbon is a switch -- a click steps the difficulty (no hover / pressed art exists for ribbons) |
| Level-up | the cards, `340x200` | panel | selected → hover; held → pressed |
| Pause | each row, `560x64` | wide | selected → hover; held → pressed; Quit → danger; the Key layout value on the right half |

Card content (names, rows, badges, tags) starts 16 px in, inside the flat
centre of the 9-slice art, and shifts `PRESSED_DY` on a sunk card.

### Text on the sheets (2026-09-04)

Two bundled faces, asked for by *role* in `game/fonts.py`, never by file:
`heading()` is **NunitoSans** -- every title: screen titles, hero and trait
names, card names, the Begin label, "Difficulty:", "Paused", "Level Up",
the summary titles; `body()` is **Fredoka** -- everything else, including
the difficulty *type*; `mono()` is the dev overlay's monospace. A missing
file degrades to SysFont as before.

The sheets are light, so text drawn on them uses its own pair:
`config.COLOR_ON_BUTTON` (`(28, 28, 34)`, a near-black -- the owner asked for a
shade clearer than pure black) for titles and labels,
`COLOR_ON_BUTTON_DIM` (`(60, 62, 72)`, judged in a real window) for the
secondary lines -- identity and description text, the difficulty type,
badges, tags, the pause screen's Key layout value. The light `COLOR_TEXT`
pair stays for the dark background (HUD, summaries, Options, dev menu).

Labels sit on a button's *visual* centre: the wide sheet's ink is 56 px in
its 64 px frame with the empty 8 px at the bottom, so `draw_button` centres
its label on `rect.centery + LABEL_DY` (`-6`: the 4-px ink offset plus a
2-px optical nudge) and the hand-blitted pause labels apply the same
constant. A sunk button adds `PRESSED_DY` on top. The ribbon fills its frame
and takes no lift.

### The mouse side

`ui.mouse.MouseNav` gives a screen `hover` (the key under the cursor as of
the last motion, `None` off everything) and `pressed_on` (the key the
current left press landed on). Screens pick a button's state from those two
plus their own selection; picks still happen on the release.

### Tests

`tests/rendering/test_ui_panels.py — SliceTests` pins caps and corners
against the source sheet pixel-for-pixel (including the pre-scaled case
against a hand-scaled reference). `test_widgets.py` pins state / shape /
variant → sheet, the 4-px label shift and the fallbacks. Each screen's art
tests spy on `draw_button` / `draw_ribbon` for the state per element and
sample one cap or corner pixel against the sheet.
