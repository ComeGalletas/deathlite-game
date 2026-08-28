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
- `data/sprites.json`: character, enemy, and projectile sprite metadata.
- `data/terrain.json`: terrain and decoration rig metadata.
- `game/states/playing_state.py`: creates animators and draws gameplay sprites.
- `entities/enemy.py`: creates enemy animators and changes enemy animation states.

## Metadata and Sprite Rigs

A rig is a named metadata entry. For example, `hero_aegis` in `data/sprites.json` contains:

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

Terrain decoration rigs are declared in `data/terrain.json` rather than `data/sprites.json`. They still use `Assets.frames()` and the same rig concepts.

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

Animated strips are not used for the arrow projectile. The arrow is a single-image rig in `data/sprites.json`:

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
2. Add a rig entry to `data/sprites.json` or `data/terrain.json`.
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
