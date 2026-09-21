"""What a kill, a pickup and a level pay out (structure review, D3).

`Rewards` owns the run's payout rules: the gold, gems and drops a kill
leaves, the on-kill blessing effects, the potions collected off the
ground, the boss's reward, and the level-up flow that opens the offering.
It reads and writes the `Run` (`run.stats`, the pools, the player) and
reaches the coordinator only for the two things that are the state's --
suspending the mouse before an overlay, and pushing the level-up screen
onto the stack.

`PlayingState` keeps one-line forwarders (`_apply_on_kill_effects`,
`_roll_potion_drop`, `_collect_potions`, `_open_level_up`,
`_on_boss_killed`, `_drop_item`) for the tests that call them.
"""
from __future__ import annotations

import logging

import pygame

from entities.pickup import XP_TIER_COLORS
from game.events import Events
from progression import potions as potion_rules
from progression.blessings import roll_offering
from progression.items import generate_item

log = logging.getLogger(__name__)


class Rewards:
    def __init__(self, ps) -> None:
        self.ps = ps
        self.run = getattr(ps, "run", ps)
        self.gold_carry = 0.0         # fractions of gold carried between kills
        self.drop_counter = 0         # seeds each dropped item off the run seed
        self.awaiting_level_up = False
        self.boss_defeated = None     # (boss_id, name) once the boss is down

    # --- kills ---------------------------------------------------------
    def on_enemy_killed(self, *, pos, color, xp, tags, elite=False,
                        enemy_id="") -> None:
        run = self.run
        run.particles.burst(pos, color, count=16 if elite else 10,
                            speed=200 if elite else 160, life=0.5)
        # In-run gold for the Merchant, scaled by the Gold Rush blessing (P2);
        # fractions carry over so a +15 % bonus is not rounded away.
        self.gold_carry += (2 if elite else 1) * (1.0 + run.player.stats["gold_gain"])
        whole = int(self.gold_carry)
        run.add_gold(whole)
        self.gold_carry -= whole
        if elite:
            run.shake.add(0.18)
            if run.rng.random() < 0.18:
                self.drop_item(int(1 + run.stats["time"] // 90))
        if enemy_id:
            self.roll_potion_drop(enemy_id, pos)
        gem = run.gems.acquire()
        if gem is not None:
            gem.reset(pos, xp)
            self.ps.buffs.on_gem(gem)          # Magnet pulls a fresh drop at once

    def apply_on_kill_effects(self, enemy) -> None:
        run, player = self.run, self.run.player
        # P2 Bloodletting: the weapon that landed the killing hit may heal.
        killer = player.weapon_by_id(getattr(enemy, "killed_by", ""))
        if killer is not None:
            heal = float(killer.effects.get("on_kill_heal", 0.0))
            if heal > 0.0:
                player.heal(heal)
            # Powder Keg: a kill by a blast (never by a burst) bursts again.
            keg = killer.effect("keg_frac")
            shot = getattr(enemy, "killed_by_shot", None)
            if keg > 0.0 and shot is not None and "blast" in shot[0] and "keg" not in shot[0]:
                self.ps.fx.keg_burst(enemy.pos, shot, keg, killer.weapon_id,
                                     float(killer.definition["blast_lifetime"]))
        for effect, chance, amount in player.blessing_fx.on_kill:
            if run.rng.random() >= chance:
                continue
            if effect == "soul":
                gem = run.gems.acquire()
                if gem is not None:
                    gem.reset(enemy.pos, int(amount) or 3, is_soul=True)
                    self.ps.buffs.on_gem(gem)
            elif effect == "heal":
                player.heal(amount)
            elif effect == "fire_nova" and "burn" in enemy.status:
                self.ps.fx.enemy_explosion(enemy.pos, 70.0, float(amount) or 16.0,
                                           source="fire_nova")
            elif effect == "shock_spread" and "shock" in enemy.status:
                self.spread_status(enemy.pos, "shock", 3.0, 0.12)

    def spread_status(self, pos: pygame.Vector2, status: str, dur: float,
                      potency: float) -> None:
        best, best_d2 = None, 260.0 ** 2
        for enemy in self.run.grid.query_circle(pos.x, pos.y, 260):
            if not enemy.alive:
                continue
            d2 = (enemy.pos - pos).length_squared()
            if d2 < best_d2:
                best, best_d2 = enemy, d2
        if best is not None:
            best.status.apply(status, dur, potency)

    def on_boss_killed(self) -> None:
        run = self.run
        boss = run.boss
        reward = getattr(boss, "reward_currency", 50)
        run.stats["currency"] += reward
        run.ledger.kill(boss)
        # The boss's "meaningful reward" (spec 3.7): a high-tier item.
        self.drop_item(item_level=max(3, int(1 + run.stats["time"] // 60)))
        run.particles.burst(boss.pos, boss.color, count=60, speed=340, life=0.9)
        self.ps.fx.spawn_death_fx(boss.pos, getattr(boss, "_facing", 1),
                                  scale=1.4, radius=boss.radius)   # (mostly unseen -- victory follows)
        run.shake.add(1.0)
        run.game.events.publish(Events.BOSS_KILLED, name=boss.name)
        # Kept before the boss is dropped: the victory screen names the boss
        # that fell, and with a pool to draw from that is the one fact that
        # tells two wins apart.
        self.boss_defeated = (boss.boss_id, boss.name)
        run.boss = None
        self.ps.run_end.begin(victory=True)

    # --- drops ---------------------------------------------------------
    def roll_potion_drop(self, enemy_id: str, pos) -> None:
        """CB-8: a kill's chance at a health potion, from the enemy's *base* HP.

        Base HP, not `enemy.max_hp`: the director scales the live value by
        `hp_mult` as a run goes on, so rolling against it would walk every
        enemy up to the cap. Bosses never reach here -- `on_boss_killed` is a
        separate handler.
        """
        run = self.run
        table = run.content.potions
        definition = run.content.enemies.get(enemy_id)
        if definition is None:
            return
        rarity = potion_rules.roll(float(definition["hp"]), table, run.rng)
        if rarity is None:
            return
        potion = run.potions.acquire()
        if potion is None:
            return                      # pool capped: drop nothing, never crash
        potion.reset(pos, rarity, potion_rules.heal_amount(rarity, table))

    def collect_potions(self, dt: float) -> None:
        """CB-8: advance the dropped potions and heal on pickup.

        `HealthPotion.update` refuses to be collected at full HP, so a potion
        waits on the ground rather than being spent for a sliver.
        """
        run, player = self.run, self.run.player
        for potion in run.potions:
            if not potion.update(dt, player):
                continue
            before = player.hp
            player.heal(potion.heal)
            gained = player.hp - before
            run.stats["potions"] += 1
            run.stats["potion_healing"] += gained
            run.particles.burst(player.pos,
                                potion_rules.colour(potion.rarity, run.content.potions),
                                count=14, speed=140, life=0.45, radius=2)
            if gained > 0.0:
                run.damage_numbers.add(player.pos, gained, healing=True)
        run.potions.sweep()

    def drop_item(self, item_level: int) -> None:
        run = self.run
        self.drop_counter += 1
        item = generate_item(
            run.content, seed=run.seed * 1000 + self.drop_counter,
            item_level=max(1, item_level), luck=run.player.stats["luck"])
        run.stats["dropped_items"].append(item.to_dict())
        log.info("dropped %s", item.short())

    # --- experience --------------------------------------------------
    def collect_gems(self, dt: float) -> None:
        """The XP gems flying to the hero, and what each one pays."""
        run, player = self.run, self.run.player
        xp_mult = 1.0 + player.stats["xp_gain"]
        soul_heal = player.blessing_fx.soul_heal
        for gem in run.gems:
            if gem.update(dt, player):
                run.levels.add_xp(max(1, int(round(gem.value * xp_mult))))
                run.stats["xp"] = run.levels.total_xp
                if getattr(gem, "is_soul", False) and soul_heal:
                    player.heal(soul_heal)
                run.particles.burst(player.pos,
                                    XP_TIER_COLORS.get(gem.tier, (200, 255, 200)),
                                    count=5, speed=110, life=0.3, radius=2)
                run.game.events.publish(Events.XP_COLLECTED, value=gem.value)
        run.gems.sweep()

    def open_level_up(self) -> None:
        run = self.run
        # P2: every level-up is a blessing offering (design §21) -- stat and
        # weapon blessings for what the hero owns, plus weapon grants while
        # the slots are open, rolled by the data's weights.
        choices = roll_offering(run.player, run.content, run.rng)
        if not choices:
            run.levels.consume_pending()
            return
        run.game.events.publish(Events.PLAYER_LEVELED, level=run.levels.level)
        self.awaiting_level_up = True
        self.ps._suspend_mouse()
        from game.states.level_up_state import LevelUpState
        run.game.state_machine.push(LevelUpState(run.game), player=run.player,
                                    choices=choices, on_done=self.on_level_up_chosen)

    def on_level_up_chosen(self, upgrade) -> None:
        self.run.levels.consume_pending()
        self.awaiting_level_up = False
        log.info("level %d: took %s", self.run.levels.level, upgrade.id)
