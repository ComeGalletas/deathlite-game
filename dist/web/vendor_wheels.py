"""Vendor the wasm wheels pygbag's loader fetches from localhost (BLD-006).

A pygbag page loads its Python packages as wheels, and pygbag 0.9.3 picks
where from by the page's address (`support/cross/aio/pep0723.py`,
`async_repos`): when the address starts with `http://localhost:8` every wheel
comes from `http://localhost:8000/cdn/`, otherwise from the public CDN the
package index names. pygbag's dev server (`serve.sh`) proxies `/cdn/`; a plain
static server (`python -m http.server -d dist/web/out 8000`) does not, and the
page stops on a 404 for the pygame-ce wheel. `build.sh` runs this after it
copies the bundle to `out/`, so `out/` served on port 8000 boots.

Where each fact comes from, so that a pygbag upgrade moves with it:

* the built page, `out/index.html`: the browser's Python (`data-python`, which
  gives `<abi>`, `cp<major><minor>`) and the runtime's base URL (`cdn :`), so
  a `--PYBUILD` or `--cdn` passed to pygbag is followed;
* the installed pygbag's `support/cross/aio/pep0723.py`, parsed (never
  imported, it is browser code): the package base `Config.PKG_BASE_DEFAULT`,
  the renaming table `Config.mapping`, the dependency-block reader
  `read_dependency_block_723` (compiled from that source and run as is), the
  index versions `async_repos` merges, and the
  local wheel base `rewritecdn` with the address prefix that turns it on. The
  browser runs the CDN's copy of this file for the same pygbag version, which
  is packed inside the runtime and cannot be read directly; the installed copy
  stands in for it;
* the runtime itself, `<runtime base>cpython<XY>/main.data` (about 7 MB; the
  tag is cached with the file's stamp, see below): `<api>`, its `HOST_GNU_TYPE`;
* the CDN at build time: the package index, `index-<version>-<abi>.json`,
  which names each wheel's path and, under `-CDN-`, the base it lives at.

If pygbag's code no longer has one of these, the build stops naming what is
missing rather than vendoring the wrong thing.

Which wheels: the entry's imports (pygbag scans the entry file's own imports,
`documentation/journals/pygbag.md`, W5), its dependency block (`# /// script`
or `# /// pyproject`, read by pygbag's own reader; a `!name` entry excludes a
package, as `parse_code` does), then each vendored wheel's `Requires-Dist`
(as `install_pkg` reads it). The import scan takes names as `scan_imports` does;
it skips none, where the runtime skips modules it already has, so it may name
more; that only matters for names the index has a wheel for.

The index is fetched on every build, because the browser reads the live index
at page load and the vendored wheel must be the one it names; it is about
1.5 KB, and the cached copy is used when offline. Wheels come from the cache
(their own `wheels/` folder in it, apart from the files above)
once downloaded (`build.sh` passes pygbag's own `build/web-cache/`, which
pygbag empties itself when its version changes). `<api>` is cached with the
runtime file's stamp and read again only when a HEAD request shows the file
changed (or sends no stamp to compare). Every download goes to a `.part` file and replaces the cached file
only once complete and valid (an index must be a JSON object with an http(s)
`-CDN-` URL, `file:` only from a `file:` index, and at least one wheel; a
wheel a zip whose every member reads
back with its CRC and which holds a `.dist-info/METADATA`); a cached wheel is
checked the same way before reuse; a wheel path from the index must be plain
`/`-separated names (no root, drive, `..`, characters Windows refuses or Windows
device names such as `nul`); a new index replaces the cached one only once
the wheels this build needs from it are secured; and the copy into `out/` is written whole or
not at all, and a failed run takes back what it copied there. Any failure exits
non-zero with a `VendorError` naming the URL or file that failed.

    python vendor_wheels.py --entry ../../main.py --out out --cache ../../build/web-cache/cdn
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import ipaddress
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import tomllib

TIMEOUT_S = 120
# Cached wheels live in their own folder of the cache, so no index path can
# reach the helper's own files beside it (the index, its `.new`, the target
# tag, the runtime data).
WHEELS_DIR = "wheels"
# What the runtime's HOST_GNU_TYPE looks like in its data file: one distinct
# match is required, so a runtime that names two targets fails loudly.
API_RE = re.compile(rb"\b(wasm(?:32|64)-[A-Za-z0-9_]+-emscripten)\b")
NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
# One part of a wheel path from the index (see _safe_relative).
SAFE_PART_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")
# Names Windows maps to devices whatever their extension (`nul.whl` is NUL);
# the allow-list above already refuses the superscript-digit forms.
WINDOWS_DEVICES = frozenset({"con", "prn", "aux", "nul",
                             *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))})
# A host label in a `-CDN-` URL (letters, digits, inner hyphens).
HOST_LABEL_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?")
# In pygbag's generated index.html.
PAGE_PYTHON_RE = re.compile(r'data-python="python(\d+)\.(\d+)"')
PAGE_CDN_RE = re.compile(r'^\s*cdn\s*:\s*"([^"]+)"', re.MULTILINE)
PEP0723_KEYS = ("PKG_BASE_DEFAULT", "mapping", "read_block", "versions",
                "local_base", "local_prefix")


class VendorError(Exception):
    """A wheel, the index, the page or the runtime could not be had or read;
    the message names what failed."""


@dataclass(frozen=True)
class Runtime:
    """How the browser runtime resolves wheels for this build."""
    abi: str                      # e.g. "cp312", from the page
    runtime_base: str             # the page's `cdn`, ".../cdn/0.9.3/"
    pkg_base: str                 # Config.PKG_BASE_DEFAULT, ".../cdn/"
    index_versions: tuple[str, ...]
    mapping: dict                 # Config.mapping
    read_block: Callable          # pygbag's own read_dependency_block_723
    local_base: str               # rewritecdn, "http://localhost:8000/cdn/"
    local_prefix: str             # the address prefix that uses it

    @property
    def local_folder(self) -> str:
        """Where under the served folder the local base points: "cdn"."""
        return urllib.parse.urlparse(self.local_base).path.strip("/")


# --- reading pygbag ---------------------------------------------------------

def _load_block_reader(node: ast.FunctionDef) -> Callable:
    """pygbag's own `read_dependency_block_723`, compiled from its source and
    run in a namespace holding only what it uses (tomllib, json, its two
    globals, a silent print), so the PEP 723 block is read exactly as the
    runtime reads it. Returns a function from source text to a list."""
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {"tomllib": tomllib, "json": json, "HISTORY": [], "hint_failed": [],
                 "print": lambda *a, **k: None}
    exec(compile(module, "pep0723.py:read_dependency_block_723", "exec"), namespace)  # noqa: S102
    reader = namespace[node.name]

    def read(code: str) -> list:
        try:
            return [str(dep) for dep in reader(code)]
        except Exception as exc:  # TOML errors, and the reader's own on odd shapes
            raise VendorError(f"the entry's dependency block cannot be read: {_why(exc)}") from exc
    return read


def _literal(node: ast.AST, what: str):
    """A literal from pygbag's source, or a VendorError naming it if pygbag
    no longer writes it as one."""
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError) as exc:
        raise VendorError(f"pygbag's pep0723.py no longer gives {what} as a literal "
                          f"({exc}); vendor_wheels.py needs updating for this pygbag") from exc


def parse_pep0723(source: str) -> dict:
    """The runtime settings from pep0723.py's source: PKG_BASE_DEFAULT and
    mapping from `class Config`; the block reader `read_dependency_block_723`;
    from `async_repos`, the versions it loops over (`for pygver in (...)`),
    the local wheel base it assigns to `rewritecdn`, and the `startswith`
    prefix that selects it."""
    tree = ast.parse(source)
    found: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "read_dependency_block_723":
            found["read_block"] = _load_block_reader(node)
        if isinstance(node, ast.ClassDef) and node.name == "Config":
            for stmt in node.body:
                if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)
                        and stmt.targets[0].id in ("PKG_BASE_DEFAULT", "mapping")):
                    found[stmt.targets[0].id] = _literal(stmt.value, stmt.targets[0].id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "async_repos":
            for sub in ast.walk(node):
                if (isinstance(sub, ast.For) and isinstance(sub.target, ast.Name)
                        and sub.target.id == "pygver"):
                    found["versions"] = tuple(_literal(sub.iter, "versions"))
                elif (isinstance(sub, ast.If) and isinstance(sub.test, ast.Call)
                        and isinstance(sub.test.func, ast.Attribute)
                        and sub.test.func.attr == "startswith" and sub.test.args
                        and isinstance(sub.test.args[0], ast.Constant)):
                    for stmt in sub.body:
                        if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                                and isinstance(stmt.targets[0], ast.Name)
                                and stmt.targets[0].id == "rewritecdn"
                                and isinstance(stmt.value, ast.Constant)):
                            if "local_base" in found:
                                raise VendorError("pygbag's pep0723.py sets `rewritecdn` in more "
                                                  "than one branch; vendor_wheels.py needs "
                                                  "updating for this pygbag")
                            found["local_prefix"] = sub.test.args[0].value
                            found["local_base"] = stmt.value.value
    missing = [k for k in PEP0723_KEYS if k not in found]
    if missing:
        raise VendorError(f"pygbag's pep0723.py no longer has {missing}; "
                          "vendor_wheels.py needs updating for this pygbag")
    return found


def parse_page(html: str) -> tuple[str, str]:
    """(abi, runtime base) from pygbag's generated index.html."""
    py, cdn = PAGE_PYTHON_RE.search(html), PAGE_CDN_RE.search(html)
    if not (py and cdn):
        raise VendorError("the built index.html no longer names its Python "
                          "(data-python) or its runtime (cdn :)")
    base = cdn.group(1)
    return f"cp{py.group(1)}{py.group(2)}", base if base.endswith("/") else base + "/"


