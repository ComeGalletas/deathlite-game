"""The run's opening keycap hints (journal: key_icons_journal.md, pass 5):
Move, then Attack, over the hero; shown every run while the Options
"Tutorials" row is on. Seed 1234 is pinned."""
import os
import tempfile
import unittest
from unittest import mock

import pygame

from game import config, save as save_mod
from game.game import Game
from game.states.playing.core.aim import AimInput
from game.states.playing.core.hints import RunHints
from game.states.playing.core.state import PlayingState
from game.states.playing.visual import hints as hints_draw
from ui import keycap


def _run(seed=1234, tutorials=True):
    g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
    g.set_tutorials(tutorials)
    p = PlayingState(g)
    p.enter(seed=seed)
    return g, p


class _Pressed:
    """Stands in for `pygame.key.get_pressed()`: true for `down`."""

    def __init__(self, *down):
        self.down = set(down)

    def __getitem__(self, k):
        return k in self.down


class StageTests(unittest.TestCase):
    def test_a_run_opens_on_the_move_hint(self):
        _g, p = _run()
        self.assertEqual(p.hints.stage, "move")
        self.assertTrue(p.hints.visible)
        self.assertEqual(p.hints.clusters(), [("Move", [["W"], ["A", "S", "D"]])])

    def test_the_arrows_layout_shows_arrows(self):
        g, p = _run()
        g.set_key_layout("arrows_move")
        self.assertEqual(p.hints.clusters()[0][1],
                         [["↑"], ["←", "↓", "→"]])

    def test_tutorials_off_shows_nothing(self):
        _g, p = _run(tutorials=False)
        self.assertIsNone(p.hints.stage)
        self.assertFalse(p.hints.visible)
        self.assertIsNone(hints_draw.draw(pygame.Surface((64, 64)), p))

    def test_the_build_switch_wins(self):
        with mock.patch.object(config, "TUTORIAL_HINTS", False):
            _g, p = _run()
        self.assertIsNone(p.hints.stage)

    def test_moving_three_tiles_moves_on_to_attack(self):
        _g, p = _run()
        p.player.pos.x += config.HINT_MOVE_DISTANCE - 1
        p.hints.update(1 / 60)
        self.assertEqual(p.hints.stage, "move")
        p.player.pos.x += 2
        p.hints.update(1 / 60)
        self.assertEqual(p.hints.stage, "attack")
        self.assertIsNotNone(p.hints.fading)           # the Move cluster fades out
        self.assertEqual([w for w, _ in p.hints.clusters()], ["Attack", "Aim"])
        self.assertEqual(p.hints.clusters()[0][1], [[keycap.MOUSE]])

    def test_an_aimed_attack_finishes_the_attack_hint(self):
        _g, p = _run()
        p.hints.stage = "attack"
        p._aim = AimInput(direction=None, source=None)
        p.hints.update(1 / 60)
        self.assertEqual(p.hints.stage, "attack")      # auto-aim does not count
        p._aim = AimInput(direction=pygame.Vector2(1, 0), source="mouse")
        p.hints.update(1 / 60)
        self.assertIsNone(p.hints.stage)

    def test_the_attack_hint_gives_up_after_its_time(self):
        _g, p = _run()
        p.hints.stage = "attack"
        p._aim = None
        p.hints.update(config.HINT_ATTACK_SECONDS - 0.1)
        self.assertEqual(p.hints.stage, "attack")
        p.hints.update(0.2)
        self.assertIsNone(p.hints.stage)

    def test_the_fade_runs_out(self):
        _g, p = _run()
        p.hints._advance("attack")
        p.hints.update(config.HINT_FADE + 0.01)
        self.assertIsNone(p.hints.fading)

    def test_escape_dismisses_for_the_run(self):
        g, p = _run()
        with mock.patch.object(g.state_machine, "push"):
            p.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertIsNone(p.hints.stage)
        self.assertFalse(p.hints.visible)

    def test_the_whole_update_ticks_the_hints(self):
        _g, p = _run()
        p.hints.stage = "attack"
        with mock.patch.object(pygame.key, "get_pressed", return_value=_Pressed()), \
             mock.patch.object(pygame.mouse, "get_pressed", return_value=(0, 0, 0)):
            p.update(config.HINT_ATTACK_SECONDS + 0.5)
        self.assertIsNone(p.hints.stage)

    def test_held_keys_and_the_mouse_read_through(self):
        _g, p = _run()
        self.assertEqual(p.hints.keycodes_for("W"), (pygame.K_w,))
        with mock.patch.object(pygame.key, "get_pressed", return_value=_Pressed(pygame.K_a)):
            self.assertTrue(p.hints.held("A"))
            self.assertFalse(p.hints.held("W"))
        with mock.patch.object(pygame.mouse, "get_pressed", return_value=(1, 0, 0)):
            self.assertTrue(p.hints.held(keycap.MOUSE))


