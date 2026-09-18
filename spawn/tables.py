"""`data/enemies/spawn_tables.json`: what spawns when, read once and checked.

Spawn master S2. The phase schedule used to be `_PHASES`, a list literal
in `world/spawning.py`; it is data, so it lives with the rest of the data
now, under the project's rule that tuning is never defaulted in code. The
numbers moved verbatim -- `tests/spawn/test_budget.py` replays a scripted
run and checks the enemy sequence is the one the literal produced.

Sections:

    unused      enemies benched from the run: an id here keeps its block,
                its art and its weights, but is filtered out of the phase
                types and the group followers as the tables are read, so the
                director can never roll it. Deliberately *disabled*, not
                deleted -- `spawn_at` / `spawn_group` / the dev menu still
                seat one on request.
    ramp_seconds
                S12: how long the phase schedule takes to walk from its
                first band to its last, on Normal; a difficulty divides it
                by `timeline_pace`. This is the schedule's own clock, not
                the run's -- the boss still keys off `run_duration`.
    company_stagger
                G0b: how long a company takes to materialise, in seconds.
                The positions, the point and the cap are all decided when
                the company is seated; this only spreads *when* each body
                appears. 0 means the whole company on one frame, which is a
                supported setting rather than a degenerate one.
    phases      ramp-fraction bands: `until` (exclusive upper bound),
                `interval` [at ramp start, at ramp end], `pack` [lo, hi],
                `elite` chance per slot, `types` id -> weight
    elites      what an elite slot rolls: `default`, and `rare` at
                `rare_chance` (one `random()` draw, `< chance` -> rare)
    groups      templates for S3: `leader`, `followers` id -> [lo, hi],
                optional `clearance` ("small" | "large") and `prefer` tags
    owners      S3: `cap_exempt`, the spawn owners the live cap does not
                refuse -- scripted spawns the master must always seat (an
                arena's elites). The director is never exempt. S4:
                `never_sleep`, the owners hibernation leaves alone.
    locality    S4: the heading-room dwell, the grace window, the alignment
                threshold, and the heading / grace zone weights
    population  S4: the hibernation tick, the per-frame wake budget, and
                how long a dormant enemy keeps its exact spot
    watchdog    S5: the sample interval and window of the stuck check, the
                on-screen hold, the recycle limit, and the contact margin
    placement   S3: the knobs of `spawn/placement.py` -- point cooldown,
                the distance band around the player (S11: never the
                camera), when a deferred pack relaxes the band, the
                follower ring gap, and the same-floor / preferred-tag
                weights
    difficulty  per-level overrides; a level may carry its own `phases`
                list (same shape) that replaces the shared one. Empty today:
                the four difficulty *factors* stay in `config.DIFFICULTIES`.
    residents   S4: groups seeded into an island on first visit, by room
                kind, and a per-difficulty scale
    pacing      S6: bounds, smoothing (`tau`), dead-band and signal weights
                of the pressure multiplier, the rate `window`, the
                `lull_seconds` to a full lull, and `damage_rate_full`, the
                HP fraction per second that reads as -1. S9: `base`, the
                standing multiplier on the director's cadence that the
                pacing value and the modifiers then scale (5 today)

Every enemy id named anywhere is checked against `enemies.json` when the
content loads, so a typo fails at boot rather than at minute eight.
"""
from __future__ import annotations

from typing import Iterable

__all__ = ["SpawnTables", "TableError"]


class TableError(ValueError):
    """The tables are malformed or name something that does not exist."""


def _check_phases(phases, where: str, enemy_ids, bad: list) -> None:
    if not isinstance(phases, list) or not phases:
        bad.append(f"{where}: `phases` must be a non-empty list")
        return
    last = 0.0
    for i, p in enumerate(phases):
        tag = f"{where}: phase {i}"
        until = p.get("until")
        if not isinstance(until, (int, float)) or until <= last:
            bad.append(f"{tag}: `until` must increase (got {until!r} after {last})")
        else:
            last = float(until)
        iv = p.get("interval")
        if not (isinstance(iv, list) and len(iv) == 2
                and all(isinstance(v, (int, float)) and v > 0 for v in iv)):
            bad.append(f"{tag}: `interval` must be [start, end] seconds > 0")
        pack = p.get("pack")
        if not (isinstance(pack, list) and len(pack) == 2
                and all(isinstance(v, int) and v >= 1 for v in pack)
                and pack[0] <= pack[1]):
            bad.append(f"{tag}: `pack` must be [lo, hi] with 1 <= lo <= hi")
        elite = p.get("elite", 0.0)
        if not (isinstance(elite, (int, float)) and 0.0 <= elite <= 1.0):
            bad.append(f"{tag}: `elite` must be a chance in 0..1")
        types = p.get("types")
        if not (isinstance(types, dict) and types):
            bad.append(f"{tag}: `types` must map enemy ids to weights")
        else:
            for eid, w in types.items():
                if enemy_ids is not None and eid not in enemy_ids:
                    bad.append(f"{tag}: unknown enemy {eid!r}")
                if not (isinstance(w, (int, float)) and w > 0):
                    bad.append(f"{tag}: weight of {eid!r} must be > 0")
    if last < 1.0:
        bad.append(f"{where}: phases end at {last}, before the run does (1.0)")


