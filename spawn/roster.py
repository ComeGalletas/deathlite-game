"""What a company may actually be drawn from, resolved once before a run.

Spawn master G2a. `spawn_tables.json` *declares* the six groups; this decides
what is usable, by reading each member's block in `enemies.json` and comparing
it with the half the table filed it under. The result is a `Roster`, and the
draws read it instead of the raw table.

**Why this is not load-time validation** (owner, 2026-09-17). G2 shipped a
check that refused to boot when a group's rank contradicted `enemies.json`.
The owner asked for the opposite failure mode: "a simple function to read the
list of enemies in a certain group ... in case the data is corrupted or simply
inadequate skip whichever enemy or group contains it". So a bad table costs
the offending enemy or group, never the run.

Resolution happens **once, when the spawn master is built** -- the owner's
call, since nothing edits the data mid-run -- and every decision it makes is
returned as a note for the caller to log. Nothing here is silent.

**Nothing spawnable is thrown away.** This is the rule that is easy to get
backwards. A member whose rank does not match its half is not discarded if it
could still be spawned as an ordinary body:

* a **non-elite filed under `elites`** cannot fill an elite slot -- an elite
  company is *guaranteed* elites, and letting a plain body count as one would
  quietly break that -- so it is **demoted into `commons`** and still spawns;
* an **`is_elite` enemy filed under `commons`** is a perfectly good body, so
  it **stays and spawns as a common**. It counts toward the common total
  rather than the elite count. Its own flag still earns it the gold ring, the
  doubled gold and the item roll when it dies, because those are properties
  of the body and not of the slot it was drawn from.

Only what cannot be used at all is dropped: an id with no block in
`enemies.json`, a weight that is not a positive number, a malformed count
span. A group whose `commons` ends up empty is **skipped entirely** and is
never offered to the draw; a group that loses only its elite half survives as
a common-only group.

`is_elite` is the authority, and the `"elite"` string some enemies carry in
`tags` is never consulted -- one source of truth, the same one the gold ring,
the item drop and the blessing bonus switch on.
"""
from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["Roster", "ResolvedGroup", "resolve_groups"]


@dataclass(frozen=True)
class ResolvedGroup:
    """One group, reduced to what can actually be spawned."""
    name: str
    commons: dict                      # id -> weight
    common_range: tuple               # (min, max)
    elites: dict = field(default_factory=dict)
    elite_range: tuple | None = None
    elite_step: int = 1

    @property
    def has_elites(self) -> bool:
        return bool(self.elites) and self.elite_range is not None

    def elite_count(self, steps: int) -> int:
        """How many elites a company of this group carries after `steps` of
        the ladder. Deterministic -- the minimum climbs by `elite_step` each
        step and is capped by the group's ceiling, so *which* elites appear
        is the only random part."""
        if not self.has_elites:
            return 0
        lo, hi = self.elite_range
        return min(lo + self.elite_step * max(0, int(steps)), hi)


class Roster:
    """The usable groups, and the notes explaining anything left out."""

    def __init__(self, groups: dict, notes: list) -> None:
        self.groups: dict[str, ResolvedGroup] = groups
        self.notes: list[str] = notes

    def __bool__(self) -> bool:
        return bool(self.groups)

    def get(self, name: str) -> ResolvedGroup | None:
        return self.groups.get(name)

    def names(self, elite: bool | None = None) -> list[str]:
        """The usable group names, sorted so a draw off them is a function of
        the seed. `elite=True` gives the groups that can field elites and
        `False` the ones that cannot -- the two pools the master draws from
        separately, which is what keeps an elite company unpickable while its
        gate is shut."""
        names = sorted(self.groups)
        if elite is None:
            return names
        return [n for n in names if self.groups[n].has_elites is elite]


def _weights(table, enemies, tag: str, notes: list) -> dict:
    """The members of one half that exist and carry a usable weight."""
    if not isinstance(table, dict):
        if table is not None:
            notes.append(f"{tag}: ignored, not a table of id -> weight")
        return {}
    out = {}
    for eid, w in table.items():
        if eid not in enemies:
            notes.append(f"{tag}: skipping {eid!r}, no such enemy")
            continue
        if not isinstance(w, (int, float)) or isinstance(w, bool) or w <= 0:
            notes.append(f"{tag}: skipping {eid!r}, weight {w!r} is not > 0")
            continue
        out[eid] = float(w)
    return out


