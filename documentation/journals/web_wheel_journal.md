# Web build: vendor the wheels a static host needs

**ID:** BLD-006 · **Systems:** BLD · **Type:** bug · **Branch:**
`ComeGalletas/web-wheel-vendor-5be9212c` (session worktree
`.claude/worktrees/web-hands-on-test`, from `origin/main` at `dbde8ac`, rebased on `6384fa3`, D5) ·
**Started:** 2026-10-02

## Requirement (owner, 2026-10-02)

- **Objective:** a build made by `dist/web/build.sh` runs when served by a
  plain static server, `python -m http.server -d dist/web/out 8000`.
- **Details:**
  - The owner reported "the server is not running the game properly". The
    server log showed the cause: the page loads and the apk is served
    (200), then `GET /cdn/cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl`
    returns **404**. On localhost pygbag's loader runs in "DEV MODE" and
    fetches wheels from `http://localhost:8000/cdn/`; pygbag's own dev
    server proxies that path, a static server does not. pygbag then prints
    `INVALID pygame ... File or stream is not seekable` and stops on
    `OSError: [Errno 8] Bad file descriptor`.
  - The earlier hands-on builds worked because the wheel had been copied
    into `out/cdn/cp312/` by hand. `build.sh` starts with `rm -rf out`, so
    every rebuild (the BLD-004 ones included) removed it.
  - With the wheel put back by hand, the same page booted to the menu in
    Chrome (2026-10-02).
  - The fix is the one `documentation/plans/web_plan.md` §2a planned:
    vendor the wheel in `build.sh`, its name read from pygbag's index
    rather than hard-coded.
- **Constraint:**
  - Nothing the build hard-codes may go stale on a pygbag upgrade: the
    wheel's name and the list of wheels come from the installed pygbag and
    its CDN index (owner rule: no stale duplicated references).
  - `serve.sh` is unchanged: pygbag's dev server already serves `/cdn/`.
  - The game code and the bundle's contents are unchanged.

## Confirmed reading

- **How pygbag picks a wheel** (`pygbag/support/cross/aio/pep0723.py`
  `async_repos`, 0.9.3): the runtime fetches
  `https://pygame-web.github.io/cdn/index-<pygbag version>-<abi>.json`, a map
  from import name to a wheel path such as
  `cp312/pygame_ce-2.5.7-<abi>-<abi>-<api>.whl`, and fills `<abi>` with
  `cp<major><minor>` of the browser's Python and `<api>` with its
  `HOST_GNU_TYPE` (`wasm32-bi-emscripten`, dashes to underscores). The path
  is fetched relative to the page's `cdn/` (localhost) or the CDN.
- **Which wheels:** pygbag scans the entry file's own imports
  (`journals/pygbag.md`, W5: `main.py` needs a bare `import pygame` for this
  reason). `main.py`'s third-party imports that the index names are the
  wheels a static host must serve. Today that is `pygame` alone.
- **The Python version** is pygbag's `--PYBUILD`, default
  `pygbag.app.DEFAULT_PYBUILD` ("3.12"); `build.sh` passes none. *(The helper
  reads it from the built page's `data-python`, which records the `--PYBUILD`
  actually used: critic round 2.)*

## Decisions

- **BLD-006.D1 — a small Python helper, `dist/web/vendor_wheels.py`**
  (builder). Deterministic work goes in a script with tests, not in shell:
  it reads the pygbag version and default Python from the installed
  pygbag, fetches the index, lists `main.py`'s imports, resolves each one
  the index names, and copies the wheel into `out/cdn/<path>`. `build.sh`
  calls it after copying the bundle. `/dist` is already outside the bundle.
  *(As built after the critic rounds: the Python tag and runtime base come
  from the built `out/index.html`, the rest from the installed pygbag's
  `pep0723.py` and the CDN, and the folder from pygbag's `rewritecdn`; see
  rounds 1 to 3 below.)*
