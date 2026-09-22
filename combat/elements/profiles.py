"""Per-enemy-type elemental profiles (design §3.5).

Every enemy can be affected by elements -- there is no full immunity. A
boss or a special enemy differs only by **overriding a value** or
**disabling an effect**, declared in its `enemies.json` / `bosses.json`
block under an optional `elementProfile`:

    "elementProfile": {
      "ice":      {"freeze.stacks_required": 12, "slow.max_percent": 0.2},
      "wind":     {"knockback_multiplier": 0.2},
      "overload": {"knockback_multiplier": 0.0},
      "freeze":   {"enabled": false},
      "aura":     {"enabled": false},
      "damage_multiplier": {"fire": 0.8, "thunder": 1.0}
    }

An element or reaction key takes leaf-path overrides from that config's own
schema, plus `damage_multiplier` and `knockback_multiplier`. An effect key
takes `{"enabled": bool}`. `aura.enabled = false` makes the type immune to
reactions, implemented as a permanently locked aura slot so it reuses the
locked-slot path and needs no branch of its own.

**Fail soft** (the project's rule for enemy data): a malformed entry is
skipped with a note and the rest of the profile still applies; nothing here
ever refuses to boot. Resolution happens once, at run start, because the
data does not change mid-run.

Types with no overrides all share `DEFAULT`, so the common case costs one
reference and no lookups.
"""
from __future__ import annotations

import logging

from combat.elements import config as schema
from combat.elements.ids import (
    ELEMENTS, REACTIONS, element_from_key, reaction_from_key)

log = logging.getLogger(__name__)

KEY = "elementProfile"

# Effects a profile may switch off. `aura` is the reaction immunity; the
# rest are the secondary effects the design lists (§3.5).
EFFECT_TOGGLES = ("aura", "freeze", "slow", "burn", "knockback", "frozen_contact")

_MULTIPLIERS = ("damage_multiplier", "knockback_multiplier")
_DAMAGE_LEAVES = (".frac", ".flat")


def _config_keys() -> dict[str, tuple[str, ...]]:
    """`{"fire": (leaf paths...), "overload": (...)}` -- what an element or
    reaction block may override."""
    out = {}
    for eid in ELEMENTS:
        out[eid.key] = schema.ELEMENT_SCHEMAS[eid].paths()
    for rid in REACTIONS:
        out[rid.key] = schema.REACTION_SCHEMAS[rid].paths()
    return out


CONFIG_KEYS = _config_keys()


class ElementProfile:
    """One resolved profile, shared by every enemy of its type."""
    __slots__ = ("name", "_disabled", "_damage_mult", "_knock_mult", "_values")

    def __init__(self, name: str = "default", *, disabled=(), damage_mult=None,
                 knock_mult=None, values=None) -> None:
        self.name = name
        self._disabled = frozenset(disabled)
        self._damage_mult: dict[str, float] = dict(damage_mult or {})
        self._knock_mult: dict[str, float] = dict(knock_mult or {})
        # {config key: {leaf path: value}}
        self._values: dict[str, dict[str, float]] = {
            k: dict(v) for k, v in (values or {}).items()}

    # --- queries -------------------------------------------------------
    @property
    def is_default(self) -> bool:
        return not (self._disabled or self._damage_mult or self._knock_mult
                    or self._values)

    @property
    def aura_enabled(self) -> bool:
        return "aura" not in self._disabled

    def enabled(self, effect: str) -> bool:
        """Is this secondary effect allowed on this enemy type?"""
        return effect not in self._disabled

    @property
    def disabled(self) -> frozenset:
        return self._disabled

    def touches(self, key: str) -> bool:
        """Does this profile change `key`'s config at all? When it does not,
        the registry can hand back the unmodified shared config."""
        return (key in self._values or key in self._damage_mult
                or key in self._knock_mult)

    def adjust_for(self, key: str):
        """An `(path, value) -> value` callback for one element or reaction
        config, or `None` when this profile leaves it alone.

        A named leaf override **replaces** the value outright; a damage or
        knockback multiplier scales whatever the modifier layer produced.
        """
        if not self.touches(key):
            return None
        values = self._values.get(key, {})
        dmg = self._damage_mult.get(key)
        knock = self._knock_mult.get(key)

        def adjust(path: str, value):
            if path in values:
                return values[path]
            if dmg is not None and path.endswith(_DAMAGE_LEAVES):
                return value * dmg
            if knock is not None and (path == "knockback"
                                      or path.endswith(".knockback")):
                return value * knock
            return value

        return adjust

    def __repr__(self) -> str:
        return f"<ElementProfile {self.name}{'' if not self.is_default else ' (default)'}>"


