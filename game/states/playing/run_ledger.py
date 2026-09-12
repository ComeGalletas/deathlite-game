"""The run's damage and kill ledger -- what the game-over screen reads.

The training dummy's `DpsMeter` answers "what does this build do?" by arming
itself on one enemy. The question at the end of a run is different: "what did
each weapon do, over the whole run, to everything?" That needs a listener on
**every** enemy for the run's whole length, so the ledger hangs off the same
seam the meter uses -- `Enemy._absorb`, the one place damage lands -- through
its own attribute (`enemy.ledger`), set by the spawner. The meter's
`damage_sink` and this never fight: the sink is the dummy's, the ledger is the
run's.

Three things it keeps, and why:

* **damage per source** -- keyed by whatever the damage path named itself
  with: a weapon id for a hit or a burn tick, a blessing id for a proc,
  `other` for a path that named nothing. The villager source is dropped, as
  the meter drops it: a lancer stabbing a husk is not the hero's damage.
* **when each weapon was first held** -- so a weapon's DPS is its damage
  over the time the hero *had* it. A weapon picked up at minute eight is not
  charged for the seven minutes it did not exist. Tracked by the update loop
  looking at `player.weapons` every frame (three dictionary look-ups) rather
  than by every site that hands a weapon over, none of which then has to
  remember to report.
* **kills per enemy type** -- by `enemy_id`, with the display name kept
  alongside so the screen does not need the content tables. The boss counts
  here too, under its own id.
"""
from __future__ import annotations

from game.states.playing.dps_meter import UNATTRIBUTED, VILLAGER


class RunLedger:
    def __init__(self) -> None:
        # The run clock, set by the update loop; every timestamp below is on it.
        self.now = 0.0
        self.damage: dict[str, float] = {}
        self.first_hit: dict[str, float] = {}
        self.held_since: dict[str, float] = {}
        self.kills: dict[str, int] = {}
        self.kill_names: dict[str, str] = {}

    # --- recording ------------------------------------------------
    def record(self, amount: float, source=None) -> None:
        """One hit. Called through `Enemy._absorb` / `Boss._absorb`."""
        if amount <= 0.0:
            return
        # An empty string is as unnamed as None: a projectile whose
        # `weapon_id` was never set must not become a blank row.
        key = UNATTRIBUTED if not source else str(source)
        if key == VILLAGER:
            return
        self.damage[key] = self.damage.get(key, 0.0) + amount
        self.first_hit.setdefault(key, self.now)

    def track_held(self, weapon_ids) -> None:
        """Note the clock for any weapon id seen for the first time."""
        for wid in weapon_ids:
            self.held_since.setdefault(wid, self.now)

    def kill(self, enemy) -> None:
        """A death. `enemy` is an `Enemy` or the `Boss` (duck-typed: an
        `enemy_id` or a `boss_id`, and a `name`)."""
        key = getattr(enemy, "enemy_id", None) or getattr(enemy, "boss_id", None) or "?"
        self.kills[key] = self.kills.get(key, 0) + 1
        self.kill_names.setdefault(key, str(getattr(enemy, "name", key)))

    # --- readout --------------------------------------------------
    @property
    def total(self) -> float:
        return sum(self.damage.values())

    @property
    def total_kills(self) -> int:
        return sum(self.kills.values())

    def span_of(self, source: str, end: float | None = None) -> float:
        """Seconds a source was live: from when the weapon was first held,
        else from its first hit, to `end` (the clock now by default)."""
        end = self.now if end is None else end
        since = self.held_since.get(source, self.first_hit.get(source, 0.0))
        return max(0.0, end - since)

    def dps_of(self, source: str, end: float | None = None) -> float:
        span = self.span_of(source, end)
        return self.damage.get(source, 0.0) / span if span > 0.0 else 0.0

    def weapon_rows(self, weapons, end: float | None = None) -> list[dict]:
        """One row per held weapon, in slot order: id, name, level, damage,
        share of the run total, dps over the held span."""
        total = self.total
        rows = []
        for w in weapons:
            dmg = self.damage.get(w.weapon_id, 0.0)
            rows.append({"id": w.weapon_id, "name": w.name, "level": int(w.level),
                         "damage": dmg, "share": dmg / total if total else 0.0,
                         "dps": self.dps_of(w.weapon_id, end)})
        return rows

    def other_rows(self, held_ids, names: dict | None = None,
                   end: float | None = None) -> list[dict]:
        """Every source that is not a held weapon -- blessing procs, a weapon
        the run let go of, the unattributed bucket -- biggest first. `names`
        maps an id to a display name; an id it lacks is shown titled, with
        underscores as spaces."""
        names = names or {}
        held = set(held_ids)
        total = self.total
        rows = []
        for key, dmg in sorted(self.damage.items(), key=lambda kv: -kv[1]):
            if key in held:
                continue
            rows.append({"id": key, "name": names.get(key, key.replace("_", " ").title()),
                         "level": None, "damage": dmg,
                         "share": dmg / total if total else 0.0,
                         "dps": self.dps_of(key, end)})
        return rows

    def kill_rows(self) -> list[tuple[str, int]]:
        """`[(display name, count)]`, biggest first."""
        return [(self.kill_names.get(k, k), n)
                for k, n in sorted(self.kills.items(), key=lambda kv: (-kv[1], kv[0]))]
