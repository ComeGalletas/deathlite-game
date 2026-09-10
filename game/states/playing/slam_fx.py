"""The Hammer's swing on screen (change request 1): the pending circle,
faded and darkening as the swing completes, and the impact sheet where the
blow lands.

Two small draws the renderer calls per terrace band: `draw_indicators`
between a band's ground and its sprites (a flat effect, like the hazard
discs) and `draw_impacts` with the explosions. The alpha ramp is one pure
function so a test can pin it.
"""
from __future__ import annotations

import pygame

from game import config
from systems.animation import Animator


def indicator_alpha(progress: float) -> int:
    """Alpha of the pending circle at `progress` (0 = swing just started,
    1 = about to land): a straight ramp from the faint to the dark value in
    `config.SLAM_INDICATOR_ALPHA`."""
    faint, dark = config.SLAM_INDICATOR_ALPHA
    p = min(1.0, max(0.0, float(progress)))
    return int(round(faint + (dark - faint) * p))


def pending_swings(ps):
    """`(weapon, centre, radius, progress)` for every owned weapon mid-swing."""
    out = []
    origin = ps.player.pos
    area_mult = float(ps.player.stats.get("area_multiplier", 1.0))
    for w in ps.player.weapons:
        if w.special != "slam" or w._swing_dir is None or w._swing_total <= 0.0:
            continue
        out.append((w, w.slam_centre(origin), w._area(area_mult), w.swing_progress))
    return out


def draw_indicators(surface, ps, level=None) -> None:
    cam = ps.camera
    z = cam.zoom
    for w, centre, radius, progress in pending_swings(ps):
        if ps.renderer._off_band(level, centre):
            continue
        sx, sy = cam.world_to_screen(centre)
        rr = max(2, round(radius * z))
        colour = tuple(ps.content.weapon_visual(w.visual_id).color)
        a = indicator_alpha(progress)
        disc = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
        pygame.draw.circle(disc, (*colour, a), (rr, rr), rr)
        pygame.draw.circle(disc, (*colour, min(255, a + 60)), (rr, rr), rr, 2)
        surface.blit(disc, (int(sx) - rr, int(sy) - rr))


def spawn_impact(ps, *, pos, radius, rig, weapon_id="") -> None:
    """Queue the impact sheet at `pos`, scaled to the circle's diameter. A
    weapon with no rig (or a rig with no frames) shows nothing."""
    if not rig or ps.game.assets.frame_count(rig, "loop") <= 0:
        return
    ps._impacts.append({"anim": Animator(ps.game.assets, rig, start="loop"),
                        "pos": pygame.Vector2(pos), "radius": float(radius)})


def update_impacts(ps, dt: float) -> None:
    for im in ps._impacts:
        im["anim"].update(dt)
    ps._impacts = [im for im in ps._impacts if not im["anim"].finished]


def impact_size(assets, rig: str, radius: float, zoom: float) -> tuple[int, int]:
    """The impact frame's on-screen size: the circle's diameter times the
    rig's `over_circle` (1.25 for the Hammer: the splash overhangs the blow
    by a quarter) wide, the height following the rig's `content` crop so
    the art is not squashed. The crop is the splash's bounding box over all
    its frames, so the anchor lands the splash on the blow."""
    meta = assets.meta.get(rig, {})
    d = max(2, round(radius * 2 * zoom * float(meta.get("over_circle", 1.0))))
    content = meta.get("content")
    if content and content[2] > 0:
        return d, max(2, round(d * content[3] / content[2]))
    return d, d


def impact_topleft(assets, rig: str, size: tuple[int, int], sx: float, sy: float) -> tuple[int, int]:
    """Where the frame's top-left goes so the rig's `anchor` (in crop pixels)
    sits on the blow: the anchor scales with the frame, like the character
    rigs. The Hammer's anchor is 8 px below the crop's centre, which lifts
    the splash about 11 screen px above the circle at the blow's scale
    (owner, change request 1: "raise it some 5 pixels", then "5 more")."""
    content = assets.meta.get(rig, {}).get("content")
    cw = content[2] if content else size[0]
    k = size[0] / max(1, cw)
    ax, ay = assets.anchor(rig)
    return int(round(sx - ax * k)), int(round(sy - ay * k))


def draw_impacts(surface, ps, level=None) -> None:
    cam = ps.camera
    z = cam.zoom
    assets = ps.game.assets
    for im in ps._impacts:
        if ps.renderer._off_band(level, im["pos"]):
            continue
        sx, sy = cam.world_to_screen(im["pos"])
        rig = im["anim"].rig
        size = impact_size(assets, rig, im["radius"], z)
        frame = im["anim"].frame(size=size)
        if frame is not None:
            surface.blit(frame, impact_topleft(assets, rig, size, sx, sy))
