# Desktop packaging (.exe) — execution journal

**Legacy ID:** BLD-002 · **Systems:** BLD · tagged retroactively on 2026-09-22 (DOC-001.3); predates the ID standard, so its sections do not follow it.

## Requirement (owner, 2026-09-12)

Package the game **as it stands** so it runs on another Windows PC as a `.exe`,
with no Python install on the target machine. The owner asked for a review and a
proposal before any code, then confirmed the decisions below and asked for this
journal alone — **nothing is built yet.**

The web build (`web/`, pygbag, journalled in [`pygbag.md`](pygbag.md)) is the
existing precedent for "a packaging target lives in its own folder"; this work
mirrors that shape rather than inventing a new one.

---

## Review findings

The project freezes unusually cleanly. Everything below was verified against the
tree, not assumed.

| Check | Result |
|---|---|
| Runtime third-party deps | **pygame 2.6.1 only.** `numpy` appears solely in `utilities/` dev scripts and is not installed in `.venv` |
| Dynamic imports | **none** — no `importlib`, `__import__` or `pkgutil` anywhere in runtime code, so PyInstaller's static analysis sees the whole graph |
| Relative-path `open()` | **none** — nothing depends on the working directory |
| Audio files | **none** — `systems/audio.py` synthesises every sound into a buffer |
| Optional pygame submodules | none used: no `surfarray`, `sndarray`, `freetype`, `midi`, `camera`, `scrap` |
| Runtime imports of `tests/` or `utilities/` | **none** |
| Python | 3.12.0; `.venv` holds pip + pygame + pygbag and nothing else |

### Why the three asset loaders need no change

`game/assets.py:23`, `game/content.py:18` and `game/fonts.py:32` all resolve
their directory as `Path(__file__).resolve().parent.parent / "<dir>"`.

PyInstaller (>= 5.0) sets `__file__` on a frozen module to its would-be path
*inside the bundle* — `sys._MEIPASS/game/assets.py` — so `parent.parent` lands
exactly on the bundle root. Ship `assets/` and `data/` as bundle data under
their own names and **all three resolve correctly with zero code changes.**

### The one place that pattern breaks

`game/save.py:23` uses the same idiom:

```python
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "save.json"
```

Frozen, that points *into the bundle*, which is the install folder — writable on
a Desktop unzip, blocked under `Program Files`, and (had we chosen onefile) a
temp directory Windows deletes on exit, silently destroying progression every
launch. This is the only genuine blocker, and the reason for decision **5**.

The seam already exists: `game/game.py:49` is
`self.save_path = save_path or save_mod.DEFAULT_PATH`, and `save()` already does
`path.parent.mkdir(parents=True, exist_ok=True)`, so redirecting it is a handful
of lines in `main.py` and needs no change to `save.py`'s contract.

### Payload

`assets/` is 48 MB, of which **`assets/unused/` is 40 MB** (29 MB of that in
`unordered-effects` alone). Nothing in code or `data/*.json` references it —
grepped and confirmed. There are also four `preview.gif` files under
`assets/effects/` that are gitignored but present on disk.

---

## Confirmed decisions (owner, 2026-09-12)

1. **`--onedir`, not onefile.** A folder shipped as a ZIP: unzip anywhere,
   double-click the exe. Onefile would re-extract ~950 PNGs to `%TEMP%` on every
   launch (seconds of cold start), and its self-extracting stub is the shape
   antivirus and SmartScreen flag most often.
2. **Prune `assets/unused/` from the bundle**, along with the
   `assets/effects/*.gif` previews. Takes the shipped art to ~8 MB. The files
   stay in the repo; only the bundle drops them.
3. **The game is called "Deathlite Game"** — one name, everywhere the player or
   the browser can see it. The three-way split ("Death Lite Game" in
   `config.TITLE`, "Death Lite Die" in the pygbag build and the README) is
   retired; see *Rename scope* below.
4. **Icon built from Aegis, the blue Warrior** — see the next section.
5. **Save to `%LOCALAPPDATA%\DeathliteGame\save.json`** when frozen. Survives
   reinstalls, needs no elevation, and leaves the dev tree's repo-root
   `save.json` untouched for source runs.
