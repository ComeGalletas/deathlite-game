"""Special locations (spec 5.5) for PLAYING.

`SpecialLocations` owns the run's `Interactable` list: it builds them from the
layout, answers "is the hero standing on a usable one?", dispatches the per-kind
`use_*` handler on the `E` key, and drives the elite-arena state machine each
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
from progression.blessings import roll_blessing_choices
from world.procedural import SPECIAL_KINDS

MERCHANT_COST = 30            # in-run gold
ALTAR_HP_COST_FRACTION = 0.25


class SpecialLocations:
    def __init__(self, ps) -> None:
        self.ps = ps

    def build(self) -> None:
        ps = self.ps
        ps.interactables = []
        if ps.game_map.layout is None:
            return
        for room in ps.game_map.layout.rooms:
            if room.kind in SPECIAL_KINDS:
                ps.interactables.append(Interactable(
                    room.kind, room.center.x, room.center.y, cost=MERCHANT_COST))

    def nearby(self):
        ps = self.ps
        for it in ps.interactables:
            if not it.used and it.kind != "elite_arena" and it.in_range(ps.player.pos):
                return it
        return None

    def activate_nearby(self) -> None:
        it = self.nearby()
        if it is None:
            return
        handler = getattr(self, f"use_{it.kind}", None)
        if handler is not None:
            handler(it)

    def grant_random_blessing(self) -> bool:
        ps = self.ps
        choices = roll_blessing_choices(ps.player, ps.blessing_lib, ps.rng, n=1)
        if not choices:
            return False
        choices[0].apply(ps.player)
        ps.particles.burst(ps.player.pos, (150, 190, 255), count=20,
                           speed=180, life=0.6)
        return True

    # --- per-kind handlers --------------------------------------
    def use_shrine(self, it: Interactable) -> None:
        it.used = True
        if not self.grant_random_blessing():
            self.ps.player.heal(30)

    def use_treasure(self, it: Interactable) -> None:
        ps = self.ps
        it.used = True
        ps._drop_item(max(2, int(1 + ps.stats["time"] // 80)))
        ps.particles.burst(it.pos, it.colour, count=24, speed=220, life=0.6)

    def use_fountain(self, it: Interactable) -> None:
        ps = self.ps
        it.used = True
        ps.player.heal(ps.player.max_hp)
        ps.particles.burst(ps.player.pos, it.colour, count=18, speed=140, life=0.6)

    def use_altar(self, it: Interactable) -> None:
        ps = self.ps
        cost = ps.player.max_hp * ALTAR_HP_COST_FRACTION
        if ps.player.hp <= cost + 1:
            return  # too risky -- refuse rather than kill the player
        ps.player.hp -= cost
        it.used = True
        if not self.grant_random_blessing():
            ps.player.heal(cost)  # refund if nothing to grant

    def use_merchant(self, it: Interactable) -> None:
        ps = self.ps
        if ps.stats["gold"] < it.cost:
            return
        ps.stats["gold"] -= it.cost
        it.used = True
        ps._drop_item(max(2, int(1 + ps.stats["time"] // 80)))
        ps.particles.burst(it.pos, it.colour, count=20, speed=180, life=0.5)

    # --- elite arenas -----------------------------------------
    def update_elite_arenas(self) -> None:
        ps = self.ps
        for it in ps.interactables:
            if it.kind != "elite_arena" or it.state == "done":
                continue
            if it.state == "idle" and (ps.player.pos - it.pos).length() < it.radius + 120:
                it.state = "active"
                it.arena_ids = set()
                for _ in range(3):
                    off = pygame.Vector2(ps.rng.uniform(-90, 90),
                                         ps.rng.uniform(-90, 90))
                    ps.spawn.spawn_enemy("elite", at=it.pos + off)
                    it.arena_ids.add(id(ps.enemies[-1]))
                ps._boss_warning_t = 1.6
                ps._boss_name = "Elite Arena"
            elif it.state == "active":
                live = {id(e) for e in ps.enemies if e.alive}
                if not (it.arena_ids & live):
                    it.state = "done"
                    it.used = True
                    ps._drop_item(max(3, int(2 + ps.stats["time"] // 60)))
                    ps.shake.add(0.5)
