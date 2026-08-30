"""Transient effects for PLAYING: hostile projectiles, ground hazards, blast
visuals, and the shared one-shot death poof.

`TransientFx` owns the spawn / per-frame update / cull logic for these. The
containers themselves stay on `PlayingState` (`_explosions`, `_death_fx`,
`hazards`, and the `projectiles` / `hostiles` pools) because `WorldRenderer` and
the tests read them directly; this class only mutates them.

Reads from `PlayingState`: `player`, `game_map`, `grid`, `stats`, `particles`,
`shake`, `game.events`, `projectiles`, `hostiles`, `_in_world_margin`. Writes:
appends/rebuilds `_explosions` / `_death_fx` / `hazards`, sweeps the pools.

Part of the split tracked in `journals/playing_state_refactor.md` (P5).

Deferred: folding `_death_fx` (a positional `[anim, pos, facing, scale, radius]`
list) and `_explosions` (a `{pos, radius, t, dur}` dict) into a `TimedVisual`
dataclass -- `test_enemy_sprite` asserts the list layout, so that is a separate
change once the logic is isolated here.
"""
from __future__ import annotations

import pygame

from entities.hazard import Hazard
from entities.melee_hitbox import MeleeHitbox
from game.events import Events
from systems.animation import Animator
from game import config


