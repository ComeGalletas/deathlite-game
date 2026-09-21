"""The effects that belong to a moment rather than to a body: Thunder's
jump arcs, a reaction's flash, and the Wind tornado's ring
(design §8.4, §8.5, §8.6).

Arcs and flashes are **pooled** into one fixed-size list, because a big
Thunder tree can ask for a dozen in a single frame and a runaway one must
not be able to grow the list faster than the sweep empties it. A request
past the cap is simply not drawn, which is the same level-of-detail rule
the particle budget follows.

A reaction's flash is a **blend of its two elements** -- the design's own
starting point (§8.5), and it means the six reactions are distinguishable
from each other and from either parent without six bespoke effects.
"""
from __future__ import annotations

import math

import pygame

from combat.elements import config as element_config
from combat.elements.ids import ElementId

ARC_SECONDS = 0.18
FLASH_SECONDS = 0.3
# The whole transient list, arcs and flashes together.
MAX_EFFECTS = 160

_ARC_WIDTH = 2
_ARC_JITTER = 5.0        # world px of wobble, so a bolt is not a ruler line
_ARC_SEGMENTS = 4
_FLASH_RINGS = 3


class Arc:
    """One Thunder jump, from where it left to where it landed."""
    __slots__ = ("a", "b", "element", "until", "seed")

    def __init__(self, a, b, element, until: float) -> None:
        self.a = pygame.Vector2(a)
        self.b = pygame.Vector2(b)
        self.element = element
        self.until = float(until)
        # Fixed per arc so the wobble holds still for its lifetime rather
        # than reshuffling every frame.
        self.seed = (int(self.a.x) * 31 + int(self.b.y)) & 0xFF

    def draw(self, surface, cam, visuals, now: float) -> None:
        left = self.until - now
        if left <= 0.0:
            return
        colour = visuals.tint(self.element)
        alpha = max(20, int(235 * min(1.0, left / ARC_SECONDS)))
        points = _jagged(self.a, self.b, self.seed)
        screen = [cam.world_to_screen(p) for p in points]
        _line_strip(surface, screen, colour, alpha, _ARC_WIDTH)


