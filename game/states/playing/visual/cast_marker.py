"""The Hexcaller's cast, drawn where it will land for the whole wind-up
(ENT-013).

A caster that declares a `cast_marker` block snapshots its target into
`bb.slot(ATTACK_SLOT)["cast_at"]` when its wind-up starts, and drops its
hazard there when the wind-up ends. Nothing used to show the spot in
between, so the hazard appeared under the player with no warning; now, for
as long as the enemy is `telegraphing`, the spot carries two authored
layers, flat on its terrace under the characters:

* **the footprint** -- the hazard sprite's own first frame (its small pink
  ring) at the hazard's size, fading in from `footprint_alpha[0]` to
  `footprint_alpha[1]` over the wind-up. It is exactly the area that is
  about to burn;
* **the charge** -- the `sprite` rig (the Gigapack's violet charge-up)
  looping over it: something is gathering here, get out.

When the wind-up ends the hazard itself takes over (`WorldRenderer.hazards`).
An enemy with no `cast_marker` block, or a wind-up with no snapshot, draws
nothing.
"""
from __future__ import annotations

from entities.ai.machine import ATTACK_SLOT, time_in_state


def draw(surface, ps, level=None) -> None:
    ren = ps.renderer
    run = getattr(ren, "run", ps)
    for enemy in run.enemies:
        marker = enemy.cfg.get("cast_marker")
        if marker is None or not enemy.alive or not enemy.telegraphing:
            continue
        at = enemy.bb.slot(ATTACK_SLOT).get("cast_at")
        if at is None or ren._off_band(level, at):
            continue
        draw_one(surface, ps, enemy, marker, at)


def progress(enemy) -> float:
    """How far into its wind-up the caster is, 0 to 1."""
    total = float(enemy.cfg["cast_telegraph"])
    if total <= 0.0:
        return 1.0
    return max(0.0, min(1.0, time_in_state(enemy) / total))


def draw_one(surface, ps, enemy, marker, at) -> None:
    run = ps.run
    assets = ps.game.assets
    z = run.camera.zoom
    sx, sy = run.camera.world_to_screen(at)
    t = progress(enemy)

    footprint = _footprint(assets, enemy, z)
    if footprint is not None:
        lo, hi = marker["footprint_alpha"]
        faded = footprint.copy()
        faded.set_alpha(int(round(lo + (hi - lo) * t)))
        surface.blit(faded, faded.get_rect(center=(int(sx), int(sy))))

    rig = marker["sprite"]
    base = assets.scale_for(rig)
    if base is None:
        return
    frames = assets.frames(rig, "loop", size=(max(1, round(base[0] * z)),
                                              max(1, round(base[1] * z))))
    if not frames:
        return
    fps = assets.fps(rig, "loop")
    frame = frames[int(time_in_state(enemy) * fps) % len(frames)]
    surface.blit(frame, frame.get_rect(center=(int(sx), int(sy))))


def _footprint(assets, enemy, z):
    """The hazard sprite's first frame at the size the hazard draws it --
    the same `scale_for` path as `WorldRenderer._hazard_sprite`, so the ring
    is the true footprint."""
    rig = enemy.cfg.get("hazard_sprite")
    if not rig:
        return None
    radius = float(enemy.cfg["hazard_radius"])
    base = assets.scale_for(rig) or (round(radius * 2), round(radius * 2))
    frames = assets.frames(rig, "loop", size=(max(1, round(base[0] * z)),
                                              max(1, round(base[1] * z))))
    return frames[0] if frames else None
