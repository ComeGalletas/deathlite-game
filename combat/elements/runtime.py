"""Building the elemental system for a run.

One function, so `PlayingState` does not have to know how the registry, the
profiles and the tracking fit together. Profiles are resolved **once, here**,
because the data cannot change mid-run, and their complaints are logged
rather than raised: bad enemy data degrades in this project, it never
refuses to boot (`spawn/roster.py` sets the precedent).
"""
from __future__ import annotations

import logging

from combat.elements import reactions
from combat.elements.profiles import log_notes, resolve
from combat.elements.registry import get_registry
from combat.elements.resolve import ElementalResolver
from combat.elements.world import RunWorld

log = logging.getLogger(__name__)


def build_resolver(run) -> ElementalResolver:
    """The run's `ElementalResolver`, wired to its ledger's element books."""
    registry = get_registry(run.content)
    # The registry is cached per `Content`, which is a process-wide
    # singleton: a previous run's buffs must not leak into this one.
    registry.clear_modifiers()

    profiles, notes = resolve(run.content.enemies, kind="enemy")
    boss_profiles, boss_notes = resolve(run.content.bosses, kind="boss")
    profiles.update(boss_profiles)
    log_notes(notes + boss_notes)

    overridden = sum(1 for p in profiles.values() if not p.is_default)
    if overridden:
        log.info("elemental profiles: %d of %d types carry overrides",
                 overridden, len(profiles))

    tracking = getattr(run.ledger, "elements", None)
    return ElementalResolver(registry, profiles=profiles, tracking=tracking,
                             world=RunWorld(run), reaction_runner=reactions.run)
