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

from combat.elements.ids import ElementId
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


def draw_auras(surface, run, visuals, now: float, budget) -> int:
    """One pass over the live bodies. Returns how many auras were drawn."""
    cam = run.camera
    view = cam.visible_rect().inflate(140, 140)
    drawn = 0
    for body in _bodies(run):
        state = getattr(body, "elemental", None)
        if state is None or not view.collidepoint(body.pos.x, body.pos.y):
            continue
        element = state.element(now)
        if element:
            _aura(surface, cam, body, visuals[element], visuals.aura, budget, run)
            drawn += 1
        elif state.is_locked(now):
            _locked(surface, cam, body, visuals.aura)
    return drawn


def draw_statuses(surface, run, visuals, now: float) -> None:
    cam = run.camera
    view = cam.visible_rect().inflate(140, 140)
    for body in _bodies(run):
        status = getattr(body, "status", None)
        if status is None or not view.collidepoint(body.pos.x, body.pos.y):
            continue
        marks = _marks(status)
        if not marks:
            continue
        sx, sy = cam.world_to_screen(body.pos)
        top = sy - (body.radius + _STATUS_LIFT) * cam.zoom
        for i, mark in enumerate(marks):
            mark(surface, visuals, sx, top - i * _STATUS_STEP * cam.zoom, cam.zoom)


# --- the aura ---------------------------------------------------------------------

def _aura(surface, cam, body, profile, style, budget, run) -> None:
    sx, sy = cam.world_to_screen(body.pos)
    radius = (body.radius + style.ring_pad) * cam.zoom

    # The ring is drawn for every element, authored art or not. It is
    # the part that has to be *readable* -- an aura is the only sign of
    # what an enemy will react to -- and Thunder's authored sheet is
    # sparse lightning, lovely but not a shape that says "primed".
    # So the rig goes over the ring rather than instead of it.
    _ring(surface, (int(sx), int(sy)), int(radius), profile.colour,
          style.alpha, style.ring_width)
    frame = profile.aura_frame(size=_rig_size(radius))
    if frame is not None:
        surface.blit(frame, frame.get_rect(center=(int(sx), int(sy))))

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


def _rig_size(radius: float):
    side = max(8, int(radius * 2.6))
    return (side, side)


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
    run.particles.burst(body.pos, profile.colour, count=1, speed=p.speed,
                        life=p.life, radius=p.radius)


def _ring(surface, center, radius: int, colour, alpha: int, width: int) -> None:
    if alpha <= 0 or radius <= 0:
        return
    size = radius * 2 + width * 2 + 2
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(layer, (*colour, alpha), (size // 2, size // 2),
                       radius, max(1, width))
    surface.blit(layer, (center[0] - size // 2, center[1] - size // 2))


# --- the statuses ------------------------------------------------------------------

def _marks(status) -> list:
    out = []
    if "burn" in status:
        out.append(_burn_mark)
    if "freeze" in status:
        out.append(_freeze_mark)
    elif "chill" in status:
        out.append(_slow_mark)
    return out


def _burn_mark(surface, visuals, sx, sy, zoom) -> None:
    """Fire's authored flame where the art exists, its marker where not."""
    profile = visuals.get(ElementId.FIRE)
    frame = profile.status_frame() if profile else None
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
