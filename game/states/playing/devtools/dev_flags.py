"""The developer run's switches and readouts (structure review, D3).

`DevFlags` holds the toggles the dev menu and the F-keys flip -- unlimited
HP, silenced weapons, zero-damage hits, the three overlays -- and the rules
behind them: the HP ratchet, the debug key table, the live difficulty
switch, and the F1 overlay's metrics. All of it is a developer run's
business, so it sits with the other developer tooling.

`PlayingState` keeps the `_dev_*` names as properties over this object
(the dev menu writes them; the tests read them) and forwards
`handle_debug_key`, `_apply_dev_unlimited_hp`, `_set_difficulty` and
`_report_debug` here.
"""
from __future__ import annotations

import logging

from game import config

log = logging.getLogger(__name__)


class DevFlags:
    def __init__(self) -> None:
        self.unlimited_hp = False       # HP ratchet (dev menu D2)
        self.no_attack = False          # hero weapons silenced (dev menu D2)
        self.no_damage = False          # weapons still fire, hits deal 0 (dev menu)
        self.hp_floor = 0.0
        self.show_colliders = False     # F7 / dev menu: true collider overlay
        self.show_spawn_points = False  # F8 / dev menu: generated spawn points
        self.show_aim = False           # dev menu: CB-5 manual-aim line
        self.show_auras = False         # dev menu: elemental aura inspector
        self.show_reaction_log = False  # dev menu: CMB-009.4 reaction log

    def apply_unlimited_hp(self, run) -> None:
        """Dev toggle: HP never ends a frame lower than it started (it may still
        dip and flash mid-frame). Healing raises the floor; it never drops."""
        if not (run.dev_mode and self.unlimited_hp):
            return
        player = run.player
        self.hp_floor = max(self.hp_floor, player.hp)
        if player.hp < self.hp_floor:
            player.hp = self.hp_floor
        if not player.alive and self.hp_floor > 0.0:
            player.alive = True

    def set_difficulty(self, ps, name: str) -> None:
        """Dev-menu live switch. Re-binds the run's difficulty on the fly; the
        spawn schedule and the boss re-key off the new pace immediately -- see
        SpawnDirector.set_difficulty (raising the pace late can arm the boss on
        the next frame, which is intentional for testing)."""
        if name not in config.DIFFICULTIES:
            return
        ps.run.difficulty = name
        ps.director.set_difficulty(name)

    def handle_debug_key(self, ps, key: int) -> bool:
        """Return True if the key was a consumed debug binding."""
        run = ps.run
        keys = config.DEBUG_KEYS
        if key == keys["toggle_invuln"]:
            run.player.invulnerable = not run.player.invulnerable
            log.info("debug: invulnerable = %s", run.player.invulnerable)
        elif key == keys["spawn_enemy"]:
            ps.spawn.spawn_enemy("bear" if run.rng.random() < 0.3 else "skull",
                                 owner="dev")
        elif key == keys["grant_xp"]:
            run.levels.add_xp(25)
        elif key == keys["force_level_up"]:
            from progression.experience import xp_for_level
            run.levels.add_xp(xp_for_level(run.levels.level) - run.levels.xp_into_level)
        elif key == keys["spawn_boss"]:
            ps.spawn.spawn_boss()
        elif key == keys["toggle_collision_vis"]:
            if not run.dev_mode:
                return False                     # collider overlay is dev-only
            self.show_colliders = not self.show_colliders
        elif key == keys["toggle_spawn_vis"]:
            if not run.dev_mode:
                return False                     # spawn-point overlay is dev-only
            self.show_spawn_points = not self.show_spawn_points
        elif key == keys["reload_elements"]:
            if not run.dev_mode:
                return False                     # a tuning tool: dev-only
            from game.states.playing.devtools.element_reload import (
                reload_element_data)
            ok, message = reload_element_data(run)
            run.notice(message, seconds=2.5 if ok else 6.0)
        else:
            return False
        return True

    def report_debug(self, ps) -> None:
        """The F1 overlay's metrics for the run."""
        run = ps.run
        d = run.game.debug
        d.set_metric("state", "PLAYING")
        d.set_metric("seed", run.seed)
        d.set_metric("hero", run.character_id)
        d.set_metric("blessings", sum(run.player.blessings.values()))
        d.set_metric("run time", f"{run.stats['time']:6.1f}s")
        if ps.dps.armed:                         # only while a dummy is up
            d.set_metric("dummy dps", ps.dps.summary())
            d.set_metric("dummy by", ps.dps.breakdown_line())
        d.set_metric("enemies", len(run.enemies))
        d.set_metric("boss", "yes" if run.boss else "no")
        d.set_metric("projectiles", len(run.projectiles))
        d.set_metric("hostiles", len(run.hostiles))
        d.set_metric("summons", len(run.summons))
        d.set_metric("hazards", len(run.hazards))
        d.set_metric("melee hitboxes", len(run.melee_hitboxes))
        d.set_metric("gems", len(run.gems))
        d.set_metric("particles", len(run.particles))
        el = run.elements
        d.set_metric("auras", f"{el.active_auras(run.enemies, run.stats['time'])} live "
                              f"{el.stats.applications} applied "
                              f"{el.stats.corpse_hits} on corpses")
        d.set_metric("reactions", f"{el.stats.reactions_this_frame}/frame "
                                  f"{el.stats.reactions_total} total "
                                  f"{el.pending} held")
        # CMB-009.2: the two §9.8 counters the metrics lacked.
        d.set_metric("thunder jumps", f"{el.stats.jump_nodes_this_frame}/frame "
                                      f"{el.stats.jump_nodes_total} total")
        d.set_metric("wind areas", f"{len(run.wind_areas)}/"
                                   f"{el.registry.global_cfg.max_active_wind_areas}")
        vis = run.element_visuals
        if vis is not None:
            d.set_metric("element fx", f"{vis.report()}  "
                                       f"{len(run.element_fx)} transient")
        d.set_metric("level", run.levels.level)
        d.set_metric("kills", run.stats["kills"])
        m = ps.spawn.master
        loc = m.locality
        d.set_metric("zone", f"cur {loc.current} head {loc.heading} grace {loc.grace_room}"
                             + ("  ALL" if m.all_active else "")
                             + ("  FROZEN" if m.frozen else ""))
        d.set_metric("population",
                     f"live {len(run.enemies)} dormant {m.population.total_dormant} "
                     f"cap {ps.director.enemy_count_cap(run.stats['time'])}/{m.world_cap} "
                     f"debt {m.debt} recycled {m.recycled}")
        d.set_metric("companies", f"{m.companies} seated, {m.gate_waits} cap waits, "
                                  f"{m.pending} in flight")
        if ps._nav is not None:
            d.set_metric("nav", f"on {ps._nav_last_ms:4.1f}ms  x{ps._nav_rebuilds}")
        elif config.ENEMY_PATHFINDING:
            d.set_metric("nav", "on (no layout)")
