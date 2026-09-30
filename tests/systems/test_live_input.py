"""`run_on_top` and `StateMachine.is_covered` (RND-010.D6): the run shows held
input unless another state sits above it on the stack. A run drawn on its
own, as many tests draw it, counts as on top."""
import types
import unittest

from game.state import State, StateMachine
from game.states.playing.visual.live_input import run_on_top


def _machine():
    game = types.SimpleNamespace(music=None)
    game.state_machine = StateMachine(game)
    return game


class LiveInputTests(unittest.TestCase):
    def test_no_state_machine_is_on_top(self):
        self.assertTrue(run_on_top(types.SimpleNamespace(game=None)))
        self.assertTrue(run_on_top(object()))

    def test_a_run_not_on_the_stack_is_on_top(self):
        game = _machine()
        run = State(game)
        self.assertFalse(game.state_machine.is_covered(run))
        self.assertTrue(run_on_top(run))

    def test_the_top_state_is_on_top(self):
        game = _machine()
        run = State(game)
        game.state_machine.push(run)
        self.assertTrue(run_on_top(run))

    def test_a_state_under_an_overlay_is_covered(self):
        game = _machine()
        run, overlay = State(game), State(game)
        game.state_machine.push(run)
        game.state_machine.push(overlay)
        self.assertTrue(game.state_machine.is_covered(run))
        self.assertFalse(run_on_top(run))
        self.assertTrue(run_on_top(overlay))
        game.state_machine.pop()
        self.assertTrue(run_on_top(run))


if __name__ == "__main__":
    unittest.main()
