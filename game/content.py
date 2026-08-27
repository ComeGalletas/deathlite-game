"""Loads static game data from data/*.json into plain dicts.

Spec section 7: content lives in data files, code provides behavior. This module
is the single load point. Missing files or malformed JSON raise a clear
`ContentError` at startup rather than failing mysteriously deep in gameplay.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class ContentError(RuntimeError):
    pass


def _load(name: str) -> dict[str, Any]:
    path = DATA_DIR / name
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise ContentError(f"missing data file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContentError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContentError(f"{path} must contain a JSON object at top level")
    return data


class Content:
    """Immutable-ish container for all loaded definitions."""

    def __init__(self) -> None:
        self.weapons: dict[str, dict] = _load("weapons.json")
        self.enemies: dict[str, dict] = _load("enemies.json")
        self.bosses: dict[str, dict] = _load("bosses.json")
        self.characters: dict[str, dict] = _load("characters.json")
        self.blessings: dict[str, dict] = _load("blessings.json")
        self.items: dict = _load("items.json")
        self.meta_upgrades: dict[str, dict] = _load("meta_upgrades.json")
        self.sprites: dict[str, dict] = _load("sprites.json")
        self.terrain: dict = _load("terrain.json")
        log.info("content loaded: %d weapons, %d enemies, %d bosses, "
                 "%d characters, %d blessings, %d affixes, %d meta upgrades, "
                 "%d sprite rigs, %d terrain rigs",
                 len(self.weapons), len(self.enemies), len(self.bosses),
                 len(self.characters), len(self.blessings),
                 len(self.items.get("affixes", {})), len(self.meta_upgrades),
                 len(self.sprites), len(self.terrain.get("rigs", {})))

    def weapon(self, weapon_id: str) -> dict:
        try:
            return self.weapons[weapon_id]
        except KeyError as exc:
            raise ContentError(f"unknown weapon id: {weapon_id!r}") from exc

    def enemy(self, enemy_id: str) -> dict:
        try:
            return self.enemies[enemy_id]
        except KeyError as exc:
            raise ContentError(f"unknown enemy id: {enemy_id!r}") from exc

    def boss(self, boss_id: str) -> dict:
        try:
            return self.bosses[boss_id]
        except KeyError as exc:
            raise ContentError(f"unknown boss id: {boss_id!r}") from exc

    def character(self, char_id: str) -> dict:
        try:
            return self.characters[char_id]
        except KeyError as exc:
            raise ContentError(f"unknown character id: {char_id!r}") from exc


_cache: Content | None = None


def get_content() -> Content:
    """Process-wide singleton; loaded on first use."""
    global _cache
    if _cache is None:
        _cache = Content()
    return _cache
