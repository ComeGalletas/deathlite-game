"""The element registry (design §2.5): one place that holds, per run, the
four element objects, their effective configs, the global block and the
reaction lookup table.

* `config(element)` -- the baked config of an element with its modifiers
  applied; recomputed only when a modifier changed (`Modifiers.dirty`).
* `reaction(aura, incoming)` -- the `ReactionVariant` for an enemy holding
  `aura` hit by `incoming`, or `None` (same element, no aura, no element).
  The table is a 5x5 tuple indexed by `ElementId`, O(1), with both cells of
  a pair pointing at the same reaction id but their own baked variant.
* `reaction_config(reaction, trigger)` -- one variant, modifiers applied.

`get_registry(content)` caches one registry per `Content` object, like the
blessing catalog; a run reads it through `run.content`.
"""
from __future__ import annotations

from collections import namedtuple

from combat.elements import config as schema
from combat.elements.base import Element
from combat.elements.ids import ELEMENTS, REACTIONS, ElementId, ReactionId
from combat.elements.modifiers import Modifiers

ReactionVariant = namedtuple("ReactionVariant", "reaction aura incoming")
ReactionVariant.__doc__ = """One cell of the table: which reaction fires when
an enemy carrying `aura` is hit by `incoming`. Its config comes from
`ElementRegistry.reaction_config(reaction, incoming)`."""


class ElementRegistry:
    def __init__(self, elements_data: dict, reactions_data: dict,
                 element_classes: dict[ElementId, type] | None = None) -> None:
        """`elements_data` / `reactions_data` are the validated dicts
        `Content` holds (`config.check_elements` / `check_reactions`).
        `element_classes` maps ids to `Element` subclasses; an id it lacks
        gets the placeholder base `Element` (M1)."""
        self.global_cfg = schema.GLOBAL.bake(elements_data["global"])
        if element_classes is None:
            # Imported here, not at module scope: an element imports the
            # resolver, which must stay importable without the registry.
            from combat.elements.catalog import ELEMENT_CLASSES
            element_classes = ELEMENT_CLASSES
        classes = element_classes
        self._elements: tuple = tuple(
            None if eid == ElementId.NONE else classes.get(eid, Element)(eid)
            for eid in ElementId)

        self._base: dict[ElementId, dict] = {
            eid: elements_data["elements"][eid.key] for eid in ELEMENTS}
        self._mods: dict[ElementId, Modifiers] = {
            eid: Modifiers(schema.ELEMENT_SCHEMAS[eid].paths()) for eid in ELEMENTS}
        self._cache: dict[ElementId, object] = {}

        self._reaction_base: dict[tuple[ReactionId, ElementId], dict] = {}
        self._reaction_mods: dict[ReactionId, Modifiers] = {
            rid: Modifiers(schema.REACTION_SCHEMAS[rid].paths()) for rid in REACTIONS}
        self._reaction_cache: dict[tuple[ReactionId, ElementId], object] = {}
        table = [[None] * len(ElementId) for _ in ElementId]
        for rid in REACTIONS:
            entry = reactions_data["reactions"][rid.key]
            a, b = schema.REACTION_PAIRS[rid]
            for aura, incoming in ((a, b), (b, a)):
                self._reaction_base[(rid, incoming)] = schema.variant_data(entry, incoming)
                table[aura][incoming] = ReactionVariant(rid, aura, incoming)
        self._table = tuple(tuple(row) for row in table)

    # --- elements -----------------------------------------------------------
    def element(self, element: ElementId) -> Element:
        e = self._elements[element]
        if e is None:
            raise KeyError("ElementId.NONE has no element")
        return e

    @property
    def elements(self) -> tuple:
        """The four elements in id order."""
        return tuple(self._elements[eid] for eid in ELEMENTS)

    def modifiers(self, element: ElementId) -> Modifiers:
        return self._mods[element]

    def config(self, element: ElementId, profile=None):
        """The effective config record: the data, then the run-time
        modifiers, then the target's enemy profile (design §3.5, in that
        order). Rebaked only when a modifier changes, and cached per
        profile -- there are a handful of distinct profiles at most, so the
        per-hit cost is one dictionary lookup and never a merge."""
        mods = self._mods[element]
        if mods.dirty:
            self._cache.clear()
            mods.dirty = False
        key = (element, profile if profile is not None and
               profile.touches(element.key) else None)
        cached = self._cache.get(key)
        if cached is None:
            cached = schema.ELEMENT_SCHEMAS[element].bake(
                self._base[element], self._adjuster(mods, key[1], element.key))
            self._cache[key] = cached
        return cached

    @staticmethod
    def _adjuster(mods: Modifiers, profile, config_key: str):
        """One `(path, value) -> value` callback composing the modifier layer
        with the profile's overrides, or `None` when neither touches this
        config (so baking hands back the data untouched)."""
        mod_adjust = mods.adjust if mods else None
        profile_adjust = profile.adjust_for(config_key) if profile is not None else None
        if profile_adjust is None:
            return mod_adjust
        if mod_adjust is None:
            return profile_adjust
        return lambda path, value: profile_adjust(path, mod_adjust(path, value))

    # --- reactions ------------------------------------------------------------
    def reaction(self, aura: ElementId, incoming: ElementId) -> ReactionVariant | None:
        return self._table[aura][incoming]

    def reaction_modifiers(self, reaction: ReactionId) -> Modifiers:
        return self._reaction_mods[reaction]

    def reaction_config(self, reaction: ReactionId, trigger: ElementId, profile=None):
        """The baked variant of `reaction` for the hit element `trigger`,
        with the target's profile applied (§3.5)."""
        if (reaction, trigger) not in self._reaction_base:
            raise KeyError(f"{reaction.key} is not triggered by {trigger.key}")
        mods = self._reaction_mods[reaction]
        if mods.dirty:
            self._reaction_cache.clear()
            mods.dirty = False
        key = (reaction, trigger,
               profile if profile is not None and profile.touches(reaction.key) else None)
        cached = self._reaction_cache.get(key)
        if cached is None:
            cached = schema.REACTION_SCHEMAS[reaction].bake(
                self._reaction_base[(reaction, trigger)],
                self._adjuster(mods, key[2], reaction.key))
            self._reaction_cache[key] = cached
        return cached

    def clear_modifiers(self) -> None:
        """Run end / dev reset: every element and reaction back to its data."""
        for m in (*self._mods.values(), *self._reaction_mods.values()):
            m.clear()
        self._cache.clear()
        self._reaction_cache.clear()


_REGISTRIES: dict[int, ElementRegistry] = {}


def get_registry(content, element_classes: dict | None = None) -> ElementRegistry:
    """One registry per `Content` object. `element_classes` is for tests;
    left out, the real four are used, so a registry can never come back
    holding placeholders just because a test asked for one first."""
    key = id(content)
    if key not in _REGISTRIES:
        _REGISTRIES[key] = ElementRegistry(content.elements, content.reactions,
                                           element_classes)
    return _REGISTRIES[key]
