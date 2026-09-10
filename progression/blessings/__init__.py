"""Blessings (six-weapon system P2, design §21).

"Blessing" is anything the player is offered on a level-up or at a shrine /
altar. The catalog (`catalog.py`) is `data/blessings.json`: stat blessings
and weapon blessings, each with cumulative per-level values. `offer.py`
builds the valid set for a run -- gated on the weapons the hero owns -- adds
the weapon grants while slots are open, and rolls the weighted offering
(`data/offering.json`). `apply.py` raises a blessing one level on the hero
or a weapon. `effects.py` keeps the flattened `BlessingEffects` aggregate the
hit resolver reads; since the elemental blessings went, only item affixes
feed it.
"""
from progression.blessings.apply import apply_blessing, level_of         # noqa: F401
from progression.blessings.catalog import (                              # noqa: F401
    CATEGORIES, KINDS, RARITIES, BlessingDef, Catalog, OfferingRules,
    get_catalog, get_rules,
)
from progression.blessings.effects import BlessingEffects, rebuild       # noqa: F401
from progression.blessings.offer import (                                # noqa: F401
    forge_offers, forge_offers_for, grant_offers, roll_offering, valid_offers,
)

__all__ = [
    "CATEGORIES", "KINDS", "RARITIES", "BlessingDef", "BlessingEffects",
    "Catalog", "OfferingRules", "apply_blessing", "get_catalog", "get_rules",
    "grant_offers", "level_of", "rebuild", "roll_offering", "valid_offers",
]
