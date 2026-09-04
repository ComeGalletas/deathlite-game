# Web build (pygbag) — dev log

Tracks getting **Death Lite Die** running in the browser via
[pygbag](https://pygame-web.github.io/) and deployed from GitHub, the same way
`assets_journal.md` tracks the art passes and `enemy_ai.md` tracks the AI
refactor. The general `journal.md` gets a one-paragraph pointer here once this
lands.

Milestones are **W1–W9**. Each ends green — `python -m unittest discover -s
tests -t .` plus a `pygbag` local run — before the next.

**Status:** W1–W8 done (2026-08-28) — the browser build runs (menu, gameplay,
audio, session-only save) at 1280×720/60 fps, and all pygbag files live in
`web/`. **W9** (the GitHub Pages workflow + `.nojekyll`) is the only one left and
is deliberately **not created yet** — owner will add it; the ready-to-paste
sketch is under "GitHub Actions sketch" below.

---

## Goal

Ship a playable browser build with **zero gameplay divergence** from desktop:
same loop, same content, same RNG. The browser has no durable filesystem and a
fragile audio context, so the two places the builds legitimately differ are

1. **persistence** — the web build never reads or writes `save.json`; every
   session starts clean (owner's call: *no* IndexedDB save for the web version),
   and
2. **mixer bring-up** — the web build must not tear down and re-open the
   WebAudio context.

Both are handled behind flags / an adapter so desktop is untouched.

## Constraints (as given)

- No save for the browser version — a `config` flag that makes the game skip
  looking for / writing the save file entirely.
- A mixer adapter that switches between browser and local modes.
- Create the pygbag entry points now; **don't** create the GitHub workflow /
  Pages files yet.
- Recommend 3 easy-to-download cartoonish fonts.

---

## Compatibility scan (baseline, pre-changes)

| Area | Web status | Notes |
|---|---|---|
| Python / pygame | ✅ | pygbag ships CPython 3.12 + pygame-ce 2.5.x; project targets 3.12 / pygame 2.5.2, API-identical. No numpy / `sndarray`; `array` + `math` synth only. |
| Asset + data loading | ✅ | `game/assets.py` / `game/content.py` read lazily via `Path(__file__).parent.parent / …`; pygbag unpacks the bundle into MEMFS at the same layout. `assets/` ≈ 7.9 MB, `data/` 73 KB → ~8 MB bundle. |
| Threads / subprocess / blocking IO | ✅ none | No `threading`, `multiprocessing`, `subprocess`, `input()`, `time.sleep`, `pygame.time.wait`. |
| Main loop | ⛔ → fixed in **W1** | `Game.run()` was a hard blocking `while` loop; the browser needs `await asyncio.sleep(0)` once per frame. |
| Save file | ⛔ → fixed in **W2** | `game/save.py` writes next to `main.py`; in MEMFS that is lost on reload. Web build now skips it via `config.SAVE_ENABLED`. |
| Mixer | ⚠️ → fixed in **W3** | `AudioManager` did `mixer.quit()` + `mixer.init(22050, -16, 1)` after `pygame.init()`; unreliable in emscripten. Now behind `systems/mixer_backend.py`. |
| Fonts | ⚠️ → fixed in **W4** | 25+ `pygame.font.SysFont("georgia" / "consolas" / "arialrounded")` call sites. Browser has no system fonts. Now routed through `game/fonts.py` + a bundled Fredoka. |
| Window | ✅ → tuned in **W7** | Was `set_mode((1600, 900))` then CSS-scaled to the 1280×720 canvas. Web profile now renders at 1280×720 / `CAMERA_ZOOM 1.2` — 1:1 with the canvas, same field of view. |

---

## Milestones

| # | Scope | Ends when |
|---|-------|-----------|
| **W1 ✅** | **Async loop / entry points.** `game/game.py`: loop body factored into `_start()` + `_step()`; `run()` (desktop, unchanged behaviour) and new `async run_async()` (browser — `await asyncio.sleep(0)` per frame, also works on desktop via `asyncio.run`) both drive them. `main.py` rewritten: `async def main()`, `asyncio.run(main())`, and a `sys.platform == "emscripten"` check that flips the web config. New `main_web.py`: explicit browser entry that forces `config.SAVE_ENABLED = False` then calls the same `Game().run_async()` — kept to one meaningful line so it can't drift from `main.py`. **Done 2026-08-28** — full suite **573 green**; scripted 5-frame `_start`/`_step`/`await` drive confirms the async path boots the menu and renders. |
| **W2 ✅** | **Session-only persistence flag.** `config.SAVE_ENABLED: bool = True` (new "Persistence" section). `game/game.py.__init__`: `self.save = save_mod.load(...) if config.SAVE_ENABLED else save_mod.SaveData()` — no disk read when off. `Game.persist()`: early `return` when off — no disk write. `game/save.py` untouched (it deliberately imports nothing from the project). Desktop default `True`; `main.py`/`main_web.py` set it `False` under emscripten. **Done 2026-08-28** — suite green; `config.SAVE_ENABLED = False` then `Game()` boots with a fresh `SaveData` and `persist()` is a verified no-op. |
| **W3 ✅** | **Mixer adapter.** New `systems/mixer_backend.py`: `MixerBackend` base owns the shared *buffer → `Sound`* path (linear resample `SYNTH_RATE`→device rate + mono→N-channel up-mix, both skipped on the desktop fast path); `DesktopMixer` (quit + re-init at 22050/mono/24ch — the old behaviour), `BrowserMixer` (init once, **no quit**, accept the browser's rate/channels, 16ch), `SilentMixer` (headless / dummy driver — every call a no-op). `make_mixer_backend(force=None)` picks `browser` under emscripten else `desktop`, and falls back to `silent` on any `pygame.error`. `systems/audio.py`: `_RATE = SYNTH_RATE`; `_render(samples, backend)` and `_build_library(backend)` route through `backend.make_sound`; `AudioManager.__init__` builds the backend, drops cues that failed to render, and stays disabled if none survive. **Done 2026-08-28** — suite green (incl. `test_audio.py`'s degrade cases); desktop run reports `backend: desktop ready: True 22050 Hz 1 ch`, all 8 cues built. |
| **W4 ✅** | **Bundled font.** `assets/fonts/Fredoka-VariableFont_wdth,wght.ttf` added (owner). New `game/fonts.py` — `heading(px)` (bold) / `body(px)` / `mono(px)` return `pygame.font.Font(bundled_path, px)`, degrading to `SysFont("georgia"/"consolas")` then the default face when the file is missing (same contract as `assets.py` / `save.py`). **No module-level cache** — like the `SysFont` calls it replaces, every call builds a fresh `Font`; a cache would hand back stale `Font` objects across a `pygame.quit()`/`init()` cycle and segfault the suite (hit exactly that during the swap, in `test_damage_numbers`). All ~30 `SysFont` call sites across `game/states/*`, `ui/*`, `systems/debug_overlay.py` swapped: `georgia`→`heading`/`body`, `consolas`→`mono`, `arialrounded` (damage numbers)→`body(bold=True)`. **Done 2026-08-28** — full suite **573 green**; menu + char-select screenshots confirm Fredoka renders throughout (headings bold, body at reading weight). |
| **W5** | **GitHub deploy (files added by owner).** `.nojekyll` at repo root; `.github/workflows/deploy-web.yml` (sketch below); enable **Settings → Pages → Source: GitHub Actions**. Build command: `python -m pygbag --build --ume_block 0 --title "Death Lite Die" --ignore ".venv,tests,journals,documentation,utilities,.git,.pytest_cache,red,save.json,save.json.corrupt" main_web.py`. Artifact = `build/web/`, published via `actions/upload-pages-artifact` + `actions/deploy-pages`. | green Action run; game loads at `https://comegalletas.github.io/deathlite-game/` |
| **W6 ✅** | **Docs.** `README.md` — new "Play in the browser" section, project-layout tree + test count refreshed. "Web build (pygbag)" pointers appended to `journals/journal.md` and `journals/transcript.md`. **Done 2026-08-28.** |
| **W7 ✅** | **Web resolution + entry consolidation.** `config.apply_web_profile()` (new, end of `config.py`) sets `SAVE_ENABLED=False`, `FPS=60`, `SCREEN_WIDTH/HEIGHT=1280/720`, `CAMERA_ZOOM=1.2` — `1280/1.2 == 1600/1.5`, so the visible world extent and on-screen sprite size are unchanged while per-frame blit work drops ~35%. Verified: `PlayingState.camera.world_span()` is `(1066.67, 600.0)` in both profiles. `main_web.py` **deleted**; `main.py` is the sole entry — it calls `apply_web_profile()` under emscripten **or** with a `--web` arg (desktop testing). **Done 2026-08-28** — suite **578 green**; `main.py --web` on the desktop confirmed to apply 1280×720/60/no-save. |
| **W8 ✅** | **`web/` folder.** All pygbag packaging moved out of the root into `web/`: `pygbag.ini` (+ `/web` added to its `ignoreDirs`), `build.sh`, `serve.sh`, `web/README.md`. The helpers `cd web` (so pygbag reads `web/pygbag.ini` from the CWD) and point at `../main.py` — which must stay at the root because pygbag packs the folder containing the entry script. `build/` is derived from the entry's location so it still lands at the repo root; added to `.gitignore`. Root now holds only `main.py` (+ gitignored `build/`) for the web build. **Done 2026-08-28** — `bash web/build.sh` → 650-file apk, no `.venv` / `tests/` / `web/` / `pygbag.ini` inside. |

---

## Font recommendations (W4)

**Chosen: Fredoka** (variable weight/width), bundled at
`assets/fonts/Fredoka-VariableFont_wdth,wght.ttf` and used for every non-mono
call site via `game/fonts.py`. The dev overlay / dev-menu keep a `mono()` role
(`SysFont("consolas")` on desktop, default face in-browser) for column
alignment.

The other two below were the runner-up picks, kept here in case a distinct
display face is wanted for the title screen / big banners later. All three are
**SIL Open Font License** (free to bundle and redistribute), one-click download
from [fonts.google.com](https://fonts.google.com):

| Face | Download | Role | Why |
|---|---|---|---|
| **Fredoka** ✅ *(chosen)* | `fonts.google.com/specimen/Fredoka` | Everything except the dev overlay | Rounded geometric sans, even colour, crisp at 15–20 px; synthetic bold reads fine for headings. Bundled as the variable font (~154 KB, one file). |
| **Baloo 2** (Regular / ExtraBold) | `fonts.google.com/specimen/Baloo+2` | Optional: headings, hero names, difficulty labels | Chunky rounded slab — high-impact at 30–56 px. |
| **Luckiest Guy** (single weight) | `fonts.google.com/specimen/Luckiest+Guy` | Optional: title screen + big banners only | Comic poster lettering. Too heavy for body text — reserve it for 1–3 word hits. |

To add a distinct display face later: drop the `.ttf` in `assets/fonts/`, add a
`"display"` role to `_FILES` / `_SYS_FALLBACK` in `game/fonts.py` and a
`display(px)` helper, then point `config.TITLE` / the level-up + boss banners at
it.

---

## GitHub Actions sketch (W9 — not committed yet)

Uses `pygame-web/pygbag-action` — its `ini` / `build` inputs, and it can prune
the bundle (the raw `python -m pygbag` CLI has **no** `--ignore`; it only skips
dotfiles / `__pycache__` / `build/` and honours `.gitignore`, so `.venv` is out
but `tests/` `journals/` `documentation/` would otherwise be packed).

The build must run with the working directory set to `web/` (so pygbag reads
`web/pygbag.ini`) and the entry given as `../main.py`. `build/web/` still lands
at the repo root (pygbag derives it from the entry's location).

```yaml
name: Deploy web build
on:
  push: { branches: [main] }
  workflow_dispatch:
permissions: { contents: read, pages: write, id-token: write }
concurrency: { group: pages, cancel-in-progress: true }
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: |
          python -m pip install --upgrade pygbag
          cd web && python -m pygbag --build --ume_block 0 --title "Death Lite Die" ../main.py
      - run: touch build/web/.nojekyll
      - uses: actions/upload-pages-artifact@v3
        with: { path: build/web }
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: { name: github-pages, url: "${{ steps.deployment.outputs.page_url }}" }
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

(`bash web/build.sh` runs the same command locally.)

## `web/pygbag.ini`

pygbag 0.9.x has no `--ignore` flag and, with no config file, walks the whole
project folder -- including `.venv`, where it hits pygame's bundled
`examples/data/boom.wav` and aborts ("common unsupported format"). It reads
`pygbag.ini` from the **current working directory**, so `web/build.sh` /
`web/serve.sh` `cd web` first:

```ini
[DEPENDENCIES]
ignoreDirs = ["/.venv", "/.git", "/.github", "/.pytest_cache", "/tests", "/journals", "/documentation", "/utilities", "/build", "/web"]
ignoreFiles = ["save.json", "save.json.corrupt", "red", "death_must_die_lite_game_spec.md", "sprite_functionality.md"]
```

`ignoreDirs` entries are folder paths from the project root with a **leading
slash** (pygbag's built-in `IGNORE` convention -- `/build`, `/venv`, `/.git`);
`ignoreFiles` entries are bare basenames. `/web` is listed so this folder's
scripts + `build/` output are not packed. Verified: `bash web/build.sh` packs
**650 files, ~7 MB apk, zero `.venv` / `tests` / `web` entries**.

## Browser boot gotchas found

* **`pygame` key constants at import time.** `game/config.py` (`DEBUG_KEYS`) and
  `entities/player.py` (`_LEFT_KEYS` etc.) referenced `pygame.K_F1` / `pygame.K_a`
  at module scope. Desktop pygame star-imports `pygame.constants` into the
  package namespace at `import pygame`; pygbag's pygame-ce does **not** until
  later, so those modules raised `AttributeError: module 'pygame' has no
  attribute 'K_F1'` before `pygame.init()` and the whole app failed to load
  (blank grey canvas, error only visible via `#debug`).
  *First fix attempt* — `from pygame.constants import K_F1, ...` — made it worse:
  pygbag's top-level import hook treats a dotted `pygame.<sub>` name as a PyPI
  package (`aio.pep0723.pip_install("pygame.constants")` → 404 →
  `ModuleNotFoundError`). **Working fix:** hardcode the raw SDLK integers
  (`K_F1 == 1073741882`, `K_a == 97`, `K_LEFT == 1073741904`, ...) with a
  comment. They are fixed by SDL and are exactly what `pygame.K_*` returns.
  `config.py` no longer imports `pygame` at all. Reading `pygame.K_*` *inside a
  function* stays fine — that runs after init.
* **`import pygame.gfxdraw` at module scope** (`playing_state.py`) — same
  pygbag hook hazard. Moved to a lazy `_get_gfxdraw()` (import inside a
  try/except on first `_draw_cone` call); `None` → a plain translucent
  `pygame.draw.polygon` sector on an SRCALPHA scratch surface, no AA edge.
* **Entry point.** pygbag's generated `index.html` runs `appdir/assets/main.py`
  regardless of the CLI arg, and sources it with `__name__` set to the module
  name — so `if __name__ == "__main__": asyncio.run(main())` never fired.
  `asyncio.run(main())` is now unguarded at module scope in both entry files.
* **`pygame` was a stub** (`module 'pygame' has no attribute 'init'`) — pygbag
  scans **the entry file's own imports** to decide which wasm wheels to preload.
  Our thin `main.py` only imported `game.*`, so pygame was never fetched.
  Fix: a bare `import pygame` at the top of `main.py`.
* **Diagnosing:** load `http://localhost:8000/#debug` — pygbag then shows its
  Python REPL/console on the page; import tracebacks print there, not in the JS
  console.

## Performance (W7)

All applied by `config.apply_web_profile()` under emscripten / `--web`:

* **Frame cap 60.** The page composites at ~60 Hz; `FPS = 120` just spends WASM
  budget on frames that are never presented.
* **Render target 1280×720 @ `CAMERA_ZOOM 1.2`.** That is the pygbag canvas
  size, so there is no CSS downscale, and `1280 / 1.2 == 1600 / 1.5` keeps the
  visible world extent (and on-screen sprite size) identical to the desktop
  build — ~35 % fewer pixels blitted per frame. Everything reads `config.SCREEN_*`
  / `CAMERA_ZOOM` at call time (the one default-arg capture in
  `systems.camera.Camera` is overridden by an explicit arg in `PlayingState`),
  so the reassignment propagates. `PlayingState.camera.world_span()` verified
  identical `(1066.67, 600.0)` in both profiles.
* **Mixer runs at the browser's rate** (observed 96000 Hz / 2 ch). `BrowserMixer`
  resamples each of the 8 synth buffers 22050 → device rate and up-mixes to
  stereo once at startup (pure-Python loops) — a one-time ~sub-second cost, no
  steady-state impact.

## Local test

```
bash web/serve.sh     # rebuild + serve http://localhost:8000
bash web/build.sh      # build only -> build/web/
```

Or by hand: `cd web && python -m pygbag --ume_block 0 --title "Death Lite Die"
../main.py`. First run downloads a CPython-WASM runtime (cached after). Serve an
existing build statically with `python -m http.server -d build/web 8000`. Load
`http://localhost:8000/#debug` to keep pygbag's on-page Python console visible.
Confirm the menu renders (Fredoka), a run starts, and — expected — progression
does not survive a reload.

---

## TODO

- [x] W1 — async loop + `main.py` / `main_web.py` entry points
- [x] W2 — `config.SAVE_ENABLED`, save read/write skipped when off
- [x] W3 — `systems/mixer_backend.py` adapter, `audio.py` routed through it
- [x] W4 — Fredoka bundled, `game/fonts.py` added, all ~30 `SysFont` call sites swapped
- [x] W4 follow-up — `tests/rendering/test_fonts.py` (5): bundled face present, helpers render, missing-bundle fallback, no cache across a `quit()`/`init()` cycle
- [x] W5 prep — `pygbag.ini` (bundle exclusions); `pygbag --build` verified green (652 files / 6.7 MB apk, no `.venv`). Build/run from **`main.py`** — pygbag's `index.html` hardcodes `main.py` as the entry, so `main_web.py` is desktop-only.
- [x] W5 — first browser boot: two import-time `pygame` constant bugs fixed (see below). `asyncio.run(main())` in `main.py`/`main_web.py` un-guarded (pygbag sources the entry with `__name__` != `"__main__"`).
- [x] W5 — browser boot works: menu + run + audio (browser mixer @ 96 kHz) + session-only save confirmed
- [x] W5 — entry file must `import pygame` directly (pygbag preloads from the entry's imports)
- [x] W6 — `README.md` "Play in the browser" section + pointers in `journal.md` / `transcript.md`
- [x] W7 — `config.apply_web_profile()`: 60 fps + 1280×720 @ zoom 1.2 (same FOV); `main_web.py` folded into `main.py --web`
- [x] W8 — pygbag files moved to `web/` (`pygbag.ini`, `build.sh`, `serve.sh`, README); `build/` gitignored; root clean
- [ ] W9 — `.nojekyll` + `.github/workflows/deploy-web.yml` (sketch above); enable Pages (GitHub Actions source)
- [ ] (optional) trim the browser bundle — audio synth runs at load; measure and, if slow in WASM, pre-bake the 8 buffers

---

## W10 check (2026-09-03) -- after spawn master S7

Rebuilt and served the bundle from a plain static server (not pygbag's)
and drove it from an embedded browser. Full findings and the plan:
`documentation/web_plan.md`. In short:

- `web/pygbag.ini` lacked `/.claude`; the worktree copy under it went into
  the bundle (2,103 files / 82 MB). Fixed: 1,083 files / 44.8 MB, with
  `spawn/` and `data/spawn_tables.json` in.
- **A static host cannot serve the build as generated**: the loader asks
  for `/cdn/cp312/pygame_ce-2.5.7-...whl` next to the page, which only
  pygbag's dev server provides, 404s, and reloads in a loop. W9 (GitHub
  Pages) needs the wheel vendored into `build/web/cdn/cp312/` -- with it
  in place the game boots, starts a run, and the spawn master's overlay
  lines show.
- 670 of 893 asset files (34.7 MB of 45.8) are referenced by neither
  data nor code; 29 MB is `assets/unordered-effects/`.
- Per-frame WASM readings at a run's start: update 30-58 ms (the
  flow-field rebuild), render 14-20 ms; about 2-4x desktop. Frame *rate*
  could not be measured -- the embedded pane never fires
  `requestAnimationFrame`, so its 0.3 FPS is the pane's, not the game's.
