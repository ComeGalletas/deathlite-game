"""Which pytest tier each test needs, read from its source, against the tier
`tests/conftest.py` gives it.

The tiers (`pytest.ini`) are assigned by path, so a new module lands in `unit`
unless someone remembers to list it. `unit` is the tier run on every save and
promises "nothing generated; no Game booted"; a module that builds a real
`Game` there quietly makes every save slower (TST-006: `test_run_hints.py` and
`test_key_marker.py` each booted a run and generated seed 1234 inside `unit`).

This reads every `tests/**/test_*.py` with `ast`, follows the calls each test
makes -- into its own module's helpers, `self.`/`cls.` methods, base classes,
and any in-repo module it imports (`tests.boot`, `tests.worlds`, `tools.*`,
`game.*`, `world.*`) -- and records what it reaches:

- **integration**: constructing `Game`, `PlayingState` or `LoadingState`.
- **world**: `generate_world`, `generate_world_steps`, or a `GameMap` handed a
  seed (`GameMap()` and `GameMap(seed=None)` are one hand-built room, and
  `GameMap(layout=...)` takes a layout built elsewhere, which is where the
  cost is counted).

A test needs the highest tier any of these reaches from the test method, its
class's `setUp`/`setUpClass` (and friends, through the base classes), the class
body, or the module body and `setUpModule`. It is *under-tiered* when conftest
gives it less. Over-tiering (a pure test listed in `integration`) only costs
the fast tier some coverage and is reported separately.

A Python child process (`subprocess.run/Popen/...`) is read too: the code of a
`-c` argument, the module of `-m`, or the script a path names, when the
argument is a literal, an f-string, `os.path.join` of literals, or a module
constant built from those. A child the reader cannot resolve counts as
`integration`, because a fresh interpreter is never cheap and usually boots.

What the reading cannot see (TST-006 critic pass; none of these occur in the
suite today, and `tier_trace.py` is the runtime cross-check):

- a call through an object it cannot type: a helper instance's own method
  (`Harness().boot()`, `self.h.boot()`), `game.state_machine.change(...)`,
  a factory passed in as an argument;
- an alias made by assignment (`G = Game`, a class attribute
  `factory = Game`), `functools.partial(Game)`, `getattr`/`importlib`;
- a base `setUp` that calls a method only the subclass defines;
- a boot inside a test decorator;
- `GameMap(**kwargs)` (read as unseeded);
- two different imports under one local name in one module (the last one
  read wins).

From the command line::

    python -m tools.verification.tier_audit            # under-tiered tests, with the call chain
    python -m tools.verification.tier_audit --over     # also tests listed above what they need

Exit status is 1 when anything is under-tiered.
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RANK = {"unit": 0, "world": 1, "integration": 2, "sweep": 3}

# Constructing any of these boots a real game (a window, an asset load, and for
# the two states a world build). Keyed by where the class is *defined*, so an
# alias or a re-export resolves to the same entry.
BOOT = {
    ("game.game", "Game"),
    ("game.states.playing.core.state", "PlayingState"),
    ("game.states.loading_state", "LoadingState"),
}
# Calling any of these generates a height-map world.
GENERATE = {
    ("world.gen", "generate_world"),
    ("world.gen", "generate_world_steps"),
}
# Generates only when handed a seed (see `GameMap.__init__`).
GAME_MAP = ("world.map", "GameMap")

_FIXTURES = ("setUp", "tearDown", "setUpClass", "tearDownClass",
             "asyncSetUp", "asyncTearDown")
_MODULE_FIXTURES = ("setUpModule", "tearDownModule")


@dataclass(frozen=True)
class Need:
    """The tier something needs, and the call chain that decided it."""
    tier: str = "unit"
    chain: tuple = ()

    def via(self, step: str) -> "Need":
        return Need(self.tier, (step,) + self.chain) if self.chain else self

    def __or__(self, other: "Need") -> "Need":
        return other if RANK[other.tier] > RANK[self.tier] else self


NOTHING = Need()


@dataclass
class Module:
    name: str
    path: Path
    tree: ast.Module
    functions: dict = field(default_factory=dict)
    classes: dict = field(default_factory=dict)
    # local name -> (module, attr); attr None when the name is the module itself
    imports: dict = field(default_factory=dict)


class Index:
    """Parsed in-repo modules, loaded on first use, and the call resolver."""

    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self._modules: dict = {}
        self._needs: dict = {}
        self._open: set = set()     # keys being evaluated right now
        self._hits: list = []       # per open body: open keys it ran into

    # -- modules ------------------------------------------------------------

    def module(self, name: str):
        if name in self._modules:
            return self._modules[name]
        rel = Path(*name.split("."))
        path = next((p for p in (self.root / rel.with_suffix(".py"),
                                 self.root / rel / "__init__.py") if p.is_file()),
                    None)
        mod = self._load(name, path) if path is not None else None
        self._modules[name] = mod
        return mod

    def _load(self, name: str, path: Path) -> Module:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        return self._index(Module(name, path, tree))

    def _index(self, mod: Module) -> Module:
        name, path, tree = mod.name, mod.path, mod.tree
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                mod.functions[node.name] = node
            elif isinstance(node, ast.ClassDef):
                mod.classes[node.name] = node
        # Imports anywhere in the module: tests import inside setUpClass.
        package = name if path.name == "__init__.py" else name.rpartition(".")[0]
        for node in _statements(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname:
                        mod.imports[a.asname] = (a.name, None)
                    else:
                        top = a.name.split(".")[0]
                        mod.imports[top] = (top, None)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    parts = package.split(".")
                    parts = parts[:len(parts) - node.level + 1]
                    base = ".".join(p for p in parts + [base] if p)
                for a in node.names:
                    mod.imports[a.asname or a.name] = (base, a.name)
        return mod

    def symbol(self, modname: str, attr, seen=()):
        """What `attr` of module `modname` is: ("module", name),
        ("function", module, name), ("class", module, name), or None when it
        is not in the repo."""
        if attr is None:
            return ("module", modname) if self.module(modname) else None
        if (modname, attr) in seen:
            return None
        mod = self.module(modname)
        if mod is None:
            return None
        if attr in mod.functions:
            return ("function", modname, attr)
        if attr in mod.classes:
            return ("class", modname, attr)
        if attr in mod.imports:                       # a re-export
            src, name = mod.imports[attr]
            return self.symbol(src, name, seen + ((modname, attr),))
        if self.module(f"{modname}.{attr}"):          # a submodule
            return ("module", f"{modname}.{attr}")
        return None

    def name(self, mod: Module, ident: str):
        """Resolve a bare name used in `mod`."""
        if ident in mod.functions:
            return ("function", mod.name, ident)
        if ident in mod.classes:
            return ("class", mod.name, ident)
        if ident in mod.imports:
            return self.symbol(*mod.imports[ident])
        return None

    # -- classes ------------------------------------------------------------

    def bases(self, modname: str, cls: str) -> list:
        """The in-repo base classes of `cls`, as (module, name)."""
        mod = self.module(modname)
        out = []
        for b in mod.classes[cls].bases:
            target = self._expr(mod, b)
            if target and target[0] == "class":
                out.append(target[1:])
        return out

    def mro(self, modname: str, cls: str) -> list:
        order, todo = [], [(modname, cls)]
        while todo:
            c = todo.pop(0)
            if c in order:
                continue
            order.append(c)
            todo.extend(self.bases(*c))
        return order

    def method(self, modname: str, cls: str, name: str):
        for m, c in self.mro(modname, cls):
            for node in self.module(m).classes[c].body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and node.name == name:
                    return (m, c, name)
        return None

    def is_testcase(self, modname: str, cls: str) -> bool:
        """Whether unittest (and so pytest) collects this class."""
        for m, c in self.mro(modname, cls):
            mod = self.module(m)
            for b in mod.classes[c].bases:
                dotted = _dotted(b)
                if dotted is None:
                    continue
                head, _, tail = dotted.rpartition(".")
                if tail.endswith("TestCase"):
                    src = mod.imports.get(head or tail)
                    if src and src[0] == "unittest":
                        return True
        return False

    def _expr(self, mod: Module, node):
        """Resolve a Name/Attribute expression used in `mod`."""
        if isinstance(node, ast.Name):
            return self.name(mod, node.id)
        if isinstance(node, ast.Attribute):
            inner = self._expr(mod, node.value)
            if inner and inner[0] == "module":
                return self.symbol(inner[1], node.attr)
        return None

    # -- what a body reaches -----------------------------------------------

    def need_of_body(self, mod: Module, nodes, owner=None, key=None) -> Need:
        """The tier the statements `nodes` need; `owner` is the (module, class)
        they are a method of, for `self.`/`cls.`/`super()` calls.

        Recursion: a body that calls back into one still being read gets
        NOTHING for that call. Its answer is then partial -- it depends on
        where the cycle was entered -- so it is not cached until every body
        of the cycle has closed; the outermost one caches the whole answer."""
        if key is not None:
            if key in self._needs:
                return self._needs[key]
            if key in self._open:
                if self._hits:
                    self._hits[-1].add(key)
                return NOTHING
            self._open.add(key)
        self._hits.append(set())
        need = NOTHING
        for stmt in nodes:
            for node in ast.walk(stmt):
                if isinstance(node, ast.Call):
                    need = need | self._call(mod, node, owner)
                    if need.tier == "integration":
                        break
            if need.tier == "integration":
                break
        hits = self._hits.pop()
        hits.discard(key)
        if key is not None:
            self._open.discard(key)
        if hits:                                      # still inside a cycle
            if self._hits:
                self._hits[-1] |= hits
        elif key is not None:
            self._needs[key] = need
        return need

    def module_body(self, modname: str) -> Need:
        """What importing (or running) a module does: its statements outside
        any `def` or `class`, which include an `if __name__ == "__main__"`."""
        mod = self.module(modname)
        body = [s for s in mod.tree.body
                if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef))]
        return self.need_of_body(mod, body, key=("body", modname))

    def function(self, modname: str, name: str) -> Need:
        mod = self.module(modname)
        return self.need_of_body(mod, mod.functions[name].body,
                                 key=("f", modname, name))

    def bound(self, modname: str, cls: str, name: str) -> Need:
        mod = self.module(modname)
        node = next(n for n in mod.classes[cls].body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name == name)
        return self.need_of_body(mod, node.body, owner=(modname, cls),
                                 key=("m", modname, cls, name))

    def construct(self, modname: str, cls: str) -> Need:
        """What `cls(...)` reaches: a primitive anywhere in its MRO, or its
        `__init__` / `__post_init__`."""
        for m, c in self.mro(modname, cls):
            if (m, c) in BOOT:
                return Need("integration", (f"{c}(",))
        need = NOTHING
        for hook in ("__init__", "__post_init__"):
            found = self.method(modname, cls, hook)
            if found:
                need = need | self.bound(*found).via(f"{found[1]}.{hook}")
        return need

    def _child(self, mod: Module, call: ast.Call) -> Need:
        """What a `subprocess` child runs: `-c` code, a `-m` module, or a
        script path; `integration` when it cannot be read."""
        unread = Need("integration", ("a child process the reader cannot read",))
        argv = _resolve(mod, call.args[0]) if call.args else None
        if not isinstance(argv, (ast.List, ast.Tuple)):
            return unread
        texts = [_text(mod, a) for a in argv.elts]
        for flag, value in zip(texts, texts[1:]):
            if flag == "-c":
                if value is None:
                    return unread
                try:
                    tree = ast.parse(value)
                except SyntaxError:
                    return unread
                child = self._index(Module(f"{mod.name}.<child>", mod.path, tree))
                return self.need_of_body(child, tree.body).via("child -c")
            if flag == "-m":
                if value is None or self.module(value) is None:
                    return unread
                return self.module_body(value).via(f"child -m {value}")
        for value in texts:
            if value and value.endswith(".py"):
                rel = Path(value)
                if rel.is_absolute() or not (self.root / rel).is_file():
                    return unread
                name = ".".join(rel.with_suffix("").parts)
                if self.module(name) is None:
                    return unread
                return self.module_body(name).via(f"child {rel.as_posix()}")
        if any(t is None for t in texts):
            return unread
        return NOTHING                                # not a Python program

    def _call(self, mod: Module, call: ast.Call, owner) -> Need:
        func = call.func
        if _dotted(func) in _SPAWN or (
                isinstance(func, ast.Name)
                and mod.imports.get(func.id, (None,))[0] == "subprocess"
                and func.id in {n.split(".")[1] for n in _SPAWN}):
            return self._child(mod, call)
        if isinstance(func, ast.Attribute) and owner is not None:
            recv = func.value
            if isinstance(recv, ast.Name) and recv.id in ("self", "cls"):
                found = self.method(*owner, func.attr)
                return self.bound(*found).via(f"{found[1]}.{found[2]}") \
                    if found else NOTHING
            if isinstance(recv, ast.Call) and isinstance(recv.func, ast.Name) \
                    and recv.func.id == "super":
                for base in self.mro(*owner)[1:]:
                    found = self.method(*base, func.attr)
                    if found:
                        return self.bound(*found).via(f"{found[1]}.{found[2]}")
                return NOTHING
        if isinstance(func, ast.Attribute):
            recv = self._expr(mod, func.value)
            if recv and recv[0] == "class":           # Class.method(...)
                found = self.method(recv[1], recv[2], func.attr)
                return self.bound(*found).via(f"{found[1]}.{found[2]}") \
                    if found else NOTHING
        target = self._expr(mod, func)
        if target is None:
            return NOTHING
        kind, where, what = target[0], target[1], target[-1]
        if kind == "function":
            if (where, what) in GENERATE:
                return Need("world", (f"{what}(",))
            return self.function(where, what).via(f"{where}.{what}")
        if kind == "class":
            if (where, what) == GAME_MAP:
                return Need("world", ("GameMap(seed)",)) if _seeded(call) \
                    else NOTHING
            return self.construct(where, what).via(f"{where}.{what}")
        return NOTHING


def _statements(node):
    """Every statement under `node`, without descending into expressions --
    an import is always a statement, and this is a fraction of `ast.walk`."""
    for name in ("body", "orelse", "finalbody", "handlers", "cases"):
        for child in getattr(node, name, ()) or ():
            if isinstance(child, list):              # a match case's body
                continue
            yield child
            yield from _statements(child)


_SPAWN = {"subprocess.run", "subprocess.Popen", "subprocess.call",
          "subprocess.check_call", "subprocess.check_output"}


def _resolve(mod: Module, node):
    """A bare name bound once at module level stands for its value."""
    seen = set()
    while isinstance(node, ast.Name) and node.id not in seen:
        seen.add(node.id)
        found = [s.value for s in mod.tree.body if isinstance(s, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == node.id
                         for t in s.targets)]
        if len(found) != 1:
            return node
        node = found[0]
    return node


def _text(mod: Module, node):
    """The string an argv element is, as far as it can be read: literals,
    f-strings (a placeholder for each value), `+`, `os.path.join`, module
    constants. None when it cannot be read."""
    node = _resolve(mod, node)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "0"
                       for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _text(mod, node.left), _text(mod, node.right)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.Call) and _dotted(node.func) == "os.path.join":
        parts = [_text(mod, a) for a in node.args]
        return None if None in parts else "/".join(parts)
    if _dotted(node) == "sys.executable":
        return "<python>"
    return None


def _seeded(call: ast.Call) -> bool:
    """Whether a `GameMap(...)` call hands it a seed that is not `None`."""
    args = list(call.args[:1])
    args += [k.value for k in call.keywords if k.arg == "seed"]
    return any(not (isinstance(a, ast.Constant) and a.value is None) for a in args)


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr}" if head else None
    return None


# -- the suite ---------------------------------------------------------------

@dataclass(frozen=True)
class Test:
    nodeid: str          # as pytest prints it: tests/a/test_b.py::Class::test_x
    need: Need
    tier: str            # what conftest gives it


def tests(index: Index, tier_of, paths=None):
    """Every collected test under `index.root/tests` -- unittest methods and
    module-level `test_*` functions, which pytest collects too -- with the
    tier it needs and the tier `tier_of(nodeid)` gives it."""
    root = index.root
    paths = sorted((root / "tests").rglob("test_*.py")) if paths is None else paths
    for path in paths:
        rel = path.relative_to(root).as_posix()
        modname = rel[:-3].replace("/", ".")
        mod = index.module(modname)
        # The module body runs at import; setUpModule before any class.
        need_mod = index.module_body(modname).via(f"{rel} (module body)")
        for fx in _MODULE_FIXTURES:
            if fx in mod.functions:
                need_mod = need_mod | index.function(modname, fx).via(fx)
        for fname in mod.functions:
            if fname.startswith("test"):
                need = need_mod | index.function(modname, fname).via(fname)
                nodeid = f"{rel}::{fname}"
                yield Test(nodeid, need, tier_of(nodeid))
        for cname in mod.classes:
            if not index.is_testcase(modname, cname):
                continue
            need_cls = need_mod
            for m, c in index.mro(modname, cname):
                cmod = index.module(m)
                cbody = [s for s in cmod.classes[c].body
                         if not isinstance(s, (ast.FunctionDef,
                                               ast.AsyncFunctionDef))]
                need_cls = need_cls | index.need_of_body(
                    cmod, cbody, key=("cbody", m, c)).via(f"{c} (class body)")
            for fx in _FIXTURES:
                found = index.method(modname, cname, fx)
                if found:
                    need_cls = need_cls | index.bound(*found) \
                        .via(f"{found[1]}.{fx}")
            names = []
            for m, c in index.mro(modname, cname):
                for n in index.module(m).classes[c].body:
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                            and n.name.startswith("test") and n.name not in names:
                        names.append(n.name)
            for name in names:
                found = index.method(modname, cname, name)
                need = need_cls | index.bound(*found).via(f"{found[1]}.{name}")
                nodeid = f"{rel}::{cname}::{name}"
                yield Test(nodeid, need, tier_of(nodeid))


def under(results):
    return [t for t in results if RANK[t.tier] < RANK[t.need.tier]]


def over(results):
    return [t for t in results
            if t.tier in ("world", "integration")
            and RANK[t.tier] > RANK[t.need.tier]]


def _split(nodeid: str):
    """(module path, class or None) of a nodeid."""
    parts = nodeid.split("::")
    return parts[0], (parts[1] if len(parts) == 3 else None)


def grouped(selected, everything, whole_classes=True) -> dict:
    """{(tier given, tier needed): {prefix: chain}} for the `selected` tests,
    at the granularity conftest registers at: the module when *every* test in
    it (from `everything`) shares the pair, otherwise the class.

    With `whole_classes` (moving tests *up*) a class that mixes pure and
    booting tests goes whole to the highest tier any test in it needs, not
    method by method (TST-006.D1). Without it (moving tests *down*, `--over`)
    a class is named only when every test in it shares the pair; otherwise
    each test is, since the rest of the class needs the tier it is in."""
    def pairs(ts):
        return {(t.tier, t.need.tier) for t in ts}

    by_mod: dict = {}
    for t in everything:
        path, cls = _split(t.nodeid)
        by_mod.setdefault(path, {}).setdefault(cls, []).append(t)
    out: dict = {}
    for t in selected:
        path, cls = _split(t.nodeid)
        pair = (t.tier, t.need.tier)
        if pairs(u for ts in by_mod[path].values() for u in ts) == {pair}:
            prefix = path
        elif cls is not None and (whole_classes
                                  or pairs(by_mod[path][cls]) == {pair}):
            prefix = f"{path}::{cls}"
        else:
            prefix = t.nodeid
        out.setdefault(pair, {}).setdefault(prefix, t.need.chain)
    return out


def _report(title: str, selected, everything, whole_classes=True) -> None:
    groups = grouped(selected, everything, whole_classes)
    for (given, needs), prefixes in sorted(groups.items()):
        print(f"{title}: in `{given}`, needs `{needs}` ({len(prefixes)})")
        for prefix, chain in sorted(prefixes.items()):
            print(f"  {prefix}")
            print(f"      via {' -> '.join(chain)}" if chain
                  else "      reaches nothing that boots or generates")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    sys.path.insert(0, str(ROOT))
    from tests.conftest import tier
    results = list(tests(Index(ROOT), tier))
    bad = under(results)
    print(f"{len(results)} tests read; {len(bad)} under-tiered")
    _report("UNDER", bad, results)
    if "--over" in argv:
        _report("OVER", over(results), results, whole_classes=False)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
