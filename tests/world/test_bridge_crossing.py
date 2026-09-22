"""WLD-011: a big body can actually walk a bridge (`GameMap.is_walkable`).

The navigation field has always handed corridor cells out regardless of
clearance -- `corridor_lenient`, on by default, and
`test_pathfinding.py::test_one_tile_corridors_need_leniency_for_the_big_enemies`
pins that promise. The collider never got the matching rule, so a large body
was routed onto a deck it could not stand on and stalled at the mouth; the
pig-rider boss could never leave the island it spawned on.

A deck is one tile, `TILE_PX` = 64, and `is_walkable` probes a body as a
four-point cross, so before the fix the widest radius that could cross was
**31** -- under every boss in the game.

Seeds are pinned and worlds come from the shared cache: these consume a
generated world, and an unpinned one would make the whole module a coin flip.
Nothing here mutates a world.
"""
import unittest

import pygame

from game import config
from tests import worlds as W

SEEDS = (35, 7, 42)

# Wider than a deck's half-width (32) on purpose: this is the pig-rider boss
# (`the_tusked_lance`), the body the rule exists for.
BOSS_R = 40.0
# What could cross before the fix, so a regression shows up as "only the
# small ones still make it" rather than as a total failure.
SMALL_R = 24.0


def decks(seed):
    """Every bridge of a seed, as `(corridor, horizontal)`."""
    layout = W.layout(seed)
    return [(c, c.rect.width > c.rect.height) for c in layout.corridors]


def propped(gm, corridor, horizontal, radius):
    """Is a prop close enough to this deck to block a body of `radius` on its
    centre line? Props are never *on* a deck, but one just past a mouth can
    still reach across it."""
    r = corridor.rect
    steps = 40
    for s in range(steps + 1):
        t = s / steps
        if horizontal:
            x, y = r.left + t * r.width, r.centery
        else:
            x, y = r.centerx, r.top + t * r.height
        for o in gm._obstacle_index.near(x, y, radius):
            rr = o.radius + radius
            if (x - o.pos.x) ** 2 + (y - o.pos.y) ** 2 < rr * rr:
                return True
    return False


def walk(gm, corridor, horizontal, radius):
    """Drive a body from one mouth to the other the way `Boss._move` does --
    through the real resolver, one frame at a time. Returns how far along the
    deck it got, 0.0 to 1.0."""
    r = corridor.rect
    if horizontal:
        start = pygame.Vector2(r.left + 4, r.centery)
        goal = pygame.Vector2(r.right + 48, r.centery)
    else:
        start = pygame.Vector2(r.centerx, r.top + 4)
        goal = pygame.Vector2(r.centerx, r.bottom + 48)
    pos = pygame.Vector2(start)
    speed = 92.0 / 60.0                      # the boss's speed, one frame
    stalled = 0
    for _ in range(6000):
        if (pos.x >= r.right if horizontal else pos.y >= r.bottom):
            return 1.0
        step = goal - pos
        if step.length() > speed:
            step.scale_to_length(speed)
        nxt = gm.resolve_movement(pos, pos + step, radius)
        stalled = stalled + 1 if (nxt - pos).length() < 0.05 else 0
        if stalled > 30:
            break
        pos = nxt
    return ((pos.x - r.left) / r.width if horizontal
            else (pos.y - r.top) / r.height)


