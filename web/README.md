# Web build (pygbag)

Everything needed to build/run **Death Lite Die** in the browser lives here, so
the repo root stays clean. Design notes and the milestone log are in
[`../journals/pygbag.md`](../journals/pygbag.md).

## Files

| File | Purpose |
|------|---------|
| `pygbag.ini` | Bundle exclusions (`.venv`, `tests/`, `journals/`, `web/`, …). pygbag reads it from the **current working directory**, which is why the helpers below `cd` into this folder. |
| `serve.sh` | Rebuild + serve at <http://localhost:8000>. |
| `build.sh` | Build only; output to `../build/web/`. |

The entry script is `../main.py` (shared with the desktop build) — pygbag packs
the folder that contains the entry, so it has to stay at the repo root. `main.py`
detects the emscripten runtime and applies the browser profile
(`config.apply_web_profile()` — 1280×720, 60 fps, no save file). `../build/` is
generated output and is gitignored.

## Commands

```bash
# from the repo root
bash web/serve.sh        # rebuild + serve on :8000
bash web/build.sh        # build only -> build/web/
```

Equivalently, by hand:

```bash
cd web
python -m pygbag --ume_block 0 --title "Death Lite Die" ../main.py
```

PowerShell:

```powershell
cd web
..\.venv\Scripts\python.exe -m pygbag --ume_block 0 --title "Death Lite Die" ..\main.py
```

First run downloads a CPython-WASM runtime (cached afterwards). Add `--build` to
produce `build/web/` without starting the server; serve that statically with
`python -m http.server -d build/web 8000`.

Load `http://localhost:8000/#debug` to keep pygbag's on-page Python console
visible — import/runtime tracebacks print there, not in the browser JS console.

## Deploy (GitHub Pages — not wired yet)

`build/web/` is the publishable artifact. A workflow sketch (`.nojekyll` +
`actions/upload-pages-artifact`) is in `../journals/pygbag.md`.
