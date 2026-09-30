# Web build (pygbag)

Everything needed to build/run **Deathlite Game** in the browser lives here,
beside the desktop build in [`../desktop/`](../desktop/); [`../README.md`](../README.md)
is the index of both. Design notes and the milestone log are in
[`../../documentation/journals/pygbag.md`](../../documentation/journals/pygbag.md);
the assessment of what still stands between this and a publishable page is
[`../../documentation/plans/web_plan.md`](../../documentation/plans/web_plan.md).

## Files

| File | Purpose |
|------|---------|
| `pygbag.ini` | Bundle exclusions (`.venv`, `tests/`, `documentation/`, `tools/`, `assets/unused/`, …). pygbag reads it from the **current working directory**, which is why the helpers below `cd` into this folder. |
| `build.sh` | Build only; copies the finished bundle to `out/` here. |
| `serve.sh` | Rebuild + serve at <http://localhost:8000> through pygbag's dev server. |
| `out/` | Generated, gitignored: the deliverable (`index.html`, `deathlite-game.apk`, …). |

The entry script is `../../main.py` (shared with the desktop build) — pygbag
packs the folder that contains the entry, so it has to stay at the repo root.
`main.py` detects the emscripten runtime and applies the browser profile
(`config.apply_web_profile()` — 1280×720 with the interface at 0.8, no save
file, the browser's own crowd (the spawn master stops spawning at 100 live
enemies against the desktop's 250, bar dev-menu and dummy spawns; waking
enemies can still push past it, as on the desktop), and frames paced by the
page's `requestAnimationFrame` rather than a 60 fps cap, measured in
Chrome). The numbers and why are in
`../../documentation/journals/web_frame_time_journal.md` (BLD-003).

**The build currently needs `--disable-sound-format-error`**: pygbag refuses
the MP3 music (`assets/music/*.mp3`, "Use OGG format instead") and
`build.sh` / `serve.sh` do not pass the flag, so both fail as they stand
(found 2026-09-30, BLD-003.6; the fix is the owner's call).

**A static host works once the pygame wheel sits next to the page**:
`out/cdn/cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl`, from
`https://pygame-web.github.io/cdn/cp312/`. Served that way by
`python -m http.server -d dist/web/out 8000`, the game boots and runs in
Chrome (BLD-003.6).

To see what a frame costs under the profile without a browser:
`python -m tools.benchmarks.spawn_stress --web --render`. It runs on the
desktop, so compare it with Chrome's own figures (BLD-003.6 in that
journal: update ~4 ms, render 32-43 ms (21-99 live; 38.0 ms at 99); the
factor depends on the desktop session); the real number needs Chrome and the F1 overlay.
What a `clock.tick` cap would do against the page's refresh, display by
display, is modelled by `python -m tools.benchmarks.raf_pacing`.

**pygbag hard-codes its output folder** to `<repo>/build/web`, with its cache
in `<repo>/build/web-cache`, and has no flag to move it. So `<repo>/build/` is
pygbag's work area (gitignored), `serve.sh` serves from there, and `build.sh`
copies the result into `out/` so the deliverable sits beside its config like
the desktop build's does.

## Commands

Until the MP3 decision (BLD-003.6, above) the two scripts fail (they pass
no extra arguments); use the by-hand commands below with
`--disable-sound-format-error` added.

```bash
# from the repo root
bash dist/web/serve.sh        # rebuild + serve on :8000
bash dist/web/build.sh        # build only -> dist/web/out/
```

Equivalently, by hand:

```bash
cd dist/web
python -m pygbag --ume_block 0 --title "Deathlite Game" ../../main.py
```

PowerShell:

```powershell
cd dist\web
..\..\.venv\Scripts\python.exe -m pygbag --ume_block 0 --title "Deathlite Game" ..\..\main.py
```

First run downloads a CPython-WASM runtime (cached afterwards). Add `--build` to
produce the bundle without starting the server; serve an existing bundle
statically with `python -m http.server -d dist/web/out 8000`.

Load `http://localhost:8000/#debug` to keep pygbag's on-page Python console
visible — import/runtime tracebacks print there, not in the browser JS console.

## Deploy (GitHub Pages — not wired yet)

`out/` is the publishable artifact, **but a plain static host cannot serve it
as generated**: the loader fetches the pygame wheel from `cdn/cp312/` next to
the page, which only pygbag's dev server provides. Vendoring that wheel and the
Pages workflow are described in `documentation/plans/web_plan.md` section 2 and
the sketch in `documentation/journals/pygbag.md`; neither is done.
