"""ui/hud.py: what the in-run HUD draws, and what it deliberately does not.

Two claims worth pinning. The HUD was cut down to four things (the level gem,
the HP and XP bars, the run timer, plus a boss bar during a boss fight), so a
test here catches a readout creeping back into a corner. And every piece drawn
from the HUD sheets has a primitive fallback, so a missing sheet degrades the
look without taking the run with it.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.assets import get_assets, reset_assets
from ui import bars
from ui.hud import HUD

GROUND = (58, 92, 54)
STATS = {"time": 187.0, "level": 7, "kills": 42, "gold": 310}


class _Player:
    hp, max_hp = 148, 240
    trait = "bulwark"
    bulwark_active = True

    def __init__(self):
        self.weapons = [mock.Mock(name="Sword", level=3)]
        self.blessings = {"sword_keen_edge": 2}


class _Boss:
    alive = True
    hp_fraction = 0.71
    name = "Warden of the Deep"


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.font.init()          # HUD builds its fonts in __init__
        pygame.display.set_mode((64, 64))

    def setUp(self):
        reset_assets()
        bars.clear_cache()
        self.hud = HUD()
        self.player = _Player()

    def screen(self):
        s = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        s.fill(GROUND)
        return s

    def painted(self, surf, rect) -> int:
        """Pixels inside `rect` that are no longer the flat ground colour."""
        return sum(1 for y in range(rect.top, rect.bottom)
                   for x in range(rect.left, rect.right)
                   if surf.get_at((x, y))[:3] != GROUND)


class ContentTests(_Base):
    """The HUD shows four things and nothing else (owner, 2026-09-12)."""

    def test_the_top_left_cluster_and_the_timer_are_drawn(self):
        s = self.screen()
        self.hud.draw(s, self.player, STATS, xp_fraction=0.35)
        cluster = pygame.Rect(16, config.HUD_LEFT_TOP, 400, 70)
        timer = pygame.Rect(config.SCREEN_WIDTH // 2 - 60, 10, 120, 40)
        self.assertGreater(self.painted(s, cluster), 500)
        self.assertGreater(self.painted(s, timer), 50)

    def test_nothing_is_drawn_in_the_other_corners(self):
        # The kill / gold counters, the trait line, the blessing list and the
        # weapon list were cut -- the run-status screen (TAB) covers them.
        s = self.screen()
        self.hud.draw(s, self.player, STATS, xp_fraction=0.35)
        w, h = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        for name, rect in (("top right", pygame.Rect(w - 400, 0, 400, 300)),
                           ("bottom left", pygame.Rect(0, h - 200, 400, 200)),
                           ("bottom right", pygame.Rect(w - 400, h - 200, 400, 200))):
            self.assertEqual(self.painted(s, rect), 0,
                             f"something is drawn in the {name} corner")

    def test_no_boss_means_no_boss_bar(self):
        s = self.screen()
        self.hud.draw(s, self.player, STATS, xp_fraction=0.35, boss=None)
        bottom = pygame.Rect(0, config.SCREEN_HEIGHT - 120, config.SCREEN_WIDTH, 120)
        self.assertEqual(self.painted(s, bottom), 0)

    def test_a_dead_boss_keeps_its_bar_off_the_screen(self):
        boss = _Boss()
        boss.alive = False
        s = self.screen()
        self.hud.draw(s, self.player, STATS, xp_fraction=0.35, boss=boss)
        bottom = pygame.Rect(0, config.SCREEN_HEIGHT - 120, config.SCREEN_WIDTH, 120)
        self.assertEqual(self.painted(s, bottom), 0)


class BossBarTests(_Base):
    """The boss bar: the same hex family as the hero's, centred and wide."""

    def test_it_is_the_hex_bar_centred_above_the_bottom_edge(self):
        s = self.screen()
        self.assertTrue(self.hud._draw_boss(s, _Boss()))
        want = bars.bar(get_assets(), frame=config.HUD_BOSS_FRAME,
                        fill=config.HUD_BOSS_FILL, empty=config.HUD_BAR_EMPTY,
                        width=int(config.SCREEN_WIDTH * config.HUD_BOSS_WIDTH)
                        // config.HUD_BAR_SCALE,
                        fraction=_Boss.hp_fraction, framed=True,
                        scale=config.HUD_BAR_SCALE)
        x = (config.SCREEN_WIDTH - want.get_width()) // 2
        y = config.SCREEN_HEIGHT - config.HUD_BOSS_BOTTOM - want.get_height()
        for wy in range(want.get_height()):
            for wx in range(want.get_width()):
                ink = want.get_at((wx, wy))
                if ink[3] == 0:
                    continue
                self.assertEqual(s.get_at((x + wx, y + wy))[:3], ink[:3],
                                 f"boss bar differs at {wx},{wy}")

    def test_it_is_about_half_the_screen_wide(self):
        s = self.screen()
        self.hud._draw_boss(s, _Boss())
        row = config.SCREEN_HEIGHT - config.HUD_BOSS_BOTTOM - 16
        lit = [x for x in range(config.SCREEN_WIDTH)
               if s.get_at((x, row))[:3] != GROUND]
        self.assertAlmostEqual(len(lit),
                               config.SCREEN_WIDTH * config.HUD_BOSS_WIDTH,
                               delta=config.HUD_BAR_SCALE * 4)

    def test_the_name_sits_clear_above_the_bar(self):
        s = self.screen()
        self.hud._draw_boss(s, _Boss())
        bar_top = config.SCREEN_HEIGHT - config.HUD_BOSS_BOTTOM \
            - 11 * config.HUD_BAR_SCALE
        band = pygame.Rect(0, bar_top - 40, config.SCREEN_WIDTH, 38)
        self.assertGreater(self.painted(s, band), 100, "the boss name is missing")


