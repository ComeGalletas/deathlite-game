"""Run-time modifiers on top of a baked config (design §2.4).

`effective = (base + flat) x mult`, per leaf path (`"chain.jumps"`,
`"hit.damage.frac"`). One `Modifiers` per element or reaction; a change
raises its `dirty` flag and the registry rebakes that config once, on the
next read -- never per hit.

Modifiers are global per element (design R27): a buff to Fire reaches every
Fire hit on every weapon. Each modifier names a `source` so the thing that
added it (a blessing, a dev-menu edit) can take it back.
"""
from __future__ import annotations

from typing import Any


class Modifiers:
    def __init__(self, paths) -> None:
        self._paths = frozenset(paths)
        self._flat: dict[str, float] = {}
        self._mult: dict[str, float] = {}
        # source -> [(path, flat, mult)], so removal restores exactly.
        self._sources: dict[str, list[tuple[str, float, float]]] = {}
        self.dirty = False

    @property
    def paths(self) -> frozenset:
        return self._paths

    def __bool__(self) -> bool:
        return bool(self._sources)

    def add(self, path: str, *, source: str, flat: float = 0.0,
            mult: float = 1.0) -> None:
        if path not in self._paths:
            raise KeyError(f"no such leaf: {path!r}")
        if not source:
            raise ValueError("a modifier needs a source")
        self._flat[path] = self._flat.get(path, 0.0) + float(flat)
        self._mult[path] = self._mult.get(path, 1.0) * float(mult)
        self._sources.setdefault(source, []).append((path, float(flat), float(mult)))
        self.dirty = True

    def remove_source(self, source: str) -> bool:
        """Take back everything `source` added. Returns whether it had any."""
        entries = self._sources.pop(source, None)
        if not entries:
            return False
        for path, flat, mult in entries:
            self._flat[path] -= flat
            if mult != 0.0:
                self._mult[path] /= mult
        self.dirty = True
        return True

    def clear(self) -> None:
        if self._sources:
            self.dirty = True
        self._flat.clear()
        self._mult.clear()
        self._sources.clear()

    def adjust(self, path: str, value: Any) -> Any:
        """`Section.bake`'s `adjust` callback."""
        return (value + self._flat.get(path, 0.0)) * self._mult.get(path, 1.0)

    def describe(self) -> dict[str, tuple[float, float]]:
        """`{path: (flat, mult)}` for every touched leaf (the dev inspector)."""
        return {p: (self._flat.get(p, 0.0), self._mult.get(p, 1.0))
                for p in sorted(set(self._flat) | set(self._mult))
                if self._flat.get(p, 0.0) != 0.0 or self._mult.get(p, 1.0) != 1.0}
