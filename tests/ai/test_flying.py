"""The `flying` tag: over the world rather than on it.

`The First Hunger` is a giant bat, and the brood it summons (`swarm`)
flies with it. Both cross a boulder, a cliff, a lake and the sea between
islands in a straight line instead of rounding one, taking the stairs to
the second, stopping dead at the third and sliding along the coast. The
edge of the world is the only wall.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.ai import build_behavior
from entities.boss import Boss
from entities.enemy import Enemy
from game.content import get_content
from tests import worlds as W
from tests.aictx import ai_ctx

SEED = W.SEEDS[0]


def _boss(flying=True):
    c = get_content()
    bid = next(iter(c.bosses))
    cfg = dict(c.boss(bid))
    if not flying:
        cfg["tags"] = tuple(t for t in cfg.get("tags", ()) if t != "flying")
    return Boss(bid, cfg, 0.0, 0.0)


def _mite_cfg(flying=True) -> dict:
    cfg = dict(get_content().enemy("swarm"))
    if not flying:
        cfg["tags"] = tuple(t for t in cfg.get("tags", ()) if t != "flying")
    return cfg


def _mite(flying=True):
    return Enemy("swarm", _mite_cfg(flying), 0.0, 0.0)


class TagTests(unittest.TestCase):
    def test_the_shipped_boss_flies(self):
        c = get_content()
        cfg = c.boss(next(iter(c.bosses)))
        self.assertIn("flying", cfg["tags"])
        self.assertEqual(cfg["sprite"], "giant_bat")     # the reason it flies
        self.assertTrue(_boss().flying)

    def test_the_tag_is_what_decides_it(self):
        self.assertFalse(_boss(flying=False).flying)

    def test_the_brood_flies_too(self):
        """The boss's `summon_brood` drops `swarm`; a walker dropped where
        the bat hovers over a cliff face is a walker in a wall."""
        c = get_content()
        boss = c.boss(next(iter(c.bosses)))
        brood = next(p for p in boss["patterns"] if p["id"] == "summon_brood")
        self.assertEqual(brood.get("summon_id", "swarm"), "swarm")
        self.assertIn("flying", c.enemy("swarm")["tags"])
        self.assertTrue(_mite().flying)
        self.assertFalse(_mite(flying=False).flying)


class ColliderTests(unittest.TestCase):
    """`GameMap.is_walkable(flying=True)`: inside the world, and nothing
    else."""

    def setUp(self):
        self.gm = W.game_map(SEED)

    def test_a_flyer_passes_over_an_obstacle_that_blocks_a_walker(self):
        blocked = 0
        for o in self.gm.obstacles:
            if self.gm.is_walkable(o.pos, 10.0):
                continue                      # not blocking there anyway
            blocked += 1
            self.assertTrue(self.gm.is_walkable(o.pos, 10.0, flying=True),
                            f"a flyer was stopped by a {o.kind}")
        self.assertGreater(blocked, 50, "no obstacle blocked a walker at all")

    def test_a_flyer_crosses_a_cliff_a_walker_may_not(self):
        """Pairs of neighbouring cells on different terraces: the elevation
        rule refuses the step, flying takes it."""
        px = 64
        refused = crossed = 0
        for room in self.gm.layout.rooms:
            for (col, row), cell in room.grid.items():
                if cell.kind != "ground":
                    continue
                here = pygame.Vector2(room.rect.left + (col + .5) * px,
                                      room.rect.top + (row + .5) * px)
                for dc, dr in ((1, 0), (0, 1)):
                    nb = room.grid.get((col + dc, row + dr))
                    if nb is None or nb.kind != "ground" or nb.level == cell.level:
                        continue
                    there = pygame.Vector2(here.x + dc * px, here.y + dr * px)
                    if self.gm.is_walkable(there, 0.0, frm=here):
                        continue
                    refused += 1
                    self.assertTrue(self.gm.is_walkable(there, 0.0, frm=here, flying=True))
                    crossed += 1
        self.assertGreater(refused, 5, "no terrace step was refused on this seed")
        self.assertEqual(refused, crossed)

    def test_a_flyer_crosses_its_own_islands_lake(self):
        """A lake is a cell of the island's height map. A body that walks is
        refused it; a bat that stops dead at a pond looks broken."""
        from world.layout import LAKE
        px = 64
        lakes = [(r, cell) for r in self.gm.layout.rooms
                 for cell, c in r.grid.items() if c.kind == LAKE]
        self.assertTrue(lakes, "no inland lake on this seed")
        for r, (col, row) in lakes:
            p = pygame.Vector2(r.rect.left + (col + .5) * px,
                               r.rect.top + (row + .5) * px)
            self.assertFalse(self.gm.is_walkable(p, 0.0))
            self.assertTrue(self.gm.is_walkable(p, 0.0, flying=True))

    def test_a_flyer_crosses_the_sea(self):
        """The water between islands is air to a flyer: a spot that is on no
        island and no bridge, refused to a walker, is taken."""
        b = self.gm.layout.bounds
        sea = [pygame.Vector2(b.left + 2, b.top + 2),
               pygame.Vector2(b.centerx, b.top + 2)]
        sea = [p for p in sea if self.gm.room_at(p) is None]
        self.assertTrue(sea, "no open sea at the world's top edge on this seed")
        for spot in sea:
            self.assertFalse(self.gm.is_walkable(spot, 0.0))
            self.assertTrue(self.gm.is_walkable(spot, 0.0, flying=True),
                            f"a flyer was held at the coast near {spot}")

    def test_the_flying_floor_is_the_world_rect(self):
        """Every point inside the world is flyable, whatever is under it; one
        pixel past any edge is not."""
        import random
        rng = random.Random(7)
        w, h = self.gm.width, self.gm.height
        for _ in range(400):
            p = pygame.Vector2(rng.uniform(0, w), rng.uniform(0, h))
            self.assertTrue(self.gm.is_walkable(p, 0.0, flying=True), p)
        for p in (pygame.Vector2(-1, h / 2), pygame.Vector2(w + 1, h / 2),
                  pygame.Vector2(w / 2, -1), pygame.Vector2(w / 2, h + 1),
                  pygame.Vector2(-500, -500)):
            self.assertFalse(self.gm.is_walkable(p, 0.0, flying=True), p)

    def test_resolve_movement_carries_the_flag_through_its_slides(self):
        """A step into a tree: refused for a walker (it slides or stays),
        taken whole for a flyer."""
        tree = next(o for o in self.gm.obstacles
                    if o.kind == "tree" and not self.gm.is_walkable(o.pos, 10.0))
        frm = pygame.Vector2(tree.pos.x - 40, tree.pos.y)
        if not self.gm.is_walkable(frm, 10.0):
            self.skipTest("no clear approach to that tree on this seed")
        walked = self.gm.resolve_movement(frm, pygame.Vector2(tree.pos), 10.0)
        flown = self.gm.resolve_movement(frm, pygame.Vector2(tree.pos), 10.0, flying=True)
        self.assertNotEqual(tuple(walked), tuple(tree.pos))
        self.assertEqual(tuple(flown), tuple(tree.pos))


class SeekTests(unittest.TestCase):
    def test_a_flyer_ignores_the_flow_field_and_beelines(self):
        """The field routes for a body that walks -- round the wall, up the
        stairs. A flyer takes the straight line."""
        from types import SimpleNamespace
        player = pygame.Vector2(300, 0)
        field = pygame.Vector2(0, 1)                    # the field says "go south"
        ctx = SimpleNamespace(player_pos=player, nav_dir=lambda p, r: pygame.Vector2(field))
        flyer, walker = _boss(), _boss(flying=False)
        self.assertAlmostEqual(flyer._seek(ctx).x, 1.0, places=3)   # straight at the player
        self.assertAlmostEqual(walker._seek(ctx).y, 1.0, places=3)  # follows the field


class BroodTests(unittest.TestCase):
    """The enemy side of the tag: the pursuit stack seeks straight with no
    obstacle avoidance, and the body moves through the flying collider."""

    @staticmethod
    def _stack(behavior: str, flying: bool) -> list:
        return build_behavior(behavior, _mite_cfg(flying)).states["move"]

    def test_a_flying_pursuit_stack_is_seek_straight_plus_separation(self):
        for behavior in ("path_chase", "swarm"):
            stack = self._stack(behavior, flying=True)
            self.assertEqual([type(c).__name__ for c in stack],
                             ["SeekTarget", "Separation"], behavior)
            self.assertEqual(stack[0].via, "straight", behavior)

    def test_a_walker_keeps_the_field_and_the_avoidance(self):
        stack = self._stack("path_chase", flying=False)
        self.assertEqual([type(c).__name__ for c in stack],
                         ["SeekTarget", "Separation", "AvoidObstacles", "Unstick"])
        self.assertEqual(stack[0].via, "nav")

    def test_a_flying_mite_moves_through_the_flying_collider(self):
        for flying in (True, False):
            seen = []

            def resolve(prev, new, r, **kw):
                seen.append(kw.get("flying", False))
                return new

            e = _mite(flying)
            e.update(ai_ctx(player=(400, 0), resolve_movement=resolve))
            self.assertEqual(seen, [flying])

    def test_a_flying_mite_heads_straight_at_the_player_across_the_field(self):
        field = pygame.Vector2(0, 1)                    # the field says "go south"
        ctx = ai_ctx(dt=0.5, player=(400, 0), nav_dir=lambda p, r: pygame.Vector2(field))
        flyer, walker = _mite(), _mite(flying=False)
        for e in (flyer, walker):
            e.bb.slot("aggro")["until"] = 99.0            # both are chasing
            e.update(ctx)
        self.assertGreater(flyer.pos.x, 0.0)
        self.assertAlmostEqual(flyer.pos.y, 0.0, places=3)
        self.assertGreater(walker.pos.y, 0.0)



class FlyerBandTests(unittest.TestCase):
    """A flyer is painted in the band of the terrain under it (`top_level_at`),
    a walker in the band of its floor (`level_at`). Over a cliff wall the two
    differ: the wall has no floor, so `level_at` says 0 and a bat drawn there
    would sink under the terrace's rim."""

    def setUp(self):
        self.gm = W.game_map(SEED)

    def test_over_a_cliff_wall_the_flyer_band_is_the_wall_top(self):
        from world.elevation import NONE
        ix = self.gm._levels
        px = 64
        walls = 0
        for room in self.gm.layout.rooms:
            for (col, row), cell in room.grid.items():
                if cell.kind != "cliff":
                    continue
                p = pygame.Vector2(room.rect.left + (col + .5) * px,
                                   room.rect.top + (row + .5) * px)
                if ix.level_at_point(p.x, p.y) != NONE:
                    continue
                walls += 1
                top = ix.top_at_point(p.x, p.y)
                self.assertGreater(top, 0)
                self.assertEqual(self.gm.renderer.level_at(p.x, p.y), 0)
                self.assertEqual(self.gm.renderer.top_level_at(p.x, p.y), top)
        self.assertGreater(walls, 5, "no cliff wall without a floor on this seed")

    def test_over_the_sea_both_bands_are_the_lowest(self):
        b = self.gm.layout.bounds
        p = pygame.Vector2(b.left + 2, b.top + 2)
        if self.gm.room_at(p) is not None:
            self.skipTest("no open sea at the world's corner on this seed")
        self.assertEqual(self.gm.renderer.level_at(p.x, p.y), 0)
        self.assertEqual(self.gm.renderer.top_level_at(p.x, p.y), 0)


