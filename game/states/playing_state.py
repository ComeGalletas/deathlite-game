"""PLAYING: the actual run.

Pipeline order (spec 1.3): INPUT -> UPDATE -> COLLISION/COMBAT -> PROGRESSION,
with RENDER in draw(). Milestone 4 adds: 10 enemy variants driven by
`entities.ai` behaviours, the phase-based `SpawnDirector` with HP/speed scaling,
hostile projectiles + explosions that damage the player, two more weapons
(orbit, cone), and the telegraphed multi-pattern `Boss` whose death wins the run.
"""
from __future__ import annotations

import logging
import math
import random
import time
from types import SimpleNamespace

import pygame

# `pygame.gfxdraw` is imported lazily in `_draw_cone` (via `_get_gfxdraw`): a
# top-level `import pygame.gfxdraw` trips pygbag's import hook, which treats the
# dotted name as a PyPI package. `None` -> fall back to `pygame.draw.polygon`.
_gfxdraw = None
_gfxdraw_tried = False


def _get_gfxdraw():
    global _gfxdraw, _gfxdraw_tried
    if not _gfxdraw_tried:
        _gfxdraw_tried = True
        try:
            import pygame.gfxdraw as _gd
            _gfxdraw = _gd
        except Exception:  # not built in this pygame (e.g. some pygbag builds)
            _gfxdraw = None
    return _gfxdraw

from game import config, fonts
from game.content import get_content
from game.events import Events
from game.state import State
from entities.player import Player
from entities.enemy import Enemy
from entities.boss import Boss
from entities.projectile import Projectile
from entities.pickup import XPGem, XP_TIER_COLORS
from entities.summon import Summon
from entities.hazard import Hazard
from entities.interactable import Interactable
from world.procedural import SPECIAL_KINDS
from combat.weapons import Weapon, FireContext
from progression.experience import LevelTracker, xp_for_level
from progression.upgrades import roll_choices
from progression.blessings import BlessingLibrary, roll_blessing_choices, rebuild as rebuild_blessings
from progression.items import Item, generate_item
from progression.stats import FLAT, MULT, PCT, Modifier
from systems.animation import Animator
from systems.camera import Camera
from systems.collision import SpatialGrid, circles_overlap
from systems.object_pool import Pool
from systems.particles import ParticleSystem
from systems.screen_shake import ScreenShake
from ui.hud import HUD
from ui.damage_numbers import DamageNumbers
from world.map import GameMap
from world.pathfinding import NavField
from world.spawning import SpawnDirector

log = logging.getLogger(__name__)

STARTING_WEAPON = "arcane_bolt"
MERCHANT_COST = 30            # in-run gold
ALTAR_HP_COST_FRACTION = 0.25


