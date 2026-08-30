"""Combat / collision resolution for PLAYING.

`CombatResolver.resolve()` runs the four hit-detection passes each frame, after
`_phase_combat` has fired the hero's weapons:

    player projectiles -> enemies/boss
    hostile projectiles -> player
    enemy/boss body contact -> player
    cull dead enemies (fires death FX + ENEMY_KILLED, ends the run on boss death)

Reads from `PlayingState`: `projectiles`, `hostiles`, `grid`, `enemies`, `boss`,
`player`, `rng`, `stats`, `damage_numbers`, `particles`, `game.events`,
`_targetables()`. Writes: `stats["damage_dealt"]` / `stats["kills"]`, reassigns
`ps.enemies` (survivors), and projectile fields. Calls back into `PlayingState`
for the run-scoped effects it doesn't own: `_on_boss_killed`,
`_apply_on_kill_effects`, `_explosion`, `_spawn_death_fx`.

Part of the split tracked in `journals/playing_state_refactor.md` (P3).
"""
from __future__ import annotations

import math

from combat.knockback import knock_split
from entities.projectile import Projectile
from game import config
from game.events import Events
from systems.collision import circles_overlap

_ENEMY_DEATH_FX_SCALE = 0.55        # enemy death poof at 55% (hero stays 1.0)