def runtime_for(page: Path, pep0723_source: str) -> Runtime:
    if not page.exists():
        raise VendorError(f"{page} is missing: run this after pygbag built the page")
    try:
        html = page.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise VendorError(f"cannot read {page}: {_why(exc)}") from exc
    abi, runtime_base = parse_page(html)
    cfg = parse_pep0723(pep0723_source)
    return Runtime(abi=abi, runtime_base=runtime_base, pkg_base=cfg["PKG_BASE_DEFAULT"],
                   index_versions=cfg["versions"], mapping=cfg["mapping"],
                   read_block=cfg["read_block"], local_base=cfg["local_base"],
                   local_prefix=cfg["local_prefix"])


def installed_pep0723() -> str:
    """The installed pygbag's pep0723.py source."""
    try:
        import pygbag
        return (Path(pygbag.__file__).parent / "support" / "cross" / "aio"
                / "pep0723.py").read_text(encoding="utf-8")
    except Exception as exc:  # not importable, or importing it fails (it reconfigures stdout)
        raise VendorError(f"cannot read the installed pygbag's pep0723.py: {_why(exc)}; "
                          "run this with the Python that built the page") from exc


# --- what the entry needs ---------------------------------------------------

def entry_imports(entry: Path) -> set[str]:
    """Top-level names the entry file imports, as pygbag's `scan_imports`
    (`support/cpythonrc.py`) takes them: an `import a.b` gives `a`, a
    `from a.b import c` gives `a`, whatever its level, so `from .x import y`
    gives `x` too; `from . import y` names no module and gives nothing."""
    tree = ast.parse(entry.read_text(encoding="utf-8"), filename=str(entry))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def block_requests(source: str, rt: Runtime) -> tuple[list[str], set[str]]:
    """(packages asked for, packages excluded) by the entry's dependency
    block, read by pygbag's own reader and then treated as `parse_code`
    treats them: an entry starting with `!` marks a package never to fetch,
    any other is the whole string, lower-cased with dashes as underscores."""
    asked, excluded = [], set()
    for dep in rt.read_block(source):
        if dep.startswith("!"):
            excluded.add(dep[1:])
        elif dep:
            asked.append(dep.lower().replace("-", "_"))
    return asked, excluded


