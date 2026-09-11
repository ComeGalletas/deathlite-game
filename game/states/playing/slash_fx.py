"""A melee swing's slash sequence on screen (owner, 2026-09-10): one Sword
attack plays its two strips back to back -- the downward slash, then the
upward one -- so the visual outlives the hit's 0.14 s window and has to be
its own timed entry, like the Hammer's impact.

A weapon opts in through its visual: `fx.slash` lists the rigs and
`fx.slash_mode = "sequence"`. `PlayingState._spawn_projectile` calls
`spawn_from_cone` for every cone spawn; a sequence weapon gets an entry in
`ps._slashes` (rigs, where the swing was, its heading, the cone's radius)
and the cone style draws no slash of its own for it. Every other cone keeps
the per-frame slash the cone style draws (`projectiles/cone.py`).

Each rig plays once at its own fps, one after the other; the entry is
culled when the last frame of the last rig has shown.
"""
from __future__ import annotations

import math

import pygame

from game.states.playing.projectiles.cone import _SLASH_ANIM, _SLASH_FWD, slash_size

SEQUENCE = "sequence"


def is_sequence(fx) -> bool:
    return bool(fx) and fx.get("slash_mode") == SEQUENCE and isinstance(fx.get("slash"), (list, tuple)) \
        and len(fx.get("slash")) > 0


def rig_durations(assets, rigs) -> list[float]:
    out = []
    for rig in rigs:
        n = assets.frame_count(rig, _SLASH_ANIM)
        fps = assets.fps(rig, _SLASH_ANIM) or 1.0
        out.append(n / fps if n else 0.0)
    return out


def spawn_from_cone(ps, proj) -> None:
    """Queue the slash sequence for a freshly spawned cone whose weapon
    visual asks for one. Silent for every other projectile."""
    fx = getattr(proj, "fx", None)
    if proj.cone_half_angle <= 0.0 or not is_sequence(fx):
        return
    rigs = [str(r) for r in fx["slash"]]
    durs = rig_durations(ps.game.assets, rigs)
    if sum(durs) <= 0.0:
        return
    ps._slashes.append({
        "rigs": rigs, "durs": durs, "t": 0.0,
        "pos": pygame.Vector2(proj.pos), "dir": pygame.Vector2(proj.cone_dir),
        "radius": float(proj.radius), "fx": fx, "level": proj.fire_level,
    })


def current(entry):
    """`(rig, index_time)` for the entry's clock: which rig is playing and
    how far into it; None once the sequence is over."""
    t = entry["t"]
    for rig, dur in zip(entry["rigs"], entry["durs"]):
        if t < dur:
            return rig, t
        t -= dur
    return None


def update(ps, dt: float) -> None:
    for e in ps._slashes:
        e["t"] += dt
    ps._slashes = [e for e in ps._slashes if current(e) is not None]


def draw(surface, ps, level=None) -> None:
    cam = ps.camera
    z = cam.zoom
    assets = ps.game.assets
    for e in ps._slashes:
        if ps.renderer._off_band(level, e["pos"]):
            continue
        cur = current(e)
        if cur is None:
            continue
        rig, t = cur
        n = max(1, assets.frame_count(rig, _SLASH_ANIM))
        idx = min(n - 1, int(t * assets.fps(rig, _SLASH_ANIM)))
        probe = _Probe(e["fx"], e["radius"])
        bw, bh = slash_size(probe, assets, rig)
        if not bw:
            continue
        heading = math.degrees(math.atan2(e["dir"].y, e["dir"].x))
        spr = assets.frame_rotated(rig, _SLASH_ANIM, idx, heading,
                                   size=(max(1, round(bw * z)), max(1, round(bh * z))))
        if spr is None:
            continue
        sx, sy = cam.world_to_screen(e["pos"])
        fwd = max(2.0, e["radius"]) * _SLASH_FWD * z
        cx = sx + math.cos(math.radians(heading)) * fwd
        cy = sy + math.sin(math.radians(heading)) * fwd
        surface.blit(spr, spr.get_rect(center=(int(cx), int(cy))))


class _Probe:
    """The two fields `slash_size` reads, for a queued entry."""
    __slots__ = ("fx", "radius")

    def __init__(self, fx, radius):
        self.fx = fx
        self.radius = radius
