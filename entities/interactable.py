"""Special-location interactables (spec 5.5).

One per special room, placed at the room centre. The player walks onto it and
presses E; `PlayingState._activate_interactable` runs the effect. Each is a
one-shot except the elite arena, which is a proximity trigger. Kept deliberately
simple -- "Do not build a giant quest system" (spec 5.5).
"""
from __future__ import annotations

import pygame

# kind -> (radius, colour, prompt)
KINDS = {
    "shrine":      (26, (120, 160, 240), "E  Shrine - gain a blessing"),
    "treasure":    (24, (230, 200, 90),  "E  Chest - claim an item"),
    "fountain":    (26, (110, 210, 230), "E  Fountain - heal to full"),
    "altar":       (26, (210, 110, 210), "E  Altar - trade 25% max HP for a blessing"),
    "merchant":    (26, (220, 190, 120), "E  Merchant - buy an item ({cost} gold)"),
    "elite_arena": (30, (230, 110, 120), "Elite arena - clear it for a rare item"),
}


class Interactable:
    __slots__ = ("kind", "pos", "radius", "colour", "prompt", "used",
                 "cost", "state", "arena_ids")

    def __init__(self, kind: str, x: float, y: float, cost: int = 0) -> None:
        radius, colour, prompt = KINDS.get(kind, KINDS["shrine"])
        self.kind = kind
        self.pos = pygame.Vector2(x, y)
        self.radius = radius
        self.colour = colour
        self.cost = cost
        self.prompt = prompt.format(cost=cost)
        self.used = False
        # elite_arena: "idle" -> "active" -> "done"
        self.state = "idle"
        self.arena_ids: set[int] = set()

    def in_range(self, point: pygame.Vector2, pad: float = 40.0) -> bool:
        return (point - self.pos).length_squared() <= (self.radius + pad) ** 2