class CombatResolver:
    def __init__(self, ps) -> None:
        self.ps = ps

    def resolve(self) -> None:
        self.projectile_hits()
        self.hostile_hits()
        self.enemy_contact()
        self.cull_dead_enemies()

    # --- player projectiles -> enemies / boss --------------------
    def projectile_hits(self) -> None:
        ps = self.ps
        # Dev toggle: weapons keep firing (animation, projectiles, knockback all
        # play) but a hit deals no HP damage and applies no on-hit status, so
        # enemies never die from the hero.
        no_dmg = ps.dev_mode and ps._dev_no_damage
        targets = ps._targetables()
        for proj in ps.projectiles:
            if not proj.active:
                continue
            near = ps.grid.query_circle(proj.pos.x, proj.pos.y, proj.radius + 40)
            if ps.boss is not None and ps.boss.alive:
                near = near + [ps.boss]
            for enemy in near:
                if not enemy.alive or id(enemy) in proj.hit_ids:
                    continue
                if not circles_overlap(proj.pos.x, proj.pos.y, proj.radius,
                                       enemy.pos.x, enemy.pos.y, enemy.radius):
                    continue
                if proj.cone_half_angle > 0.0 and not self.in_cone(proj, enemy):
                    continue

                amount = 0.0 if no_dmg else proj.damage * self.damage_multiplier(proj, enemy)
                dealt = enemy.take_damage(amount)
                proj.hit_ids.add(id(enemy))
                ps.stats["damage_dealt"] += dealt
                ps.damage_numbers.add(enemy.pos, dealt, proj.is_crit)
                ps.particles.burst(proj.pos, proj.color, count=4, speed=90,
                                   life=0.22, radius=2)
                if proj.src_weight:
                    # CB-3: same weight-split as a bump, base scaled by the
                    # weapon's weight; only the target is pushed (decision 7).
                    _, push = knock_split(proj.src_weight, enemy.weight,
                                          config.HIT_KNOCK_GAIN * proj.src_weight)
                    enemy.apply_knockback(enemy.pos - proj.pos, push)
                if not no_dmg:
                    self.apply_on_hit_effects(proj, enemy)
                ps.game.events.publish(Events.DAMAGE_DEALT, amount=dealt)
                if proj.chain_left > 0 and self.chain_to_next(proj, targets):
                    continue
                proj.on_hit()
                if not proj.active:
                    break

    def damage_multiplier(self, proj: Projectile, enemy) -> float:
        """Blessing tag bonuses + Shock + status-vulnerability synergy."""
        fx = self.ps.player.blessing_fx
        mult = 1.0 + fx.tag_bonus(proj.source_tags, getattr(enemy, "is_elite", False))
        mult *= enemy.status.damage_taken_multiplier()
        mult += fx.vuln_bonus(proj.source_tags, enemy.status)
        return mult

    def apply_on_hit_effects(self, proj: Projectile, enemy) -> None:
        ps = self.ps
        fx = ps.player.blessing_fx
        for status, tag, chance, dur, potency in fx.on_hit:
            if tag is not None and tag not in proj.source_tags:
                continue
            if ps.rng.random() < chance:
                enemy.status.apply(
                    status,
                    dur * (1.0 + fx.tuned(status, "duration")),
                    potency * (1.0 + fx.tuned(status, "potency")),
                    bonus_max_stacks=int(fx.tuned(status, "max_stacks")))
        # Nihil / Cursebrand: first hit on each enemy applies Shock.
        if ps.player.trait == "cursebrand" and id(enemy) not in ps.player._hexed:
            ps.player._hexed.add(id(enemy))
            enemy.status.apply("shock", 4.0, 0.10)

    @staticmethod
    def in_cone(proj: Projectile, enemy) -> bool:
        to_enemy = enemy.pos - proj.pos
        if to_enemy.length_squared() < 1e-6:
            return True
        cos_limit = math.cos(proj.cone_half_angle)
        return proj.cone_dir.normalize().dot(to_enemy.normalize()) >= cos_limit

    @staticmethod
    def chain_to_next(proj: Projectile, targets) -> bool:
        best, best_d2 = None, proj.chain_range ** 2
        for enemy in targets:
            if not enemy.alive or id(enemy) in proj.hit_ids:
                continue
            d2 = (enemy.pos - proj.pos).length_squared()
            if d2 < best_d2:
                best, best_d2 = enemy, d2
        if best is None:
            return False
        proj.vel = (best.pos - proj.pos).normalize() * (proj.vel.length() or 260.0)
        proj.chain_left -= 1
        proj.lifetime = max(proj.lifetime, 0.4)
        return True

    # --- hostile projectiles -> player -------------------------
    def hostile_hits(self) -> None:
        ps = self.ps
        pr = ps.player.radius
        for proj in ps.hostiles:
            if not proj.active:
                continue
            if circles_overlap(proj.pos.x, proj.pos.y, proj.radius,
                               ps.player.pos.x, ps.player.pos.y, pr):
                taken = ps.player.take_damage(proj.damage)
                proj.active = False
                if taken > 0:
                    ps.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)

    # --- enemy / boss body contact -> player -------------------
    def enemy_contact(self) -> None:
        """Each touching enemy deals a bite (`contact_damage * contact_interval`,
        before armor) once per its `contact_interval`; `contact_cd` -- ticked
        down in Enemy/Boss.update -- paces it."""
        ps = self.ps
        pr = ps.player.radius
        contacts = list(ps.grid.query_circle(ps.player.pos.x, ps.player.pos.y, pr + 48))
        if ps.boss is not None and ps.boss.alive:
            contacts.append(ps.boss)
        for enemy in contacts:
            if not enemy.alive or enemy.contact_cd > 0.0:
                continue
            if not getattr(enemy, "contact_damage_enabled", True):
                continue
            if circles_overlap(ps.player.pos.x, ps.player.pos.y, pr,
                               enemy.pos.x, enemy.pos.y, enemy.radius):
                enemy.contact_cd = enemy.contact_interval
                taken = ps.player.take_damage(
                    enemy.contact_damage * enemy.contact_interval)
                if taken > 0:
                    ps.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)

    # --- reap the dead ----------------------------------------
    def cull_dead_enemies(self) -> None:
        ps = self.ps
        if ps.boss is not None and not ps.boss.alive:
            ps._on_boss_killed()

        if not ps.enemies:
            return
        survivors = []
        for e in ps.enemies:
            if e.alive:
                survivors.append(e)
                continue
            # Death effects fire NOW, at the instant of death.
            ps.stats["kills"] += 1
            if e.explode_radius > 0.0:
                ps.fx.explosion(e.pos, e.explode_radius, e.explode_damage)
            ps._apply_on_kill_effects(e)
            ps.game.events.publish(Events.ENEMY_KILLED, pos=e.pos.copy(),
                                   color=e.color, xp=e.xp_reward, tags=e.tags,
                                   elite=e.is_elite)
            ps.fx.spawn_death_fx(e.pos, getattr(e, "_facing", 1),
                                 scale=_ENEMY_DEATH_FX_SCALE, radius=e.radius)
        ps.enemies = survivors
