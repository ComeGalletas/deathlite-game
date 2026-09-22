"""What the element and reaction data files may say (design §2.3, §4, §5).

This module is the taxonomy: which elements exist, which reaction each pair
produces, and the exact set of numbers each one is tuned by. The numbers
themselves live in `data/weapons/elements.json` and
`data/weapons/reactions.json`; a missing, unknown or out-of-range value
stops the boot (the files are content, like `weapons.json`).

Key names follow the project's snake_case (`chain.max_targets`), not the
design's camelCase; the mapping is one-to-one and recorded in the journal.
"""
from __future__ import annotations

from typing import Any

from combat.elements.ids import ELEMENTS, REACTIONS, ElementId, ReactionId
from combat.elements.schema import (
    ElementDataError, Section, b, deep_merge, dmg, f, i)

# --- the global block (design §3, §9) ------------------------------------------

GLOBAL = Section("GlobalConfig", {
    # Seconds the aura slot stays locked on an enemy after any reaction.
    "reaction_aura_cooldown": f(0.0),
    # Reactions resolved per frame; the rest are deferred, never dropped.
    "max_reactions_per_frame": i(1),
    # Simultaneous Wind areas (base Wind and the Wind reactions together).
    "max_active_wind_areas": i(1),
})

# --- per-element schemas (design §4) ----------------------------------------------

AURA = Section("AuraConfig", {"duration": f(0.0, lo_open=True)})

FIRE = Section("FireConfig", {
    "aura": AURA,
    "hit": Section("FireHit", {"damage": dmg()}),
    "burn": Section("BurnConfig", {
        "tick": dmg(),                              # per tick
        "tick_interval": f(0.0, lo_open=True),
    }),
})

ICE = Section("IceConfig", {
    "aura": AURA,
    "slow": Section("SlowConfig", {
        "percent_per_stack": f(0.0, 1.0),
        "max_percent": f(0.0, 1.0),
    }),
    "freeze": Section("FreezeConfig", {
        "stacks_required": i(1),
        "duration": f(0.0, lo_open=True),
        "immunity_duration": f(0.0),
        # Frozen contact damage (design §4.2 addendum, R25).
        "contact": Section("FrozenContact", {"enabled": b(), "damage": dmg()}),
    }),
})

THUNDER = Section("ThunderConfig", {
    "aura": AURA,
    "chain": Section("ChainConfig", {
        "damage": dmg(),
        "targets_per_jump": i(1),
        "jumps": i(0),
        "max_range": f(0.0, lo_open=True),
        "max_targets": i(1),
        "falloff": f(0.0, 1.0),                     # damage multiplier per jump level
    }),
})

WIND = Section("WindConfig", {
    "aura": AURA,
    "hit": Section("WindHit", {"damage": dmg()}),
    "area": Section("WindAreaConfig", {
        "duration": f(0.0, lo_open=True),
        "radius": f(0.0, lo_open=True),
        "damage": dmg(),
        "knockback": f(0.0),
        "max_range": f(0.0, lo_open=True),
        "max_targets": i(1),
    }),
})

ELEMENT_SCHEMAS: dict[ElementId, Section] = {
    ElementId.FIRE: FIRE, ElementId.ICE: ICE,
    ElementId.THUNDER: THUNDER, ElementId.WIND: WIND,
}

# --- reactions (design §5) --------------------------------------------------------

# Every reaction may lock the aura slot beyond the global cooldown.
_LOCK = {"lock_aura_slot": b(), "lock_duration": f(0.0)}
# Every effect that reaches other enemies carries its own caps.
_AREA_CAPS = {"max_range": f(0.0, lo_open=True), "max_targets": i(1)}
# The Wind-area payload the three Wind reactions share (§4.4, §5.5).
_WIND_AREA = {"duration": f(0.0, lo_open=True), "radius": f(0.0, lo_open=True),
              "damage": dmg(), "knockback": f(0.0), **_AREA_CAPS}

REACTION_SCHEMAS: dict[ReactionId, Section] = {
    ReactionId.FROSTBURN: Section("FrostburnConfig", {
        "tick": dmg(), "tick_interval": f(0.0, lo_open=True),
        "duration": f(0.0, lo_open=True), "slow_percent": f(0.0, 1.0), **_LOCK}),
    ReactionId.OVERLOAD: Section("OverloadConfig", {
        "damage": dmg(), "shockwave_damage": dmg(),
        "shockwave_radius": f(0.0, lo_open=True), "knockback": f(0.0),
        "max_knockback_speed": f(0.0, lo_open=True), **_AREA_CAPS, **_LOCK}),
    ReactionId.SUPERCONDUCT: Section("SuperconductConfig", {
        "damage": dmg(), "bonus_jumps": i(1), "targets_per_jump": i(1),
        "slow_percent": f(0.0, 1.0), "slow_duration": f(0.0, lo_open=True),
        **_AREA_CAPS, **_LOCK}),
    ReactionId.FIREWIND: Section("FireWindConfig", {
        **_WIND_AREA, "burn_tick": dmg(), "burn_tick_interval": f(0.0, lo_open=True),
        "burn_duration": f(0.0, lo_open=True), **_LOCK}),
    ReactionId.ICEWIND: Section("IceWindConfig", {
        **_WIND_AREA, "stacks_per_contact": i(1),
        "slow_duration": f(0.0, lo_open=True), **_LOCK}),
    ReactionId.THUNDERWIND: Section("ThunderWindConfig", {
        **_WIND_AREA, "strike_targets": i(1), "strike_damage": dmg(),
        "strike_range": f(0.0, lo_open=True), **_LOCK}),
}

