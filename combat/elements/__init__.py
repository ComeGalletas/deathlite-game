"""The elemental infusion system (journal: `elemental_system_journal.md`).

Elements are code: `ids.py` names them, `base.py` is the interface every
element implements, `registry.py` holds the one instance of each with its
effective (modified) config and the reaction lookup table. JSON only tunes
numbers: `config.py` is the schema that `data/weapons/elements.json` and
`data/weapons/reactions.json` must match, baked at load into immutable
records so nothing parses or merges at hit time. `modifiers.py` layers
run-time buffs on top of the baked values and recomputes only when one
changes.

Milestone 1 (M1) of the plan; the element behaviours, the aura state and the
hit resolution follow in M2 and M3.
"""
from combat.elements.ids import ElementId, ReactionId          # noqa: F401
from combat.elements.registry import ElementRegistry, get_registry  # noqa: F401
from combat.elements.schema import ElementDataError            # noqa: F401

__all__ = ["ElementId", "ReactionId", "ElementRegistry", "get_registry",
           "ElementDataError"]
