"""Generic object pool for high-frequency short-lived objects (spec 6.2):
projectiles, particles, damage numbers, XP gems.

Objects are never destroyed; they are marked inactive and reused. Callers:
  * `acquire()` -> a recycled or new object with `active = True`
  * set it up
  * when done, set `obj.active = False`; `sweep()` returns it to the free list

The pool is capped (spec 6.3): once `max_size` live objects exist, `acquire()`
returns None and the caller degrades gracefully instead of the game crashing.
"""
from __future__ import annotations

from typing import Callable, Generic, Iterator, TypeVar

T = TypeVar("T")


class Pool(Generic[T]):
    def __init__(self, factory: Callable[[], T], max_size: int,
                 prefill: int = 0) -> None:
        self._factory = factory
        self.max_size = max_size
        self._active: list[T] = []
        self._free: list[T] = [factory() for _ in range(prefill)]

    def __len__(self) -> int:
        return len(self._active)

    def __iter__(self) -> Iterator[T]:
        return iter(self._active)

    @property
    def active(self) -> list[T]:
        return self._active

    def acquire(self) -> T | None:
        if len(self._active) >= self.max_size:
            return None  # graceful cap
        obj = self._free.pop() if self._free else self._factory()
        obj.active = True  # type: ignore[attr-defined]
        self._active.append(obj)
        return obj

    def sweep(self) -> int:
        """Move every object whose `.active` went False back to the free list.
        Returns how many were reclaimed."""
        still: list[T] = []
        reclaimed = 0
        for obj in self._active:
            if getattr(obj, "active", False):
                still.append(obj)
            else:
                self._free.append(obj)
                reclaimed += 1
        self._active = still
        return reclaimed

    def clear(self) -> None:
        for obj in self._active:
            obj.active = False  # type: ignore[attr-defined]
        self._free.extend(self._active)
        self._active.clear()
