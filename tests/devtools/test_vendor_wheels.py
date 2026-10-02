"""`dist/web/vendor_wheels.py`: the wheels a static server needs (BLD-006).

No network: a fake CDN is a temporary folder reached through `file://` URLs,
which `urllib` opens like any other, and a guard fails any other URL. The
fixture index is the real `index-0.9.3-cp312.json` entry for pygame, trimmed,
so the resolution test names exactly the file the static server 404'd on
(2026-10-02). `PEP0723_SHAPE` is the part of pygbag 0.9.3's
`support/cross/aio/pep0723.py` the helper reads, as it is there (the block
reader verbatim), and `PAGE` the two lines of pygbag's generated index.html
it reads.
"""
import http.client
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "dist" / "web"

# Loaded by path (dist/web is not a package); registered first, because a
# dataclass looks its module up in sys.modules.
_spec = importlib.util.spec_from_file_location("vendor_wheels", WEB / "vendor_wheels.py")
vw = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("vendor_wheels", vw)
_spec.loader.exec_module(vw)

PYGAME_PATH = "cp312/pygame_ce-2.5.7-<abi>-<abi>-<api>.whl"
STATIC_404 = "cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl"
BIDI = "pkg/python_bidi-0.4.2-py2.py3-none-any.whl"
MAPPING = {"pygame_ce": "pygame", "pillow": "PIL"}

PEP0723_SHAPE = '''
class Config:
    READ_723 = True
    PKG_BASE_DEFAULT = "https://pygame-web.github.io/cdn/"
    mapping = {
        "pygame_ce": "pygame",
        "pillow": "PIL",
    }

def read_dependency_block_723(code):
    global HISTORY, hint_failed
    # Skip lines until we reach a dependency block (OR EOF).
    has_block = False

    content = []
    for line in code.split("\\n"):
        if not has_block:
            # compat with draft PEP for pyproject
            if line.rstrip() in ["# /// pyproject", "# /// script"]:
                has_block = True
            continue

        if not line.startswith("#"):
            break

        if line.strip() == "# ///":
            break

        content.append(line[2:])

    struct = tomllib.loads("\\n".join(content))
    if struct:
        print("# 109\\n",json.dumps(struct, sort_keys=True, indent=4))

    # compat with draft PEP
    if struct.get("project", None):
        struct = struct.get("project", {"dependencies": []})
    deps = struct.get("dependencies", [])
    for dep in deps:
        yield dep

async def async_repos():
    abitag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    for repo in Config.PKG_INDEXES:
        merged = {}
        for pygver in ('0.9.3', ):
            idx = f"{repo}index-{pygver}-{abitag}.json"

    if not aio.cross.simulator:
        rewritecdn = ""
        import platform

        if os.environ.get("PYGPI", ""):
            rewritecdn = os.environ.get("PYGPI")
        elif platform.window.location.href.startswith("http://localhost:8"):
            rewritecdn = "http://localhost:8000/cdn/"
'''

PAGE = ('<html lang="en-us"><script src="https://pygame-web.github.io/cdn/0.9.3/pythons.js" '
        'type=module id="site" data-python="python3.12" data-os="vtx,snd,gui" async defer>\n'
        '    cdn : "https://pygame-web.github.io/cdn/0.9.3/",\n')

READ_BLOCK = vw.parse_pep0723(PEP0723_SHAPE)["read_block"]


def _wheel_bytes(tag="x", requires=(), metadata=True) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("pkg/__init__.py", f"# payload {tag} " + "x" * 64 + "\n")
        if metadata:
            lines = ["Metadata-Version: 2.1", "Name: pkg"]
            lines += [f"Requires-Dist: {r}" for r in requires]
            zf.writestr("pkg-1.0.dist-info/METADATA", "\n".join(lines) + "\n")
    return buf.getvalue()


def _corrupt(data: bytes, marker: bytes) -> bytes:
    """`data` with one byte flipped inside the stored member that holds
    `marker`: the directory still reads, the member fails its CRC."""
    at = data.index(marker) + len(marker) // 2
    return data[:at] + bytes([data[at] ^ 0xFF]) + data[at + 1:]


def _central(data: bytes, offset: int, value: int) -> bytes:
    """`data` with the 2-byte field at `offset` of its first central
    directory entry set to `value` (8: flags, 10: compression method)."""
    at = data.index(b"PK\x01\x02") + offset
    return data[:at] + value.to_bytes(2, "little") + data[at + 2:]


def _damaged_bodies(good: bytes) -> dict:
    """Every kind of wheel damage the helper must refuse, by name."""
    return {
        "truncated": good[: len(good) // 2],
        "member CRC": _corrupt(good, b"# payload"),
        "metadata CRC": _corrupt(good, b"Metadata-Version"),
        "directory": good[:good.rindex(b"PK\x01\x02")] + b"PK\x01\x02junk"
        + good[good.rindex(b"PK\x05\x06"):],
        "encryption flag": _central(good, 8, 0x0001),       # RuntimeError in zipfile
        "compression method": _central(good, 10, 99),       # NotImplementedError
    }


def _runtime(base="x/", **kw):
    fields = {"abi": "cp312", "runtime_base": base + "0.9.3/", "pkg_base": base,
              "index_versions": ("0.9.3",), "mapping": MAPPING, "read_block": READ_BLOCK,
              "local_base": "http://localhost:8000/cdn/", "local_prefix": "http://localhost:8"}
    return vw.Runtime(**{**fields, **kw})


class FakeCdn:
    """A CDN folder (index, runtime data file, pygame wheel) reached through
    `file://`, plus an empty work area. `urls` records every request,
    relative to the CDN, HEAD requests marked; any URL that is not `file:`
    fails the test."""

    def __init__(self, test: unittest.TestCase):
        tmp = Path(test.enterContext(tempfile.TemporaryDirectory()))
        self.root = tmp / "cdn"
        self.base = self.root.as_uri() + "/"
        self.out = tmp / "out"
        self.cache = tmp / "cache"
        self.entry = tmp / "main.py"
        self.entry.write_text("import asyncio\nimport pygame\nfrom game.game import Game\n",
                              encoding="utf-8")
        self.index = {
            "-CDN-": self.base,
            "pygame": PYGAME_PATH,
            "PIL": "cp312/pillow-11.3.0-<abi>-<abi>-<api>.whl",
            "bidi": BIDI,
        }
        self.write_index()
        self.data = self.root / "0.9.3" / "cpython312" / "main.data"
        self.data.parent.mkdir(parents=True)
        self.data.write_bytes(b"\x00junk HOST_GNU_TYPE='wasm32-bi-emscripten' more\x00")
        self.wheel = self.add_wheel(STATIC_404)
        self.rt = _runtime(self.base)
        self.urls: list[str] = []
        self.log: list[str] = []
        self.real_urlopen = vw.urllib.request.urlopen

        def file_only(req, *a, **kw):
            url = getattr(req, "full_url", str(req))
            if not url.startswith("file:"):
                raise AssertionError(f"test reached the network: {url}")
            head = "HEAD " if getattr(req, "get_method", lambda: "GET")() == "HEAD" else ""
            self.urls.append(head + url.removeprefix(self.base))
            return self.real_urlopen(req, *a, **kw)

        test.enterContext(mock.patch.object(vw.urllib.request, "urlopen", file_only))

    def add_wheel(self, path, root=None, **kw) -> Path:
        dest = (root or self.root) / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_wheel_bytes(**kw))
        return dest

    def write_index(self):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "index-0.9.3-cp312.json").write_text(json.dumps(self.index), encoding="utf-8")

    def vendor(self):
        self.urls.clear()
        with redirect_stdout(io.StringIO()):
            return vw.vendor(self.entry, self.out, self.cache, rt=self.rt, log=self.log.append)

    def go_offline(self):
        for p in self.root.rglob("*"):
            if p.is_file():
                p.unlink()

    def leftovers(self):
        """Partial files anywhere, and any wheel in the cache or `out/`."""
        found = []
        for top in (self.cache, self.out):
            if top.exists():
                found += [p for p in top.rglob("*") if p.is_file() and
                          (p.name.endswith(".part") or p.suffix == ".whl")]
        return found


