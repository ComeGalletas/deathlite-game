"""The two layers on a body: its aura, and its statuses (design §8.3).

They are separate on purpose. The **aura** is the one thing a player must be
able to read, because it is the only in-game sign of what an enemy will
react to; the **statuses** are what is currently happening to it. Reading
"this one is primed with fire" and "this one is burning" as the same mark
would make the whole reaction system guesswork.

So an aura is a ring at the body's edge plus its element's marker shape,
drawn from an authored rig where one exists, and a **locked** slot is the
same ring gone dim and hollow -- recognisable as "primed" versus "cannot be
primed" without a legend.

Statuses sit above the head instead, so the two never overlap: a flame for
burning, a chevron for slowed, a bracket for frozen.
"""
from __future__ import annotations

import pygame

from game.states.playing.visual.elements import markers

# Status marks, above the head so they never sit on the aura ring.
_STATUS_LIFT = 12
_STATUS_STEP = 9
_STATUS_ALPHA = 215

# Slowed and frozen have no authored art; these are their shapes.
_SLOW_SHAPE = ((0.0, 0.0), (0.5, 0.55), (1.0, 0.0), (1.0, 0.35),
               (0.5, 0.9), (0.0, 0.35))
_FREEZE_SHAPE = ((0.0, 0.0), (1.0, 0.0), (1.0, 0.25), (0.3, 0.25),
                 (0.3, 0.75), (1.0, 0.75), (1.0, 1.0), (0.0, 1.0))

_SLOW_COLOUR = (140, 200, 255)
_FREEZE_COLOUR = (215, 240, 255)
_BURN_COLOUR = (255, 150, 70)


def draw_auras(surface, run, visuals, now: float, budget, level=None) -> int:
    """One pass over the live bodies. Returns how many auras were drawn.

    Called once per terrace band, so a body's aura is painted with the
    ground it stands on and ends up *under* the body itself (M10 rule 3).
    """
    from game.states.playing.visual.elements.transient import off_band

    cam = run.camera
    view = cam.visible_rect().inflate(140, 140)
    drawn = 0
    for body in _bodies(run):
        state = getattr(body, "elemental", None)
        if state is None or not view.collidepoint(body.pos.x, body.pos.y):
            continue
        if off_band(run, level, body.pos):
            continue
        element = state.element(now)
        if element:
            _aura(surface, cam, body, visuals[element], visuals.aura, budget, run)
            drawn += 1
        elif state.is_locked(now):
            _locked(surface, cam, body, visuals.aura)
    return drawn


def draw_statuses(surface, run, visuals, now: float, level=None) -> None:
    from game.states.playing.visual.elements.transient import off_band

    cam = run.camera
    view = cam.visible_rect().inflate(140, 140)
    for body in _bodies(run):
        status = getattr(body, "status", None)
        if status is None or not view.collidepoint(body.pos.x, body.pos.y):
            continue
        if off_band(run, level, body.pos):
            continue
        sx, sy = cam.world_to_screen(body.pos)
        # Freeze is not a mark over the head: it is the body encased, so it
        # draws on the body and the marks stack above whatever is left.
        if "freeze" in status:
            _freeze_block(surface, visuals, body, status, sx, sy, cam.zoom)
        marks = _marks(status)
        if not marks:
            continue
        top = sy - (body.radius + _STATUS_LIFT) * cam.zoom
        for i, mark in enumerate(marks):
            mark(surface, visuals, sx, top - i * _STATUS_STEP * cam.zoom, cam.zoom)


# --- the aura ---------------------------------------------------------------------

def _aura(surface, cam, body, profile, style, budget, run) -> None:
    """The sprite, or the ring and marker where there is no sprite.

    Not both. M8 drew the ring under every element and layered the rig on
    top, because the one authored sheet it had was sparse lightning that did
    not read as "primed" alone. M10 replaced the art with whole shapes and
    the owner's rule with it: where a sprite is wired it *is* the indicator,
    and the ring and the marker stay only as the fallback that keeps the
    game playable with an empty `assets/`.
    """
    sx, sy = cam.world_to_screen(body.pos)
    radius = (body.radius + style.ring_pad) * cam.zoom
    size = profile.aura_size(radius * 2.0 * style.rig_scale)
    frame = profile.aura_frame(size=size) if size else None
    if frame is not None:
        surface.blit(frame, frame.get_rect(center=(int(sx), int(sy))))
    else:
        _ring(surface, (int(sx), int(sy)), int(radius), profile.colour,
              style.alpha, style.ring_width)
        markers.draw(surface, profile.marker, sx,
                     sy - radius - style.marker_gap * cam.zoom,
                     style.marker_size * cam.zoom, profile.colour, style.alpha)
    _shed(run, body, profile, budget)


def _locked(surface, cam, body, style) -> None:
    """A slot that cannot take an aura: the same ring, dimmed and dashed, so
    "primed" and "cannot be primed" are one glance apart."""
    sx, sy = cam.world_to_screen(body.pos)
    radius = int((body.radius + style.ring_pad) * cam.zoom)
    _ring(surface, (int(sx), int(sy)), radius, (190, 190, 200),
          style.locked_alpha, 1)


