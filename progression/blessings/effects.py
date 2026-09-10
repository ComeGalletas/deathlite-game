"""The flattened combat aggregate the hit resolver reads (`player.blessing_fx`).

Before P2 every elemental blessing folded into this. Those blessings are
gone (design §21); the aggregate stays because the resolver's damage
multiplier and on-hit pass read it, and because equipped items still add
tag-damage affixes ("of the Maw", "of the Hunt"). `rebuild` is called at run
start, after every blessing, and after equipment changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field


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


def rebuild(player, library=None) -> None:
    """Recompute `player.blessing_fx`. `library` is accepted and ignored so
    the pre-P2 call sites keep working."""
    fx = BlessingEffects()
    # Equipped items contribute their tag-damage affixes (spec 4.5). Their
    # plain stat affixes are applied to the StatSet at run start.
    for item in getattr(player, "equipment", ()):
        for tag, value in item.tag_effects():
            fx.tag_damage[tag] = fx.tag_damage.get(tag, 0.0) + value
    player.blessing_fx = fx
