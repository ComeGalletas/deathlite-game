"""Meta-progression (spec 4.6).

Persistent upgrades bought with Salvage between runs. Values are deliberately
small (spec: "Persistent upgrades should be modest ... do not make future runs
trivial"). Stats prefixed with `__` are meta-only knobs (e.g. `__salvage_gain`)
and are consumed here, not pushed to the player's StatSet.
"""
from __future__ import annotations

from dataclasses import dataclass

from progression.stats import FLAT, MULT, PCT, Modifier

_OP = {"flat": FLAT, "pct": PCT, "mult": MULT}


@dataclass
class MetaCatalog:
    defs: dict[str, dict]

    def cost(self, upgrade_id: str, current_level: int) -> int:
        d = self.defs[upgrade_id]
        return int(d["cost_base"] + d["cost_step"] * current_level)

    def max_level(self, upgrade_id: str) -> int:
        return int(self.defs[upgrade_id]["max_level"])

    def can_buy(self, upgrade_id: str, level: int, currency: int) -> bool:
        return (level < self.max_level(upgrade_id)
                and currency >= self.cost(upgrade_id, level))

    # --- run-start application ------------------------------------
    def player_modifiers(self, levels: dict[str, int]) -> list[Modifier]:
        mods: list[Modifier] = []
        for uid, lvl in levels.items():
            d = self.defs.get(uid)
            if not d or lvl <= 0 or d["stat"].startswith("__"):
                continue
            mods.append(Modifier(d["stat"], _OP[d["op"]],
                                 d["per_level"] * lvl, f"meta:{uid}"))
        return mods

    def salvage_multiplier(self, levels: dict[str, int]) -> float:
        d = self.defs.get("salvager")
        if not d:
            return 1.0
        return 1.0 + d["per_level"] * levels.get("salvager", 0)


def buy(catalog: MetaCatalog, save, upgrade_id: str) -> bool:
    """Attempt a purchase; mutates `save` (currency + meta level). Returns
    True on success."""
    level = save.meta.get(upgrade_id, 0)
    if not catalog.can_buy(upgrade_id, level, save.currency):
        return False
    save.currency -= catalog.cost(upgrade_id, level)
    save.meta[upgrade_id] = level + 1
    return True