class Pep0723Tests(unittest.TestCase):
    """The runtime settings come from pygbag's own source, so an upgrade
    moves them; a source that no longer has them stops the build."""

    def test_the_settings_are_read_from_the_source(self):
        cfg = vw.parse_pep0723(PEP0723_SHAPE)
        self.assertEqual(cfg["PKG_BASE_DEFAULT"], "https://pygame-web.github.io/cdn/")
        self.assertEqual(cfg["mapping"], MAPPING)
        self.assertEqual(cfg["versions"], ("0.9.3",))
        self.assertEqual(cfg["local_base"], "http://localhost:8000/cdn/")
        self.assertEqual(cfg["local_prefix"], "http://localhost:8")
        self.assertTrue(callable(cfg["read_block"]))

    def test_every_index_version_the_runtime_loops_over_is_read(self):
        src = PEP0723_SHAPE.replace("('0.9.3', )", "('0.9.3', '0.9.4')")
        self.assertEqual(vw.parse_pep0723(src)["versions"], ("0.9.3", "0.9.4"))

    def test_a_moved_local_base_moves_the_vendored_folder(self):
        """`out/cdn/` is not assumed: it is where `rewritecdn` points."""
        src = PEP0723_SHAPE.replace('"http://localhost:8000/cdn/"', '"http://localhost:8000/wheels/"')
        rt = _runtime(local_base=vw.parse_pep0723(src)["local_base"])
        self.assertEqual(rt.local_folder, "wheels")

    def test_the_block_reader_is_pygbags_own_code(self):
        """A change to pygbag's reader changes what the helper reads."""
        src = PEP0723_SHAPE.replace('"# /// script"]', '"# /// script", "# /// deps"]')
        read = vw.parse_pep0723(src)["read_block"]
        self.assertEqual(read('# /// deps\n# dependencies = ["bidi"]\n# ///\n'), ["bidi"])
        self.assertEqual(READ_BLOCK('# /// deps\n# dependencies = ["bidi"]\n# ///\n'), [])

    def test_two_rewritecdn_branches_are_an_error_not_a_guess(self):
        src = PEP0723_SHAPE + (
            '\n        elif platform.window.location.href.startswith("http://127.0.0.1:8"):\n'
            '            rewritecdn = "http://127.0.0.1:8000/cdn/"\n')
        with self.assertRaises(vw.VendorError) as ctx:
            vw.parse_pep0723(src)
        self.assertIn("more than one branch", str(ctx.exception))

    def test_a_setting_that_is_no_longer_a_literal_is_an_error_naming_it(self):
        src = PEP0723_SHAPE.replace("for pygver in ('0.9.3', ):", "for pygver in VERSIONS:")
        with self.assertRaises(vw.VendorError) as ctx:
            vw.parse_pep0723(src)
        self.assertIn("versions", str(ctx.exception))

    def test_a_source_without_them_is_an_error_naming_what_is_gone(self):
        for old, new, key in (("PKG_BASE_DEFAULT", "PKG_BASE", "PKG_BASE_DEFAULT"),
                              ("rewritecdn = \"http", "rewrite = \"http", "local_base"),
                              (".startswith(", ".endswith(", "local_prefix"),
                              ("def read_dependency_block_723", "def read_block", "read_block")):
            with self.subTest(key), self.assertRaises(vw.VendorError) as ctx:
                vw.parse_pep0723(PEP0723_SHAPE.replace(old, new))
            self.assertIn(key, str(ctx.exception))


