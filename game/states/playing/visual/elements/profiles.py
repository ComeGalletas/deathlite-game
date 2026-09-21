"""One visual profile per element (design §8.1).

Colour, marker shape, particle preset, and the authored rigs an element has
if any. Loaded once per `Content` and baked, the way every other piece of
presentation data in this project is.

Two things here are deliberately shared rather than per-enemy:

* **one animation clock per element**, not one per aura. A hundred burning
  enemies are a hundred blits of the same frame, not a hundred `Animator`s
  ticking in parallel. Every aura of an element is therefore in phase with
  every other, which is a uniformity worth the saving at this crowd size.
* **the particle budget**, because the point of a budget is that everything
  draws from the same one.
"""
from __future__ import annotations

from dataclasses import dataclass

from combat.elements.ids import ELEMENTS, ElementId
from systems.animation import Animator


@dataclass(frozen=True)
class Particles:
    rate: float          # particles a second, per aura
    speed: float
    life: float
    radius: float


@dataclass(frozen=True)
class AuraStyle:
    ring_pad: float
    ring_width: int
    alpha: int
    locked_alpha: int
    marker_size: int
    marker_gap: int


@dataclass(frozen=True)
class Budget:
    per_frame: int
    per_element: int


class ElementVisualProfile:
    """Everything the layers need to draw one element."""
    __slots__ = ("element", "colour", "marker", "aura_rig", "status_rig",
                 "particles", "_aura_anim", "_status_anim")

    def __init__(self, element: ElementId, spec: dict, assets) -> None:
        self.element = element
        self.colour = tuple(int(c) for c in spec["colour"])
        self.marker = str(spec["marker"])
        self.aura_rig = spec.get("aura_rig") or None
        self.status_rig = spec.get("status_rig") or None
        p = spec["particles"]
        self.particles = Particles(float(p["rate"]), float(p["speed"]),
                                   float(p["life"]), float(p["radius"]))
        self._aura_anim = Animator(assets, self.aura_rig, "loop") if self.aura_rig else None
        self._status_anim = Animator(assets, self.status_rig, "loop") if self.status_rig else None

    @property
    def key(self) -> str:
        return self.element.key

    def update(self, dt: float) -> None:
        for anim in (self._aura_anim, self._status_anim):
            if anim is not None:
                anim.update(dt)

    def aura_frame(self, size=None):
        """The authored aura frame, or None when the element has no rig and
        the procedural ring carries it instead."""
        return self._aura_anim.frame(size=size) if self._aura_anim else None

    def status_frame(self, size=None):
        return self._status_anim.frame(size=size) if self._status_anim else None

    def __repr__(self) -> str:
        return f"<ElementVisualProfile {self.key}>"


class VisualSet:
    """The four profiles plus the shared styling and budget."""

    def __init__(self, data: dict, assets) -> None:
        self.aura = AuraStyle(**{k: v for k, v in data["aura"].items()
                                 if not k.startswith("_")})
        budget = {k: v for k, v in data["budget"].items() if not k.startswith("_")}
        self.budget = Budget(int(budget["per_frame"]), int(budget["per_element"]))
        self._by_id = {
            element: ElementVisualProfile(element, data["elements"][element.key],
                                          assets)
            for element in ELEMENTS}

    def __getitem__(self, element: ElementId) -> ElementVisualProfile:
        return self._by_id[element]

    def get(self, element: ElementId):
        return self._by_id.get(element)

    def tint(self, element: ElementId) -> tuple[int, int, int]:
        profile = self._by_id.get(element)
        return profile.colour if profile else (255, 255, 255)

    def update(self, dt: float) -> None:
        for profile in self._by_id.values():
            profile.update(dt)

    def __iter__(self):
        return iter(self._by_id.values())


_SETS: dict[int, VisualSet] = {}


def get_visuals(content, assets=None) -> VisualSet:
    """One set per `Content`, like the blessing catalog and the element
    registry."""
    key = id(content)
    if key not in _SETS:
        if assets is None:
            from game.assets import get_assets
            assets = get_assets()
        _SETS[key] = VisualSet(content.element_visuals, assets)
    return _SETS[key]
