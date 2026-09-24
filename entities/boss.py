"""The boss (spec 3.7).

It cycles authored attack patterns, each with a visible telegraph before the
dangerous frames -- on the shared AI machine since ENT-015: the cycle is the
`boss_patterns` behaviour (`entities/ai/behaviors/boss.py`) and each pattern a
registered building block (`entities/ai/patterns.py`). Not "a big enemy with more HP":
it has three distinct patterns (radial bullet ring, telegraphed charge, brood
summon), a health bar (drawn by the HUD) and a currency reward on death.

Duck-types the bits of `Enemy` the combat loop needs: `pos`, `radius`, `alive`,
`hit_flash`, `is_elite`, `tags`, `take_damage`, `apply_knockback`,
`contact_damage`.
"""
from __future__ import annotations

import pygame

from combat.damage import apply_armor
from combat.elements.aura import ElementalState
from combat.status import StatusState
from entities.ai.behaviors.boss import enter
from entities.ai.blackboard import Blackboard
from entities.ai.components import SeekTarget
from entities.ai.machine import ATTACK_SLOT
from entities.ai.registry import build_behavior
from entities.ai.steering import Steering
from game import config
from game.assets import get_assets
from systems.animation import Animator

# `ctx` in this module is the PlayingState AI adapter (satisfies entities.ai
# Perception + Combat); duck-typed, so the methods take a bare `ctx`.