6. **Version `0.5`.** A new `config.VERSION` — distinct from `save.SAVE_VERSION`
   (currently `2`), which is the save *schema* version and unrelated. The exe's
   own Windows version resource is deliberately deferred: get the bundle built
   and tested first, then revisit versioning.
7. **No crash/error logging in the build.** Declined by the owner — this is a
   demo handed to one machine, not something that needs diagnostics from the
   field. `--windowed` therefore leaves `sys.stderr` as `None` and
   `main.py`'s `logging.basicConfig` is a silent no-op, which is accepted.

### Rename scope

Live references only. Journal entries keep the old names — they are a historical
record and rewriting them would falsify it.

| File | Now | Becomes |
|---|---|---|
| `game/config.py:16` | `TITLE = "Death Lite Game"` | `"Deathlite Game"` |
| `game/config.py` | — | new `VERSION = "0.5"` |
| `web/build.sh:8` | `--title "Death Lite Die"` | `"Deathlite Game"` |
| `web/serve.sh:10` | `--title "Death Lite Die"` | `"Deathlite Game"` |
| `web/README.md:3,33,40` | prose + both example commands | `"Deathlite Game"` |
| `README.md:1` | `# Death Lite Die` | `# Deathlite Game` |

Left alone: `tests/rendering/test_fonts.py:62` renders the string
`"Death Lite 123"` as a font sample, not as a title.

**Filenames and paths drop the space** — `DeathliteGame.exe`,
`dist/DeathliteGame/`, `%LOCALAPPDATA%\DeathliteGame\` — because spaces in
paths are awkward to script around. Everything the player *reads* says
"Deathlite Game". Trivially changed if the owner wants the space carried
through.

---

## The icon

The source is Aegis's own sheet — `hero_aegis` in `data/character_sprites.json`
points at `assets/characters/blue/warrior/idle.png`, a 1536×192 strip of eight
192×192 frames.

Measured ink boxes (all eight idle frames are a subtle bob, near-identical):

```
frame 0   bbox (62, 48) 79×89   centre (101, 92)   <- tallest, most upright
frame 4   bbox (59, 52) 83×85   centre (100, 94)
```

**Superseded — the 128 box was the wrong call.** The original proposal was idle
frame 0 cropped to `Rect(37, 28, 128, 128)`, chosen because 128 is a
whole-integer ratio to 16/32/64/128/256 and so every `.ico` entry would be an
exact nearest-neighbour resample; 48 was to be omitted as the one standard size
that does not divide 128 evenly (2.67×).

Rendering the candidates side by side showed the ratio was never what mattered.
**The margin was.** The warrior occupies only 79×89 of the 192 frame — the rest
is animation headroom the pack ships — so a 128 box spends most of a 16 px icon
on nothing, and at that size the figure breaks into disconnected blocks with no
readable silhouette. Squaring up on the *ink* instead keeps the plume, the
shield cross and the sword legible all the way down; the difference at 16 and
32 px is not subtle. With a tight crop the non-integer ratios stop mattering,
so **48 is kept** and the full standard set ships.

**Chosen — idle frame 0, squared on its ink: `Rect(53, 44, 96, 96)`.** Derived
at build time rather than hard-coded (ink `(62, 48) 79×89` → centre `(101, 92)`,
`max(79, 89)` snapped up to a multiple of 8 → 96), so a repacked sheet still
lands on the figure instead of silently cropping its head off.

**Every size is nearest-neighbour** (`pygame.transform.scale`). `smoothscale`
was rendered alongside and is worse at every size: it blurs pixel art, and at
16 px it reduces the knight to a smudge. The 2.67× upscale to 256 leaves some
pixel blocks a column wider than others, invisible at that size and a far better
trade than an illegible taskbar icon.

If a more dramatic icon is wanted, `attack1.png` **frame 2** is the full swing —
bbox (43, 50) 120×104, centre (103, 102) — and fits the same 128 crop rule at
`Rect(39, 38, 128, 128)`.

**Producing the `.ico` needs no new dependency.** Pillow is not installed and
need not be: pygame can crop and scale the frames and emit PNG bytes, and a
Vista+ `.ico` is a `struct`-packed `ICONDIR` plus an entry table wrapping
PNG-encoded images. A small script under `utilities/` (where the other sprite
tools already live) can write it, so the icon is reproducible from the sheet
rather than a committed binary nobody can regenerate.

Worth doing in the same pass: **`pygame.display.set_icon()` is never called** —
`game/game.py:34` sets the caption only, so the window and taskbar show pygame's
default icon even today. The same crop feeds both, so one script should emit the
`.ico` for the exe and a PNG for `set_icon`.

---

## Proposed layout

Mirrors `web/` exactly, keeping the repo root clean:

```
desktop/
  README.md            # mirrors web/README.md — what each file is, how to build
  DeathliteGame.spec   # PyInstaller spec: datas, excludes, name, icon, windowed
  build.ps1            # mirrors web/build.sh — one command to produce dist/
