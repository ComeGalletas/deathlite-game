"""Summon rendering (assets journal, WA5): the `@summon_style` registry, the
bite's `melee` classification, the Spirit Wolf drawn from its rig or from the
colour-disc fallback, and the animation state that picks the wolf's strip --
`bite_*` for `_BITE_ANIM_S` after a bite, `run_*` facing the way it moves.

Real assets, no world. Behaviour (chasing, the leash ring, the totem's
phases) is pinned elsewhere: `tests/combat/test_summons.py` and
`tests/render/test_totem_sprite.py`.
"""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities import summon as summon_mod
from entities.projectile import Projectile
from entities.summon import Summon
from game.assets import get_assets
from game.states.playing.visual import projectiles
from game.states.playing.visual import summons
from game.states.playing.visual.drawctx import DrawCtx
from tests.combat.fakes import FakeTarget

COLOUR = (10, 200, 30)
CORE = (240, 245, 255)


def _display():
    pygame.display.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 64))


def _wolf(pos=(0, 0)):
    s = Summon()
    s.active = True
    s.reset(kind="wolf", pos=pygame.Vector2(pos), damage=12, lifetime=99,
            color=COLOUR, tags=("summon",), speed=240, attack_range=70)
    return s


def _ctx(shots, enemies, player=(0, 0)):
    return SimpleNamespace(enemies=enemies,
                           spawn_projectile=lambda **kw: shots.append(kw),
                           player_pos=pygame.Vector2(player))


def _draw(s, zoom=1.0):
    surface = pygame.Surface((160, 160), pygame.SRCALPHA)
    summons.draw_summon(surface, 80, 80, s, DrawCtx(get_assets(), 0.0, zoom))
    return surface


def _ink(surface):
    return [(x, y) for x in range(surface.get_width()) for y in range(surface.get_height())
            if surface.get_at((x, y))[3] > 0]


class RegistryTests(unittest.TestCase):
    def test_the_disc_totem_and_wolf_are_registered(self):
        self.assertLessEqual({"disc", "totem", "wolf"}, set(summons.registered()))

    def test_a_kind_registers_once(self):
        with self.assertRaises(ValueError):
            summons.summon_style("wolf")(lambda *a: None)

    def test_an_unknown_kind_draws_the_default_disc(self):
        _display()
        s = SimpleNamespace(kind="no_such_summon", color=COLOUR)
        surface = _draw(s)
        self.assertEqual(surface.get_at((80, 80))[:3], CORE)        # the bright core
        self.assertEqual(surface.get_at((80 + 6, 80))[:3], COLOUR)  # inside the disc
        self.assertEqual(surface.get_at((80 + 12, 80))[3], 0)       # past its 9 px


class BiteClassifyTests(unittest.TestCase):
    def test_the_bite_is_a_melee_hitbox_that_draws_nothing(self):
        """The wolf's bite is spawned as `style="melee"`: `classify` honours
        an explicit style, and the melee family paints nothing -- the bite
        is sold by the wolf's own `bite_*` strip."""
        _display()
        s, shots = _wolf(), []
        for _ in range(60):
            s.update(1 / 60, _ctx(shots, [FakeTarget(30, 0)]))
            if shots:
                break
        self.assertTrue(shots, "the wolf never bit a foe 30 px away")
        self.assertEqual(shots[0]["style"], "melee")
        p = Projectile()
        p.reset(pos=pygame.Vector2(), vel=pygame.Vector2(1, 0), damage=1,
                radius=22, lifetime=0.12, style="melee")
        self.assertEqual(projectiles.classify(p, "bolt"), "melee")
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        projectiles.draw_projectile(surface, 32, 32, p,
                                    DrawCtx(get_assets(), 0.0, 1.0), default="bolt")
        self.assertEqual(_ink(surface), [])

    def test_without_a_style_the_fields_decide(self):
        p = Projectile()
        p.reset(pos=pygame.Vector2(), vel=pygame.Vector2(1, 0), damage=1,
                radius=4, lifetime=1.0)
        self.assertEqual(projectiles.classify(p, "bolt"), "bolt")


class WolfDrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()

    def test_the_rig_is_drawn_when_it_resolves(self):
        s = _wolf()
        s.anim.play("run_right")
        surface = _draw(s)
        ink = _ink(surface)
        self.assertGreater(len(ink), 60)
        # Not the fallback: the sprite has no disc of the summon's colour
        # with a white core at the seat.
        colours = {surface.get_at(p)[:3] for p in ink}
        self.assertNotEqual(colours, {COLOUR, CORE})
        self.assertNotEqual(surface.get_at((80, 80))[:3], CORE)

    def test_the_sprite_scales_with_the_zoom(self):
        s = _wolf()
        s.anim.play("run_right")
        near = _ink(_draw(s, zoom=1.0))
        far = _ink(_draw(s, zoom=1.5))
        self.assertGreater(len(far), len(near) * 1.5)

    def test_without_the_rig_the_colour_disc_draws(self):
        s = _wolf()
        s.anim.rig = "no_such_rig"
        surface = _draw(s)
        self.assertEqual(surface.get_at((80, 80))[:3], CORE)
        self.assertEqual(surface.get_at((80 + 6, 80))[:3], COLOUR)

    def test_without_an_animator_the_colour_disc_draws(self):
        s = _wolf()
        s.anim = None
        surface = _draw(s)
        self.assertEqual(surface.get_at((80, 80))[:3], CORE)
        self.assertEqual(surface.get_at((80, 80 + 6))[:3], COLOUR)


class WolfAnimTests(unittest.TestCase):
    """The strip the wolf's `Animator` is told to play."""

    @classmethod
    def setUpClass(cls):
        _display()

    def _bite(self, foe_x):
        s, shots = _wolf(), []
        for _ in range(60):
            s.update(1 / 60, _ctx(shots, [FakeTarget(foe_x, 0)]))
            if shots:
                return s, shots
        self.fail("the wolf never bit")

    def test_a_bite_shows_the_bite_strip_for_its_hold_then_runs(self):
        s, _ = self._bite(30)
        hold = summon_mod._BITE_ANIM_S
        self.assertAlmostEqual(hold, 0.32, delta=0.1, msg="about the 5-frame strip at 16 fps")
        self.assertEqual(s.anim.anim, "bite_right")
        # Keep the foe in reach but let no second bite start: a long cooldown.
        s.attack_cd = 99.0
        t = 0.0
        ctx = _ctx([], [FakeTarget(30, 0)])
        while t < hold - 0.05:
            s.update(1 / 60, ctx)
            t += 1 / 60
            self.assertEqual(s.anim.anim, "bite_right", f"at {t:.2f} s")
        for _ in range(12):
            s.update(1 / 60, ctx)
        self.assertEqual(s.anim.anim, "run_right")

    def test_a_bite_faces_its_target(self):
        s, _ = self._bite(-30)
        self.assertEqual(s.anim.anim, "bite_left")

    def test_the_run_faces_the_way_the_wolf_moves(self):
        for foe_x, want in ((600, "run_right"), (-600, "run_left")):
            with self.subTest(foe=foe_x):
                s = _wolf()
                for _ in range(10):
                    s.update(1 / 60, _ctx([], [FakeTarget(foe_x, 0)]))
                self.assertEqual(s.vel.x > 0, foe_x > 0)
                self.assertEqual(s.anim.anim, want)

    def test_the_last_facing_is_kept_when_the_wolf_stops(self):
        s = _wolf()
        for _ in range(10):
            s.update(1 / 60, _ctx([], [FakeTarget(-600, 0)]))
        self.assertEqual(s._side, "left")
        s.attack_cd = 99.0
        s.update(1 / 60, _ctx([], [FakeTarget(s.pos.x - 20, 0)]))   # in range: it stops
        self.assertEqual(s.vel.length(), 0.0)
        self.assertEqual(s.anim.anim, "run_left", "poised, still facing its last way")

    def test_with_nothing_in_reach_and_standing_still_it_sleeps(self):
        s = _wolf()
        s.update(1 / 60, _ctx([], []))
        self.assertEqual(s.anim.anim, "idle")


if __name__ == "__main__":
    unittest.main()
