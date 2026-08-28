from __future__ import annotations

import pygame


def unit_to(src: pygame.Vector2, dst: pygame.Vector2) -> pygame.Vector2:
    d = dst - src
    return d.normalize() if d.length_squared() > 1e-12 else pygame.Vector2()
