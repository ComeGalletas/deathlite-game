"""Treasure chests in the run (CB-9).

`Chests` owns the run's chest props: it builds them from `layout.chests` (the
seed decided where they are and which tier each is), answers "is the hero
standing on an unopened one?", pays the loot out when `E` is pressed, and
advances the lid animations each frame.

It is deliberately a sibling of `SpecialLocations` rather than another
`Interactable` kind. A chest carries a rarity, an animation and a rolled
payload, none of which a special-room one-off has, and there are fifteen to
twenty of them against a handful of those.

Reads from `PlayingState`: `game_map`, `player`, `stats`, `rng`, `content`,
`potions`. Writes `ps.chests`, and uses `ps.particles` / `ps.notice` for
feedback. The payload rules are all in `progression/chests.py`; the blessing
itself comes from the offering, filtered to the rarity the chest rolled.
"""
from __future__ import annotations

import pygame

from entities.chest import Chest
from progression import chests as chest_rules
from progression.blessings import roll_offering


class Chests:
    def __init__(self, ps) -> None:
        self.ps = ps
        self.run = getattr(ps, "run", ps)
    # --- setup ---------------------------------------------------
    def build(self) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        run.chests = []
        layout = run.game_map.layout
        if layout is None:
            return
        radius = chest_rules.radius(run.content.chests)
        for record in getattr(layout, "chests", ()):
            run.chests.append(Chest(record.x, record.y, record.rarity,
                                   floor=record.floor, radius=radius))

    # --- per frame -----------------------------------------------
    def update(self, dt: float) -> None:
        duration = chest_rules.open_seconds(self.run.content.chests)
        for chest in self.run.chests:
            chest.update(dt, duration)

    def nearby(self):
        """The nearest unopened chest the hero can reach, or `None`. Nearest
        rather than first so two chests sharing a corner open in the order the
        player walks into them."""
        ps = self.ps
        run = getattr(self, "run", ps)
        best, best_d = None, 0.0
        for chest in run.chests:
            if chest.opened or not chest.in_range(run.player.pos):
                continue
            d = (chest.pos - run.player.pos).length_squared()
            if best is None or d < best_d:
                best, best_d = chest, d
        return best

    # --- opening -------------------------------------------------
    def activate_nearby(self) -> bool:
        """Open the chest the hero is standing on. Returns True if one was."""
        chest = self.nearby()
        if chest is None:
            return False
        self.open(chest)
        return True

    def open(self, chest) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        table = run.content.chests
        chest.opened = True
        chest.age = 0.0
        run.stats["chests"] = run.stats.get("chests", 0) + 1

        gold = chest_rules.gold(chest.rarity, table, run.rng)
        ps.add_gold(gold)

        parts = [f"{gold} gold"]
        potion = self._spill_potion(chest, table)
        if potion is not None:
            parts.append(f"a {potion} potion")
        blessing = self._grant_blessing(chest, table)
        if blessing is not None:
            parts.append(blessing)

        run.particles.burst(chest.pos, chest_rules.colour(chest.rarity, table),
                           count=26, speed=220, life=0.6)
        ps.notice(f"{chest.rarity.capitalize()} chest: {self._listed(parts)}.")

    @staticmethod
    def _listed(parts: list[str]) -> str:
        if len(parts) == 1:
            return parts[0]
        return ", ".join(parts[:-1]) + " and " + parts[-1]

    def _spill_potion(self, chest, table) -> str | None:
        """Put this chest's one potion **on** it -- centred `potion_lift` px
        above the chest's baseline, which lands it in the open box's mouth
        rather than beside it, so the loot reads as coming out of the chest it
        was found in. `WorldRenderer` draws potions after chests, so the chest
        art never covers it.

        `None` if the potion pool is capped, which degrades the chest rather
        than crashing the run.
        """
        ps = self.ps
        run = getattr(self, "run", ps)
        from progression import potions as potion_rules
        potion = run.potions.acquire()
        if potion is None:
            return None
        rarity = chest_rules.potion_rarity(chest.rarity, table)
        at = chest.pos - pygame.Vector2(0.0, chest_rules.potion_lift(table))
        potion.reset(at, rarity, potion_rules.heal_amount(rarity, run.content.potions))
        return rarity

    def _grant_blessing(self, chest, table) -> str | None:
        """Grant the blessing this chest rolled, and name it for the notice.

        Falls back a step at a time rather than silently paying nothing: the
        rolled rarity first, then any rarity, and -- if the hero has genuinely
        maxed everything the offering can show -- nothing at all, which is why
        the caller treats `None` as "the chest just had gold and a potion".
        """
        ps = self.ps
        run = getattr(self, "run", ps)
        rarity = chest_rules.blessing_rarity(chest.rarity, table, run.rng)
        if rarity is None:
            return None
        kinds = ("stat", "weapon")
        choices = roll_offering(run.player, run.content, run.rng, 1,
                                kinds=kinds, rarities=(rarity,))
        if not choices:
            choices = roll_offering(run.player, run.content, run.rng, 1, kinds=kinds)
        if not choices:
            return None
        upgrade = choices[0]
        upgrade.apply(ps.player)
        ps.particles.burst(ps.player.pos, (150, 190, 255), count=20,
                           speed=180, life=0.6)
        return upgrade.title