class SettingTests(unittest.TestCase):
    def test_the_setting_persists_and_defaults_on(self):
        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        self.assertTrue(g.tutorials)
        g.set_tutorials(False)
        self.assertFalse(save_mod.load(g.save_path).settings["tutorials"])
        g.set_tutorials(True)
        self.assertTrue(save_mod.load(g.save_path).settings["tutorials"])

    def test_the_options_row_toggles_and_persists(self):
        from game.states.options_state import OptionsState
        g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        g.state_machine.change(OptionsState(g))
        opt = g.state_machine.current
        opt.sel = opt._rows.index("tutorials")
        g.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertFalse(g.tutorials)
        self.assertFalse(save_mod.load(g.save_path).settings["tutorials"])
        g.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))
        self.assertTrue(g.tutorials)
        # And it is in the in-run rows too.
        opt2 = OptionsState(g)
        g.state_machine.change(opt2, in_run=True)
        self.assertIn("tutorials", opt2._rows)


class DrawTests(unittest.TestCase):
    def setUp(self):
        self.g, self.p = _run()
        self.surface = pygame.Surface(self.g.screen.get_size(), pygame.SRCALPHA)

    def test_the_move_hint_is_four_blue_caps_over_the_hero(self):
        p = self.p
        with mock.patch.object(keycap, "draw_keycap", wraps=keycap.draw_keycap) as m:
            rect = hints_draw.draw(self.surface, p)
        self.assertEqual(m.call_count, 4)
        self.assertEqual([c.args[3] for c in m.call_args_list], ["W", "A", "S", "D"])
        self.assertTrue(all(c.kwargs["colour"] == "blue" for c in m.call_args_list))
        cx, top = hints_draw.hero_top(p)
        self.assertLessEqual(rect.bottom, top - hints_draw.CLEAR_PX)
        self.assertLess(rect.left, cx)
        self.assertGreater(rect.right, cx)

    def test_the_hero_top_is_above_the_collider(self):
        p = self.p
        sx, sy = p.camera.world_to_screen(p.player.pos)
        cx, top = hints_draw.hero_top(p)
        self.assertEqual(cx, round(sx))
        self.assertLess(top, sy)

    def test_a_held_key_sinks_its_cap(self):
        p = self.p
        with mock.patch.object(pygame.key, "get_pressed", return_value=_Pressed(pygame.K_d)), \
             mock.patch.object(keycap, "draw_keycap", wraps=keycap.draw_keycap) as m:
            hints_draw.draw(self.surface, p)
        states = {c.args[3]: c.kwargs["state"] for c in m.call_args_list}
        self.assertEqual(states, {"W": "raised", "A": "raised", "S": "raised", "D": "pressed"})

    def test_the_attack_hint_shows_the_mouse_and_the_aim_keys(self):
        p = self.p
        p.hints.stage = "attack"
        with mock.patch.object(keycap, "draw_keycap", wraps=keycap.draw_keycap) as m:
            hints_draw.draw(self.surface, p)
        self.assertEqual([c.args[3] for c in m.call_args_list],
                         [keycap.MOUSE, "↑", "←", "↓", "→"])

    def test_a_fading_stage_is_drawn_translucent_then_gone(self):
        p = self.p
        p.hints._advance("attack")
        p.hints.update(config.HINT_FADE / 2)
        with mock.patch.object(keycap, "draw_keycap", wraps=keycap.draw_keycap) as m:
            self.assertIsNotNone(hints_draw.draw(self.surface, p))
        self.assertEqual([c.args[3] for c in m.call_args_list], ["W", "A", "S", "D"])
        p.hints.update(config.HINT_FADE)
        with mock.patch.object(keycap, "draw_keycap", wraps=keycap.draw_keycap) as m:
            hints_draw.draw(self.surface, p)
        self.assertEqual(m.call_args_list[0].args[3], keycap.MOUSE)

    def test_a_whole_frame_reaches_the_hints(self):
        p = self.p
        with mock.patch.object(hints_draw, "draw", wraps=hints_draw.draw) as m:
            p.draw(self.surface)
        self.assertEqual(m.call_count, 1)


if __name__ == "__main__":
    unittest.main()
