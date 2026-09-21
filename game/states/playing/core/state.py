"""PLAYING: the actual run.

Pipeline order (spec 1.3): INPUT -> UPDATE -> COLLISION/COMBAT -> PROGRESSION,
with RENDER in draw(). `PlayingState` is the coordinator: it builds the
`Run` (`core/run.py`) and the sub-systems over it, owns the frame pipeline
and the draw order, routes events, and forwards the names the tests and the
older call sites read. The rules live beside it, one concern per module:

    run.py          the run's state and its few whole-run rules
    combat.py       the per-frame hit passes          effects.py   spawns, hazards, fx
    spawning.py     the spawn master's host           rewards.py   kills, drops, level-ups
    run_end.py      the banner, the summary, the hand-off
    hero.py         the hero's set-up and animation   physics.py   bumping
    locations.py    the interactables                 buffs.py     the buff buildings
    chests.py / npcs.py / fish_huts.py / navigation.py / hints.py / perception.py
    ../devtools/    dev flags, overlays, the DPS meter
    ../visual/      the world renderer and the scene composition

Milestone 4 added the enemy variants driven by `entities.ai`, the spawn
director with HP/speed scaling, hostile projectiles and the boss whose death
wins the run; structure review D (2026-09-20) moved the run's state into
`Run` and the payout / end / hero / dev rules into their own modules.
"""
from __future__ import annotations

import logging
import random

import pygame

from game import config, fonts
from game.content import get_content
from game.events import Events
from game.state import State
from entities.player import Player
from entities.projectile import Projectile
from entities.pickup import XPGem
from entities.potion import HealthPotion
from entities.summon import Summon
from combat.weapons import Weapon, FireContext
from combat.elements import area as wind_area
from game.states.playing.visual import elements as element_fx
from game.states.playing.visual.elements import ElementVisuals
from combat.elements.runtime import build_resolver
from progression.experience import LevelTracker
from game.states.playing.core.aim import AimInput, read_aim
from progression.blessings import get_catalog, rebuild as rebuild_blessings
from systems.camera import Camera
from systems.collision import SpatialGrid
from systems.object_pool import Pool
from systems.particles import ParticleSystem
from systems.screen_shake import ScreenShake
from ui.hud import HUD
from game.display import uibox
from ui.damage_numbers import DamageNumbers
from world.map import GameMap
from world.nav.field import NavField
from spawn.budget import SpawnDirector
from game.states.playing.visual import rendering as _rendering
from game.states.playing.visual import hints as hints_draw
from game.states.playing.visual import key_marker
from game.states.playing.visual import scene, slam_fx, slash_fx
from game.states.playing.visual.rendering import WorldRenderer
from game.states.playing.core import hero as hero_rules
from game.states.playing.core import interactions
from game.states.playing.core.buffs import BuffSystem
from game.states.playing.core.chests import Chests
from game.states.playing.core.combat import CombatResolver
from game.states.playing.core.effects import TransientFx
from game.states.playing.core.fish_huts import FishHuts
from game.states.playing.core.hints import RunHints
from game.states.playing.core.locations import SpecialLocations
from game.states.playing.core.navigation import NavCoordinator
from game.states.playing.core.npcs import Npcs
from game.states.playing.core.perception import PlayingPerception
from game.states.playing.core.physics import BumpResolver
from game.states.playing.core.rewards import Rewards
from game.states.playing.core.run import ALIASES, FIELDS, Run
from game.states.playing.core.run_end import RunEnd
from game.states.playing.core.run_ledger import RunLedger
from game.states.playing.core.spawning import EnemyControl
from game.states.playing.devtools.dev_flags import DevFlags
from game.states.playing.devtools.dps_meter import DpsMeter

log = logging.getLogger(__name__)

STARTING_WEAPON = hero_rules.STARTING_WEAPON


def _forward(owner: str, name: str) -> property:
    """A property reading and writing `self.<owner>.<name>` -- how the
    state keeps the names that moved into `Run` and the extracted modules."""
    return property(lambda self: getattr(getattr(self, owner), name),
                    lambda self, v: setattr(getattr(self, owner), name, v))


