"""Special-location interactables (spec 5.5).

One per special room, placed at the room centre. The player walks onto it and
presses the interact key; `PlayingState._activate_interactable` runs the effect. Each is a
one-shot except the elite arena, which is a proximity trigger. Kept deliberately
simple -- "Do not build a giant quest system" (spec 5.5).
"""
from __future__ import annotations

import pygame

# kind -> (radius, colour). Nothing here is text: the interact keycap that
# floats over the element is drawn by `visual/key_marker.py` from
# `config.KEY_INTERACT` (journal: key_icons_journal.md).
KINDS = {
    "shrine":      (26, (120, 160, 240)),
    "treasure":    (24, (230, 200, 90)),
    # HI-2: the village's sanctuary prop, skinned with the heal effect.
    "fountain":    (26, (110, 210, 230)),
    # HI-2: the forge stands on the village island; the handler is a stub
    # until weapon forging (six_weapon_system_design.md 7) lands.
    "forge":       (44, (230, 150, 80)),
    "altar":       (26, (210, 110, 210)),
    "merchant":    (26, (220, 190, 120)),
    # Buff buildings (journal: buff_buildings_journal.md): the interactable
    # stands on the building obstacle, which carries the art; the radius is
    # the reach round the building the interact key answers from.
    "magnet":      (38, (255, 214, 90)),
    "turbo":       (36, (255, 150, 60)),
    "haste":       (36, (120, 220, 255)),
    "pinball":     (36, (190, 120, 255)),
    "vampire":     (36, (230, 40, 60)),
}


class Interactable:
    __slots__ = ("kind", "pos", "radius", "colour", "used", "cost")

    def __init__(self, kind: str, x: float, y: float, cost: int = 0) -> None:
        radius, colour = KINDS.get(kind, KINDS["shrine"])
        self.kind = kind
        self.pos = pygame.Vector2(x, y)
        self.radius = radius
        self.colour = colour
        self.cost = cost
        self.used = False

    def in_range(self, point: pygame.Vector2, pad: float = 40.0) -> bool:
        return (point - self.pos).length_squared() <= (self.radius + pad) ** 2
