"""HI-3: the villagers (`entities/npc.py`, `game/states/playing/npcs.py`).

Driven through a real headless run so the NPCs are built from the same
`Village` records and step against the same map the game uses. One run per
class, shared, since a boot costs a few seconds.
"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.enemy import Enemy
from entities.npc import ATTACK, CHASE, IDLE, RETURN, WALK, WORK, SheepNpc
from game import config
from game.content import get_content
from game.game import Game
from game.states.menu_state import MenuState
from game.states.playing_state import PlayingState


def fresh_playing():
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    for _ in range(2):
        game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    from tests.boot import settle
    p = settle(game)
    assert isinstance(p, PlayingState)
    return game, p


class VillagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game, cls.p = fresh_playing()
        cls.lay = cls.p.game_map.layout

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _by_kind(self, kind):
        return [n for n in self.p.npcs if n.kind == kind]

    def test_every_village_has_a_smith_pawns_guards_and_sheep_where_it_has_a_pen(self):
        p, lay = self.p, self.lay
        self.assertTrue(lay.villages)
        self.assertGreaterEqual(len(self._by_kind("smith")), 1)
        self.assertGreaterEqual(len(self._by_kind("pawn")), 1)
        self.assertGreaterEqual(len(self._by_kind("lancer")), 1)
        if any(v.pen is not None for v in lay.villages):
            self.assertGreaterEqual(len(self._by_kind("sheep")), 1)
        for n in p.npcs:
            room = p.game_map.room_at(n.pos)
            self.assertIsNotNone(room, f"{n.kind} stands in the sea")
            self.assertEqual(room.kind, "village", f"{n.kind} is off the village")

    def test_the_smith_stands_by_the_forge_and_the_guards_by_their_posts(self):
        px = config.TILE_PX
        forges = [v.forge for v in self.lay.villages]
        for n in self._by_kind("smith"):
            self.assertLessEqual(min(f.distance_to(n.home) for f in forges), 2.5 * px)
        posts = [pygame.Vector2(pt) for v in self.lay.villages for pair in v.posts for pt in pair]
        for n in self._by_kind("lancer"):
            near = posts or forges   # no military row anywhere: they muster at the forge
            self.assertLessEqual(min(pt.distance_to(n.home) for pt in near), 3 * px)

    def test_each_village_keeps_a_garrison_of_four_or_five(self):
        lo, hi = get_content().npcs["placement"]["lancers"]
        self.assertEqual((lo, hi), (4, 5))
        forges = [v.forge for v in self.lay.villages]
        per = [0] * len(forges)
        for n in self._by_kind("lancer"):
            per[min(range(len(forges)), key=lambda i: forges[i].distance_to(n.home))] += 1
        for k, count in enumerate(per):
            self.assertTrue(lo <= count <= hi, f"village {k} has {count} lancers")

    def _lancer_with_room(self):
        """A lancer and a spot 70 px east of its post the terrain accepts,
        so a foe can stand there."""
        p = self.p
        for n in self._by_kind("lancer"):
            base = n.base()
            for ang in range(0, 360, 45):
                spot = base + pygame.Vector2(70, 0).rotate(ang)
                # The foe's spot fits a tank and the lancer's straight charge
                # to it is clear the whole way (a clipped building corner
                # would send the charge sliding instead).
                if p.game_map.is_walkable(spot, 24) and all(
                        p.game_map.is_walkable(base.lerp(spot, k / 14), n.radius + 2)
                        for k in range(15)):
                    return n, spot
        self.fail("no lancer has open ground beside its post")

    def _fight(self, n, foe, seconds):
        """Tick the villagers with `foe` in the world until it is hurt or
        `seconds` pass. Returns the states seen on every lancer that took
        the foe on, and those lancers: a post is shared by two or more
        (all of them, on a village with no military row), so a neighbour
        may well get there first."""
        p = self.p
        p.camera.snap_to(n.base())
        seen, fighters = set(), []
        for _ in range(int(60 * seconds)):
            p.grid.rebuild(p.enemies)
            p.npc_manager.update(1 / 60)
            for l in self._by_kind("lancer"):
                if l.foe is foe:
                    seen.add(l.state)
                    if l not in fighters:
                        fighters.append(l)
            if foe.hp < foe.max_hp:
                break
        return seen, fighters

    def test_a_lancer_charges_a_close_enemy_strikes_and_walks_back(self):
        p = self.p
        n, spot = self._lancer_with_room()
        n.pos.update(n.base()); n.state = IDLE; n.timer = 0.2; n.foe = None
        foe = Enemy("tank", get_content().enemy("tank"), spot.x, spot.y)
        p.enemies.append(foe)
        try:
            seen, fighters = self._fight(n, foe, 6)
            self.assertIn(n, fighters, "the lancer by the foe never took it on")
            self.assertIn(CHASE, seen, "no lancer charged")
            self.assertIn(ATTACK, seen, "no lancer thrust")
            self.assertLess(foe.hp, foe.max_hp, "the thrust did no damage")
            striking = [l for l in fighters if l.state == ATTACK]
            self.assertTrue(striking, "the blow landed with nobody mid-thrust")
            for l in striking:
                self.assertLessEqual(l.pos.distance_to(foe.pos) - foe.radius, l.reach * 1.3 + 4)
            # The foe falls; the lancers walk back to their post and patrol on.
            foe.alive = False
            p.enemies.remove(foe)
            p.grid.rebuild(p.enemies)
            seen = set()
            for _ in range(60 * 12):
                p.npc_manager.update(1 / 60)
                seen.update(l.state for l in fighters)
                if all(l.state == IDLE for l in fighters):
                    break
            self.assertIn(RETURN, seen)
            for l in fighters:
                self.assertEqual(l.state, IDLE)
                self.assertIsNone(l.foe)
                self.assertLessEqual(l.pos.distance_to(l.base()), 1.5 * config.TILE_PX)
        finally:
            if foe in p.enemies:
                p.enemies.remove(foe)
            p.grid.rebuild(p.enemies)

    def test_a_lancer_ignores_an_enemy_beyond_its_aggro_radius(self):
        p = self.p
        n, spot = self._lancer_with_room()
        n.pos.update(n.base()); n.state = IDLE; n.timer = 0.2; n.foe = None
        # Beyond the aggro radius of this lancer, and of every other one:
        # another post may stand between here and there.
        lancers = self._by_kind("lancer")
        for ang in range(0, 360, 30):
            far = n.base() + pygame.Vector2(n.aggro + 3 * config.TILE_PX, 0).rotate(ang)
            if all(far.distance_to(l.pos) > l.aggro * 1.5 for l in lancers):
                break
        else:
            self.skipTest("no spot clear of every lancer's aggro radius")
        foe = Enemy("tank", get_content().enemy("tank"), far.x, far.y)
        p.enemies.append(foe)
        try:
            seen, fighters = self._fight(n, foe, 3)
            self.assertFalse(fighters, f"a lancer left its post: {seen}")
            self.assertEqual(foe.hp, foe.max_hp)
        finally:
            p.enemies.remove(foe)
            p.grid.rebuild(p.enemies)

    def test_colours_are_mixed_not_one_per_village(self):
        """Never a colour band: with four colours cycling, four villagers of
        one kind show at least two colours."""
        for kind in ("pawn", "lancer"):
            rigs = [n.rig for n in self._by_kind(kind)]
            if len(rigs) >= 4:
                self.assertGreater(len(set(rigs)), 1, f"{kind}s all wear {rigs[0]}")
        spec = get_content().npcs
        for n in self.p.npcs:
            self.assertIn(n.rig, self.p.game.assets.meta, f"{n.kind} rig {n.rig} is not declared")

    def test_villagers_walk_and_stay_on_their_leash(self):
        p = self.p
        v = self.lay.villages[0]
        p.player.pos.update(v.forge.x + 120, v.forge.y + 90)
        p.camera.snap_to(v.forge)
        start = {id(n): n.pos.copy() for n in p.npcs}
        px = config.TILE_PX
        for _ in range(60 * 10):
            p.npc_manager.update(1 / 60)
            for n in p.npcs:
                if isinstance(n, SheepNpc):
                    self.assertTrue(n.pen.collidepoint(n.pos.x, n.pos.y),
                                    "a sheep left the pen")
                elif not n.posts:
                    self.assertLessEqual(n.home.distance_to(n.pos), n.leash + 2 * px,
                                         f"{n.kind} strayed off its leash")
                self.assertTrue(p.game_map.is_walkable(n.pos, 0.0) or
                                p.game_map.room_at(n.pos) is not None,
                                f"{n.kind} stepped off the floor")
        near = [n for n in p.npcs if v.forge.distance_to(n.pos) < 20 * px]
        moved = [n for n in near if (n.pos - start[id(n)]).length() > 8]
        self.assertGreater(len(moved), 0, "nobody in the village moved in ten seconds")
        self.assertTrue({n.state for n in p.npcs} <= {IDLE, WALK, WORK})

    def test_villagers_do_not_block_the_hero(self):
        """Walking straight through a villager moves the hero as if nobody
        were there. Picked where the map itself is open on both sides, so
        a building beside the villager (the smith stands at the forge) is
        not what the test measures."""
        p = self.p
        r = p.player.radius
        for n in p.npcs:
            start = pygame.Vector2(n.pos.x - 20, n.pos.y)
            target = pygame.Vector2(n.pos.x + 20, n.pos.y)
            if not (p.game_map.is_walkable(start, r) and p.game_map.is_walkable(target, r)):
                continue
            p.player.pos.update(start)
            got = p.game_map.resolve_movement(p.player.pos, target, r)
            self.assertEqual(got, target)
            return
        self.skipTest("no villager standing in the open on this seed")

    def test_villagers_are_seeded_by_the_world(self):
        """The same seed builds the same people in the same places."""
        p = self.p
        before = [(n.kind, n.rig, round(n.home.x), round(n.home.y)) for n in p.npcs]
        p.npc_manager.build()
        after = [(n.kind, n.rig, round(n.home.x), round(n.home.y)) for n in p.npcs]
        self.assertEqual(before, after)

    def test_villagers_are_drawn_with_the_characters(self):
        p = self.p
        v = self.lay.villages[0]
        p.camera.snap_to(v.forge)
        items = p._actor_items()
        # the hero plus at least one villager in view
        self.assertGreater(len(items), 1)
        surface = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        p.draw(surface)                   # draws without raising


if __name__ == "__main__":
    unittest.main()