def requirement_name(req: str) -> str | None:
    """The distribution name of a requirement, or None when the runtime skips
    it (one with extras, or one only an extra pulls in)."""
    if "; extra " in req:
        return None
    m = NAME_RE.match(req)
    if not m:
        return None
    if req[m.end():].lstrip().startswith("["):
        return None
    return m.group(1)


def remap(name: str, mapping: dict) -> str:
    """The runtime's `pip_install` key: lower case, dashes to underscores,
    then its renaming table."""
    key = name.lower().replace("-", "_")
    return mapping.get(key, key)


def wheel_requires(wheel: Path) -> list[str]:
    """`Requires-Dist` names of a wheel that the runtime installs with it."""
    with zipfile.ZipFile(wheel) as zf:
        meta = next((n for n in zf.namelist() if n.endswith(".dist-info/METADATA")), None)
        text = zf.read(meta).decode("utf-8", "replace") if meta else ""
    names = []
    for line in text.splitlines():
        if line.startswith("Requires-Dist: "):
            name = requirement_name(line[len("Requires-Dist: "):])
            if name:
                names.append(name)
    return names


def resolve(index: dict, name: str, rt: Runtime, api: str) -> str | None:
    """The wheel path, relative to the index's `-CDN-`, for `name` as written
    or as the runtime remaps it; None when the index has no wheel for it (the
    runtime then looks on PyPI, which no local server affects)."""
    for key in (name, remap(name, rt.mapping)):
        if key == "-CDN-" or key not in index:
            continue
        path = str(index[key]).replace("<abi>", rt.abi).replace("<api>", api)
        if path.endswith(".whl"):
            return path
    return None


