# The terrain's ground bands: journal

**ID:** RND-009 · **System:** rendering · **Type:** performance ·
**Status:** done (2026-09-29): investigated, no code change; the bands sit
at the blitter's floor · **Branch:** ComeGalletas/rnd-009-ground-bands-9ec11fc6
(stacked on ENT-018, owner)

---

## RND-009: Requirement (owner, 2026-09-29)

- **Objective:** Cut the draw time of the terrain's ground bands, the
  largest single item left in the frame (RND-008.7: 3.4 ms of an 8 to
  10 ms draw at 2560 × 1080, 100 packed).
- **Details:** chosen by the owner over finishing ENT-018's small exact
  changes and over a crowd LOD that would change play (ENT-018.D1).
- **Constraint:**
  - Pixels do not change.
  - The resolution stays native (RND-008.D4).
  - A candidate is timed without wrappers, old against new, before it is
    built (the lesson of ENT-018.3).

## RND-009: What was measured (2026-09-29)

Windows renderer, 2560 × 1080, zoom 1.797, seed 35, 100 packed round the
hero. Scripts in the session scratchpad: `bands_probe.py` and
`blit_exp.py` to `blit_exp4.py`.

- **What a band is.** Each terrace's ground is one baked surface. At this
  zoom terrace 0's is 5405 × 3220 (17.4 Mpx) and terrace 1's is 9.55 Mpx.
  SDL clips a blit to the screen, so the cost is the roughly 2.8 Mpx in
  view per band.
- **Its pixels.** 50 % fully transparent, 49 % fully opaque, and about
  0.8 % in between (374,862 translucent pixels across the 19 zoomed band
  surfaces), along edges and shadows.
- **The cost.** The three bands take 3.2 to 4.1 ms together, about 0.7 ns
  per pixel in view. `draw_ground_band`'s own work (the per-call sort, the
  view test) is about 0.06 ms of it.
- **An opaque pixel blended over the frame gives exactly its own colour**
  (checked over 256 values). So a copy of the opaque part would be exact,
  if a copy were faster.

| Candidate, all bands in view | Bytes the same | Time against the alpha blit |
|---|---|---|
| the current per-pixel alpha blit | (reference) | 1.92 + 1.10 + 0.16 ms |
| RLE on the alpha surface | **no** | 64 ms for terrace 0 alone |
| an opaque copy with a colour key and RLE (the translucent 0.8 % would still need a second pass) | not tried: 18× slower | 35.9 ms against 1.92 for terrace 0 |
| only the tiles that hold a visible pixel, `blit(area=...)`, 128 / 256 / 512 px | **no** (each tile's float position truncates on its own) | −11 % / −1 % / +4 % |

## RND-009: Finding and close

- **The ground bands are at the floor of pygame's per-pixel alpha
  blitter,** which runs near memory speed. Every exact candidate was either
  inexact or slower, and the one that gained anything (−11 % with small
  tiles) changed bytes. **No code change was made.**
- **What could still cut them** changes the picture or the pipeline, so
  each is the owner's decision:
  - pre-composite the water and terrace 0 into one opaque buffer that
    scrolls with the camera (a plain copy instead of two blends; the
    water's animation has to be kept);
  - draw fewer layers where terraces overlap;
  - lower-cost art for the ground.
- The frame's other large lever stays the crowd LOD for a packed
  on-screen crowd (ENT-018.D1, option 3), which changes how crowds move.

## RND-009: Tasks

- [x] RND-009.1: Measure what the bands blit and try every exact candidate, timed without wrappers; this journal and the index row
