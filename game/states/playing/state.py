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
from types import SimpleNamespace

import pygame

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
from entities.melee_hitbox import MeleeHitbox
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
from game.states.playing import rendering as _rendering
from game.states.playing.rendering import WorldRenderer
from game.states.playing.combat import CombatResolver
from game.states.playing.physics import BumpResolver
from game.states.playing.locations import SpecialLocations
from game.states.playing.effects import TransientFx
from game.states.playing.navigation import NavCoordinator
from game.states.playing.spawning import EnemyControl
from game.states.playing.perception import PlayingPerception

log = logging.getLogger(__name__)

STARTING_WEAPON = "arcane_bolt"


class PlayingState(State):
    def enter(self, *, seed: int | None = None, character_id: str | None = None,
              dev: bool = False, difficulty: str | None = None, **kwargs) -> None:
        self._init_run(seed, dev, difficulty)
        self._init_world()
        self._init_player(character_id)
        self._init_scaffold()
        self._init_nav()
        self._subscribe_events()

    # --- enter() steps ---------------------------------------------
    def _init_run(self, seed, dev, difficulty) -> None:
        """Seed, RNG, difficulty and the developer-sandbox flags."""
        self.content = get_content()
        self.dev_mode = bool(dev)     # developer sandbox: no save, restart on end
        self.difficulty = (difficulty if difficulty in config.DIFFICULTIES
                           else config.DIFFICULTY_DEFAULT)
        self._dev_unlimited_hp = False   # HP ratchet (dev menu D2)
        self._dev_no_attack = False      # hero weapons silenced (dev menu D2)
        self._dev_no_damage = False      # weapons still fire, hits deal 0 (dev menu)
        self._dev_hp_floor = 0.0
        self._dev_show_colliders = False  # F7 / dev menu: true collider overlay
        self.run_seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.run_seed)

    def _init_world(self) -> None:
        """The map, its special locations, and the phase-based spawn director."""
        self.game_map = GameMap(seed=self.run_seed)
        self.locations = SpecialLocations(self)
        self.locations.build()
        self.director = SpawnDirector(config.RUN_DURATION_SECONDS, rng=self.rng,
                                      difficulty=self.difficulty)
        self.spawn = EnemyControl(self)

    def _init_player(self, character_id) -> None:
        """The hero: stats, starting weapon, sprite rig, persistent bonuses,
        blessing library, and the camera that follows it."""
        start = self.game_map.center
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

    def _init_scaffold(self) -> None:
        """Entity pools, the feedback systems, HUD/levels, transient-FX lists,
        the run stats dict, the renderer, and the on-screen timers/fonts."""
        self.enemies: list[Enemy] = []
        self.boss: Boss | None = None
        self.projectiles: Pool[Projectile] = Pool(Projectile, config.MAX_PROJECTILES, prefill=128)
        self.hostiles: Pool[Projectile] = Pool(Projectile, config.MAX_PROJECTILES, prefill=64)
        self.gems: Pool[XPGem] = Pool(XPGem, config.MAX_PROJECTILES, prefill=64)
        self.summons: Pool[Summon] = Pool(Summon, 32, prefill=8)
        self.hazards: list[Hazard] = []
        self.melee_hitboxes: list[MeleeHitbox] = []
        self.particles = ParticleSystem()
        self.damage_numbers = DamageNumbers()
        self.shake = ScreenShake()
        self.grid = SpatialGrid()
        self.hud = HUD()
        self.levels = LevelTracker()

        self._explosions: list[dict] = []   # transient blast visuals
        # One-shot death poofs: [Animator("dead"), world_pos, facing]. Any entity
        # (hero or enemy) that dies pushes one; drawn in the depth layer, dropped
        # when the animation finishes.
        self._death_fx: list = []
        # Projectile dust trails: [Animator("dust burst"), world_pos, size, tint,
        # fade]. A `fx.trail` projectile sheds one per `spacing` px; each plays
        # its one-shot burst where it was dropped, then is culled.
        self._trail_fx: list = []
        self._last_move_dir = pygame.Vector2(1, 0)
        self._awaiting_level_up = False
        self._hurt_flash_t = 0.0
        self._boss_warning_t = 0.0
        self._boss_name = ""
        self._banner_font = fonts.heading(40)
        self._prompt_font = fonts.heading(20)

        # World-layer painter. Read-only view of this state (see rendering.py).
        self.renderer = WorldRenderer(self)
        # Per-frame hit-detection passes (see combat.py).
        self.combat = CombatResolver(self)
        # Unit bumping: overlapping bodies shove each other (see physics.py).
        self.bump = BumpResolver(self)
        # Hostile projectiles, hazards, blast visuals, death poofs (see effects.py).
        self.fx = TransientFx(self)
        # Flow-field steering queries (see navigation.py).
        self.nav = NavCoordinator(self)

        # `currency` = Salvage banked to the save at run end (boss + elite arena).
        # `gold` = spent in-run at the Merchant only, never banked.
        self.stats = {"time": 0.0, "level": 1, "kills": 0, "damage_dealt": 0.0,
                      "xp": 0, "currency": 0, "gold": 0, "dropped_items": []}
        self._drop_counter = 0

    def _init_nav(self) -> None:
        """Enemy flow-field navigation (config.ENEMY_PATHFINDING). Built once from
        the static layout; rebuilt toward the player on a timer by
        `NavCoordinator.update`. Inert until a behaviour reads `ctx.nav_dir` (M4).
        The counters here are read by `_report_debug` and `test_enemy_nav`."""
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

    def _subscribe_events(self) -> None:
        """Own our feedback subscriptions so they can be removed cleanly on exit
        (the bus also carries persistent listeners such as audio)."""
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
            self.locations.activate_nearby()
        elif event.key == pygame.K_BACKQUOTE and self.dev_mode:
            from game.states.dev_menu_state import DevMenuState
            self.game.state_machine.push(DevMenuState(self.game), playing=self)

    def handle_debug_key(self, key: int) -> bool:
        keys = config.DEBUG_KEYS
        if key == keys["toggle_invuln"]:
            self.player.invulnerable = not self.player.invulnerable
            log.info("debug: invulnerable = %s", self.player.invulnerable)
        elif key == keys["spawn_enemy"]:
            self.spawn.spawn_enemy("elite" if self.rng.random() < 0.3 else "chaser")
        elif key == keys["grant_xp"]:
            self.levels.add_xp(25)
        elif key == keys["force_level_up"]:
            self.levels.add_xp(xp_for_level(self.levels.level) - self.levels.xp_into_level)
        elif key == keys["spawn_boss"]:
            self.spawn.spawn_boss()
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
            self.fx.spawn_death_fx(self.player.pos, getattr(self.player, "_facing", 1),
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
            self._trail_fx.clear()
            self.player.alive = True
            self.player.hp = max(self.player.hp, self._dev_hp_floor,
                                 self.player.max_hp * 0.5)
            return
        self._death_seq_t -= dt
        self._update_hero_anim(dt)
        self.fx.update_death_fx(dt)
        self.fx.update_trail_fx(dt)
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
        self.nav.update(dt)
        self.spawn.tick_director(dt)

        ectx = self._enemy_context(dt)
        for e in self.enemies:
            e.update(ectx)
        if self.boss is not None and self.boss.alive:
            self.boss.update(ectx)

        self.bump.resolve()          # CB-3: overlapping bodies shove each other

        self.fx.update_projectiles(dt)

        self._update_summons(dt)
        self.fx.update_hazards(dt)
        self.fx.update_melee_hitboxes(dt)
        self.locations.update_elite_arenas()
        self.fx.update_death_fx(dt)
        self.fx.update_trail_fx(dt)
        self.particles.update(dt)
        self.damage_numbers.update(dt)
        self.shake.update(dt)
        self.fx.update_explosions(dt)
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

        self.combat.resolve()

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

    def _enemy_context(self, dt: float) -> PlayingPerception:
        """One object per frame, handed to every enemy and the boss (satisfies
        the `entities.ai` `Perception` + `Combat` protocols; the boss duck-types
        the same attributes)."""
        return PlayingPerception(
            dt=dt, now=self.stats["time"], player_pos=self.player.pos,
            player=self.player, rng=self.rng,
            nav_dir=self.nav.direction, neighbors=self.nav.neighbors,
            obstacles_near=self.nav.obstacles_near,
            is_walkable=self.game_map.is_walkable,
            resolve_movement=self.game_map.resolve_movement,
            fire_projectile=self.fx.fire_hostile, summon=self.spawn.summon,
            explosion=self.fx.explosion, spawn_hazard=self.fx.spawn_hazard,
            melee_hit=self.fx.melee_hit,
            report_damage=self._report_dot)

    # Nav-field steering (see navigation.py); these two names are called by
    # `test_enemy_nav` directly.
    def _update_nav(self, dt: float) -> None:
        self.nav.update(dt)

    def _nav_dir(self, pos, radius) -> pygame.Vector2:
        return self.nav.direction(pos, radius)

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

    # --- spawning (see spawning.py) --------------------
    def _in_world_margin(self, pos: pygame.Vector2, margin: float) -> bool:
        return (-margin <= pos.x <= self.game_map.width + margin
                and -margin <= pos.y <= self.game_map.height + margin)

    # Delegators: F2/F5 debug keys, elite arenas, and many tests call these.
    def _spawn_enemy(self, enemy_id, at=None) -> None:
        self.spawn.spawn_enemy(enemy_id, at)

    def _spawn_boss(self) -> None:
        self.spawn.spawn_boss()

    # --- special locations (see locations.py) -----------
    # Thin forwarders for the `use_*` / `_update_elite_arenas` names the
    # interactables tests call directly.
    def _use_shrine(self, it):    self.locations.use_shrine(it)
    def _use_treasure(self, it):  self.locations.use_treasure(it)
    def _use_fountain(self, it):  self.locations.use_fountain(it)
    def _use_altar(self, it):     self.locations.use_altar(it)
    def _use_merchant(self, it):  self.locations.use_merchant(it)

    def _update_elite_arenas(self) -> None:
        self.locations.update_elite_arenas()

    def _resolve_visual(self, kw: dict) -> None:
        """Fill `color` / `style` / `fx` from `data/weapon_visuals.json` for a
        spawn that named its `weapon_id`. An explicit value in `kw` (e.g. the
        wolf's bite) wins; a spawn with no `weapon_id` keeps the pool default."""
        wid = kw.pop("weapon_id", "")
        if not wid:
            return
        vis = self.content.weapon_visual(wid)
        kw.setdefault("color", vis.color)
        kw.setdefault("style", vis.style)
        kw.setdefault("fx", vis.fx)

    def _spawn_projectile(self, **kw):
        proj = self.projectiles.acquire()
        if proj is None:
            return None
        self._resolve_visual(kw)
        proj.reset(**kw)
        self.game.audio.play_shoot()
        return proj

    # --- summons (spec 5.8) ------------------------------
    def _spawn_summon(self, **kw):
        s = self.summons.acquire()
        if s is None:
            return None
        self._resolve_visual(kw)
        kw.pop("style", None)                 # summons dispatch their draw on `kind`
        s.reset(**kw)
        return s

    def _update_summons(self, dt: float) -> None:
        sctx = SimpleNamespace(enemies=self._targetables(),
                               spawn_projectile=self._spawn_projectile,
                               player_pos=self.player.pos)
        for s in self.summons:
            s.update(dt, sctx)
        self.summons.sweep()

    # --- transient FX (see effects.py) -----------------
    def _spawn_hazard(self, *a, **kw):    # tests call this one
        self.fx.spawn_hazard(*a, **kw)

    def _update_death_fx(self, dt: float) -> None:  # tests call this one
        self.fx.update_death_fx(dt)

    # --- collision resolution (see combat.py) -----------
    def _cull_dead_enemies(self) -> None:   # tests reach for this one
        self.combat.cull_dead_enemies()

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
                self.fx.enemy_explosion(enemy.pos, 70.0, float(amount) or 16.0)
            elif effect == "shock_spread" and "shock" in enemy.status:
                self._spread_status(enemy.pos, "shock", 3.0, 0.12)

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
        self.fx.spawn_death_fx(self.boss.pos, getattr(self.boss, "_facing", 1),
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
        d.set_metric("melee hitboxes", len(self.melee_hitboxes))
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
            self.renderer.interactables(surface)
            self.renderer.hazards(surface)
            self.renderer.gems(surface)
            self.renderer.explosions(surface)
            self.renderer.trail_fx(surface)             # projectile dust trails, under the bolts
            self._draw_player_projectiles(surface)      # weapon effects sit behind the characters
            self._draw_depth_layer(surface)
            self._draw_hostile_projectiles(surface)     # enemy shots stay on top (danger readability)
            self.particles.draw(surface, self.camera)
            self.damage_numbers.draw(surface, self.camera)
            self.renderer.collider_overlay(surface)     # dev-only, on top of the world
        finally:
            self.camera.pos += offset

        self.hud.draw(surface, self.player, self.stats,
                      xp_fraction=self.levels.progress_fraction, boss=self.boss)
        self.renderer.feedback_overlays(surface)
    # --- render: scene composition ---------------
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

    # --- render: thin forwarders to WorldRenderer -------------
    # The bodies live in `game/states/playing/rendering.py`; these stay so that
    # `draw()` / `_depth_items()` and existing call sites + tests keep a stable
    # `PlayingState` surface. `_hit_tinted` / `_draw_cone` are pure helpers.
    _hit_tinted = staticmethod(_rendering.hit_tinted)
    _draw_cone = staticmethod(_rendering.draw_cone)

    def _sprite_drop(self, radius: float) -> float:
        return self.renderer.sprite_drop(radius)

    def _draw_player(self, surface) -> None:
        self.renderer.player(surface)

    def _draw_one_enemy(self, surface, e) -> None:
        self.renderer.one_enemy(surface, e)

    def _draw_boss(self, surface) -> None:
        self.renderer.boss(surface)

    def _draw_one_summon(self, surface, s) -> None:
        self.renderer.one_summon(surface, s)

    def _draw_death_fx(self, surface, fx) -> None:
        self.renderer.death_fx(surface, fx)

    def _draw_player_projectiles(self, surface) -> None:
        self.renderer.player_projectiles(surface)

    def _draw_hostile_projectiles(self, surface) -> None:
        self.renderer.hostile_projectiles(surface)
