"""Transient effects for PLAYING: hostile projectiles, ground hazards, blast
visuals, and the shared one-shot death poof.

`TransientFx` owns the spawn / per-frame update / cull logic for these, and
the LD-9 D10 elevation rule for shots (`stamp_fire_level` / `block_on_terrain`). The
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

import math

from entities.hazard import Hazard
from entities.melee_hitbox import MeleeHitbox
from game.events import Events
from game.assets import get_assets
from systems.animation import Animator
from game import config

_HERO_HAZARD_COLOUR = (255, 150, 60)   # P3: the Meteor Hammer's crater
_TICK_LIFE = 0.03                       # P3: a hero hazard's bite lives one frame
from world.elevation import NONE as _NO_LEVEL


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
        self.stamp_fire_level(proj)

    def stamp_fire_level(self, proj) -> None:
        """Record the elevation a shot leaves from, for `block_on_terrain`.

        Sampled at the muzzle rather than on the projectile's first update: a
        fast shot has already travelled several pixels by then, which at a
        terrace rim is enough to sample the tile beyond the edge and give the
        shot the wrong floor to be judged against."""
        levels = getattr(self.ps.game_map, "_levels", None)
        if levels is not None:
            proj.fire_level = levels.top_at_point(proj.pos.x, proj.pos.y)

    def block_on_terrain(self, proj) -> None:
        """LD-9 D10: a shot dies against terrain that stands above the floor it
        was fired from.

        The rule, as set with the rest of the phase: a projectile travels over
        its own floor and over anything lower, so shooting *down* off a terrace
        works. Shooting *up* does not -- it hits the cliffside. Together with
        elevation-blind aggro that makes high ground asymmetrically strong,
        which is deliberate: a ranged enemy above can fire down while the
        player's answer hits the wall. It is the first balance lever to reach
        for if plateaus feel unfair.

        `top_at_point` is what makes this land on the *face* rather than on the
        rim above it. A cliff face has no walkable level, so a test against
        `level_at_point` would let the shot through the wall and only kill it
        on the plateau beyond -- reading as if it had passed through the rock.
        The void reports `NONE` and blocks nothing, so a shot still crosses open
        sea between islands.

        Orbiters are exempt for the same reason they skip the obstacle test:
        they are anchored to the player and are not travelling anywhere.
        """
        if (not proj.active or proj.fire_level == _NO_LEVEL or proj.orbit_speed
                or proj.no_block):
            return
        levels = getattr(self.ps.game_map, "_levels", None)
        if levels is None:
            return
        here = levels.top_at_point(proj.pos.x, proj.pos.y)
        if here != _NO_LEVEL and here > proj.fire_level:
            self.ps.particles.burst(proj.pos, proj.color, count=3, speed=70,
                                    life=0.2, radius=2)
            proj.active = False

    def block_on_obstacle(self, proj) -> None:
        ps = self.ps
        if not proj.active or proj.chain_left or proj.orbit_speed or proj.no_block:
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
            self.block_on_terrain(p)
            self._shed_trail(p, (p.pos - before).length())
            if p.blast_radius > 0.0 and not p.active and not p.detonated:
                self.detonate(p)        # fuse ran out, or the bomb was blocked
        ps.projectiles.sweep()
        for p in ps.hostiles:
            p.update(dt)
            if not ps._in_world_margin(p.pos, 60):
                p.active = False
            else:
                self.block_on_obstacle(p)
                self.block_on_terrain(p)
        ps.hostiles.sweep()

    # --- bombs (six-weapon system P1) ----------------------
    def detonate(self, bomb) -> None:
        """Turn a spent bomb into its blast: a stationary projectile the size
        of `blast_radius` that lives `blast_lifetime` and scores hits through
        the normal resolver (multipliers, crit, knockback, on-hit). Plus the
        ring visual, a burst and a shake. The hero is never hurt by it."""
        ps = self.ps
        bomb.detonated = True
        pos = pygame.Vector2(bomb.pos)
        blast = ps._spawn_projectile(
            pos=pos, vel=pygame.Vector2(), damage=bomb.damage,
            radius=bomb.blast_radius, lifetime=bomb.blast_lifetime,
            pierce=999, src_weight=bomb.src_weight, weapon_id=bomb.weapon_id,
            source_tags=bomb.source_tags, is_crit=bomb.is_crit,
            style="blast", color=(255, 190, 110), no_block=True)
        if blast is not None:
            blast.fire_level = bomb.fire_level
        ps._explosions.append(self.burst_visual(pos, bomb.blast_radius))
        ps.particles.burst(pos, (255, 160, 80), count=18, speed=240, life=0.45)
        ps.shake.add(0.3)
        self.scatter_bomblets(bomb, pos)

    _BURST_RIG = "explosion"

    def burst_visual(self, pos, radius: float) -> dict:
        """An `_explosions` entry that plays the `explosion` rig's one-shot
        `burst` (effects/explosion_2.png) scaled to the blast diameter, and
        lives exactly as long as the strip. Without the rig it is the plain
        expanding ring the other explosions use."""
        assets = get_assets()
        n = assets.frame_count(self._BURST_RIG, "burst")
        if n <= 0:
            return {"pos": pos, "radius": radius, "t": 0.0, "dur": 0.35}
        return {"pos": pos, "radius": radius, "t": 0.0,
                "dur": n / assets.fps(self._BURST_RIG, "burst"),
                "anim": Animator(assets, self._BURST_RIG, start="burst")}

    def scatter_bomblets(self, bomb, pos) -> None:
        """P3 Cluster Bomb: the blast throws `cluster_count` lighter bomblets
        outward; each lands and goes off after `cluster_fuse`. Bomblets carry
        the `cluster` tag and never scatter again."""
        ps = self.ps
        w = ps.player.weapon_by_id(bomb.weapon_id) if bomb.weapon_id else None
        if w is None or "cluster" in bomb.source_tags:
            return
        n = int(w.effect("cluster_count"))
        if n <= 0:
            return
        fx = w.effects
        speed = float(fx.get("cluster_speed", 180.0))
        fuse = float(fx.get("cluster_fuse", 0.5))
        base = ps.rng.random() * math.tau
        for i in range(n):
            a = base + math.tau * i / n
            ps._spawn_projectile(
                pos=pos, vel=pygame.Vector2(math.cos(a), math.sin(a)) * speed,
                damage=bomb.damage * float(fx.get("cluster_damage_mult", 0.4)),
                radius=max(3.0, bomb.radius * 0.7), lifetime=fuse, pierce=0,
                src_weight=bomb.src_weight * 0.5, weapon_id=bomb.weapon_id,
                source_tags=tuple(bomb.source_tags) + ("cluster",),
                is_crit=bomb.is_crit, inert=True, stop_after=fuse * 0.5,
                blast_radius=bomb.blast_radius * float(fx.get("cluster_radius_mult", 0.6)),
                blast_lifetime=bomb.blast_lifetime)

    # --- ground hazards (spec 5.6) --------------------------
    def spawn_hazard(self, pos, radius, dps, duration, tick_interval=None,
                     sprite=None, owner="enemy", weapon_id="", source_tags=()) -> None:
        colour = _HERO_HAZARD_COLOUR if owner == "player" else (200, 90, 220)
        self.ps.hazards.append(
            Hazard(pos.x, pos.y, radius, dps, duration, color=colour,
                   tick_interval=tick_interval, sprite=sprite, owner=owner,
                   weapon_id=weapon_id, source_tags=source_tags))

    def hero_hazard_tick(self, hz, dt: float) -> None:
        """P3: a hero-owned hazard bites every `tick_interval` through the
        normal resolver -- a stationary, invisible, weightless one-frame
        projectile the size of the pool, so multipliers and on-hit apply and
        the hero is never hurt."""
        owed = hz.due_damage(dt)
        if owed <= 0.0:
            return
        self.ps._spawn_projectile(
            pos=hz.pos, vel=pygame.Vector2(), damage=owed, radius=hz.radius,
            lifetime=_TICK_LIFE, pierce=999, src_weight=0.0,
            weapon_id=hz.weapon_id, source_tags=hz.source_tags,
            style="hidden", no_block=True)

    def update_hazards(self, dt: float) -> None:
        ps = self.ps
        for hz in ps.hazards:
            hz.update(dt)
            if hz.owner == "player":
                if hz.alive:
                    self.hero_hazard_tick(hz, dt)
                continue
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
            if "anim" in ex:
                ex["anim"].update(dt)
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
