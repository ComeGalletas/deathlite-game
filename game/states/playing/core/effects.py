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

`_death_fx` and `_explosions` hold `TimedVisual` entries
(`core/timed_visual.py`, SYS-009); they were a positional list and a dict.
"""
from __future__ import annotations

import pygame

import math

from entities.hazard import Hazard
from game.states.playing.visual import elements as element_fx
from entities.melee_hitbox import MeleeHitbox
from game.events import Events
from game.assets import get_assets
from systems.animation import Animator
from game.states.playing.core.timed_visual import TimedVisual
from game import config

_HERO_HAZARD_COLOUR = (255, 150, 60)   # P3: the Meteor Hammer's crater
_TICK_LIFE = 0.03                       # P3: a hero hazard's bite lives one frame
from world.elevation import NONE as _NO_LEVEL


class TransientFx:
    def __init__(self, ps) -> None:
        self.ps = ps
        # A bare namespace standing in for the state (the tests' fakes) is
        # its own run: it carries the pools and services under the same names.
        self.run = getattr(ps, "run", ps)

    # --- the hero's spawns (structure review, D2) -------------------
    # The callbacks every `FireContext` and summon carries: they used to be
    # methods of the state, reached back through `ps`. `PlayingState` keeps
    # `_spawn_projectile` / `_spawn_summon` / `_spawn_impact` /
    # `_spawn_hero_hazard` as forwarders for the tests that call them.
    def resolve_visual(self, kw: dict) -> None:
        """Fill `color` / `style` / `fx` from `data/weapons/weapon_visuals.json` for a
        spawn that named its `weapon_id`. An explicit value in `kw` (e.g. the
        wolf's bite) wins; a spawn with no `weapon_id` keeps the pool default."""
        content = self.run.content
        wid = kw.get("weapon_id", "")
        # P3: a forged weapon may name its Forge's look (`visual`); it falls
        # back to the base weapon's entry when the Forge has none.
        vid = kw.pop("visual", None)
        if not wid and not vid:
            return
        if vid and vid in content.weapon_visuals:
            vis = content.weapon_visual(vid)
        else:
            vis = content.weapon_visual(wid)
        kw.setdefault("color", vis.color)
        kw.setdefault("style", vis.style)
        kw.setdefault("fx", vis.fx)
        # M6: an element-carrying shot is tinted toward its element, so
        # a player can see which attacks are the infused ones. The M8
        # visual system replaces this with the shared profiles.
        element = kw.get("element")
        if element:
            kw["color"] = element_fx.blend(kw["color"], element_fx.tint(element))

    def spawn_projectile(self, **kw):
        from game.states.playing.visual import slash_fx
        proj = self.run.projectiles.acquire()
        if proj is None:
            return None
        self.resolve_visual(kw)
        proj.reset(**kw)
        # LD-9 D10: stamp the floor it leaves from, at the muzzle. See
        # `block_on_terrain`.
        self.stamp_fire_level(proj)
        slash_fx.spawn_from_cone(self.ps, proj)     # a sequence weapon's swing visual
        self.run.game.audio.play_shoot()
        return proj

    def spawn_summon(self, **kw):
        s = self.run.summons.acquire()
        if s is None:
            return None
        self.resolve_visual(kw)
        kw.pop("style", None)                 # summons dispatch their draw on `kind`
        s.reset(**kw)
        return s

    def spawn_impact(self, *, pos, radius, rig, weapon_id="", anim="loop",
                     infusion=None) -> None:
        """CR1: the Hammer's impact sheet at the blow; the totem bolt's burst."""
        from game.states.playing.visual import slam_fx
        slam_fx.spawn_impact(self.ps, pos=pos, radius=radius, rig=rig,
                             infusion=infusion,
                             weapon_id=weapon_id, anim=anim)

    def spawn_hero_hazard(self, *, pos, radius, dps, duration, weapon_id="",
                          source_tags=()) -> None:
        """P3: a hero-owned ground hazard (Meteor Hammer's crater)."""
        self.spawn_hazard(pos, radius, dps, duration, owner="player",
                          weapon_id=weapon_id, source_tags=source_tags)

    def update_summons(self, dt: float) -> None:
        """The summons' frame (spec 5.8): each hunts from the same view of
        the field the hero's weapons get."""
        from types import SimpleNamespace
        run = self.run
        sctx = SimpleNamespace(enemies=run.targetables(),
                               spawn_projectile=self.ps._spawn_projectile,
                               player_pos=run.player.pos,
                               attack_speed_mult=self.ps.buffs.attack_speed_mult())
        for s in run.summons:
            s.update(dt, sctx)
        run.summons.sweep()

    # --- hostile projectiles ----------------------------------
    def fire_hostile(self, *, pos, vel, damage, radius, style: str = "",
                     fx: dict | None = None, pierce: int = 0,
                     lifetime: float = 6.0, stop_after: float = 0.0,
                     blast_radius: float = 0.0, inert: bool = False) -> None:
        """One enemy shot.

        `style` / `fx` / `pierce` were added in R1 of
        `journals/enemy_roster_expansion_journal.md`. Until then this method
        dropped them, which is why *every* hostile shot in the game was the
        same red-tinted `arrow` -- the slingshot gnome's own acorn art had sat
        unread since it was delivered. `Projectile.reset` had always taken all
        three; this call site was the only thing in the way.

        The defaults are exactly the old behaviour, so an enemy whose JSON
        block names no shot art still fires the red arrow.
        """
        proj = self.run.hostiles.acquire()
        if proj is None:
            return
        proj.reset(pos=pos, vel=vel, damage=damage, radius=radius,
                   lifetime=lifetime, color=(255, 110, 90), hostile=True,
                   style=style, fx=fx, pierce=int(pierce),
                   stop_after=stop_after, blast_radius=blast_radius,
                   inert=inert)
        self.stamp_fire_level(proj)

    def stamp_fire_level(self, proj) -> None:
        """Record the elevation a shot leaves from, for `block_on_terrain`.

        Sampled at the muzzle rather than on the projectile's first update: a
        fast shot has already travelled several pixels by then, which at a
        terrace rim is enough to sample the tile beyond the edge and give the
        shot the wrong floor to be judged against."""
        levels = getattr(self.run.game_map, "_levels", None)
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
        levels = getattr(self.run.game_map, "_levels", None)
        if levels is None:
            return
        here = levels.top_at_point(proj.pos.x, proj.pos.y)
        if here != _NO_LEVEL and here > proj.fire_level:
            self.run.particles.burst(proj.pos, proj.color, count=3, speed=70,
                                    life=0.2, radius=2)
            proj.active = False

    def block_on_obstacle(self, proj) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        if not proj.active or proj.chain_left or proj.orbit_speed or proj.no_block:
            return
        if run.game_map.blocking_obstacle_hit(proj.pos, proj.radius) is not None:
            run.particles.burst(proj.pos, proj.color, count=3, speed=70,
                               life=0.2, radius=2)
            proj.active = False

    def _terrain_stops(self, proj, pos) -> bool:
        """Would a bouncing shot at `pos` be stopped by the terrain: a
        terrace above the floor it was fired from (the D10 rule), or ground
        it cannot roll on at all -- a cliff face, the shoreline, the sea?"""
        gm = self.run.game_map
        levels = getattr(gm, "_levels", None)
        if levels is not None and proj.fire_level != _NO_LEVEL:
            here = levels.top_at_point(pos.x, pos.y)
            if here != _NO_LEVEL and here > proj.fire_level:
                return True
        return not gm.is_walkable(pos, proj.radius)

    def bounce(self, proj, before) -> None:
        """A pinball (buff buildings) reflects off what an ordinary shot dies
        against: an obstacle, about the normal from the obstacle's centre;
        terrain, about the axis it crossed (probed one axis at a time, both
        at a corner). Each bounce costs one of `bounces_left`; the last one
        spends the ball."""
        ps = self.ps
        run = getattr(self, "run", ps)
        if not proj.active:
            return
        hit = run.game_map.blocking_obstacle_hit(proj.pos, proj.radius)
        if hit is not None:
            n = proj.pos - hit.pos
            if n.length_squared() < 1e-6:
                n = -proj.vel
            n = n.normalize()
            proj.vel -= 2.0 * proj.vel.dot(n) * n
            proj.pos.update(hit.pos + n * (hit.radius + proj.radius + 1.0))
        elif self._terrain_stops(proj, proj.pos):
            along_x = pygame.Vector2(proj.pos.x, before.y)
            along_y = pygame.Vector2(before.x, proj.pos.y)
            flip_x = self._terrain_stops(proj, along_x)
            flip_y = self._terrain_stops(proj, along_y)
            if not flip_x and not flip_y:
                flip_x = flip_y = True                    # a corner: straight back
            if flip_x:
                proj.vel.x = -proj.vel.x
            if flip_y:
                proj.vel.y = -proj.vel.y
            proj.pos.update(before)
        else:
            return
        proj.bounces_left -= 1
        run.particles.burst(proj.pos, proj.color, count=4, speed=90, life=0.25, radius=2)
        if proj.bounces_left <= 0:
            proj.active = False

    def update_projectiles(self, dt: float) -> None:
        """Advance both projectile pools, block them on obstacles, and drop
        hostile shots that leave the world margin. A player projectile carrying
        a `fx.trail` spec sheds a fading dust puff every `spacing` world px."""
        ps = self.ps
        run = getattr(self, "run", ps)
        for p in run.projectiles:
            before = pygame.Vector2(p.pos)
            p.update(dt)
            self.ride_stuck(p)
            if p.bounces_left > 0:
                self.bounce(p, before)
            else:
                self.block_on_obstacle(p)
                self.block_on_terrain(p)
            self._shed_trail(p, (p.pos - before).length())
            if p.blast_radius > 0.0 and not p.active and not p.detonated:
                self.detonate(p)        # fuse ran out, or the bomb was blocked
        run.projectiles.sweep()
        for p in run.hostiles:
            p.update(dt)
            if not ps._in_world_margin(p.pos, 60):
                p.active = False
            else:
                self.block_on_obstacle(p)
                self.block_on_terrain(p)
            # An enemy bomb blows up where it stopped. The hero's bombs go
            # through `detonate`, which spawns the blast into the *player's*
            # projectile pool and would hurt enemies; a hostile one is an
            # `explosion`, which is the enemy side's area damage and hits the
            # player (`journals/bomb_fish_journal.md`).
            if p.blast_radius > 0.0 and not p.active and not p.detonated:
                p.detonated = True
                # No screen-shake for the thrown bomb (owner, 2026-09-19):
                # the Bloat lobs one every few seconds and a shake per landing
                # was too much. The corpse blast on death keeps its shake.
                self.explosion(pygame.Vector2(p.pos), p.blast_radius, p.damage,
                               shake=False)
        run.hostiles.sweep()

    # --- bombs (six-weapon system P1) ----------------------
    def detonate(self, bomb) -> None:
        """Turn a spent bomb into its blast: a stationary projectile the size
        of `blast_radius` that lives `blast_lifetime` and scores hits through
        the normal resolver (multipliers, crit, knockback, on-hit). Plus the
        ring visual, a burst and a shake. The hero is never hurt by it."""
        ps = self.ps
        run = getattr(self, "run", ps)
        bomb.detonated = True
        pos = pygame.Vector2(bomb.pos)
        blast = ps._spawn_projectile(
            pos=pos, vel=pygame.Vector2(), damage=bomb.damage,
            radius=bomb.blast_radius, lifetime=bomb.blast_lifetime,
            pierce=999, src_weight=bomb.src_weight, weapon_id=bomb.weapon_id,
            source_tags=tuple(bomb.source_tags) + ("blast",), is_crit=bomb.is_crit,
            style="blast", color=(255, 190, 110), no_block=True)
        if blast is not None:
            blast.fire_level = bomb.fire_level
            # The blast *is* the bomb's hit, so it carries the attack's
            # element (§6.3: every hit an attack produces shares it).
            blast.element = bomb.element
            blast.infusion = bomb.infusion
        run._explosions.append(self.burst_visual(
            pos, bomb.blast_radius, rig=self.burst_rig(bomb),
            infusion=bomb.infusion))
        ps.particles.burst(pos, (255, 160, 80), count=18, speed=240, life=0.45)
        ps.shake.add(0.3)
        self.scatter_bomblets(bomb, pos)

    def ride_stuck(self, p) -> None:
        """Sticky Bomb: a bomb stuck to an enemy rides on it; when the enemy
        dies the bomb drops where it was and burns the rest of its fuse."""
        host = p.stuck_to
        if host is None:
            return
        if getattr(host, "alive", False):
            p.pos.update(host.pos)
        else:
            p.stuck_to = None

    def keg_burst(self, pos, shot, frac: float, weapon_id: str, lifetime: float) -> None:
        """Powder Keg: an enemy the Bomb's blast killed bursts for `frac` of
        that blast's damage in 60 % of its radius. `shot` is the killing
        blast's `(tags, damage, radius)`. The burst carries the `keg` tag and
        never bursts again."""
        ps = self.ps
        run = getattr(self, "run", ps)
        tags, damage, radius = shot
        radius = radius * 0.6
        at = pygame.Vector2(pos)
        ps._spawn_projectile(
            pos=at, vel=pygame.Vector2(), damage=damage * frac,
            radius=radius, lifetime=lifetime, pierce=999, src_weight=0.0,
            weapon_id=weapon_id, source_tags=tuple(tags) + ("keg",),
            style="blast", color=(255, 190, 110), no_block=True)
        ps._explosions.append(self.burst_visual(at, radius, rig=self._BOMBLET_BURST_RIG))
        ps.particles.burst(at, (255, 160, 80), count=10, speed=180, life=0.35)

    _BURST_RIG = "explosion"
    # A Cluster Bomb bomblet gets the small sibling of that sheet (owner,
    # 2026-09-12): same pack, same 192 px grid, rounder and two frames
    # shorter, so three simultaneous bomblets read as the blast spreading
    # out rather than as three copies of it.
    _BOMBLET_BURST_RIG = "explosion_small"

    def burst_rig(self, bomb) -> str:
        """Which burst sheet a detonation plays. A bomblet is identified by
        the `cluster` tag it already carries -- the same test that stops it
        scattering again in `scatter_bomblets`."""
        return (self._BOMBLET_BURST_RIG if "cluster" in bomb.source_tags
                else self._BURST_RIG)

    def burst_visual(self, pos, radius: float, rig: str | None = None,
                     infusion=None) -> TimedVisual:
        """An `_explosions` entry that plays `rig`'s one-shot `burst` scaled
        to the blast diameter, and lives exactly as long as the strip.
        Without the rig it is the plain expanding ring the other explosions
        use. `rig` defaults to the Bomb's own `explosion`.

        `infusion` colours the burst where the Bomb was infused (M13):
        the explosion keeps its own art -- it is the Bomb's, not the
        element's -- and is recoloured for the element rather than
        replaced."""
        rig = rig or self._BURST_RIG
        assets = get_assets()
        n = assets.frame_count(rig, "burst")
        if n <= 0:
            return TimedVisual(pygame.Vector2(pos), radius=radius, dur=0.35,
                               infusion=infusion)
        return TimedVisual(pygame.Vector2(pos), radius=radius,
                           dur=n / assets.fps(rig, "burst"), infusion=infusion,
                           anim=Animator(assets, rig, start="burst"))

    _BOMB_RIG = "bomb"

    def bomblet_scale(self, mult: float):
        """The `fx.scale` a bomblet draws its bomb sprite at: the `bomb`
        rig's own `scale`, times `cluster_radius_mult`.

        The owner wants a bomblet visibly smaller than the bomb that threw it
        (2026-09-12) and no second hand-tuned number for it, so the sprite
        rides the same ratio as the blast: shrink the blast and the ball
        shrinks with it, and there is nothing to keep in sync. `None` when
        the rig is missing -- `bomb.py` then falls back to the disc.
        """
        scale = get_assets().scale_for(self._BOMB_RIG)
        if not scale:
            return None
        return (max(1.0, scale[0] * mult), max(1.0, scale[1] * mult))

    def scatter_bomblets(self, bomb, pos) -> None:
        """P3 Cluster Bomb: the blast throws `cluster_count` lighter bomblets
        outward; each lands and goes off after `cluster_fuse`. Bomblets carry
        the `cluster` tag and never scatter again.

        A bomblet wears the parent's bomb sprite at `cluster_radius_mult` of
        its size, and never the rolling `spin` strip -- `bomb.anim_for` reads
        the `cluster` tag and holds the lit fuse, so a scatter reads as the
        explosion spreading out rather than as three bombs being thrown
        (owner, 2026-09-12). All `n` share one `cluster_fuse`, so they go off
        together, which is the same intent.
        """
        ps = self.ps
        run = getattr(self, "run", ps)
        w = run.player.weapon_by_id(bomb.weapon_id) if bomb.weapon_id else None
        if w is None or "cluster" in bomb.source_tags:
            return
        n = int(w.effect("cluster_count"))
        if n <= 0:
            return
        fx = w.effects
        speed = float(fx.get("cluster_speed", 180.0))
        fuse = float(fx.get("cluster_fuse", 0.5))
        radius_mult = float(fx.get("cluster_radius_mult", 0.6))
        scale = self.bomblet_scale(radius_mult)
        base = run.rng.random() * math.tau
        for i in range(n):
            a = base + math.tau * i / n
            ps._spawn_projectile(
                pos=pos, vel=pygame.Vector2(math.cos(a), math.sin(a)) * speed,
                damage=bomb.damage * float(fx.get("cluster_damage_mult", 0.4)),
                radius=max(3.0, bomb.radius * 0.7), lifetime=fuse, pierce=0,
                src_weight=bomb.src_weight * 0.5, weapon_id=bomb.weapon_id,
                source_tags=tuple(bomb.source_tags) + ("cluster",),
                is_crit=bomb.is_crit, inert=True, stop_after=fuse * 0.5,
                blast_radius=bomb.blast_radius * radius_mult,
                blast_lifetime=bomb.blast_lifetime,
                element=bomb.element, infusion=bomb.infusion,
                fx={"scale": scale} if scale else {})

    # --- ground hazards (spec 5.6) --------------------------
    def spawn_hazard(self, pos, radius, dps, duration, tick_interval=None,
                     sprite=None, owner="enemy", weapon_id="", source_tags=()) -> None:
        colour = _HERO_HAZARD_COLOUR if owner == "player" else (200, 90, 220)
        self.run.hazards.append(
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
        run = getattr(self, "run", ps)
        for hz in run.hazards:
            hz.update(dt)
            if hz.owner == "player":
                if hz.alive:
                    self.hero_hazard_tick(hz, dt)
                continue
            if hz.alive and hz.contains(run.player.pos, run.player.radius):
                bite = hz.due_damage(dt)       # dps * tick_interval per interval
                if bite > 0.0:
                    taken = run.player.take_damage(bite)
                    if taken > 0:
                        ps.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)
            else:
                hz.reset_ticks()               # partial exposure does not bank
        run.hazards = [h for h in run.hazards if h.alive]

    # --- melee attack hitboxes (chaser-style front-facing swing) ---
    def melee_hit(self, pos, radius, damage, duration) -> None:
        self.run.melee_hitboxes.append(MeleeHitbox(pos.x, pos.y, radius, damage, duration))

    def update_melee_hitboxes(self, dt: float) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        for hb in run.melee_hitboxes:
            hb.update(dt)
            if hb.alive and hb.contains(run.player.pos, run.player.radius):
                taken = run.player.take_damage(hb.consume())
                if taken > 0:
                    ps.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)
        run.melee_hitboxes = [h for h in run.melee_hitboxes if h.alive]

    # --- blast visuals -------------------------------------
    def explosion(self, pos: pygame.Vector2, radius: float, damage: float,
                  shake: bool = True) -> None:
        """The enemy side's area damage: ring, burst, and a hit on the player
        if they stand inside `radius`. `shake` is on for the corpse blast an
        exploder leaves when it dies, and off for the Bloat's thrown bomb."""
        ps = self.ps
        run = getattr(self, "run", ps)
        run._explosions.append(TimedVisual(pygame.Vector2(pos), radius=radius, dur=0.35))
        run.particles.burst(pos, (255, 160, 80), count=22, speed=260, life=0.5)
        if shake:
            run.shake.add(0.4)
        # UNUSED, ready to implement: the thrown-bomb detonation used to shake
        # the screen too (owner removed it, 2026-09-19). To bring it back drop
        # `shake=False` from the bomb call in `update_projectiles`, or give the
        # bomb its own lighter amplitude here:
        # elif <this is a thrown bomb>:
        #     run.shake.add(0.2)
        if (run.player.pos - pos).length() <= radius + run.player.radius:
            taken = run.player.take_damage(damage)
            if taken > 0:
                ps.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)

    def enemy_explosion(self, pos: pygame.Vector2, radius: float, dmg: float,
                        source=None) -> None:
        """AoE that hurts nearby enemies (not the player) -- blessing procs.

        `source` names the proc, so the blast is attributable. Without it an
        explosion kill credits nothing at all -- `killed_by` stays empty and
        the DPS meter files the damage under "other"."""
        ps = self.ps
        run = getattr(self, "run", ps)
        run._explosions.append(TimedVisual(pygame.Vector2(pos), radius=radius, dur=0.3))
        ps.particles.burst(pos, (255, 150, 70), count=14, speed=200, life=0.4)
        for enemy in ps.grid.query_circle(pos.x, pos.y, radius):
            if enemy.alive and (enemy.pos - pos).length() <= radius + enemy.radius:
                dealt = enemy.take_damage(dmg, source=source)
                if not enemy.alive and source:
                    enemy.killed_by = source
                ps.stats["damage_dealt"] += dealt

    def update_explosions(self, dt: float) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        for ex in run._explosions:
            ex.update(dt)
        ps._explosions = [e for e in ps._explosions if not e.finished]

    # --- shared death poof --------------------------------
    def spawn_death_fx(self, pos, facing: int = 1, scale: float = 1.0,
                       radius: float = float(config.PLAYER_RADIUS)) -> None:
        self.run._death_fx.append(TimedVisual(
            pygame.Vector2(pos), anim=Animator(self.ps.game.assets, "dead", start="loop"),
            facing=1 if facing >= 0 else -1, scale=float(scale), radius=float(radius)))

    def update_death_fx(self, dt: float) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        for fx in run._death_fx:
            fx.update(dt)
        run._death_fx = [fx for fx in run._death_fx if not fx.finished]

    # --- enemy spawn burst -----------------------------------
    def spawn_spawn_fx(self, body) -> None:
        """The purple burst every enemy (and the boss) appears out of --
        `[Animator("enemy_spawn"), body]` on `run._spawn_fx`. The entry keeps
        the body rather than a copy of its position so the ring follows an
        enemy that starts walking inside the burst; a body that dies first
        leaves the ring finishing where it stood. The animator is also hung
        on the body as `_spawn_fx`, which is what the renderer reads to hold
        the sprite back until the ball breaks (the rig's `reveal_frame`).
        Cosmetic only: the body is live, hittable and moving from its first
        frame. `PlayingHost.wake` does not call this -- a dormant enemy
        coming back was never a new spawn."""
        anim = Animator(self.ps.game.assets, "enemy_spawn", start="burst")
        body._spawn_fx = anim
        self.run._spawn_fx.append([anim, body])

    def update_spawn_fx(self, dt: float) -> None:
        ps = self.ps
        run = getattr(self, "run", ps)
        keep = []
        for fx in ps._spawn_fx:
            fx[0].update(dt)
            if fx[0].finished:
                if getattr(fx[1], "_spawn_fx", None) is fx[0]:
                    fx[1]._spawn_fx = None
            else:
                keep.append(fx)
        run._spawn_fx = keep

    # --- projectile dust trail ---------------------------------
    _TRAIL_CAP = 400

    def _shed_trail(self, p, moved: float) -> None:
        """Drop `[Animator("burst"), pos, size, tint, fade]` entries behind a
        moving projectile, one per `spacing` px. Each plays the one-shot dust
        `burst` once (bloom -> scatter -> fade) anchored where it was shed."""
        ps = self.ps
        run = getattr(self, "run", ps)
        tr = p.fx.get("trail") if p.fx else None
        if not tr or not p.active or len(run._trail_fx) >= self._TRAIL_CAP:
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
        run = getattr(self, "run", ps)
        for tr in ps._trail_fx:
            tr[0].update(dt)
        ps._trail_fx = [tr for tr in ps._trail_fx if not tr[0].finished]
