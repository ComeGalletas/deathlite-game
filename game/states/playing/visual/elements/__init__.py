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


def begin_frame(run) -> None:
    """Once a frame, before the banded passes start.

    The particle budget and the aura counter are per *frame*: `draw_under`
    runs once per terrace and resetting them there would give each band the
    whole budget and leave the counter showing only the last band's auras.
    """
    visuals = run.element_visuals
    if visuals is None:
        return
    visuals.begin_frame()
    visuals.auras_drawn = 0


def draw_under(surface, run, level=None) -> None:
    """The elemental state of the field, under the bodies it belongs to.

    Auras, the Wind tornado, the status marks and Thunder's jump arcs. All
    of them describe something that *is the case* about a body or a patch of
    ground, so they paint with the terrace and the sprites go over them
    (M10 rule 3). `level=None` draws the lot wherever it is, which is what
    the headless tests and `draw` below pass.
    """
    visuals = run.element_visuals
    if visuals is None:
        return
    now = run.stats["time"]
    _shed_particles(surface, run, level)
    transient.draw_areas(surface, run, visuals.profiles, now, level)
    visuals.auras_drawn += layers.draw_auras(
        surface, run, visuals.profiles, now, visuals.budget, level)
    layers.draw_statuses(surface, run, visuals.profiles, now, level)
    transient.draw_transient(surface, run, visuals.profiles, now, level,
                             over=False)


def _shed_particles(surface, run, level) -> None:
    """The aura's shed, with this terrace and under its bodies.

    Lowest of the elemental layers: these are motes coming off a body, so
    they belong beneath even the tornado and the jump arcs.
    """
    particles = getattr(run, "particles", None)
    if particles is None:
        return
    keep = None
    if level is not None:
        def keep(pos, _level=level, _run=run):
            return not transient.off_band(_run, _level, pos)
    particles.draw(surface, run.camera, under=True, keep=keep)


def draw_reactions(surface, run) -> None:
    """The reaction bursts, over every character.

    Not banded and not culled by terrace: a reaction is a moment rather
    than a state, it is the one elemental visual the player must not miss,
    and every one of them is gone inside 0.7 s.
    """
    visuals = run.element_visuals
    if visuals is None:
        return
    transient.draw_transient(surface, run, visuals.profiles,
                             run.stats["time"], None, over=True)


def draw(surface, run) -> None:
    """Every elemental visual in one pass, unbanded.

    What the game used to do, and still the right thing for a caller with
    no terraces to band against -- the headless render tests, and any
    future still of a single body.
    """
    begin_frame(run)
    draw_under(surface, run, None)
    draw_reactions(surface, run)


def sweep(run, now: float) -> None:
    transient.sweep(run, now)


def variant_rig(assets, base: str, element=None) -> str:
    """`base` in the colour of `element`, or its plain colour.

    The melee attacks are authored once per state -- `sword_slash_plain`,
    `sword_slash_fire`, and so on -- rather than tinted, because the pack
    they come from drew all nine colours of each animation and an authored
    colour beats a computed one (M13).

    A rig is only treated as variant-cut when its `_plain` exists. That
    guard is not ceremony: `variant_rig(assets, "totem_bolt", FIRE)` would
    otherwise resolve to `totem_bolt_fire`, which is a real rig and is the
    Grave Totem bolt's flame tail -- nothing to do with an infusion. Name
    guessing across a flat rig namespace finds things it did not mean to,
    and `_plain` is the marker that says this family was cut on purpose.
    """
    if assets.frame_count(f"{base}_plain", "loop") <= 0:
        return base
    if element:
        name = f"{base}_{element.key}"
        if assets.frame_count(name, "loop") > 0:
            return name
    return f"{base}_plain"


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
