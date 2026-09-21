"""The tiny schema language the element and reaction configs are declared in.

A schema is a tree of `Section`s whose leaves are `Field`s. It does three
jobs, all at load time, none at hit time:

* **validate** a JSON block -- every key present, no unknown key, every
  value of the right type and inside its range (design §2.3);
* **bake** the validated block into an immutable record -- a `namedtuple`
  per section, so gameplay code reads `cfg.chain.jumps` with no dictionary
  lookups and cannot mutate it (§2.3, §9);
* **name** every leaf by a dotted path (`"chain.jumps"`), which is what the
  run-time modifiers (§2.4) and the per-enemy profile overrides (§3.5)
  address.

A damage value is its own field kind: `{"frac": 0.25}` scales with the hit
that triggered the effect, `{"flat": 12}` is a flat number (the owner's
decision of 2026-09-21, design open item 11). It bakes to a `DamageSpec`.

Keys beginning with `_` are comments and are ignored, as everywhere in
`data/`.
"""
from __future__ import annotations

from collections import namedtuple
from typing import Any, Callable


class ElementDataError(ValueError):
    """Bad element / reaction data. `game.content` turns it into a
    `ContentError` at boot."""


# --- leaves ------------------------------------------------------------------

class Field:
    """One numeric or boolean leaf. `lo` / `hi` are inclusive bounds; with
    `lo_open` the lower bound is exclusive (a duration must be > 0)."""
    __slots__ = ("kind", "lo", "hi", "lo_open")

    def __init__(self, kind: str, lo=None, hi=None, lo_open: bool = False) -> None:
        self.kind = kind
        self.lo = lo
        self.hi = hi
        self.lo_open = lo_open

    def check(self, path: str, value: Any):
        """Validate and coerce `value`; raise `ElementDataError` naming `path`."""
        if self.kind == "bool":
            if not isinstance(value, bool):
                raise ElementDataError(f"{path}: expected true/false, got {value!r}")
            return value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ElementDataError(f"{path}: expected a number, got {value!r}")
        if self.kind == "int":
            if float(value) != int(value):
                raise ElementDataError(f"{path}: expected a whole number, got {value!r}")
            value = int(value)
        else:
            value = float(value)
        if self.lo is not None and (value < self.lo or (self.lo_open and value <= self.lo)):
            bound = f"> {self.lo}" if self.lo_open else f">= {self.lo}"
            raise ElementDataError(f"{path}: {value} must be {bound}")
        if self.hi is not None and value > self.hi:
            raise ElementDataError(f"{path}: {value} must be <= {self.hi}")
        return value

    def clamp(self, value):
        """A modified value pulled back inside the field's bounds, and back to
        the field's type (a modifier on an int leaf yields an int)."""
        if self.kind == "bool":
            return bool(value)
        if self.lo is not None:
            if self.lo_open and value <= self.lo:
                value = self.lo + (1e-6 if self.kind == "float" else 1)
            elif value < self.lo:
                value = self.lo
        if self.hi is not None and value > self.hi:
            value = self.hi
        return int(round(value)) if self.kind == "int" else float(value)


def f(lo=None, hi=None, *, lo_open: bool = False) -> Field:
    return Field("float", lo, hi, lo_open)


def i(lo=None, hi=None) -> Field:
    return Field("int", lo, hi)


def b() -> Field:
    return Field("bool")


DamageSpec = namedtuple("DamageSpec", "frac flat")
DamageSpec.__doc__ = """A damage value: `frac` of the triggering hit, or `flat`."""


def _resolve(self: DamageSpec, hit_damage: float) -> float:
    """The damage this spec deals for a hit worth `hit_damage`."""
    if self.flat is not None:
        return float(self.flat)
    return float(self.frac) * float(hit_damage)


DamageSpec.resolve = _resolve

_DAMAGE_KEYS = ("frac", "flat")


