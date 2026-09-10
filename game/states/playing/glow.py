"""Soft glow discs for the world pass (journal: "Breathing glow under the XP
orbs", 2026-09-04).

`GlowCache` pre-renders a white (or any colour) disc with a stepped soft
edge once per `(diameter, alpha)` and hands the same Surface back on every
later call, so a renderer that paints a glow under a hundred orbs does one
dict lookup and one blit per orb and never allocates per frame. Alpha values
are quantised to `steps` levels between `alpha_min` and `alpha_max` first,
which is what keeps the cache small (~3 orb sizes x 8 steps).

`pulse_alpha(age, cfg)` is the breathing curve: a sine over `period` seconds
between the two alphas, driven by the caller's clock -- the orbs use their
own `age`, so orbs that dropped at different moments breathe out of phase.

The cache is generic on purpose: a fixed-alpha, non-breathing glow (the one
planned under enemy projectiles) is `surface(diameter, alpha)` with a
constant alpha.
"""
from __future__ import annotations

import math

import pygame

from game import config

# Soft edge: concentric filled discs from the rim inward, each a step more
# opaque, so the centre carries the full alpha and the rim fades to nothing.
_RINGS = (1.0, 0.8, 0.6, 0.42)


def pulse_alpha(age: float, cfg: dict | None = None) -> int:
    """Alpha in `[alpha_min, alpha_max]` for a glow that has breathed for
    `age` seconds: mid-way at 0, peaking at a quarter period, lowest at
    three quarters. A non-positive period holds the maximum."""
    cfg = cfg or config.XP_GLOW
    lo, hi = int(cfg["alpha_min"]), int(cfg["alpha_max"])
    period = float(cfg["period"])
    if period <= 0.0:
        return hi
    phase = 0.5 + 0.5 * math.sin(math.tau * age / period)
    return int(round(lo + (hi - lo) * phase))


def quantise(alpha: int, cfg: dict | None = None) -> int:
    """Snap `alpha` to one of `steps` levels between the config's min and
    max (both inclusive), so every breathing value hits a cached surface."""
    cfg = cfg or config.XP_GLOW
    lo, hi = int(cfg["alpha_min"]), int(cfg["alpha_max"])
    steps = max(1, int(cfg["steps"]))
    if steps == 1 or hi <= lo:
        return hi
    span = hi - lo
    k = round((min(max(alpha, lo), hi) - lo) / span * (steps - 1))
    return int(round(lo + span * k / (steps - 1)))


class GlowCache:
    def __init__(self, cfg: dict | None = None) -> None:
        self.cfg = cfg or config.XP_GLOW
        self._surfs: dict[tuple[int, int, tuple], pygame.Surface] = {}

    def clear(self) -> None:
        self._surfs.clear()

    def __len__(self) -> int:
        return len(self._surfs)

    def diameter(self, orb_px: float, zoom: float) -> int:
        """Screen-pixel diameter of the glow under an orb `orb_px` world px
        wide: `scale` times the orb, at the camera zoom. 0 when off."""
        scale = float(self.cfg["scale"])
        if scale <= 0.0:
            return 0
        return max(2, int(round(orb_px * scale * zoom)))

    def surface(self, diameter: int, alpha: int, colour=None) -> pygame.Surface | None:
        """The cached disc, built on first use. None for a zero diameter."""
        if diameter <= 0 or alpha <= 0:
            return None
        colour = tuple(colour if colour is not None else self.cfg["colour"])
        key = (int(diameter), int(alpha), colour)
        surf = self._surfs.get(key)
        if surf is None:
            surf = self._build(int(diameter), int(alpha), colour)
            self._surfs[key] = surf
        return surf

    def pulsed(self, orb_px: float, zoom: float, age: float) -> pygame.Surface | None:
        """The breathing glow for an orb: quantised pulse alpha -> surface."""
        d = self.diameter(orb_px, zoom)
        if d == 0:
            return None
        return self.surface(d, quantise(pulse_alpha(age, self.cfg), self.cfg))

    @staticmethod
    def _build(diameter: int, alpha: int, colour) -> pygame.Surface:
        surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        c = diameter / 2.0
        n = len(_RINGS)
        for i, frac in enumerate(_RINGS):
            r = max(1, int(round(c * frac)))
            a = int(round(alpha * (i + 1) / n))
            pygame.draw.circle(surf, (*colour, a), (int(c), int(c)), r)
        return surf
