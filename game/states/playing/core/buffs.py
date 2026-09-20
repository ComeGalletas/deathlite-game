"""The buff buildings' timed buffs (journal: buff_buildings_journal.md).

`BuffSystem` owns `{kind: seconds_left}` for the hero. A buff starts when
the interact key fires a building (`SpecialLocations.use` hands the
interactable here), applies its stat changes as `Modifier`s under one
source name, and takes them back when the timer runs out. Everything a buff
does that is not a stat -- Magnet's pull, Turbo's weight and contact bites,
Haste's summon cadence, Pinball's throws, Vampire's heal -- is a small hook
the owning system calls with the buff's numbers read from
`data/world/buildings.json`.

The three activation feedbacks live here too, as state the renderer and the
HUD read: `tint` (the screen-wide gradient flash), `hero_fx` (the effect
strip over the hero) and `banners` (the flying name).

Reads from `PlayingState`: `player`, `content`, `gems`, `grid`, `stats`,
`enemies`, `boss`, `damage_numbers`, `game_map`, `dev_mode`. Writes the
hero's modifiers and weight, and `stats["damage_dealt"]` for Turbo's bites.
"""
from __future__ import annotations

import math

import pygame

from game import config
from game.events import Events
from progression.stats import FLAT, Modifier
from systems.collision import circles_overlap
from ui.buff_banner import BuffBanners


def _source(kind: str) -> str:
    return f"buff:{kind}"


