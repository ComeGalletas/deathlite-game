# Web build — what the check found, and how the game should run in a browser

> Assessment (2026-09-03), after spawn master S7 and the fluidity plan.
> Measured facts are marked; the rest is a proposal. The pygbag milestones
> W1-W8 in `journals/pygbag.md` are the baseline this builds on.

**In one paragraph.** The browser build boots and starts a run with the
spawn master in it, but three things stand between it and something you
could publish: the generated page cannot be served from a plain static
host (it 404s on the pygame wheel), the bundle is 45 MB of which 35 MB is
art nothing references, and the per-frame work that is already the
desktop's problem is two to four times more expensive in WebAssembly, so
the flow-field spike becomes a visible hitch and world generation becomes
a long wait. None of it needs new architecture: fix the deploy, trim the
bundle, ship the two fluidity items first, and give the browser profile
its own spawn-master numbers.

---

## 1. What the check found (measured)

| Finding | Evidence |
|---|---|
| `pygbag.ini` was missing `/.claude` | The first build packed 2,103 files / 82 MB; `.claude/worktrees/` held a full copy of the repo. Fixed in `web/pygbag.ini`; the bundle is now 1,083 files / 44.8 MB with `spawn/` and `data/spawn_tables.json` inside and no tests, journals or web folder. |
| **A static host cannot serve the build as generated** | Served from `python -m http.server -d build/web`, the loader fetches the 44 MB bundle, then `GET /cdn/cp312/pygame_ce-2.5.7-...whl` → 404, stalls on a grey canvas, and the page reloads itself in a loop. pygbag's own dev server proxies `/cdn/` to the CDN; a static host does not. **The W9 GitHub Pages plan would hit this.** With the wheel copied to `build/web/cdn/cp312/` the game boots. |
| The game runs in the browser with the spawn master | Menu, hero select, loading screen, a run with the F1 overlay showing the zone / population / pressure lines, all from the static server plus the vendored wheel. Nothing in `spawn/` touches threads, files or numpy. |
| 35 MB of the bundle is art nothing loads | 893 asset files; 223 (11.1 MB) are named by `data/*.json` or a code string, 670 (34.7 MB) are not -- 29 MB of it `assets/unordered-effects/`, the rest stray sheets under `characters/`, `terrain/`, `enemies/`. |
| Per-frame cost in WASM, start of a run, no enemies | Overlay readings: update 30-58 ms (the flow-field rebuild, ~23 ms on desktop), render 14-20 ms at 1280x720 (about 4 ms on desktop's software path). Roughly **2-4x** desktop. |
| Frame *rate* could not be measured here | The embedded browser pane never fires `requestAnimationFrame` (0 per second, measured), so pygbag's loop only advances between captures; its 0.3 FPS is the pane, not the game. No real Chrome was connected to this session. Measure on a real browser before tuning. |

The desktop loading work under the web profile is 2.3 s (generation
1.6 s in 32 steps, bake 0.4 s in 14, navigation 0.3 s). At 2-4x that is a
5-10 s loading screen in the browser, with single steps of up to 0.16 s
on desktop stalling the hero animation for half a second each in WASM.

---

## 2. Deploy: make the build static-hostable

The only blocker for W9. Two ways; the first is a line in `build.sh`.

**2a. Vendor the wheel next to the page.** After `pygbag --build`, copy
the pygame-ce wheel the loader asks for into the output:

    mkdir -p build/web/cdn/cp312
    curl -sSL -o build/web/cdn/cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl \
      https://pygame-web.github.io/cdn/cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl

The wheel is 1.5 MB. The version string is whatever
`https://pygame-web.github.io/cdn/index-0.9.3-cp312.json` maps `pygame`
to; read it from there in the script rather than hard-coding, so a
pygbag upgrade does not silently break the deploy. This is what the
GitHub Action in `journals/pygbag.md` needs as a step before
`upload-pages-artifact`.

**2b. Point the loader at the CDN for wheels.** pygbag's `--cdn` flag
sets the interpreter's base; the wheel path in the index is relative to
the *page*, so this does not help on its own. Not pursued.

Everything else the loader needs (`pythons.js`, `main.wasm`, `main.data`)
already comes from the CDN, so 2a is the whole fix.

---

## 3. Bundle: ship what the game loads

45 MB is a long first load and a long unpack (the loader untars the whole
archive into memory before Python starts). The game names its assets in
`data/*.json` and a few code strings; nothing else is ever opened.

**Proposal: a manifest-driven pack.** A small script
(`web/manifest.py`) walks `data/*.json` and the code for asset paths,
writes the list, and the build packs only those plus `assets/fonts/`.
pygbag has `ignoreFiles` but no include list, so the clean way is to
stage: copy the referenced files into `build/stage/` mirroring the tree,
copy the code and data alongside, and point pygbag at the stage. Expected
bundle: ~11 MB of art + 1 MB of code and data, a quarter of today.

`assets/unordered-effects/` (29 MB) is source material, not game
content; it can also simply move out of `assets/` and the same result
follows without a script. Do that first; the manifest is for the long
tail.

---

## 4. Frame time in the browser

The fluidity plan's two items (`documentation/fluidity_plan.md`) matter
more here than on desktop, because everything is 2-4x slower and the
compositor budget is a hard 16.7 ms at 60 Hz:

1. **The obstacle spatial index in `GameMap.is_walkable`** (desktop:
   93 → 4 us a call, update p50 6.0 → 1.2 ms at 100 live). In WASM the
   scan is the difference between a playable crowd and not.
2. **The time-sliced flow-field fill.** A 23 ms desktop rebuild is a
   50-90 ms hitch in the browser -- three to five dropped frames every
   time the hero crosses two lattice cells. Slicing the fill at ~3 ms a
   frame removes the hitch outright. A worker *process* is not available
   in pygbag; the slice is the browser's only answer.

Then the browser profile gets its own spawn-master numbers, set in
`config.apply_web_profile()` like the resolution and frame cap:

| Knob | Desktop | Browser | Why |
|---|---|---|---|
| `ENEMY_LIVE_CAP` | 100 | 60 | the simulation budget is the same 16.7 ms and each body costs 2-4x |
| `ENEMY_LOD_SKIP` | 2 | 3 | measured on desktop: 2 → 5.8 ms, 3 → 5.1; the extra step is worth more when every tick is dearer |
| `ENEMY_NAV_REBUILD_INTERVAL` | 0.4 s | 0.6 s | fewer fills; the sliced fill makes each one free of hitches, this makes them rarer |
| `NAV_FILL_MAX_COST` | 4500 | 3500 | a smaller fill; enemies past it keep the bearing fallback and their pursuit timer ends the attempt |

None of these are new mechanisms; they are the same knobs read at call
time, so `apply_web_profile()` can set them the way it sets `FPS`.
Measure on a real browser with the F1 overlay before committing to the
values -- the pane used here cannot.

**Render.** 14-20 ms at 1280x720 with fifteen bodies in view is already
most of the frame. The terrain path composites several scaled surfaces
per frame; the `_blit_cache` fills per band on first sight (the 62 ms
frame on desktop). Two cheap moves, both browser-side only: keep
`CAMERA_ZOOM` at 1.25 (integer tile size, no seams, already done) and
pre-warm the blit cache for the start island during the loading screen,
so the first seconds of a run do not stutter. Beyond that, profile draw
under the stress harness (`--draw`, on the fluidity list) before
touching the renderer.

---

## 5. Loading in the browser

The loading screen already slices generation and bake a step per frame
(`game/states/loading_state.py`). In WASM the whole thing is a 5-10 s
wait, which is acceptable for a run start if the animation keeps moving.
Two things keep it moving:

- **Finer steps where a step is long.** The four slowest generation
  steps are the repair (0.16 s), the scatter (0.13 s), the first
  spawn-point island (0.12 s, it builds the lattice) and a terrace field
  (0.11 s). Each becomes several yields: the repair per round, the
  scatter per island, the lattice as its own step. Under 50 ms a step on
  desktop keeps the hero animating in WASM.
- **A progress bar from the step labels.** `generate_world_steps` and
  `bake_steps` already yield a label per step; the loading state knows
  the count. Draw the fraction. Cheap, and it turns "is it stuck?" into
  "it is at 60 %".

There is no background thread to move this onto in the browser, and no
worker that could share the Python heap; slicing is the mechanism.

---

## 6. Order

| Step | Effort | Where |
|---|---|---|
| vendor the wheel in `build.sh` and the deploy action (2a) | an hour | `web/build.sh`, the W9 workflow |
| move `assets/unordered-effects/` out of the bundle | minutes | `web/pygbag.ini` `ignoreDirs`, or the folder itself |
| obstacle index, sliced fill (fluidity plan items 1 and 3) | a day and a half | `world/map.py`, `world/nav/field.py` |
| browser spawn-master knobs in `apply_web_profile()` | an hour, after measuring on a real browser | `game/config.py` |
| finer loading steps + progress bar | half a day | `world/gen/__init__.py`, `world/gen/repair.py`, `game/states/loading_state.py` |
| manifest-driven pack (3) | half a day | new `web/manifest.py`, `web/build.sh` |
| W9: GitHub Pages workflow | an hour | `.github/workflows/deploy-web.yml` |
