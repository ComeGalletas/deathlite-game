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
| `pygbag.ini` | Bundle exclusions (`.venv`, `tests/`, `documentation/`, `tools/`, `assets/unused/`, `assets/music/`, `assets/sound_effects/`, …). pygbag reads it from the **current working directory**, which is why the helpers below `cd` into this folder. |
| `build.sh` | Build only; copies the finished bundle to `out/` here and vendors the pygame-ce wheel into `out/cdn/`. |
| `vendor_wheels.py` | Called by `build.sh`: resolves the wheels `main.py` needs from pygbag's index and copies them into `out/cdn/` (BLD-006). |
| `serve.sh` | Rebuild + serve at <http://localhost:8000> through pygbag's dev server. |
| `out/` | Generated, gitignored: the deliverable (`index.html`, the `.apk` and `.tar.gz` named after the checkout's folder, e.g. `deathlite-game.apk`, and `cdn/`). |

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

**The web release has no audio** (owner, 2026-09-30, BLD-004). The profile
sets `config.AUDIO_ENABLED = False`: pygame comes up with no mixer device
(`systems/mixer_backend.py` `init_pygame`), no sound effect or music track
is loaded, and every audio call is a no-op (the Options volume rows, its mute row and the
M key still change their values, which drive nothing). The desktop build
keeps its music and sound effects. Journal:
`../../documentation/journals/web_audio_journal.md`.

`pygbag.ini` leaves `assets/music/` and `assets/sound_effects/` out of the
bundle. Sizes in decimal MB: 9.4 MB of audio used to ship (the 5.9 MB of
`sound_effects/unused/` originals were already excluded). The five nested
`unused/` folders under `effects/`, `enemies/` and `ui/` (0.8 MB) and the
`CLAUDE.md` and `FUNCTIONAL_README.md` files are excluded too. The apk
measured 19.6 MB with the audio (BLD-003.6), 10.4 MB without it, and 9.5 MB
without all of these (9,538,932 bytes).

That also settles the build failure BLD-003.6 found. On Windows and macOS,
pygbag 0.9.3 refuses any MP3, WAV or AIFF file with no OGG beside it ("Use
OGG format instead", `pygbag/pack.py`), so both the MP3 music and the WAV
cues tripped it (the error names only the first file it meets, the music).
On Linux it first tries to transcode them with ffmpeg, and without ffmpeg
stops on an MP3 with a different message. With both folders out of the
bundle `build.sh` and `serve.sh` build as they stand on any of them.

**Serving `out/` with a plain static server** (BLD-006,
`../../documentation/journals/web_wheel_journal.md`). The page loads its
pygame-ce wheel separately from the bundle, and pygbag 0.9.3 picks where from
by the page's address (`pygbag/support/cross/aio/pep0723.py`, a prefix test
on the address):

- an address starting with `http://localhost:8`: always from
  `http://localhost:8000/cdn/` (the port is fixed in pygbag).
  - `http://localhost:8000/`: that is the page's own `out/cdn/`. `build.sh`
    vendors the wheel there (`vendor_wheels.py`, below), so
    `python -m http.server -d dist/web/out 8000` serves a page that boots.
    Without it the server log shows `GET /cdn/cp312/pygame_ce-...whl 404`
    and the page stops on `OSError: [Errno 8] Bad file descriptor`.
  - any other such port (8001, 8080, 81, ...): the wheel request goes to
    port 8000, another origin, and fails ("Failed to fetch" in the
    console); the page stays grey whatever is vendored. Use port 8000.
- any other address (`http://127.0.0.1:<port>/`, a real host): from the
  public CDN the index names, `https://pygame-web.github.io/cdn/`, so the
  vendored copy is not used and the browser needs the internet. Measured on
  `127.0.0.1:8001` in Chrome, 2026-10-02.

`vendor_wheels.py` resolves the wheel as the browser runtime does. The
browser's Python and runtime come from the built `out/index.html`; the
package base, renaming table, index versions and the local `cdn/` address
come from the installed pygbag's runtime code (standing in for the CDN's copy
of the same version, which the browser runs); the wheel list from pygbag's
package index and the runtime's target from the runtime itself, both on the
CDN. So a pygbag upgrade moves with it, and if pygbag's code changes shape
the build stops and says what it could not find.

Each build re-reads the 1.5 KB index, since the browser reads the live index
at page load and the vendored wheel must be the one it names. The wheel is
downloaded once and cached in `<repo>/build/web-cache/cdn/wheels/` (apart from
the helper's own files in `cdn/`); the runtime's
target (from its 6.7 MB data file) is cached with that file's stamp and read
again only when a HEAD request shows the file changed or gives no ETag,
Last-Modified or length to compare (a server that refuses
HEAD keeps the cached target, with a note in the build output). An offline build uses
the cache. Every download and every cached wheel is checked before use (an
index must name an http(s) `-CDN-` and a wheel; a wheel's every member must
read back with its CRC), so a bad response is refused rather than cached.
pygbag empties `build/web-cache/` itself when its version changes, so the
first build after a pygbag upgrade downloads again.

Two consequences when testing by hand:

- `out/` is tied to the index of its build day. If pygame-web publishes a
  new pygame-ce under the same pygbag version, an old `out/` asks for a wheel
  it does not have: rebuild.
- `http.server` lets Chrome reuse a cached bundle and wheel from an earlier
  build. After a rebuild, reload with Ctrl+Shift+R.

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
produce the bundle without starting the server. To serve a bundle `build.sh`
made, statically, run from the repo root and open `http://localhost:8000/`
(port 8000 exactly; see "Serving `out/`" above):

```bash
python -m http.server -d dist/web/out 8000
```

Load `http://localhost:8000/#debug` to keep pygbag's on-page Python console
visible — import/runtime tracebacks print there, not in the browser JS console.

## Deploy (GitHub Pages — not wired yet)

`out/` is the publishable artifact. On an address that does not start with `http://localhost:8`
the page takes its pygame-ce wheel from the public pygbag CDN, as it did on
`127.0.0.1:8001` (BLD-006), so the vendored `out/cdn/` copy is simply unused
there. Not yet verified on a real host: the Pages workflow itself, sketched in
`documentation/journals/pygbag.md`, is not done (W9, parked).
