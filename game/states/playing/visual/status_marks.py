"""The `mark` status drawn on the body that carries it (RND-007).

The Rod leaves `mark` on what it hits; Marked Prey and Crossfire pay out
against it. It is drawn as raspberry lock-on brackets framing the body
(`data/weapons/status_visuals.json` `mark`, art cut by
`tools/asset_pipeline/cut_mark_brackets.py`):

* **only while it matters** -- a weapon the hero holds carries one of the
  visual's `shown_with_effects` (`syn_vs_marked`) above 0 (owner,
  2026-09-24). A Rod build nothing pays out for shows nothing.
* **framing the body** -- centred on the drawn sprite, the art's `box` scaled
  to `over_body` x the sprite's larger drawn side, so a turtle and a skull
  are both bracketed, and the brackets breathe with the strip.
* **fading out** over the status's last `fade` seconds.

Drawn right after the body's own sprite (`WorldRenderer.one_enemy` /
`boss`), so it depth-sorts with the body: a body standing in front still
covers it. The authored brackets replace the procedural status ring, which
stays for the primitive fallback in the data's `colour`.
"""
from __future__ import annotations

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


def frame_size(assets, body, zoom: float) -> tuple[int, int] | None:
    """The strip's drawn size: its `box` framing the body's drawn sprite."""
    s = spec()
    anim = getattr(body, "anim", None)
    rig_size = assets.scale_for(anim.rig) if anim is not None else None
    if not rig_size:
        return None
    target = max(rig_size) * zoom * float(s["over_body"])
    k = target / float(s["box"])
    fw, fh = assets.scale_for(s["sprite"])
    return max(1, round(fw * k)), max(1, round(fh * k))


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
    cx, cy, _d = renderer.spawn_fx_geometry(body)
    surface.blit(frame, frame.get_rect(center=(round(cx), round(cy))))
