"""The `mark` status drawn on the body that carries it (RND-007).

The Rod leaves `mark` on what it hits; Marked Prey and Crossfire pay out
against it. It is drawn as raspberry lock-on brackets framing the body
(`data/weapons/status_visuals.json` `mark`, art cut by
`tools/asset_pipeline/cut_mark_brackets.py`):

* **only while it matters** -- a weapon the hero holds carries one of the
  visual's `shown_with_effects` (`syn_vs_marked`) above 0 (owner,
  2026-09-24). A Rod build nothing pays out for shows nothing.
* **framing the body** -- centred on the body, the art's `box` scaled
  to `over_body` x the body's larger side (its resting pose, `body_box`), so
  a turtle and a skull are both bracketed, and the brackets breathe with the
  strip.
* **fading out** over the status's last `fade` seconds.

Drawn right after the body's own sprite (`WorldRenderer.one_enemy` /
`boss`), so it depth-sorts with the body: a body standing in front still
covers it. The authored brackets replace the procedural status ring, which
stays for the primitive fallback in the data's `colour`.
"""
from __future__ import annotations

import pygame

from game.content import get_content

STATUS = "mark"


def spec() -> dict:
    return get_content().status_visuals[STATUS]


def shown(run) -> bool:
    """Does the hero hold anything that reads the mark?"""
    keys = spec()["shown_with_effects"]
    return any(w.effect(k) > 0.0 for w in run.player.weapons for k in keys)


def alpha(body) -> int:
    """255 until the last `fade` seconds of the status, then down to 0."""
    fade = float(spec()["fade"])
    left = body.status.remaining(STATUS)
    if fade <= 0.0 or left >= fade:
        return 255
    return max(0, int(255 * left / fade))


_BODY_BOXES: dict = {}


def body_box(assets, rig: str, zoom: float) -> pygame.Rect | None:
    """Where the body is inside the rig's drawn frame, at `zoom`: the visible
    bounds of its first idle frame (its first strip's, for a rig with no
    idle). A rig's `scale` is its whole content crop, swing room included --
    1.5 to 2 times the body -- and the current frame's bounds jump with every
    swing, so the resting pose is the body's size. Cached per rig and zoom."""
    key = (rig, round(zoom, 4))
    if key in _BODY_BOXES:
        return _BODY_BOXES[key]
    size = assets.scale_for(rig)
    box = None
    if size:
        anims = (assets.rig(rig) or {}).get("anims", {})
        name = "idle" if "idle" in anims else next(iter(anims), None)
        frames = (assets.frames(rig, name, size=(max(1, round(size[0] * zoom)),
                                                 max(1, round(size[1] * zoom))))
                  if name else [])
        if frames:
            bb = frames[0].get_bounding_rect()
            box = bb if bb.width and bb.height else None
    _BODY_BOXES[key] = box
    return box


def frame_size(assets, body, zoom: float) -> tuple[int, int] | None:
    """The strip's drawn size: its `box` framing the body at `over_body`
    times the body's larger side."""
    s = spec()
    anim = getattr(body, "anim", None)
    bb = body_box(assets, anim.rig, zoom) if anim is not None else None
    if bb is None:
        return None
    k = max(bb.width, bb.height) * float(s["over_body"]) / float(s["box"])
    fw, fh = assets.scale_for(s["sprite"])
    return max(1, round(fw * k)), max(1, round(fh * k))


def body_centre(renderer, assets, body, zoom: float) -> tuple[float, float] | None:
    """The body's centre on screen: its box placed the way the sprite is --
    the rig's anchor on the world position, mirrored with the facing, and
    dropped below the collider (`WorldRenderer.blit_rig`)."""
    rig = body.anim.rig
    bb = body_box(assets, rig, zoom)
    if bb is None:
        return None
    flip = getattr(body, "_facing", 1) < 0 and assets.face(rig) == "right"
    ax, ay = renderer.anchor_for(rig, flip)
    sx, sy = renderer.run.camera.world_to_screen(body.pos)
    left = sx - ax * zoom
    top = sy - ay * zoom + renderer.sprite_drop(body.radius)
    fw = assets.scale_for(rig)[0] * zoom
    cx = (fw - bb.centerx) if flip else bb.centerx
    return left + cx, top + bb.centery


def draw(renderer, surface, body) -> None:
    """The brackets on `body`, if it is marked and the mark matters."""
    if STATUS not in body.status:
        return
    run = renderer.run
    if not shown(run):
        return
    ps = renderer.ps
    assets = ps.game.assets
    s = spec()
    size = frame_size(assets, body, run.camera.zoom)
    if size is None:
        return
    rig = s["sprite"]
    frames = assets.frames(rig, "loop", size=size)
    if not frames:
        return
    i = int(run.stats["time"] * assets.fps(rig, "loop")) % len(frames)
    frame = frames[i]
    a = alpha(body)
    if a < 255:
        frame = frame.copy()
        frame.set_alpha(a)
    centre = body_centre(renderer, assets, body, run.camera.zoom)
    if centre is None:
        return
    surface.blit(frame, frame.get_rect(center=(round(centre[0]), round(centre[1]))))