class PlayingState(State):
    # The world fills the render surface; the HUD is drawn on the UI box
    # from `draw` itself (see there). Mouse events arrive in surface
    # coordinates, which is what the manual aim reads against the camera.
    ui_box = False
    # The run's track. Swapping to it here rather than on the loading
    # screen means the crossfade lands as the world appears.
    music = "gameplay"

    def enter(self, *, seed: int | None = None, character_id: str | None = None,
              dev: bool = False, difficulty: str | None = None,
              prebuilt=None, main_weapon: str | None = None, **kwargs) -> None:
        self._chosen_main_weapon = main_weapon      # P5: from the hero select
        # `prebuilt` is the loading screen's world -- a baked `GameMap` and a
        # `NavField` built a slice at a time under this same seed. Without it
        # the run builds everything here, as the tests and any other caller do.
        self._prebuilt = prebuilt
        self._init_run(seed, dev, difficulty)
        self._init_world()
        self._init_player(character_id)
        self._init_scaffold()
        self._init_nav()
        self._subscribe_events()
        # The opening Move / Attack keycap hints (journal: key_icons_journal.md):
        # last, since they read the hero's spawn.
        self.hints = RunHints(self)

    # --- enter() steps ---------------------------------------------
    def _init_run(self, seed, dev, difficulty) -> None:
        """The `Run` -- seed, RNG, difficulty -- and the developer switches."""
        run_seed = seed if seed is not None else random.randrange(1 << 30)
        self.run = Run(
            seed=run_seed, rng=random.Random(run_seed),
            difficulty=(difficulty if difficulty in config.DIFFICULTIES
                        else config.DIFFICULTY_DEFAULT),
            dev_mode=bool(dev),          # developer sandbox: no save, restart on end
            content=get_content(), game=self.game,
            auto_attack=config.AUTO_ATTACK_DEFAULT, aim=AimInput.none())
        self.dev = DevFlags()

    def _init_world(self) -> None:
        """The map, its special locations, and the phase-based spawn director."""
        run = self.run
        run.game_map = (self._prebuilt.game_map if self._prebuilt is not None
                        else GameMap(seed=run.seed))
        self.locations = SpecialLocations(self)
        # The buff buildings' timed buffs (journal: buff_buildings_journal.md).
        self.buffs = BuffSystem(self)
        self.locations.build()
        # CB-9: the treasure chests the seed seated across the islands.
        self.chest_manager = Chests(self)
        self.chest_manager.build()
        # The villagers (HI-3): scenery that moves, from the village records.
        self.npc_manager = Npcs(self)
        self.npc_manager.build()
        self.fish_hut_manager = FishHuts(self)
        self.fish_hut_manager.build()
        self.director = SpawnDirector(config.RUN_DURATION_SECONDS, rng=run.rng,
                                      difficulty=run.difficulty)
        self.spawn = EnemyControl(self)

    def _init_player(self, character_id) -> None:
        """The hero: stats, starting weapon, sprite rig, persistent bonuses,
        blessing library, and the camera that follows it."""
        run = self.run
        start = run.game_map.center
        run.character_id = character_id or next(iter(run.content.characters))
        cdef = run.content.character(run.character_id)
        run.player = Player(start.x, start.y,
                            base_stats=cdef.get("base_stats"),
                            trait=cdef.get("trait", ""),
                            trait_params=cdef.get("trait_params"),
                            character_id=run.character_id, rng=run.rng)
        weapon_id = hero_rules.main_weapon_for(run, cdef, self._chosen_main_weapon)
        run.player.weapons = [Weapon(weapon_id, run.content.weapon(weapon_id))]
        self.hero = hero_rules.HeroAnim(run, cdef)

        # Meta-progression + equipped items applied before the run starts.
        hero_rules.apply_persistent_bonuses(run)

        # The blessing catalog (P2). `blessing_lib` is the older name the dev
        # menu and its tests use for the same object.
        self.catalog = get_catalog(run.content)
        self.blessing_lib = self.catalog
        rebuild_blessings(run.player)

        # The world is drawn straight to the screen; `Camera.zoom` magnifies at
        # draw time -- `config.effective_zoom()`, the design zoom times the
        # native render scale -- so sprites stay crisp and the view covers
        # the same world area at every window size. HUD is unscaled.
        run.camera = Camera(run.game_map.width, run.game_map.height,
                            config.SCREEN_WIDTH, config.SCREEN_HEIGHT,
                            zoom=config.effective_zoom())
        run.camera.snap_to(run.player.pos)

    def _init_scaffold(self) -> None:
        """Entity pools, the feedback systems, HUD/levels, the run stats, the
        sub-systems, and the on-screen fonts."""
        run = self.run
        run.projectiles = Pool(Projectile, config.MAX_PROJECTILES, prefill=128)
        run.hostiles = Pool(Projectile, config.MAX_PROJECTILES, prefill=64)
        run.gems = Pool(XPGem, config.MAX_PROJECTILES, prefill=64)
        # CB-8: health potions dropped by enemies. Capped from data so a
        # potion flood degrades gracefully like every other pool.
        run.potions = Pool(HealthPotion, int(run.content.potions.get("pool_size", 64)),
                           prefill=8)
        run.summons = Pool(Summon, 32, prefill=8)
        run.particles = ParticleSystem()
        run.damage_numbers = DamageNumbers()
        run.shake = ScreenShake()
        run.grid = SpatialGrid()
        run.levels = LevelTracker()
        # `currency` = Salvage banked to the save at run end (boss + elite arena).
        # `gold` = spent in-run at the Merchant only, never banked.
        run.stats = {"time": 0.0, "level": 1, "kills": 0, "damage_dealt": 0.0,
                     "xp": 0, "currency": 0, "gold": 0, "gold_earned": 0,
                     "dropped_items": [],
                     "potions": 0, "potion_healing": 0.0,
                     "chests": 0}          # CB-9: treasure chests opened
        # Damage per source and kills per enemy type for the whole run, fed
        # through every enemy's `ledger` attribute (`core/run_ledger.py`). Built
        # before anything can spawn: the spawner hands it to each enemy.
        run.ledger = RunLedger()
        # The elemental resolver: the aura rules, the reaction budget and
        # the per-enemy-type profiles, resolved once here because the data
        # does not change mid-run.
        run.elements = build_resolver(run)
        run.element_visuals = ElementVisuals(run.content)

        self.hud = HUD()
        self._banner_font = fonts.heading(40)
        self._prompt_font = fonts.heading(20)

        # World-layer painter. Read-only view of this state (see rendering.py).
        self.renderer = WorldRenderer(self)
        # Per-frame hit-detection passes (see combat.py).
        self.combat = CombatResolver(self)
        # Unit bumping: overlapping bodies shove each other (see physics.py).
        self.bump = BumpResolver(self)
        # Hostile projectiles, hazards, blast visuals, death poofs, and the
        # hero's own spawns (see effects.py).
        self.fx = TransientFx(self)
        # Flow-field steering queries (see navigation.py).
        self.nav = NavCoordinator(self)
        # Kills, drops, potions, level-ups (see rewards.py); how the run ends
        # (see run_end.py).
        self.rewards = Rewards(self)
        self.run_end = RunEnd(self)
        # Damage-per-second against the dev menu's training dummy. Inert --
        # and free -- until something arms it (`devtools/dps_meter.py`).
        self.dps = DpsMeter()

    def _init_nav(self) -> None:
        """Enemy flow-field navigation (config.ENEMY_PATHFINDING). Built once from
        the static layout; rebuilt toward the player on a timer by
        `NavCoordinator.update`. Inert until a behaviour reads `ctx.nav_dir` (M4).
        The counters here are read by `report_debug` and `test_enemy_nav`."""
        self._nav: NavField | None = None
        self._nav_t = 0.0
        self._nav_rr = 0                  # round-robin index over the nav classes
        self._nav_last_ms = 0.0          # last rebuild cost (debug overlay)
        self._nav_rebuilds = 0
        self._obstacle_grid: SpatialGrid | None = None
        gm = self.game_map
        if config.ENEMY_PATHFINDING and gm.layout is not None:
            ready = getattr(self._prebuilt, "nav", None)
            self._nav = (ready if ready is not None
                         else NavField(gm.layout, gm.obstacles))
            self._nav.rebuild(self.player.pos)
            self._nav_t = config.ENEMY_NAV_REBUILD_INTERVAL
            # Static -> built once; `path_chase` reads it for local obstacle
            # avoidance (a push off the nearest prop, on top of the field).
            self._obstacle_grid = SpatialGrid()
            self._obstacle_grid.rebuild(gm.obstacles)

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
        spawn = getattr(self, "spawn", None)
        if spawn is not None:
            spawn.close()                    # the master's pacing signals

    # --- events -------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.run.tap_pending = True   # one click-attack, consumed on fire
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == config.KEY_TOGGLE_AUTO_ATTACK:
            self.run.auto_attack = not self.run.auto_attack
            log.info("auto attack %s", "on" if self.run.auto_attack else "off")
        elif event.key == pygame.K_TAB:
            # The build screen: an overlay over the frozen run (journal:
            # run_status_journal.md). TAB again, or ESC, closes it.
            from game.states.run_status_state import RunStatusState
            self.game.state_machine.push(RunStatusState(self.game), playing=self)
        elif event.key == pygame.K_ESCAPE:
            from game.states.paused_state import PausedState
            self.hints.dismiss()             # the pause menu lists every key
            self._suspend_mouse()
            self.game.state_machine.push(PausedState(self.game))
        elif event.key == config.KEY_INTERACT:
            # The closest usable chest or location within reach -- the one
            # the keycap is floating over (journal: key_icons_journal.md).
            target = interactions.nearest(self)
            if target is not None:
                interactions.activate(self, target)
        elif event.key == pygame.K_BACKQUOTE and self.dev_mode:
            from game.states.dev_menu_state import DevMenuState
            self._suspend_mouse()
            self.game.state_machine.push(DevMenuState(self.game), playing=self)

    def _suspend_mouse(self) -> None:
        """An overlay is about to cover the run: forget any queued tap and
        ignore the button until it has been up for a frame, so the click that
        closes the overlay cannot land as an attack."""
        self.run.tap_pending = False
        self.run.mouse_armed = False

    def on_display_changed(self) -> None:
        """The display was re-opened under the run (Options from the pause
        menu; stage 1b of the native-resolution journal). The camera is
        rebuilt for the new surface and effective zoom at the same world
        centre, so the hero does not move on screen; the fonts and the HUD
        follow the new scale; the sea buffer is re-tiled for the new world
        span; and one frame of the world is drawn off screen so the terrain
        and sprite caches refill before the player sees the next one."""
        old = self.camera
        span_w, span_h = old.world_span()
        centre = pygame.Vector2(old.pos.x + span_w / 2.0, old.pos.y + span_h / 2.0)
        cam = Camera(self.game_map.width, self.game_map.height,
                     config.SCREEN_WIDTH, config.SCREEN_HEIGHT,
                     zoom=config.effective_zoom())
        cam.follow_lerp = old.follow_lerp
        cam.snap_to(centre)
        self.camera = cam
        self.hud = HUD()
        self._banner_font = fonts.heading(40)
        self._prompt_font = fonts.heading(20)
        gm = self.game_map
        if getattr(gm, "_tiles_ready", False):
            from world.terrain import bake as terrain_bake
            buf, wt = terrain_bake.water_buffer(self.game.assets)
            if buf is not None:
                gm._water_buf, gm._water_tile = buf, wt
        try:
            scratch = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
            self._draw_world(scratch)
        except pygame.error:
            pass                                   # a headless surface: no warm-up

    def handle_debug_key(self, key: int) -> bool:
        return self.dev.handle_debug_key(self, key)

    # --- pipeline ---------------------------------------------
    def update(self, dt: float) -> None:
        if self.run_end.ending:
            self.run_end.ending_sequence(dt)
            return

        self._phase_input()
        self.hints.update(dt)
        self._phase_update(dt)
        self._phase_combat(dt)
        self._phase_progression(dt)
        run = self.run
        run.stats["time"] += dt
        run.ledger.now = run.stats["time"]
        run.ledger.track_held(w.weapon_id for w in run.player.weapons)
        self.dps.update(dt)
        self.dev.apply_unlimited_hp(run)
        if not run.player.alive:
            # The shared death poof, then the end banner over the scene: the
            # run keeps animating its effects under it and hands off to the
            # summary when the banner has played (journal: end_banner_journal.md).
            self.fx.spawn_death_fx(run.player.pos, getattr(run.player, "_facing", 1),
                                   radius=run.player.radius)
            self.run_end.begin(victory=False)
        self.dev.report_debug(self)

    def _phase_input(self) -> None:
        run = self.run
        pressed = pygame.key.get_pressed()
        keys = self.game.keys
        run.player.handle_input(pressed, keys["move"])
        if run.player._move_dir.length_squared() > 0:
            run.last_move_dir = run.player._move_dir.copy()
        buttons = pygame.mouse.get_pressed()
        if not run.mouse_armed and not any(buttons):
            run.mouse_armed = True            # released once since the overlay
        # CB-5: this frame's manual aim, if any. It faces the hero; the combat
        # phase decides what to do with it.
        run.aim = read_aim(pressed, buttons,
                           pygame.mouse.get_pos(), run.camera, run.player.pos,
                           keys["aim"], run.last_move_dir,
                           tap_pending=run.tap_pending, armed=run.mouse_armed)
        if run.aim.active:
            run.player.face(run.aim.direction)

    def consume_tap(self) -> None:
        """The queued click-attack went off (called by the combat phase)."""
        self.run.tap_pending = False

    def _phase_update(self, dt: float) -> None:
        run = self.run
        run.player.update(dt, run.game_map)
        # Footsteps follow the *input* direction, not the resolved motion, so
        # a shove or a walk into a wall does not produce phantom steps. The
        # cadence lives in the audio system (`_Footsteps`).
        self.game.audio.tick_footsteps(
            dt, run.player._move_dir.length_squared() > 0,
            run.player.move_speed)
        self.hero.update(dt)
        run.camera.update(dt, run.player.pos)
        self.nav.update(dt)
        self.spawn.tick_director(dt)

        ectx = self._enemy_context(dt)
        run.frame += 1
        lod = config.ENEMY_LOD_SKIP
        if lod > 1:
            # Spawn master S7 tick LOD: an enemy that is neither chasing nor
            # on screen updates every `lod` frames with a `dt` spanning the
            # gap, and sits the frames between out entirely. The profile
            # put the per-enemy cost in the movement probe, not the AI, so
            # the whole frame is skipped, not just the behaviour tick.
            lod_ctx = self._enemy_context(dt * lod)
            view = run.camera.visible_rect().inflate(config.ENEMY_LOD_VIEW_PAD,
                                                     config.ENEMY_LOD_VIEW_PAD)
            eligible = self.spawn.lod_eligible
            for i, e in enumerate(run.enemies):
                if eligible(e, view):
                    if (run.frame + i) % lod == 0:
                        e.update(lod_ctx)
                else:
                    e.update(ectx)
        else:
            for e in run.enemies:
                e.update(ectx)
        if run.boss is not None and run.boss.alive:
            run.boss.update(ectx)

        self.bump.resolve()          # CB-3: overlapping bodies shove each other
        self.buffs.update(dt)        # timers, Turbo's bites, Pinball's throws

        self.fx.update_projectiles(dt)

        self.fx.update_summons(dt)
        self.npc_manager.update(dt)
        self.fish_hut_manager.update(dt)
        self.fx.update_hazards(dt)
        # Elemental Wind areas: they follow the enemy they formed on and
        # check contact at their own low rate, so this is a short list
        # walk (design 9.7).
        run.wind_areas = wind_area.update_all(
            run.wind_areas, run.stats["time"], run.elements.world)
        element_fx.sweep(run, run.stats["time"])
        run.element_visuals.update(dt)
        self.fx.update_melee_hitboxes(dt)
        self.chest_manager.update(dt)      # CB-9: the lids that are opening
        self.fx.update_death_fx(dt)
        self.fx.update_trail_fx(dt)
        self.fx.update_spawn_fx(dt)
        run.particles.update(dt)
        run.damage_numbers.update(dt)
        run.shake.update(dt)
        self.fx.update_explosions(dt)
        slam_fx.update_impacts(self, dt)
        slash_fx.update(self, dt)
        run.hurt_flash_t = max(0.0, run.hurt_flash_t - dt)
        run.boss_warning_t = max(0.0, run.boss_warning_t - dt)
        run.notice_t = max(0.0, run.notice_t - dt)

    def _phase_combat(self, dt: float) -> None:
        run = self.run
        run.grid.rebuild(run.enemies)
        # Elemental system: reset this frame's reaction budget and run
        # whatever the last frame's budget held over (design 9.3).
        run.elements.begin_frame(run.stats["time"])

        s = run.player.stats
        ctx = FireContext(
            origin=run.player.pos, enemies=run.targetables(),
            damage_multiplier=s["damage_multiplier"] * run.player.outgoing_damage_multiplier(),
            attack_speed_multiplier=s["attack_speed_multiplier"],
            projectile_speed_multiplier=s["projectile_speed_multiplier"],
            area_multiplier=s["area_multiplier"], fallback_dir=run.last_move_dir,
            spawn_projectile=self._spawn_projectile, anchor=run.player.pos,
            crit_chance=min(0.75, 0.02 * s["luck"] + s["crit_chance"]),
            crit_multiplier=2.0 + s["crit_damage"],
            rng=run.rng, spawn_summon=self._spawn_summon,
            aim=run.aim, auto_attack=run.auto_attack,
            weapon_mods=run.player.weapon_mods,
            melee_damage_mult=1.0 + s["melee_damage"],
            ranged_damage_mult=1.0 + s["ranged_damage"],
            spawn_hazard=self._spawn_hero_hazard,
            spawn_impact=self._spawn_impact)
        if not (run.dev_mode and self.dev.no_attack):
            main = run.player.weapons[0] if run.player.weapons else None
            tap_fired = False
            for weapon in run.player.weapons:
                fired = weapon.update(dt, ctx)
                if fired and weapon is main:
                    run.player.trigger_attack_anim()   # anim syncs to the main weapon only
                tap_fired = tap_fired or fired
            # CB-5: a queued click is one attack -- spent on the frame any
            # directional weapon fires from it.
            if tap_fired and run.aim.tap:
                self.consume_tap()

        self.combat.resolve()

    def _phase_progression(self, dt: float) -> None:
        run = self.run
        self.rewards.collect_gems(dt)
        self.rewards.collect_potions(dt)
        run.stats["level"] = run.levels.level
        if run.levels.pending_level_ups > 0 and not self.rewards.awaiting_level_up:
            self.rewards.open_level_up()

    # --- context builders ---------------------------------
    def _enemy_context(self, dt: float) -> PlayingPerception:
        """One object per frame, handed to every enemy and the boss (satisfies
        the `entities.ai` `Perception` + `Combat` protocols; the boss duck-types
        the same attributes)."""
        run = self.run
        return PlayingPerception(
            dt=dt, now=run.stats["time"], player_pos=run.player.pos,
            player=run.player, rng=run.rng,
            nav_dir=self.nav.direction, neighbors=self.nav.neighbors,
            obstacles_near=self.nav.obstacles_near,
            is_walkable=run.game_map.is_walkable,
            resolve_movement=run.game_map.resolve_movement,
            fire_projectile=self.fx.fire_hostile, summon=self.spawn.summon,
            explosion=self.fx.explosion, spawn_hazard=self.fx.spawn_hazard,
            melee_hit=self.fx.melee_hit,
            report_damage=self._report_dot)

    def _report_dot(self, amount: float) -> None:
        self.run.stats["damage_dealt"] += amount

    # --- event handlers ----------------------------
    def _on_player_damaged(self, *, amount) -> None:
        run = self.run
        run.shake.add(min(0.4, 0.05 + amount * 0.02))
        run.hurt_flash_t = min(0.35, run.hurt_flash_t + 0.12 + amount * 0.01)
        if amount > 0:
            run.damage_numbers.add(run.player.pos, amount, incoming=True)

    def _on_boss_spawned(self, *, name) -> None:
        self.run.boss_warning_t = 2.6
        self.run.boss_name = name

    # --- render ---------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        run = self.run
        # Screen-shake is an amplitude in screen pixels; camera.pos is world
        # space, so convert through the zoom before nudging it.
        offset = run.shake.offset / run.camera.zoom
        run.camera.pos -= offset
        try:
            # The elemental state of the field is painted terrace by terrace
            # inside `_draw_world`, under the bodies it belongs to; this
            # resets the per-frame budget and counter before those passes
            # start (M10 rule 3).
            element_fx.begin_frame(run)
            self._draw_world(surface)
            self._draw_hostile_projectiles(surface)     # enemy shots stay on top (danger readability)
            run.particles.draw(surface, run.camera)
            run.damage_numbers.draw(surface, run.camera)
            element_fx.draw_reactions(surface, run)     # over everything, and brief
            self.renderer.collider_overlay(surface)     # dev-only, on top of the world
            self.renderer.spawn_point_overlay(surface)  # dev-only, same layer
            self.renderer.aim_overlay(surface)          # dev-only, same layer
            self.renderer.aura_overlay(surface)         # dev-only, same layer
            key_marker.draw(surface, self)              # the interact cap, over its element
            hints_draw.draw(surface, self)              # the opening Move / Attack hints
        finally:
            run.camera.pos += offset

        # The world above fills the render surface (2100 wide on a 21:9
        # render); the interface stays in the centred 16:9 box.
        box = uibox.box(surface)
        self.hud.draw(box, run.player, run.stats,
                      xp_fraction=run.levels.progress_fraction, boss=run.boss)
        self.renderer.feedback_overlays(surface, box)

    # =================================================================
    # Forwarders: the names the tests, the overlays and the older call
    # sites read on the state, now kept elsewhere. Kept thin and together.
    # =================================================================

    # --- the run's state (core/run.py): every `Run` field under its own
    # name and the `ALIASES`, installed below the class ----------------
    def notice(self, text: str, seconds: float = 2.5) -> None:
        self.run.notice(text, seconds)

    # Applied to `self.run`, or to `self` when there is none: the gold tests
    # call these unbound on a bare namespace that carries only `stats`.
    def add_gold(self, amount: int) -> int:
        return Run.add_gold(getattr(self, "run", self), amount)

    def spend_gold(self, amount: int) -> bool:
        return Run.spend_gold(getattr(self, "run", self), amount)

    def _targetables(self) -> list:
        return self.run.targetables()

    def _in_world_margin(self, pos: pygame.Vector2, margin: float) -> bool:
        return self.run.in_world_margin(pos, margin)

    # --- the hero (core/hero.py) --------------------------------------
    _hero_anim = _forward("hero", "anim")
    _hero_color = _forward("hero", "color")
    _hero_has_hurt = _forward("hero", "has_hurt")

    # The two rules read `_hero_anim` / `_hero_has_hurt` through the
    # properties above, so they also work unbound on a bare namespace that
    # sets those names directly (the hero-animation tests).
    def _hero_has_anim(self, name: str) -> bool:
        return hero_rules.has_anim(self._hero_anim, self.game.assets, name)

    def _hero_anim_name(self) -> str:
        return hero_rules.anim_name(self.player, self._hero_has_hurt, self._hero_has_anim)

    def _update_hero_anim(self, dt: float) -> None:
        self.hero.update(dt)

    def _main_weapon_for(self, cdef: dict) -> str:
        return hero_rules.main_weapon_for(self.run, cdef, self._chosen_main_weapon)

    _OP_MAP = hero_rules._OP_MAP             # the dev menu's item equip reads it

    # --- the developer switches (devtools/dev_flags.py) ----------------
    _dev_unlimited_hp = _forward("dev", "unlimited_hp")
    _dev_no_attack = _forward("dev", "no_attack")
    _dev_no_damage = _forward("dev", "no_damage")
    _dev_hp_floor = _forward("dev", "hp_floor")
    _dev_show_colliders = _forward("dev", "show_colliders")
    _dev_show_spawn_points = _forward("dev", "show_spawn_points")
    _dev_show_aim = _forward("dev", "show_aim")
    _dev_show_auras = _forward("dev", "show_auras")

    def _apply_dev_unlimited_hp(self) -> None:
        self.dev.apply_unlimited_hp(self.run)

    def _set_difficulty(self, name: str) -> None:
        self.dev.set_difficulty(self, name)

    def _report_debug(self) -> None:
        self.dev.report_debug(self)

    # --- spawning (see spawning.py); F2/F5, elite arenas and many tests ---
    def _spawn_enemy(self, enemy_id, at=None, owner="direct"):
        return self.spawn.spawn_enemy(enemy_id, at, owner=owner)

    # --- rewards, the run's end, the dev switches: flags the tests read ---
    _awaiting_level_up = _forward("rewards", "awaiting_level_up")
    _ending = _forward("run_end", "ending")

    def _apply_dev_unlimited_hp(self) -> None:
        self.dev.apply_unlimited_hp(self.run)

    def _set_difficulty(self, name: str) -> None:
        self.dev.set_difficulty(self, name)

    def _report_debug(self) -> None:
        self.dev.report_debug(self)

    # --- scene composition (see visual/scene.py) --------------------------
    def _depth_items(self) -> list:
        return scene.depth_items(self)

    def _draw_world(self, surface) -> None:
        scene.draw_world(self, surface)

    def _draw_flat_effects(self, surface, level: int) -> None:
        scene.draw_flat_effects(self, surface, level)

    def _actor_items(self) -> list:
        return scene.actor_items(self)

    # --- pure painters (see visual/rendering.py) ---------------------------
    _hit_tinted = staticmethod(_rendering.hit_tinted)
    _draw_cone = staticmethod(_rendering.draw_cone)


