# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows desktop build of Deathlite Game.

Mirrors `../web/pygbag.ini`'s role for the browser build: this file is the
single place that says what goes into the bundle. Design notes and the decision
log are in `../../documentation/journals/desktop_packaging_journal.md`.

Build it with `build.ps1` rather than by hand -- that script pins the Python to
`.venv` (which is what keeps numpy out of the bundle) and redirects PyInstaller's
work directory to `work/` here, away from `<repo>/build/`, which pygbag owns.

Two things worth knowing before editing:

* **`onedir`, not onefile** (owner's call). The output is a folder shipped as a
  ZIP. Onefile would re-extract every asset to %TEMP% on each launch and its
  self-extracting stub attracts antivirus warnings.
* **Assets are allow-listed, never deny-listed.** `assets/` also holds reserve
  packs that the game does not load -- `unused/`, the reserve art library
  (hundreds of MB, tens of thousands of files). Listing what ships
  means a new pack dropped into `assets/` tomorrow cannot silently add itself
  to the build; a deny-list would let it in. `ASSET_DIRS` below was derived from
  every asset path referenced by `data/*.json` and `game/config.py`.
"""
import os
import re
import sys
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable,
    VarFileInfo, VarStruct, VSVersionInfo,
)

ROOT = Path(SPECPATH).parent.parent   # repo root; SPECPATH is dist/desktop
NAME = "DeathliteGame"                # exe / dist folder name (no space: paths)

# --- what ships ---------------------------------------------------------------
# Top-level `assets/` folders the game actually loads from. Derived, not guessed:
# every "*.png" / "*.ttf" string in data/*.json and game/config.py resolves into
# one of these. `fonts` carries no directory prefix in the data (game/fonts.py
# names the files directly) but is required all the same, and `music` holds
# the two streamed tracks named by `config.MUSIC_TRACKS` (about 8.5 MB, the
# largest single contribution to the bundle). `sound_effects` holds the cues
# named by `config.SOUND_EFFECTS`; its `unused/` folder of Freesound originals
# is skipped by SKIP_DIRS below, like every other `unused/`.
ASSET_DIRS = [
    "buildings", "characters", "effects", "enemies",
    "fonts", "items", "music", "projectiles", "sound_effects",
    "terrain", "ui",
]

# Editor/preview cruft that lives beside the sprites the game loads. `.ico` is
# here because `assets/ui/icon.ico` is a *build input* -- PyInstaller embeds it
# into the exe as a resource, and nothing loads it at runtime (the window icon
# is the `.png` beside it, which does ship).
SKIP_SUFFIXES = {".gif", ".aseprite", ".ico"}

# `unused` is this project's name for "source-pack originals kept for reference",
# and it appears at more than one depth: `assets/unused/` at the top, but also
# e.g. `assets/effects/weapons/grave_totem/unused/`, which holds the full sheets
# that were repacked into the strips loaded beside it. Matched at any depth, so
# the convention keeps working wherever it is used next.
SKIP_DIRS = {"unused"}


def _tree(rel: str) -> list[tuple[str, str]]:
    """(source, dest-dir) pairs for every shippable file under `ROOT/rel`.

    Per-file rather than per-directory so the filters actually apply -- handing
    PyInstaller a directory would copy the previews in with the sprites.
    """
    base = ROOT / rel
    out = []
    for src in sorted(base.rglob("*")):
        if not src.is_file():
            continue
        if src.suffix.lower() in SKIP_SUFFIXES:
            continue
        if SKIP_DIRS & set(p.lower() for p in src.relative_to(base).parts[:-1]):
            continue
        out.append((str(src), str(src.parent.relative_to(ROOT))))
    return out


datas = []
for _d in ASSET_DIRS:
    datas += _tree(f"assets/{_d}")
datas += _tree("data")                       # the JSON content layer, whole

# Attribution rides along even though it is not loaded at runtime.
_credits = ROOT / "assets" / "CREDITS.md"
if _credits.exists():
    datas.append((str(_credits), "assets"))

# --- what does not ship -------------------------------------------------------
# `.venv` holds only pygame + pygbag + PyInstaller, so most of this never had a
# chance to be pulled in; it is belt-and-braces against a future dependency.
# numpy in particular is imported by three scripts under `tools/asset_pipeline/` and would
# add ~30 MB if it ever landed in the runtime path.
excludes = [
    "numpy", "tkinter", "pygbag", "pytest", "_pytest",
    "setuptools", "pip", "PIL", "IPython",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],                 # nothing dynamic: no importlib anywhere
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# The icon is produced in step 4 of the plan (from Aegis's idle sheet) and may
# not exist yet -- the build must not hard-fail before then.
_icon = ROOT / "assets" / "ui" / "icon.ico"
icon = str(_icon) if _icon.exists() else None

# A packaged build is windowed, so it has no stdout/stderr and `logging` goes
# nowhere -- deliberate (the owner declined crash logging for this demo), but it
# leaves no way to see what a misbehaving bundle is doing. Setting DLG_CONSOLE=1
# at *build* time produces an otherwise identical build with a console attached,
# which is how you read the startup log (the save path it resolved, refused
# vsync, missing assets) without editing this file.
CONSOLE = os.environ.get("DLG_CONSOLE") == "1"

# --- Windows version resource -------------------------------------------------
# What right-click -> Properties -> Details shows, and the name Task Manager
# gives the running process (that is `FileDescription`, not the filename).
#
# The numbers are read out of `game/config.py` rather than restated here, so
# they cannot drift from the game's own `config.VERSION`. That import is safe
# and free: `config.py` is contractually dependency-free -- it imports nothing
# from the project -- so it pulls in no pygame and nothing else.
sys.path.insert(0, str(ROOT))
from game import config as _cfg


def _vers4(text: str) -> tuple:
    """'0.5' -> (0, 5, 0, 0). Windows wants exactly four 16-bit fields."""
    parts = [int(p) for p in re.findall(r"\d+", text)[:4]]
    return tuple((parts + [0, 0, 0, 0])[:4])


_v4 = _vers4(_cfg.VERSION)

# CompanyName and LegalCopyright are deliberately blank. A version resource is a
# provenance claim, and there is no company or filed copyright to name here --
# an invented one would be worse than an empty field. Fill them in if this ever
# ships under a name.
version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=_v4, prodvers=_v4,
        mask=0x3F, flags=0x0,
        OS=0x40004,               # VOS_NT_WINDOWS32
        fileType=0x1,             # VFT_APP
        subtype=0x0, date=(0, 0),
    ),
    kids=[
        StringFileInfo([StringTable("040904B0", [   # US English, Unicode
            StringStruct("CompanyName", ""),
            StringStruct("FileDescription", _cfg.TITLE),
            StringStruct("FileVersion", _cfg.VERSION),
            StringStruct("InternalName", NAME),
            StringStruct("LegalCopyright", ""),
            StringStruct("OriginalFilename", f"{NAME}.exe"),
            StringStruct("ProductName", _cfg.TITLE),
            StringStruct("ProductVersion", _cfg.VERSION),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,            # onedir: binaries live in _internal/
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                        # UPX-packed exes trip antivirus heuristics
    console=CONSOLE,                  # windowed unless DLG_CONSOLE=1 (see above)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
    version=version_info,             # built above from config.VERSION
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=NAME,
)
