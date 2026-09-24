"""Hot-reload of the element data in a live run (CMB-009.3, design §10.3).

F9 in a developer run re-reads `data/weapons/elements.json` and
`data/weapons/reactions.json`, validates them exactly as a boot does, and
swaps the new numbers into the run's `ElementRegistry` -- so a tuning pass
needs no restart. Whatever the run itself has done stays: the element
objects, and the modifier layers the run's buffs and blessings wrote, which
now apply on top of the new data.

It is all or nothing. A file that fails validation, or that validates but
cannot bake, leaves the old values in place and says why; the run carries
on with what it had.

What it does not reach: anything built once at run start from those files
and held on to -- a Wind area already on the field keeps the config it was
seeded with until it expires -- and `element_visuals.json`, which is
presentation, not tuning.
"""
from __future__ import annotations

import logging

from combat.elements.registry import ElementRegistry
from game import content as content_mod

log = logging.getLogger(__name__)

ELEMENTS_FILE = "weapons/elements.json"
REACTIONS_FILE = "weapons/reactions.json"


def reload_element_data(run, load=None) -> tuple[bool, str]:
    """Reload the run's element data. Returns `(ok, message)`; on failure
    nothing has changed. `load(name) -> dict` reads one data file (the
    content loader by default; tests hand in their own)."""
    load = load or content_mod._load
    try:
        elements = content_mod._check_elements(load(ELEMENTS_FILE))
        reactions = content_mod._check_reactions(load(REACTIONS_FILE))
        fresh = ElementRegistry(elements, reactions)
    except (content_mod.ContentError, KeyError, TypeError, ValueError) as exc:
        log.warning("element reload refused, keeping the old data: %s", exc)
        return False, f"Element reload failed: {exc}"
    run.elements.registry.adopt(fresh)
    # The run's `Content` holds the same dicts the next registry would be
    # built from; keep it in step so nothing reads the old numbers later.
    run.content.elements = elements
    run.content.reactions = reactions
    log.info("element data reloaded")
    return True, "Element data reloaded"
