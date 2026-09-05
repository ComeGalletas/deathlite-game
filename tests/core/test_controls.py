"""CB-5 group A: the controls configuration and the active key layout.

`config.KEY_LAYOUTS` holds raw SDL keycodes (the module is imported before
`pygame.init()`), so the first test pins them against `pygame.K_*`; the rest
cover the layout accessors on `Game`, which read and persist
`save.settings["key_layout"]`.
"""
import json
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.game import Game

_DIRS = ("left", "right", "up", "down")


class KeyLayoutConfigTests(unittest.TestCase):
    def test_raw_keycodes_match_pygame(self):
        self.assertEqual(config.KEY_TOGGLE_AUTO_ATTACK, pygame.K_q)
        wasd = config.KEY_LAYOUTS["wasd_move"]["move"]
        arrows = config.KEY_LAYOUTS["wasd_move"]["aim"]
        self.assertEqual(wasd, {"left": (pygame.K_a,), "right": (pygame.K_d,),
                                "up": (pygame.K_w,), "down": (pygame.K_s,)})
        self.assertEqual(arrows, {"left": (pygame.K_LEFT,), "right": (pygame.K_RIGHT,),
                                  "up": (pygame.K_UP,), "down": (pygame.K_DOWN,)})

    def test_every_layout_binds_move_and_aim_to_disjoint_keys(self):
        for name, layout in config.KEY_LAYOUTS.items():
            with self.subTest(layout=name):
                self.assertEqual(set(layout), {"move", "aim"})
                for role in ("move", "aim"):
                    self.assertEqual(set(layout[role]), set(_DIRS))
                move = {k for keys in layout["move"].values() for k in keys}
                aim = {k for keys in layout["aim"].values() for k in keys}
                self.assertFalse(move & aim, "a key cannot both move and aim")
                self.assertNotIn(config.KEY_TOGGLE_AUTO_ATTACK, move | aim)

    def test_swapped_layout_is_the_mirror_of_the_default(self):
        base = config.KEY_LAYOUTS["wasd_move"]
        swapped = config.KEY_LAYOUTS["arrows_move"]
        self.assertEqual(swapped["move"], base["aim"])
        self.assertEqual(swapped["aim"], base["move"])

    def test_default_layout_exists_and_is_labelled(self):
        self.assertIn(config.DEFAULT_KEY_LAYOUT, config.KEY_LAYOUTS)
        self.assertEqual(set(config.KEY_LAYOUT_LABELS), set(config.KEY_LAYOUTS))
        self.assertTrue(config.AUTO_ATTACK_DEFAULT)
        self.assertGreater(config.MANUAL_AIM_ASSIST_DEG, 0.0)


class GameKeyLayoutTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "save.json")
        self.game = Game(save_path=self.path)

    def tearDown(self):
        pygame.quit()

    def test_fresh_game_uses_the_default_layout(self):
        self.assertEqual(self.game.key_layout, config.DEFAULT_KEY_LAYOUT)
        self.assertIs(self.game.keys, config.KEY_LAYOUTS[config.DEFAULT_KEY_LAYOUT])

    def test_set_key_layout_persists_immediately(self):
        self.game.set_key_layout("arrows_move")
        self.assertEqual(self.game.key_layout, "arrows_move")
        self.assertIs(self.game.keys, config.KEY_LAYOUTS["arrows_move"])
        if config.SAVE_ENABLED:
            on_disk = json.loads(open(self.path, encoding="utf-8").read())
            self.assertEqual(on_disk["settings"]["key_layout"], "arrows_move")

    def test_unknown_layout_is_refused(self):
        with self.assertRaises(ValueError):
            self.game.set_key_layout("dvorak")
        self.assertEqual(self.game.key_layout, config.DEFAULT_KEY_LAYOUT)

    def test_cycle_walks_every_layout_and_wraps(self):
        seen = [self.game.key_layout]
        for _ in range(len(config.KEY_LAYOUTS)):
            seen.append(self.game.cycle_key_layout())
        self.assertEqual(seen[0], seen[-1])
        self.assertEqual(set(seen), set(config.KEY_LAYOUTS))

    def test_a_junk_layout_in_the_save_reads_as_the_default(self):
        # Defence in depth: `save.py` already coerces, but the property must
        # never hand out a name `config.KEY_LAYOUTS` cannot index.
        self.game.save.settings["key_layout"] = "dvorak"
        self.assertEqual(self.game.key_layout, config.DEFAULT_KEY_LAYOUT)
        self.assertIs(self.game.keys, config.KEY_LAYOUTS[config.DEFAULT_KEY_LAYOUT])


if __name__ == "__main__":
    unittest.main()