class ShotsOverTheSeaTests(unittest.TestCase):
    """LD-9 D10 already lets a shot cross the void: `top_at_point` answers
    `NONE` over the sea, and a shot *fired* from over the sea carries `NONE`
    and is judged against nothing. So the bat's barrage from offshore, and
    the hero's answer from the beach, both land."""

    def setUp(self):
        self.gm = W.game_map(SEED)
        b = self.gm.layout.bounds
        self.sea = pygame.Vector2(b.left + 2, b.top + 2)
        if self.gm.room_at(self.sea) is not None:
            self.skipTest("no open sea at the world's corner on this seed")

    def _fx(self):
        from types import SimpleNamespace
        from game.states.playing.effects import TransientFx
        bursts = []
        ps = SimpleNamespace(game_map=self.gm,
                             particles=SimpleNamespace(burst=lambda *a, **k: bursts.append(a)))
        return TransientFx(ps), bursts

    def test_a_shot_from_the_beach_reaches_a_bat_over_the_sea(self):
        from entities.projectile import Projectile
        fx, bursts = self._fx()
        p = Projectile()
        p.reset(pos=pygame.Vector2(self.sea), vel=pygame.Vector2(), damage=1,
                radius=4, lifetime=1.0)
        p.active = True                          # the pool's job, done by hand
        p.fire_level = 2                         # fired from a high terrace
        fx.block_on_terrain(p)
        self.assertTrue(p.active)
        self.assertEqual(bursts, [])

    def test_a_barrage_fired_from_over_the_sea_is_never_blocked(self):
        from entities.projectile import Projectile
        from world.elevation import NONE
        fx, bursts = self._fx()
        p = Projectile()
        p.reset(pos=pygame.Vector2(self.sea), vel=pygame.Vector2(), damage=1,
                radius=4, lifetime=1.0)
        p.active = True                          # the pool's job, done by hand
        fx.stamp_fire_level(p)
        self.assertEqual(p.fire_level, NONE)
        # ...and later over the highest ground on the map
        ix = self.gm._levels
        high = max(((ix.top_at_point(r.rect.centerx, r.rect.centery), r)
                    for r in self.gm.layout.rooms), key=lambda t: t[0])[1]
        p.pos.update(high.rect.centerx, high.rect.centery)
        fx.block_on_terrain(p)
        self.assertTrue(p.active)
        self.assertEqual(bursts, [])


