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
from dataclasses import dataclass, field, asdict
from pathlib import Path

log = logging.getLogger(__name__)

SAVE_VERSION = 1
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "save.json"

# Characters available from the very first launch.
_STARTER_CHARACTERS = ["aegis", "kestrel", "nihil"]

# Per-run best records are bucketed by difficulty and never compared across
# buckets (a Fast run's time only ranks against other Fast runs). Mirror
# config.DIFFICULTY_ORDER; kept local so this module stays dependency-free.
_RECORD_DIFFICULTIES = ("normal", "fast", "super_fast")
_RECORD_KEYS = ("time", "level", "kills", "damage_dealt")


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
    settings: dict = field(default_factory=lambda: {"muted": False, "volume": 0.7})

    # --- helpers -------------------------------------------------
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
    if isinstance(raw.get("settings"), dict):
        d.settings.update(raw["settings"])
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