class DamageField(Field):
    """`{"frac": x}` or `{"flat": y}`, exactly one, both >= 0. Its leaf
    paths are `<path>.frac` and `<path>.flat` so a modifier can target
    whichever the data uses."""
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("damage", 0.0, None, False)

    def check(self, path: str, value: Any):
        if not isinstance(value, dict):
            raise ElementDataError(
                f"{path}: expected {{\"frac\": x}} or {{\"flat\": y}}, got {value!r}")
        keys = [k for k in value if not k.startswith("_")]
        if len(keys) != 1 or keys[0] not in _DAMAGE_KEYS:
            raise ElementDataError(
                f"{path}: needs exactly one of {_DAMAGE_KEYS}, got {sorted(keys)}")
        key = keys[0]
        num = value[key]
        if isinstance(num, bool) or not isinstance(num, (int, float)) or num < 0.0:
            raise ElementDataError(f"{path}.{key}: expected a number >= 0, got {num!r}")
        return {key: float(num)}

    def clamp(self, value):
        return max(0.0, float(value))


def dmg() -> DamageField:
    return DamageField()


# --- sections ----------------------------------------------------------------

Adjust = Callable[[str, Any], Any]      # (leaf path, base value) -> value


class Section:
    """A named group of fields and sub-sections; bakes to a namedtuple."""

    def __init__(self, name: str, fields: dict[str, "Field | Section"]) -> None:
        self.name = name
        self.fields = dict(fields)
        self.record = namedtuple(name, list(self.fields))

    # -- validation --
    def validate(self, path: str, data: Any, *, partial: bool = False) -> dict:
        """Return a coerced copy of `data`. `partial` allows missing keys (a
        per-trigger override, a profile override) but never unknown ones."""
        if not isinstance(data, dict):
            raise ElementDataError(f"{path}: expected an object, got {data!r}")
        out: dict = {}
        for key, value in data.items():
            if key.startswith("_"):
                continue
            node = self.fields.get(key)
            if node is None:
                raise ElementDataError(
                    f"{path}.{key}: unknown key (allowed: {sorted(self.fields)})")
            sub = f"{path}.{key}"
            if isinstance(node, Section):
                out[key] = node.validate(sub, value, partial=partial)
            else:
                out[key] = node.check(sub, value)
        if not partial:
            missing = [k for k in self.fields if k not in out]
            if missing:
                raise ElementDataError(f"{path}: missing {missing}")
        return out

    # -- baking --
    def bake(self, data: dict, adjust: Adjust | None = None, path: str = ""):
        """`data` must already be validated. `adjust(leaf_path, value)`, when
        given, is applied to every numeric leaf (the modifier layer) and the
        result is clamped back into the leaf's range."""
        values = []
        for key, node in self.fields.items():
            sub = f"{path}.{key}" if path else key
            value = data[key]
            if isinstance(node, Section):
                values.append(node.bake(value, adjust, sub))
            elif isinstance(node, DamageField):
                spec = {k: None for k in _DAMAGE_KEYS}
                for k, v in value.items():
                    spec[k] = node.clamp(adjust(f"{sub}.{k}", v)) if adjust else v
                values.append(DamageSpec(**spec))
            elif adjust is not None and node.kind != "bool":
                values.append(node.clamp(adjust(sub, value)))
            else:
                values.append(value)
        return self.record(*values)

    # -- introspection --
    def paths(self, prefix: str = "") -> tuple[str, ...]:
        """Every leaf path, dotted. A damage leaf contributes both
        `.frac` and `.flat`."""
        out: list[str] = []
        for key, node in self.fields.items():
            sub = f"{prefix}.{key}" if prefix else key
            if isinstance(node, Section):
                out.extend(node.paths(sub))
            elif isinstance(node, DamageField):
                out.extend(f"{sub}.{k}" for k in _DAMAGE_KEYS)
            else:
                out.append(sub)
        return tuple(out)


def deep_merge(base: dict, override: dict) -> dict:
    """`base` with `override` laid over it, recursing into sub-objects. Both
    are validated dicts; neither is mutated."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict) \
                and not _is_damage(value):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _is_damage(value: dict) -> bool:
    return len(value) == 1 and next(iter(value)) in _DAMAGE_KEYS
