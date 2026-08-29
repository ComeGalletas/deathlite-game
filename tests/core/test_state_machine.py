"""Milestone 1: state stack semantics -- push/pop/change and the
update_below / draw_below propagation rules."""
import unittest

from game.state import State, StateMachine


class Rec(State):
    """Records which hooks fired, for assertions."""
    draw_below = False
    update_below = False

    def __init__(self, name, draw_below=False, update_below=False):
        super().__init__(game=None)
        self.name = name
        self.draw_below = draw_below
        self.update_below = update_below
        self.log = []

    def enter(self, **kw): self.log.append("enter")
    def exit(self): self.log.append("exit")
    def update(self, dt): self.log.append(("update", dt))
    def draw(self, surface): self.log.append("draw")


class StateMachineTests(unittest.TestCase):
    def setUp(self):
        self.sm = StateMachine(game=None)

    def test_change_clears_stack_and_calls_lifecycle(self):
        a, b = Rec("a"), Rec("b")
        self.sm.change(a)
        self.sm.change(b)
        self.assertIn("enter", a.log)
        self.assertIn("exit", a.log)
        self.assertIs(self.sm.current, b)

    def test_push_pop_returns_to_previous(self):
        a, b = Rec("a"), Rec("b")
        self.sm.push(a)
        self.sm.push(b)
        self.assertIs(self.sm.current, b)
        self.sm.pop()
        self.assertIs(self.sm.current, a)
        self.assertIn("exit", b.log)

    def test_update_stops_at_opaque_overlay(self):
        base = Rec("base")
        overlay = Rec("overlay", update_below=False)
        self.sm.push(base)
        self.sm.push(overlay)
        self.sm.update(0.016)
        self.assertTrue(any(e[0] == "update" for e in overlay.log if isinstance(e, tuple)))
        self.assertFalse(any(isinstance(e, tuple) for e in base.log))

    def test_update_passes_through_transparent_overlay(self):
        base = Rec("base")
        overlay = Rec("overlay", update_below=True)
        self.sm.push(base)
        self.sm.push(overlay)
        self.sm.update(0.016)
        self.assertTrue(any(isinstance(e, tuple) for e in base.log))

    def test_draw_starts_below_transparent_overlay(self):
        base = Rec("base")
        overlay = Rec("overlay", draw_below=True)
        self.sm.push(base)
        self.sm.push(overlay)
        self.sm.draw(surface=None)
        self.assertEqual(base.log.count("draw"), 1)
        self.assertEqual(overlay.log.count("draw"), 1)


if __name__ == "__main__":
    unittest.main()
