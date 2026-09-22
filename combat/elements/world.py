"""The four things an element needs from the running game.

Elements are stateless rules; they must not reach into `PlayingState`, and
they must stay testable without a world. So everything outward-facing goes
through one small adapter:

    deal(target, amount, weapon_id, effect)  -- damage, credited both ways
    nearest(pos, count, radius, exclude)     -- the spatial query (§9.2)
    knock(target, direction, strength, ...)  -- the existing CB-3 impulse
    add_area(area)                           -- a Wind area, or False at the cap

`RunWorld` is the real one. `NullWorld` records instead of acting, which is
what the unit tests drive the elements with.

`deal` is the important one. Elemental damage lands through the same
`take_damage` every other path uses, so the run ledger, the DPS meter, the
training dummy's invulnerability and `stats["damage_dealt"]` all see it --
the smoke test pins the ledger's total against that stat, and a path that
skipped it would show up as a hole rather than as a silent divergence.
"""
from __future__ import annotations

import pygame


# How long an elemental damage number stays up, against the 0.6 s a
# weapon's own number gets. Longer because these arrive in a stream -- a
# burn tick, a chain node, a shockwave -- and a stream of 0.6 s numbers
# reads as flicker rather than as damage.
#
# Not longer than this: `MAX_DAMAGE_NUMBERS` is 200 and a saturated pool
# drops whatever asks next, which could be the *weapon's* number. Measured
# against the stress harness before settling (journal, M11 E1).
ELEMENT_NUMBER_SECONDS = 0.9

# A reaction's name, which is a word and has to be read rather than
# glanced at, so it outlasts even an elemental number. It sits higher than
# the numbers too: the same body is usually taking the reaction's damage
# in the same frame, and the two would otherwise overlap.
LABEL_SECONDS = 1.1
LABEL_LIFT = 16.0


class NullWorld:
    """Records what was asked of it; acts only on the target itself. The
    unit tests' world."""

    def __init__(self, targets=(), tracking=None) -> None:
        self.targets = list(targets)
        self.tracking = tracking
        self.dealt: list[tuple] = []
        self.knocks: list[tuple] = []
        self.areas: list = []
        self.arcs: list = []
        self.flashes: list = []
        self.labels: list = []
        self.area_cap = 99

    def deal(self, target, amount: float, weapon_id: str, effect: str) -> float:
        if amount <= 0.0 or not getattr(target, "alive", False):
            return 0.0
        self.dealt.append((target, amount, weapon_id, effect))
        dealt = target.take_damage(amount, source=weapon_id, effect=effect)
        if self.tracking is not None:
            self.tracking.record_damage(dealt, weapon_id, effect)
        return dealt

    def nearest(self, pos, count: int, radius: float, exclude=()) -> list:
        if count <= 0 or radius <= 0.0:
            return []
        r2 = radius * radius
        near = [e for e in self.targets
                if getattr(e, "alive", False) and id(e) not in exclude
                and (e.pos - pos).length_squared() <= r2]
        near.sort(key=lambda e: (e.pos - pos).length_squared())
        return near[:count]

    def knock(self, target, direction, strength: float, *, weapon_id: str = "",
              max_speed: float = 0.0) -> None:
        self.knocks.append((target, strength, weapon_id))
        push = getattr(target, "apply_knockback", None)
        if push is not None:
            push(direction, strength)
        # Mirrors `RunWorld.knock`, so the speed clamp is testable
        # without building a run.
        if max_speed > 0.0:
            knock = getattr(target, "_knock", None)
            if knock is not None and knock.length_squared() > max_speed ** 2:
                knock.scale_to_length(max_speed)

    def add_area(self, area) -> bool:
        if len(self.areas) >= self.area_cap:
            return False
        self.areas.append(area)
        return True

    def add_arc(self, start, end, element, until: float) -> None:
        self.arcs.append((start, end, element, until))

    def add_flash(self, pos, reaction, radius: float, started: float) -> None:
        self.flashes.append((pos, reaction, radius, started))

    def add_label(self, pos, reaction) -> None:
        self.labels.append((pos, reaction))


