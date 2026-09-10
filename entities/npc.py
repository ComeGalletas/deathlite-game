"""Village NPCs (HI-3): pawns, the smith, the lancers and the sheep.

An `Npc` is scenery that moves. It has no health, no collider anyone else
tests against and no effect on the run beyond a lancer's lance: the hero
and the enemies walk through it, it never blocks a shot. What it has is a
rig, an `Animator`, a home and a small state machine -- stand for a while,
pick a spot near home the terrain accepts, walk there in a straight line
sliding round whatever is in the way, stand again. A lancer's home
alternates between the two guard posts it patrols; a sheep's is the pen,
and its "walk" is the bounce.

A kind with `aggro` in its tuning fights (the lancers): an enemy inside its
aggro radius is charged, thrust at while its edge is within the lance's
reach, and followed no further than `chase` from the post it left. The foe
dying or getting away sends the lancer back to that post, and the ordinary
patrol resumes from there. Hits reach the world through the `on_hit`
callback the manager hands in; this module never touches an enemy itself.

Tuning per kind is `data/npcs.json`; this module keeps only the machine.
"""
from __future__ import annotations

import math
import random

import pygame

from systems.animation import Animator

IDLE, WALK, WORK = "idle", "walk", "work"
CHASE, ATTACK, RETURN = "chase", "attack", "return"

# A walk that gets nowhere for this long is abandoned: the NPC is wedged
# against a building the straight line cannot slide round.
_STUCK_S = 0.8
_ARRIVE_PX = 4.0
# A chased foe is given up once it is this many aggro radii away, or once
# a chase has spent this long without getting any nearer to it (the lancer
# is sliding round a building corner or hopping off a wedge, not closing).
_LOSE_FACTOR = 1.3
_NOPROG_S = 1.0
# The attack strips, by the direction of the thrust (mirrored for west).
_ATTACK_ANIMS = ("attack_up", "attack_up_right", "attack_right",
                 "attack_down_right", "attack_down")


