"""The reactions (design §5), and the dispatcher the resolver calls.

One module per reaction, as the plan asks, because they have little in
common beyond the two rules in `base.py`: Frostburn is a pair of statuses,
Overload is a blast, Superconduct is a spread, and the three Wind
reactions are the §4.4 area with three different payloads.

`run` is what `ElementalResolver.reaction_runner` is wired to. A reaction
id with no entry is simply not run, so the table can be filled in over
several milestones without the resolver knowing.
"""
from __future__ import annotations

from combat.elements.ids import ReactionId
from combat.elements.reactions.base import Reaction, blast, status_on  # noqa: F401
from combat.elements.reactions.firewind import FireWind
from combat.elements.reactions.frostburn import Frostburn
from combat.elements.reactions.icewind import IceWind
from combat.elements.reactions.overload import Overload
from combat.elements.reactions.superconduct import Superconduct
from combat.elements.reactions.thunderwind import ThunderWind

REACTIONS: dict[ReactionId, Reaction] = {
    r.ID: r for r in (Frostburn(), Overload(), Superconduct(),
                      FireWind(), IceWind(), ThunderWind())
}


def run(target, variant, config, ctx) -> bool:
    """Fire the reaction `variant` names. Returns whether one ran."""
    reaction = REACTIONS.get(variant.reaction)
    if reaction is None:
        return False
    reaction.run(target, config, ctx)
    # One flash per reaction, here rather than in each of the six: they
    # all go off the same way and the blend is derived from the pair.
    # `ctx.now`, not an expiry: how long the thing stays on screen is the
    # renderer's business and comes from `element_visuals.json`. This used
    # to import the duration from the visual layer, which had the combat
    # side reaching across the seam to ask how long its own effect lasted.
    ctx.world.add_flash(target.pos, variant.reaction, _flash_radius(config),
                        ctx.now)
    return True


def _flash_radius(config) -> float:
    """How wide the reaction actually reached, so the flash matches it:
    a blast's shockwave, an area's circle, or a modest default for a
    reaction that only touched its own target."""
    for field in ("shockwave_radius", "radius", "max_range"):
        value = getattr(config, field, None)
        if value:
            return float(value)
    return 40.0


def implemented() -> tuple[ReactionId, ...]:
    return tuple(sorted(REACTIONS, key=int))


__all__ = ["REACTIONS", "Reaction", "run", "implemented", "blast", "status_on"]