- **BLD-006.D2 — a cache outside `out/`** (builder): downloads land in
  `build/web-cache/cdn/` (pygbag's own cache folder, gitignored), so a
  rebuild does not download the wheel again and an offline rebuild with a
  cache still works. A download is written to a `.part` file and renamed,
  so a failed one never leaves a truncated wheel behind; any failure stops
  the build with the URL that failed. *(Revised after critic round 1: the
  index is re-read on every build on purpose, because the browser reads the
  live index and the vendored wheel must be the one it names; and a
  download replaces a cached file only once validated, an index as JSON and
  a wheel as a zip with `.dist-info/METADATA`, so a bad response cannot
  poison the cache.)*
- **BLD-006.D3 — the `<api>` tag is a constant in the helper**
  (`wasm32_bi_emscripten`, builder): it is the browser runtime's
  `HOST_GNU_TYPE`, which no local Python can report. Stated where it is
  defined, with the pygbag source it mirrors. *(Superseded after critic
  round 1, which named it and the CDN base as hard-coded values a pygbag
  upgrade could make stale. As built after the later rounds: the tag is read
  from the runtime's own `main.data` and cached, with that file's stamp
  (ETag, Last-Modified, length), in `api-<16-hex hash of runtime base and
  Python>.txt`; it is read again when a HEAD shows the stamp changed or
  gives none. From the installed `pep0723.py` the helper parses the package
  base, the renaming table, the index versions, `rewritecdn` and the address
  prefix that selects it, and compiles and runs pygbag's own
  `read_dependency_block_723`; the Python tag and runtime base come from
  the built page.)*
- **BLD-006.D5 — renumbered from BLD-005** (builder): PR #65, merged after
  this branch began, took BLD-005 for the desktop build. Every reference on
  this branch was moved to BLD-006 before its first push.
- **BLD-006.D4 — where the wheel comes from depends on the page's address;
  the docs say so** (builder, found while verifying). pygbag 0.9.3
  (`support/cross/aio/pep0723.py`, `async_repos`) rewrites every wheel's
  base to `http://localhost:8000/cdn/` when the page's URL starts with
  `http://localhost:8`, with port 8000 hard-coded; otherwise it uses the
  index's `-CDN-`, the public CDN. Measured in Chrome on 2026-10-02 against
  the same `out/`:
  - `localhost:8000`: the wheel from the page's `cdn/`, 404 before BLD-006,
    200 after; boots.
  - `localhost:8001`: the wheel requested from `localhost:8000/cdn/`
    ("Failed to fetch", another origin); grey canvas. No vendoring can fix
    this, so the README says to use port 8000.
  - `127.0.0.1:8001`: the wheel from `pygame-web.github.io/cdn/` (200,
    1,527,290 bytes); boots with nothing vendored.
  So the old premise that "a static host 404s on the wheel" (BLD-003.6,
  `web_plan.md` §1 and §2, `pending_plans.md` §7, `pygbag.md`) was a
  `localhost` measurement: a real host takes the public-CDN branch and the
  W9 Pages deploy does not need the vendored copy. Vendoring stays, for the
  owner's local `python -m http.server -d dist/web/out 8000` check, which is
  this requirement. The docs are corrected in place, dated.

## Plan

1. Journal and index (this file); BLD-004.D3 recorded as decided.
2. `dist/web/vendor_wheels.py` and the call in `build.sh`. Tests in
   `tests/devtools/test_vendor_wheels.py`, with no network: name resolution
   from a fixture index, the import scan of `main.py`, the cache and offline
   paths, a failed download leaving nothing behind, and `build.sh` calling
   the helper after the copy.
3. A real `build.sh` run, the static server, Chrome to the menu with no 404
   in the server log; docs; one cold critic pass; close.

## Critic rubric (frozen before building)

1. After `dist/web/build.sh` as the owner runs it, `python -m http.server
   -d dist/web/out 8000` serves a page that boots to the menu in Chrome, and
   the server log shows no 404. Run, not reasoned about.
2. Nothing about the wheel is hard-coded that a pygbag upgrade would make
   stale: its version comes from pygbag's index, the Python tag from the
   installed pygbag, the list of wheels from `main.py`'s imports. Tests show
   the resolution against a fixture index.
3. A rebuild does not download again; an offline rebuild with a cache
   works; a failed download fails the build loudly and leaves no partial
   wheel in the cache or in `out/`. Tested.
4. Every doc that describes serving the web build, the wheel, or vendoring
   agrees with the code (`dist/web/README.md`, `documentation/plans/web_plan.md`,
   `documentation/plans/pending_plans.md`, `documentation/journals/pygbag.md`,
   `dist/README.md`).

*(The rubric stays as frozen. Two notes on how later rounds read it: item
2's "the Python tag from the installed pygbag" is met more strictly by
reading it from the page pygbag built (round 2), which follows a
`--PYBUILD` the installed default would not; and the critics from round 2
on also held items 3 and 4 to the cases they found (non-index JSON,
protocol errors, damaged members, the PEP 723 reader), which the work then
met rather than argued down.)*

## Tasks

- [x] BLD-006.1 — journal, index entry, BLD-004.D3 recorded
- [x] BLD-006.2 — `vendor_wheels.py`, `build.sh` calls it, tests
- [x] BLD-006.3 — real build, static server in Chrome, docs, critic, close

## Progress

### BLD-006.2 — the helper, `build.sh`, tests (2026-10-02; the first version, reworked after critic rounds 1 and 2 below)

- `dist/web/vendor_wheels.py`: `pygbag_tags()` (version and abi from the
  installed pygbag), `entry_imports()` (`main.py`'s absolute top-level
  imports, via `ast`), `resolve()` (the index entries those imports name,
  `<abi>`/`<api>` filled, non-wheel keys such as `-CDN-` skipped),
  `load_index()` (fresh when online, the cached copy when not), `vendor()`
  (downloads from the index's own `-CDN-` base through a `.part` file, checks
  it is a zip, caches it, copies it to `out/cdn/<path>`). Any failure is a
  `VendorError` naming the URL; the command line exits 1.
- `dist/web/build.sh` calls it right after `cp -r ../../build/web out`,
  under its existing `set -e`.
- `tests/devtools/test_vendor_wheels.py`, 20 tests, no network (a `file://`
  fake CDN, and a guard that fails any other URL; the first run without it
  found `vendor()`'s `cdn=CDN` default bound at definition, so a patched
  `CDN` still reached the real CDN; the default is now late-bound).
  The real `main.py` resolves to exactly the wheel the static server 404'd
  on. Fifteen mutations of the helper and `build.sh` each fail the module.

### BLD-006.3 — the real build, the browser, docs (2026-10-02)

- `dist/web/build.sh` as the owner runs it (only `PYTHON` set to the
  venv): exit 0, `vendor_wheels: pygame -> out\cdn\cp312\pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl`;
  the wheel and the index cached in `build/web-cache/cdn/`; git status
  clean.
- `python -m http.server -d dist/web/out 8000`, Chrome at
  `http://localhost:8000/`: the menu. The server log for the wheel: 404 at
  10:51:07 and 10:51:51 (before), 200 at 10:58:57 after the build, 304 on
  the next load. The other two addresses: D4.
- Docs: `dist/web/README.md` (the serving rules by address, the serve
  command, the files table, Deploy), `dist/README.md`,
  `FUNCTIONAL_README.md`, `plans/web_plan.md` (header, §2 note, §6 row),
  `plans/pending_plans.md` (§7), `journals/pygbag.md` (TODO note, the W9
  finding, the ignore-list entry).

**Critic round 1 (cold, rubric only): FAIL on items 2 to 4.** Item 1
passed: it ran `build.sh` in place, served on 8000 and reached the menu in
Chrome with 0 404s, and confirmed the address rule in Chrome (`127.0.0.1`
took the public CDN, `localhost:8000` the local copy). Findings and fixes:

1. *ID collision*: PR #65 took BLD-005 after this branch began. D5:
   renumbered to BLD-006, branch rebased on `6384fa3`, index next-free
   BLD-007.
2. *Cache poisoning*: a non-JSON 200 for the index replaced the cached
   one, breaking later offline builds. Every download is now validated on
   its `.part` file before it replaces anything (D2).
3. *"A rebuild downloads nothing" was false*: the index is re-read each
   build, now on purpose and stated so (D2); a test pins the exact fetches
   of a first build (index, runtime data, wheel) and of a rebuild (index).
4. *`API_TAG` and the CDN base were hard-coded*: D3 superseded; the helper
   reads `pep0723.py` (package base, renaming table, PEP 723 pattern,
   index versions, all merged as `async_repos` does) and the runtime's
   `main.data` (the target, once). The real build derived
   `wasm32_bi_emscripten` from it.
5. *An old `out/` goes stale when pygame-web changes the index*: stated in
   `dist/web/README.md`, with the Ctrl+Shift+R tip for cached files
   (its note 9).
6. *Index versions came from `pygbag.VERSION`, the runtime loops over its
   own tuple*: read from `pep0723.py` now (4).
7. *Dependencies not followed*: `Requires-Dist` (extras and extra-only
   lines skipped, as the runtime does) and the entry's PEP 723 `script`
   block are followed; index entries are vendored, the rest are logged as
   PyPI fetches, which no local server affects.
8. *An empty zip passed as a wheel*: a wheel needs `.dist-info/METADATA`.
9. *Doc wording*: "localhost:8xxx" became the exact prefix rule
   (`http://localhost:8`, port 8000 fixed), the 8001 case reads "fails to
   fetch" rather than 404, and "relative to the page" holds on 8000 only;
   the helper's docstring no longer says "the page's own `cdn/`" in
   general.

Tests after round 1: 33 in `tests/devtools/test_vendor_wheels.py`, still
with no network. Mutation check, 25 breaks (the placeholders, the remap,
PEP 723 and `Requires-Dist` following, each validation, the cache, the
offline fallback, the `-CDN-` base, the cached target, an ambiguous
target, the runtime data kept, index versions, the `pep0723.py` parse, an
empty wheel list, the exit code, `build.sh`'s call and its order): all
fail the module. The one that first survived, reading only the first
index version, got its test (two indexes, the later one winning).

- Real builds after round 1, `build.sh` as it stands: the first printed
  `reading the runtime's target from https://pygame-web.github.io/cdn/0.9.3/cpython312/main.data (once)`
  and cached `api-0.9.3-cp312.txt` (`wasm32_bi_emscripten`; renamed since to `api-<16-hex hash>.txt` holding the tag and the runtime stamp, rounds 2, 3 and 7); the second
  did not read it again. Both vendored
  `cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl`.
- `python -m http.server -d dist/web/out 8000`, Chrome at
  `http://localhost:8000/` with its cache refreshed for the bundle and the
  wheel: the menu; the server log for the session has 0 404s (200 on the
  refreshed files, 304 on the reload).

**Critic round 2 (cold, rubric only): FAIL on items 2 to 4.** Item 1
passed again (menu in Chrome, no 404 from the page; a cold real run
produced the same wheel and target). Its probes, and the fixes:

1. *A JSON 200 that is not an index* (`{"message": "rate limited"}`)
   replaced the cached index. An index must now be a JSON object with a
   `-CDN-` string and at least one `.whl` value (`_valid_index`); a test
   feeds an HTML page, a JSON error, JSON naming no wheel and a JSON list,
   then builds offline.
2. *`out/cdn/` copied pygbag's `rewritecdn` literal without reading it*:
   `parse_pep0723` now reads `rewritecdn` and the `startswith` prefix that
   selects it, and the folder is that URL's path (`Runtime.local_folder`);
   a moved `rewritecdn` moves the folder, a missing one stops the build.
3. *`pygbag.md` "Local test" served `build/web` statically* (it 404s) with
   W8-era paths: rewritten, dated.
4. *The README said everything comes from the installed pygbag*: it now
   says which fact comes from where (page, pygbag, CDN).
5. *`http.client` errors escaped*: caught with the rest; a `BadStatusLine`
   on the index falls back to the cache, an `IncompleteRead` on a wheel
   fails naming the URL. Both tested.
6. *The installed `support/` stands in for the CDN's runtime code*: the
   docstring says so.
7. *Python tag and runtime base came from pygbag's defaults*: they come
   from the built `out/index.html` (`data-python`, `cdn :`), so a
   `--PYBUILD` or `--cdn` given to pygbag is followed; a page without them,
   or no page, stops the build.
8. *Journal staleness*: the header names the rebase, the first-version
   progress entry is marked as such.

Tests after round 2: 42 in the module (7 subtests). Mutation check, 33
breaks including the seven new ones (index shape, index with no wheel,
`HTTPException`, `rewritecdn` and the local folder, the page's Python and
runtime, a missing page), each fails the module; the script now reports a
mutation whose pattern no longer matches as NO-OP instead of a pass (an
earlier run of the stale script showed two such no-ops). Real build:
`reading the runtime's target ... (once)`, the same wheel at
`out/cdn/cp312/`, and `pages at http://localhost:8... fetch these from
http://localhost:8000/cdn/`.

**Critic round 3 (cold, rubric only): items 1 and 2 PASS, 3 and 4 FAIL.**
Item 1 passed again (menu in Chrome, 0 404s, the `/cdn//cp312/` form pygbag's
`check_list` builds also resolves); an offline `build.sh` through a dead
proxy built from the cache. Findings and fixes:

1. *A wheel with a damaged member passed* (`_valid_wheel` read only the
   member list), was cached and reused for good; a damaged METADATA
   crashed after the file was cached. `_valid_wheel` now runs `testzip`
   (every member read back against its CRC) and treats any zip or zlib
   error as invalid; the same check guards a cached wheel before reuse.
   Tested: damaged payload, damaged METADATA, broken directory, as a
   download (refused, nothing kept) and as a cached file (fetched again).
2. *The PEP 723 handling did not match the runtime* (the runtime reads
   `# /// pyproject` and `[project]` too, through
   `read_dependency_block_723`; `BLOCK_RE_723` is never used). The helper
   now compiles pygbag's own `read_dependency_block_723` from the installed
   source and runs it as is, then treats entries as `parse_code` does: `!`
   excludes a package (the runtime marks it installed), anything else is
   the whole string lower-cased with dashes as underscores. Tested,
   including that a changed reader in pygbag's source changes the result.
3. *D2's "cannot poison the cache" was false*: true now, by 1.
4. *Corruption escaped as raw tracebacks*: covered by 1.
5. *A relative `-CDN-` passed*: an index needs an absolute `-CDN-` URL. An
   index-shaped body from the wrong source still cannot be told apart; the
   build then fails on the wheel and the next build repairs the cache
   (stated in `_valid_index`).
6. *The cached `<api>` was never revalidated*: it is stored with the
   runtime file's stamp (ETag, Last-Modified, length) and read again when a
   HEAD shows the file changed. A server refusing HEAD still builds (GET),
   then keeps the cached tag with a note; offline, the same.
7. *pygbag empties `build/web-cache/` on a version change*: stated in the
   README.
8. *Type `fix` is not an index type*: `bug`, as BLD-005.
9. *The rubric heading versus what the critics applied*: a note under the
   rubric; the round-1 cache file name is annotated.
10. *Concurrent builds shared `.part` names*: the name carries the process
    id.

Tests after round 3: 47 in the module (17 subtests). Mutation check, 43
breaks (the round-3 ones: the block reader, `!` exclusions, block names,
members not read back, zip errors escaping, a relative `-CDN-`, the stamp
ignored, the offline target, a HEAD refusal aborting a first build) all
fail the module, no NO-OP. One mutation first survived (a failed HEAD with
no cache raising at once): equivalent offline, but wrong for a server that
refuses HEAD, so the raise was removed and the HEAD-refusal test added.

- Real builds after round 3: the first read the runtime (stamp
  `"69b99c9a-65c141"|Tue, 17 Mar 2026 18:25:30 GMT|6668609`, target
  `wasm32_bi_emscripten`), the rebuild matched the stamp and read nothing
  but the index; both vendored the same wheel to `out/cdn/cp312/`.

**Critic round 4 (cold, rubric only): items 1 to 3 PASS, item 4 FAIL.** It
reached the menu in Chrome with 0 404s, built offline through a dead
proxy from the cache, and found the HEAD stamp stable. Findings and fixes:

1. *Two kinds of zip damage escaped as raw tracebacks*: a damaged
   compression method (`NotImplementedError`) or encryption flag
   (`RuntimeError`) in the central directory, as a download or as a cached
   wheel, so "any failure names the URL" and "a damaged file is fetched
   again" were false. `_valid_wheel` now treats any exception while reading
   the archive as invalid; both kinds join the damage tests (download
   refused, cached file fetched again).
2. *Deeply nested JSON as the index crashed with `RecursionError`*:
   `_valid_index` treats any parse failure as invalid; tested.
3. *A non-literal setting in a future `pep0723.py` would raise a raw
   `ValueError`*: `_literal` turns it into a `VendorError` naming the
   setting; tested.
4. *The dated status blocks of `pending_plans.md` still listed vendoring
   as open*: annotated as done, as `pygbag.md` was.
5. *D1 was not marked as superseded*: annotated.
6. *Index paths were joined without containment*: an absolute path or one
   with `..` is refused; tested.

Tests after round 4: 49 in the module (26 subtests). Mutation check: 46
breaks, all fail the module, no NO-OP (the four new ones: the round-3
exception tuple, the index parse tuple, an unguarded literal, an unsafe
path accepted).

**Critic round 5 (cold, rubric only): items 1 and 2 PASS, 3 and 4 FAIL on
narrow cases.** Menu in Chrome again with 0 404s; an offline run through a
dead proxy built from the cache; NaN, huge integers, a BOM, UTF-16, a
socket timeout, `RemoteDisconnected` and an SSL error all fell back
cleanly. Findings and fixes:

1. *A `-CDN-` that `urlparse` rejects* (`http://[::1/`) raised a raw
   `ValueError` from `_valid_index`: the check is guarded and the index is
   invalid.
2. *A `-CDN-` host `urlopen` cannot encode* (`http://a..b/`, an empty IDNA
   label) passed and later raised a raw `UnicodeError`: `_valid_index`
   encodes the host as IDNA and refuses it, and both transport `except`s
   (download and stamp) catch `ValueError` too, so such a URL becomes a
   `VendorError` naming it.
3. *The docstring said the target is "cached as a one-line file"*: it is
   the tag and the runtime's stamp; reworded.
- Taken from its notes: a Windows-rooted index path (`/x.whl`, which
  Windows reads as the drive root, and `C:x.whl`, `\srv\share\x.whl`,
  backslash `..`) is refused (`_safe_relative`, POSIX and Windows rules);
  the "Confirmed reading" Python line is annotated.

Tests after round 5: 51 in the module (37 subtests); the bad-index test now
checks the log per body (the earlier "any line" check let a mutation of
the urlparse guard pass, because `_download` also catches `ValueError`),
with a host-less and an `ftp` `-CDN-` added; a dropped connection or a bad
URL on the HEAD still builds. Mutation check: 52 breaks, all fail the
module, no NO-OP; the two transport `except` lines carry a comment so each
can be broken alone.

**Critic round 6 (cold, rubric only): items 1, 2 and 4 PASS, item 3 FAIL.**
It reached the menu in Chrome with 0 404s again, rebuilt against the real
CDN with only the index fetched and the runtime stamped, and built offline
with every request refused. Findings and fixes:

1. *`_download` made the cache folder before its `try`*: an index path
   with characters Windows refuses (`a?b`, `C:`, `a:b.whl`) raised a raw
   `OSError` / `ValueError`. Folder and `.part` name are made inside the
   `try`, so the failure is a `VendorError` naming the URL; tested with a
   file standing where the cache folder should be.
2. *Index paths whose parts end in a space or dot* (`.. `, `...`) passed
   and created folders Windows cannot delete, which would break pygbag's
   own `shutil.rmtree` of `build/web-cache/` on its next upgrade.
   `_safe_relative` is now an allow-list: `/`-separated parts of letters,
   digits and `._+-`, starting with a letter or digit, none ending in a
   dot (all 23 paths in the real 0.9.3 index fit); tested with fifteen bad
   shapes, checking that no folder was made in the cache.
- Taken from its notes: the copy into `out/` and the cached target are
  written through a `.part` and renamed (`_write_atomic`), so a full disk
  leaves no half wheel and fails as a `VendorError`; a `file:` `-CDN-` is
  only taken from an index read from `file:` (a remote index must name
  http(s)); a stamp with no ETag, Last-Modified or length cannot show a
  change, so the target is read again in that case. Each is tested.

Tests after round 6: 56 in the module (52 subtests). Mutation check: 57
breaks, all fail the module, no NO-OP; two first survived (a trailing-dot
part that otherwise fits the pattern, and `_download`'s folder made outside
its `try`) and got their tests.

**Critic round 7 (cold, rubric only): items 1, 2 and 4 PASS, item 3 FAIL
on "no stray folders".** Item 1 passed with a negative control as well:
the same `out/` without `cdn/` logged the wheel 404 and stopped on
`INVALID pygame ... not seekable` / `Bad file descriptor`, as the README
says. An offline run against the real page, pygbag and a copy of the real
cache vendored a byte-identical wheel. Findings and fixes:

1. *A failed download or write left empty folders in the cache*
   (`deep/er/` for a damaged body, `deep/er/still/` for a 404, `ok/` for an
   over-long folder name). `_download` and `_write_atomic` now note the
   folders they make (`_make_parents`) and remove them again, deepest
   first while empty, when the call fails (`_clean_up`); tested for the
   three cases, checking the cache holds no folder at all.
- Taken from its notes: a cached target that is not UTF-8 is treated as
  absent and read again; an entry with a syntax error or not UTF-8, a page
  that is not UTF-8 and a missing pygbag are each a `VendorError` naming
  what failed; the target's cache name is a 16-character hash of the
  runtime base and Python (an arbitrarily long `--cdn` still fits); the
  README says a server refusing HEAD keeps the cached target, and the
  `build.sh` comment names the HEAD it sends. Each is tested.

Tests after round 7: 62 in the module (57 subtests). Mutation check: 64
breaks, all fail the module, no NO-OP, none duplicated; the one that first
survived (the `page.exists()` check, redundant with the read's own
`VendorError`) is pinned by its message in the test.

**Critic round 8 (cold, rubric only): items 1 and 2 PASS, 3 and 4 FAIL.**
Menu in Chrome with 0 404s; the rebuild kept the cached wheel; an offline
run with the real page, pygbag and cache gave a byte-identical wheel; it
also confirmed `main.data` is compressed, so the installed `pep0723.py`
standing in for the CDN copy is justified. Findings and fixes:

1. *Windows device names passed the path rule* (`con.whl`, `aux/x.whl`,
   `nul/x.whl`...), and `nul` as a folder fooled `exists()`, leaving an
   empty `cp312/`. `_safe_relative` refuses any part whose name before the
   first dot is a device name (`con`, `prn`, `aux`, `nul`, `com0-9`,
   `lpt0-9`); `_make_parents` makes folders level by level and counts a
   level present only if `is_dir()`, checks each `mkdir` really made a
   folder (on Windows `mkdir("nul")` returns without making one), and the
   cleanup tries every folder it made (an `rmdir` only removes an empty
   one). Tested, including a direct download through a `nul` folder.
2. *A malformed `-CDN-` replaced the cached index* (a non-numeric or
   out-of-range port, whitespace, a NUL, CR/LF, a `-` host, a bad `%`
   escape), so a later offline rebuild failed. `_valid_base` refuses a
   base `urllib` could not fetch as written: whitespace or control
   characters, bad `%` escapes, a bad port, a user or password, a host
   that is not plain labels or an IP. Tested with those bodies and with
   real bases accepted (`pygame-web.github.io`, `localhost:8000`,
   `127.0.0.1:8001`, `[::1]:8000`, `%20` in the path).
3. *The docs claimed what 1 and 2 lacked*: true now; the docstrings name
   the device rule and the new index commit.
- Taken from its notes: a new index is kept as `<name>.new` and put in
  place only once every wheel this build needs from it is secured (round 12
  corrected "every wheel it names"), so an index whose needed wheel
  cannot be had never replaces one whose wheels are cached (tested, with
  the offline rebuild afterwards, and the normal replacement after a good
  build); any unexpected exception in a download, write or HEAD becomes a
  `VendorError` naming the URL or file (tested with `TypeError`,
  `LookupError`, `RuntimeError`); the import scan now takes `from .x
  import y` as `x`, as pygbag's `scan_imports` does; `pending_plans.md` §7
  says the Pages deploy should not need the wheel and that a real host is
  not verified; the stale old-format tag file was removed from the local
  cache.

Tests after round 8: 67 in the module (82 subtests). Mutation check: 71
breaks, all fail the module, no NO-OP. Two mutations first survived as a
pair (the `is_dir` check after `mkdir`, and the cleanup trying every
folder): each alone is enough for the `nul` case, so the pair is one
mutation that fails. One survived because the code was redundant (an empty
host already fails the label check); the redundant check was removed.

**Critic round 9 (cold, rubric only): items 1, 2 and 3 PASS, item 4 FAIL.**
Menu in Chrome with 0 404s; offline against the real page, pygbag and
cache gave a byte-identical wheel; its probes (a reset mid-body, a
dependency failing after the first wheel, a path over 260 characters,
HEAD up but GET down, Ctrl+C mid-download, `con1`, `conin$`, `com¹`, the
Kelvin sign) all ended cleanly. Findings and fixes:

1. *D3's annotation described an earlier version* (a one-line tag file,
   a parsed PEP 723 pattern): rewritten to the design as built.
2. *A tag-file name in the round-1 entry was out of date*: corrected to
   `api-<16-hex hash>.txt`.
3. *"Any failure is a VendorError" did not hold for two dependency-block
   shapes* (`dependencies = 5`, `project = "x"`, on which pygbag's own
   reader raises): any error from the reader is a `VendorError` naming the
   block; tested.
- Taken from its notes: the BLD-003.6 line in `web_frame_time_journal.md`
  that called the vendored wheel "the fix a Vercel or Pages deploy needs"
  is annotated; a `.part` file that cannot be removed (locked) no longer
  hides the real error; a `-CDN-` with port 0 or a dotted-number host that
  is not an IPv4 address is refused; the README names the no-stamp case.
- Left as known residuals, both loud if they ever bite: the index file
  name `index-<version>-<abi>.json` and the runtime path
  `cpython<XY>/main.data` are written in the helper rather than read from
  pygbag (a change would 404, and pygbag empties the cache on an upgrade);
  the `parse_code` and `install_pkg` rules for `!` exclusions, name
  normalising and `Requires-Dist` extras are mirrored in Python, not run
  from pygbag (they only touch dependency-block and `Requires-Dist` edge
  cases; this game imports only pygame).

Tests after round 9: 68 in the module (89 subtests). Mutation check: 74
breaks, all fail the module, no NO-OP.

**Critic round 10 (cold, rubric only): items 1 and 2 PASS, 3 and 4 FAIL
on one root cause.** Menu in Chrome with 0 404s; the vendored wheel's
sha256 matches the live CDN copy; a dozen failure probes against a real
local HTTP CDN each ended in a `VendorError` with nothing left behind.
Findings and fixes:

1. *Two cleanups were unguarded*: the `<index>.new` in `vendor()` and the
   runtime data file in `api_tag()`. A file held open on Windows (an
   indexer, a scanner) raised a raw `PermissionError` that hid the real
   `VendorError`, or failed a good build, and left the file behind. Every
   cleanup now goes through `_discard`, which leaves a locked file rather
   than raise; tested for a locked `.new` (failing and good builds) and a
   locked data file.
- Taken from its notes: a failed first run removes the cache root it
  made; a rename into the cache that fails names the cache file, not the
  download; any failure to import pygbag (it reconfigures stdout on
  import) is a `VendorError`; a `pep0723.py` that sets `rewritecdn` in two
  branches stops the build rather than picking one. Each is tested.

Tests after round 10: 74 in the module (91 subtests). Mutation check: 79
breaks, all fail the module, no NO-OP.

**Critic round 11 (cold, rubric only): items 1, 2 and 4 PASS, item 3 FAIL
on one point.** Menu in Chrome with 0 404s; a cold real build fetched the
index, HEAD and GET of the runtime, then the wheel; the rebuild only the
index and one HEAD; sixteen hostile index paths and five bad `-CDN-` bases
refused with nothing written. Finding and fix:

1. *A failed write into the cache inside `_download` read as "download
   failed" and did not name the file* (Windows drops the filename from an
   OSError's repr): with the cache path a file, no request was even made.
   `_download` now tells the three apart: making the folder or opening the
   `.part` is "cannot write <file>", reading the response is "download
   failed: <url>", writing a chunk is "cannot write <.part>", each with the
   error's text (which carries the path). Tested: a file where the cache
   folder goes, the cache itself a file (no request made), a full disk
   mid-download, a body cut off mid-read.
- Taken from its notes: `.part` files a killed run left are swept when
  older than an hour (a live build beside this one keeps its own); the
  `_valid_index` docstring says exactly when an index from the wrong source
  is kept (only once every wheel this build needs from it is secured; round
  12 corrected "every wheel it names"); `web_plan.md`
  §2's "only blocker" and "the whole fix" are marked as superseded.
- Known residuals, complete: the index file name and the
  `cpython<XY>/main.data` path (round 9); the page fields' patterns
  (`data-python`, `cdn :`) and the target's pattern `API_RE`, which fail
  with a `VendorError` if pygbag writes them differently; the `parse_code`
  and `install_pkg` rules mirrored in Python (round 9). None goes stale
  silently.

Tests after round 11: 78 in the module (91 subtests). Mutation check: 84
breaks, all fail the module, no NO-OP; the one that first survived (a
non-OSError while reading the body) got its test.

**Critic round 12 (cold, rubric only): items 1, 2 and 3 PASS, item 4
FAIL on one rule's wording.** Menu in Chrome and in the desktop browser
pane with no 404 from the page; nineteen hostile index paths and four
hostile `-CDN-` bases refused; a locked target or damaged cached wheel
named in its `VendorError`. Finding and fix:

1. *Four places said a new index is kept once "every wheel it names" is
   secured*; the code secures the wheels this build needs from it, which
   is what offline builds need (a probe committed an index also naming
   nonexistent `numpy` and `PIL` wheels, correctly). The module docstring,
   `load_index`, `_valid_index` and the round 8 and 11 lines now say so; a
   test pins it.
- Taken from its notes: the "Local test" note in `pygbag.md` gives the
  right dates for the moves (`web/` in W8, `dist/web/` on 2026-09-13); the
  W8-era GitHub Actions sketch there is marked out of date, with what
  changed; the two reads of files the run had just written (the merged
  index, the runtime data) are `VendorError`s if the file is locked by
  then. Tested.

Tests after round 12: 80 in the module (93 subtests). Mutation check: 86
breaks, all fail the module, no NO-OP.

**Critic round 13 (cold, rubric only): items 1 and 2 PASS, 3 and 4 FAIL.**
Menu in Chrome with 0 404s; the vendored wheel's sha256 matches the live
CDN copy; a rebuild logged only the index and one HEAD against the live
CDN. Finding and fix:

1. *Wheels were cached beside the helper's own files*, so an index path
   whose first part was one of their names (`index-0.9.3-cp312.json/...`,
   `main-<key>.data/...`) collided with them: a stray folder, and every
   later build failing until the cache was deleted by hand. Cached wheels
   now live in their own `wheels/` folder of the cache, which no index path
   can leave; tested for all four names, each followed by a build with the
   real index.
- Taken from its notes: a failed build takes back the wheels it had
  already copied into `out/` (and the folders that held only them), so a
  static server never serves a half-vendored `out/`; the fresh index is
  staged under a per-process name, so two builds sharing a cache never
  discard each other's. Both tested.
- Left as a known residual: a cached wheel is trusted by its path once it
  passes the zip and CRC check (pygbag's index carries no hashes); a
  valid wheel from a wrong source would stay until pygbag empties the
  cache on its next upgrade.
- The cache layout changed (wheels under `wheels/`), so the first build
  after this change downloads the wheel once more; the old `cp312/` folder
  is left for pygbag's own cache clear.

Tests after round 13: 83 in the module (97 subtests). Mutation check: 89
breaks, all fail the module, no NO-OP.

**Critic round 14 (cold, rubric only): PASS on all four items.** It built
with `build.sh`, served `out/` on port 8000 and reached the menu in Chrome
with no 404 (the page's wheel request a 304 from the vendored copy); a
first build made four requests (index, HEAD and GET of the runtime, wheel)
and a rebuild two (index, HEAD); offline rebuilds worked through the helper
and through `build.sh` behind a dead proxy; a forced-offline `build.sh` on
an empty cache exited 1 naming the index URL with nothing left behind; and
twenty hostile index paths, hostile `-CDN-` bases, bad bodies, colliding
file and folder names, a dependency failing after the first wheel was
copied, and bad entries all ended in a `VendorError` with no partial file
or stray folder in the cache or `out/`. Tests: 113 passed with every socket
blocked; ruff clean.

- Taken from its notes: every error message uses `_why` (the error's type
  and text, which keeps an OSError's file name on Windows).
- Its remaining notes, recorded as known residuals, none of which touches
  this game's build: `http.client` does not raise on a body cut short of
  its Content-Length, so "complete" means complete enough to validate
  (indexes and wheels are validated; the runtime data only needs the
  target pattern); behind a captive portal that answers HEAD with a new
  stamp, an otherwise offline build fails loudly at the target step rather
  than using the cached tag; a `Requires-Dist` name is tried as written
  before the runtime's remapped key, so a dependency the browser would
  fetch from PyPI could be vendored too (harmless, or a loud failure if it
  cannot be had); the tests parse a copy of `pep0723.py`'s shape, so drift
  in the real file is caught by a real build, which parsed it correctly in
  every run; the import scan also names stdlib and local modules, which
  only matters if the index ever gained such a key.

## Close (2026-10-02)

BLD-006 is done. `dist/web/build.sh` vendors the pygame-ce wheel into
`out/cdn/` through `dist/web/vendor_wheels.py`, so
`python -m http.server -d dist/web/out 8000` serves a page that boots to
the menu (the owner's report: a 404 on the wheel). Everything the helper
resolves comes from the installed pygbag, the built page and the CDN, as
the browser runtime resolves it; downloads are cached, validated and
cleaned up so a bad response or a failed run never poisons the cache or
leaves `out/` half done. Measuring it corrected an old premise: the wheel
404 is a `localhost:8xxx` effect, so a real host takes the public CDN and
the Pages deploy should not need vendoring (D4). 83 tests in the module,
89 mutations each caught; fourteen cold critic rounds, the last a pass.
