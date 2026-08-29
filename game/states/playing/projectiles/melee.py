"""`melee` -- a short-lived contact hitbox with no visual of its own (the Spirit
Wolf's bite). The animation that sells the hit lives on the attacker's sprite;
the projectile is only the collision shape, so it draws nothing.
"""
from __future__ import annotations

from game.states.playing.projectiles import style


@style("melee")
def melee(surface, sx, sy, p, ctx) -> None:
    return