class BossSpawnPointTests(unittest.TestCase):
    """The boss appears `config.BOSS_SPAWN_DISTANCE` from the hero on a random
    side, clamped to the world; the boss room is not consulted."""

    def test_the_point_is_the_configured_distance_from_the_hero(self):
        import random
        from game import config
        from game.states.playing.spawning import boss_spawn_point
        hero = pygame.Vector2(3000, 3000)
        for seed in range(6):
            p = boss_spawn_point(hero, random.Random(seed), 6000, 6000)
            self.assertAlmostEqual((p - hero).length(), config.BOSS_SPAWN_DISTANCE, places=5)

    def test_the_point_is_clamped_inside_the_world(self):
        import random
        from game.states.playing.spawning import boss_spawn_point
        for hero in (pygame.Vector2(0, 0), pygame.Vector2(6000, 0),
                     pygame.Vector2(0, 6000), pygame.Vector2(6000, 6000)):
            for seed in range(8):
                p = boss_spawn_point(hero, random.Random(seed), 6000, 6000, distance=560)
                self.assertTrue(0 <= p.x <= 6000 and 0 <= p.y <= 6000, p)
                self.assertLessEqual((p - hero).length(), 560 + 1e-6)

    def test_the_spawner_asks_beside_the_hero_not_in_the_boss_room(self):
        import random
        from types import SimpleNamespace
        from game import config
        from game.states.playing.spawning import EnemyControl
        gm = W.game_map(SEED)
        start = gm.layout.room(gm.layout.start_id).center
        ps = SimpleNamespace(player=SimpleNamespace(pos=pygame.Vector2(start)),
                             rng=random.Random(1), game_map=gm)
        p = EnemyControl.boss_spawn_point(SimpleNamespace(ps=ps))
        boss_room = gm.layout.room(gm.layout.boss_id).center
        self.assertAlmostEqual((p - start).length(), config.BOSS_SPAWN_DISTANCE, places=3)
        self.assertGreater((p - boss_room).length(), config.BOSS_SPAWN_DISTANCE)


if __name__ == "__main__":
    unittest.main()