# --- downloads --------------------------------------------------------------

def _safe_relative(path: str) -> bool:
    """An index path that is safe to join to a folder on any OS: `/`-separated
    parts that each start with a letter or digit and use only letters,
    digits and `._+-`, none ending in a dot. That rules out roots, drives,
    `..`, backslashes, characters Windows refuses (`:?*<>|"`), control
    characters, parts ending in a space or dot, which Windows creates as
    folders it then cannot delete, and Windows device names (`nul`, `con`,
    `com1`, ... whatever the extension). Every path in pygbag 0.9.3's index has
    this shape (`cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl`)."""
    parts = path.split("/")
    return all(SAFE_PART_RE.fullmatch(p) and not p.endswith(".")
               and p.split(".")[0].lower() not in WINDOWS_DEVICES for p in parts)


def _valid_wheel(path: Path) -> bool:
    """A wheel: a zip whose every member reads back with its stored CRC
    (`testzip`), holding a `.dist-info/METADATA`. Run on a download before it
    is cached and on a cached wheel before it is reused, so a damaged file
    is fetched again rather than vendored."""
    try:
        with zipfile.ZipFile(path) as zf:
            return (zf.testzip() is None
                    and any(n.endswith(".dist-info/METADATA") for n in zf.namelist()))
    except Exception:   # noqa: BLE001 -- zipfile raises BadZipFile, zlib.error,
        return False    # EOFError, NotImplementedError (method), RuntimeError (encrypted)...


