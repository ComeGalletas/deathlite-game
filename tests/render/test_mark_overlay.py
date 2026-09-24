"""RND-007: the `mark` status drawn as lock-on brackets on the marked body.

Pure: a stand-in run and body around the real `WorldRenderer`, asset loader,
status state and `status_marks` module. The numbers come from
`data/weapons/status_visuals.json`.
"""
import inspect
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat.status import StatusState
from game.assets import get_assets
from game.states.playing.visual import rendering, status_marks
from game.states.playing.visual.rendering import WorldRenderer
from systems.animation import Animator

BG = (0, 0, 0)


class _Weapon:
    def __init__(self, **effects):
        self.effects = effects

    def effect(self, key, default=0.0):
        return float(self.effects.get(key, default))


def _body(rig="skull", marked=True, left=1.5, pos=(200, 200)):
    status = StatusState()
    if marked:
        status.apply("mark", left, 1.0)
    return SimpleNamespace(pos=pygame.Vector2(pos), radius=10.0, _facing=1,
                           status=status, anim=Animator(get_assets(), rig))


def _renderer(weapons, t=0.0):
    camera = SimpleNamespace(zoom=1.0, world_to_screen=lambda p: (p[0], p[1]))
    run = SimpleNamespace(camera=camera, stats={"time": t},
                          player=SimpleNamespace(weapons=list(weapons)))
    ps = SimpleNamespace(run=run, game=SimpleNamespace(assets=get_assets()))
    return WorldRenderer(ps)


def _lit(surface):
    return surface.get_bounding_rect()


class MarkOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    def _draw(self, body, weapons):
        surf = pygame.Surface((400, 400), pygame.SRCALPHA)
        status_marks.draw(_renderer(weapons), surf, body)
        return surf

    def test_a_marked_body_is_bracketed_while_a_blessing_reads_the_mark(self):
        surf = self._draw(_body(), [_Weapon(syn_vs_marked=0.3)])
        box = _lit(surf)
        self.assertGreater(box.width, 0, "nothing drawn")
        self.assertTrue(box.collidepoint(200, 190), "not round the body")

    def test_nothing_without_a_blessing_that_reads_the_mark(self):
        """A Rod build nothing pays out for shows nothing (owner)."""
        surf = self._draw(_body(), [_Weapon(syn_after_sword=0.5), _Weapon()])
        self.assertEqual(_lit(surf).width, 0)

    def test_nothing_on_an_unmarked_body(self):
        surf = self._draw(_body(marked=False), [_Weapon(syn_vs_marked=0.3)])
        self.assertEqual(_lit(surf).width, 0)

    def test_it_fades_over_the_marks_last_seconds(self):
        fade = status_marks.spec()["fade"]
        self.assertEqual(status_marks.alpha(_body(left=1.5)), 255)
        self.assertAlmostEqual(status_marks.alpha(_body(left=fade / 2)), 127, delta=2)

    def test_the_brackets_frame_the_body_whatever_its_size(self):
        """The art's box is scaled to `over_body` x the body's larger side --
        its resting pose, not the rig's crop, which carries swing room (the
        first build framed the crop and bracketed a bear at twice its size)."""
        a = get_assets()
        s = status_marks.spec()
        for rig in ("skull", "turtle", "bear"):
            with self.subTest(rig=rig):
                size = status_marks.frame_size(a, _body(rig), 1.0)
                bb = status_marks.body_box(a, rig, 1.0)
                self.assertAlmostEqual(size[0] * s["box"] / a.scale_for(s["sprite"])[0],
                                       max(bb.width, bb.height) * s["over_body"], delta=2)
                self.assertLess(max(bb.width, bb.height), max(a.scale_for(rig)),
                                "the body box should be tighter than the rig crop")
        small = status_marks.frame_size(a, _body("skull"), 1.0)
        big = status_marks.frame_size(a, _body("turtle"), 1.0)
        self.assertGreater(big[0], small[0])

    def test_the_brackets_are_centred_on_the_body_either_way_it_faces(self):
        """The drawn brackets' centre is the body box's, placed as the
        sprite is -- mirrored when the body faces left."""
        a = get_assets()
        r = _renderer([_Weapon(syn_vs_marked=0.3)])
        for facing in (1, -1):
            body = _body("bear")
            body._facing = facing
            cx, cy = status_marks.body_centre(r, a, body, 1.0)
            flip = facing < 0 and a.face("bear") == "right"
            frame = a.frames("bear", "idle", size=a.scale_for("bear"), flip=flip)[0]
            ax, ay = r.anchor_for("bear", flip)
            left, top = 200 - ax, 200 - ay + r.sprite_drop(body.radius)
            want = frame.get_bounding_rect().move(round(left), round(top)).center
            with self.subTest(facing=facing):
                self.assertAlmostEqual(cx, want[0], delta=1.5)
                self.assertAlmostEqual(cy, want[1], delta=1.5)

    def test_it_is_drawn_right_after_the_body_for_enemies_and_the_boss(self):
        """Over the body, and depth-sorted with it."""
        enemy = inspect.getsource(WorldRenderer.one_enemy)
        self.assertLess(enemy.index("self.enemy_sprite(surface, e)"),
                        enemy.index("status_marks.draw(self, surface, e)"))
        boss = inspect.getsource(WorldRenderer.boss)
        self.assertLess(boss.index("self.blit_rig("),
                        boss.index("status_marks.draw(self, surface, b)"))

    def test_the_fallback_ring_is_the_datas_raspberry(self):
        self.assertEqual(rendering._STATUS_TINT["mark"],
                         tuple(status_marks.spec()["colour"]))


if __name__ == "__main__":
    unittest.main()
