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

import pygame

from game.states.playing.visual.elements import layers, transient
from game.states.playing.visual.elements.budget import ParticleBudget
from game.states.playing.visual.elements.building_glow import BuildingGlow
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
        # CMB-009.1: the glow under an elemental buff building. No `elements`
        # block means no building is ever elemental, so there is no glow.
        block = content.buildings.get("elements")
        self.building_glow = BuildingGlow(block["glow"]) if block else None

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


_WASH_CACHE: dict[tuple, tuple] = {}
_WASH_CACHE_CAP = 512


def washed(frame, element, profiles=None):
    """`frame` coloured toward `element`, or `frame` itself for no element.

    How a **primed enemy** wears the element that is on it. The element's
    colour is lifted most of the way to white, multiplied over the frame
    and laid back at `wash.alpha`, which shifts an enemy's hue without
    darkening it -- a straight multiply by a saturated colour would crush
    every channel the tint is low in and turn a bone-white skeleton navy.

    It is not how an *attack* wears its element, though M13 first built it
    that way. A multiply can only ever darken toward the overlap of two
    hues, so on saturated art -- the orbiter is 1.00 saturation -- it
    cannot produce the element's colour at any strength: measured at four,
    stronger only meant muddier. Those sprites are recoloured offline
    instead (`recolour_element_variants.py`) and resolved by
    `variant_rig`, which also costs nothing to draw.

    Cached on `(id(frame), element)`, with the source kept in the entry so
    its id cannot be recycled under the cache. The frames handed in are the
    asset cache's own surfaces, so the same one comes back for every frame
    of an animation and copying it per draw would be the expensive way to
    do this.
    """
    if not element or frame is None:
        return frame
    key = (id(frame), int(element))
    hit = _WASH_CACHE.get(key)
    if hit is not None and hit[0] is frame:
        return hit[1]
    if profiles is None:
        from game.content import get_content
        profiles = get_visuals(get_content())
    style = profiles.wash
    colour = profiles.tint(element)
    pale = tuple(int(c + (255 - c) * style.lift) for c in colour)
    over = frame.copy()
    over.fill((*pale, 255), special_flags=pygame.BLEND_RGBA_MULT)
    over.set_alpha(style.alpha)
    out = frame.copy()
    out.blit(over, (0, 0))
    if len(_WASH_CACHE) >= _WASH_CACHE_CAP:
        _WASH_CACHE.clear()
    _WASH_CACHE[key] = (frame, out)
    return out


def variant_rig(assets, base: str, element=None) -> str:
    """`base` in the colour of `element`, or its plain colour.

    Two kinds of family arrive here, and each says which it is in the data.

    A melee attack is **replaced**. The pack it comes from drew all nine
    colours of every animation, so `sword_slash` has no rig of its own and
    five siblings carry the art: `sword_slash_plain` and one per element.
    The `_plain` sibling is the marker.

    Everything else is **recoloured**. The rig keeps its own art for an
    uninfused weapon and declares an `infused` block, from which
    `tools/asset_pipeline/recolour_element_variants.py` generates the four
    element rigs. There is deliberately no `_plain`: it would be a second
    copy of sheets the base already owns, and a copy is a thing that goes
    stale when the art it was copied from is replaced.

    Neither is guessed from a name. `variant_rig(assets, "totem_bolt",
    FIRE)` would otherwise resolve to `totem_bolt_fire`, which is a real
    rig and is the Grave Totem bolt's flame tail -- nothing to do with an
    infusion. Name guessing across a flat rig namespace finds things it did
    not mean to.
    """
    if assets.rig(f"{base}_plain") is not None:
        plain = f"{base}_plain"
    elif (assets.rig(base) or {}).get("infused") is not None:
        plain = base
    else:
        return base
    if element:
        name = f"{base}_{element.key}"
        if assets.rig(name) is not None:
            return name
    return plain


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