class Flash:
    """A reaction going off: rings in the blend of the two elements that
    made it."""
    __slots__ = ("pos", "reaction", "radius", "until")

    def __init__(self, pos, reaction, radius: float, until: float) -> None:
        self.pos = pygame.Vector2(pos)
        self.reaction = reaction
        self.radius = float(radius)
        self.until = float(until)

    def draw(self, surface, cam, visuals, now: float) -> None:
        left = self.until - now
        if left <= 0.0:
            return
        # Clamped, not assumed: a caller is free to hand a longer lifetime
        # than the nominal one, and an alpha over 255 is a hard error in
        # pygame rather than a bright ring.
        fade = min(1.0, max(0.0, left / FLASH_SECONDS))
        grown = 1.0 - fade
        alpha = int(210 * fade)
        sx, sy = cam.world_to_screen(self.pos)
        palette = blend_colours(visuals, self.reaction)
        spread = self.radius * (0.35 + 0.65 * grown)
        # A soft disc under the rings, so a reaction reads as something
        # going off rather than as three outlines over busy terrain.
        _disc(surface, (int(sx), int(sy)), int(spread * cam.zoom),
              palette[len(palette) // 2], int(alpha * 0.28))
        for i, colour in enumerate(palette):
            radius = int((spread - i * 4) * cam.zoom)
            if radius > 0:
                _ring(surface, (int(sx), int(sy)), radius, colour,
                      max(0, alpha - i * 30), 3)


def blend_colours(visuals, reaction) -> list[tuple[int, int, int]]:
    """A reaction's palette: its two parents and the mix between them, so
    every reaction reads as *both* of the elements that made it (§8.5)."""
    pair = element_config.REACTION_PAIRS.get(reaction)
    if not pair:
        return [(255, 255, 255)]
    first, second = (visuals.tint(e) for e in pair)
    return [first, mix(first, second, 0.5), second][:_FLASH_RINGS]


def mix(a, b, amount: float) -> tuple[int, int, int]:
    keep = 1.0 - amount
    return tuple(int(round(x * keep + y * amount)) for x, y in zip(a, b))


def draw_areas(surface, run, visuals, now: float) -> None:
    """The Wind tornado: a ring at its true radius, plus a second turning
    inside it so the thing reads as spinning rather than as a circle. A
    Wind *reaction*'s area is tinted toward the element it was paired with,
    which is how one component serves all four (§8.4)."""
    cam = run.camera
    for area in run.wind_areas:
        left = area.remaining(now)
        if left <= 0.0:
            continue
        colour = _area_colour(visuals, area)
        sx, sy = cam.world_to_screen(area.pos)
        radius = max(2, int(area.radius * cam.zoom))
        fade = min(1.0, left / 0.4)
        _ring(surface, (int(sx), int(sy)), radius, colour, int(110 * fade), 3)
        spin = now * 5.0
        inner = int(radius * 0.62)
        if inner > 2:
            _arc_ring(surface, (int(sx), int(sy)), inner, colour,
                      int(150 * fade), spin)


def _area_colour(visuals, area):
    """Wind, mixed toward whatever the reaction paired it with."""
    from combat.elements import tracking

    other = {tracking.FIREWIND: ElementId.FIRE,
             tracking.ICEWIND: ElementId.ICE,
             tracking.THUNDERWIND: ElementId.THUNDER}.get(area.effect)
    wind = visuals.tint(ElementId.WIND)
    return wind if other is None else mix(wind, visuals.tint(other), 0.55)


# --- the pooled list --------------------------------------------------------------

def add(run, effect) -> bool:
    fx = run.element_fx
    if len(fx) >= MAX_EFFECTS:
        return False
    fx.append(effect)
    return True


def sweep(run, now: float) -> None:
    fx = run.element_fx
    if fx:
        run.element_fx = [e for e in fx if e.until > now]


def draw_transient(surface, run, visuals, now: float) -> None:
    cam = run.camera
    for effect in run.element_fx:
        effect.draw(surface, cam, visuals, now)


# --- drawing helpers ----------------------------------------------------------------

def _jagged(a, b, seed: int):
    """A few kinked points between `a` and `b`. Lightning is not a ruler."""
    span = b - a
    length = span.length()
    if length < 1e-3:
        return [a, b]
    normal = pygame.Vector2(-span.y, span.x) / length
    out = [a]
    for i in range(1, _ARC_SEGMENTS):
        t = i / _ARC_SEGMENTS
        # Deterministic wobble from the arc's own seed, alternating sides.
        offset = ((seed >> i) & 0x7) / 7.0 - 0.5
        sway = normal * (offset * _ARC_JITTER * (1.0 if i % 2 else -1.0))
        out.append(a + span * t + sway)
    out.append(b)
    return out


def _line_strip(surface, points, colour, alpha: int, width: int) -> None:
    alpha = min(255, int(alpha))
    if len(points) < 2 or alpha <= 0:
        return
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    pad = width + 2
    left, top = int(min(xs)) - pad, int(min(ys)) - pad
    w = int(max(xs) - min(xs)) + pad * 2
    h = int(max(ys) - min(ys)) + pad * 2
    if w <= 0 or h <= 0:
        return
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    local = [(x - left, y - top) for x, y in points]
    pygame.draw.lines(layer, (*colour, alpha), False, local, width)
    surface.blit(layer, (left, top))


def _ring(surface, center, radius: int, colour, alpha: int, width: int) -> None:
    alpha = min(255, int(alpha))
    if alpha <= 0 or radius <= 0:
        return
    size = radius * 2 + width * 2 + 2
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(layer, (*colour, alpha), (size // 2, size // 2),
                       radius, max(1, width))
    surface.blit(layer, (center[0] - size // 2, center[1] - size // 2))


def _disc(surface, center, radius: int, colour, alpha: int) -> None:
    alpha = min(255, int(alpha))
    if alpha <= 0 or radius <= 0:
        return
    size = radius * 2 + 2
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(layer, (*colour, alpha), (size // 2, size // 2), radius)
    surface.blit(layer, (center[0] - size // 2, center[1] - size // 2))


def _arc_ring(surface, center, radius: int, colour, alpha: int,
              phase: float) -> None:
    """Three short arcs turning together -- the tornado's motion, which is
    what tells it apart from every other circle on screen."""
    alpha = min(255, int(alpha))
    if alpha <= 0 or radius <= 1:
        return
    size = radius * 2 + 6
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    box = pygame.Rect(3, 3, radius * 2, radius * 2)
    for i in range(3):
        start = phase + i * (math.tau / 3)
        pygame.draw.arc(layer, (*colour, alpha), box, start,
                        start + math.tau / 6, 2)
    surface.blit(layer, (center[0] - size // 2, center[1] - size // 2))
