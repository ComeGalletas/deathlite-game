"""Every asset the game names ships in the desktop bundle (BLD-005).

`dist/desktop/DeathliteGame.spec` allow-lists the `assets/` folders that go
into the .exe (`ASSET_DIRS`), so the reserve library under `assets/unused/`
can never join the build by accident. The cost is that a new top-level folder
ships only once someone adds it to that list. `assets/infused/` was missed:
the 2026-10-02 rebuild would have dropped all 40 elemental sheets, and a
windowed exe has no stderr to show the `asset missing` warnings.

These tests run the real spec, not a copy of its rules. The PyInstaller names
it uses (`Analysis`, `PYZ`, `EXE`, `COLLECT`, the version-resource classes)
are stubbed, so the spec runs on the system Python the suite uses, which has
no PyInstaller. They then check every asset path the game names against the
spec's `datas`: the sprite sheets in `data/**/*.json`, the paths in
`game/config.py` and the bundled fonts in `game/fonts.py`.
"""
import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from game import config, fonts
from game.assets import ASSETS_DIR

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "dist" / "desktop" / "DeathliteGame.spec"
ASSET_SUFFIXES = (".png", ".ttf", ".otf", ".wav", ".ogg", ".mp3")


class _Recorder:
    """Stands in for every PyInstaller call; keeps what it was given."""

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs
        self.pure = self.scripts = self.binaries = self.datas = []


def _run_spec() -> dict:
    """Execute the spec as PyInstaller would; return its namespace."""
    versioninfo = types.ModuleType("PyInstaller.utils.win32.versioninfo")
    for name in ("FixedFileInfo", "StringFileInfo", "StringStruct",
                 "StringTable", "VarFileInfo", "VarStruct", "VSVersionInfo"):
        setattr(versioninfo, name, _Recorder)
    stubs = {
        "PyInstaller": types.ModuleType("PyInstaller"),
        "PyInstaller.utils": types.ModuleType("PyInstaller.utils"),
        "PyInstaller.utils.win32": types.ModuleType("PyInstaller.utils.win32"),
        "PyInstaller.utils.win32.versioninfo": versioninfo,
    }
    ns = {"__file__": str(SPEC), "SPECPATH": str(SPEC.parent),
          "Analysis": _Recorder, "PYZ": _Recorder, "EXE": _Recorder,
          "COLLECT": _Recorder}
    saved_path = list(sys.path)       # the spec puts the repo root on it
    try:
        with mock.patch.dict(sys.modules, stubs):
            exec(compile(SPEC.read_text(encoding="utf-8"), str(SPEC), "exec"), ns)
    finally:
        sys.path[:] = saved_path
    return ns


def _strings(node):
    """Every string inside a nested JSON / config value."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            yield from _strings(v)


def _referenced_assets() -> dict[str, str]:
    """{path relative to assets/: where it is named}."""
    refs: dict[str, str] = {}
    for path in sorted((REPO / "data").rglob("*.json")):
        for s in _strings(json.loads(path.read_text(encoding="utf-8"))):
            if s.lower().endswith(ASSET_SUFFIXES):
                refs.setdefault(s.replace("\\", "/"), path.relative_to(REPO).as_posix())
    for name, value in vars(config).items():
        if name.isupper():
            for s in _strings(value):
                if s.lower().endswith(ASSET_SUFFIXES):
                    refs.setdefault(s.replace("\\", "/"), f"config.{name}")
    for fname in fonts._FILES.values():
        refs.setdefault(f"fonts/{fname}", "fonts._FILES")
    return refs


class DesktopBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = _run_spec()
        # (source, dest-dir) pairs -> the shipped files, relative to the repo.
        cls.shipped = {
            Path(src).resolve().relative_to(REPO).as_posix()
            for src, _dest in cls.ns["datas"]
        }
        cls.refs = _referenced_assets()

    def test_the_scan_finds_the_game_s_assets(self):
        """Control: the scan really sees the data, config and font paths, so
        an empty scan cannot pass the test below."""
        self.assertGreater(len(self.refs), 300)
        self.assertIn("ui/icon.png", self.refs)                # config
        self.assertIn("music/gameplay-1.mp3", self.refs)       # config dict
        self.assertTrue(any(r.startswith("infused/") for r in self.refs))
        self.assertTrue(any(r.startswith("fonts/") for r in self.refs))

    def test_every_named_asset_exists(self):
        missing = sorted(r for r in self.refs if not (ASSETS_DIR / r).is_file())
        self.assertEqual(missing, [], "named but not on disk")

    def test_every_named_asset_ships(self):
        """The bug: a folder the data loads from but `ASSET_DIRS` omits."""
        dropped = sorted(f"{r}  (named in {self.refs[r]})"
                         for r in self.refs if f"assets/{r}" not in self.shipped)
        self.assertEqual(dropped, [],
                         "add the folder to ASSET_DIRS in DeathliteGame.spec")

    def test_the_infused_sheets_ship(self):
        """The regression on its own: all of `assets/infused/` that loads."""
        infused = [r for r in self.refs if r.startswith("infused/")]
        self.assertGreaterEqual(len(infused), 40)
        self.assertTrue(all(f"assets/{r}" in self.shipped for r in infused))

    def test_every_allow_listed_folder_exists(self):
        """A stale entry would silently ship nothing."""
        for d in self.ns["ASSET_DIRS"]:
            self.assertTrue((ASSETS_DIR / d).is_dir(), d)

    def test_the_reserve_library_stays_out(self):
        """The point of allow-listing: nothing under any `unused/` folder,
        and no editor or preview files."""
        self.assertFalse([p for p in self.shipped if "/unused/" in p])
        self.assertFalse([p for p in self.shipped
                          if p.endswith((".gif", ".aseprite", ".ico"))])

    def test_the_data_layer_ships_whole(self):
        on_disk = {p.relative_to(REPO).as_posix()
                   for p in (REPO / "data").rglob("*") if p.is_file()}
        self.assertEqual(on_disk - self.shipped, set())


if __name__ == "__main__":
    unittest.main()