class RunWorld:
    """The real adapter, over a `Run`."""

    def __init__(self, run) -> None:
        self.run = run
        self.tracking = getattr(run.ledger, "elements", None)

    def effect_colour(self, effect: str):
        """The colour a piece of elemental damage should be written in, or
        None where the run has no visuals (the headless tests).

        A reaction takes the **mix of its two elements**, which is what a
        reaction's colour is (owner, M12) and what `blend_colours` already
        builds for its flash -- so the number, the burst and M11's label
        cannot disagree about what an Overload looks like.
        """
        from combat.elements import tracking
        from combat.elements.config import REACTION_PAIRS
        from combat.elements.ids import ElementId
        from game.states.playing.visual.elements.transient import mix

        visuals = getattr(self.run, "element_visuals", None)
        source = tracking.source_of(effect)
        if visuals is None or source is None:
            return None
        if isinstance(source, ElementId):
            return visuals.tint(source)
        first, second = (visuals.tint(e) for e in REACTION_PAIRS[source])
        return mix(first, second, 0.5)

    # --- damage ---------------------------------------------------------
    def deal(self, target, amount: float, weapon_id: str, effect: str) -> float:
        """One piece of elemental damage, through the ordinary funnel.

        Mirrors what `CombatResolver.projectile_hits` does around its own
        `take_damage`: the run's damage total, a floating number, and
        `killed_by` so an on-kill blessing knows what finished the enemy.
        """
        if amount <= 0.0 or not getattr(target, "alive", False):
            return 0.0
        run = self.run
        dealt = target.take_damage(amount, source=weapon_id, effect=effect)
        if not target.alive:
            # The *effect* is what killed it, not the weapon: "died to an
            # Overload" is the readable answer, and the weapon is still on
            # every damage record.
            target.killed_by = effect or weapon_id
        run.stats["damage_dealt"] += dealt
        # `low_priority`: a burning crowd can ask for more numbers than the
        # pool holds, and the weapon's own number is the one that must not
        # be the casualty.
        run.damage_numbers.add(target.pos, dealt, False,
                               colour=self.effect_colour(effect),
                               life=ELEMENT_NUMBER_SECONDS,
                               low_priority=True)
        if self.tracking is not None:
            self.tracking.record_damage(dealt, weapon_id, effect)
        return dealt

    # --- queries ---------------------------------------------------------
    def nearest(self, pos, count: int, radius: float, exclude=()) -> list:
        """The `count` closest living targets within `radius`, nearest
        first. The boss is a candidate like any other body."""
        run = self.run
        out = run.grid.nearest(pos.x, pos.y, count, radius, exclude=exclude)
        boss = run.boss
        if boss is not None and boss.alive and id(boss) not in exclude:
            if (boss.pos - pos).length_squared() <= radius * radius:
                out = sorted(out + [boss],
                             key=lambda e: (e.pos - pos).length_squared())[:count]
        return out

    # --- impulses ---------------------------------------------------------
    def knock(self, target, direction, strength: float, *, weapon_id: str = "",
              max_speed: float = 0.0) -> None:
        """Push `target` away along `direction`, through the same
        `apply_knockback` a weapon hit uses, so weight and the decay curve
        behave identically. `max_speed` clamps the accumulated impulse, which
        is what keeps stacked shockwaves from flinging bodies off the map.
        """
        push = getattr(target, "apply_knockback", None)
        if push is None or strength <= 0.0:
            return
        push(direction, strength)
        state = getattr(target, "elemental", None)
        if state is not None and weapon_id:
            # Who to credit if this body is frozen and slides into another.
            state.knock_source = weapon_id
        if max_speed > 0.0:
            knock = getattr(target, "_knock", None)
            if knock is not None and knock.length_squared() > max_speed * max_speed:
                knock.scale_to_length(max_speed)

    # --- wind areas ---------------------------------------------------------
    def add_area(self, area) -> bool:
        """Seat a Wind area, unless the run is already at its cap."""
        run = self.run
        cap = run.elements.registry.global_cfg.max_active_wind_areas
        if len(run.wind_areas) >= cap:
            return False
        run.wind_areas.append(area)
        return True

    def add_arc(self, start, end, element, until: float) -> None:
        """One Thunder jump, drawn as a kinked bolt (design §8.6)."""
        from game.states.playing.visual.elements import Arc, transient
        transient.add(self.run, Arc(start, end, element, until))

    def add_flash(self, pos, reaction, radius: float, started: float) -> None:
        """A reaction going off: its authored burst, or the blend of its two
        elements where none is wired (§8.5, M10 rule 2).

        How long it lasts is looked up here rather than passed in, because
        it is presentation tuning and lives in `element_visuals.json` with
        the rest of it."""
        from game.states.playing.visual.elements import Flash, transient
        visuals = getattr(self.run, "element_visuals", None)
        burst = (visuals.profiles.reaction(getattr(reaction, "key", ""))
                 if visuals is not None else None)
        seconds = burst.seconds if burst is not None else transient.FLASH_SECONDS
        transient.add(self.run, Flash(pos, reaction, radius, started, seconds))

    def add_label(self, pos, reaction) -> None:
        """The reaction's name, out of the body it fired on (M11 C).

        The text is `tracking.label`, which the run summary already uses,
        so the two can never disagree about what a reaction is called. The
        two colours are the pair's own, in `REACTION_PAIRS` order unless
        `element_visuals.json` names a different one for that reaction --
        Frostburn does, reading blue inside and red outside.
        """
        from combat.elements import tracking
        from combat.elements.config import REACTION_PAIRS

        numbers = getattr(self.run, "damage_numbers", None)
        visuals = getattr(self.run, "element_visuals", None)
        if numbers is None or visuals is None:
            return
        burst = visuals.profiles.reaction(reaction.key)
        pair = REACTION_PAIRS[reaction]
        fill, ring = burst.label_pair(pair) if burst is not None else pair
        numbers.add_label(pos, tracking.label(reaction.key),
                          visuals.tint(fill), visuals.tint(ring),
                          life=LABEL_SECONDS, lift=LABEL_LIFT)


def direction_from(origin, target) -> pygame.Vector2:
    """A unit vector from `origin` to `target`'s position, or a fixed one
    when they are coincident (so a knockback never comes out as zero)."""
    delta = pygame.Vector2(target.pos) - pygame.Vector2(origin)
    if delta.length_squared() < 1e-6:
        return pygame.Vector2(1.0, 0.0)
    return delta.normalize()
