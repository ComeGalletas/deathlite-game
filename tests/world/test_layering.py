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
        """The list is the guard: a module joins `world.rules` only when it
        can be read by every layer without pulling one of them in.

        `spacing` joined it when the spawn-point stage needed the spatial hash
        the decor scatter already used (D1,
        `documentation/journals/placement_review_journal.md`). It qualifies by
        the hardest reading of the rule above: it imports nothing at all --
        not the data model, not the terrain data -- and the test below says
        so, so it cannot quietly grow a dependency later."""
        names = {p.stem for p in (WORLD / "rules").glob("*.py")} - {"__init__"}
        self.assertEqual(names,
                         {"frontier", "inset", "floor", "steps", "biome", "spacing"})

    def test_the_spatial_hash_stays_pure_geometry(self):
        """`spacing` is shared by the generator and the bake. It earns that by
        importing nothing, which is what keeps it from being a back door
        between the two."""
        imports = {i for i in _imports(WORLD / "rules" / "spacing.py")
                   if not i.startswith("__future__")}
        self.assertEqual(imports, set(), f"world/rules/spacing.py imports {imports}")


if __name__ == "__main__":
    unittest.main()
