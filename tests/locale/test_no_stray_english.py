"""No stray English in the player-facing code (UI-014.11).

Every module under `ui/`, `game/states/`, `progression/` and `game/display/`
is parsed, and every string literal with words in it must be one of:

* a docstring, or text inside a log call, a `raise` or an `assert`;
* a locale key: the first argument of `locale.t`, `name`, `has`, `plural`,
  `text`, `english` or `unit` (f-strings included, `f"difficulty.{d}"`);
* an identifier-like id (`"sword"`, `"status.more"`, `"buff:{kind}"`),
  a name in `__all__`, a regular expression, a `__repr__` / `__str__` body,
  or a ctypes structure's field name;
* a name handed to `getattr`, `WinDLL` and the like, directly or through a
  `for` over a literal tuple whose variable is used for nothing else
  (TST-009);
* an entry of `ALLOWED`, which says why that English is meant to stay.

The developer tools stay English (UI-014.D6) and are not scanned. A new
player-facing string written as a literal fails here with its file and
line; the fix is a locale key, or an `ALLOWED` entry with its reason.
`ALLOWED` cannot go stale: an entry nothing matches fails too.

What it cannot tell apart: a single lowercase word with no spaces
("paused") reads as an id, the shape every key and table name has. Words
with a space, a capital or a "..." are judged.
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRS = ("ui", "game/states", "progression", "game/display")
DEV = re.compile(r"(^|/)(dev_[^/]*|devtools)(/|\.py$)|debug")
WORDS = re.compile(r"[A-Za-z]{2,}")
# Ids have no spaces: "status.more", "buff:{}", "bless:{}#{}"; "{}" is an
# f-string hole. A space means words, and words are judged.
IDENT = re.compile(r"^(?!.*\.\.)[a-z0-9_./:%<>=#?\[\](){}-]*$")   # "loading..." is words
CONSTANT = re.compile(r"^[A-Z0-9]+(_[A-Z0-9]+)+$")  # SDL_HINT_NAME; a bare "PAUSED" is judged
NAME_ARGS = {"getattr", "hasattr", "setattr", "CDLL", "WinDLL", "find_library",
             "OpenKey", "QueryValueEx", "import_module"}
LOCALE_FUNCS = {"t", "name", "has", "plural", "text", "english", "unit"}
LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical"}
LOGGERS = {"log", "_log", "logger", "_logger", "logging", "LOG"}     # what a log call is made on

# (module, literal) -> why this English stays.
ALLOWED = {
    # Key legends: a keycap shows what the key prints (UI-014.D16).
    **{("ui/keycap.py", k): "a keycap legend (UI-014.D16)"
       for k in ("TAB", "ESC", "ENTER", "CTRL", "ALT")},
    **{("ui/keycap.py", k): "a pygame key name, looked up, never drawn"
       for k in ("left ctrl", "right ctrl", "left alt", "right alt",
                 "left shift", "right shift")},
    ("game/states/game_over_state.py", "ENTER"): "a key legend in the hint (UI-014.D16)",
    ("game/states/game_over_state.py", "ESC"): "a key legend in the hint (UI-014.D16)",
    ("game/states/victory_state.py", "ENTER"): "a key legend in the hint (UI-014.D16)",
    ("game/states/victory_state.py", "ESC"): "a key legend in the hint (UI-014.D16)",
    # Roman numerals are the same in every language.
    **{("progression/blessings/catalog.py", n): "a roman numeral"
       for n in ("II", "III", "IV", "VI", "VII", "VIII", "IX")},
    # Loading steps: yielded to pace the work, never drawn (the label is a key).
    ("game/states/loading_state.py", "warming the view {} of {}"): "a loading step, not drawn",
    ("game/states/loading_state.py", "warming the animations"): "a loading step, not drawn",
    ("game/states/loading_state.py", "PrebuiltWorld"): "a type name in a comparison",
    ("game/states/loading_state.py", "game_map nav"): "a profiling label, not drawn",
    # The element budget's and visuals' status lines are developer overlays (D6).
    ("game/states/playing/visual/elements/budget.py", "{}/{} used, {} refused"):
        "the developer overlay's budget line (D6)",
    ("game/states/playing/visual/elements/__init__.py", "{} drawn  {}"):
        "the developer overlay's element line (D6)",
}


def _docstrings(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                out.add(id(body[0].value))
    return out


def _call_name(f) -> str:
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")


def _looked_up_names(loop) -> bool:
    """A `for name in ("A", "B"):` whose loop variable is only ever an argument
    of a name lookup (`getattr(k32, name)`): the literals are names, as a
    constant passed straight to `getattr` is (SYS-011's ctypes prototypes)."""
    if not (isinstance(loop.target, ast.Name) and isinstance(loop.iter, (ast.Tuple, ast.List))
            and all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                    for e in loop.iter.elts)):
        return False
    var = loop.target.id
    uses, lookups = set(), set()
    for stmt in loop.body:
        for n in ast.walk(stmt):
            if isinstance(n, ast.Name) and n.id == var and isinstance(n.ctx, ast.Load):
                uses.add(id(n))
            elif isinstance(n, ast.Call) and _call_name(n.func) in NAME_ARGS:
                lookups.update(id(a) for a in n.args if isinstance(a, ast.Name) and a.id == var)
    return bool(uses) and uses == lookups


