"""Import direction inside `world/`.

`world.rules` is a layer, not a dumping ground: it reads the data model and
the terrain data, and nothing else in `world/`. The elevation index sits
just above it. If something cannot be placed under that rule, it does not
go there -- this test is what keeps the package from becoming `common`.
"""
import ast
import pathlib
import unittest

WORLD = pathlib.Path(__file__).resolve().parents[2] / "world"

# module or package -> the `world.*` / `game.*` prefixes it may not import
RULES = {
    "rules": ("world.gen", "world.terrain", "world.map", "world.pathfinding",
              "world.elevation", "world.spawning", "world.digest"),
    "elevation.py": ("world.gen", "world.terrain", "world.map",
                     "world.pathfinding", "world.spawning"),
    "layout.py": ("world.gen", "world.terrain", "world.map",
                  "world.pathfinding", "world.rules", "world.elevation"),
    # The bake and the draw read the layout and the rules; a palette is data
    # decided at generation and stored on the room, never re-derived here.
    "terrain": ("world.gen", "world.pathfinding", "world.spawning"),
}


def _imports(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
            out.update(f"{node.module}.{a.name}" for a in node.names)
    return out


def _modules(target: pathlib.Path):
    if target.is_dir():
        return sorted(target.rglob("*.py"))
    return [target]


class LayeringTests(unittest.TestCase):
    def test_rules_and_the_index_import_nothing_above_them(self):
        for name, banned in RULES.items():
            for path in _modules(WORLD / name):
                for imp in _imports(path):
                    for prefix in banned:
                        self.assertFalse(
                            imp == prefix or imp.startswith(prefix + "."),
                            f"{path.relative_to(WORLD.parent)} imports {imp}")

    def test_the_rules_package_has_the_modules_it_says(self):
        names = {p.stem for p in (WORLD / "rules").glob("*.py")} - {"__init__"}
        self.assertEqual(names, {"frontier", "inset", "floor", "steps", "biome"})


if __name__ == "__main__":
    unittest.main()