def _valid_index(path: Path, allow_file: bool = False) -> bool:
    """A package index: a JSON object naming its `-CDN-` base as an absolute
    URL and at least one wheel. Anything else answering 200 (an error or
    rate-limit body, a captive portal) is not one. An index-shaped body from
    the wrong source cannot be told apart here: the build fails on a wheel
    it needs from it that cannot be had, and the index is kept only once
    every wheel this build needs from it is secured (wheels it names that
    the entry does not need are not checked; offline builds need only the
    entry's); the next build with the real index puts the real one back."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:   # noqa: BLE001 -- ValueError, UnicodeDecodeError, RecursionError...
        return False
    if not (isinstance(data, dict) and isinstance(data.get("-CDN-"), str)):
        return False
    return (_valid_base(data["-CDN-"], allow_file)
            and any(isinstance(v, str) and v.endswith(".whl") for v in data.values()))


def _valid_base(base: str, allow_file: bool) -> bool:
    """A `-CDN-` wheel base `urllib` can fetch from as written: no whitespace,
    control characters or bad `%` escapes anywhere; http(s) (or `file:` from
    a `file:` index) with a host of plain labels (or an IP), a numeric port
    in range if any, and no user or password."""
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in base):
        return False
    if re.search(r"%(?![0-9A-Fa-f]{2})", base):
        return False
    try:
        cdn = urllib.parse.urlsplit(base)
        if cdn.scheme not in (("http", "https", "file") if allow_file else ("http", "https")):
            return False
        if cdn.scheme == "file":
            return True
        if cdn.port == 0:                        # .port raises ValueError if not a port
            return False
        host = cdn.hostname or ""
        if cdn.username is not None or cdn.password is not None:
            return False
        if host.startswith("[") or ":" in host:  # IPv6, validated by urlsplit already
            return True
        labels = host.split(".")
        if all(label.isdigit() for label in labels):   # all numbers: a real IPv4
            ipaddress.IPv4Address(host)
            return True
        return all(HOST_LABEL_RE.fullmatch(label) for label in labels)
    except (ValueError, UnicodeError):
        return False


def _download(url: str, dest: Path, valid=None, what: str = "file") -> None:
    """`url` to `dest` through `dest.part`; `dest` is replaced only when the
    whole file arrived and `valid(part)` holds, so a bad response never
    overwrites a good cached copy, and no folder made for it is left behind
    when it fails."""
    part, made, done = None, [], False
    try:
        try:                                  # the cache side: folder and .part file
            made = _make_parents(dest)
            part = dest.with_name(f"{dest.name}.{os.getpid()}.part")   # one per build process
            fh = open(part, "wb")  # noqa: SIM115 -- closed by the `with fh` below
        except Exception as exc:              # write: any OS or path failure
            raise VendorError(f"cannot write {part or dest}: {_why(exc)}") from exc
        with fh:
            try:
                resp = urllib.request.urlopen(url, timeout=TIMEOUT_S)
            except Exception as exc:          # download: any transport failure
                raise VendorError(f"download failed: {url}: {_why(exc)}") from exc
            with resp:
                while True:
                    try:
                        chunk = resp.read(1 << 16)
                    except Exception as exc:  # download: cut off mid-body
                        raise VendorError(f"download failed: {url}: {_why(exc)}") from exc
                    if not chunk:
                        break
                    try:
                        fh.write(chunk)
                    except Exception as exc:  # write: disk full, file locked
                        raise VendorError(f"cannot write {part}: {_why(exc)}") from exc
        if valid is not None and not valid(part):
            raise VendorError(f"{url} is not a valid {what}")
        try:
            os.replace(part, dest)
        except OSError as exc:                # the download was fine; the cache file is not
            raise VendorError(f"cannot write {dest}: {_why(exc)}") from exc
        done = True
    finally:
        _clean_up(part, made, done)


def _why(exc: BaseException) -> str:
    """An exception for a message: its type and its text, which for an
    OSError carries the file name (its repr does not, on Windows)."""
    return f"{type(exc).__name__}: {exc}"


def _write_atomic(dest: Path, write) -> None:
    """`write(part)` then rename onto `dest`, so `dest` is never half
    written; any failure is a VendorError naming `dest`, and leaves no
    folder made for it."""
    part, made, done = None, [], False
    try:
        made = _make_parents(dest)
        part = dest.with_name(f"{dest.name}.{os.getpid()}.part")
        write(part)
        os.replace(part, dest)
        done = True
    except Exception as exc:  # write: any OS or copy failure
        raise VendorError(f"cannot write {dest}: {_why(exc)}") from exc
    finally:
        _clean_up(part, made, done)


def _make_parents(dest: Path) -> list[Path]:
    """Make `dest`'s parent folders one level at a time, top down, and return
    the ones this call made, deepest first. A level counts as present only
    if it is a folder (`is_dir`), not merely if it `exists()`, which a
    device name (`nul`) fools; anything else is made, or the call fails."""
    chain = [*reversed(dest.parent.parents), dest.parent]
    made: list[Path] = []
    try:
        for folder in chain:
            if folder.is_dir():
                continue
            folder.mkdir()                  # on Windows `nul` "succeeds" and makes nothing
            if not folder.is_dir():
                raise NotADirectoryError(f"{folder} could not be made as a folder")
            made.append(folder)
    except BaseException:
        _remove_empty(made[::-1])
        raise
    return made[::-1]


def _remove_empty(folders: list[Path]) -> None:
    for folder in folders:                  # deepest first
        try:
            folder.rmdir()                  # only succeeds while empty, so trying
        except OSError:                     # every one is safe: a folder holding
            pass                            # anything stays


STALE_PART_S = 3600


def _sweep_stale_parts(cache: Path) -> None:
    """Remove `.part` files a killed run left in the cache (their names
    carry that run's process id, so no later run would reuse them). Only
    ones untouched for an hour go, so a build running beside this one keeps
    its own."""
    now = time.time()
    for part in cache.rglob("*.part"):
        try:
            if now - part.stat().st_mtime > STALE_PART_S:
                _discard(part)
        except OSError:
            pass


def _discard(path: Path | None) -> None:
    """Remove a temporary file if it is there. Every cleanup goes through
    this: a file held open (antivirus, an indexer) is left rather than
    allowed to raise, so the real outcome, success or the VendorError, is
    never hidden behind a cleanup failure."""
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _clean_up(part: Path | None, made: list[Path], done: bool) -> None:
    """After a download or write: drop the `.part` file, and when the call
    failed, the folders it made."""
    _discard(part)
    if not done:
        _remove_empty(made)


def load_index(rt: Runtime, cache: Path, log, fresh: list) -> dict:
    """The merged index for every version the runtime reads, fetched fresh
    (the browser reads the live one) or, offline, from the cache. A fresh
    index is kept beside the cached one (`<name>.new`) and its pair added to
    `fresh`; `vendor` puts it in place only once every wheel this build
    needs from it is secured, so a new index whose needed wheel cannot be
    had never replaces one whose needed wheels are cached."""
    merged: dict = {}
    for version in rt.index_versions:
        name = f"index-{version}-{rt.abi}.json"
        url = rt.pkg_base + name
        cached = cache / name
        # A `file:` wheel base is only taken from an index read from `file:`
        # (a local mirror, the tests); a remote index must name http(s).
        local = url.startswith("file:")

        def valid(p: Path, local: bool = local) -> bool:
            return _valid_index(p, allow_file=local)

        new = cache / f"{name}.{os.getpid()}.new"   # one per build process
        try:
            _download(url, new, valid, "package index")
            fresh.append((new, cached))
            source = new
        except VendorError as exc:
            if not (cached.exists() and valid(cached)):
                raise
            log(f"{exc}; using the cached {name}")
            source = cached
        try:
            merged.update(json.loads(source.read_text(encoding="utf-8")))
        except Exception as exc:              # read: validated, then locked or changed
            raise VendorError(f"cannot read {source}: {_why(exc)}") from exc
    return merged


def _stamp(url: str) -> str:
    """What identifies the file at `url` without fetching it: its ETag,
    Last-Modified and length, from a HEAD request."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            h = resp.headers
            return "|".join(h.get(k, "") for k in ("ETag", "Last-Modified", "Content-Length"))
    except Exception as exc:  # stamp: any failure means no stamp
        raise VendorError(f"cannot reach {url}: {_why(exc)}") from exc


def api_tag(rt: Runtime, cache: Path, log) -> str:
    """The runtime's `<api>` tag, read from its data file and cached with
    that file's stamp. Each build compares the stamp (a HEAD request) and
    reads the file again only if it changed; offline, the cached tag is
    used."""
    # A short, file-name-safe key per runtime base and Python (any length of
    # base URL fits), so another pygbag or --cdn reads its own target.
    key = hashlib.sha256(f"{rt.runtime_base}|{rt.abi}".encode()).hexdigest()[:16]
    tag_file = cache / f"api-{key}.txt"
    url = f"{rt.runtime_base}cpython{rt.abi[2:]}/main.data"
    try:
        stamp, offline = _stamp(url), None
    except VendorError as exc:
        stamp, offline = None, exc
    try:
        lines = tag_file.read_text(encoding="utf-8").splitlines() + ["", ""]
    except (OSError, UnicodeDecodeError):       # missing or unreadable: no cached tag
        lines = ["", ""]
    tag, cached_stamp = lines[0].strip(), lines[1].strip()
    if tag and API_RE.fullmatch(tag.replace("_", "-").encode()):
        if offline is not None:
            log(f"{offline}; using the cached runtime target {tag}")
            return tag
        if stamp == cached_stamp and stamp.strip("|"):
            return tag
        if not stamp.strip("|"):
            log(f"{url} sends no ETag, Last-Modified or length; reading its target again")
        else:
            log(f"the runtime at {url} changed; reading its target again")
    # No usable cached tag: read the file, even when the HEAD failed (a server
    # may refuse HEAD and still serve GET; offline, this download fails too).
    data = cache / f"main-{key}.data"
    log(f"reading the runtime's target from {url}")
    _download(url, data, what="runtime data")
    try:
        try:
            found = set(API_RE.findall(data.read_bytes()))
        except OSError as exc:                # read: just written, then locked
            raise VendorError(f"cannot read {data}: {_why(exc)}") from exc
    finally:
        _discard(data)
    if len(found) != 1:
        raise VendorError(f"{url} names {len(found)} wasm targets "
                          f"({sorted(f.decode() for f in found)}); expected exactly one")
    tag = found.pop().decode().replace("-", "_")
    record = f"{tag}\n{stamp or ''}\n"
    _write_atomic(tag_file, lambda p: p.write_text(record, encoding="utf-8"))
    return tag


def vendor(entry: Path, out: Path, cache: Path, *, rt: Runtime | None = None,
           log=None) -> list[Path]:
    """Copy every wheel the entry needs to where the runtime's local base
    points under `out/` (`out/cdn/<path>`). Returns the files written.
    Raises `VendorError` on any failure."""
    log = log or (lambda msg: print(f"vendor_wheels: {msg}", file=sys.stderr))
    rt = rt or runtime_for(out / "index.html", installed_pep0723())
    fresh: list[tuple[Path, Path]] = []
    written: list[Path] = []
    cache_was_there, done = cache.is_dir(), False
    if cache_was_there:
        _sweep_stale_parts(cache)
    try:
        _vendor_with(load_index(rt, cache, log, fresh), entry, out, cache, rt, log, written)
        for new, cached in fresh:            # every wheel this build needs is secured
            try:
                os.replace(new, cached)
            except OSError as exc:
                raise VendorError(f"cannot write {cached}: {_why(exc)}") from exc
        done = True
        return written
    finally:
        for new, _ in fresh:
            _discard(new)
        if not done:
            # Never leave a half-vendored out/: take back the wheels this run
            # copied there, and the folders that held only them.
            for target in written:
                _discard(target)
                _remove_empty([*target.parents][:len(target.relative_to(out).parts) - 1])
            if not cache_was_there:
                _remove_empty([cache])       # a cache root this failed run made


def _vendor_with(index: dict, entry: Path, out: Path, cache: Path, rt: Runtime,
                 log, written: list[Path]) -> None:
    """`vendor`'s work once the index is in hand; every file copied into
    `out/` is added to `written` as it lands."""
    api = api_tag(rt, cache, log)
    base = str(index.get("-CDN-", rt.pkg_base))
    base = base if base.endswith("/") else base + "/"

    try:
        asked, excluded = block_requests(entry.read_text(encoding="utf-8"), rt)
        imported = entry_imports(entry)
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as exc:
        raise VendorError(f"cannot read the entry {entry}: {_why(exc)}") from exc
    wanted = sorted(imported) + asked
    pending = [(name, False) for name in wanted]       # (name, a dependency?)
    # The runtime puts a `!name` in its HISTORY, which `pip_install` then
    # treats as installed: compared, as there, against the remapped key.
    seen: set[str] = set(excluded)
    while pending:
        name, is_dep = pending.pop(0)
        key = remap(name, rt.mapping)
        if key in seen:
            continue
        seen.add(key)
        path = resolve(index, name, rt, api)
        if path is None:
            if is_dep:
                log(f"{name}: not in the pygbag index; the runtime fetches it from PyPI")
            continue
        if not _safe_relative(path):
            raise VendorError(f"the index names an unsafe wheel path for {name}: {path!r}")
        cached = cache / WHEELS_DIR / path       # apart from the helper's own files
        if not (cached.exists() and _valid_wheel(cached)):
            _download(base + path, cached, _valid_wheel, "wheel")
        target = out / rt.local_folder / path
        _write_atomic(target, lambda p, src=cached: shutil.copyfile(src, p))
        print(f"vendor_wheels: {name} -> {target}")
        written.append(target)
        pending += [(dep, True) for dep in wheel_requires(cached)]
    if not written:
        raise VendorError(f"{entry} needs nothing the pygbag index names; "
                          "pygbag would load no pygame")
    print(f"vendor_wheels: pages at {rt.local_prefix}... fetch these from {rt.local_base}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--entry", type=Path, required=True, help="the pygbag entry script (main.py)")
    ap.add_argument("--out", type=Path, required=True,
                    help="the built bundle folder to serve (holds index.html)")
    ap.add_argument("--cache", type=Path, required=True, help="where downloads are kept")
    args = ap.parse_args(argv)
    try:
        vendor(args.entry, args.out, args.cache)
    except VendorError as exc:
        print(f"vendor_wheels: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