class SpawnTables:
    def __init__(self, data: dict, enemy_ids: Iterable[str] | None = None) -> None:
        self._data = data
        ids = set(enemy_ids) if enemy_ids is not None else None
        problems = self.validate(data, ids)
        if problems:
            raise TableError("spawn_tables.json: " + "; ".join(problems))
        self.unused: frozenset = frozenset(data.get("unused", ()))
        self._phases: list = self._enabled_phases(data["phases"])
        # S12: the schedule's own clock. Defaulted here only so tables
        # handed in by a test (and the pre-S12 fixture) stay constructible;
        # the shipped tables always carry it.
        self.ramp_seconds: float = float(data.get("ramp_seconds", 600.0))
        # G0b: 0 is a first-class value (the whole company on one frame),
        # so it is also the default a hand-made test table gets.
        self.company_stagger: float = float(data.get("company_stagger", 0.0))
        self._overrides: dict = {
            lvl: ({**over, "phases": self._enabled_phases(over["phases"])}
                  if "phases" in over else over)
            for lvl, over in data.get("difficulty", {}).items()}
        self.elites: dict = data["elites"]
        self.groups: dict = {name: self._enabled_group(g)
                             for name, g in data.get("groups", {}).items()}
        self.placement: dict = data.get("placement", {})
        self.owners: dict = data.get("owners", {})
        self.locality: dict = data.get("locality", {})
        self.population: dict = data.get("population", {})
        self.watchdog: dict = data.get("watchdog", {})
        self.residents: dict = data.get("residents", {})
        self.pacing: dict = data.get("pacing", {})

    # --- the unused category -------------------------------------------
    def _enabled_phases(self, phases: list) -> list:
        """`phases` with every benched enemy dropped from its `types`.

        Filtered once, here, rather than on every lookup: `phase_at` hands the
        same dict back each call and callers compare phases by identity.
        """
        if not self.unused:
            return phases
        return [{**p, "types": {k: v for k, v in p["types"].items()
                                if k not in self.unused}}
                for p in phases]

    def _enabled_group(self, group: dict) -> dict:
        if not self.unused or not group.get("followers"):
            return group
        return {**group, "followers": {k: v for k, v in group["followers"].items()
                                       if k not in self.unused}}

    # --- checks --------------------------------------------------------
    @staticmethod
    def validate(data: dict, enemy_ids=None) -> list[str]:
        """Every problem, as a sentence each; empty when the tables are sound."""
        bad: list[str] = []
        _check_phases(data.get("phases"), "phases", enemy_ids, bad)
        unused = data.get("unused", [])
        if not (isinstance(unused, list)
                and all(isinstance(x, str) for x in unused)):
            bad.append("`unused` must be a list of enemy ids")
        else:
            disabled = set(unused)
            for eid in unused:
                if enemy_ids is not None and eid not in enemy_ids:
                    bad.append(f"unused: unknown enemy {eid!r}")
            # Benching must not empty a band, orphan a group or silence the
            # elite slot -- those are table errors, not tuning.
            for i, p in enumerate(data.get("phases") or []):
                types = p.get("types")
                if isinstance(types, dict) and types and not (set(types) - disabled):
                    bad.append(f"phases: phase {i} has nothing left once "
                               f"{sorted(disabled & set(types))} are unused")
            for name, g in data.get("groups", {}).items():
                if g.get("leader") in disabled:
                    bad.append(f"group {name!r}: its leader {g['leader']!r} is unused")
            el = data.get("elites")
            if isinstance(el, dict):
                for key in ("default", "rare"):
                    if el.get(key) in disabled:
                        bad.append(f"elites: `{key}` names the unused {el[key]!r}")
        ramp = data.get("ramp_seconds", 600.0)
        if not (isinstance(ramp, (int, float)) and ramp > 0):
            bad.append("`ramp_seconds` must be a number > 0")
        stagger = data.get("company_stagger", 0.0)
        if not (isinstance(stagger, (int, float)) and stagger >= 0):
            bad.append("`company_stagger` must be a number >= 0")
        el = data.get("elites")
        if not isinstance(el, dict):
            bad.append("`elites` must be an object")
        else:
            for key in ("default", "rare"):
                eid = el.get(key)
                if not isinstance(eid, str):
                    bad.append(f"elites: `{key}` must name an enemy")
                elif enemy_ids is not None and eid not in enemy_ids:
                    bad.append(f"elites: unknown enemy {eid!r}")
            ch = el.get("rare_chance", 0.0)
            if not (isinstance(ch, (int, float)) and 0.0 <= ch <= 1.0):
                bad.append("elites: `rare_chance` must be a chance in 0..1")
        for name, g in data.get("groups", {}).items():
            tag = f"group {name!r}"
            leader = g.get("leader")
            if not isinstance(leader, str):
                bad.append(f"{tag}: needs a `leader`")
            elif enemy_ids is not None and leader not in enemy_ids:
                bad.append(f"{tag}: unknown leader {leader!r}")
            followers = g.get("followers", {})
            if not isinstance(followers, dict):
                bad.append(f"{tag}: `followers` must map enemy ids to [lo, hi]")
                continue
            for eid, span in followers.items():
                if enemy_ids is not None and eid not in enemy_ids:
                    bad.append(f"{tag}: unknown follower {eid!r}")
                if not (isinstance(span, list) and len(span) == 2
                        and all(isinstance(v, int) and v >= 0 for v in span)
                        and span[0] <= span[1]):
                    bad.append(f"{tag}: {eid!r} count must be [lo, hi]")
            if g.get("clearance", "large") not in ("small", "large"):
                bad.append(f"{tag}: `clearance` must be small or large")
        ow = data.get("owners", {})
        if not isinstance(ow, dict) or not all(
                isinstance(v, list) and all(isinstance(x, str) for x in v) for v in ow.values()):
            bad.append("`owners` must map names to lists of owner strings")
        for section in ("placement", "locality", "population", "watchdog"):
            sec = data.get(section, {})
            if not isinstance(sec, dict):
                bad.append(f"`{section}` must be an object")
                continue
            for key, v in sec.items():
                # `_`-prefixed keys are comments, the convention the rest of
                # the data uses (`game/content.py` skips them everywhere, and
                # `potions.json` documents its bands that way). Without this a
                # note written beside a tuning value fails content load.
                if key.startswith("_"):
                    continue
                if not (isinstance(v, (int, float)) and v >= 0):
                    bad.append(f"{section}: `{key}` must be a number >= 0")
        pc = data.get("pacing", {})
        if not isinstance(pc, dict):
            bad.append("`pacing` must be an object")
        else:
            b = pc.get("bounds")
            if b is not None and not (isinstance(b, list) and len(b) == 2
                                      and 0 < b[0] <= 1.0 <= b[1]):
                bad.append("pacing: `bounds` must be [lo, hi] with lo <= 1 <= hi")
            base = pc.get("base", 1.0)
            if not (isinstance(base, (int, float)) and base > 0):
                bad.append("pacing: `base` must be a number > 0")
            w = pc.get("weights", {})
            if not isinstance(w, dict) or any(
                    not (isinstance(v, (int, float)) and v >= 0) for v in w.values()):
                bad.append("pacing: `weights` must map signals to numbers >= 0")
        for level, over in data.get("difficulty", {}).items():
            if not isinstance(over, dict):
                bad.append(f"difficulty {level!r}: must be an object")
            elif "phases" in over:
                _check_phases(over["phases"], f"difficulty {level!r}", enemy_ids, bad)
        return bad

    # --- lookups ------------------------------------------------------
    def phases(self, difficulty: str | None = None) -> list:
        """The phase list a difficulty plays: its own if it carries one,
        else the shared schedule."""
        over = self._overrides.get(difficulty or "", {})
        return over.get("phases", self._phases)

    def phase_at(self, fraction: float, difficulty: str | None = None) -> dict:
        """The band a ramp fraction (0..1) falls in; the last band past the
        end, so the rest of the run keeps the final mix."""
        phases = self.phases(difficulty)
        for phase in phases:
            if fraction < phase["until"]:
                return phase
        return phases[-1]

    def group(self, name: str) -> dict:
        try:
            return self.groups[name]
        except KeyError as exc:
            raise TableError(f"unknown spawn group: {name!r}") from exc

    def enemy_ids(self) -> set[str]:
        """Every enemy id the tables can ever ask for."""
        out = set()
        for level in [None, *self._overrides]:
            for p in self.phases(level):
                out.update(p["types"])
        out.update((self.elites["default"], self.elites["rare"]))
        for g in self.groups.values():
            out.add(g["leader"])
            out.update(g.get("followers", {}))
        return out
