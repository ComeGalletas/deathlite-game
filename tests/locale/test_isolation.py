"""No test boots a real `Game` from the developer's own save (UI-014.3).

`Game()` with no `save_path` loads the repo-root `save.json` -- the one the
game writes when played from source -- and since UI-014 it sets the process
language from it. A developer who picked Spanish would then run every later
test in Spanish, and English text assertions would fail by test order. The
pytest fixture in `tests/conftest.py` resets the language around every test;
this check keeps the cause out as well, so the plain unittest runner is
covered too."""
import ast
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent


def _unpinned_game_calls():
    for path in sorted(TESTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "Game"
                    and not any(k.arg == "save_path" for k in node.keywords)
                    and not node.args):
                yield f"{path.relative_to(TESTS)}:{node.lineno}"


class GameSavePathTests(unittest.TestCase):
    def test_every_game_a_test_boots_has_its_own_save_path(self):
        self.assertEqual(list(_unpinned_game_calls()), [])

    def test_the_check_finds_an_unpinned_call(self):
        tree = ast.parse("Game()\nGame(save_path=p)\nGame(p)\n")
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        unpinned = [n for n in calls
                    if not any(k.arg == "save_path" for k in n.keywords)
                    and not n.args]
        self.assertEqual(len(unpinned), 1)


if __name__ == "__main__":
    unittest.main()
