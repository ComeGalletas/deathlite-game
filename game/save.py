"""Human-readable JSON save file (spec 4.7).

Persists: unlocked characters, Salvage currency, purchased meta upgrades, best
run stats, discovered item ids, the item stash + equipped slots, and settings.

Robustness rules from the spec:
  * a missing file yields a fresh default -- never an error
  * a corrupt file is backed up to `<name>.corrupt` and replaced with a default
  * unknown / missing keys fall back to defaults (forward/backward compatible)
  * writes are atomic (temp file + replace) so a crash mid-write can't shred it
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

SAVE_VERSION = 2      # 2: per-hero `heroes` state (six-weapon system P5)
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "save.json"

# Where a *packaged* build keeps its save instead. `DEFAULT_PATH` resolves next
# to this module, which is right from the source tree and wrong the moment the
# game is frozen: PyInstaller sets `__file__` to a path inside the bundle, so
# the save would land in the install folder -- unwritable under `Program Files`.
# `main.py` hands this to `Game(save_path=...)` when `sys.frozen` is set; a
# source run never sees it and still uses `DEFAULT_PATH`.
APP_DIR_NAME = "DeathliteGame"


def user_save_path(app: str = APP_DIR_NAME) -> Path:
    """Per-user, writable save location for a packaged build.

    `%LOCALAPPDATA%\\<app>\\save.json` on Windows. Falls back to `%APPDATA%`,
    then to a dot-directory under the home folder -- so the caller always gets a
    usable path rather than having to handle `None` on a machine (or platform)
    without those variables. The directory is not created here: `save()` already
    does that on first write.
    """
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / app / "save.json"

# Characters available from the very first launch.
_STARTER_CHARACTERS = ["aegis", "kestrel", "nihil"]

# Per-run best records are bucketed by difficulty and never compared across
# buckets (a Fast run's time only ranks against other Fast runs). Mirror
# config.DIFFICULTY_ORDER; kept local so this module stays dependency-free.
_RECORD_DIFFICULTIES = ("normal", "fast", "super_fast")
_RECORD_KEYS = ("time", "level", "kills", "damage_dealt")

# Mirror config.KEY_LAYOUTS / DEFAULT_KEY_LAYOUT, local for the same reason.
# An unknown layout name in the file falls back to the default (CB-5).
_KEY_LAYOUTS = ("wasd_move", "arrows_move")
_DEFAULT_KEY_LAYOUT = "wasd_move"
_DISPLAY_MODES = ("windowed", "borderless")   # game/display/window.MODES
_RENDER_ASPECTS = ("16:9", "21:9")            # game/display/window.ASPECTS


@dataclass
class SaveData:
    version: int = SAVE_VERSION
    currency: int = 0
    unlocked_characters: list[str] = field(default_factory=lambda: list(_STARTER_CHARACTERS))
    meta: dict[str, int] = field(default_factory=dict)              # upgrade id -> level
    best: dict[str, float] = field(default_factory=dict)           # stat -> best value
    # difficulty -> {stat -> best value}; independent per bucket (see above).
    records: dict = field(default_factory=lambda: {
        d: {} for d in _RECORD_DIFFICULTIES})
    discovered_items: list[str] = field(default_factory=list)
    stash: list[dict] = field(default_factory=list)               # serialised Items
    equipped: dict[str, str | None] = field(default_factory=lambda: {
        "weapon": None, "armor": None, "accessory": None})
    settings: dict = field(default_factory=lambda: {
        "muted": False, "volume": 0.7, "key_layout": _DEFAULT_KEY_LAYOUT})
    # P5 (design §20): per hero, whether the boss has been cleared with that
    # hero (which unlocks the main-weapon choice) and the chosen main weapon.
    heroes: dict[str, dict] = field(default_factory=dict)

    # --- per-hero state (P5) -------------------------------------
    def hero(self, cid: str) -> dict:
        return self.heroes.setdefault(str(cid), {"cleared": False, "main_weapon": None})

    def hero_cleared(self, cid: str) -> bool:
        return bool(self.heroes.get(str(cid), {}).get("cleared", False))

    def mark_cleared(self, cid: str) -> None:
        self.hero(cid)["cleared"] = True

    def main_weapon(self, cid: str) -> str | None:
        """The chosen main weapon, only once the hero has cleared the boss."""
        h = self.heroes.get(str(cid))
        if not h or not h.get("cleared"):
            return None
        return h.get("main_weapon") or None

    def set_main_weapon(self, cid: str, weapon_id: str | None) -> None:
        self.hero(cid)["main_weapon"] = str(weapon_id) if weapon_id else None

    # --- helpers -------------------------------------------------
    def beaten_records(self, stats: dict, difficulty: str = "normal") -> list[str]:
        """Which of this difficulty's records `stats` would beat.

        Must be asked **before** `record_best`, which overwrites the values it
        compares against -- afterwards every answer is "no". It shares
        `_RECORD_KEYS` and the comparison with `record_best` on purpose: a run
        that this reports as a new best is exactly a run that one stores, so a
        screen can never advertise a record the save did not take.
        """
        if difficulty not in _RECORD_DIFFICULTIES:
            difficulty = "normal"
        bucket = self.records.get(difficulty, {})
        return [key for key in _RECORD_KEYS
                if float(stats.get(key, 0)) > float(bucket.get(key, 0.0))]

    def record_best(self, stats: dict, difficulty: str = "normal") -> None:
        if difficulty not in _RECORD_DIFFICULTIES:
            difficulty = "normal"
        bucket = self.records.setdefault(difficulty, {})
        for key in _RECORD_KEYS:
            val = float(stats.get(key, 0))
            if val > self.best.get(key, 0.0):          # legacy all-difficulty max
                self.best[key] = val
            if val > bucket.get(key, 0.0):             # per-difficulty record
                bucket[key] = val

    def add_item(self, item_dict: dict) -> None:
        self.stash.append(item_dict)
        iid = item_dict.get("item_id")
        if iid and iid not in self.discovered_items:
            self.discovered_items.append(iid)

    def equipped_items(self) -> list[dict]:
        by_id = {it["item_id"]: it for it in self.stash}
        return [by_id[i] for i in self.equipped.values() if i and i in by_id]


def _coerce(raw: dict) -> SaveData:
    """Build a SaveData from an arbitrary dict, ignoring junk, filling gaps.
    Every field is defended individually -- a bad value never propagates."""
    d = SaveData()
    if not isinstance(raw, dict):
        return d
    if _is_int(raw.get("currency")):
        d.currency = int(raw["currency"])
    if isinstance(raw.get("unlocked_characters"), list) and raw["unlocked_characters"]:
        d.unlocked_characters = [str(c) for c in raw["unlocked_characters"]]
    if isinstance(raw.get("meta"), dict):
        d.meta = {str(k): int(v) for k, v in raw["meta"].items() if _is_int(v)}
    if isinstance(raw.get("best"), dict):
        d.best = {str(k): float(v) for k, v in raw["best"].items() if _is_num(v)}
    if isinstance(raw.get("records"), dict):
        for diff, vals in raw["records"].items():
            if diff in _RECORD_DIFFICULTIES and isinstance(vals, dict):
                d.records[diff] = {str(k): float(v)
                                   for k, v in vals.items() if _is_num(v)}
    if isinstance(raw.get("discovered_items"), list):
        d.discovered_items = [str(x) for x in raw["discovered_items"]]
    if isinstance(raw.get("stash"), list):
        d.stash = [x for x in raw["stash"] if isinstance(x, dict) and "item_id" in x]
    if isinstance(raw.get("equipped"), dict):
        for slot in ("weapon", "armor", "accessory"):
            v = raw["equipped"].get(slot)
            d.equipped[slot] = str(v) if v else None
    if isinstance(raw.get("heroes"), dict):
        for cid, h in raw["heroes"].items():
            if not isinstance(h, dict):
                continue
            mw = h.get("main_weapon")
            d.heroes[str(cid)] = {"cleared": bool(h.get("cleared", False)),
                                  "main_weapon": str(mw) if mw else None}
    if isinstance(raw.get("settings"), dict):
        d.settings.update(raw["settings"])
    if d.settings.get("key_layout") not in _KEY_LAYOUTS:
        d.settings["key_layout"] = _DEFAULT_KEY_LAYOUT
    # The window (game/display/): a mode the game knows and a plausible
    # size, or nothing -- the desktop can change between sessions, so the
    # size is clamped when applied, not here.
    disp = d.settings.get("display")
    clean: dict = {}
    if isinstance(disp, dict):
        if disp.get("mode") in _DISPLAY_MODES:
            clean["mode"] = disp["mode"]
        win = disp.get("window")
        if (isinstance(win, (list, tuple)) and len(win) == 2
                and all(_is_int(v) and int(v) > 0 for v in win)):
            clean["window"] = [int(win[0]), int(win[1])]
        if disp.get("render") in _RENDER_ASPECTS:
            clean["render"] = disp["render"]
    if clean:
        d.settings["display"] = clean
    else:
        d.settings.pop("display", None)
    return d


def _is_int(v) -> bool:
    try:
        int(v); return True
    except (TypeError, ValueError):
        return False


def _is_num(v) -> bool:
    try:
        float(v); return True
    except (TypeError, ValueError):
        return False


def load(path: Path | str = DEFAULT_PATH) -> SaveData:
    path = Path(path)
    if not path.exists():
        log.info("no save at %s -- starting fresh", path)
        return SaveData()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        backup = path.with_suffix(path.suffix + ".corrupt")
        log.warning("save file unreadable (%s); backing up to %s", exc, backup)
        try:
            path.replace(backup)
        except OSError:
            pass
        return SaveData()
    return _coerce(raw)


def save(data: SaveData, path: Path | str = DEFAULT_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(asdict(data), indent=2, sort_keys=True),
                   encoding="utf-8")
    os.replace(tmp, path)  # atomic on the same filesystem
