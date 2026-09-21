"""Which class implements which element.

Its own module so the registry can default to the real four without
importing them directly, which would close a cycle: an element imports the
resolver (Thunder needs `Outcome`), and the resolver must stay importable
without the registry.
"""
from __future__ import annotations

from combat.elements.fire import Fire
from combat.elements.ice import Ice
from combat.elements.ids import ElementId
from combat.elements.thunder import Thunder
from combat.elements.wind import Wind

ELEMENT_CLASSES = {
    ElementId.FIRE: Fire,
    ElementId.ICE: Ice,
    ElementId.THUNDER: Thunder,
    ElementId.WIND: Wind,
}
