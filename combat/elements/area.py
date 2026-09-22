"""The Wind area: a brief tornado that follows the enemy it formed on
(design §4.4).

A reusable component with a swappable **payload**, because the three Wind
reactions are the same area with something extra on contact (FireWind leaves
a burn, IceWind adds slow stacks, ThunderWind strikes). Only the payload and
the numbers differ, so only the payload and the numbers are parameters.

Three rules keep it cheap with a dozen of these alive at once:

* contact is checked at a low fixed rate (`CHECK_HZ`), not every frame;
* each body is contacted **once** per area instance, tracked by id;
* the area is bounded by `max_targets` as well as by its radius.

The enemy the area formed on is excluded from its own area, so it takes the
Wind hit but not the area damage and is not knocked away from itself.
"""
from __future__ import annotations

import pygame

from combat.elements.world import direction_from

CHECK_HZ = 10.0
_CHECK_INTERVAL = 1.0 / CHECK_HZ


class WindArea:
    __slots__ = ("pos", "radius", "expires_at", "next_check_at", "anchor",
                 "damage", "knockback", "weapon_id", "effect", "max_targets",
                 "taken", "hit_ids", "payload", "max_speed", "allows")

    def __init__(self, *, pos, radius: float, expires_at: float, damage: float,
                 knockback: float, weapon_id: str, effect: str,
                 max_targets: int, anchor=None, payload=None,
                 max_speed: float = 0.0, allows=None) -> None:
        self.pos = pygame.Vector2(pos)
        self.radius = float(radius)
        self.expires_at = float(expires_at)
        # Checked on the frame it spawns, then at CHECK_HZ.
        self.next_check_at = 0.0
        self.anchor = anchor
        self.damage = float(damage)
        self.knockback = float(knockback)
        self.weapon_id = weapon_id
        self.effect = effect
        self.max_targets = int(max_targets)
        self.taken = 0
        # The enemy it formed on never contacts its own area.
        self.hit_ids: set[int] = {id(anchor)} if anchor is not None else set()
        # `payload(target, area, world, now, damage)` -- what a Wind
        # *reaction* adds. `now` is the live clock; `damage` is this
        # area's own figure, which is the value a spread aura carries
        # forward (owner, 2026-09-22). The figure rather than what the
        # body actually lost, so a shield soaking the hit does not also
        # strip the aura it leaves behind.
        self.payload = payload
        self.max_speed = float(max_speed)
        # `allows(target, effect)` -- the contacted body's own profile,
        # which the area outlives its context to keep asking.
        self.allows = allows

    @property
    def alive(self) -> bool:
        return self.taken < self.max_targets

    def remaining(self, now: float) -> float:
        return max(0.0, self.expires_at - now)

    def update(self, now: float, world) -> bool:
        """Advance one frame. Returns whether the area is still going."""
        if now >= self.expires_at:
            return False
        if self.anchor is not None and getattr(self.anchor, "alive", False):
            self.pos.update(self.anchor.pos)          # it follows its enemy
        if now < self.next_check_at:
            return True
        self.next_check_at = now + _CHECK_INTERVAL
        self.contact(world, now)
        return True

    def contact(self, world, now: float = 0.0) -> int:
        """One sweep: damage, knock back and pay the payload on every body
        inside that this area has not already taken.

        `now` is the **live** clock, not the reaction's. A payload that
        spreads an aura (the owner's 2026-09-22 rework) resolves it through
        the resolver, which times auras and locks against the run clock, and
        an area outlives the context it was built from by up to its whole
        duration -- so passing the stale time would set auras that expired
        before they were written."""
        room = self.max_targets - self.taken
        if room <= 0:
            return 0
        hit = 0
        for target in world.nearest(self.pos, room, self.radius,
                                    exclude=self.hit_ids):
            self.hit_ids.add(id(target))
            self.taken += 1
            hit += 1
            world.deal(target, self.damage, self.weapon_id, self.effect)
            if not getattr(target, "alive", False):
                continue                     # died to the area: nothing more
            if self.knockback > 0.0 and (self.allows is None
                                         or self.allows(target, "knockback")):
                world.knock(target, direction_from(self.pos, target),
                            self.knockback, weapon_id=self.weapon_id,
                            max_speed=self.max_speed)
            if self.payload is not None:
                self.payload(target, self, world, now, self.damage)
        return hit


def update_all(areas: list, now: float, world) -> list:
    """Advance every live area and drop the spent ones. Returns the list to
    keep, so the caller can rebind it the way the run's other transient
    lists are swept."""
    return [a for a in areas if a.update(now, world)]