class TransientFx:
    def __init__(self, ps) -> None:
        self.ps = ps

    # --- hostile projectiles ----------------------------------
    def fire_hostile(self, *, pos, vel, damage, radius) -> None:
        proj = self.ps.hostiles.acquire()
        if proj is None:
            return
        proj.reset(pos=pos, vel=vel, damage=damage, radius=radius,
                   lifetime=6.0, color=(255, 110, 90), hostile=True)

    def block_on_obstacle(self, proj) -> None:
        ps = self.ps
        if not proj.active or proj.chain_left or proj.orbit_speed:
            return
        if ps.game_map.blocking_obstacle_hit(proj.pos, proj.radius) is not None:
            ps.particles.burst(proj.pos, proj.color, count=3, speed=70,
                               life=0.2, radius=2)
            proj.active = False

    def update_projectiles(self, dt: float) -> None:
        """Advance both projectile pools, block them on obstacles, and drop
        hostile shots that leave the world margin. A player projectile carrying
        a `fx.trail` spec sheds a fading dust puff every `spacing` world px."""
        ps = self.ps
        for p in ps.projectiles:
            before = pygame.Vector2(p.pos)
            p.update(dt)
            self.block_on_obstacle(p)
            self._shed_trail(p, (p.pos - before).length())
        ps.projectiles.sweep()
        for p in ps.hostiles:
            p.update(dt)
            if not ps._in_world_margin(p.pos, 60):
                p.active = False
            else:
                self.block_on_obstacle(p)
        ps.hostiles.sweep()

    # --- ground hazards (spec 5.6) --------------------------
    def spawn_hazard(self, pos, radius, dps, duration, tick_interval=None) -> None:
        self.ps.hazards.append(
            Hazard(pos.x, pos.y, radius, dps, duration, tick_interval=tick_interval))

    def update_hazards(self, dt: float) -> None:
        ps = self.ps
        for hz in ps.hazards:
            hz.update(dt)
            if hz.alive and hz.contains(ps.player.pos, ps.player.radius):
                bite = hz.due_damage(dt)       # dps * tick_interval per interval
                if bite > 0.0:
                    taken = ps.player.take_damage(bite)
                    if taken > 0:
                        ps.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)
            else:
                hz.reset_ticks()               # partial exposure does not bank
        ps.hazards = [h for h in ps.hazards if h.alive]

    # --- melee attack hitboxes (chaser-style front-facing swing) ---
    def melee_hit(self, pos, radius, damage, duration) -> None:
        self.ps.melee_hitboxes.append(MeleeHitbox(pos.x, pos.y, radius, damage, duration))

    def update_melee_hitboxes(self, dt: float) -> None:
        ps = self.ps
        for hb in ps.melee_hitboxes:
            hb.update(dt)
            if hb.alive and hb.contains(ps.player.pos, ps.player.radius):
                taken = ps.player.take_damage(hb.consume())
                if taken > 0:
                    ps.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)
        ps.melee_hitboxes = [h for h in ps.melee_hitboxes if h.alive]

    # --- blast visuals -------------------------------------
    def explosion(self, pos: pygame.Vector2, radius: float, damage: float) -> None:
        ps = self.ps
        ps._explosions.append({"pos": pygame.Vector2(pos), "radius": radius,
                               "t": 0.0, "dur": 0.35})
        ps.particles.burst(pos, (255, 160, 80), count=22, speed=260, life=0.5)
        ps.shake.add(0.4)
        if (ps.player.pos - pos).length() <= radius + ps.player.radius:
            taken = ps.player.take_damage(damage)
            if taken > 0:
                ps.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)

    def enemy_explosion(self, pos: pygame.Vector2, radius: float, dmg: float) -> None:
        """AoE that hurts nearby enemies (not the player) -- blessing procs."""
        ps = self.ps
        ps._explosions.append({"pos": pygame.Vector2(pos), "radius": radius,
                               "t": 0.0, "dur": 0.3})
        ps.particles.burst(pos, (255, 150, 70), count=14, speed=200, life=0.4)
        for enemy in ps.grid.query_circle(pos.x, pos.y, radius):
            if enemy.alive and (enemy.pos - pos).length() <= radius + enemy.radius:
                dealt = enemy.take_damage(dmg)
                ps.stats["damage_dealt"] += dealt

    def update_explosions(self, dt: float) -> None:
        ps = self.ps
        for ex in ps._explosions:
            ex["t"] += dt
        ps._explosions = [e for e in ps._explosions if e["t"] < e["dur"]]

    # --- shared death poof --------------------------------
    def spawn_death_fx(self, pos, facing: int = 1, scale: float = 1.0,
                       radius: float = float(config.PLAYER_RADIUS)) -> None:
        self.ps._death_fx.append(
            [Animator(self.ps.game.assets, "dead", start="loop"),
             pygame.Vector2(pos), 1 if facing >= 0 else -1, float(scale),
             float(radius)])

    def update_death_fx(self, dt: float) -> None:
        ps = self.ps
        for fx in ps._death_fx:
            fx[0].update(dt)
        ps._death_fx = [fx for fx in ps._death_fx if not fx[0].finished]

    # --- projectile dust trail ---------------------------------
    _TRAIL_CAP = 400

    def _shed_trail(self, p, moved: float) -> None:
        """Drop `[Animator("burst"), pos, size, tint, fade]` entries behind a
        moving projectile, one per `spacing` px. Each plays the one-shot dust
        `burst` once (bloom -> scatter -> fade) anchored where it was shed."""
        ps = self.ps
        tr = p.fx.get("trail") if p.fx else None
        if not tr or not p.active or len(ps._trail_fx) >= self._TRAIL_CAP:
            return
        p.trail_shed += moved
        spacing = max(1.0, float(tr.get("spacing", 24)))
        while p.trail_shed >= spacing and len(ps._trail_fx) < self._TRAIL_CAP:
            p.trail_shed -= spacing
            ps._trail_fx.append([
                Animator(ps.game.assets, tr.get("rig", "dust_puff"), start="burst"),
                pygame.Vector2(p.pos),
                tuple(tr.get("scale", (28, 28))),
                tuple(tr["tint"]) if "tint" in tr else None,
                bool(tr.get("fade", False)),
            ])

    def update_trail_fx(self, dt: float) -> None:
        ps = self.ps
        for tr in ps._trail_fx:
            tr[0].update(dt)
        ps._trail_fx = [tr for tr in ps._trail_fx if not tr[0].finished]