class Boss:
    stun_immune = True      # P1: the Hammer's stun never lands on a boss
    killed_by = ""          # P2: set by the resolver on the killing hit

    def __init__(self, boss_id: str, definition: dict, x: float, y: float) -> None:
        self.boss_id = boss_id
        self.cfg = definition
        self.name = definition.get("name", boss_id)
        self.max_hp = float(definition["hp"])
        self.hp = self.max_hp
        # The run's `RunLedger` (set by the spawner), as on `Enemy`.
        self.ledger = None
        self.speed = float(definition["speed"])
        self._base_contact = float(definition["contact_damage"])
        self.contact_damage = self._base_contact
        # Contact lands as a timed bite, like ordinary enemies (see Enemy).
        self.contact_interval = float(
            definition.get("contact_interval", config.INCOMING_TICK_INTERVAL))
        self.contact_cd = 0.0
        self.radius = float(definition["radius"])
        # How far the boss sees (world px). Beyond it the boss does nothing
        # but close in -- no telegraph, no pattern, the pattern clock held --
        # and picks its cycle back up the moment the player is inside again.
        # Sized in the data to cover the whole view, so a boss the player can
        # see is a boss that fights...
        self.vision_range = float(definition["vision_range"])
        self.closing = False
        # ...and it closes at this multiple of `speed`. A ground boss can start
        # that walk much further out than the flyer ever did -- its spawn ring
        # searches outward for land -- and a long patrol-speed approach is dead
        # time, not tension. The sprint ends the instant the hero is in sight,
        # so the fight itself is fought at `speed`.
        self.closing_speed = float(definition.get(
            "closing_speed_mult", config.BOSS_CLOSING_SPEED_MULT))
        self.xp_reward = int(definition.get("experience_reward", 200))
        self.reward_currency = int(definition.get("reward_currency", 50))
        self.color = tuple(definition.get("color", (180, 40, 70)))
        self.tags = tuple(definition.get("tags", ("boss",)))
        # `flying`: over the world rather than on it. The collider drops the
        # terrace margin, the elevation rule and every obstacle for it
        # (`GameMap.is_walkable(flying=True)`), and it seeks in a straight
        # line instead of following the flow field -- a field that rounds
        # walls and climbs stairs is routing for a body that has to walk.
        self.flying = "flying" in self.tags
        self.is_elite = True
        self.weight = float("inf")            # CB-3: immovable; only shoves others

        self.pos = pygame.Vector2(x, y)
        self.vel = pygame.Vector2()
        self.alive = True
        self.hit_flash = 0.0
        self.status = StatusState()
        self.elemental = ElementalState()
        self.recent_hits: dict[str, float] = {}   # P4 synergies
        self.hit_streak: dict[str, int] = {}
        # Duck-typed to satisfy the shared combat loop / draw code.
        self.shield_hp = 0.0
        self.explode_radius = 0.0

        # The attack cycle: intro -> telegraph -> active -> recover, pattern
        # by pattern, on the shared machine; its state lives on `bb`.
        self.bb = Blackboard()
        self._behavior = build_behavior(definition["behavior"], definition)
        self._cycles = "intro" in self._behavior.states
        if self._cycles:
            enter(self, definition["intro"])
        # Out of sight it closes in on the flow field (straight for a flyer).
        self._closer = SeekTarget(via="straight" if self.flying else "nav",
                                  slew=0.0, weight=1.0)

        # Sprite animation (same contract as Enemy: idle / walk / attack, no
        # hurt/death strip -> the renderer red-tints on hit + plays the shared
        # `dead` poof).
        rig = definition.get("sprite")
        self.anim = Animator(get_assets(), rig) if rig else None
        self._has_hurt = self.anim is not None and get_assets().frame_count(rig, "hurt") > 0
        self._hurt_t = 0.0
        self._facing = -1

    # --- combat --------------------------------------------------
    def _absorb(self, dealt: float, source,
                effect: str | None = None) -> float:
        """The one place damage lands on the boss (as `Enemy._absorb`): the
        run ledger hears it here, whichever path delivered it. The boss is
        never the metered target, so there is no `damage_sink`."""
        if self.ledger is not None:
            self.ledger.record(dealt, source, effect)
        self.hp -= dealt
        if self.hp <= 0:
            self.hp = 0.0
            self.alive = False
        return dealt

    def take_damage(self, amount: float, armor: float = 0.0, source=None,
                    effect: str | None = None) -> float:
        dealt = apply_armor(amount, armor)
        self.hit_flash = 0.06
        if self.anim is not None:
            self._hurt_t = 0.22
            if self._has_hurt:
                self.anim.play("hurt", restart=True)
        return self._absorb(dealt, source, effect)

    def apply_knockback(self, *_args) -> None:
        pass  # immovable

    @property
    def hp_fraction(self) -> float:
        return 0.0 if self.max_hp <= 0 else max(0.0, self.hp / self.max_hp)

    @property
    def telegraph_fraction(self) -> float:
        if self.phase != "telegraph" or self.phase_len <= 0:
            return 0.0
        return 1.0 - max(0.0, self.phase_t / self.phase_len)

    # --- the attack cycle (ENT-015: `behaviors/boss.py`) -----------
    # The cycle runs on the shared AI machine; these are views onto it, under
    # the names the renderer, the HUD and the tests have always read.
    @property
    def phase(self) -> str:
        return self._behavior.state_of(self)

    @phase.setter
    def phase(self, name: str) -> None:
        self._behavior.set_state(self, name)

    @property
    def pattern(self) -> dict:
        return self.bb.slot(ATTACK_SLOT).get("pattern") or {}

    @pattern.setter
    def pattern(self, p: dict) -> None:
        self.bb.slot(ATTACK_SLOT)["pattern"] = p

    @property
    def phase_t(self) -> float:
        """Seconds left in the current phase."""
        return self.bb.slot(ATTACK_SLOT).get("left", 0.0)

    @property
    def phase_len(self) -> float:
        return self.bb.slot(ATTACK_SLOT).get("len", 0.0)

    @property
    def telegraph_fraction(self) -> float:
        if self.phase != "telegraph" or self.phase_len <= 0:
            return 0.0
        return 1.0 - max(0.0, self.phase_t / self.phase_len)

    def _anim_name(self) -> str:
        if not self.alive:
            return "death"
        if self._hurt_t > 0.0 and self._has_hurt:
            return "hurt"
        if self.phase in ("telegraph", "active") and not self.closing:
            # A charge's active phase is the dash itself, not a swing: the
            # locomotion animation reads as speed, where a held attack pose
            # sliding across the ground reads as a bug. The telegraph still
            # plays `attack`, which is where the wind-up belongs.
            if self.phase == "active" and self.pattern.get("id") == "charge":
                return "walk"
            return "attack"                    # wind-up + the dangerous frames
        return "walk" if self.vel.length_squared() > 1.0 else "idle"

    def update(self, ctx) -> None:
        dt = ctx.dt
        self.contact_cd = max(0.0, self.contact_cd - dt)
        if self.hit_flash > 0.0:
            self.hit_flash = max(0.0, self.hit_flash - dt)
        self._hurt_t = max(0.0, self._hurt_t - dt)
        if self.anim is not None:
            fdx = ctx.player_pos.x - self.pos.x
            if fdx > 1.0:
                self._facing = 1
            elif fdx < -1.0:
                self._facing = -1
            self.anim.play(self._anim_name())
            self.anim.update(dt)
        self.status.update(
            dt, lambda amt, src, eff=None: self._status_damage(amt, ctx, src, eff))
        self.contact_damage = self._base_contact
        chill = self.status.speed_multiplier()

        # Out of sight: close in, and nothing else. The machine is not ticked,
        # so its clock holds where it is and a telegraph that was half done
        # resumes half done. A committed charge (`active`) runs its course
        # first -- it is the one phase that is already a dash at the player.
        # A boss with no pattern cycle only ever comes for the player.
        if self._cycles:
            far = (ctx.player_pos - self.pos).length_squared() > self.vision_range ** 2
            self.closing = far and self.phase != "active"
            if self.closing:
                acc = Steering()
                self._closer.tick(self, ctx, ctx, acc)
                self.vel = acc.resolve(self.speed * self.closing_speed)
                self.pos = self._move(ctx, self.vel * dt * chill)
                return

        self._behavior.tick(self, ctx, ctx)      # ctx satisfies Perception + Combat
        # Chill does not slow the committed charge dash.
        scale = (1.0 if self.pattern.get("id") == "charge" and self.phase == "active"
                 else chill)
        self.pos = self._move(ctx, self.vel * dt * scale)

    def _move(self, ctx, step: pygame.Vector2) -> pygame.Vector2:
        """One step through the collider, flying or not."""
        return ctx.resolve_movement(self.pos, self.pos + step, self.radius,
                                    flying=self.flying)

    def _status_damage(self, amount: float, ctx, source=None,
                       effect: str | None = None) -> None:
        # A damage-over-time tick; `source` is the weapon keeping it alive.
        if not self.alive:
            return
        self._absorb(amount, source, effect)
        ctx.report_damage(amount)
