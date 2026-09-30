"""RND-008.4: the elemental draw costs less and paints the same
(`frame_time_journal.md`).

Three changes, each pinned against the path it replaced:

* **Terraces sorted once a frame.** `elements.bands` sorts the bodies in
  view and the aura motes onto their terraces before the banded passes,
  where each pass used to test every body and mote against its own
  terrace. Pinned: each terrace's share is exactly, and in the same order,
  what its own pass would pick; a whole frame is pixel-identical with and
  without the sort; and, since RND-011 moved the aura's shed into the
  update, the world draw leaves the run's random streams and particle
  pool as it found them, sorted or not. The fight is seed 35's harness
  crowd, packed and primed, which stands on three terraces.
* **The burn flame scaled once** per frame and size, not every frame:
  the same pixels, kept per source surface, not served for another.
* **Plain damage numbers rendered once** per font, text and colour: the
  same pixels, alpha included, when several numbers share a glyph.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.states.playing.visual import elements as element_fx
from game.states.playing.visual.elements import layers, transient
from tools.benchmarks import spawn_stress as S
from ui.damage_numbers import DamageNumbers

SEED = 35


def _pixels(surface):
    return pygame.image.tobytes(surface, "RGBA")


class TerraceSortTests(unittest.TestCase):
    """One primed, packed fight, shared; nothing here moves it."""

    @classmethod
    def setUpClass(cls):
        cls.game, cls.ps = S.build(SEED, 100, 0, 300.0, config.ENEMY_LOD_SKIP)
        ps = cls.ps
        # The terrain animates on the wall clock unless handed one.
        ps.game_map.renderer.clock = lambda: 0.0
        S.infuse(ps, SEED)
        S.run(ps, 20)
        S.cascade_setup(ps)                     # every body primed, packed round the hero
        cls._add_the_edge_cases(ps)
        S.run(ps, 10, render=True)              # statuses, and the motes the auras shed
        cls.fight = ps.run
        cls.bands = element_fx.bands(ps.run)
        cls.levels = sorted(set(cls.bands.bodies) | set(cls.bands.motes))

    @classmethod
    def _add_the_edge_cases(cls, ps):
        """The packed crowd stands on two of the island's three terraces;
        three bodies go onto the third. The boss is placed in view (first
        in `_bodies` order) and a bumblebee hovers where the floor under it
        is not the top of the terrain: the actor pass bands a flyer by the
        top, the elemental passes by the floor, and the sort must follow
        the elemental passes."""
        from combat.elements.ids import ELEMENTS

        r = ps.game_map.renderer
        view = ps.camera.visible_rect().inflate(-80, -80)
        spots = [(x, y) for x in range(view.left, view.right, 16)
                 for y in range(view.top, view.bottom, 16)]
        now = ps.run.stats["time"]
        top = [s for s in spots if r.level_at(*s) == 2]
        for body, spot in zip(ps.run.enemies[:3], top):
            body.pos.update(spot)
        ps.spawn.spawn_boss()
        boss = ps.run.boss
        boss.pos.update(view.center)
        boss.elemental.set_aura(ELEMENTS[1], now, 600.0)
        cliff = next(s for s in spots if r.top_level_at(*s) != r.level_at(*s))
        bee = ps.spawn.master.spawn_at("bumblebee", pygame.Vector2(cliff), owner="test")
        bee.elemental.set_aura(ELEMENTS[2], now, 600.0)
        cls.edge = {"top": top[:3], "boss": boss, "bee": bee}

    def test_the_fight_covers_what_the_sort_must_get_right(self):
        # Without this the tests below could pass on a flat field, with no
        # boss and no flyer, where there is nothing to get wrong.
        r = self.ps.game_map.renderer
        self.assertEqual(len(self.edge["top"]), 3, "no room on the third terrace")
        self.assertEqual(sorted(self.bands.bodies), [0, 1, 2])
        boss, bee = self.edge["boss"], self.edge["bee"]
        self.assertTrue(bee.flying)
        self.assertNotEqual(r.top_level_at(bee.pos.x, bee.pos.y),
                            r.level_at(bee.pos.x, bee.pos.y))
        self.assertIn(bee, self.bands.bodies[r.level_at(bee.pos.x, bee.pos.y)])
        first = self.bands.bodies[r.level_at(boss.pos.x, boss.pos.y)][0]
        self.assertIs(first, boss)
        self.assertTrue(self.fight.particles.layer(True), "no aura motes to sort")

    def test_a_pass_picks_what_the_old_per_pass_filter_picked(self):
        # The oracle is the filter each pass ran before RND-008.4, written
        # out here: in view with a 140 px pad, on the pass's terrace. One
        # body is moved out of view so the view half has something to drop
        # (an aura off screen draws nothing; the shed, in the update since
        # RND-011, uses the same filter and sheds nothing for it either).
        fight = self.fight
        body = fight.enemies[0]
        home = body.pos.copy()
        view = fight.camera.visible_rect()
        body.pos.update(view.right + 400, view.centery)
        try:
            for level in [None, *self.levels]:
                with self.subTest(level=level):
                    pad = fight.camera.visible_rect().inflate(140, 140)
                    old = [b for b in layers._bodies(fight)
                           if pad.collidepoint(b.pos.x, b.pos.y)
                           and not transient.off_band(fight, level, b.pos)]
                    got = layers.in_band(fight, level)
                    self.assertEqual(got, old)
                    self.assertNotIn(body, got)
        finally:
            body.pos.update(home)

    def test_each_terrace_gets_the_bodies_its_own_pass_picks(self):
        for level in self.levels:
            with self.subTest(level=level):
                self.assertEqual(self.bands.bodies.get(level, []),
                                 layers.in_band(self.fight, level))

    def test_each_terrace_gets_the_motes_its_own_pass_picks(self):
        for level in self.levels:
            with self.subTest(level=level):
                picked = [p for p in self.fight.particles.layer(True)
                          if not transient.off_band(self.fight, level, p.pos)]
                self.assertEqual(self.bands.motes.get(level, []), picked)

    def test_the_world_draw_leaves_the_run_as_it_found_it(self):
        # Before RND-011 each drawn aura rolled `run.rng`, so the order the
        # sort visited bodies in was a gameplay fact. The draw rolls
        # nothing now, sorted or not: both streams and the pool hold still.
        fight = self.fight
        vis = fight.element_visuals
        for sorted_ in (True, False):
            with self.subTest(sorted=sorted_):
                real = element_fx.bands if sorted_ else (lambda run: None)
                rng, own = fight.rng.getstate(), vis.rng.getstate()
                motes = len(fight.particles)
                with mock.patch.object(element_fx, "bands", real):
                    element_fx.begin_frame(fight)
                    self.ps._draw_world(pygame.Surface(
                        (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)))
                self.assertGreater(vis.auras_drawn, 0, "no aura was drawn")
                self.assertEqual(fight.rng.getstate(), rng)
                self.assertEqual(vis.rng.getstate(), own)
                self.assertEqual(len(fight.particles), motes)

    def test_the_burn_mark_scales_its_flame_once(self):
        visuals = self.fight.element_visuals.profiles
        frame = visuals.status_frame("burn")
        self.assertIsNotNone(frame, "no burn art to scale")
        layers._SCALED.clear()
        zoom = self.ps.camera.zoom
        drawn = []
        with mock.patch.object(pygame.transform, "smoothscale",
                               wraps=pygame.transform.smoothscale) as m:
            for _ in range(2):
                s = pygame.Surface((300, 300), pygame.SRCALPHA)
                layers._burn_mark(s, visuals, 150, 200, zoom)
                drawn.append(_pixels(s))
        self.assertEqual(m.call_count, 1)
        want = pygame.Surface((300, 300), pygame.SRCALPHA)
        scaled = pygame.transform.smoothscale(
            frame, (max(4, int(frame.get_width() * 0.34 * zoom)),
                    max(6, int(frame.get_height() * 0.34 * zoom))))
        want.blit(scaled, scaled.get_rect(midbottom=(150, 200)))
        self.assertEqual(drawn, [_pixels(want)] * 2)

    def test_a_frame_sorts_its_bodies_once_not_once_per_terrace(self):
        # The saving itself: the passes take their share of the sort and
        # never filter the whole field again for their own terrace.
        with mock.patch.object(layers, "in_band", wraps=layers.in_band) as m:
            element_fx.begin_frame(self.fight)
            self.ps._draw_world(pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT)))
        self.assertEqual([c.args[1] for c in m.call_args_list], [None])

    def test_a_whole_frame_is_the_same_picture_with_and_without_the_sort(self):
        ps = self.ps

        def frame(sorted_):
            real = element_fx.bands if sorted_ else (lambda run: None)
            s = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
            # No stub needed since RND-011: the draw sheds nothing, so the
            # three frames differ only if the sort changes the picture.
            with mock.patch.object(element_fx, "bands", real):
                ps.draw(s)
            return _pixels(s)

        first = frame(True)
        self.assertEqual(frame(False), first)
        self.assertEqual(frame(True), first)        # and the frame is stable


class BurnFlameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))

    def setUp(self):
        layers._SCALED.clear()
        self.frame = pygame.Surface((40, 60), pygame.SRCALPHA)
        pygame.draw.polygon(self.frame, (255, 140, 40, 230), [(20, 0), (39, 59), (0, 59)])

    def test_the_kept_copy_is_the_same_picture(self):
        got = layers._scaled(self.frame, (14, 20))
        self.assertIs(layers._scaled(self.frame, (14, 20)), got)
        fresh = pygame.transform.smoothscale(self.frame, (14, 20))
        self.assertEqual(_pixels(got), _pixels(fresh))

    def test_another_surface_is_never_served_a_copy_kept_for_one_gone(self):
        # An id can be recycled once its surface is gone; the entry keeps
        # the source and checks it.
        other = pygame.Surface((40, 60), pygame.SRCALPHA)
        other.fill((0, 90, 255, 255))
        layers._SCALED[(id(other), (14, 20))] = (self.frame, layers._scaled(self.frame, (14, 20)))
        got = layers._scaled(other, (14, 20))
        self.assertEqual(_pixels(got), _pixels(pygame.transform.smoothscale(other, (14, 20))))

    def test_the_store_is_bounded(self):
        with mock.patch.object(layers, "_SCALED_CAP", 3):
            for w in range(4, 14):
                layers._scaled(self.frame, (w, 20))
                self.assertLessEqual(len(layers._SCALED), 3)


class _Camera:
    zoom = 1.5

    def world_to_screen(self, pos):
        return pos.x, pos.y


class PlainNumberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((64, 64))
        pygame.font.init()

    def _draw(self, numbers):
        s = pygame.Surface((400, 200), pygame.SRCALPHA)
        s.fill((30, 60, 40, 255))
        numbers.draw(s, _Camera())
        return _pixels(s)

    def _numbers(self):
        n = DamageNumbers()
        # Two identical plain numbers at different points of their life
        # share one glyph and must still draw at their own alpha; a crit and
        # an incoming number use the other fonts.
        n.add(pygame.Vector2(80, 80), 12)
        n.add(pygame.Vector2(200, 80), 12)
        n.add(pygame.Vector2(300, 80), 12, crit=True)
        n.add(pygame.Vector2(80, 160), 7, incoming=True)
        n.add(pygame.Vector2(200, 160), 5, healing=True)
        n.update(0.1)
        live = list(n._pool)
        live[1].life = live[1].max_life * 0.3
        return n

    def test_kept_glyphs_draw_what_fresh_renders_draw(self):
        cached = self._numbers()
        fresh = self._numbers()
        uncached = mock.patch.object(
            DamageNumbers, "_plain", lambda self, font, text, colour: font.render(text, True, colour))
        for step in range(3):                             # cold, then warm as the alphas fall
            with self.subTest(step=step):
                with uncached:
                    want = self._draw(fresh)
                self.assertEqual(self._draw(cached), want)
            cached.update(0.1)
            fresh.update(0.1)

    def test_a_glyph_is_rendered_once(self):
        numbers = self._numbers()
        self._draw(numbers)
        kept = dict(numbers._glyphs)
        self._draw(numbers)
        self.assertEqual(numbers._glyphs, kept)
        self.assertEqual(len(kept), 4)                   # 12, 12 crit, 7 incoming, +5


if __name__ == "__main__":
    unittest.main()