def _span(value, tag: str, notes: list) -> tuple | None:
    if not (isinstance(value, (list, tuple)) and len(value) == 2):
        notes.append(f"{tag}: {value!r} is not a [min, max] pair")
        return None
    lo, hi = value
    if not all(isinstance(v, int) and not isinstance(v, bool) and v >= 1
               for v in (lo, hi)):
        notes.append(f"{tag}: {value!r} must be whole numbers >= 1")
        return None
    if lo > hi:
        notes.append(f"{tag}: {value!r} has min above max")
        return None
    return (int(lo), int(hi))


def _resolve_one(name: str, g, enemies, elites: set, notes: list) -> ResolvedGroup | None:
    tag = f"group {name!r}"
    if not isinstance(g, dict):
        notes.append(f"{tag}: skipped, not an object")
        return None

    commons = _weights(g.get("commons"), enemies, f"{tag} commons", notes)
    declared_elites = _weights(g.get("elites"), enemies, f"{tag} elites", notes)

    # The rank pass. A body filed among the elites that is not one cannot
    # fill an elite slot, but it can still fight: demote it rather than lose
    # it. A real elite filed among the commons simply spawns as a common.
    kept_elites = {}
    for eid, w in declared_elites.items():
        if eid in elites:
            kept_elites[eid] = w
        elif eid in commons:
            notes.append(f"{tag}: {eid!r} is not `is_elite`; already a common, "
                         f"so its elite listing is ignored")
        else:
            commons[eid] = w
            notes.append(f"{tag}: {eid!r} is not `is_elite`, so it was moved "
                         f"from `elites` to `commons` rather than dropped")
    for eid in commons:
        if eid in elites and eid not in declared_elites:
            notes.append(f"{tag}: {eid!r} is `is_elite` but listed in `commons`, "
                         f"so it spawns as a common and does not count as one")

    span = _span(g.get("common_range"), f"{tag} `common_range`", notes)
    if span is None:
        notes.append(f"{tag}: skipped, it has no usable `common_range`")
        return None
    if not commons:
        notes.append(f"{tag}: skipped, nothing left to draw a common from")
        return None

    if not kept_elites:
        if g.get("elites"):
            notes.append(f"{tag}: kept as a common-only group, its elite half "
                         f"has nothing usable left")
        return ResolvedGroup(name, commons, span)

    erange = _span(g.get("elite_range"), f"{tag} `elite_range`", notes)
    step = g.get("elite_step", 1)
    if not (isinstance(step, int) and not isinstance(step, bool) and step >= 1):
        notes.append(f"{tag}: `elite_step` {step!r} must be a whole number >= 1")
        erange = None
    if erange is None:
        notes.append(f"{tag}: kept as a common-only group, its elite ladder "
                     f"does not hold up")
        return ResolvedGroup(name, commons, span)
    return ResolvedGroup(name, commons, span, kept_elites, erange, int(step))


def resolve_groups(groups: dict, enemies) -> Roster:
    """Read the declared `groups` against `enemies` and return what is
    usable, plus a note for every decision made.

    `enemies` is the loaded `enemies.json` mapping -- the definitions, not
    just the ids, because the rank pass needs each member's `is_elite`.
    """
    elites = {eid for eid, e in enemies.items()
              if isinstance(e, dict) and e.get("is_elite")}
    notes: list[str] = []
    out: dict[str, ResolvedGroup] = {}
    if not isinstance(groups, dict) or not groups:
        notes.append("groups: nothing declared, so no company can be drawn")
        return Roster(out, notes)
    for name, g in groups.items():
        if name.startswith("_"):          # a comment, the convention data uses
            continue
        resolved = _resolve_one(name, g, enemies, elites, notes)
        if resolved is not None:
            out[name] = resolved
    if not out:
        notes.append("groups: no group is usable, so no enemies will spawn")
    return Roster(out, notes)