class PageTests(unittest.TestCase):
    """The browser's Python and runtime come from the page pygbag built, so a
    `--PYBUILD` or `--cdn` given to pygbag is followed."""

    def test_the_python_and_the_runtime_are_read_from_the_page(self):
        self.assertEqual(vw.parse_page(PAGE), ("cp312", "https://pygame-web.github.io/cdn/0.9.3/"))

    def test_another_python_or_cdn_is_followed(self):
        page = PAGE.replace("python3.12", "python3.13").replace(
            'cdn : "https://pygame-web.github.io/cdn/0.9.3/"', 'cdn : "https://mirror.example/x"')
        self.assertEqual(vw.parse_page(page), ("cp313", "https://mirror.example/x/"))

    def test_a_page_without_them_is_an_error(self):
        with self.assertRaises(vw.VendorError):
            vw.parse_page("<html></html>")

    def test_a_built_page_and_pygbag_source_make_the_runtime(self):
        """The generated page is not in the repo (it is build output), so
        this uses the two fields as pygbag 0.9.3 writes them (PAGE); a real
        build is the check against the real page."""
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (tmp / "index.html").write_text(PAGE, encoding="utf-8")
        rt = vw.runtime_for(tmp / "index.html", PEP0723_SHAPE)
        self.assertEqual((rt.abi, rt.local_folder), ("cp312", "cdn"))

    def test_running_before_the_page_exists_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(vw.VendorError) as ctx:
            vw.runtime_for(Path(tmp) / "index.html", PEP0723_SHAPE)
        self.assertIn("is missing: run this after pygbag built the page", str(ctx.exception))


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.rt = _runtime()

    def test_the_real_entry_resolves_to_the_wheel_the_static_server_404d_on(self):
        imports = vw.entry_imports(REPO / "main.py")
        self.assertIn("pygame", imports)
        self.assertEqual(vw.block_requests((REPO / "main.py").read_text(encoding="utf-8"),
                                           self.rt), ([], set()))
        index = {"-CDN-": "https://pygame-web.github.io/cdn/", "pygame": PYGAME_PATH}
        got = {n: vw.resolve(index, n, self.rt, "wasm32_bi_emscripten") for n in imports}
        self.assertEqual({n: p for n, p in got.items() if p}, {"pygame": STATIC_404})

    def test_the_tags_are_filled_in(self):
        rt = _runtime(abi="cp313")
        self.assertEqual(vw.resolve({"pygame": PYGAME_PATH}, "pygame", rt, "wasm64_x"),
                         "cp312/pygame_ce-2.5.7-cp313-cp313-wasm64_x.whl")

    def test_a_distribution_name_is_remapped_as_the_runtime_does(self):
        self.assertEqual(vw.remap("Pygame-CE", MAPPING), "pygame")
        self.assertEqual(vw.resolve({"pygame": PYGAME_PATH}, "pygame-ce", self.rt, "a"),
                         "cp312/pygame_ce-2.5.7-cp312-cp312-a.whl")

    def test_the_cdn_key_and_non_wheels_are_never_wheels(self):
        index = {"-CDN-": "https://x/", "data": "cp312/thing.tar"}
        self.assertIsNone(vw.resolve(index, "-CDN-", self.rt, "a"))
        self.assertIsNone(vw.resolve(index, "data", self.rt, "a"))

    def test_entry_imports_takes_top_level_names_as_pygbag_does(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / "main.py"
            entry.write_text("import os.path, pygame\nfrom PIL import Image\n"
                             "from . import local\nfrom .x import y\n"
                             "def f():\n    import bidi.algorithm\n", encoding="utf-8")
            self.assertEqual(vw.entry_imports(entry), {"os", "pygame", "PIL", "bidi", "x"})

    def test_requirements_the_runtime_skips_are_skipped(self):
        self.assertEqual(vw.requirement_name("numpy>=1.0"), "numpy")
        self.assertEqual(vw.requirement_name("typing-extensions ; python_version<'3.13'"),
                         "typing-extensions")
        self.assertIsNone(vw.requirement_name("pytest ; extra == 'test'"))
        self.assertIsNone(vw.requirement_name("requests[socks]>=2"))

    def test_both_block_kinds_are_read_as_the_runtime_reads_them(self):
        """`# /// script` and `# /// pyproject` with `[project]`; a `!name`
        excludes; an entry is the whole string, lower-cased, dashes as
        underscores (a version specifier stays on it, as in `parse_code`)."""
        script = ('# /// script\n# dependencies = [\n#   "Pygame-CE",\n#   "!numpy",\n'
                  '#   "bidi>=0.4",\n# ]\n# ///\nimport asyncio\n')
        pyproject = '# /// pyproject\n# [project]\n# dependencies = ["bidi"]\n# ///\n'
        self.assertEqual(vw.block_requests(script, self.rt),
                         (["pygame_ce", "bidi>=0.4"], {"numpy"}))
        self.assertEqual(vw.block_requests(pyproject, self.rt), (["bidi"], set()))
        self.assertEqual(vw.block_requests("import asyncio\n", self.rt), ([], set()))

    def test_a_block_that_cannot_be_read_is_an_error(self):
        """Not TOML, or TOML of a shape pygbag's reader trips on
        (`dependencies` not a list, `project` not a table)."""
        for block in ("# /// script\n# dependencies = [\n# ///\n",
                      "# /// script\n# dependencies = 5\n# ///\n",
                      '# /// pyproject\n# project = "x"\n# ///\n'):
            with self.subTest(block), self.assertRaises(vw.VendorError) as ctx:
                vw.block_requests(block, self.rt)
            self.assertIn("dependency block cannot be read", str(ctx.exception))


class VendorTests(unittest.TestCase):
    def setUp(self):
        self.cdn = FakeCdn(self)

    def test_the_wheel_lands_under_out_cdn_where_the_loader_asks(self):
        written = self.cdn.vendor()
        target = self.cdn.out / "cdn" / STATIC_404
        self.assertEqual(written, [target])
        self.assertEqual(target.read_bytes(), self.cdn.wheel.read_bytes())

    def test_the_folder_follows_the_runtimes_local_base(self):
        self.cdn.rt = _runtime(self.cdn.base, local_base="http://localhost:8000/wheels/")
        self.assertEqual(self.cdn.vendor(), [self.cdn.out / "wheels" / STATIC_404])

    def test_a_first_build_fetches_the_index_the_runtime_and_the_wheel(self):
        self.cdn.vendor()
        self.assertEqual(self.cdn.urls, ["index-0.9.3-cp312.json",
                                         "HEAD 0.9.3/cpython312/main.data",
                                         "0.9.3/cpython312/main.data", STATIC_404])

    def test_a_rebuild_fetches_only_the_index_and_checks_the_runtime(self):
        """The index is re-read on purpose (the browser reads the live one);
        the runtime is only stamped (HEAD); the wheel comes from the cache."""
        self.cdn.vendor()
        self.cdn.vendor()
        self.assertEqual(self.cdn.urls, ["index-0.9.3-cp312.json",
                                         "HEAD 0.9.3/cpython312/main.data"])

    def test_a_runtime_rebuilt_in_place_is_read_again(self):
        self.cdn.vendor()
        self.cdn.data.write_bytes(b"rebuilt, longer than before: wasm64-bi-emscripten\x00")
        self.cdn.rt = _runtime(self.cdn.base)
        self.cdn.index["pygame"] = "cp312/pygame_ce-2.5.7-<abi>-<abi>-<api>.whl"
        self.cdn.write_index()
        self.cdn.add_wheel("cp312/pygame_ce-2.5.7-cp312-cp312-wasm64_bi_emscripten.whl")
        written = self.cdn.vendor()
        self.assertEqual([p.name for p in written],
                         ["pygame_ce-2.5.7-cp312-cp312-wasm64_bi_emscripten.whl"])
        self.assertTrue(any("changed; reading its target again" in m for m in self.cdn.log))

    def test_the_runtime_data_file_is_not_kept_only_its_target(self):
        self.cdn.vendor()
        self.assertEqual(list(self.cdn.cache.glob("*.data")), [])
        tags = list(self.cdn.cache.glob("api-*.txt"))
        self.assertEqual([t.read_text().splitlines()[0] for t in tags], ["wasm32_bi_emscripten"])

    def test_an_unreadable_cached_target_is_read_again(self):
        self.cdn.vendor()
        tag_file = next(self.cdn.cache.glob("api-*.txt"))
        tag_file.write_bytes(b"\xff\xfe\x00garbage")
        self.cdn.vendor()
        self.assertIn("0.9.3/cpython312/main.data", self.cdn.urls)
        self.assertEqual(tag_file.read_text().splitlines()[0], "wasm32_bi_emscripten")

    def test_a_long_runtime_base_still_gives_a_short_cache_name(self):
        deep = self.cdn.root / ("d" * 120) / ("e" * 120)
        (deep / "cpython312").mkdir(parents=True)
        (deep / "cpython312" / "main.data").write_bytes(self.cdn.data.read_bytes())
        self.cdn.rt = _runtime(self.cdn.base, runtime_base=deep.as_uri() + "/")
        self.cdn.vendor()
        names = [p.name for p in self.cdn.cache.glob("api-*.txt")]
        self.assertEqual(len(names), 1)
        self.assertLess(len(names[0]), 40)

    def test_failed_nested_downloads_leave_no_folders(self):
        """A damaged body, a 404 and an over-long folder name, each at a
        path whose folders do not exist yet: the cache afterwards holds the
        index and the target and no folder at all."""
        cases = {"damaged": ("deep/er/x.whl", b"<html>nope</html>"),
                 "missing": ("deep/er/still/x.whl", None),
                 "over-long folder": ("ok/" + "f" * 300 + "/x.whl", None)}
        for what, (path, body) in cases.items():
            with self.subTest(what):
                self.cdn.index["pygame"] = path
                self.cdn.write_index()
                if body is not None:
                    (self.cdn.root / path).parent.mkdir(parents=True, exist_ok=True)
                    (self.cdn.root / path).write_bytes(body)
                with self.assertRaises(vw.VendorError):
                    self.cdn.vendor()
                self.assertEqual([p for p in self.cdn.cache.rglob("*") if p.is_dir()], [])
                self.assertEqual(self.cdn.leftovers(), [])

    def test_an_entry_that_cannot_be_read_is_an_error(self):
        for what, body in (("syntax error", b"import pygame\ndef (:\n"),
                           ("not utf-8", b"import pygame\n# \xff\xfe\n")):
            with self.subTest(what):
                self.cdn.entry.write_bytes(body)
                with self.assertRaises(vw.VendorError) as ctx:
                    self.cdn.vendor()
                self.assertIn("cannot read the entry", str(ctx.exception))

    def test_a_page_that_cannot_be_read_is_an_error(self):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (tmp / "index.html").write_bytes(b"\xff\xfe data-python")
        with self.assertRaises(vw.VendorError) as ctx:
            vw.runtime_for(tmp / "index.html", PEP0723_SHAPE)
        self.assertIn("cannot read", str(ctx.exception))

    def test_no_pygbag_to_read_is_an_error(self):
        """Not importable, or a module that fails as it is used (pygbag
        reconfigures stdout on import, which fails on a stand-in stream)."""
        for stand_in in (None, object()):
            with self.subTest(repr(stand_in)), \
                    mock.patch.dict(sys.modules, {"pygbag": stand_in}), \
                    self.assertRaises(vw.VendorError) as ctx:
                vw.installed_pep0723()
            self.assertIn("pygbag", str(ctx.exception))

    def test_a_runtime_naming_two_targets_is_an_error(self):
        self.cdn.data.write_bytes(b"wasm32-bi-emscripten and wasm64-bi-emscripten")
        with self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn("2 wasm targets", str(ctx.exception))

    def test_a_runtime_naming_no_target_is_an_error(self):
        self.cdn.data.write_bytes(b"nothing here")
        with self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn("main.data", str(ctx.exception))

    def test_nothing_the_entry_does_not_need_is_vendored(self):
        self.cdn.vendor()
        wheels = sorted(p.name for p in (self.cdn.out / "cdn").rglob("*.whl"))
        self.assertEqual(wheels, [Path(STATIC_404).name])

    def test_the_wheel_base_comes_from_the_index(self):
        other = self.cdn.root.parent / "mirror"
        self.cdn.add_wheel(STATIC_404, root=other, tag="mirror")
        self.cdn.index["-CDN-"] = other.as_uri() + "/"
        self.cdn.write_index()
        self.cdn.wheel.unlink()
        self.cdn.vendor()
        self.assertIn(b"mirror", zipfile.ZipFile(self.cdn.out / "cdn" / STATIC_404)
                      .read("pkg/__init__.py"))

    def test_every_index_the_runtime_reads_is_merged_later_ones_winning(self):
        """As `async_repos` merges them: a wheel only the second index names
        is vendored, and its entry wins over the first index's."""
        second = {"-CDN-": self.cdn.base, "pygame": "cp312/pygame_ce-2.6.0-<abi>-<abi>-<api>.whl"}
        (self.cdn.root / "index-0.9.4-cp312.json").write_text(json.dumps(second))
        newer = self.cdn.add_wheel("cp312/pygame_ce-2.6.0-cp312-cp312-wasm32_bi_emscripten.whl")
        self.cdn.rt = _runtime(self.cdn.base, index_versions=("0.9.3", "0.9.4"))
        written = self.cdn.vendor()
        self.assertEqual([p.name for p in written], [newer.name])

    def test_an_offline_rebuild_with_a_cache_works(self):
        self.cdn.vendor()
        self.cdn.go_offline()
        self.cdn.vendor()
        self.assertTrue((self.cdn.out / "cdn" / STATIC_404).exists())
        self.assertTrue(any("using the cached index" in m for m in self.cdn.log))
        self.assertTrue(any("using the cached runtime target" in m for m in self.cdn.log))

    def test_a_server_refusing_head_still_builds(self):
        """A 405 on HEAD: the first build reads the runtime with GET; later
        builds keep the cached target, and say so."""
        real = self.cdn.real_urlopen

        def no_head(req, *a, **kw):
            if getattr(req, "get_method", lambda: "GET")() == "HEAD":
                raise vw.urllib.error.HTTPError(req.full_url, 405, "Method Not Allowed", {}, None)
            return real(req, *a, **kw)

        with mock.patch.object(vw.urllib.request, "urlopen", no_head):
            self.cdn.vendor()
            self.cdn.vendor()
        self.assertTrue((self.cdn.out / "cdn" / STATIC_404).exists())
        self.assertTrue(any("using the cached runtime target" in m for m in self.cdn.log))

    def test_a_dropped_connection_on_head_still_builds(self):
        """HEAD failing with a protocol error (not an HTTP status) is treated
        as no stamp, never as a crash."""
        real = self.cdn.real_urlopen
        for error in (http.client.RemoteDisconnected("closed"), ValueError("bad url")):
            with self.subTest(type(error).__name__):
                def flaky_head(req, *a, error=error, **kw):
                    if getattr(req, "get_method", lambda: "GET")() == "HEAD":
                        raise error
                    return real(req, *a, **kw)

                with mock.patch.object(vw.urllib.request, "urlopen", flaky_head):
                    self.cdn.vendor()
                self.assertTrue((self.cdn.out / "cdn" / STATIC_404).exists())

    def test_an_offline_first_build_fails_naming_the_url(self):
        self.cdn.go_offline()
        with self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn("index-0.9.3-cp312.json", str(ctx.exception))
        self.assertEqual(self.cdn.leftovers(), [])

    def test_a_bad_index_response_never_replaces_the_cached_one(self):
        """Answers that are not an index, each with a 200: an HTML page, a
        JSON error body, JSON naming no wheel, a list, a relative `-CDN-`.
        The build carries on with the cached index, which stays intact for
        later offline builds."""
        self.cdn.vendor()
        cached = self.cdn.cache / "index-0.9.3-cp312.json"
        good = cached.read_bytes()
        live = self.cdn.root / "index-0.9.3-cp312.json"
        for body in ("<html>login</html>", '{"message": "rate limited"}',
                     json.dumps({"-CDN-": self.cdn.base, "pygame": "not-a-wheel"}), "[]",
                     json.dumps({"-CDN-": "cdn/", "pygame": PYGAME_PATH}),
                     json.dumps({"-CDN-": "http://[::1/", "pygame": PYGAME_PATH}),  # urlparse ValueError
                     json.dumps({"-CDN-": "http://a..b/", "pygame": PYGAME_PATH}),  # no IDNA host
                     json.dumps({"-CDN-": "http:///nohost/", "pygame": PYGAME_PATH}),
                     json.dumps({"-CDN-": "ftp://x.example/", "pygame": PYGAME_PATH}),
                     *(json.dumps({"-CDN-": bad, "pygame": PYGAME_PATH}) for bad in (
                         "http://x:abc/", "http://x:99999/", "http://exa mple/", "http://x\x00y/",
                         "https://x/\r\nHost: evil/", "https://-/", "http://x/%zz/",
                         "http://user:pw@x.example/", "http://x.example:0/", "http://0/",
                         "http://1.2.3.4.5/")),
                     "[" * 200_000):                       # RecursionError in json
            with self.subTest(body[:40]):
                live.write_text(body)
                self.cdn.log.clear()
                self.cdn.vendor()
                self.assertEqual(cached.read_bytes(), good)
                self.assertTrue(any("is not a valid package index" in m for m in self.cdn.log),
                                self.cdn.log)
                self.assertFalse(list(self.cdn.cache.rglob("*.part")))
        self.cdn.go_offline()
        self.cdn.vendor()

    def test_a_broken_connection_falls_back_to_the_cached_index(self):
        self.cdn.vendor()
        real = self.cdn.real_urlopen

        def broken(req, *a, **kw):
            if getattr(req, "full_url", str(req)).endswith(".json"):
                raise http.client.BadStatusLine("garbage")
            return real(req, *a, **kw)

        with mock.patch.object(vw.urllib.request, "urlopen", broken):
            self.cdn.vendor()
        self.assertTrue(any("BadStatusLine" in m for m in self.cdn.log))

    def test_a_cut_off_wheel_download_fails_naming_the_url(self):
        def cut_off(req, *a, **kw):
            if getattr(req, "full_url", str(req)).endswith(".whl"):
                raise http.client.IncompleteRead(b"PK")
            return self.cdn.real_urlopen(req, *a, **kw)

        with mock.patch.object(vw.urllib.request, "urlopen", cut_off), \
                self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn(STATIC_404, str(ctx.exception))
        self.assertEqual(self.cdn.leftovers(), [])

    def test_a_url_urlopen_rejects_fails_naming_it(self):
        """`urlopen` raises ValueError / UnicodeError for some URLs before any
        network access (an empty IDNA label): a VendorError, not a traceback."""
        def bad_host(req, *a, **kw):
            if getattr(req, "full_url", str(req)).endswith(".whl"):
                raise UnicodeError("label empty or too long")
            return self.cdn.real_urlopen(req, *a, **kw)

        with mock.patch.object(vw.urllib.request, "urlopen", bad_host), \
                self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn(STATIC_404, str(ctx.exception))
        self.assertEqual(self.cdn.leftovers(), [])

    def test_a_bad_index_and_no_cache_fails_naming_the_url(self):
        (self.cdn.root / "index-0.9.3-cp312.json").write_text('{"message": "rate limited"}')
        with self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn(self.cdn.base + "index-0.9.3-cp312.json", str(ctx.exception))
        self.assertFalse((self.cdn.cache / "index-0.9.3-cp312.json").exists())

    def test_a_missing_wheel_fails_naming_the_url_and_leaves_nothing(self):
        self.cdn.wheel.unlink()
        with self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn(STATIC_404, str(ctx.exception))
        self.assertEqual(self.cdn.leftovers(), [])

    def test_a_damaged_wheel_download_is_rejected_and_not_kept(self):
        """Not a zip, no metadata, a member failing its CRC (payload or the
        METADATA itself), a broken directory: each fails naming the URL and
        leaves nothing in the cache or `out/`."""
        bodies = {"html": b"<html>404</html>", "no metadata": _wheel_bytes(metadata=False),
                  **_damaged_bodies(_wheel_bytes())}
        for what, body in bodies.items():
            with self.subTest(what):
                self.cdn.wheel.write_bytes(body)
                with self.assertRaises(vw.VendorError) as ctx:
                    self.cdn.vendor()
                self.assertIn(STATIC_404, str(ctx.exception))
                self.assertEqual(self.cdn.leftovers(), [])

    def test_a_damaged_cached_wheel_is_fetched_again(self):
        self.cdn.vendor()
        cached = self.cdn.cache / vw.WHEELS_DIR / STATIC_404
        good = cached.read_bytes()
        for what, body in _damaged_bodies(good).items():
            with self.subTest(what):
                cached.write_bytes(body)
                self.cdn.vendor()
                self.assertEqual(cached.read_bytes(), good)
                self.assertEqual((self.cdn.out / "cdn" / STATIC_404).read_bytes(), good)
                self.assertIn(STATIC_404, self.cdn.urls)

    def test_requires_dist_is_followed_as_the_runtime_follows_it(self):
        """Index dependencies are vendored (the runtime fetches them from the
        same `cdn/`); others go to PyPI and are only logged; extras skipped."""
        self.cdn.wheel.write_bytes(_wheel_bytes(requires=[
            "python-bidi>=0.4", "requests[socks]", "pytest ; extra == 'test'", "colorama"]))
        self.cdn.index["python_bidi"] = BIDI
        self.cdn.write_index()
        self.cdn.add_wheel(BIDI)
        self.cdn.vendor()
        got = sorted(p.name for p in (self.cdn.out / "cdn").rglob("*.whl"))
        self.assertEqual(got, sorted([Path(STATIC_404).name, Path(BIDI).name]))
        self.assertTrue(any("colorama" in m and "PyPI" in m for m in self.cdn.log))
        self.assertFalse(any("requests" in m or "pytest" in m for m in self.cdn.log))

    def test_a_block_dependency_is_vendored(self):
        self.cdn.entry.write_text('# /// pyproject\n# [project]\n# dependencies = ["bidi"]\n'
                                  "# ///\nimport pygame\n", encoding="utf-8")
        self.cdn.add_wheel(BIDI)
        self.cdn.vendor()
        self.assertTrue((self.cdn.out / "cdn" / BIDI).exists())

    def test_a_block_exclusion_is_never_vendored(self):
        """`!pygame` makes the runtime treat pygame as installed."""
        self.cdn.entry.write_text('# /// script\n# dependencies = ["!pygame", "bidi"]\n'
                                  "# ///\nimport pygame\n", encoding="utf-8")
        self.cdn.add_wheel(BIDI)
        written = self.cdn.vendor()
        self.assertEqual([p.name for p in written], [Path(BIDI).name])

    def test_an_index_path_leaving_the_folders_is_refused(self):
        """Escapes, Windows roots and drives, characters Windows refuses, and
        parts ending in a space or dot (folders Windows cannot delete, which
        would break pygbag's own cache clear): refused before any folder is
        made, so the cache holds only what a good build leaves."""
        for bad in ("../escape-<abi>.whl", "cp312/../../escape.whl", "/escape.whl",
                    "C:/escape.whl", "C:escape.whl", r"\\srv\share\escape.whl",
                    r"cp312\..\..\escape.whl", "cp312/a?b/escape.whl", "cp312/C:/escape.whl",
                    "cp312/a:b.whl", "cp312/.. /.. /escape.whl", "cp312/.../.../escape.whl",
                    "cp312/... /escape.whl", "cp312/escape\x01.whl", "cp312/ escape.whl",
                    "cp312//escape.whl", "cp312/escape./x.whl",
                    "cp312/con.whl", "cp312/aux/x.whl", "cp312/COM1.whl", "cp312/lpt1/x.whl",
                    "cp312/prn.whl", "nul.whl", "cp312/CON/x.whl", "cp312/nul/x.whl",
                    "cp312/Nul.tar/x.whl"):
            with self.subTest(repr(bad)):
                self.cdn.index["pygame"] = bad
                self.cdn.write_index()
                with self.assertRaises(vw.VendorError) as ctx:
                    self.cdn.vendor()
                self.assertIn("unsafe wheel path", str(ctx.exception))
                self.assertFalse(list(self.cdn.out.parent.glob("escape*")))
                self.assertEqual(sorted(p.name for p in self.cdn.cache.iterdir()
                                        if p.is_dir()), [])

    def test_every_real_index_path_shape_is_accepted(self):
        for path in (STATIC_404, BIDI, "cp312/cffi-1.18.0.dev0-cp312-cp312-wasm32_bi_emscripten.whl",
                     "cp312/lvgl-0.1.1b0-cp312-cp312-wasm32_bi_emscripten.whl",
                     "pkg/some_pkg-1.0+local-py3-none-any.whl"):
            with self.subTest(path):
                self.assertTrue(vw._safe_relative(path))

    def test_real_world_wheel_bases_are_accepted(self):
        for base in ("https://pygame-web.github.io/cdn/", "http://localhost:8000/cdn/",
                     "http://127.0.0.1:8001/x/", "http://[::1]:8000/cdn/", "http://10.0.0.1/w/",
                     "https://cdn.example.org/a%20b/"):
            with self.subTest(base):
                self.assertTrue(vw._valid_base(base, allow_file=False))

    def test_a_new_index_is_kept_only_once_its_wheels_are_secured(self):
        """A valid new index naming a wheel that cannot be had: the build
        fails, the cached index stays the old one, and an offline rebuild
        still works from it."""
        self.cdn.vendor()
        cached = self.cdn.cache / "index-0.9.3-cp312.json"
        old = cached.read_bytes()
        self.cdn.index["pygame"] = "cp312/pygame_ce-9.9.9-<abi>-<abi>-<api>.whl"
        self.cdn.write_index()
        with self.assertRaises(vw.VendorError):
            self.cdn.vendor()
        self.assertEqual(cached.read_bytes(), old)
        self.assertFalse(list(self.cdn.cache.glob("*.new")))
        self.cdn.go_offline()
        self.assertEqual([p.name for p in self.cdn.vendor()], [Path(STATIC_404).name])

    def test_wheel_paths_named_like_the_helpers_own_files_cannot_reach_them(self):
        """An index path whose first part is the index, the tag or the
        runtime data file name: wheels are cached in their own folder, so
        the build works and later builds keep working."""
        self.cdn.vendor()
        tag = next(self.cdn.cache.glob("api-*.txt")).name
        mirror = self.cdn.root.parent / "mirror"            # the CDN root holds the index
        for first in ("index-0.9.3-cp312.json", "index-0.9.3-cp312.json.123.new", tag,
                      tag.replace("api-", "main-").replace(".txt", ".data")):
            with self.subTest(first):
                path = f"{first}/pg.whl"
                self.cdn.add_wheel(path, root=mirror)
                self.cdn.index.update({"pygame": path, "-CDN-": mirror.as_uri() + "/"})
                self.cdn.write_index()
                self.assertEqual(self.cdn.vendor(), [self.cdn.out / "cdn" / path])
                self.cdn.index.update({"pygame": PYGAME_PATH, "-CDN-": self.cdn.base})
                self.cdn.write_index()                      # the real index back
                self.assertEqual(self.cdn.vendor(), [self.cdn.out / "cdn" / STATIC_404])
                self.assertTrue((self.cdn.cache / "index-0.9.3-cp312.json").is_file())
                self.assertTrue((self.cdn.cache / tag).is_file())

    def test_a_fresh_index_is_staged_under_a_per_process_name(self):
        """Two builds sharing a cache never discard each other's new index."""
        dests = []
        real = vw._download

        def spy(url, dest, *a, **kw):
            dests.append(dest)
            return real(url, dest, *a, **kw)

        with mock.patch.object(vw, "_download", spy):
            self.cdn.vendor()
        staged = [d.name for d in dests if d.name.startswith("index-")]
        self.assertEqual(staged, [f"index-0.9.3-cp312.json.{vw.os.getpid()}.new"])

    def test_a_failed_build_leaves_no_half_vendored_out(self):
        """The first wheel lands in out/, then a dependency it requires
        cannot be had: the build fails and out/ holds none of it."""
        self.cdn.wheel.write_bytes(_wheel_bytes(requires=["python-bidi"]))
        self.cdn.index["python_bidi"] = BIDI                # named, but not served
        self.cdn.write_index()
        with self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn(BIDI, str(ctx.exception))
        self.assertFalse((self.cdn.out / "cdn").exists())

    def test_wheels_the_entry_does_not_need_do_not_hold_back_the_index(self):
        """The index is committed once the wheels this build needs are
        secured; other wheels it names are not fetched or checked."""
        self.cdn.vendor()
        self.cdn.index["numpy"] = "cp312/numpy-9.9.9-nonexistent.whl"
        self.cdn.write_index()
        self.cdn.vendor()
        cached = json.loads((self.cdn.cache / "index-0.9.3-cp312.json").read_text())
        self.assertIn("numpy", cached)
        self.assertNotIn("cp312/numpy-9.9.9-nonexistent.whl", self.cdn.urls)

    def test_a_locked_index_or_runtime_file_at_read_time_is_a_vendor_error(self):
        real_text, real_bytes = Path.read_text, Path.read_bytes

        def text(path, *a, **kw):
            if path.name.endswith(".new") and ".json." in path.name:
                raise PermissionError(32, "in use by another process", str(path))
            return real_text(path, *a, **kw)

        def data(path, *a, **kw):
            if path.suffix == ".data":
                raise PermissionError(32, "in use by another process", str(path))
            return real_bytes(path, *a, **kw)

        for what, patch in (("index", mock.patch.object(Path, "read_text", text)),
                            ("runtime", mock.patch.object(Path, "read_bytes", data))):
            with self.subTest(what), patch, self.assertRaises(vw.VendorError) as ctx:
                self.cdn.vendor()
            self.assertIn("cannot read", str(ctx.exception))

    def test_a_new_index_replaces_the_cached_one_after_a_good_build(self):
        self.cdn.vendor()
        self.cdn.index["PIL"] = "cp312/pillow-12.0.0-<abi>-<abi>-<api>.whl"
        self.cdn.write_index()
        self.cdn.vendor()
        cached = json.loads((self.cdn.cache / "index-0.9.3-cp312.json").read_text())
        self.assertEqual(cached["PIL"], "cp312/pillow-12.0.0-<abi>-<abi>-<api>.whl")

    def test_unexpected_transport_errors_are_vendor_errors(self):
        for error in (TypeError("bad"), LookupError("codec"), RuntimeError("mid-read")):
            with self.subTest(type(error).__name__):
                def odd(req, *a, error=error, **kw):
                    if getattr(req, "full_url", str(req)).endswith(".whl"):
                        raise error
                    return self.cdn.real_urlopen(req, *a, **kw)

                with mock.patch.object(vw.urllib.request, "urlopen", odd), \
                        self.assertRaises(vw.VendorError) as ctx:
                    self.cdn.vendor()
                self.assertIn(STATIC_404, str(ctx.exception))
                self.assertEqual(self.cdn.leftovers(), [])

    def test_a_failed_download_through_a_device_named_folder_leaves_no_folder(self):
        """`nul` exists() on Windows without being a folder; the folders made
        are judged by `is_dir`, so none is left when the download fails."""
        dest = self.cdn.cache / "cp312" / "nul" / "x.whl"
        with self.assertRaises(vw.VendorError):
            vw._download(self.cdn.base + "missing.whl", dest, vw._valid_wheel, "wheel")
        self.assertFalse(self.cdn.cache.exists() and any(self.cdn.cache.iterdir()))

    def test_a_part_file_that_cannot_be_removed_never_hides_the_error(self):
        """A locked `.part` (antivirus, indexer): the real VendorError still
        surfaces, naming the URL."""
        self.cdn.wheel.unlink()
        real_unlink = Path.unlink

        def locked(path, *a, **kw):
            if path.name.endswith(".part"):
                raise PermissionError(13, "locked")
            return real_unlink(path, *a, **kw)

        with mock.patch.object(Path, "unlink", locked), \
                self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn(STATIC_404, str(ctx.exception))

    def _locked(self, suffix):
        """`Path.unlink` refusing files ending in `suffix`, as a Windows file
        held open by another process does."""
        real_unlink = Path.unlink

        def unlink(path, *a, **kw):
            if path.name.endswith(suffix):
                raise PermissionError(32, "in use by another process")
            return real_unlink(path, *a, **kw)
        return mock.patch.object(Path, "unlink", unlink)

    def test_a_locked_new_index_never_hides_the_error(self):
        self.cdn.wheel.unlink()
        with self._locked(".new"), self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn(STATIC_404, str(ctx.exception))

    def test_a_locked_new_index_never_fails_a_good_build(self):
        with self._locked(".new"):
            self.assertEqual(self.cdn.vendor(), [self.cdn.out / "cdn" / STATIC_404])

    def test_a_locked_runtime_data_file_never_fails_a_good_build(self):
        with self._locked(".data"):
            self.assertEqual(self.cdn.vendor(), [self.cdn.out / "cdn" / STATIC_404])

    def test_a_failed_first_run_leaves_no_cache_folder(self):
        """The cache root is made by the run; when it fails, it goes too."""
        self.cdn.data.unlink()                              # the runtime 404s
        with self.assertRaises(vw.VendorError):
            self.cdn.vendor()
        self.assertFalse(self.cdn.cache.exists())

    def test_a_cache_file_that_cannot_be_replaced_names_the_file(self):
        real_replace = vw.os.replace

        def read_only(src, dst):
            if str(dst).endswith(".whl") and "cache" in str(dst):
                raise PermissionError(5, "read-only")
            return real_replace(src, dst)

        with mock.patch.object(vw.os, "replace", read_only), \
                self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn("cannot write", str(ctx.exception))
        self.assertIn(Path(STATIC_404).name, str(ctx.exception))

    def test_a_remote_index_may_not_point_wheels_at_local_files(self):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory())) / "i.json"
        tmp.write_text(json.dumps({"-CDN-": "file:///C:/", "pygame": PYGAME_PATH}))
        self.assertFalse(vw._valid_index(tmp))
        self.assertTrue(vw._valid_index(tmp, allow_file=True))

    def test_a_stamp_with_no_information_reads_the_runtime_again(self):
        """No ETag, Last-Modified or length: a change cannot be seen, so
        the target is read again rather than trusted for good."""
        with mock.patch.object(vw, "_stamp", return_value="||"):
            self.cdn.vendor()
            self.cdn.vendor()
        self.assertIn("0.9.3/cpython312/main.data", self.cdn.urls)
        self.assertTrue(any("sends no ETag" in m for m in self.cdn.log))

    def test_a_cache_folder_that_cannot_be_made_fails_naming_the_file(self):
        """A file where the wheel's cache folder should be: a VendorError
        saying it cannot write there and naming the cache path, not a raw
        OSError and not a "download failed" pointing at the network."""
        self.cdn.cache.mkdir(parents=True)
        (self.cdn.cache / vw.WHEELS_DIR).mkdir()
        (self.cdn.cache / vw.WHEELS_DIR / "cp312").write_text("in the way")
        with self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn("cannot write", str(ctx.exception))
        self.assertNotIn("download failed", str(ctx.exception))
        self.assertIn(str(self.cdn.cache / vw.WHEELS_DIR / "cp312"), str(ctx.exception))

    def test_a_cache_that_is_a_file_fails_naming_it_before_any_request(self):
        self.cdn.cache.parent.mkdir(parents=True, exist_ok=True)
        self.cdn.cache.write_text("not a folder")
        with self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn("cannot write", str(ctx.exception))
        self.assertIn(str(self.cdn.cache), str(ctx.exception))
        self.assertEqual(self.cdn.urls, [])

    def test_a_body_cut_off_mid_read_fails_naming_the_url(self):
        """The response opens, then reading it fails (a protocol error, not
        an OSError): a VendorError naming the URL, nothing left."""
        class CutOff(io.BytesIO):
            def read(self, n=-1):
                raise http.client.IncompleteRead(b"PK", 1000)

        def cut_off(req, *a, **kw):
            if getattr(req, "full_url", str(req)).endswith(".whl"):
                return CutOff()
            return self.cdn.real_urlopen(req, *a, **kw)

        with mock.patch.object(vw.urllib.request, "urlopen", cut_off), \
                self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn("download failed", str(ctx.exception))
        self.assertIn(STATIC_404, str(ctx.exception))
        self.assertEqual(self.cdn.leftovers(), [])

    def test_a_killed_runs_part_files_are_swept_a_live_one_is_kept(self):
        self.cdn.vendor()
        old = self.cdn.cache / vw.WHEELS_DIR / "cp312" / "x.whl.99999.part"
        live = self.cdn.cache / vw.WHEELS_DIR / "cp312" / "y.whl.88888.part"
        old.write_bytes(b"half")
        live.write_bytes(b"half")
        long_ago = vw.time.time() - 2 * vw.STALE_PART_S
        vw.os.utime(old, (long_ago, long_ago))
        self.cdn.vendor()
        self.assertFalse(old.exists())
        self.assertTrue(live.exists())

    def test_a_full_disk_mid_download_names_the_part_file(self):
        real_open = open

        def full_disk(file, mode="r", *a, **kw):
            fh = real_open(file, mode, *a, **kw)
            if str(file).endswith(".part"):
                def write(_):
                    raise OSError(28, "No space left on device", str(file))
                fh.write = write
            return fh

        with mock.patch("builtins.open", full_disk), \
                self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn("cannot write", str(ctx.exception))
        self.assertIn(".part", str(ctx.exception))
        self.assertIn("No space left", str(ctx.exception))
        self.assertEqual(self.cdn.leftovers(), [])

    def test_a_failed_copy_into_out_leaves_no_half_wheel(self):
        def disk_full(src, dst, *a, **kw):
            Path(dst).write_bytes(b"PK partial")
            raise OSError(28, "No space left on device")

        with mock.patch.object(vw.shutil, "copyfile", disk_full), \
                self.assertRaises(vw.VendorError) as ctx:
            self.cdn.vendor()
        self.assertIn("cannot write", str(ctx.exception))
        self.assertFalse((self.cdn.out / "cdn" / STATIC_404).exists())
        self.assertFalse(list(self.cdn.out.rglob("*.part")))

    def test_an_entry_that_needs_no_wheel_is_an_error(self):
        """pygbag would load no pygame: the build must not pass quietly."""
        self.cdn.entry.write_text("import os\n", encoding="utf-8")
        with self.assertRaises(vw.VendorError):
            self.cdn.vendor()

    def test_the_command_line_exits_non_zero_on_failure(self):
        self.cdn.wheel.unlink()
        argv = ["--entry", str(self.cdn.entry), "--out", str(self.cdn.out),
                "--cache", str(self.cdn.cache)]
        err = io.StringIO()
        with mock.patch.object(vw, "runtime_for", return_value=self.cdn.rt), \
                mock.patch.object(vw, "installed_pep0723", return_value=""), \
                redirect_stderr(err), redirect_stdout(io.StringIO()):
            self.assertEqual(vw.main(argv), 1)
        self.assertIn("download failed", err.getvalue())


class BuildScriptTests(unittest.TestCase):
    """`build.sh` runs the helper on the folder it serves, after the copy
    that would otherwise wipe it, and stops the build when it fails."""

    def setUp(self):
        self.text = (WEB / "build.sh").read_text(encoding="utf-8")

    def _call(self):
        return next(ln for ln in self.text.splitlines() if "vendor_wheels.py" in ln
                    and not ln.lstrip().startswith("#"))

    def test_the_helper_runs_after_out_is_copied(self):
        lines = self.text.splitlines()
        self.assertLess(lines.index("cp -r ../../build/web out"), lines.index(self._call()))

    def test_it_vendors_into_out_from_the_entry_with_the_build_python(self):
        line = self._call()
        self.assertTrue(line.startswith('"$PY" vendor_wheels.py'), line)
        self.assertIn("--entry ../../main.py", line)
        self.assertIn("--out out", line)
        self.assertRegex(line, r"--cache \.\./\.\./build/")

    def test_a_failure_stops_the_build(self):
        self.assertRegex(self.text, re.compile(r"^set -e$", re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