def _shed(run, body, profile, budget) -> None:
    """A trickle of particles from the aura, inside the elemental budget."""
    if budget is None:
        return
    rate = profile.particles.rate
    # One chance a frame rather than an accumulator per enemy: with a crowd
    # this large the average is what matters and a per-body float would cost
    # more than the particle.
    if run.rng.random() > rate / 60.0:
        return
    if not budget.take(profile.element, 1):
        return
    p = profile.particles
    # `under`: the shed is part of the aura, and the aura draws behind the
    # body wearing it (M10 rule 3). Without this the one elemental visual
    # the elements package does not draw itself would be the one visual
    # still sitting on top of the crowd.
    run.particles.burst(body.pos, profile.colour, count=1, speed=p.speed,
                        life=p.life, radius=p.radius, under=True)


def _ring(surface, center, radius: int, colour, alpha: int, width: int) -> None:
    if alpha <= 0 or radius <= 0:
        return
    size = radius * 2 + width * 2 + 2
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(layer, (*colour, alpha), (size // 2, size // 2),
                       radius, max(1, width))
    surface.blit(layer, (center[0] - size // 2, center[1] - size // 2))


# --- the statuses ------------------------------------------------------------------

# How long the block's shatter takes, out of the strip's 40 frames. The
# freeze itself is 1.5 s by default but tunable and modifiable, and no
# original duration is kept anywhere, so the block holds *formed* for
# however long the freeze runs and shatters over its last moments. The
# formation frames are skipped; giving them their proper run would mean
# recording when each body froze, which is combat-side state for a
# rendering detail.
_SHATTER_SECONDS = 0.45
_SHATTER_FROM = 0.72          # the strip is formed up to here, shattering after


def _marks(status) -> list:
    out = []
    if "burn" in status:
        out.append(_burn_mark)
    if "freeze" in status:
        pass                  # drawn on the body by `_freeze_block`
    elif "chill" in status:
        out.append(_slow_mark)
    return out


def _freeze_block(surface, visuals, body, status, sx, sy, zoom) -> None:
    """The authored ice block over a frozen body, or the bracket where the
    art is missing."""
    rig = visuals.status_rig("freeze")
    if rig is None:
        _freeze_mark(surface, visuals, sx,
                     sy - (body.radius + _STATUS_LIFT) * zoom, zoom)
        return
    left = status.remaining("freeze")
    if left > _SHATTER_SECONDS:
        progress = _SHATTER_FROM
    else:
        progress = _SHATTER_FROM + (1.0 - _SHATTER_FROM) * (
            1.0 - max(0.0, left) / _SHATTER_SECONDS)
    frame = visuals.status_frame_at("freeze", progress,
                                    size=_block_size(visuals, body, zoom))
    if frame is not None:
        surface.blit(frame, frame.get_rect(center=(int(sx), int(sy))))


def _block_size(visuals, body, zoom):
    natural = visuals.status_natural("freeze")
    if not natural:
        return None
    nw, nh = natural
    width = max(6, int(body.radius * 2.6 * zoom))
    return (width, max(6, int(width * nh / nw)))


def _burn_mark(surface, visuals, sx, sy, zoom) -> None:
    """The authored flame where the art exists, its marker where not.

    Asked for by *status id* rather than through Fire's profile: this same
    burn is applied by the weapon blessings, which have no element behind
    them at all, and it has to look the same either way."""
    frame = visuals.status_frame("burn")
    if frame is not None:
        scaled = pygame.transform.smoothscale(
            frame, (max(4, int(frame.get_width() * 0.34 * zoom)),
                    max(6, int(frame.get_height() * 0.34 * zoom))))
        surface.blit(scaled, scaled.get_rect(midbottom=(int(sx), int(sy))))
        return
    markers.draw(surface, "flame", sx, sy, 6 * zoom, _BURN_COLOUR, _STATUS_ALPHA)


def _slow_mark(surface, visuals, sx, sy, zoom) -> None:
    _shape(surface, _SLOW_SHAPE, sx, sy, 7 * zoom, _SLOW_COLOUR)


def _freeze_mark(surface, visuals, sx, sy, zoom) -> None:
    _shape(surface, _FREEZE_SHAPE, sx, sy, 8 * zoom, _FREEZE_COLOUR)


def _shape(surface, shape, cx, cy, size, colour) -> None:
    if size < 2:
        return
    pts = [(cx + (x - 0.5) * size, cy + (y - 0.5) * size) for x, y in shape]
    box = pygame.Rect(0, 0, int(size) + 4, int(size) + 4)
    layer = pygame.Surface(box.size, pygame.SRCALPHA)
    local = [(x - cx + box.width / 2, y - cy + box.height / 2) for x, y in pts]
    pygame.draw.polygon(layer, (*colour, _STATUS_ALPHA), local)
    pygame.draw.polygon(layer, (18, 16, 24, _STATUS_ALPHA), local, 1)
    surface.blit(layer, (int(cx - box.width / 2), int(cy - box.height / 2)))


def _bodies(run):
    if run.boss is not None and run.boss.alive:
        yield run.boss
    yield from run.enemies