```

* **datas** — `assets/` minus `unused/` and `*.gif`; `data/` whole.
* **excludes** — `tests`, `utilities`, `pygbag`, `tkinter`, `numpy`. Building
  from `.venv` already keeps numpy out; the exclude is belt-and-braces.
* **output** — `dist/DeathliteGame/`, gitignored alongside `build/`.

Estimated size: **~45–60 MB unpacked, ~30 MB zipped** (pygame's SDL DLLs ~16 MB,
CPython ~12 MB, pruned assets + data ~9 MB, compiled game code ~3 MB). No VC++
redistributable needed — Windows 10/11 ship the UCRT.

### Work, in order

1. Rename + `VERSION = "0.5"`, per the table above. Small and self-contained,
   so it lands first and everything after it reads one name.
2. `desktop/` skeleton — spec, `build.ps1`, `README.md`.
3. Save relocation in `main.py`, guarded on `getattr(sys, "frozen", False)` so
   source runs keep the repo-root `save.json`.
4. Icon script under `utilities/`, emitting the `.ico` and the `set_icon` PNG;
   wire `set_icon` into `Game.__init__`.
5. First build, then a smoke run **from the ZIP, on a clean path** — the only
   test that proves the bundle, since a build launched inside the source tree
   can pass by accidentally reading the repo.
6. Only once that passes: revisit the exe's Windows version resource
   (decision 6).

---

## Open questions

None — all four originally raised here are closed.

* **Name**, **version** and **no logging** — settled by decisions 3, 6 and 7.
* **Asset licensing** — raised because `assets/CREDITS.md` still carries
  `_<FILL IN>_` for the Tiny Swords licence and attribution, and shipping a
  bundle redistributes that art. **Closed by the owner (2026-09-12):** the build
  is not commercial and goes to a small, known group, so the placeholders stay
  as they are. Worth revisiting only if distribution ever widens.

---

## Progress

* **2026-09-12** — Review done, decisions 1–5 confirmed by the owner, this
  journal written. No code, no `desktop/` folder, no build yet.
* **2026-09-12** — Owner closed three of the four open questions: version is
  **0.5**, the game is **"Deathlite Game"** everywhere, and **no error logging**
  goes in because this is a demo build for one machine. The exe's Windows
  version resource waits until the bundle builds and is tested. Journal updated;
  still no code.
* **2026-09-12** — The last open question closed too: the owner waived the
  `assets/CREDITS.md` licensing placeholders, since the build is not commercial
  and reaches only a small known group.
* **2026-09-12** — **Step 1 done.** All six live name references renamed to
  "Deathlite Game" (`config.TITLE`, `web/build.sh`, `web/serve.sh`, three spots
  in `web/README.md`, the `README.md` heading) and `config.VERSION = "0.5"`
  added beside `TITLE`, commented to distinguish it from `save.SAVE_VERSION`.
  Journal entries keep the old names as historical record, and
  `tests/rendering/test_fonts.py`'s `"Death Lite 123"` render sample is left
  alone — it is a font sample, not a title.

  Verified: a headless boot reports the window caption as "Deathlite Game" and
  `config.VERSION` as `0.5`, with `SAVE_VERSION` still `2`. 118 of 119 tests
  pass across `test_menu.py`, `test_window.py`, `test_fonts.py`,
  `test_smoke.py` and `test_save.py`. The one failure,
  `CharacterSelectInstructionsTests::test_content_comes_from_config`, is
  **pre-existing** — it fails identically with this change reverted, and
  belongs to the uncommitted hero-select instruction work in the tree, not to
  the rename. No test asserts `config.TITLE` or the caption, so the rename had
  no test surface to break.

  The full suite afterwards: **2001 passed, 16 failed, 1 skipped** in 13m 18s.
  Every failure maps to a file already modified in the working tree before this
  work began — 13 bomb/blast tests against `combat/weapons/bomb.py`,
  `tests/combat/test_bomb.py` and `data/weapons.json`; the menu instructions
  test against `game/states/character_select_state.py`; and
  `test_repair.py` / `test_village_tidy.py` against `world/gen/village.py` and
  `world/layout.py`. This step's footprint is six files (`game/config.py`,
  `web/build.sh`, `web/serve.sh`, `web/README.md`, `README.md`, this journal),
  none of them under `combat/`, `world/` or `game/states/`.

  Also worth carrying into step 2: **`.venv` has no pytest** — the suite runs on
  the system Python. The *build* must still run from `.venv`, which is what
  keeps numpy out of the bundle.
* **2026-09-12** — **Step 2 done.** PyInstaller 6.22.2 installed into `.venv`,
  and the `desktop/` skeleton written: `DeathliteGame.spec`, `build.ps1`,
  `README.md`. No build run yet — that is step 5.

  **The pruning rule had to change.** Partway through this step a new
  `assets/Super Pixel Effects Gigapack/` appeared on disk — **254 MB across
  61,783 files**, untracked, and referenced by nothing in `data/` or the code.
  Decision 2's "exclude `assets/unused/`" would not have caught it, and a naive
  `assets/` copy would have turned a 7 MB payload into ~300 MB and made
  PyInstaller grind through 62k files.

  So the spec **allow-lists** asset folders rather than deny-listing them.
  `ASSET_DIRS` names the nine top-level folders under `assets/` that the game
  loads from, derived rather than guessed: every `*.png` / `*.ttf` string in
  `data/*.json` and `game/config.py` resolves into one of
  `buildings, characters, effects, enemies, items, projectiles, terrain, ui`,
  plus `fonts`, which carries no directory prefix in the data because
  `game/fonts.py` names its two files directly. The trade-off is that **new art
  in a new top-level folder must be added to `ASSET_DIRS` or it will not
  ship** — noted in `desktop/README.md`, and worth the protection against the
  next pack dropped into `assets/`.

  Two filters ride along: `*.gif` / `*.aseprite` (editor and preview cruft
  beside the loaded sprites), and **any directory named `unused` at any depth**.
  That last one was not in the original plan — validation caught
  `assets/effects/weapons/grave_totem/unused/`, holding the full sheets that
  were repacked into the strips loaded next to them. Matching the name at any
  depth keeps the project's own convention working wherever it is used next.

  Also handled: **PyInstaller's default work directory is `build/`, which the
  pygbag build already owns** (`build/web`, `build/web-cache`). `build.ps1`
  redirects it to `build/pyinstaller` and removes it afterwards unless
  `-KeepWork` is passed. `dist/` and the Gigapack were added to `.gitignore`.

  Verified without building: the spec was stub-executed (PyInstaller's
  `Analysis` / `PYZ` / `EXE` / `COLLECT` replaced with recorders) to exercise
  the real file — **323 entries, 6.86 MB, no missing sources**, nothing from
  `unused/` or the Gigapack, no `.gif`/`.aseprite`, and the ten loaded
  `grave_totem` strips all present while the eight reference originals beside
  them are dropped. `EXE` resolves to `name="DeathliteGame"`, `console=False`,
  `icon=None` (step 4 has not made it yet — the spec tolerates its absence by
  design so the build works before then). `build.ps1` parses clean under
  PowerShell 5.1.
* **2026-09-12** — **Step 3 done.** The save relocation, split the same way
  `config.apply_web_profile()` is: `game/save.py` gains `user_save_path()`,
  which *knows* the per-user location, and `main.py` decides *when* to use it —
  environment detection already lives there, right beside the existing
  `sys.platform == "emscripten"` branch.

  `user_save_path()` returns `%LOCALAPPDATA%\DeathliteGame\save.json`, falling
  back to `%APPDATA%` and then `~/.local/share`, so the caller always gets a
  usable path instead of having to handle `None`. It deliberately does not
  create the directory — `save()` has always done that on first write, which is
  what makes this a two-function change rather than a refactor. `main.py` passes
  it only when `getattr(sys, "frozen", False)`.

  Every read and write already funnels through `Game.save_path`
  (`game/game.py:49`, `:50`, `:101`) and nothing else calls `save_mod.load` or
  `save_mod.save` directly, so one constructor argument covers the whole
  surface.

  Verified: a source run still resolves to the repo-root `save.json`; the frozen
  branch resolves to `%LOCALAPPDATA%\DeathliteGame\save.json`; the
  fallback ladder produces `%APPDATA%` then `~/.local/share` when those
  variables are stripped; and a write into a not-yet-existing directory creates
  it and round-trips (`currency = 1234` read back intact). 28 tests pass across
  `test_save.py`, `test_loading.py` and `test_smoke.py`.
* **2026-09-12** — **Step 4 done.** `utilities/make_icon.py` writes both files
  from one crop: `assets/ui/icon.ico` (256/128/64/48/32/16, 9,924 bytes) for the
  exe and `assets/ui/icon.png` (96×96 native, unresampled) for the window. The
  crop changed from the planned 128 box to a 96 box squared on the ink — see
  *The icon* above for why, and for why 48 came back and `smoothscale` did not.

  The `.ico` is written by hand with `struct`, no new dependency: PNG-compressed
  entries in a plain ICONDIR, which every Windows since Vista reads, at a
  quarter the size of the old BMP+mask form and with alpha intact.

  `pygame.display.set_icon` is now wired into `Game.__init__`, **before**
  `_open_window()` because that is where SDL picks the icon up. It loads
  straight off disk rather than through `Assets`, since it runs before a display
  exists and `convert_alpha` needs one; a missing file logs and leaves pygame's
  default, matching the degrade contract the cursor and sprites already follow.
  The path is `config.WINDOW_ICON`, beside the other menu art constants.

  Verified four ways: the container round-trips (6 contiguous entries, each
  decoding at its declared size, total matching the file length); **Windows'
  own parser** loads it and resolves every requested size; **PyInstaller's**
  `IconFile` parses it and builds the `RT_GROUP_ICON` structures, with the 128
  entry round-tripping to `0x80` correctly (PyInstaller reads `bWidth` signed
  and reports it as `-128`, which is cosmetic); and a headless boot sets the
  icon, returns `False` without raising when pointed at a missing file, and
  recovers. The spec now resolves `icon=` to the `.ico`, `icon.png` ships and
  `icon.ico` does not — it is a build input, added to `SKIP_SUFFIXES`.

  116 of 117 tests pass across `test_window.py`, `test_menu.py`,
  `test_smoke.py` and `test_assets.py`; the single failure is the same
  pre-existing `test_content_comes_from_config`.
* **2026-09-12** — **Step 5 done. The bundle builds, ships and runs.**

  `dist/DeathliteGame/` — **42.1 MB across 441 files**, zipping to **22.2 MB**,
  comfortably under the 45–60 MB / ~30 MB estimated in step 2. The exe itself is
  3.2 MB; the rest is `_internal/`.

  Verified from a **fresh extraction of the shipped ZIP into a clean temp path
  outside the repo**, which is the only test that proves the bundle — a build
  launched inside the source tree can pass by accidentally reading the repo. It
  starts, the window titles itself "Deathlite Game", Aegis appears in the title
  bar at 16 px, and the menu renders its background, logo, buttons and fonts
  entirely from the bundle. `assets/characters`, `terrain`, `ui`, `fonts` and
  `data` are all present in `_internal/`; `assets/unused` and the Gigapack are
  both absent.

  **The save was proven in both directions in the real frozen runtime**, not
  inferred. A console build (below) printed at startup:

      INFO game.save: no save at %LOCALAPPDATA%\DeathliteGame\save.json -- starting fresh
      INFO game.content: content loaded: 9 weapons, 14 enemies, 1 bosses, 3 characters, ...

  and pressing the mute key wrote that same file back with `settings.muted:
  true`, `version: 2` and the three starter heroes.

  Two fixes came out of this, both now in `build.ps1`:

  * **`Compress-Archive` failed** on the very first run — it opens every file
    itself and aborts the whole archive if anything else holds one, which an
    antivirus scanning a freshly written `_internal/` will. Replaced with
    `[System.IO.Compression.ZipFile]::CreateFromDirectory`, which is also
    several times faster on a few hundred files.
  * **`-Console`** is now a first-class flag rather than a manual incantation:
    it sets `DLG_CONSOLE=1`, which the spec reads to attach a console, and
    sends the result to `dist_console/` so it can never be confused with the
    shipping build. Worth keeping precisely *because* file logging was declined
    (decision 7) — it is the only way to see inside a packaged build, and it is
    what settled the save-path question above. `dist_console/` is gitignored.

  One false alarm worth recording so it is not re-investigated: the mute key
  appeared not to work under synthetic input, which briefly looked like a
  packaging bug. It was the test harness — `keybd_event` was being passed
  scancode 0, and SDL2 reads scancodes from raw input. With the real scancode
  (`MapVirtualKey(0x4D, 0)` → 50) it worked first time. Arrow keys had masked
  this by working anyway.

* **2026-09-12** — **Step 6 done, and with it the whole plan.** The Windows
  version resource is embedded, so right-click → Properties → Details now reads
  `0.5` and Task Manager names the process "Deathlite Game" rather than
  `DeathliteGame.exe`.

  **It is built from `config.VERSION`, not restated.** The spec imports
  `game.config` directly — safe and free, because that module is contractually
  dependency-free, so the import pulls in no pygame and nothing else (verified:
  importing it adds exactly one module, `game`). `build.ps1` already read the
  same constant for the ZIP filename, so **one constant now moves the exe's
  version, the properties dialog and the archive name together**, with nothing
  to keep in sync by hand.

  `FileDescription` carries `config.TITLE` because that, not the filename, is
  what Task Manager displays. **`CompanyName` and `LegalCopyright` are
  deliberately blank**: a version resource is a provenance claim, there is no
  company or filed copyright to name, and an invented one would be worse than
  an empty field. Both are one-line fills if that ever changes.

  Verified by reading the resource back out of the built exe with
  `[System.Diagnostics.FileVersionInfo]` — the same API Explorer uses:

      FileDescription 'Deathlite Game'    ProductName    'Deathlite Game'
      FileVersion     '0.5'               ProductVersion '0.5'
      InternalName    'DeathliteGame'     OriginalFilename 'DeathliteGame.exe'
      numeric          0.5.0.0            icon still embedded (32x32 probe)

  Then a final end-to-end pass from a fresh unzip of the shipped archive: it
  runs, titles itself "Deathlite Game", reports "Deathlite Game" as its process
  description, and writes its save to `%LOCALAPPDATA%`. All test artifacts
  removed afterwards.

## Status

**Done. The demo is ready to hand over.** `dist/DeathliteGame-0.5.zip`, 22.3 MB
— unzip anywhere, run `DeathliteGame.exe`. No Python, no VC++ redistributable.

    powershell -ExecutionPolicy Bypass -File desktop\build.ps1 -Zip

All six planned steps are complete and every decision in this journal is
settled. Worth knowing for whoever picks this up next:

* **Bumping the version is one edit** — `config.VERSION` in `game/config.py`.
* **New art in a new top-level `assets/` folder must be added to `ASSET_DIRS`**
  in the spec, or it will not ship. That is the cost of the allow-list, and it
  is what stops the next 254 MB pack from joining the build unnoticed.
* **`build.ps1 -Console`** is the only way to see inside a packaged build,
  since file logging was declined.

### 2026-09-13 -- moved under `dist/`

All packaging now lives in one place: this build is `dist/desktop/` (spec,
`build.ps1`, README) and the browser build is `dist/web/`, with `dist/README.md`
as the index. Outputs moved with the configs: the shipping bundle and ZIP go to
`dist/desktop/out/`, the `-Console` build to `dist/desktop/out-console/`, and
PyInstaller's intermediates to `dist/desktop/work/` (all gitignored; the old
`dist/`, `dist_console/` and `build/pyinstaller` locations are gone). The spec
resolves the repo root as `Path(SPECPATH).parent.parent` and `build.ps1` walks
two levels up; nothing about what ships changed.
