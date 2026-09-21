"""The elemental visual system (design §8).

One way to show any element, on anything. The layers split the way the
design asks: an **aura** at a body's edge, **statuses** above its head, and
the **transient** effects that belong to a moment rather than to a body.

Three rules hold across all of it:

* **shape as well as colour.** Every element has a marker silhouette, so
  none of this depends on telling orange from yellow.
* **a budget, not a flood.** Elemental particles draw from their own
  per-frame allowance, so a hundred auras cannot starve the hit bursts of
  the shared pool.
* **authored art where it exists, procedural where it does not.** Only
  Thunder has an authored aura today and only Fire a flame; the rest fall
  back to the ring, which the design names as the baseline.

This package replaces the placeholder `visual/element_fx.py` of M3.
"""
from __future__ import annotations

from game.states.playing.visual.elements import layers, transient
from game.states.playing.visual.elements.budget import ParticleBudget
from game.states.playing.visual.elements.profiles import get_visuals
from game.states.playing.visual.elements.transient import (  # noqa: F401
    ARC_SECONDS, Arc, Flash, mix)


class ElementVisuals:
    """What a run holds: the profiles, the budget and the frame's counters.

    One per run, built beside the resolver. The drawing functions are free
    functions; this is the state they share.
    """

    def __init__(self, content, assets=None) -> None:
        self.profiles = get_visuals(content, assets)
        self.budget = ParticleBudget(self.profiles.budget.per_frame,
                                     self.profiles.budget.per_element)
        self.auras_drawn = 0

    def update(self, dt: float) -> None:
        """Advance the shared per-element animation clocks."""
        self.profiles.update(dt)

    def begin_frame(self) -> None:
        self.budget.begin_frame()

    def tint(self, element):
        return self.profiles.tint(element)

    def report(self) -> str:
        return f"{self.auras_drawn} drawn  {self.budget.report()}"


def draw(surface, run) -> None:
    """Every elemental visual, over the world and under the HUD."""
    visuals = run.element_visuals
    if visuals is None:
        return
    now = run.stats["time"]
    visuals.begin_frame()
    transient.draw_areas(surface, run, visuals.profiles, now)
    visuals.auras_drawn = layers.draw_auras(surface, run, visuals.profiles, now,
                                            visuals.budget)
    layers.draw_statuses(surface, run, visuals.profiles, now)
    transient.draw_transient(surface, run, visuals.profiles, now)


def sweep(run, now: float) -> None:
    transient.sweep(run, now)


def tint(element):
    """The element's colour, for callers outside a run (the build pane)."""
    from game.content import get_content
    return get_visuals(get_content()).tint(element)


def blend(colour, toward, amount: float = 0.55):
    """`colour` mixed toward `toward` -- how an infused projectile is
    tinted without losing the weapon's own look."""
    return mix(colour, toward, amount)


__all__ = ["ElementVisuals", "draw", "sweep", "tint", "blend", "mix",
           "Arc", "Flash", "ARC_SECONDS"]
