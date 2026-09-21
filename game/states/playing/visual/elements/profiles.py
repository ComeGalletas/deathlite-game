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
    rig_scale: float


@dataclass(frozen=True)
class Budget:
    per_frame: int
    per_element: int


class ReactionBurst:
    """The authored one-shot a reaction plays, and how long it plays for.

    Not an `Animator`: a reaction burst cannot ride a shared clock the way
    an aura does. Two Overloads half a second apart are two separate
    events, and each has to start at its own first frame -- so the frame is
    taken by index off the individual flash's age (`frame_at`).
    """
    __slots__ = ("key", "rig", "seconds", "size", "_assets", "_frames",
                 "_natural")

    def __init__(self, key: str, spec: dict, assets) -> None:
        self.key = key
        self.rig = str(spec["rig"])
        self.seconds = float(spec["seconds"])
        self.size = float(spec["size"])
        self._assets = assets
        self._frames = None
        self._natural = None

    @property
    def natural(self):
        """The art's own frame size, so a burst keeps its aspect when it is
        scaled to how far the reaction actually reached."""
        if self._natural is None:
            frame = self._assets.frame(self.rig, "loop", 0)
            self._natural = frame.get_size() if frame else (0, 0)
        return self._natural if self._natural[0] else None

    @property
    def frames(self) -> int:
        if self._frames is None:
            self._frames = self._assets.frame_count(self.rig, "loop")
        return self._frames

    def frame_at(self, progress: float, size=None):
        """The frame `progress` (0..1) of the way through the burst.

        Clamped rather than wrapped: this plays once and then the flash is
        swept, so overshooting by a frame at the end should hold the last
        frame, not snap back to the first.
        """
        total = self.frames
        if total <= 0:
            return None
        index = min(total - 1, max(0, int(progress * total)))
        return self._assets.frame(self.rig, "loop", index, size=size)


class ElementVisualProfile:
    """Everything the layers need to draw one element."""
    __slots__ = ("element", "colour", "marker", "aura_rig",
                 "particles", "_aura_anim", "_natural")

    def __init__(self, element: ElementId, spec: dict, assets) -> None:
        self.element = element
        self.colour = tuple(int(c) for c in spec["colour"])
        self.marker = str(spec["marker"])
        self.aura_rig = spec.get("aura_rig") or None
        p = spec["particles"]
        self.particles = Particles(float(p["rate"]), float(p["speed"]),
                                   float(p["life"]), float(p["radius"]))
        self._aura_anim = Animator(assets, self.aura_rig, "loop") if self.aura_rig else None
        self._natural = None

    @property
    def key(self) -> str:
        return self.element.key

    def update(self, dt: float) -> None:
        if self._aura_anim is not None:
            self._aura_anim.update(dt)

    def aura_frame(self, size=None):
        """The authored aura frame, or None when the element has no rig and
        the procedural ring carries it instead."""
        return self._aura_anim.frame(size=size) if self._aura_anim else None

    def aura_size(self, width: float):
        """`width` px across, with the art's own aspect kept.

        These frames are not square -- the cut trimmed each strip to its own
        content -- and forcing them into a square box would stretch a ring
        into an ellipse. Cached on the profile because the natural size is a
        property of the sheet and never changes.
        """
        if self._natural is None:
            frame = self.aura_frame()
            if frame is None:
                return None
            self._natural = frame.get_size()
        nw, nh = self._natural
        w = max(4, int(width))
        return (w, max(4, int(w * nh / nw)))

    def __repr__(self) -> str:
        return f"<ElementVisualProfile {self.key}>"


class VisualSet:
    """The four profiles plus the shared styling, the status rigs, the
    reaction bursts and the budget."""

    def __init__(self, data: dict, assets) -> None:
        self.aura = AuraStyle(**{k: v for k, v in data["aura"].items()
                                 if not k.startswith("_")})
        budget = {k: v for k, v in data["budget"].items() if not k.startswith("_")}
        self.budget = Budget(int(budget["per_frame"]), int(budget["per_element"]))
        self._by_id = {
            element: ElementVisualProfile(element, data["elements"][element.key],
                                          assets)
            for element in ELEMENTS}
        # Status art is keyed by status id, not by element: `burn` is shared
        # with the weapon blessings' own burn and `chill` has no art at all,
        # so neither is a property of the element that applied it.
        self._statuses = {
            key: Animator(assets, rig, "loop")
            for key, rig in data["statuses"].items() if not key.startswith("_")}
        self._reactions = {
            key: ReactionBurst(key, spec, assets)
            for key, spec in data["reactions"].items() if not key.startswith("_")}
        self._assets = assets
        self._naturals: dict[str, tuple | None] = {}

    def __getitem__(self, element: ElementId) -> ElementVisualProfile:
        return self._by_id[element]

    def get(self, element: ElementId):
        return self._by_id.get(element)

    def tint(self, element: ElementId) -> tuple[int, int, int]:
        profile = self._by_id.get(element)
        return profile.colour if profile else (255, 255, 255)

    def status_frame(self, status: str, size=None):
        """The authored frame for a status, or None where it has no art.

        `index` is not taken here: `burn` loops on the shared clock like an
        aura, and `freeze` -- the one status whose art has a beginning and
        an end -- is drawn by index off the body's own timer instead, since
        every enemy freezes on its own schedule.
        """
        anim = self._statuses.get(status)
        return anim.frame(size=size) if anim is not None else None

    def status_rig(self, status: str):
        """The rig name behind a status, for the callers that index it
        themselves rather than riding the shared clock."""
        anim = self._statuses.get(status)
        return anim.rig if anim is not None else None

    def status_frame_at(self, status: str, progress: float, size=None):
        """A status's art at `progress` (0..1) of its strip.

        Freeze is the one that needs this. Its art has a beginning and an
        end -- a block forms and shatters -- and every enemy freezes on its
        own schedule, so it cannot ride the shared clock the way a looping
        burn does.
        """
        rig = self.status_rig(status)
        if rig is None:
            return None
        total = self._assets.frame_count(rig, "loop")
        if total <= 0:
            return None
        index = min(total - 1, max(0, int(progress * total)))
        return self._assets.frame(rig, "loop", index, size=size)

    def status_natural(self, status: str):
        """A status frame's own size, for callers keeping its aspect."""
        rig = self.status_rig(status)
        if rig is None:
            return None
        if rig not in self._naturals:
            frame = self._assets.frame(rig, "loop", 0)
            self._naturals[rig] = frame.get_size() if frame else None
        return self._naturals[rig]

    def reaction(self, key: str):
        """The authored burst for a reaction, or None where none is wired
        and the procedural flash carries it instead."""
        return self._reactions.get(key)

    def update(self, dt: float) -> None:
        for profile in self._by_id.values():
            profile.update(dt)
        for anim in self._statuses.values():
            anim.update(dt)

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