# Which unordered pair produces which reaction: taxonomy, never data.
REACTION_PAIRS: dict[ReactionId, tuple[ElementId, ElementId]] = {
    ReactionId.FROSTBURN: (ElementId.FIRE, ElementId.ICE),
    ReactionId.OVERLOAD: (ElementId.FIRE, ElementId.THUNDER),
    ReactionId.SUPERCONDUCT: (ElementId.ICE, ElementId.THUNDER),
    ReactionId.FIREWIND: (ElementId.FIRE, ElementId.WIND),
    ReactionId.ICEWIND: (ElementId.ICE, ElementId.WIND),
    ReactionId.THUNDERWIND: (ElementId.THUNDER, ElementId.WIND),
}

TRIGGERED_BY = "triggered_by"


# --- validation entry points ---------------------------------------------------------

def check_elements(data: Any) -> dict:
    """Validate `elements.json`; return a coerced copy with the same shape:
    `{"global": {...}, "elements": {"fire": {...}, ...}}`."""
    if not isinstance(data, dict):
        raise ElementDataError("elements.json: expected an object at top level")
    out = {"global": GLOBAL.validate("elements.json: global", data.get("global"))}
    elements = data.get("elements")
    if not isinstance(elements, dict):
        raise ElementDataError("elements.json: `elements` must be an object")
    got = {k for k in elements if not k.startswith("_")}
    want = {e.key for e in ELEMENTS}
    if got != want:
        raise ElementDataError(
            f"elements.json: `elements` covers {sorted(got)}, expected {sorted(want)}")
    baked: dict[str, dict] = {}
    for eid in ELEMENTS:
        baked[eid.key] = ELEMENT_SCHEMAS[eid].validate(
            f"elements.json: {eid.key}", elements[eid.key])
    out["elements"] = baked
    return out


def check_reactions(data: Any) -> dict:
    """Validate `reactions.json`; return a coerced copy
    `{"reactions": {"overload": {<base>, "triggered_by": {"fire": {<partial>}}}}}`.
    A `triggered_by` override may name only the pair's own elements and only
    keys the reaction's base schema has (design §5.2)."""
    if not isinstance(data, dict):
        raise ElementDataError("reactions.json: expected an object at top level")
    table = data.get("reactions")
    if not isinstance(table, dict):
        raise ElementDataError("reactions.json: `reactions` must be an object")
    got = {k for k in table if not k.startswith("_")}
    want = {r.key for r in REACTIONS}
    if got != want:
        raise ElementDataError(
            f"reactions.json: `reactions` covers {sorted(got)}, expected {sorted(want)}")
    out: dict[str, dict] = {}
    for rid in REACTIONS:
        path = f"reactions.json: {rid.key}"
        raw = table[rid.key]
        if not isinstance(raw, dict):
            raise ElementDataError(f"{path}: expected an object, got {raw!r}")
        base = {k: v for k, v in raw.items() if k != TRIGGERED_BY}
        entry = REACTION_SCHEMAS[rid].validate(path, base)
        overrides: dict[str, dict] = {}
        pair_keys = {e.key for e in REACTION_PAIRS[rid]}
        for trigger, override in (raw.get(TRIGGERED_BY) or {}).items():
            if trigger.startswith("_"):
                continue
            if trigger not in pair_keys:
                raise ElementDataError(
                    f"{path}.{TRIGGERED_BY}: {trigger!r} is not one of {sorted(pair_keys)}")
            overrides[trigger] = REACTION_SCHEMAS[rid].validate(
                f"{path}.{TRIGGERED_BY}.{trigger}", override, partial=True)
        entry[TRIGGERED_BY] = overrides
        out[rid.key] = entry
    return {"reactions": out}


def variant_data(entry: dict, trigger: ElementId) -> dict:
    """The validated base of a reaction with the override for `trigger`
    laid over it -- the dict one directional variant is baked from."""
    base = {k: v for k, v in entry.items() if k != TRIGGERED_BY}
    override = entry.get(TRIGGERED_BY, {}).get(trigger.key)
    return deep_merge(base, override) if override else base