# The `Run` fields under their own names (`ps.enemies` is `ps.run.enemies`),
# and the underscore aliases the tests read (`ps._explosions`). `game` is
# left out: it is the state's own, set by `State.__init__`.
for _name in FIELDS:
    if _name != "game":
        setattr(PlayingState, _name, _forward("run", _name))
for _alias, _name in ALIASES.items():
    setattr(PlayingState, _alias, _forward("run", _name))
del _name, _alias


# The pass-through forwarders: `ps.<name>(...)` is `ps.<owner>.<method>(...)`.
# One table rather than sixty one-line methods -- it is the compatibility
# surface the tests and the older call sites read, kept legible as a list.
# A test may still patch one on the instance (`p._draw_player = ...`): an
# instance attribute shadows the class function as it always did.
_FORWARDERS = {
    # special locations (locations.py); the interactables tests
    "_use_shrine": ("locations", "use_shrine"), "_use_treasure": ("locations", "use_treasure"),
    "_use_fountain": ("locations", "use_fountain"), "_use_forge": ("locations", "use_forge"),
    "_use_altar": ("locations", "use_altar"), "_use_merchant": ("locations", "use_merchant"),
    # the spawn master's host (spawning.py)
    "_spawn_boss": ("spawn", "spawn_boss"),
    # the hero's spawns and the transient fx (effects.py)
    "_resolve_visual": ("fx", "resolve_visual"), "_spawn_projectile": ("fx", "spawn_projectile"),
    "_spawn_summon": ("fx", "spawn_summon"), "_spawn_impact": ("fx", "spawn_impact"),
    "_spawn_hero_hazard": ("fx", "spawn_hero_hazard"), "_spawn_hazard": ("fx", "spawn_hazard"),
    "_update_death_fx": ("fx", "update_death_fx"), "_update_summons": ("fx", "update_summons"),
    # collision resolution (combat.py)
    "_cull_dead_enemies": ("combat", "cull_dead_enemies"),
    # kills, drops, level-ups (rewards.py)
    "_on_enemy_killed": ("rewards", "on_enemy_killed"),
    "_apply_on_kill_effects": ("rewards", "apply_on_kill_effects"),
    "_spread_status": ("rewards", "spread_status"), "_on_boss_killed": ("rewards", "on_boss_killed"),
    "_roll_potion_drop": ("rewards", "roll_potion_drop"), "_collect_potions": ("rewards", "collect_potions"),
    "_drop_item": ("rewards", "drop_item"), "_open_level_up": ("rewards", "open_level_up"),
    "_on_level_up_chosen": ("rewards", "on_level_up_chosen"),
    # the run's end (run_end.py)
    "_begin_end": ("run_end", "begin"), "_end_run": ("run_end", "end"),
    "_snapshot_summary": ("run_end", "snapshot_summary"), "_hand_off": ("run_end", "hand_off"),
    "_restart_dev_run": ("run_end", "restart_dev_run"),
    "_run_ending_sequence": ("run_end", "ending_sequence"),
    # the hero's animation (hero.py)
    "_update_hero_anim": ("hero", "update"),
    # navigation (navigation.py); `test_enemy_nav` calls these
    "_update_nav": ("nav", "update"), "_nav_dir": ("nav", "direction"),
    # the painters (visual/rendering.py); the scene calls these, a test may patch them
    "_sprite_drop": ("renderer", "sprite_drop"), "_draw_player": ("renderer", "player"),
    "_draw_one_enemy": ("renderer", "one_enemy"), "_draw_boss": ("renderer", "boss"),
    "_draw_one_summon": ("renderer", "one_summon"), "_draw_death_fx": ("renderer", "death_fx"),
    "_draw_spawn_fx": ("renderer", "spawn_fx"),
    "_draw_player_projectiles": ("renderer", "player_projectiles"),
    "_draw_hostile_projectiles": ("renderer", "hostile_projectiles"),
}


# The owners a forwarder may build on the spot when `self` has none: a test
# calls `PlayingState._resolve_visual(fake, kw)` or
# `PlayingState._apply_on_kill_effects(fake, enemy)` unbound on a bare
# namespace, which carries the fields the rule reads but no sub-systems.
_OWNER_FACTORY = {"fx": TransientFx, "rewards": Rewards, "run_end": RunEnd,
                  "combat": CombatResolver}


def _delegate(owner: str, method: str):
    def call(self, *args, **kwargs):
        target = getattr(self, owner, None)
        if target is None and owner in _OWNER_FACTORY:
            target = _OWNER_FACTORY[owner](self)
        return getattr(target, method)(*args, **kwargs)
    call.__name__ = method
    call.__qualname__ = f"PlayingState.{method}"
    return call


for _name, (_owner, _method) in _FORWARDERS.items():
    setattr(PlayingState, _name, _delegate(_owner, _method))
del _name, _owner, _method
