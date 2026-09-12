"""`totem_bolt` -- the Grave Totem's bolt: a pulsing blue orb with a blue
flame trailing behind it (assets journal, "Grave Totem bolt -- rework",
2026-09-12; owner: the ball is the bolt, the flame is its tail).

Two rigs, both looping off the shared run clock like `orbit` / `thunder`, so
the bolt carries no animation state of its own:

* the **orb** (`fx.orb_rig`, `totem_bolt` / `orb`) centred on the bolt,
  `fx.orb_px` world px across;
* the **tail** (`fx.fire_rig`, `totem_bolt_fire`) rotated so its tip points
  away from the direction of travel and placed so its base sits on the
  bolt: the flame is authored pointing up (`heading_deg` 270 in the rig),
  so the angle passed is `tail heading - 270`. `fx.tail_px` long.

The burst where the bolt lands is not drawn here: `fx.impact` names the
rig / anim the combat resolver hands to `slam_fx.spawn_impact` when a hit
consumes the bolt. A missing rig -> the plain disc `bolt` drew before.
"""
from __future__ import annotations

import math

import pygame

from game.states.playing.projectiles import style

_ORB_RIG, _ORB_ANIM = "totem_bolt", "orb"
_FIRE_RIG, _FIRE_ANIM = "totem_bolt_fire", "loop"


def _frame_index(assets, rig: str, anim: str, now: float) -> int:
    n = max(1, assets.frame_count(rig, anim))
    return int(now * assets.fps(rig, anim)) % n


def tail_angle(vel: pygame.Vector2, authored_deg: float) -> float:
    """The rotation to pass for the flame so its tip trails the bolt:
    screen-CW degrees, the tail's heading minus the art's own."""
    heading = math.degrees(math.atan2(vel.y, vel.x)) if vel.length_squared() > 1e-6 else 0.0
    return heading + 180.0 - authored_deg


@style("totem_bolt")
def totem_bolt(surface, sx, sy, p, ctx) -> None:
    z = ctx.zoom
    assets = ctx.assets
    fx = p.fx or {}
    orb_rig = fx.get("orb_rig", _ORB_RIG)
    fire_rig = fx.get("fire_rig", _FIRE_RIG)
    orb_px = float(fx.get("orb_px", 24))
    tail_px = float(fx.get("tail_px", 28))

    drew = False
    # Tail first, so the orb sits over its base.
    meta = assets.meta.get(fire_rig)
    if meta:
        content = meta.get("content") or [0, 0, 1, 1]
        aspect = content[2] / max(1, content[3])          # width / height
        size = (max(1, round(tail_px * aspect * z)), max(1, round(tail_px * z)))
        authored = float(meta.get("heading_deg", 270.0))
        idx = _frame_index(assets, fire_rig, _FIRE_ANIM, ctx.now)
        spr = assets.frame_rotated(fire_rig, _FIRE_ANIM, idx, tail_angle(p.vel, authored), size=size)
        if spr is not None:
            # The flame's base sits on the bolt: its centre goes half a tail
            # length back along the travel line.
            back = -p.vel.normalize() if p.vel.length_squared() > 1e-6 else pygame.Vector2(-1, 0)
            cx = sx + back.x * tail_px * 0.5 * z
            cy = sy + back.y * tail_px * 0.5 * z
            surface.blit(spr, spr.get_rect(center=(int(cx), int(cy))))
            drew = True

    idx = _frame_index(assets, orb_rig, _ORB_ANIM, ctx.now)
    size = (max(1, round(orb_px * z)), max(1, round(orb_px * z)))
    orb = assets.frame(orb_rig, _ORB_ANIM, idx, size=size)
    if orb is not None:
        surface.blit(orb, orb.get_rect(center=(int(sx), int(sy))))
        drew = True

    if not drew:  # rigs / sheets missing -> the plain disc it replaces
        pygame.draw.circle(surface, p.color, (int(sx), int(sy)), max(2, round(p.radius * z)))