class Npc:
    __slots__ = ("kind", "rig", "pos", "home", "posts", "post", "leash",
                 "speed", "radius", "anim", "state", "timer", "target",
                 "facing", "work_chance", "_stuck", "_last",
                 "aggro", "chase", "charge", "reach", "damage", "hit_frame",
                 "cooldown", "foe", "_struck", "_cool", "_best", "_noprog")

    def __init__(self, kind: str, rig: str, x: float, y: float, spec: dict,
                 assets, *, leash_px: float, posts=None,
                 aggro_px: float = 0.0, chase_px: float = 0.0) -> None:
        self.kind = kind
        self.rig = rig
        self.pos = pygame.Vector2(x, y)
        self.home = pygame.Vector2(x, y)
        # A patrol: the spots a lancer walks between. Empty for the rest.
        self.posts = [pygame.Vector2(p) for p in (posts or ())]
        self.post = 0
        self.leash = leash_px
        self.speed = float(spec["speed"])
        self.radius = float(spec["radius"])
        self.work_chance = float(spec.get("work", 0.0))
        # The fight, for a kind that has one (`aggro` in its tuning).
        self.aggro = float(aggro_px)
        self.chase = float(chase_px)
        self.charge = float(spec.get("charge", spec["speed"]))
        self.reach = float(spec.get("reach", 0.0))
        self.damage = float(spec.get("damage", 0.0))
        self.hit_frame = int(spec.get("hit_frame", 0))
        self.cooldown = float(spec.get("cooldown", 0.0))
        self.foe = None
        self._struck = False
        self._cool = 0.0
        self._best = 0.0
        self._noprog = 0.0
        self.anim = Animator(assets, rig, start=IDLE) if assets.rig(rig) else None
        self.state = IDLE
        self.timer = 0.0
        self.target = pygame.Vector2(x, y)
        self.facing = 1
        self._stuck = 0.0
        self._last = pygame.Vector2(x, y)

    # --- the machine --------------------------------------------------
    def update(self, dt: float, rng: random.Random, world, idle_range,
               foes=None, on_hit=None) -> None:
        """`foes(x, y, r)` lists the live enemies near a point and
        `on_hit(npc, foe)` lands a blow; both only matter to a kind with
        an aggro radius and may be left out for the rest."""
        if self.anim is not None:
            self.anim.update(dt)
        if self.aggro > 0.0 and foes is not None:
            if self.state in (IDLE, WALK, RETURN):
                foe = self._spot(foes)
                if foe is not None:
                    self._engage(foe)
            if self.state == CHASE:
                self._chase(dt, world)
                return
            if self.state == ATTACK:
                self._strike(dt, on_hit)
                return
        if self.state == WORK:
            if self.anim is None or self.anim.finished:
                self._rest(rng, idle_range)
            return
        if self.state == IDLE:
            self.timer -= dt
            if self.timer <= 0.0:
                self._choose(rng, world)
            return
        # WALK, and RETURN (the walk back to the post after a fight)
        if self._step_toward(self.target, self.speed, dt, world):
            self.pos.update(self.target)
            self._arrive(rng, idle_range)
        elif self._stuck >= _STUCK_S:
            self._arrive(rng, idle_range)

    def _step_toward(self, goal, speed: float, dt: float, world) -> bool:
        """One frame of straight-line walking toward `goal`, sliding round
        obstacles. True when within arriving distance; `_stuck` climbs
        while the walk gets nowhere."""
        to = goal - self.pos
        dist = to.length()
        if dist <= _ARRIVE_PX:
            return True
        step = to * (min(dist, speed * dt) / dist)
        new = self.pos + step
        moved = world.resolve_movement(self.pos, new, self.radius)
        if abs(step.x) > 1e-3:
            self.facing = 1 if step.x > 0 else -1
        if (moved - self.pos).length_squared() < 0.25 * step.length_squared():
            self._stuck += dt
        else:
            self._stuck = 0.0
        self.pos.update(moved)
        return False

    def _rest(self, rng, idle_range) -> None:
        self.state = IDLE
        self.timer = rng.uniform(*idle_range)
        if self.anim is not None:
            self.anim.play(IDLE)

    def _arrive(self, rng, idle_range) -> None:
        self._stuck = 0.0
        if self.work_chance and rng.random() < self.work_chance and self.anim is not None:
            self.state = WORK
            self.anim.play(WORK, restart=True)
            return
        self._rest(rng, idle_range)

    def _choose(self, rng, world) -> None:
        """A spot to walk to: the next post on a patrol, otherwise a point
        within the leash of home that the terrain accepts. Nothing found
        in a few tries means stand a little longer."""
        if self.posts:
            self.post = (self.post + 1) % len(self.posts)
            self.target = pygame.Vector2(self.posts[self.post])
        else:
            for _ in range(6):
                ang = rng.uniform(0.0, 6.283185307)
                d = rng.uniform(0.3, 1.0) * self.leash
                cand = self.home + pygame.Vector2(d, 0).rotate_rad(ang)
                if world.is_walkable(cand, self.radius):
                    self.target = cand
                    break
            else:
                self.timer = 0.6
                return
        self.state = WALK
        self._stuck = 0.0
        if self.anim is not None:
            self.anim.play(WALK)

    # --- the fight ----------------------------------------------------
    def base(self) -> pygame.Vector2:
        """Where the fight is measured from and returned to: the post the
        patrol is on, or home for a lancer with none."""
        return self.posts[self.post] if self.posts else self.home

    def _spot(self, foes):
        """The nearest live enemy inside the aggro radius that a chase
        would still be allowed to reach, or `None`."""
        best, best_d = None, self.aggro
        base = self.base()
        for e in foes(self.pos.x, self.pos.y, self.aggro):
            if not getattr(e, "alive", False):
                continue
            d = e.pos.distance_to(self.pos)
            if d < best_d and e.pos.distance_to(base) <= self.chase:
                best, best_d = e, d
        return best

    def _engage(self, foe) -> None:
        self.foe = foe
        self.state = CHASE
        self._stuck = 0.0
        self._cool = 0.0
        self._best = foe.pos.distance_to(self.pos)
        self._noprog = 0.0
        if self.anim is not None:
            self.anim.play(WALK)

    def _disengage(self) -> None:
        """Back to the post; the patrol picks up from there on arrival."""
        self.foe = None
        self.state = RETURN
        self.target = pygame.Vector2(self.base())
        self._stuck = 0.0
        if self.anim is not None:
            self.anim.play(WALK)

    def _in_reach(self, foe) -> bool:
        return foe.pos.distance_to(self.pos) - foe.radius <= self.reach

    def _chase(self, dt: float, world) -> None:
        foe = self.foe
        self._cool = max(0.0, self._cool - dt)
        if (foe is None or not foe.alive
                or foe.pos.distance_to(self.pos) > self.aggro * _LOSE_FACTOR
                or self.pos.distance_to(self.base()) > self.chase):
            self._disengage()
            return
        if self._in_reach(foe):
            if foe.pos.x != self.pos.x:
                self.facing = 1 if foe.pos.x > self.pos.x else -1
            if self._cool <= 0.0:
                self._begin_strike(foe)
            elif self.anim is not None:
                self.anim.play(IDLE)        # squared up, between thrusts
            return
        if self.anim is not None:
            self.anim.play(WALK)
        self._step_toward(foe.pos, self.charge, dt, world)
        d = foe.pos.distance_to(self.pos)
        if d < self._best - 1.0:
            self._best, self._noprog = d, 0.0
        else:
            self._noprog += dt
        if self._stuck >= _STUCK_S or self._noprog >= _NOPROG_S:
            self._disengage()

    def _begin_strike(self, foe) -> None:
        self.state = ATTACK
        self._struck = False
        if self.anim is None:
            return
        d = foe.pos - self.pos
        # Which strip: the thrust's angle above the horizontal, west
        # mirrored by the draw.
        ang = math.degrees(math.atan2(-d.y, abs(d.x)))
        name = _ATTACK_ANIMS[min(4, int((90.0 - ang + 22.5) // 45.0))]
        assets = self.anim.assets
        if assets.frame_count(self.rig, name) <= 0:
            name = "attack_right"
        if assets.frame_count(self.rig, name) <= 0:
            self.anim = None            # no strip at all: the blow still lands
            return
        self.anim.play(name, restart=True)

    def _strike(self, dt: float, on_hit) -> None:
        foe = self.foe
        if self.anim is None or self.anim.index >= self.hit_frame:
            if not self._struck:
                self._struck = True
                if (on_hit is not None and foe is not None and foe.alive
                        and foe.pos.distance_to(self.pos) - foe.radius
                        <= self.reach * _LOSE_FACTOR):
                    on_hit(self, foe)
        if self.anim is None or self.anim.finished:
            self._cool = self.cooldown
            self.state = CHASE          # re-read the foe next frame


class SheepNpc(Npc):
    """A sheep stirs: a short hop within its own leash of where it stands,
    clamped to the pen's interior rectangle so it never bounces into the
    fence. Slight movement, not a wander."""
    __slots__ = ("pen",)

    def __init__(self, rig, x, y, spec, assets, pen: pygame.Rect, leash_px: float) -> None:
        super().__init__("sheep", rig, x, y, spec, assets, leash_px=leash_px)
        self.pen = pen

    def _choose(self, rng, world) -> None:
        pad = self.radius + 4
        if self.pen.width <= 2 * pad or self.pen.height <= 2 * pad:
            self.timer = 1.0
            return
        ang = rng.uniform(0.0, 6.283185307)
        d = rng.uniform(0.3, 1.0) * self.leash
        cand = self.home + pygame.Vector2(d, 0).rotate_rad(ang)
        self.target = pygame.Vector2(
            min(max(cand.x, self.pen.left + pad), self.pen.right - pad),
            min(max(cand.y, self.pen.top + pad), self.pen.bottom - pad))
        self.state = WALK
        self._stuck = 0.0
        if self.anim is not None:
            self.anim.play(WALK)