class BuffSystem:
    def __init__(self, ps) -> None:
        self.ps = ps
        data = ps.content.buildings
        self.defs: dict[str, dict] = data.get("buffs", {})
        self.feedback: dict = data.get("feedback", {})
        self.active: dict[str, float] = {}
        # Turbo: id(enemy) -> seconds until it may take the next bite.
        self._contact_cd: dict[int, float] = {}
        self._pinball_t = 0.0
        # Feedback state. `tint` is `[seconds_left, palette]`; `hero_fx` a
        # list of `[rig, age]`; `banners` the flying names.
        self.tint: list | None = None
        self.hero_fx: list[list] = []
        self.banners = BuffBanners(float(self.feedback.get("banner_seconds", 7.0)))

    # --- queries ------------------------------------------------
    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(self.defs)

    def is_buff(self, kind: str) -> bool:
        return kind in self.defs

    def is_active(self, kind: str) -> bool:
        return kind in self.active

    def spec(self, kind: str) -> dict:
        return self.defs[kind]

    def palette(self, kind: str) -> list:
        return [tuple(int(c) for c in col) for col in self.defs[kind]["palette"]]

    def attack_speed_mult(self) -> float:
        """What the summons pace their attacks by: Haste's add, or 1."""
        if "haste" in self.active:
            return 1.0 + float(self.defs["haste"].get("attack_speed_add", 1.0))
        return 1.0

    def rows(self) -> list[tuple[str, float, str, tuple]]:
        """`(kind, fraction_left, icon_rig, colour)` per active buff, in
        activation order -- what the HUD row draws."""
        out = []
        for kind, left in self.active.items():
            spec = self.defs[kind]
            out.append((kind, max(0.0, min(1.0, left / float(spec["duration"]))),
                        spec.get("icon_rig", ""), self.palette(kind)[0]))
        return out

    # --- activation ---------------------------------------------
    def activate(self, it) -> None:
        """The interact key on a building: one use, then the buff."""
        it.used = True
        self.start(it.kind)
        self._mark_used(it)
        ps = self.ps
        ps.particles.burst(ps.player.pos, self.palette(it.kind)[0], count=22,
                           speed=170, life=0.6)

    def start(self, kind: str) -> None:
        """Grant `kind` for its full duration. A buff already running is
        refreshed to the full duration, never stacked."""
        spec = self.defs[kind]
        if kind not in self.active:
            self._apply(kind, spec)
        self.active[kind] = float(spec["duration"])
        palette = self.palette(kind)
        self.tint = [float(self.feedback.get("tint_seconds", 0.9)), palette]
        self.hero_fx.append([spec.get("fx_rig", ""), 0.0])
        self.banners.add(str(spec.get("name", kind.title())), palette[0])

    def _apply(self, kind: str, spec: dict) -> None:
        ps = self.ps
        player = ps.player
        src = _source(kind)
        mods = []
        if "speed_add" in spec:
            mods.append(Modifier("move_speed", FLAT, float(spec["speed_add"]), src))
        if "armor_add" in spec:
            mods.append(Modifier("armor", FLAT, float(spec["armor_add"]), src))
        if "attack_speed_add" in spec:
            mods.append(Modifier("attack_speed_multiplier", FLAT,
                                 float(spec["attack_speed_add"]), src))
        if "damage_add" in spec:
            mods.append(Modifier("damage_multiplier", FLAT, float(spec["damage_add"]), src))
        if mods:
            player.add_modifiers(*mods)
        if kind == "turbo":
            # Maximum weight: every bump lands wholly on the other body. The
            # boss is `inf` too, and two immovables shove neither.
            player.weight = math.inf
            self._contact_cd.clear()
        elif kind == "magnet":
            for gem in ps.gems:
                if gem.active:
                    gem.homing = True
        elif kind == "pinball":
            self._pinball_t = 0.0          # the first ball flies with the next attack

    def _expire(self, kind: str) -> None:
        player = self.ps.player
        player.remove_modifier_source(_source(kind))
        if kind == "turbo":
            player.weight = float(config.PLAYER_WEIGHT)
            self._contact_cd.clear()

    def _mark_used(self, it) -> None:
        """Swap the building's skin for its `used_rig` where the kind has
        one (the mine's door goes dark); every other kind keeps its art."""
        rig = self.defs[it.kind].get("used_rig")
        if not rig:
            return
        gm = self.ps.game_map
        for i, o in enumerate(getattr(gm, "obstacles", ())):
            if o.kind == it.kind and (o.pos - it.pos).length_squared() <= 1.0:
                from world.terrain.decor.obstacle_skins import reskin_obstacle
                reskin_obstacle(gm, self.ps.game.assets, i, rig)
                return

    # --- per frame ----------------------------------------------
    def update(self, dt: float) -> None:
        for kind in list(self.active):
            self.active[kind] -= dt
            if self.active[kind] <= 0.0:
                del self.active[kind]
                self._expire(kind)
        if "turbo" in self.active:
            self._turbo_contact(dt)
        if "pinball" in self.active:
            self._pinball(dt)
        if self.tint is not None:
            self.tint[0] -= dt
            if self.tint[0] <= 0.0:
                self.tint = None
        seconds = float(self.feedback.get("hero_fx_seconds", 2.0))
        for fx in self.hero_fx:
            fx[1] += dt
        self.hero_fx = [fx for fx in self.hero_fx if fx[1] < seconds]
        self.banners.update(dt)

    # --- hooks the other systems call ---------------------------
    def on_gem(self, gem) -> None:
        """A gem just dropped: Magnet pulls it in at once."""
        if "magnet" in self.active:
            gem.homing = True

    def on_weapon_hit(self, proj, enemy) -> None:
        """A hero projectile hit an enemy: Vampire heals per hit, summons'
        shots excluded."""
        if "vampire" not in self.active:
            return
        w = self.ps.player.weapon_by_id(proj.weapon_id) if proj.weapon_id else None
        if w is not None and w.is_summon:
            return
        self.ps.player.heal(float(self.defs["vampire"].get("heal_per_hit", 1.0)))

    # --- Turbo: contact bites -----------------------------------
    def _turbo_contact(self, dt: float) -> None:
        ps = self.ps
        spec = self.defs["turbo"]
        tick = max(0.05, float(spec.get("contact_tick", 0.5)))
        amount = float(spec.get("contact_dps", 5.0)) * tick
        for key in list(self._contact_cd):
            self._contact_cd[key] -= dt
            if self._contact_cd[key] <= 0.0:
                del self._contact_cd[key]
        p = ps.player
        if not p.alive:
            return
        no_dmg = ps.dev_mode and getattr(ps, "_dev_no_damage", False)
        for e in ps.grid.query_circle(p.pos.x, p.pos.y, p.radius + 48):
            if not e.alive or id(e) in self._contact_cd:
                continue
            if not circles_overlap(p.pos.x, p.pos.y, p.radius, e.pos.x, e.pos.y, e.radius):
                continue
            self._contact_cd[id(e)] = tick
            if no_dmg:
                continue
            dealt = e.take_damage(amount, source="turbo")
            if not e.alive:
                e.killed_by = "turbo"
            ps.stats["damage_dealt"] += dealt
            ps.damage_numbers.add(e.pos, dealt)
            ps.game.events.publish(Events.DAMAGE_DEALT, amount=dealt)

    # --- Pinball: the throws ------------------------------------
    def _pinball(self, dt: float) -> None:
        ps = self.ps
        spec = self.defs["pinball"].get("pinball", {})
        self._pinball_t -= dt
        if self._pinball_t > 0.0:
            return
        if ps.player._attack_t <= 0.0:
            return                          # "when attacking": no swing, no ball
        direction = self._aim_dir()
        speed = float(spec.get("speed", 260.0))
        dmg = float(spec.get("damage", 40.0)) * float(ps.player.stats["damage_multiplier"])
        ps._spawn_projectile(
            pos=pygame.Vector2(ps.player.pos), vel=direction * speed, damage=dmg,
            radius=float(spec.get("radius", 10.0)), lifetime=float(spec.get("lifetime", 10.0)),
            pierce=999, src_weight=float(spec.get("weight", 400.0)),
            color=self.palette("pinball")[0], style="pinball", weapon_id="pinball",
            rehit_interval=float(spec.get("rehit", 0.5)),
            bounces=int(spec.get("bounces", 10)))
        self._pinball_t = float(spec.get("every", 2.0))

    def _aim_dir(self) -> pygame.Vector2:
        ps = self.ps
        aim = getattr(ps, "_aim", None)
        if aim is not None and getattr(aim, "active", False):
            d = pygame.Vector2(aim.direction)
            if d.length_squared() > 1e-6:
                return d.normalize()
        best, best_d = None, 0.0
        for e in ps._targetables():
            if not e.alive:
                continue
            d = (e.pos - ps.player.pos).length_squared()
            if best is None or d < best_d:
                best, best_d = e, d
        if best is not None and best_d > 1e-6:
            return (best.pos - ps.player.pos).normalize()
        d = pygame.Vector2(ps._last_move_dir)
        return d.normalize() if d.length_squared() > 1e-6 else pygame.Vector2(1, 0)