DEFAULT = ElementProfile()


# --- resolution ----------------------------------------------------------------

def resolve(definitions: dict, *, kind: str = "enemy") -> tuple[dict, list[str]]:
    """Resolve every `elementProfile` in a block of enemy or boss
    definitions. Returns `({id: ElementProfile}, notes)`; ids with no
    overrides (or with unusable ones) map to the shared `DEFAULT`."""
    profiles: dict[str, ElementProfile] = {}
    notes: list[str] = []
    for entity_id, definition in definitions.items():
        if entity_id.startswith("_") or not isinstance(definition, dict):
            continue
        raw = definition.get(KEY)
        if raw is None:
            profiles[entity_id] = DEFAULT
            continue
        profile, entry_notes = _parse(f"{kind} {entity_id}", raw)
        notes.extend(entry_notes)
        profiles[entity_id] = profile
    return profiles, notes


def _parse(where: str, raw) -> tuple[ElementProfile, list[str]]:
    notes: list[str] = []
    if not isinstance(raw, dict):
        return DEFAULT, [f"{where}: {KEY} is not an object; ignored"]

    disabled: set[str] = set()
    damage_mult: dict[str, float] = {}
    knock_mult: dict[str, float] = {}
    values: dict[str, dict[str, float]] = {}

    for key, block in raw.items():
        if key.startswith("_"):
            continue
        if key == "damage_multiplier":
            _read_multipliers(where, key, block, damage_mult, notes)
        elif key in EFFECT_TOGGLES:
            _read_toggle(where, key, block, disabled, notes)
        elif key in CONFIG_KEYS:
            _read_config(where, key, block, damage_mult, knock_mult, values, notes)
        else:
            notes.append(f"{where}: {KEY}.{key} is not an element, reaction, "
                         f"effect toggle or damage_multiplier; ignored")

    profile = ElementProfile(where, disabled=disabled, damage_mult=damage_mult,
                             knock_mult=knock_mult, values=values)
    return (DEFAULT if profile.is_default else profile), notes


def _read_toggle(where: str, key: str, block, disabled: set, notes: list) -> None:
    if not isinstance(block, dict) or "enabled" not in block:
        notes.append(f"{where}: {KEY}.{key} needs {{\"enabled\": true|false}}; ignored")
        return
    if not isinstance(block["enabled"], bool):
        notes.append(f"{where}: {KEY}.{key}.enabled is not true/false; ignored")
        return
    unknown = [k for k in block if k != "enabled" and not k.startswith("_")]
    if unknown:
        notes.append(f"{where}: {KEY}.{key} ignores {sorted(unknown)}")
    if not block["enabled"]:
        disabled.add(key)


def _read_multipliers(where: str, key: str, block, into: dict, notes: list) -> None:
    """The top-level `damage_multiplier` block: element or reaction -> factor."""
    if not isinstance(block, dict):
        notes.append(f"{where}: {KEY}.{key} is not an object; ignored")
        return
    for name, value in block.items():
        if name.startswith("_"):
            continue
        if name not in CONFIG_KEYS:
            notes.append(f"{where}: {KEY}.{key}.{name} is not an element or "
                         f"reaction; ignored")
            continue
        factor = _as_factor(f"{where}: {KEY}.{key}.{name}", value, notes)
        if factor is not None:
            into[name] = factor


def _read_config(where: str, key: str, block, damage_mult: dict, knock_mult: dict,
                 values: dict, notes: list) -> None:
    """One element or reaction block: leaf overrides plus its own
    `damage_multiplier` / `knockback_multiplier`."""
    if not isinstance(block, dict):
        notes.append(f"{where}: {KEY}.{key} is not an object; ignored")
        return
    allowed = CONFIG_KEYS[key]
    for path, value in block.items():
        if path.startswith("_"):
            continue
        where_path = f"{where}: {KEY}.{key}.{path}"
        if path in _MULTIPLIERS:
            factor = _as_factor(where_path, value, notes)
            if factor is not None:
                (damage_mult if path == "damage_multiplier" else knock_mult)[key] = factor
            continue
        if path not in allowed:
            notes.append(f"{where_path} is not a value of {key}; ignored")
            continue
        number = _as_number(where_path, value, notes)
        if number is not None:
            values.setdefault(key, {})[path] = number


def _as_factor(where: str, value, notes: list) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0.0:
        notes.append(f"{where}: {value!r} is not a multiplier >= 0; ignored")
        return None
    return float(value)


def _as_number(where: str, value, notes: list) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        notes.append(f"{where}: {value!r} is not a number; ignored")
        return None
    return float(value)


def log_notes(notes) -> None:
    for note in notes:
        log.warning("element profile: %s", note)
