"""`data/spawn_tables.json`: what spawns when, read once and checked.

Spawn master S2. The phase schedule used to be `_PHASES`, a list literal
in `world/spawning.py`; it is data, so it lives with the rest of the data
now, under the project's rule that tuning is never defaulted in code. The
numbers moved verbatim -- `tests/spawn/test_budget.py` replays a scripted
run and checks the enemy sequence is the one the literal produced.

Sections:

    phases      run-fraction bands: `until` (exclusive upper bound),
                `interval` [at band start, at run end], `pack` [lo, hi],
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
                view pad, minimum distance from the player, when a deferred
                pack relaxes the view rule, the follower ring gap, and the
                same-floor / preferred-tag weights
    difficulty  per-level overrides; a level may carry its own `phases`
                list (same shape) that replaces the shared one. Empty today:
                the four difficulty *factors* stay in `config.DIFFICULTIES`.
    residents   S4: groups seeded into an island on first visit, by room
                kind, and a per-difficulty scale
    pacing      S6: bounds, smoothing (`tau`), dead-band and signal weights
                of the pressure multiplier, the rate `window`, the
                `lull_seconds` to a full lull, and `damage_rate_full`, the
                HP fraction per second that reads as -1

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
        self._phases: list = data["phases"]
        self._overrides: dict = data.get("difficulty", {})
        self.elites: dict = data["elites"]
        self.groups: dict = data.get("groups", {})
        self.placement: dict = data.get("placement", {})
        self.owners: dict = data.get("owners", {})
        self.locality: dict = data.get("locality", {})
        self.population: dict = data.get("population", {})
        self.watchdog: dict = data.get("watchdog", {})
        self.residents: dict = data.get("residents", {})
        self.pacing: dict = data.get("pacing", {})

    # --- checks --------------------------------------------------------
    @staticmethod
    def validate(data: dict, enemy_ids=None) -> list[str]:
        """Every problem, as a sentence each; empty when the tables are sound."""
        bad: list[str] = []
        _check_phases(data.get("phases"), "phases", enemy_ids, bad)
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
        """The band a run fraction (0..1) falls in; the last band past the
        end, so a run that overstays keeps its final mix."""
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