def _text(node) -> str:
    """A literal's text; an f-string's literal parts with `{}` holes."""
    if isinstance(node, ast.JoinedStr):
        return "".join(p.value if isinstance(p, ast.Constant) else "{}" for p in node.values)
    return node.value


def stray_literals(source: str) -> list[tuple[int, str]]:
    """`[(line, text)]` of the literals in `source` that no rule excuses."""
    tree = ast.parse(source)
    skip = _docstrings(tree)

    def skip_all(node):
        skip.update(id(n) for n in ast.walk(node))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Raise, ast.Assert)):
            skip_all(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                node.name in ("__repr__", "__str__"):
            skip_all(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                skip_all(node.returns)                    # a string annotation
            for a in node.args.args + node.args.kwonlyargs:
                if a.annotation is not None:
                    skip_all(a.annotation)
        elif isinstance(node, ast.AnnAssign):
            skip_all(node.annotation)
        elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in ("__all__", "_fields_") for t in node.targets):
            skip_all(node)
        elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Attribute) and t.attr in ("__qualname__", "__name__")
                for t in node.targets):
            skip_all(node.value)                          # a name for tracebacks
        elif isinstance(node, ast.ClassDef) and any(
                isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_fields_"
                                                  for t in s.targets) for s in node.body):
            skip_all(node)                                # a ctypes structure
        elif isinstance(node, ast.For) and _looked_up_names(node):
            skip_all(node.iter)
        elif isinstance(node, ast.Call):
            f = node.func
            name = _call_name(f)
            owner = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else ""
            # The receiver's own name, `self.log` included: a `toast.warning(...)`
            # is not a log call.
            receiver = (f.value.attr if isinstance(f, ast.Attribute)
                        and isinstance(f.value, ast.Attribute) else owner)
            if (name in LOG_METHODS and receiver in LOGGERS) or owner == "warnings":
                skip_all(node)
            elif owner == "locale" and name in LOCALE_FUNCS and node.args:
                skip_all(node.args[0])
            elif owner == "re" and node.args:
                skip_all(node.args[0])
            elif name in NAME_ARGS:
                for a in node.args:                       # attribute, library, registry names
                    if isinstance(a, ast.Constant):
                        skip.add(id(a))
    out = []
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.JoinedStr) or (isinstance(node, ast.Constant)
                                               and isinstance(node.value, str)):
            if isinstance(node, ast.Constant) and any(
                    id(node) in {id(v) for v in j.values}
                    for j in ast.walk(tree) if isinstance(j, ast.JoinedStr)):
                continue                                  # a part of an f-string: judged whole
            text = _text(node)
            if WORDS.search(text) and not IDENT.match(text) and not CONSTANT.match(text):
                out.append((node.lineno, text))
    return out


def scan():
    found = []
    for d in DIRS:
        for path in sorted((ROOT / d).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if DEV.search(rel):
                continue
            for line, text in stray_literals(path.read_text(encoding="utf-8")):
                found.append((rel, line, text))
    return found


class NoStrayEnglishTests(unittest.TestCase):
    def test_no_player_facing_literal_is_english(self):
        stray = [f"{rel}:{line}  {text!r}" for rel, line, text in scan()
                 if (rel, text) not in ALLOWED]
        self.assertEqual(stray, [], "\n" + "\n".join(stray) +
                         "\n-> a locale key, or an ALLOWED entry with its reason")

    def test_every_allowed_entry_still_exists(self):
        found = {(rel, text) for rel, _line, text in scan()}
        self.assertEqual(sorted(set(ALLOWED) - found), [])

    def test_the_scan_sees_a_stray_literal(self):
        """The scan is not vacuous: a drawn English literal is caught, a
        locale key and a docstring are not."""
        src = ('"""Doc."""\n'
               'def draw(font, locale) -> "Surface":\n'
               '    font.render("Game Over", True, (1, 1, 1))\n'
               '    font.render(locale.t("end.game_over"), True, (1, 1, 1))\n'
               '    font.render(f"{3} more items", True, (1, 1, 1))\n'
               '    font.render(f"status.{3}", True, (1, 1, 1))\n'
               '    getattr(font, "OVER", None)\n'
               '    environ["SDL_RENDER_SCALE_QUALITY"] = "1"\n'
               '    log.warning("font missing, using %s", 3)\n'
               '    self.log.info("run started")\n'
               '    toast.warning("Low HP")\n'
               '    font.render("loading...", True, (1, 1, 1))\n'
               '    font.render("press any key", True, (1, 1, 1))\n'
               '    font.render(card.text("Press start"), True, (1, 1, 1))\n'
               '    for n in ("SetProcessInformation", "GetProcessInformation"):\n'
               '        getattr(font, n).restype = None\n'
               '    for n in ("Resume Game", "Quit Game"):\n'
               '        getattr(font, n)\n'
               '        font.render(n, True, (1, 1, 1))\n')
        got = sorted(t for _l, t in stray_literals(src))
        self.assertEqual(got, sorted(["Game Over", "{} more items", "Low HP", "loading...",
                                      "press any key", "Press start",
                                      "Resume Game", "Quit Game"]))


if __name__ == "__main__":
    unittest.main()