class FallbackTests(_Base):
    """A missing sheet degrades the look, never the run."""

    def test_the_meters_fall_back_to_rectangles(self):
        with mock.patch.object(config, "HUD_BAR_FRAME", "no_such_rig"):
            s = self.screen()
            self.assertFalse(self.hud._draw_meters(s, self.player, STATS, 0.35))
            self.hud.draw(s, self.player, STATS, xp_fraction=0.35)
            self.assertEqual(s.get_at((16, config.HUD_LEFT_TOP))[:3],
                             config.COLOR_WORLD_BORDER)

    def test_the_boss_bar_falls_back_to_a_rectangle(self):
        with mock.patch.object(config, "HUD_BOSS_FRAME", "no_such_rig"):
            s = self.screen()
            self.assertFalse(self.hud._draw_boss(s, _Boss()))
            self.hud.draw(s, self.player, STATS, xp_fraction=0.35, boss=_Boss())
            bottom = pygame.Rect(0, config.SCREEN_HEIGHT - 120,
                                 config.SCREEN_WIDTH, 120)
            self.assertGreater(self.painted(s, bottom), 1000)

    def test_both_fallbacks_sit_where_the_art_sits(self):
        # The HUD must not jump when the sheets go missing.
        art, flat = self.screen(), self.screen()
        self.hud.draw(art, self.player, STATS, xp_fraction=0.35, boss=_Boss())
        with mock.patch.object(config, "HUD_BAR_FRAME", "no_such_rig"), \
             mock.patch.object(config, "HUD_BOSS_FRAME", "no_such_rig"):
            self.hud.draw(flat, self.player, STATS, xp_fraction=0.35, boss=_Boss())
        for name, rect in (
                ("meters", pygame.Rect(0, 0, 400, config.HUD_LEFT_TOP)),
                ("boss", pygame.Rect(0, config.SCREEN_HEIGHT
                                     - config.HUD_BOSS_BOTTOM, 1600, 28))):
            self.assertEqual(self.painted(art, rect), 0, f"{name} art overflows")
            self.assertEqual(self.painted(flat, rect), 0, f"{name} fallback overflows")

class LevelNumberTests(_Base):
    """The level number on the gem (owner, 2026-09-15: it read slightly right
    of centre). The digit's ink is centred on the core art's centre, then
    nudged by `HUD_LEVEL_NUDGE`; so every digit lands the same way."""

    def _ink_centre(self, level):
        s = self.screen()
        self.hud.draw(s, self.player, dict(STATS, level=level), xp_fraction=0.5)
        gem = pygame.Rect(16, config.HUD_LEFT_TOP, config.HUD_GEM_PX, config.HUD_GEM_PX)
        dark = [(x, y) for y in range(gem.top, gem.bottom) for x in range(gem.left, gem.right)
                if s.get_at((x, y))[:3] == config.COLOR_ON_BUTTON]
        self.assertTrue(dark, "no digit ink found on the gem")
        xs, ys = [x for x, _ in dark], [y for _, y in dark]
        return ((min(xs) + max(xs) + 1) / 2.0, (min(ys) + max(ys) + 1) / 2.0)

    def test_the_digit_ink_sits_on_the_core_centre_plus_the_nudge(self):
        cx, cy = bars.core_centre(get_assets(), core=config.HUD_GEM_CORE, size=config.HUD_GEM_PX)
        nx, ny = config.HUD_LEVEL_NUDGE
        want = (16 + cx + nx, config.HUD_LEFT_TOP + cy + ny)
        for level in (1, 4, 7, 12):
            got = self._ink_centre(level)
            self.assertLessEqual(abs(got[0] - want[0]), 1.0, (level, got, want))
            self.assertLessEqual(abs(got[1] - want[1]), 1.0, (level, got, want))

    def test_every_digit_lands_alike(self):
        centres = [self._ink_centre(level) for level in (1, 4, 7)]
        self.assertLessEqual(max(c[0] for c in centres) - min(c[0] for c in centres), 1.0)

    def test_the_core_centre_falls_back_to_the_sprite_centre_without_art(self):
        with mock.patch.object(config, "HUD_GEM_CORE", "no_such_core"):
            bars.clear_cache()
            self.assertEqual(bars.core_centre(get_assets(), core=config.HUD_GEM_CORE, size=64),
                             (32.0, 32.0))

