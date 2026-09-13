# Distribution builds

Everything that packages **Deathlite Game** lives under this folder, one
sub-folder per target. The game's own source, `main.py` and `assets/` stay at
the repo root; nothing here is imported at runtime.

| Target | Folder | Tool | Command (from the repo root) | Deliverable |
|--------|--------|------|------------------------------|-------------|
| Windows desktop | [`desktop/`](desktop/) | PyInstaller | `powershell -ExecutionPolicy Bypass -File dist\desktop\build.ps1 -Zip` | `dist/desktop/out/DeathliteGame-<version>.zip` |
| Windows desktop, diagnostic (console attached) | [`desktop/`](desktop/) | PyInstaller | `powershell -ExecutionPolicy Bypass -File dist\desktop\build.ps1 -Console` | `dist/desktop/out-console/DeathliteGame/` |
| Browser (WebAssembly) | [`web/`](web/) | pygbag | `bash dist/web/build.sh` (build) / `bash dist/web/serve.sh` (build + serve on :8000) | `dist/web/out/` |

Each target's README explains its files and pitfalls. Rules that hold for all
of them:

* **Each target's config is the single source for what ships.** The desktop
  spec allow-lists asset folders; `web/pygbag.ini` deny-lists them. New art in
  a new top-level `assets/` folder has to be registered in both.
* **Outputs land in `out/` (and `out-console/`) beside the config that made
  them**, gitignored. The one exception is pygbag's fixed work folder
  `<repo>/build/`, which it hard-codes; `web/build.sh` copies the finished
  bundle from there into `web/out/`.
* **Both builds use `.venv`** (pygame, PyInstaller, pygbag; no numpy). The test
  suite runs on the system Python instead.
* **The version is `config.VERSION`** in `game/config.py`, read by both
  targets. There is nothing else to bump.

Browser deployment (GitHub Pages, vendoring the pygame wheel next to the page)
is not wired up; the plan is in
[`../documentation/plans/web_plan.md`](../documentation/plans/web_plan.md).
