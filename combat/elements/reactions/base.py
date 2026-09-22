"""What every reaction is, and the rules none of them may break.

**Secondary hits apply auras where the reaction says so** (owner's rework,
2026-09-22). This reverses design §5.3 and the reaction-depth-1 guarantee of
§5.4: the three Wind reactions prime everything their tornado touches, and
Superconduct primes everything its jump tree reaches, so a reaction *can*
start another one. It goes through `ElementalResolver.spread_aura`, which
documents what bounds the cascade -- the per-enemy aura lock and the
per-frame reaction budget -- and is the single seam a depth cap would sit
behind. Overload and Frostburn spread nothing and so remain terminal.

**The damage floor is the carrier's alone.** A reaction's figure is raised
to `global.reaction_min_damage` on the enemy whose aura it consumed, and the
bodies it spreads to take the raw figure. That is why the reactions here
call `ctx.floored(...)` exactly once, on their own target.

**Nothing is written to a dead carrier** (the death rule, 2026-09-21). A
reaction still fires when the hit that triggered it killed the enemy -- the
blast is owed to the enemies around it -- but any status it would have put
on the carrier is skipped. Damage needs no check: the world refuses damage
to a dead target, so the carrier's share is dropped automatically.
"""
from __future__ import annotations

from combat.elements.ids import ReactionId
from combat.elements.wind import Wind
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


def wind_reaction(target, config, ctx, *, effect: str, element, payload=None):
    """The whole shape the three Wind reactions share (owner's rework,
    2026-09-22): one two-source figure, paid to the carrier and carried by
    the tornado, and that tornado priming every body it touches with
    `element` on top of the reaction's own `payload`.

    Only the element and the extra payload differ between FireWind, IceWind
    and ThunderWind, so only those are parameters. Returns the seated area,
    or None when the run is at its Wind-area cap.

    The carrier is paid here rather than by the area: it is excluded from
    its own tornado (so it is neither shoved away from itself nor hit
    twice), and it is the one body the floor applies to.
    """
    amount = ctx.pair_damage(config.damage)
    ctx.deal(target, ctx.floored(amount), effect)

    def contact(other, _area, _world, now: float, damage: float) -> None:
        # The aura goes on **first**, and the reaction's own payload lands
        # over it. Both orders survive a cascade -- the payload is written
        # standalone, so a reaction the aura sets off cannot end it -- but
        # only this one keeps the payload's identity. Priming a body runs
        # the element's own `on_applied`, which for Fire is a burn and for
        # Ice a chill on the very rows FireWind and IceWind use; whoever
        # applies last owns the row's credit, its tick interval and whether
        # it is bound. Spreading first therefore leaves FireWind's burn
        # credited to FireWind and standalone, which is what the run
        # summary needs to tell it from Fire's own.
        ctx.resolver.spread_aura(other, element, weapon_id=ctx.weapon_id,
                                 hit_damage=damage, now=now)
        if payload is not None:
            payload(other, config, ctx)

    return Wind.spawn_area(target, ctx, config=config, effect=effect,
                           payload=contact, damage=amount)
