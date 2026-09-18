"""`data/enemies/spawn_tables.json`: what spawns when, read once and checked.

Spawn master S2, rewritten for the company model in G3. What used to live
here was a phase schedule -- ramp-fraction bands of enemy weights, pack
sizes and intervals. A company is now one social group drawn whole, so the
bands went and `groups` plus `cooldowns` took their place. Tuning is still
never defaulted in code.

Sections:

    unused      enemies benched from the run: an id here keeps its block,
                its art and its weights, but is filtered out of a group's
                members as the tables are read, so no company can draw it.
                Deliberately *disabled*, not deleted -- `spawn_at` /
                `spawn_group` / the dev menu still seat one on request.
    company_stagger
                G0b: how long a company takes to materialise, in seconds.
                The positions, the point and the cap are all decided when
                the company is seated; this only spreads *when* each body
                appears. 0 means the whole company on one frame, which is a
                supported setting rather than a degenerate one.
    groups      G2: the six social groups a company is drawn from. Each has
                `commons` (id -> weight) and `common_range` [min, max]; the
                two elite-bearing groups add `elites` (id -> weight),
                `elite_range` [base minimum, ceiling] and `elite_step`, how
                much that minimum climbs every `cooldowns.step_seconds`. A
                company is one group, so the group is the unit of variety.
                This replaced the leader + followers templates outright --
                a company has no leader, only a body seated first -- and
                clearance is no longer declared here because placement
                derives it from the largest body in the company.
                Only the *presence* of this section is checked here (G2a,
                owner 2026-09-17). Its members, weights, spans and ranks are
                resolved once per run by `spawn/roster.py`, which skips or
                demotes what it cannot use and logs each decision, so bad
                group data costs an enemy or a group and never the run.
    cooldowns   G2: the two ladders. `common` is the cadence for a company
                of any kind; `elite` gates *eligibility* for the two elite
                groups. Both step down every `step_seconds`, by
                `common_decay` / `elite_decay`, flooring at
                `common_floor` / `elite_floor`. `elite_unlock` is a hard
                gate before which no elite group is picked at all, and
                `cap_retry` is the wait before re-counting a company that
                did not fit under the live cap. Normal seconds; everything
                here, the step included, divides by `timeline_pace`.
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
    difficulty  per-level overrides. Empty today: the four difficulty
                *factors* stay in `config.DIFFICULTIES`.
    residents   S4: how many companies are seeded into an island on first
                visit, by room kind, and a per-difficulty scale

G3 retired `phases`, `ramp_seconds`, the top-level `elites` slot and
`pacing`: the six groups and the cooldown ladder replaced them outright.
Enemy ids are therefore no longer checked here at all -- the only place they
appear now is `groups`, which `spawn/roster.py` resolves once per run and
fails soft on.
"""
from __future__ import annotations

from typing import Iterable

__all__ = ["SpawnTables", "TableError"]


class TableError(ValueError):
    """The tables are malformed or name something that does not exist."""


_COOLDOWN_KEYS = ("common", "common_decay", "common_floor",
                  "elite", "elite_decay", "elite_floor",
                  "step_seconds", "elite_unlock", "cap_retry")


def _check_groups(data: dict, bad: list) -> None:
    """Only that there is something to resolve.

    G2 checked every member here and refused to load on a bad one. The owner
    reversed that on 2026-09-17: a corrupt or inadequate group should cost
    the offending enemy or group, not the run. Member ids, weights, count
    spans and rank are all decided once per run by `spawn/roster.py`, which
    skips or demotes what it cannot use and logs every decision.

    What stays fatal is only what leaves nothing to resolve at all -- there
    is no enemy to skip and no company could be built either way.
    """
    groups = data.get("groups")
    if not (isinstance(groups, dict) and groups):
        bad.append("`groups` must be a non-empty object")


