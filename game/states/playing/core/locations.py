"""Special locations (spec 5.5) for PLAYING.

`SpecialLocations` owns the run's `Interactable` list: it builds them from the
layout, answers "is the hero standing on a usable one?", dispatches the per-kind
`use_*` handler on the interact key, and drives the elite-arena state machine each
frame.

Reads from `PlayingState`: `game_map`, `player`, `stats`, `rng`, `blessing_lib`,
`enemies`. Uses `ps.particles` / `ps.shake` for feedback, writes
`ps.interactables` (in `build()`) and `ps._boss_warning_t` / `ps._boss_name`
(arena banner), and calls back `ps._drop_item` and `ps.spawn.spawn_enemy`.

Part of the split tracked in `journals/playing_state_refactor.md` (P4).
"""
from __future__ import annotations

import pygame

from entities.interactable import Interactable
from game.states.playing.core import elemental, infusion
from progression.blessings import roll_offering
from world.gen.tuning import SPECIAL_KINDS

MERCHANT_COST = 30            # in-run gold
ALTAR_HP_COST_FRACTION = 0.25


class SpecialLocations:
    def __init__(self, ps) -> None:
        self.ps = ps
        self.run = getattr(ps, "run", ps)
    def build(self) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        run.interactables = []
        if run.game_map.layout is None:
            return
        # Parked since 2026-09-20: `SPECIAL_KINDS` is empty, so no shrine,
        # treasure, altar or merchant is ever built here -- the generator no
        # longer labels an island with one. The loop and the four `use_*`
        # handlers below are kept as the template for when those facilities
        # come back in another form
        # (`journals/special_facilities_journal.md`).
        for room in run.game_map.layout.rooms:
            if room.kind in SPECIAL_KINDS:
                run.interactables.append(Interactable(
                    room.kind, room.center.x, room.center.y, cost=MERCHANT_COST))
        # HI-2: every village carries the forge and the sanctuary heal, where
        # the village pass put them.
        for v in getattr(run.game_map.layout, "villages", ()):
            run.interactables.append(Interactable("forge", v.forge.x, v.forge.y))
            run.interactables.append(Interactable("fountain", v.heal.x, v.heal.y))
            # M7: the Monastery is the village town hall, which the
            # village pass has always placed and nothing has ever used.
            # No new building, no change to generation.
            for kind, x, y in v.buildings:
                if kind == "monastery":
                    run.interactables.append(Interactable("monastery", x, y))
                    break
        # The buff buildings (journal: buff_buildings_journal.md): one
        # interactable on each building obstacle, which carries the art.
        for o in run.game_map.layout.buff_buildings(ps.buffs.kinds):
            run.interactables.append(Interactable(
                o.kind, o.pos.x, o.pos.y,
                element=elemental.roll(run, o)))

    def nearby(self):
        ps = self.ps
        run = getattr(self, "run", ps)
        for it in run.interactables:
            if not it.used and it.in_range(run.player.pos):
                return it
        return None

    def use(self, it) -> None:
        """Run `it`'s per-kind handler (the interact key, via
        `core/interactions.py`)."""
        if self.ps.buffs.is_buff(it.kind):
            self.ps.buffs.activate(it)
            return
        handler = getattr(self, f"use_{it.kind}", None)
        if handler is not None:
            handler(it)

    def activate_nearby(self) -> None:
        it = self.nearby()
        if it is not None:
            self.use(it)

    def grant_random_blessing(self) -> bool:
        ps = self.ps
        run = getattr(self, "run", ps)
        # P2: one blessing, never a weapon grant (a shrine does not hand out
        # weapons; the level-up does).
        choices = roll_offering(run.player, run.content, run.rng, 1,
                                kinds=("stat", "weapon"))
        if not choices:
            return False
        choices[0].apply(run.player)
        run.particles.burst(run.player.pos, (150, 190, 255), count=20,
                           speed=180, life=0.6)
        return True

    # --- per-kind handlers --------------------------------------
    def use_shrine(self, it: Interactable) -> None:
        it.used = True
        if not self.grant_random_blessing():
            self.run.player.heal(30)

    def use_treasure(self, it: Interactable) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        it.used = True
        ps._drop_item(max(2, int(1 + run.stats["time"] // 80)))
        run.particles.burst(it.pos, it.colour, count=24, speed=220, life=0.6)

    def use_fountain(self, it: Interactable) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        it.used = True
        run.player.heal(run.player.max_hp)
        run.particles.burst(run.player.pos, it.colour, count=18, speed=140, life=0.6)

    def use_altar(self, it: Interactable) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        cost = run.player.max_hp * ALTAR_HP_COST_FRACTION
        if run.player.hp <= cost + 1:
            return  # too risky -- refuse rather than kill the player
        run.player.hp -= cost
        it.used = True
        if not self.grant_random_blessing():
            run.player.heal(cost)  # refund if nothing to grant

    def use_monastery(self, it: Interactable) -> None:
        """The Monastery (design §7.2, confirmed 2026-09-21): the player
        picks any of the four elements and one weapon to carry it. It
        rolls nothing, offers every element whatever the run has
        unlocked, and is spent after a single use."""
        ps = self.ps
        run = getattr(self, "run", ps)
        run.particles.burst(it.pos, it.colour, count=18, speed=150, life=0.5)
        infusion.offer(
            ps, title="The Monastery  -  choose an element, then a weapon",
            on_done=lambda u: self._infused(it, u))

    def _infused(self, it: Interactable, upgrade) -> None:
        """Spend the source and say what happened. Only a completed pick
        spends it -- walking away with ESC leaves it standing."""
        it.used = True
        infusion._noticed(self.ps, upgrade)

    def use_forge(self, it: Interactable) -> None:
        """P3 (design §7), change request 6: offer the Forgings of *a chosen*
        weapon. The Forge is never consumed, and with nothing eligible it says
        what is missing instead of doing nothing.

        It used to take `eligible[0]`, so a player carrying two qualifying
        weapons could not reforge the second one at all. The overlay now gets
        every non-summon weapon and a way to build the cards for whichever one
        the player picks.
        """
        ps = self.ps
        run = getattr(self, "run", ps)
        from combat.weapons.forge import blessing_levels, forge_eligible
        from progression.blessings import get_rules
        from progression.blessings.offer import forge_offers_for
        from ui.forge_rail import rows_for
        need = get_rules(run.content).forge_requires_levels
        run.particles.burst(it.pos, it.colour, count=16, speed=160, life=0.5)
        if not any(forge_eligible(w, need) for w in run.player.weapons):
            ps.notice(self.forge_requirements(need))
            return
        rows = rows_for(run.player.weapons, need, blessing_levels,
                        forged_name=lambda w: w.name)
        offers = lambda w: forge_offers_for(run.player, run.content, w)
        ps._suspend_mouse()
        from game.states.level_up_state import LevelUpState
        ps.game.state_machine.push(
            LevelUpState(ps.game), player=run.player,
            weapon_rows=rows, offers_for=offers,
            # Names both halves, as it did before the picker: which weapon was
            # reforged is no longer obvious now that the player chose it from a
            # list of several.
            on_done=lambda u: ps.notice(
                f"The {str(u.weapon).replace('_', ' ')} is reforged: {u.title}."),
            title="The Forge  -  choose a weapon to reforge", cancelable=True,
            hint=("Up/Down pick the weapon    -    1/2/3 or Left/Right + Enter "
                  "to forge    -    ESC to leave"))

    def forge_requirements(self, need: int) -> str:
        """The message for a Forge with nothing to work on."""
        from combat.weapons.forge import blessing_levels
        ps = self.ps
        run = getattr(self, "run", ps)
        unforged = [w for w in run.player.weapons if w.forge is None and not w.is_summon]
        if not unforged:
            return "Every weapon is already forged."
        w = min(unforged, key=lambda w: need - blessing_levels(w))
        missing = need - blessing_levels(w)
        return (f"The Forge needs a weapon with {need} blessings: "
                f"the {w.name} needs {missing} more.")

    def use_merchant(self, it: Interactable) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        if not ps.spend_gold(it.cost):
            return
        it.used = True
        ps._drop_item(max(2, int(1 + ps.stats["time"] // 80)))
        ps.particles.burst(it.pos, it.colour, count=20, speed=180, life=0.5)
