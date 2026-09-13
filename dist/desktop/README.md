# Desktop build (PyInstaller)

Everything needed to package **Deathlite Game** as a Windows `.exe` lives here,
beside the browser build in [`../web/`](../web/); [`../README.md`](../README.md)
is the index of both. Design notes and the decision log are in
[`../../documentation/journals/desktop_packaging_journal.md`](../../documentation/journals/desktop_packaging_journal.md).

## Files

| File | Purpose |
|------|---------|
| `DeathliteGame.spec` | The whole bundle definition: which assets ship, what is excluded, the exe's name and icon. |
| `build.ps1` | Build, report the size, optionally ZIP it. Pins the Python to `.venv` and keeps PyInstaller's work files in `work/` here. |
| `out/`, `out-console/`, `work/` | Generated, gitignored: the shipping bundle, the diagnostic bundle, PyInstaller's intermediates. |

The entry script is `../../main.py`, shared with the source and web builds.

## Commands

```powershell
powershell -ExecutionPolicy Bypass -File dist\desktop\build.ps1
```

Add `-Zip` to also produce `out/DeathliteGame-0.5.zip` (the version is read out
of `game/config.py`, so it cannot drift from the game):

```powershell
powershell -ExecutionPolicy Bypass -File dist\desktop\build.ps1 -Zip
```

Output is `out/DeathliteGame/` — a folder containing `DeathliteGame.exe` and an
`_internal/` directory. **Ship the whole folder, not just the exe.** The
recipient unzips it anywhere and double-clicks the exe; no Python, and no VC++
redistributable (Windows 10/11 already ship the UCRT).

## Debugging a packaged build

A windowed build has no stdout or stderr at all, so `logging` goes nowhere and a
misbehaving bundle tells you nothing. `-Console` builds an otherwise identical
exe with a console attached, into `out-console/` so it can never be mistaken
for the shipping one:

```powershell
powershell -ExecutionPolicy Bypass -File dist\desktop\build.ps1 -Console
```

Run that exe from a terminal and the startup log appears on stderr — which save
path it resolved, whether vsync was refused, any missing asset. This is how the
`%LOCALAPPDATA%` save path was confirmed in the real frozen runtime rather than
assumed.

## Things that are easy to get wrong

**Build from `.venv`, not the system Python.** `build.ps1` enforces this. The
venv holds only pygame and the build tools; the system Python has numpy, which
would add ~30 MB if it ever became a bundle candidate. (The *test* suite is the
other way round — pytest is installed system-wide, not in the venv.)

**PyInstaller's work directory is redirected.** Its default is `<repo>/build/`,
which pygbag owns (`build/web`, `build/web-cache`). `build.ps1` sends it to
`work/` in this folder and deletes it afterwards unless you pass `-KeepWork`.

**Assets are allow-listed, not deny-listed.** `ASSET_DIRS` in the spec names the
nine folders under `assets/` that the game actually loads; anything else is
ignored. This matters more than it sounds: `assets/` also holds `unused/`, the
reserve art library (hundreds of MB, tens of thousands of files) that the game
never references. A deny-list would let the next pack dropped in there silently
join the build. **If you add art in a new top-level folder under `assets/`, add
it to `ASSET_DIRS` or it will not ship.**

The shipped payload is ~320 files and ~7 MB of art and data.

**`onedir`, not onefile.** Deliberate. Onefile re-extracts every asset to
`%TEMP%` on each launch — seconds of cold start — and its self-extracting stub
is the shape antivirus and SmartScreen flag most often.

## Version

`config.VERSION` in `game/config.py` is the single source. The spec imports it
to build the Windows version resource (right-click -> Properties -> Details),
and `build.ps1` reads it for the ZIP filename -- so bumping that one constant
moves the exe's version, the properties dialog and the archive name together.
There is nothing to keep in sync by hand.

`FileDescription` is what **Task Manager** shows as the process name, so it
carries `config.TITLE` rather than the filename. `CompanyName` and
`LegalCopyright` are deliberately blank: a version resource is a provenance
claim, and an invented one would be worse than an empty field.

## Where the save goes

The frozen build writes to `%LOCALAPPDATA%\DeathliteGame\save.json`, not into the
bundle. Running from source is unchanged and still uses the repo-root
`save.json`. Delete the LocalAppData file to test a first-launch experience.
