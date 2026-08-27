"""Passive blessings (spec 4.2 / 4.3).

Blessings are data (data/blessings.json). Each has a list of small typed
`effects`; six kinds cover the spec's examples without a bespoke system per
blessing:

  stat_mod      -> a StatSet Modifier on the player
  tag_damage    -> +% damage for hits carrying a tag ("area"/"elite" included)
  on_hit_status -> chance to apply a status when a matching-tag hit lands
  status_vuln   -> extra % damage to enemies under a status (optionally only
                   from a given attack tag) -- this is the synergy layer
  status_tune   -> adjust an applied status's potency / duration / max stacks
  on_kill       -> soul / heal / fire_nova / shock_spread on an enemy's death

`BlessingEffects` is the flattened, stack-aware aggregate the combat loop reads.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from progression.stats import FLAT, MULT, PCT, Modifier
from progression.upgrades import Upgrade

_OP_MAP = {"flat": FLAT, "pct": PCT, "mult": MULT}


@dataclass
class Blessing:
    id: str
    source: str
    name: str
    description: str
    tags: tuple[str, ...]
    max_stacks: int
    effects: list[dict]

    @classmethod
    def from_data(cls, bid: str, d: dict) -> "Blessing":
        return cls(bid, d["source"], d["name"], d.get("description", ""),
                   tuple(d.get("tags", ())), int(d.get("max_stacks", 1)),
                   list(d.get("effects", [])))


@dataclass
class BlessingEffects:
    tag_damage: dict[str, float] = field(default_factory=dict)          # tag -> +frac
    on_hit: list[tuple] = field(default_factory=list)                   # (status, tag|None, chance, dur, potency)
    status_vuln: list[tuple] = field(default_factory=list)             # (status, attack_tag|None, +frac)
    status_tune: dict[tuple, float] = field(default_factory=dict)      # (status, field) -> value
    on_kill: list[tuple] = field(default_factory=list)                # (effect, chance, amount)
    soul_heal: int = 0

    def tag_bonus(self, tags, is_elite: bool) -> float:
        total = sum(self.tag_damage.get(t, 0.0) for t in tags)
        if is_elite:
            total += self.tag_damage.get("elite", 0.0)
        return total

    def vuln_bonus(self, tags, status_state) -> float:
        total = 0.0
        for status, atk_tag, frac in self.status_vuln:
            if status in status_state and (atk_tag is None or atk_tag in tags):
                total += frac
        return total

    def tuned(self, status: str, field_: str) -> float:
        return (self.status_tune.get((status, field_), 0.0)
                + self.status_tune.get(("*", field_), 0.0))


class BlessingLibrary:
    def __init__(self, data: dict[str, dict]) -> None:
        self.by_id = {bid: Blessing.from_data(bid, d) for bid, d in data.items()}
        self.sources = sorted({b.source for b in self.by_id.values()})

    def get(self, bid: str) -> Blessing:
        return self.by_id[bid]


# --- application -------------------------------------------------------
def apply_blessing(player, blessing: Blessing) -> None:
    player.blessings[blessing.id] = player.blessings.get(blessing.id, 0) + 1
    _apply_stat_mods(player, blessing)
    rebuild(player, _library_from(player))


def _library_from(player):
    # The library is stashed on the player when the run starts.
    return player._blessing_library


def _apply_stat_mods(player, blessing: Blessing) -> None:
    stack = player.blessings[blessing.id]
    src = f"bless:{blessing.id}#{stack}"
    mods = []
    for eff in blessing.effects:
        if eff["kind"] == "stat_mod":
            mods.append(Modifier(eff["stat"], _OP_MAP[eff["op"]], eff["value"], src))
    if mods:
        player.add_modifiers(*mods)


def rebuild(player, library: BlessingLibrary) -> None:
    """Recompute the flattened `BlessingEffects` from every owned stack."""
    fx = BlessingEffects()
    for bid, stacks in player.blessings.items():
        b = library.get(bid)
        for eff in b.effects:
            kind = eff["kind"]
            if kind == "tag_damage":
                fx.tag_damage[eff["tag"]] = fx.tag_damage.get(eff["tag"], 0.0) + eff["value"] * stacks
            elif kind == "on_hit_status":
                # Multiple stacks raise the proc chance (capped later).
                fx.on_hit.append((eff["status"], eff.get("tag"),
                                  min(1.0, eff["chance"] * stacks),
                                  eff["duration"], eff["potency"]))
            elif kind == "status_vuln":
                fx.status_vuln.append((eff["status"], eff.get("attack_tag"),
                                       eff["value"] * stacks))
            elif kind == "status_tune":
                key = (eff["status"], eff["field"])
                fx.status_tune[key] = fx.status_tune.get(key, 0.0) + eff["value"] * stacks
            elif kind == "on_kill":
                if eff["effect"] == "soul_heal":
                    fx.soul_heal += int(eff.get("amount", 1)) * stacks
                else:
                    fx.on_kill.append((eff["effect"],
                                       min(1.0, eff["chance"] * stacks),
                                       eff.get("amount", 0)))

    # Equipped items contribute their tag-damage affixes to the same aggregate
    # (spec 4.5: affixes interact with build tags). Their plain stat affixes are
    # applied to the StatSet separately at run start.
    for item in getattr(player, "equipment", ()):
        for tag, value in item.tag_effects():
            fx.tag_damage[tag] = fx.tag_damage.get(tag, 0.0) + value

    player.blessing_fx = fx


# --- level-up integration --------------------------------------------
def roll_blessing_choices(player, library: BlessingLibrary,
                          rng: random.Random, n: int = 3) -> list[Upgrade]:
    """Offer blessings the player can still take (below max stacks). Returned as
    `Upgrade` records so the existing level-up screen renders them unchanged."""
    pool = [b for b in library.by_id.values()
            if player.blessings.get(b.id, 0) < b.max_stacks]
    rng.shuffle(pool)
    chosen = pool[:n]
    out = []
    for b in chosen:
        out.append(Upgrade(
            id=f"bless:{b.id}", title=f"{b.source.title()} - {b.name}",
            description=b.description, weight=1.0,
            apply=lambda p, _b=b: apply_blessing(p, _b),
            max_stacks=b.max_stacks, tags=b.tags + (b.source,)))
    return out