def _check_cooldowns(data: dict, bad: list) -> None:
    cd = data.get("cooldowns")
    if not isinstance(cd, dict):
        bad.append("`cooldowns` must be an object")
        return
    for key in _COOLDOWN_KEYS:
        v = cd.get(key)
        if not isinstance(v, (int, float)):
            bad.append(f"cooldowns: `{key}` must be a number")
        elif v < 0:
            bad.append(f"cooldowns: `{key}` must be >= 0")
    for start, floor in (("common", "common_floor"), ("elite", "elite_floor")):
        a, b = cd.get(start), cd.get(floor)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b > a:
            bad.append(f"cooldowns: `{floor}` ({b}) is above `{start}` ({a})")
    for key in ("step_seconds", "cap_retry"):
        v = cd.get(key)
        if isinstance(v, (int, float)) and v <= 0:
            bad.append(f"cooldowns: `{key}` must be > 0")


class SpawnTables:
    def __init__(self, data: dict, enemy_ids: Iterable[str] | None = None) -> None:
        self._data = data
        ids = set(enemy_ids) if enemy_ids is not None else None
        problems = self.validate(data, enemy_ids)
        if problems:
            raise TableError("spawn_tables.json: " + "; ".join(problems))
        self.unused: frozenset = frozenset(data.get("unused", ()))
        # G0b: 0 is a first-class value (the whole company on one frame),
        # so it is also the default a hand-made test table gets.
        self.company_stagger: float = float(data.get("company_stagger", 0.0))
        self._overrides: dict = dict(data.get("difficulty", {}))
        # G2: the six social groups. `_`-prefixed keys are comments, the
        # convention the rest of the data uses, and are not groups.
        self.groups: dict = {name: self._enabled_group(g)
                             for name, g in data.get("groups", {}).items()
                             if not name.startswith("_")}
        self.cooldowns: dict = data.get("cooldowns", {})
        self.placement: dict = data.get("placement", {})
        self.owners: dict = data.get("owners", {})
        self.locality: dict = data.get("locality", {})
        self.population: dict = data.get("population", {})
        self.watchdog: dict = data.get("watchdog", {})
        self.residents: dict = data.get("residents", {})

    # --- the unused category -------------------------------------------
    def _enabled_group(self, group: dict) -> dict:
        """A group with its benched members dropped from both halves. Done
        once, at construction, so a company can never draw one."""
        if not self.unused:
            return group
        out = dict(group)
        for half in ("commons", "elites"):
            members = group.get(half)
            if isinstance(members, dict):
                out[half] = {k: v for k, v in members.items()
                             if k not in self.unused}
        return out

    # --- checks --------------------------------------------------------
    @staticmethod
    def validate(data: dict, enemy_ids=None) -> list[str]:
        """Every problem, as a sentence each; empty when the tables are sound."""
        bad: list[str] = []
        unused = data.get("unused", [])
        if not (isinstance(unused, list)
                and all(isinstance(x, str) for x in unused)):
            bad.append("`unused` must be a list of enemy ids")
        else:
            disabled = set(unused)
            for eid in unused:
                if enemy_ids is not None and eid not in enemy_ids:
                    bad.append(f"unused: unknown enemy {eid!r}")
        stagger = data.get("company_stagger", 0.0)
        if not (isinstance(stagger, (int, float)) and stagger >= 0):
            bad.append("`company_stagger` must be a number >= 0")
        _check_groups(data, bad)
        _check_cooldowns(data, bad)
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
        for level, over in data.get("difficulty", {}).items():
            if not isinstance(over, dict):
                bad.append(f"difficulty {level!r}: must be an object")
        return bad

    # --- lookups ------------------------------------------------------
    def group(self, name: str) -> dict:
        try:
            return self.groups[name]
        except KeyError as exc:
            raise TableError(f"unknown spawn group: {name!r}") from exc

    # `group_names` and `elite_count` moved to `spawn/roster.py` in G2a. They
    # read the *declared* table, and the draw must read the *resolved* one --
    # a group whose members did not hold up may be common-only or absent
    # altogether, and an accessor here could not know that.

    def enemy_ids(self) -> set[str]:
        """Every enemy id the tables can ever ask for -- the members of the
        six groups, since G3 left nothing else that names one. Declared
        rather than resolved: this is what the data asks for, and
        `spawn/roster.py` decides what of it can actually be used."""
        out = set()
        for g in self.groups.values():
            out.update(g.get("commons", {}))
            out.update(g.get("elites", {}))
        return out
