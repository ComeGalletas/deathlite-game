"""The one thing the interact key applies to (journal: key_icons_journal.md,
pass 2).

Special locations and chests are two lists with two managers, and until
now each answered "is the hero on one of mine?" on its own: the first
interactable in list order won, and a location beat a chest by fiat. With
the keycap drawn *over* the element it fires, the rule has to be one rule
for both -- **the closest usable element within reach** -- so the key the
player sees is always the key that fires. Both the marker
(`visual/key_marker.py`) and the E handler ask here.

At an equal distance a location wins, as it always did; in a generated
world that never happens (a chest is never seated inside a special
island's clear disc), so it only pins the old order for hand-built tests.
"""
from __future__ import annotations

from entities.chest import Chest
from entities.interactable import Interactable


def usable(obj) -> bool:
    """Can the interact key still do something with `obj`?"""
    if isinstance(obj, Chest):
        return not obj.opened
    return not obj.used


def nearest(ps):
    """The closest unused interactable or unopened chest within reach of
    the hero, or `None`. Locations are ranked first so a tie goes to them."""
    pos = ps.player.pos
    best, best_d = None, 0.0
    for obj in (*ps.interactables, *ps.chests):
        if not usable(obj) or not obj.in_range(pos):
            continue
        d = (obj.pos - pos).length_squared()
        if best is None or d < best_d:
            best, best_d = obj, d
    return best


def kind_of(obj) -> str:
    """`"chest"` for a chest, else the interactable's kind."""
    return "chest" if isinstance(obj, Chest) else obj.kind


def activate(ps, obj) -> None:
    """Use `obj`: open a chest, or run the location's `use_<kind>` handler."""
    if isinstance(obj, Chest):
        ps.chest_manager.open(obj)
    elif isinstance(obj, Interactable):
        ps.locations.use(obj)
