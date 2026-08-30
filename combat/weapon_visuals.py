"""Weapon presentation, split out of the gameplay data.

`data/weapons.json` holds only mechanics + identity; the *look* of a weapon --
projectile colour, the `projectiles/` draw family, and any per-weapon effect
tuning -- lives in `data/weapon_visuals.json` and is resolved here, on the
render / spawn side. The logic in `combat/weapons.py` never reads it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

_DEFAULT_COLOR = (255, 255, 255)


@dataclass(frozen=True)
class WeaponVisual:
    color: tuple[int, int, int] = _DEFAULT_COLOR
    style: str = ""                       # a `projectiles/` @style family, or ""
    fx: dict = field(default_factory=dict)  # free-form per-weapon effect tuning

    @classmethod
    def from_dict(cls, d: dict | None) -> "WeaponVisual":
        d = d or {}
        c = d.get("color", _DEFAULT_COLOR)
        return cls(color=(int(c[0]), int(c[1]), int(c[2])),
                   style=str(d.get("style", "")),
                   fx=dict(d.get("fx", {})))