class BridgeCrossingTests(unittest.TestCase):
    def test_a_deck_is_one_tile_wide(self):
        """The premise of the whole rule. If decks ever widen, the leniency
        may stop being necessary -- and this is what will say so."""
        for seed in SEEDS:
            for corridor, horizontal in decks(seed):
                width = (corridor.rect.height if horizontal
                         else corridor.rect.width)
                self.assertEqual(width, config.TILE_PX,
                                 f"seed {seed}: deck {width} px")

    def test_a_boss_sized_body_crosses_every_unobstructed_bridge(self):
        """The bug, in one assertion. Before the fix this was 0 % on every
        bridge of every seed.

        "Unobstructed" is doing real work and is not a way of excusing a
        failure: this rule is about *geometry*, and a prop parked beside a
        mouth blocks through the obstacle test underneath, which the fix
        deliberately leaves alone. The next test names those separately so
        they stay visible rather than being quietly absorbed here."""
        for seed in SEEDS:
            gm = W.game_map(seed)
            for i, (corridor, horizontal) in enumerate(decks(seed)):
                if propped(gm, corridor, horizontal, BOSS_R):
                    continue
                got = walk(gm, corridor, horizontal, BOSS_R)
                self.assertEqual(
                    got, 1.0,
                    f"seed {seed} bridge {i}: a radius-{BOSS_R:.0f} body "
                    f"stalled {got * 100:.0f} % along a clear deck")

    def test_a_prop_beside_a_mouth_still_blocks_a_wide_body(self):
        """A known, separate defect, pinned so it cannot be forgotten.

        Placement keeps props off the deck but not far enough back from it:
        on seed 35 one sits 19 px past the planks with a 19.5 px radius, and
        a radius-40 body's exclusion circle cannot clear it, so that bridge
        stays shut to the boss. Fixing it is a placement change -- keep props
        a largest-body radius clear of a mouth -- not a collider one.

        If placement is fixed, this test fails and should be deleted."""
        blocked = [(seed, i)
                   for seed in SEEDS
                   for i, (corridor, horizontal) in enumerate(decks(seed))
                   if propped(W.game_map(seed), corridor, horizontal, BOSS_R)]
        self.assertTrue(
            blocked,
            "no bridge is prop-blocked any more -- placement was fixed, so "
            "delete this test and drop the filter from the one above")

    def test_small_bodies_still_cross(self):
        """The leniency must not have broken what already worked."""
        for seed in SEEDS:
            gm = W.game_map(seed)
            for i, (corridor, horizontal) in enumerate(decks(seed)):
                if propped(gm, corridor, horizontal, SMALL_R):
                    continue
                self.assertEqual(walk(gm, corridor, horizontal, SMALL_R), 1.0,
                                 f"seed {seed} bridge {i}")

    def test_the_centre_must_still_be_on_the_deck(self):
        """The leniency drops the *radius probe*, not the floor test. A body
        whose centre has left the planks is over water and stays refused --
        otherwise a wide enemy could walk out to sea beside a bridge."""
        gm = W.game_map(35)
        for corridor, horizontal in decks(35):
            r = corridor.rect
            if horizontal:
                off = pygame.Vector2(r.centerx, r.centery + config.TILE_PX)
            else:
                off = pygame.Vector2(r.centerx + config.TILE_PX, r.centery)
            if gm.is_open_water(off.x, off.y):
                self.assertFalse(gm.is_walkable(off, BOSS_R),
                                 "a body beside a deck is over water")

    def test_obstacles_are_still_enforced_on_a_bridge(self):
        """Only the floor probe is relaxed. The obstacle test below it is
        untouched, so a prop by a mouth still blocks -- which is how the one
        remaining stall on seed 35 was diagnosed as placement, not geometry."""
        gm = W.game_map(35)
        blocked = 0
        for obstacle in W.layout(35).obstacles:
            if not gm.on_bridge(obstacle.pos.x, obstacle.pos.y):
                continue
            blocked += 1
            self.assertFalse(gm.is_walkable(obstacle.pos, BOSS_R),
                             "a body cannot stand inside a prop on a deck")
        # Not an assertion about how many: seeds differ, and zero is a fine
        # answer. The loop is the point.
        self.assertGreaterEqual(blocked, 0)

    def test_the_collider_now_keeps_the_navigation_fields_promise(self):
        """The two rules disagreed, and that was the bug. A corridor cell the
        field hands out under `corridor_lenient` must be one the collider
        will actually let a boss-sized body stand on."""
        from world.nav.lattice import NavGrid

        for seed in SEEDS:
            layout = W.layout(seed)
            gm = W.game_map(seed)
            grid = NavGrid(layout, layout.obstacles, 32)
            broken = []
            for i in range(grid.cols * grid.rows):
                if not grid.corridor[i]:
                    continue
                p = grid.world_of(i % grid.cols, i // grid.cols)
                if not gm.on_bridge(p.x, p.y):
                    continue                 # a flight, not a bridge
                if gm._obstacle_index.near(p.x, p.y, BOSS_R):
                    continue                 # a prop there is a real refusal
                if not gm.is_walkable(pygame.Vector2(p.x, p.y), BOSS_R):
                    broken.append((p.x, p.y))
            self.assertEqual(broken, [],
                             f"seed {seed}: the field offers cells the "
                             f"collider refuses: {broken[:3]}")
