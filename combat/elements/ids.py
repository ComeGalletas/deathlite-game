"""Element and reaction identifiers (design §2.1).

Compact integer enums: everything on the hot path -- the registry tuple, the
reaction table, the aura slot on an enemy -- is indexed by these, never by
name. The names are only for data files, logs and the dev inspector.
"""
from __future__ import annotations

from enum import IntEnum


class ElementId(IntEnum):
    NONE = 0
    FIRE = 1
    ICE = 2
    THUNDER = 3
    WIND = 4

    @property
    def key(self) -> str:
        """The JSON / log name (`"fire"`)."""
        return self.name.lower()


# The four real elements, in id order: the data file must define exactly these.
ELEMENTS: tuple[ElementId, ...] = (ElementId.FIRE, ElementId.ICE,
                                   ElementId.THUNDER, ElementId.WIND)

_BY_KEY = {e.key: e for e in ELEMENTS}


def element_from_key(key: str) -> ElementId:
    """`"fire"` -> `ElementId.FIRE`; raises `KeyError` for anything else."""
    return _BY_KEY[key]


class ReactionId(IntEnum):
    """One per unordered element pair (design §5.1). The pair each one
    belongs to is taxonomy and lives in `config.REACTION_PAIRS`."""
    FROSTBURN = 1      # Fire + Ice
    OVERLOAD = 2       # Fire + Thunder
    SUPERCONDUCT = 3   # Ice + Thunder
    FIREWIND = 4       # Fire + Wind
    ICEWIND = 5        # Ice + Wind
    THUNDERWIND = 6    # Thunder + Wind

    @property
    def key(self) -> str:
        return self.name.lower()


REACTIONS: tuple[ReactionId, ...] = tuple(ReactionId)

_REACTION_BY_KEY = {r.key: r for r in REACTIONS}


def reaction_from_key(key: str) -> ReactionId:
    return _REACTION_BY_KEY[key]