class PlayingState(State):
    def enter(self, *, seed: int | None = None, character_id: str | None = None,
              dev: bool = False, difficulty: str | None = None, **kwargs) -> None:
        self.content = get_content()
        self.dev_mode = bool(dev)     # developer sandbox: no save, restart on end
        self.difficulty = (difficulty if difficulty in config.DIFFICULTIES
                           else config.DIFFICULTY_DEFAULT)
        self._dev_unlimited_hp = False   # HP ratchet (dev menu D2)
        self._dev_no_attack = False      # hero weapons silenced (dev menu D2)
        self._dev_hp_floor = 0.0
        self._dev_show_colliders = False  # F7 / dev menu: true collider overlay
        self.run_seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.run_seed)

        self.game_map = GameMap(seed=self.run_seed)
        start = self.game_map.center
        self._build_interactables()

        self.character_id = character_id or next(iter(self.content.characters))
        cdef = self.content.character(self.character_id)
        self.player = Player(start.x, start.y,
                             base_stats=cdef.get("base_stats"),
                             trait=cdef.get("trait", ""),
                             character_id=self.character_id)
        weapon_id = cdef.get("starting_weapon", STARTING_WEAPON)
        self.player.weapons = [Weapon(weapon_id, self.content.weapon(weapon_id))]

        # Hero sprite: only the characters that declare a rig get one; the rest
        # keep the primitive circle (fallback in `_draw_player`).
        hero_rig = cdef.get("sprite")
        self._hero_anim = Animator(self.game.assets, hero_rig) if hero_rig else None
        self._hero_has_hurt = (hero_rig is not None
                               and self.game.assets.frame_count(hero_rig, "hurt") > 0)
        # Per-hero accent colour (primitive fallback + any HUD tint); the shared
        # config default covers characters with no `color`.
        self._hero_color = tuple(cdef.get("color", config.COLOR_PLAYER))
        self._death_seq_t: float | None = None   # window held open for the hero death poof

        # Meta-progression + equipped items applied before the run starts.
        self._apply_persistent_bonuses()

        # Blessing library is stashed on the player so apply_blessing can reach it.
        self.blessing_lib = BlessingLibrary(self.content.blessings)
        self.player._blessing_library = self.blessing_lib
        rebuild_blessings(self.player, self.blessing_lib)

        # The world is drawn straight to the screen; `Camera.zoom` magnifies at
        # draw time (config.CAMERA_ZOOM), so sprites stay crisp. HUD is unscaled.
        self.camera = Camera(self.game_map.width, self.game_map.height,
                             config.SCREEN_WIDTH, config.SCREEN_HEIGHT,
                             zoom=config.CAMERA_ZOOM)
        self.camera.snap_to(self.player.pos)

        self.enemies: list[Enemy] = []
        self.boss: Boss | None = None
        self.projectiles: Pool[Projectile] = Pool(Projectile, config.MAX_PROJECTILES, prefill=128)
        self.hostiles: Pool[Projectile] = Pool(Projectile, config.MAX_PROJECTILES, prefill=64)
        self.gems: Pool[XPGem] = Pool(XPGem, config.MAX_PROJECTILES, prefill=64)
        self.summons: Pool[Summon] = Pool(Summon, 32, prefill=8)
        self.hazards: list[Hazard] = []
        self.particles = ParticleSystem()
        self.damage_numbers = DamageNumbers()
        self.shake = ScreenShake()
        self.grid = SpatialGrid()

        # Enemy flow-field navigation (config.ENEMY_PATHFINDING). Built once from
        # the static layout; rebuilt toward the player on a timer in
        # `_update_nav`. Inert until a behaviour reads `ctx.nav_dir` (M4).
        self._nav: NavField | None = None
        self._nav_t = 0.0
        self._nav_rr = 0                  # round-robin index over the nav classes
        self._nav_last_ms = 0.0          # last rebuild cost (debug overlay)
        self._nav_rebuilds = 0
        self._obstacle_grid: SpatialGrid | None = None
        if config.ENEMY_PATHFINDING and self.game_map.layout is not None:
            self._nav = NavField(self.game_map.layout, self.game_map.obstacles)
            self._nav.rebuild(self.player.pos)
            self._nav_t = config.ENEMY_NAV_REBUILD_INTERVAL
            # Static -> built once; `path_chase` reads it for local obstacle
            # avoidance (a push off the nearest prop, on top of the field).
            self._obstacle_grid = SpatialGrid()
            self._obstacle_grid.rebuild(self.game_map.obstacles)

        self.director = SpawnDirector(config.RUN_DURATION_SECONDS, rng=self.rng,
                                      difficulty=self.difficulty)
        self.hud = HUD()
        self.levels = LevelTracker()

        self._explosions: list[dict] = []   # transient blast visuals
        # One-shot death poofs: [Animator("dead"), world_pos, facing]. Any entity
        # (hero or enemy) that dies pushes one; drawn in the depth layer, dropped
        # when the animation finishes.
        self._death_fx: list = []
        self._last_move_dir = pygame.Vector2(1, 0)
        self._awaiting_level_up = False
        self._hurt_flash_t = 0.0
        self._boss_warning_t = 0.0
        self._boss_name = ""
        self._banner_font = fonts.heading(40)
        self._prompt_font = fonts.heading(20)

        # `currency` = Salvage banked to the save at run end (boss + elite arena).
        # `gold` = spent in-run at the Merchant only, never banked.
        self.stats = {"time": 0.0, "level": 1, "kills": 0, "damage_dealt": 0.0,
                      "xp": 0, "currency": 0, "gold": 0, "dropped_items": []}
        self._drop_counter = 0

        # Own our feedback subscriptions so they can be removed cleanly on exit
        # (the bus also carries persistent listeners such as audio).
        bus = self.game.events
        self._subs = [
            (Events.ENEMY_KILLED, self._on_enemy_killed),
            (Events.PLAYER_DAMAGED, self._on_player_damaged),
            (Events.BOSS_SPAWNED, self._on_boss_spawned),
        ]
        for name, handler in self._subs:
            bus.subscribe(name, handler)

    def exit(self) -> None:
        for name, handler in getattr(self, "_subs", ()):
            self.game.events.unsubscribe(name, handler)

    # --- events -------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            from game.states.paused_state import PausedState
            self.game.state_machine.push(PausedState(self.game))
        elif event.key == pygame.K_e:
            self._activate_nearby_interactable()
        elif event.key == pygame.K_BACKQUOTE and self.dev_mode:
            from game.states.dev_menu_state import DevMenuState
            self.game.state_machine.push(DevMenuState(self.game), playing=self)

    def handle_debug_key(self, key: int) -> bool:
        keys = config.DEBUG_KEYS
        if key == keys["toggle_invuln"]:
            self.player.invulnerable = not self.player.invulnerable
            log.info("debug: invulnerable = %s", self.player.invulnerable)
        elif key == keys["spawn_enemy"]:
            self._spawn_enemy("elite" if self.rng.random() < 0.3 else "chaser")
        elif key == keys["grant_xp"]:
            self.levels.add_xp(25)
        elif key == keys["force_level_up"]:
            self.levels.add_xp(xp_for_level(self.levels.level) - self.levels.xp_into_level)
        elif key == keys["spawn_boss"]:
            self._spawn_boss()
        elif key == keys["toggle_collision_vis"]:
            if not self.dev_mode:
                return False                     # collider overlay is dev-only
            self._dev_show_colliders = not self._dev_show_colliders
        else:
            return False
        return True

    # --- pipeline ---------------------------------------------
    def update(self, dt: float) -> None:
        if self._death_seq_t is not None:
            self._run_death_sequence(dt)
            return

        self._phase_input()
        self._phase_update(dt)
        self._phase_combat(dt)
        self._phase_progression(dt)

        self.stats["time"] += dt
        self._apply_dev_unlimited_hp()
        if not self.player.alive:
            # Hold the run open for the shared death poof, then end.
            self._spawn_death_fx(self.player.pos, getattr(self.player, "_facing", 1),
                                 radius=self.player.radius)
            self._death_seq_t = 1.05
        self._report_debug()

    def _apply_dev_unlimited_hp(self) -> None:
        """Dev toggle: HP never ends a frame lower than it started (it may still
        dip and flash mid-frame). Healing raises the floor; it never drops."""
        if not (self.dev_mode and self._dev_unlimited_hp):
            return
        self._dev_hp_floor = max(self._dev_hp_floor, self.player.hp)
        if self.player.hp < self._dev_hp_floor:
            self.player.hp = self._dev_hp_floor
        if not self.player.alive and self._dev_hp_floor > 0.0:
            self.player.alive = True

    def _set_difficulty(self, name: str) -> None:
        """Dev-menu live switch. Re-binds the run's difficulty on the fly; the
        spawn schedule and the boss re-key off the new pace immediately -- see
        SpawnDirector.set_difficulty (raising the pace late can arm the boss on
        the next frame, which is intentional for testing)."""
        if name not in config.DIFFICULTIES:
            return
        self.difficulty = name
        self.director.set_difficulty(name)

    def _run_death_sequence(self, dt: float) -> None:
        if self.dev_mode and self._dev_unlimited_hp:
            # Unlimited HP switched on mid-death-animation: cancel the end.
            self._death_seq_t = None
            self._death_fx.clear()
            self.player.alive = True
            self.player.hp = max(self.player.hp, self._dev_hp_floor,
                                 self.player.max_hp * 0.5)
            return
        self._death_seq_t -= dt
        self._update_hero_anim(dt)
        self._update_death_fx(dt)
        self.camera.update(dt, self.player.pos)
        self.particles.update(dt)
        self.damage_numbers.update(dt)
        self.shake.update(dt)
        if self._death_seq_t <= 0.0:
            self._death_seq_t = None
            self._end_run(victory=False)

    def _hero_anim_name(self) -> str:
        p = self.player
        if not p.alive:
            return "death"
        if p._hurt_t > 0.0 and self._hero_has_hurt:
            return "hurt"
        if p._attack_t > 0.0:
            return "attack"
        return "walk" if p._move_dir.length_squared() > 0 else "idle"

    def _update_hero_anim(self, dt: float) -> None:
        if self._hero_anim is None:
            return
        self._hero_anim.play(self._hero_anim_name())
        self._hero_anim.update(dt)

    def _phase_input(self) -> None:
        self.player.handle_input(pygame.key.get_pressed())
        if self.player._move_dir.length_squared() > 0:
            self._last_move_dir = self.player._move_dir.copy()

    def _phase_update(self, dt: float) -> None:
        self.player.update(dt, self.game_map)
        self._update_hero_anim(dt)
        self.camera.update(dt, self.player.pos)
        self._update_nav(dt)

        elapsed = self.stats["time"]
        if self.director.should_spawn_boss(elapsed):
            self._spawn_boss()
        for enemy_id in self.director.update(dt, elapsed, len(self.enemies)):
            self._spawn_enemy(enemy_id)

        ectx = self._enemy_context(dt)
        for e in self.enemies:
            e.update(ectx)
        if self.boss is not None and self.boss.alive:
            self.boss.update(ectx)

        for p in self.projectiles:
            p.update(dt)
            self._block_on_obstacle(p)
        self.projectiles.sweep()
        for p in self.hostiles:
            p.update(dt)
            if not self._in_world_margin(p.pos, 60):
                p.active = False
            else:
                self._block_on_obstacle(p)
        self.hostiles.sweep()

        self._update_summons(dt)
        self._update_hazards(dt)
        self._update_elite_arenas()
        self._update_death_fx(dt)
        self.particles.update(dt)
        self.damage_numbers.update(dt)
        self.shake.update(dt)
        self._update_explosions(dt)
        self._hurt_flash_t = max(0.0, self._hurt_flash_t - dt)
        self._boss_warning_t = max(0.0, self._boss_warning_t - dt)

    def _phase_combat(self, dt: float) -> None:
        self.grid.rebuild(self.enemies)

        s = self.player.stats
        ctx = FireContext(
            origin=self.player.pos, enemies=self._targetables(),
            damage_multiplier=s["damage_multiplier"] * self.player.outgoing_damage_multiplier(),
            attack_speed_multiplier=s["attack_speed_multiplier"],
            projectile_speed_multiplier=s["projectile_speed_multiplier"],
            area_multiplier=s["area_multiplier"], fallback_dir=self._last_move_dir,
            spawn_projectile=self._spawn_projectile, anchor=self.player.pos,
            crit_chance=min(0.75, 0.02 * s["luck"] + s["crit_chance"]),
            crit_multiplier=2.0 + s["crit_damage"],
            rng=self.rng, spawn_summon=self._spawn_summon)
        if not (self.dev_mode and self._dev_no_attack):
            main = self.player.weapons[0] if self.player.weapons else None
            for weapon in self.player.weapons:
                fired = weapon.update(dt, ctx)
                if fired and weapon is main:
                    self.player.trigger_attack_anim()   # anim syncs to the main weapon only

        self._resolve_projectile_hits()
        self._resolve_hostile_hits()
        self._resolve_enemy_contact()
        self._cull_dead_enemies()

    def _phase_progression(self, dt: float) -> None:
        xp_mult = 1.0 + self.player.stats["xp_gain"]
        soul_heal = self.player.blessing_fx.soul_heal
        for gem in self.gems:
            if gem.update(dt, self.player):
                self.levels.add_xp(max(1, int(round(gem.value * xp_mult))))
                self.stats["xp"] = self.levels.total_xp
                if getattr(gem, "is_soul", False) and soul_heal:
                    self.player.heal(soul_heal)
                self.particles.burst(self.player.pos,
                                     XP_TIER_COLORS.get(gem.tier, (200, 255, 200)),
                                     count=5, speed=110, life=0.3, radius=2)
                self.game.events.publish(Events.XP_COLLECTED, value=gem.value)
        self.gems.sweep()
        self.stats["level"] = self.levels.level

        if self.levels.pending_level_ups > 0 and not self._awaiting_level_up:
            self._open_level_up()

    # --- context builders ---------------------------------
    def _targetables(self) -> list:
        if self.boss is not None and self.boss.alive:
            return self.enemies + [self.boss]
        return self.enemies

    def _enemy_context(self, dt: float):
        """One object per frame, handed to every enemy and the boss. Satisfies
        the `entities.ai` `Perception` + `Combat` protocols; the boss duck-types
        the same callbacks."""
        return SimpleNamespace(
            dt=dt, now=self.stats["time"], player_pos=self.player.pos,
            player=self.player, rng=self.rng,
            nav_dir=self._nav_dir, neighbors=self._nav_neighbors,
            obstacles_near=self._obstacles_near,
            is_walkable=self.game_map.is_walkable,
            resolve_movement=self.game_map.resolve_movement,
            fire_projectile=self._fire_hostile, summon=self._summon,
            explosion=self._explosion, spawn_hazard=self._spawn_hazard,
            report_damage=self._report_dot)

    def _nav_neighbors(self, pos, radius) -> list:
        return self.grid.query_circle(pos.x, pos.y, radius)

    def _obstacles_near(self, pos, radius) -> list:
        if self._obstacle_grid is None:
            return []
        return self._obstacle_grid.query_circle(pos.x, pos.y, radius)

    # Repath early once the player is this many navigation cells from where the
    # field was last aimed -- keeps the field fresh without an 8 ms rebuild every
    # time the player nudges across a 32 px boundary (which happens ~8x/s).
    _NAV_DRIFT_CELLS = 2

    def _update_nav(self, dt: float) -> None:
        """Refresh the flow field toward the player. A large player jump repaths
        every grid at once (rare); the periodic refresh rebuilds one grid per
        tick, round-robin, at `interval / n_grids` spacing -- so each grid still
        refreshes every `ENEMY_NAV_REBUILD_INTERVAL` but only one ~4 ms rebuild
        lands on any frame instead of the ~8 ms both-grids cost."""
        if self._nav is None:
            return
        self._nav_t -= dt
        jumped = (self._nav.target_cell_drift(self.player.pos)
                  >= self._NAV_DRIFT_CELLS)
        if not jumped and self._nav_t > 0.0:
            return
        t0 = time.perf_counter()
        if jumped:
            self._nav.rebuild(self.player.pos)
            self._nav_t = config.ENEMY_NAV_REBUILD_INTERVAL
        else:
            classes = self._nav.classes
            self._nav.rebuild(self.player.pos,
                              only=classes[self._nav_rr % len(classes)])
            self._nav_rr += 1
            self._nav_t = config.ENEMY_NAV_REBUILD_INTERVAL / len(classes)
        self._nav_last_ms = (time.perf_counter() - t0) * 1000.0
        self._nav_rebuilds += 1

    def _nav_dir(self, pos, radius) -> pygame.Vector2:
        """Flow-field steering direction toward the player for an enemy of
        `radius` at `pos`; a zero vector means "no route -- fall back to
        straight chase" (`config.ENEMY_PATHFINDING` off, or an unreached cell)."""
        if self._nav is None:
            return pygame.Vector2()
        return self._nav.direction(pos, radius)

    def _report_dot(self, amount: float) -> None:
        self.stats["damage_dealt"] += amount

    _OP_MAP = {"flat": FLAT, "pct": PCT, "mult": MULT}

    def _apply_persistent_bonuses(self) -> None:
        save = self.game.save
        # Meta upgrades.
        self.player.add_modifiers(*self.game.meta_catalog.player_modifiers(save.meta))
        # Equipped items: plain stat affixes -> StatSet; tag affixes are folded
        # into blessing_fx by rebuild_blessings via player.equipment.
        self.player.equipment = [Item.from_dict(d) for d in save.equipped_items()]
        for item in self.player.equipment:
            mods = [Modifier(stat, self._OP_MAP[op], val, f"item:{item.slot}")
                    for stat, op, val in item.stat_effects()]
            self.player.add_modifiers(*mods)
            if item.unique_effect == "overflow" and self.player.weapons:
                self.player.weapons[0].bonus["projectile_count"] += 1
        self.player.hp = self.player.max_hp  # fill to the boosted maximum

    # --- spawning helpers -------------------------------
    def _in_world_margin(self, pos: pygame.Vector2, margin: float) -> bool:
        return (-margin <= pos.x <= self.game_map.width + margin
                and -margin <= pos.y <= self.game_map.height + margin)

    def _spawn_enemy(self, enemy_id: str, at: pygame.Vector2 | None = None) -> None:
        if len(self.enemies) >= self.director.enemy_count_cap(self.stats["time"]):
            return
        definition = self.content.enemy(enemy_id)
        pos = at if at is not None else self.game_map.offscreen_spawn_point(
            self.camera, self.rng)
        enemy = Enemy(enemy_id, definition, pos.x, pos.y)
        hp_mult, spd_mult = self.director.stat_multipliers(self.stats["time"])
        enemy.max_hp *= hp_mult
        enemy.hp = enemy.max_hp
        enemy.speed *= spd_mult
        self.enemies.append(enemy)

    def _summon(self, enemy_id: str, origin: pygame.Vector2, count: int) -> None:
        for _ in range(count):
            offset = pygame.Vector2(self.rng.uniform(-40, 40), self.rng.uniform(-40, 40))
            self._spawn_enemy(enemy_id, at=origin + offset)

    def _spawn_boss(self) -> None:
        if self.boss is not None:
            return
        self.director.mark_boss_spawned()
        boss_id = next(iter(self.content.bosses))
        pos = self._boss_arena_point()
        self.boss = Boss(boss_id, self.content.boss(boss_id), pos.x, pos.y)
        self.shake.add(0.7)
        self.game.events.publish(Events.BOSS_SPAWNED, name=self.boss.name)
        log.info("boss spawned: %s", self.boss.name)

    def _boss_arena_point(self) -> pygame.Vector2:
        """Centre of the boss room if there is a layout, else just off-screen."""
        if self.game_map.layout is not None:
            room = self.game_map.layout.room(self.game_map.layout.boss_id)
            return room.center
        return self.game_map.offscreen_spawn_point(self.camera, self.rng)

    # --- special locations (spec 5.5) ---------------------
    def _build_interactables(self) -> None:
        self.interactables = []
        if self.game_map.layout is None:
            return
        for room in self.game_map.layout.rooms:
            if room.kind in SPECIAL_KINDS:
                self.interactables.append(Interactable(
                    room.kind, room.center.x, room.center.y, cost=MERCHANT_COST))

    def _nearby_interactable(self):
        for it in self.interactables:
            if not it.used and it.kind != "elite_arena" and it.in_range(self.player.pos):
                return it
        return None

    def _activate_nearby_interactable(self) -> None:
        it = self._nearby_interactable()
        if it is None:
            return
        handler = getattr(self, f"_use_{it.kind}", None)
        if handler is not None:
            handler(it)

    def _grant_random_blessing(self) -> bool:
        choices = roll_blessing_choices(self.player, self.blessing_lib, self.rng, n=1)
        if not choices:
            return False
        choices[0].apply(self.player)
        self.particles.burst(self.player.pos, (150, 190, 255), count=20,
                             speed=180, life=0.6)
        return True

    def _use_shrine(self, it: Interactable) -> None:
        it.used = True
        if not self._grant_random_blessing():
            self.player.heal(30)

    def _use_treasure(self, it: Interactable) -> None:
        it.used = True
        self._drop_item(max(2, int(1 + self.stats["time"] // 80)))
        self.particles.burst(it.pos, it.colour, count=24, speed=220, life=0.6)

    def _use_fountain(self, it: Interactable) -> None:
        it.used = True
        self.player.heal(self.player.max_hp)
        self.particles.burst(self.player.pos, it.colour, count=18, speed=140, life=0.6)

    def _use_altar(self, it: Interactable) -> None:
        cost = self.player.max_hp * ALTAR_HP_COST_FRACTION
        if self.player.hp <= cost + 1:
            return  # too risky -- refuse rather than kill the player
        self.player.hp -= cost
        it.used = True
        if not self._grant_random_blessing():
            self.player.heal(cost)  # refund if nothing to grant

    def _use_merchant(self, it: Interactable) -> None:
        if self.stats["gold"] < it.cost:
            return
        self.stats["gold"] -= it.cost
        it.used = True
        self._drop_item(max(2, int(1 + self.stats["time"] // 80)))
        self.particles.burst(it.pos, it.colour, count=20, speed=180, life=0.5)

    def _update_elite_arenas(self) -> None:
        for it in self.interactables:
            if it.kind != "elite_arena" or it.state == "done":
                continue
            if it.state == "idle" and (self.player.pos - it.pos).length() < it.radius + 120:
                it.state = "active"
                it.arena_ids = set()
                for _ in range(3):
                    off = pygame.Vector2(self.rng.uniform(-90, 90),
                                         self.rng.uniform(-90, 90))
                    self._spawn_enemy("elite", at=it.pos + off)
                    it.arena_ids.add(id(self.enemies[-1]))
                self._boss_warning_t = 1.6
                self._boss_name = "Elite Arena"
            elif it.state == "active":
                live = {id(e) for e in self.enemies if e.alive}
                if not (it.arena_ids & live):
                    it.state = "done"
                    it.used = True
                    self._drop_item(max(3, int(2 + self.stats["time"] // 60)))
                    self.shake.add(0.5)

    def _spawn_projectile(self, **kw):
        proj = self.projectiles.acquire()
        if proj is None:
            return None
        proj.reset(**kw)
        self.game.audio.play_shoot()
        return proj

    def _fire_hostile(self, *, pos, vel, damage, radius) -> None:
        proj = self.hostiles.acquire()
        if proj is None:
            return
        proj.reset(pos=pos, vel=vel, damage=damage, radius=radius,
                   lifetime=6.0, color=(255, 110, 90), hostile=True)

    def _block_on_obstacle(self, proj) -> None:
        if not proj.active or proj.chain_left or proj.orbit_speed:
            return
        if self.game_map.blocking_obstacle_hit(proj.pos, proj.radius) is not None:
            self.particles.burst(proj.pos, proj.color, count=3, speed=70,
                                 life=0.2, radius=2)
            proj.active = False

    # --- summons (spec 5.8) ------------------------------
    def _spawn_summon(self, **kw):
        s = self.summons.acquire()
        if s is None:
            return None
        s.reset(**kw)
        return s

    def _update_summons(self, dt: float) -> None:
        sctx = SimpleNamespace(enemies=self._targetables(),
                               spawn_projectile=self._spawn_projectile,
                               player_pos=self.player.pos)
        for s in self.summons:
            s.update(dt, sctx)
        self.summons.sweep()

    # --- ground hazards (spec 5.6) -----------------------
    def _spawn_hazard(self, pos, radius, dps, duration, tick_interval=None) -> None:
        self.hazards.append(
            Hazard(pos.x, pos.y, radius, dps, duration, tick_interval=tick_interval))

    def _update_hazards(self, dt: float) -> None:
        for hz in self.hazards:
            hz.update(dt)
            if hz.alive and hz.contains(self.player.pos, self.player.radius):
                bite = hz.due_damage(dt)       # dps * tick_interval per interval
                if bite > 0.0:
                    taken = self.player.take_damage(bite)
                    if taken > 0:
                        self.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)
            else:
                hz.reset_ticks()               # partial exposure does not bank
        self.hazards = [h for h in self.hazards if h.alive]

    def _explosion(self, pos: pygame.Vector2, radius: float, damage: float) -> None:
        self._explosions.append({"pos": pygame.Vector2(pos), "radius": radius,
                                 "t": 0.0, "dur": 0.35})
        self.particles.burst(pos, (255, 160, 80), count=22, speed=260, life=0.5)
        self.shake.add(0.4)
        if (self.player.pos - pos).length() <= radius + self.player.radius:
            taken = self.player.take_damage(damage)
            if taken > 0:
                self.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)

    def _update_explosions(self, dt: float) -> None:
        for ex in self._explosions:
            ex["t"] += dt
        self._explosions = [e for e in self._explosions if e["t"] < e["dur"]]

    # --- collision resolution ---------------------------
    def _resolve_projectile_hits(self) -> None:
        targets = self._targetables()
        for proj in self.projectiles:
            if not proj.active:
                continue
            near = self.grid.query_circle(proj.pos.x, proj.pos.y, proj.radius + 40)
            if self.boss is not None and self.boss.alive:
                near = near + [self.boss]
            for enemy in near:
                if not enemy.alive or id(enemy) in proj.hit_ids:
                    continue
                if not circles_overlap(proj.pos.x, proj.pos.y, proj.radius,
                                       enemy.pos.x, enemy.pos.y, enemy.radius):
                    continue
                if proj.cone_half_angle > 0.0 and not self._in_cone(proj, enemy):
                    continue

                amount = proj.damage * self._damage_multiplier(proj, enemy)
                dealt = enemy.take_damage(amount)
                proj.hit_ids.add(id(enemy))
                self.stats["damage_dealt"] += dealt
                self.damage_numbers.add(enemy.pos, dealt, proj.is_crit)
                self.particles.burst(proj.pos, proj.color, count=4, speed=90,
                                     life=0.22, radius=2)
                if proj.knockback:
                    enemy.apply_knockback(enemy.pos - proj.pos, proj.knockback)
                self._apply_on_hit_effects(proj, enemy)
                self.game.events.publish(Events.DAMAGE_DEALT, amount=dealt)
                if proj.chain_left > 0 and self._chain_to_next(proj, targets):
                    continue
                proj.on_hit()
                if not proj.active:
                    break

    def _damage_multiplier(self, proj: Projectile, enemy) -> float:
        """Blessing tag bonuses + Shock + status-vulnerability synergy."""
        fx = self.player.blessing_fx
        mult = 1.0 + fx.tag_bonus(proj.source_tags, getattr(enemy, "is_elite", False))
        mult *= enemy.status.damage_taken_multiplier()
        mult += fx.vuln_bonus(proj.source_tags, enemy.status)
        return mult

    def _apply_on_hit_effects(self, proj: Projectile, enemy) -> None:
        fx = self.player.blessing_fx
        for status, tag, chance, dur, potency in fx.on_hit:
            if tag is not None and tag not in proj.source_tags:
                continue
            if self.rng.random() < chance:
                enemy.status.apply(
                    status,
                    dur * (1.0 + fx.tuned(status, "duration")),
                    potency * (1.0 + fx.tuned(status, "potency")),
                    bonus_max_stacks=int(fx.tuned(status, "max_stacks")))
        # Nihil / Cursebrand: first hit on each enemy applies Shock.
        if self.player.trait == "cursebrand" and id(enemy) not in self.player._hexed:
            self.player._hexed.add(id(enemy))
            enemy.status.apply("shock", 4.0, 0.10)

    def _in_cone(self, proj: Projectile, enemy) -> bool:
        to_enemy = enemy.pos - proj.pos
        if to_enemy.length_squared() < 1e-6:
            return True
        cos_limit = math.cos(proj.cone_half_angle)
        return proj.cone_dir.normalize().dot(to_enemy.normalize()) >= cos_limit

    def _chain_to_next(self, proj: Projectile, targets) -> bool:
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

    def _resolve_hostile_hits(self) -> None:
        pr = self.player.radius
        for proj in self.hostiles:
            if not proj.active:
                continue
            if circles_overlap(proj.pos.x, proj.pos.y, proj.radius,
                               self.player.pos.x, self.player.pos.y, pr):
                taken = self.player.take_damage(proj.damage)
                proj.active = False
                if taken > 0:
                    self.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)

    def _resolve_enemy_contact(self) -> None:
        """Each touching enemy deals a bite (`contact_damage * contact_interval`,
        before armor) once per its `contact_interval`; `contact_cd` -- ticked
        down in Enemy/Boss.update -- paces it."""
        pr = self.player.radius
        contacts = list(self.grid.query_circle(self.player.pos.x, self.player.pos.y, pr + 48))
        if self.boss is not None and self.boss.alive:
            contacts.append(self.boss)
        for enemy in contacts:
            if not enemy.alive or enemy.contact_cd > 0.0:
                continue
            if circles_overlap(self.player.pos.x, self.player.pos.y, pr,
                               enemy.pos.x, enemy.pos.y, enemy.radius):
                enemy.contact_cd = enemy.contact_interval
                taken = self.player.take_damage(
                    enemy.contact_damage * enemy.contact_interval)
                if taken > 0:
                    self.game.events.publish(Events.PLAYER_DAMAGED, amount=taken)

    def _cull_dead_enemies(self) -> None:
        if self.boss is not None and not self.boss.alive:
            self._on_boss_killed()

        if not self.enemies:
            return
        survivors = []
        for e in self.enemies:
            if e.alive:
                survivors.append(e)
                continue
            # Death effects fire NOW, at the instant of death.
            self.stats["kills"] += 1
            if e.explode_radius > 0.0:
                self._explosion(e.pos, e.explode_radius, e.explode_damage)
            self._apply_on_kill_effects(e)
            self.game.events.publish(Events.ENEMY_KILLED, pos=e.pos.copy(),
                                     color=e.color, xp=e.xp_reward, tags=e.tags,
                                     elite=e.is_elite)
            self._spawn_death_fx(e.pos, getattr(e, "_facing", 1),
                                 scale=self._ENEMY_DEATH_FX_SCALE, radius=e.radius)
        self.enemies = survivors

    _ENEMY_DEATH_FX_SCALE = 0.55        # enemy death poof at 55% (hero stays 1.0)

    def _sprite_drop(self, radius: float) -> float:
        """Downward render offset (screen px) that seats a rig's feet-anchor
        below the collider centre -- see config.SPRITE_ANCHOR_DROP. Render-only."""
        return config.SPRITE_ANCHOR_DROP * radius * self.camera.zoom

    def _spawn_death_fx(self, pos, facing: int = 1, scale: float = 1.0,
                        radius: float = float(config.PLAYER_RADIUS)) -> None:
        self._death_fx.append(
            [Animator(self.game.assets, "dead", start="loop"),
             pygame.Vector2(pos), 1 if facing >= 0 else -1, float(scale),
             float(radius)])

    def _update_death_fx(self, dt: float) -> None:
        for fx in self._death_fx:
            fx[0].update(dt)
        self._death_fx = [fx for fx in self._death_fx if not fx[0].finished]

    def _apply_on_kill_effects(self, enemy) -> None:
        for effect, chance, amount in self.player.blessing_fx.on_kill:
            if self.rng.random() >= chance:
                continue
            if effect == "soul":
                gem = self.gems.acquire()
                if gem is not None:
                    gem.reset(enemy.pos, int(amount) or 3, is_soul=True)
            elif effect == "heal":
                self.player.heal(amount)
            elif effect == "fire_nova" and "burn" in enemy.status:
                self._enemy_explosion(enemy.pos, 70.0, float(amount) or 16.0)
            elif effect == "shock_spread" and "shock" in enemy.status:
                self._spread_status(enemy.pos, "shock", 3.0, 0.12)

    def _enemy_explosion(self, pos: pygame.Vector2, radius: float, dmg: float) -> None:
        """AoE that hurts nearby enemies (not the player) -- blessing procs."""
        self._explosions.append({"pos": pygame.Vector2(pos), "radius": radius,
                                 "t": 0.0, "dur": 0.3})
        self.particles.burst(pos, (255, 150, 70), count=14, speed=200, life=0.4)
        for enemy in self.grid.query_circle(pos.x, pos.y, radius):
            if enemy.alive and (enemy.pos - pos).length() <= radius + enemy.radius:
                dealt = enemy.take_damage(dmg)
                self.stats["damage_dealt"] += dealt

    def _spread_status(self, pos: pygame.Vector2, status: str, dur: float,
                       potency: float) -> None:
        best, best_d2 = None, 260.0 ** 2
        for enemy in self.grid.query_circle(pos.x, pos.y, 260):
            if not enemy.alive:
                continue
            d2 = (enemy.pos - pos).length_squared()
            if d2 < best_d2:
                best, best_d2 = enemy, d2
        if best is not None:
            best.status.apply(status, dur, potency)

    # --- level-up flow --------------------------------
    def _open_level_up(self) -> None:
        # Every 3rd level is a blessing offering ("a god's attention"); other
        # levels draw from the weapon / stat / new-weapon pool.
        if self.levels.level % 3 == 0:
            choices = roll_blessing_choices(self.player, self.blessing_lib,
                                            self.rng, n=3)
        else:
            choices = roll_choices(self.player, self.content, self.rng, n=3)
        if not choices:
            choices = roll_choices(self.player, self.content, self.rng, n=3)
        if not choices:
            self.levels.consume_pending()
            return
        self.game.events.publish(Events.PLAYER_LEVELED, level=self.levels.level)
        self._awaiting_level_up = True
        from game.states.level_up_state import LevelUpState
        self.game.state_machine.push(LevelUpState(self.game), player=self.player,
                                     choices=choices, on_done=self._on_level_up_chosen)

    def _on_level_up_chosen(self, upgrade) -> None:
        self.levels.consume_pending()
        self._awaiting_level_up = False
        log.info("level %d: took %s", self.levels.level, upgrade.id)

    # --- event handlers ----------------------------
    def _on_enemy_killed(self, *, pos, color, xp, tags, elite=False) -> None:
        self.particles.burst(pos, color, count=16 if elite else 10,
                             speed=200 if elite else 160, life=0.5)
        self.stats["gold"] += 2 if elite else 1   # in-run gold for the Merchant
        if elite:
            self.shake.add(0.18)
            if self.rng.random() < 0.18:
                self._drop_item(int(1 + self.stats["time"] // 90))
        gem = self.gems.acquire()
        if gem is not None:
            gem.reset(pos, xp)

    def _drop_item(self, item_level: int) -> None:
        self._drop_counter += 1
        item = generate_item(
            self.content, seed=self.run_seed * 1000 + self._drop_counter,
            item_level=max(1, item_level), luck=self.player.stats["luck"])
        self.stats["dropped_items"].append(item.to_dict())
        log.info("dropped %s", item.short())

    def _on_player_damaged(self, *, amount) -> None:
        self.shake.add(min(0.4, 0.05 + amount * 0.02))
        self._hurt_flash_t = min(0.35, self._hurt_flash_t + 0.12 + amount * 0.01)
        if amount > 0:
            self.damage_numbers.add(self.player.pos, amount, incoming=True)

    def _on_boss_spawned(self, *, name) -> None:
        self._boss_warning_t = 2.6
        self._boss_name = name

    def _on_boss_killed(self) -> None:
        reward = getattr(self.boss, "reward_currency", 50)
        self.stats["currency"] += reward
        # The boss's "meaningful reward" (spec 3.7): a high-tier item.
        self._drop_item(item_level=max(3, int(1 + self.stats["time"] // 60)))
        self.particles.burst(self.boss.pos, self.boss.color, count=60,
                             speed=340, life=0.9)
        self._spawn_death_fx(self.boss.pos, getattr(self.boss, "_facing", 1),
                             scale=1.4, radius=self.boss.radius)   # (mostly unseen -- victory follows)
        self.shake.add(1.0)
        self.game.events.publish(Events.BOSS_KILLED, name=self.boss.name)
        self.boss = None
        self._end_run(victory=True)

    # --- run end ----------------------------------
    def _end_run(self, *, victory: bool) -> None:
        summary = dict(self.stats)
        summary["weapons"] = [(w.name, w.level) for w in self.player.weapons]
        summary["seed"] = self.run_seed
        summary["difficulty"] = self.difficulty
        summary["character"] = self.content.character(self.character_id)["name"]
        summary["blessings"] = dict(self.player.blessings)
        self.game.events.publish(Events.RUN_ENDED, stats=summary, victory=victory,
                                 dev=self.dev_mode)
        if self.dev_mode:
            # A dev run never shows a summary or banks anything -- it just wipes
            # back to a clean level-1 state on the same world (the "Reset run"
            # behaviour, also triggered on death).
            self._restart_dev_run()
            return
        if victory:
            from game.states.victory_state import VictoryState
            self.game.state_machine.change(VictoryState(self.game), stats=summary)
        else:
            from game.states.game_over_state import GameOverState
            self.game.state_machine.change(GameOverState(self.game), stats=summary)

    def _restart_dev_run(self) -> None:
        """Reload the developer run from scratch: same world seed, fresh hero,
        level 1, no blessings / items / upgrades, enemies cleared."""
        self.game.state_machine.change(
            PlayingState(self.game), character_id=self.character_id,
            seed=self.run_seed, dev=True)

    # --- debug -----------------------------------
    def _report_debug(self) -> None:
        d = self.game.debug
        d.set_metric("state", "PLAYING")
        d.set_metric("seed", self.run_seed)
        d.set_metric("hero", self.character_id)
        d.set_metric("blessings", sum(self.player.blessings.values()))
        d.set_metric("run time", f"{self.stats['time']:6.1f}s")
        d.set_metric("enemies", len(self.enemies))
        d.set_metric("boss", "yes" if self.boss else "no")
        d.set_metric("projectiles", len(self.projectiles))
        d.set_metric("hostiles", len(self.hostiles))
        d.set_metric("summons", len(self.summons))
        d.set_metric("hazards", len(self.hazards))
        d.set_metric("gems", len(self.gems))
        d.set_metric("particles", len(self.particles))
        d.set_metric("level", self.levels.level)
        d.set_metric("kills", self.stats["kills"])
        if self._nav is not None:
            d.set_metric("nav", f"on {self._nav_last_ms:4.1f}ms  x{self._nav_rebuilds}")
        elif config.ENEMY_PATHFINDING:
            d.set_metric("nav", "on (no layout)")

    # --- render ---------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        # Screen-shake is an amplitude in screen pixels; camera.pos is world
        # space, so convert through the zoom before nudging it.
        offset = self.shake.offset / self.camera.zoom
        self.camera.pos -= offset
        try:
            self.game_map.draw_ground(surface, self.camera)
            self.game_map.draw_room_clutter(surface, self.camera)
            self._draw_interactables(surface)
            self._draw_hazards(surface)
            self._draw_gems(surface)
            self._draw_explosions(surface)
            self._draw_player_projectiles(surface)      # weapon effects sit behind the characters
            self._draw_depth_layer(surface)
            self.game_map.draw_tree_shadows(surface, self.camera)
            self._draw_hostile_projectiles(surface)     # enemy shots stay on top (danger readability)
            self.particles.draw(surface, self.camera)
            self.damage_numbers.draw(surface, self.camera)
            self._draw_collider_overlay(surface)        # dev-only, on top of the world
        finally:
            self.camera.pos += offset

        self.hud.draw(surface, self.player, self.stats,
                      xp_fraction=self.levels.progress_fraction, boss=self.boss)
        self._draw_feedback_overlays(surface)

    def _draw_feedback_overlays(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()

        # Low-HP vignette (spec 3.6 player damage feedback) -- pulsing red frame.
        frac = self.player.hp / self.player.max_hp if self.player.max_hp else 1.0
        if frac < 0.3:
            pulse = 60 + int(40 * math.sin(self.stats["time"] * 8))
            vig = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(vig, (180, 20, 20, max(0, pulse)), (0, 0, w, h), 24)
            surface.blit(vig, (0, 0))

        # Brief full-screen red flash on taking a hit.
        if self._hurt_flash_t > 0.0:
            a = int(120 * min(1.0, self._hurt_flash_t / 0.35))
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            flash.fill((200, 30, 30, a))
            surface.blit(flash, (0, 0))

        # Boss-incoming warning banner (spec 3.6 "Boss warning").
        if self._boss_warning_t > 0.0:
            blink = (self._boss_warning_t * 4) % 1.0 < 0.6
            if blink:
                text = self._banner_font.render(
                    f"{self._boss_name} APPROACHES", True, (255, 90, 90))
                surface.blit(text, text.get_rect(center=(w // 2, 120)))

        # Interaction prompt when stood on a usable special location.
        it = self._nearby_interactable()
        if it is not None:
            afford = it.kind != "merchant" or self.stats["gold"] >= it.cost
            col = (240, 240, 245) if afford else (200, 120, 120)
            prompt = self._prompt_font.render(it.prompt, True, col)
            surface.blit(prompt, prompt.get_rect(center=(w // 2, h - 96)))

    def _draw_interactables(self, surface) -> None:
        z = self.camera.zoom
        for it in self.interactables:
            sx, sy = self.camera.world_to_screen(it.pos)
            done = it.used or it.state == "done"
            col = (90, 90, 100) if done else it.colour
            pygame.draw.circle(surface, col, (int(sx), int(sy)),
                               round(it.radius * z), 0 if done else 3)
            pygame.draw.circle(surface, (240, 245, 255), (int(sx), int(sy)), round(4 * z))
            if it.kind == "elite_arena" and it.state == "active":
                pygame.draw.circle(surface, (255, 120, 120), (int(sx), int(sy)),
                                   round((it.radius + 120) * z), 1)

    def _draw_hazards(self, surface) -> None:
        z = self.camera.zoom
        for hz in self.hazards:
            sx, sy = self.camera.world_to_screen(hz.pos)
            frac = max(0.0, hz.life / hz.max_life)
            rr = max(1, round(hz.radius * z))
            surf = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*hz.color, int(70 * frac + 20)), (rr, rr), rr)
            surface.blit(surf, (sx - rr, sy - rr))
            pygame.draw.circle(surface, hz.color, (int(sx), int(sy)), rr, 2)

    def _draw_one_summon(self, surface, s) -> None:
        z = self.camera.zoom
        sx, sy = self.camera.world_to_screen(s.pos)
        if s.kind == "totem":
            pygame.draw.rect(surface, s.color,
                             (int(sx - 7 * z), int(sy - 12 * z),
                              round(14 * z), round(24 * z)), border_radius=3)
        else:
            pygame.draw.circle(surface, s.color, (int(sx), int(sy)), round(9 * z))
        pygame.draw.circle(surface, (240, 245, 255), (int(sx), int(sy)), round(3 * z))

    def _depth_items(self) -> list:
        """`(depth_y, draw_fn)` for the whole depth-sorted layer -- map scenery
        (obstacles + interior decorations) plus the characters (hero, enemies,
        boss, summons) -- sorted back-to-front by ground-contact Y."""
        items = self.game_map.scenery_drawables(self.camera)
        for e in self.enemies:
            items.append((e.pos.y, lambda s, e=e: self._draw_one_enemy(s, e)))
        for fx in self._death_fx:                  # one-shot death poofs
            items.append((fx[1].y, lambda s, fx=fx: self._draw_death_fx(s, fx)))
        if self.boss is not None and self.boss.alive:
            items.append((self.boss.pos.y, self._draw_boss))
        for sm in self.summons:
            items.append((sm.pos.y, lambda s, sm=sm: self._draw_one_summon(s, sm)))
        items.append((self.player.pos.y, self._draw_player))
        items.sort(key=lambda t: t[0])
        return items

    def _draw_depth_layer(self, surface) -> None:
        """Paint the depth-sorted layer: a sprite lower on the map draws over the
        ones above it, so a character standing behind (a smaller Y than) a tree
        is hidden by its canopy."""
        for _, fn in self._depth_items():
            fn(surface)

    _ORB_RIGS = {0: "xp_orb_small", 1: "xp_orb_medium", 2: "xp_orb_large"}

    def _draw_gems(self, surface) -> None:
        z = self.camera.zoom
        assets = self.game.assets

        for gem in self.gems:
            sx, sy = self.camera.world_to_screen(gem.pos)
            rig = self._ORB_RIGS.get(gem.tier, "xp_orb_small")
            base_size = assets.scale_for(rig) or (8, 8)
            size = (
                max(1, round(base_size[0] * z)),
                max(1, round(base_size[1] * z)),
            )

            orb = assets.image(rig, size=size)

            if orb is not None:
                surface.blit(
                    orb,
                    orb.get_rect(center=(int(sx), int(sy))),
                )
            else:
                pygame.draw.circle(
                    surface,
                    XP_TIER_COLORS.get(gem.tier, (150, 220, 150)),
                    (int(sx), int(sy)),
                    round((3 + gem.tier) * z),
                )

    def _draw_explosions(self, surface) -> None:
        z = self.camera.zoom
        for ex in self._explosions:
            frac = ex["t"] / ex["dur"]
            sx, sy = self.camera.world_to_screen(ex["pos"])
            pygame.draw.circle(surface, (255, 180, 90),
                               (int(sx), int(sy)), int(ex["radius"] * frac * z), 3)

    _STATUS_TINT = {"burn": (255, 130, 60), "chill": (140, 210, 255),
                    "shock": (255, 230, 120)}
    _HIT_TINT = (150, 30, 30)

    @classmethod
    def _hit_tinted(cls, frame):
        """A red-tinted copy of a sprite frame -- the damage flash for rigs with
        no `hurt` strip. `BLEND_RGBA_ADD` brightens toward red and leaves the
        alpha silhouette intact (transparent pixels stay transparent)."""
        out = frame.copy()
        out.fill((*cls._HIT_TINT, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return out

    def _draw_one_enemy(self, surface, e) -> None:
        z = self.camera.zoom
        sx, sy = self.camera.world_to_screen(e.pos)
        er = e.radius * z

        sprited = e.anim is not None
        if sprited:
            self._draw_enemy_sprite(surface, e)
        else:
            colour = (255, 255, 255) if e.hit_flash > 0 else e.color
            for sid, tint in self._STATUS_TINT.items():
                if sid in e.status:
                    colour = tint
                    break
            pygame.draw.circle(surface, colour, (int(sx), int(sy)), round(er))

        # Thin state rings at the collider edge -- always for the primitive
        # fallback (the only cue with no art); for a sprited enemy only when
        # config.SHOW_ENEMY_STATE_RINGS is on (else it just reads as a collider).
        if not sprited or config.SHOW_ENEMY_STATE_RINGS:
            for sid, tint in self._STATUS_TINT.items():
                if sid in e.status:
                    pygame.draw.circle(surface, tint, (int(sx), int(sy)),
                                       round(er) + 2, 2)
                    break
            if e.is_elite:
                pygame.draw.circle(surface, (255, 220, 120), (int(sx), int(sy)),
                                   round(er) + 3, 2)
            if e.shield_hp > 0:
                pygame.draw.circle(surface, (150, 200, 255), (int(sx), int(sy)),
                                   round(er) + 5, 1)

        if e.telegraphing:                        # attack telegraph -- always on
            r = e.cfg.get("slam_radius", 120)
            pygame.draw.circle(surface, (255, 90, 90), (int(sx), int(sy)),
                               round(r * z), 2)

    def _draw_death_fx(self, surface, fx) -> None:
        anim, pos, facing, scale, radius = fx
        z = self.camera.zoom
        scale *= z
        assets = self.game.assets
        bw, bh = assets.scale_for("dead")
        size = (max(1, round(bw * scale)), max(1, round(bh * scale)))
        frame = anim.frame(size=size,
                           flip=(facing < 0 and assets.face("dead") == "right"))
        if frame is None:
            return
        ax, ay = assets.anchor("dead")
        sx, sy = self.camera.world_to_screen(pos)
        drop = self._sprite_drop(radius)     # match the sprite this poof replaced
        surface.blit(frame, (int(sx - ax * scale), int(sy - ay * scale + drop)))

    def _draw_enemy_sprite(self, surface, e) -> None:
        z = self.camera.zoom
        assets = self.game.assets
        rig = e.anim.rig
        flip = e._facing < 0 and assets.face(rig) == "right"
        bw, bh = assets.scale_for(rig)
        frame = e.anim.frame(size=(max(1, round(bw * z)), max(1, round(bh * z))),
                             flip=flip)
        sx, sy = self.camera.world_to_screen(e.pos)
        if frame is None:                        # sprite file missing -> primitive
            pygame.draw.circle(surface, e.color, (int(sx), int(sy)),
                               round(e.radius * z))
            return
        if e._hurt_t > 0.0:
            frame = self._hit_tinted(frame)     # red flash, no pop to a circle
        ax, ay = assets.anchor(rig)
        surface.blit(frame, (sx - ax * z, sy - ay * z + self._sprite_drop(e.radius)))

    def _draw_boss(self, surface) -> None:
        b = self.boss
        if b is None or not b.alive:
            return
        z = self.camera.zoom
        sx, sy = self.camera.world_to_screen(b.pos)
        br = b.radius * z
        assets = self.game.assets
        frame = None
        if b.anim is not None:
            rig = b.anim.rig
            bw, bh = assets.scale_for(rig)
            frame = b.anim.frame(size=(max(1, round(bw * z)), max(1, round(bh * z))),
                                 flip=(b._facing < 0 and assets.face(rig) == "right"))
        if frame is not None:
            if b._hurt_t > 0.0:
                frame = self._hit_tinted(frame)
            ax, ay = assets.anchor(rig)
            surface.blit(frame, (int(sx - ax * z),
                                 int(sy - ay * z + self._sprite_drop(b.radius))))
        else:
            colour = (255, 255, 255) if b.hit_flash > 0 else b.color
            pygame.draw.circle(surface, colour, (int(sx), int(sy)), round(br))
            pygame.draw.circle(surface, (255, 210, 210), (int(sx), int(sy)),
                               round(br), 3)
        if b.phase == "telegraph":
            pid = b.pattern.get("id")
            frac = b.telegraph_fraction
            if pid == "radial_barrage":
                pygame.draw.circle(surface, (255, 140, 140), (int(sx), int(sy)),
                                   round((40 + 220 * frac) * z), 2)
            elif pid == "charge":
                d = self.player.pos - b.pos
                if d.length_squared() > 1:
                    d = d.normalize() * 900
                    ex, ey = self.camera.world_to_screen(b.pos + d)
                    pygame.draw.line(surface, (255, 120, 120), (sx, sy), (ex, ey), 3)
            elif pid == "summon_brood":
                pygame.draw.circle(surface, (150, 220, 160), (int(sx), int(sy)),
                                   round(br + 20 * frac * z), 2)

    _HOSTILE_ARROW_TINT = (150, 26, 12)

    def _draw_player_projectiles(self, surface) -> None:
        cam = self.camera
        z = cam.zoom
        for p in self.projectiles:
            sx, sy = cam.world_to_screen(p.pos)
            if p.cone_half_angle > 0.0:
                self._draw_cone(surface, sx, sy, p, z)  # reaping arc = a sector, not a circle
            else:
                pygame.draw.circle(surface, p.color, (int(sx), int(sy)),
                                   max(2, round(p.radius * z)))

    @staticmethod
    def _draw_cone(surface, cx: float, cy: float, p, zoom: float = 1.0) -> None:
        """Draw the exact region `_resolve_projectile_hits` / `_in_cone` test:
        a circular **sector** with apex at the player, radius `p.radius`, spanning
        `cone_dir ± cone_half_angle`. (Was a full circle -- the wrong shape.)"""
        r = max(2.0, float(p.radius)) * zoom
        base = math.atan2(p.cone_dir.y, p.cone_dir.x)
        half = float(p.cone_half_angle)
        steps = max(2, int(math.degrees(half) / 4))
        pts = [(int(cx), int(cy))]
        for i in range(steps + 1):
            a = base - half + (2.0 * half) * i / steps
            pts.append((int(cx + math.cos(a) * r), int(cy + math.sin(a) * r)))
        col = tuple(p.color)
        gfx = _get_gfxdraw()
        if gfx is not None:
            gfx.filled_polygon(surface, pts, (*col, 70))
            gfx.aapolygon(surface, pts, (*col, 210))
        else:  # pygbag / no gfxdraw: a plain translucent sector, no AA edge
            fill = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(fill, (*col, 70), pts)
            pygame.draw.polygon(fill, (*col, 210), pts, 2)
            surface.blit(fill, (0, 0))

    def _draw_hostile_projectiles(self, surface) -> None:
        # Enemy / boss shots: a rotated arrow (falls back to a dot if the
        # sprite is missing). Rotation is cached in 8-degree buckets.
        z = self.camera.zoom
        assets = self.game.assets
        aw, ah = assets.scale_for("arrow")
        arrow_size = (max(1, round(aw * z)), max(1, round(ah * z)))
        for p in self.hostiles:
            sx, sy = self.camera.world_to_screen(p.pos)
            spr = assets.rotated(
                "arrow", math.degrees(math.atan2(p.vel.y, p.vel.x)),
                size=arrow_size, tint=self._HOSTILE_ARROW_TINT)
            if spr is not None:
                surface.blit(spr, spr.get_rect(center=(int(sx), int(sy))))
            else:
                pygame.draw.circle(surface, p.color, (int(sx), int(sy)),
                                   max(3, round(p.radius * z)))

    def _draw_player(self, surface) -> None:
        if not self.player.alive:
            return                              # the death poof (_death_fx) stands in
        z = self.camera.zoom
        sx, sy = self.camera.world_to_screen(self.player.pos)
        pr = self.player.radius * z

        frame = self._hero_sprite_frame()
        if frame is not None:
            # `anchor` is the pixel in the final sprite that sits on the world
            # position (bottom-centre-ish -- the art is bottom-heavy); the drop
            # then seats it below the collider centre (config.SPRITE_ANCHOR_DROP).
            ax, ay = self.game.assets.anchor(self._hero_anim.rig)
            if self.player._hurt_t > 0.0:
                frame = self._hit_tinted(frame)
            surface.blit(frame, (sx - ax * z,
                                 sy - ay * z + self._sprite_drop(self.player.radius)))
            if self.player.invulnerable:
                pygame.draw.circle(surface, (255, 120, 120), (sx, sy),
                                   round(pr + 4 * z), width=2)
        else:
            body = (255, 120, 120) if self.player.invulnerable else self._hero_color
            pygame.draw.circle(surface, body, (sx, sy), round(pr))
            pygame.draw.circle(surface, config.COLOR_PLAYER_OUTLINE, (sx, sy),
                               round(pr), width=2)

    def _draw_collider_overlay(self, surface) -> None:
        """Dev-mode: every true circular collider / hitbox in one pass, read
        straight off the fields the physics uses. Toggle with F7 or the dev
        menu's 'Collision shapes' row."""
        if not (self.dev_mode and self._dev_show_colliders):
            return
        cam = self.camera
        z = cam.zoom
        view = cam.visible_rect().inflate(200, 200)

        def ring(pos, r, col, w=2):
            sx, sy = cam.world_to_screen(pos)
            pygame.draw.circle(surface, col, (int(sx), int(sy)),
                               max(1, round(r * z)), w)

        ring(self.player.pos, self.player.radius, config.COLOR_DEBUG)
        ring(self.player.pos, self.player.pickup_radius, config.COLOR_DEBUG_SOFT, 1)
        for e in self.enemies:
            if view.collidepoint(e.pos.x, e.pos.y):
                ring(e.pos, e.radius, config.COLOR_DEBUG)
        if self.boss is not None and self.boss.alive:
            ring(self.boss.pos, self.boss.radius, config.COLOR_DEBUG)
        for o in self.game_map.obstacles:
            if view.collidepoint(o.pos.x, o.pos.y):
                ring(o.pos, o.radius, config.COLOR_DEBUG)
        for p in self.projectiles:
            ring(p.pos, p.radius, config.COLOR_DEBUG_HIT, 1)
        for p in self.hostiles:
            ring(p.pos, p.radius, config.COLOR_DEBUG_HIT, 1)

    def _hero_sprite_frame(self):
        if self._hero_anim is None:
            return None
        assets = self.game.assets
        rig = self._hero_anim.rig
        flip = self.player._facing < 0 and assets.face(rig) == "right"
        z = self.camera.zoom
        bw, bh = assets.scale_for(rig)
        return self._hero_anim.frame(
            size=(max(1, round(bw * z)), max(1, round(bh * z))), flip=flip)
