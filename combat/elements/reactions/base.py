"""What every reaction is, and the two rules none of them may break.

**Secondary hits never apply auras** (design §5.3). A reaction damages and
statuses the enemies it reaches, and that is all, so nothing it touches can
start another reaction. This is enforced by construction rather than by a
flag: a reaction calls `ctx.deal` and writes statuses directly, and never
re-enters `ElementalResolver.apply`. That is also what keeps **reaction
depth at exactly 1** (§5.4).

**Nothing is written to a dead carrier** (the death rule, 2026-09-21). A
reaction still fires when the hit that triggered it killed the enemy -- the
blast is owed to the enemies around it -- but any status it would have put
on the carrier is skipped. Damage needs no check: the world refuses damage
to a dead target, so the carrier's share is dropped automatically.
"""
from __future__ import annotations

from combat.elements.ids import ReactionId
from combat.elements.world import direction_from


class Reaction:
    """Base class. Subclasses set `ID` and implement `run`."""
    ID: ReactionId

    @property
    def key(self) -> str:
        return self.ID.key

    def run(self, target, config, ctx) -> None:
        """Fire on `target`, which is the enemy whose aura was consumed.
        `config` is the baked variant for the element that triggered it."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Reaction {self.key}>"


def status_on(target, ctx) -> object | None:
    """The target's status list, or None when nothing may be written to it
    -- because it has none, or because the hit that triggered the reaction
    killed it."""
    if ctx.carrier_dead:
        return None
    return getattr(target, "status", None)


def blast(target, ctx, *, effect: str, damage: float,
          knockback: float, radius: float, max_targets: int,
          max_speed: float = 0.0, payload=None) -> int:
    """A radial hit on the enemies around `target`: damage, then a shove
    away from the centre. Returns how many it reached.

    The carrier itself is never in its own blast -- it has already taken the
    reaction's direct damage -- and nothing here leaves an aura.
    """
    if radius <= 0.0 or max_targets <= 0:
        return 0
    world = ctx.world
    reached = 0
    for other in world.nearest(target.pos, max_targets, radius,
                               exclude={id(target)}):
        reached += 1
        ctx.deal(other, damage, effect)
        if not getattr(other, "alive", False):
            continue
        if knockback > 0.0 and ctx.allows_on(other, "knockback"):
            world.knock(other, direction_from(target.pos, other), knockback,
                        weapon_id=ctx.weapon_id, max_speed=max_speed)
        if payload is not None:
            payload(other)
    return reached
