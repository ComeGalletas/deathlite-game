"""The two sprite caches an enemy's draw leans on in a fight, replayed on
the fight's own requests (RND-010.3, `crowd_draw_journal.md`).

    python -m tools.benchmarks.sprite_caches --live 150 --elapsed 300
    SDL_VIDEODRIVER=windows python -m tools.benchmarks.sprite_caches --live 250 --elapsed 600

A primed enemy is drawn washed in its element (`element_fx.washed`) and a
hurt one tinted red (`rendering.hit_tinted`). Each makes its copy of the
frame once and keeps it, keyed on the frame. The tint cache is a dict
that empties itself whole when it holds 128. The wash cache was one too,
at 512, when RND-010.3 measured it; since RND-010.4 it is an LRU of
1536. A frame the cache no longer holds is copied again.

The scene is `draw_variants --elements`'s: `layer_probes.packed_scene`
with the hero fighting, every enemy primed. Every request the draw makes
to either cache over `--frames` frames is recorded, the hero jittering
on its anchor as `spawn_stress.run` does. What the draw asks for does not
depend on what a cache holds (a hit and a miss give the same pixels, and
nothing the draw changes feeds back into what it asks of the caches;
`RequestTests` pins it), so the one recording is replayed through
each policy, whichever the game now uses: emptying whole when full, and
an LRU that drops only the entry used longest ago, at each of `--wash-caps` and
`--tint-caps`. Printed per cache and cap: the misses a frame and the
worst frame's, over the frames from `--warm` on (the game's caches are
warm by then), how many times the game's policy emptied the cache in
those frames, and the most memory the replayed cache held at any point
(each copy's rows times its height). Then what emptying a full cache
costs (the game's drops its every copy at once; in the game the ghost
cache may still hold some), and what one miss and one hit cost:
every distinct source washed (or tinted) with the cache emptied, then
again with each one held, `--passes` times over, each pass on a fresh
cache after the last one's copies are dropped; the median pass and the
range are printed, the first pass (the allocator's first touch) included
in the range.

The counts depend on what is in view, so they are the screen's only with
`SDL_VIDEODRIVER=windows` (in bash; in PowerShell set it first); the
costs are the display surface's format either way.
"""
from __future__ import annotations

import argparse
import contextlib
import time
from collections import OrderedDict

from tools.benchmarks import layer_probes as LP
from tools.benchmarks import spawn_stress as S


def _modules():
    from game.states.playing.visual import elements as fx
    from game.states.playing.visual import rendering as R
    return fx, R


def nbytes(frame) -> int:
    """The pixel memory a copy of `frame` holds: `Surface.copy` keeps the
    format, so its rows are as long as the source's (`get_pitch`)."""
    return frame.get_pitch() * frame.get_height()


def record(ps, frames: int) -> dict:
    """Every request the draw makes to the two caches over `frames` frames
    of `spawn_stress.run`. Returns `{"wash": events, "tint": events,
    "sources": {...}}`: an event is `(frame, key, bytes)`, the key the
    cache's own, the bytes a copy of the frame holds (`nbytes`); `sources` maps each
    key to the `(frame, element)` it was asked for, which also keeps the
    frame alive so its id stays its own. The caches are called through:
    the game draws as it would."""
    fx, R = _modules()
    real_tint, real_wash = R.hit_tinted, fx.washed
    out = {"wash": [], "tint": [], "sources": {}}
    now = [0]

    def tint(frame):
        key = ("tint", id(frame))
        out["tint"].append((now[0], key, nbytes(frame)))
        out["sources"].setdefault(key, (frame, None))
        return real_tint(frame)

    def wash(frame, element, profiles=None):
        if element and frame is not None:
            key = ("wash", id(frame), int(element))
            out["wash"].append((now[0], key, nbytes(frame)))
            out["sources"].setdefault(key, (frame, element))
        return real_wash(frame, element, profiles)

    def tick():
        now[0] += 1

    R.hit_tinted, fx.washed = tint, wash
    try:
        S.run(ps, frames, render=True, after_draw=tick)
    finally:
        R.hit_tinted, fx.washed = real_tint, real_wash
    return out


def replay(events: list, frames: int, cap: int, lru: bool, warm: int = 0) -> dict:
    """`events` through a cache of `cap` entries: the game's (empty it
    whole when full, then add) or an LRU (drop the entry used longest
    ago). Returns `per`, the misses in each frame; `avg` and `worst`,
    their mean and most over the frames from `warm` on; `clears`, the
    times the cache emptied whole in those frames; and `peak`, the most
    bytes the cache held at any point of the whole recording."""
    cache: OrderedDict = OrderedDict()      # key -> the bytes its copy holds
    per = [0] * frames
    emptied = [0] * frames
    held = peak = 0
    for f, key, nbytes in events:
        if key in cache:
            if lru:
                cache.move_to_end(key)
            continue
        per[f] += 1
        if len(cache) >= cap:
            if lru:
                held -= cache.popitem(last=False)[1]
            else:
                cache.clear()
                emptied[f] += 1
                held = 0
        cache[key] = nbytes
        held += nbytes
        peak = max(peak, held)
    tail = per[warm:]
    return {"per": per, "avg": sum(tail) / len(tail), "worst": max(tail),
            "clears": sum(emptied[warm:]), "peak": peak}


@contextlib.contextmanager
def _empty(module, cache: str, cap: str, room: int):
    """`module`'s cache swapped for an empty one with room for `room`, and
    the game's put back after."""
    saved = getattr(module, cache), getattr(module, cap)
    setattr(module, cache, type(saved[0])())     # the game's own kind: the wash cache is an LRU
    setattr(module, cap, room)
    try:
        yield
    finally:
        setattr(module, cache, saved[0])
        setattr(module, cap, saved[1])


def miss_cost(name: str, sources: dict, passes: int = 5) -> dict | None:
    """`name`'s ("wash" or "tint") microseconds for a miss and a hit,
    one figure per pass: every source of that cache washed or tinted with
    the cache empty, then again with each one held. Each pass gets a
    fresh cache, the last pass's copies dropped with its own, so after the
    first the allocator has memory to reuse, as it has in play. Returns
    `{"miss": [...], "hit": [...]}`, the passes in order; the game's
    cache is left as found. None when the recording asked nothing of it."""
    fx, R = _modules()
    todo = [src for key, src in sources.items() if key[0] == name]
    if not todo:
        return None
    if name == "wash":
        module, call = fx, lambda f, el: fx.washed(f, el)
        names = ("_WASH_CACHE", "_WASH_CACHE_CAP")
    else:
        module, call = R, lambda f, el: R.hit_tinted(f)
        names = ("_TINT_CACHE", "_TINT_CACHE_CAP")
    out = {"miss": [], "hit": []}
    for _ in range(passes):
        with _empty(module, *names, len(todo) + 1):
            t0 = time.perf_counter()
            for frame, element in todo:
                call(frame, element)
            t1 = time.perf_counter()
            for frame, element in todo:
                call(frame, element)
            t2 = time.perf_counter()
        out["miss"].append((t1 - t0) / len(todo) * 1e6)
        out["hit"].append((t2 - t1) / len(todo) * 1e6)
    return out


def clear_cost(name: str, sources: dict, entries: int, passes: int = 5) -> dict | None:
    """Milliseconds to empty a full cache, as the game's does when it
    reaches its cap: `entries` copies made (from as many distinct sources
    as there are, up to `entries`) in a fresh cache, then the dict cleared,
    which frees every copy at once here, where nothing else holds them
    (in the game the ghost cache may). One figure per pass; `entries` is how
    many it held. The game's cache is left as found. None when the
    recording asked nothing of it."""
    fx, R = _modules()
    todo = [src for key, src in sources.items() if key[0] == name][:entries]
    if not todo:
        return None
    if name == "wash":
        module, call = fx, lambda f, el: fx.washed(f, el)
        names = ("_WASH_CACHE", "_WASH_CACHE_CAP")
    else:
        module, call = R, lambda f, el: R.hit_tinted(f)
        names = ("_TINT_CACHE", "_TINT_CACHE_CAP")
    out = {"ms": [], "entries": len(todo)}
    for _ in range(passes):
        with _empty(module, *names, len(todo) + 1):
            for frame, element in todo:
                call(frame, element)
            cache = getattr(module, names[0])
            t0 = time.perf_counter()
            cache.clear()
            out["ms"].append((time.perf_counter() - t0) * 1000.0)
    return out


def _p50(values: list) -> float:
    s = sorted(values)
    return s[len(s) // 2]


def report(name: str, events: list, frames: int, warm: int, game_cap: int, caps: list,
           cost: dict | None, clear: dict | None = None) -> list[str]:
    if not events:
        return [f"  {name}: nothing asked of it"]
    asked = sum(1 for e in events if e[0] >= warm)
    sizes = {k: b for _f, k, b in events}
    lines = [(f"  {name}: {asked / (frames - warm):.1f} requests a frame, "
              f"{len(sizes)} distinct frames, the median one {_p50(list(sizes.values())) / 1000:.1f} KB; "
              f"the game's cap {game_cap}, frames {warm} to {frames}")]
    for cap in caps:
        c = replay(events, frames, cap, lru=False, warm=warm)
        lr = replay(events, frames, cap, lru=True, warm=warm)
        lines.append(f"    cap {cap:5d}: emptied when full {c['avg']:6.2f} misses a frame, worst "
                     f"{c['worst']:4d}, emptied {c['clears']:3d} times, held at most "
                     f"{c['peak'] / 1e6:5.1f} MB  |  LRU {lr['avg']:6.2f}, worst {lr['worst']:4d}, "
                     f"held at most {lr['peak'] / 1e6:5.1f} MB")
    if cost is not None:
        m, h = cost["miss"], cost["hit"]
        lines.append(f"    a miss {_p50(m):.1f} us ({min(m):.1f} to {max(m):.1f}), a hit "
                     f"{_p50(h):.2f} us ({min(h):.2f} to {max(h):.2f}), over {len(m)} passes")
    if clear is not None:
        ms = clear["ms"]
        lines.append(f"    emptying a cache of {clear['entries']}: {_p50(ms):.2f} ms "
                     f"({min(ms):.2f} to {max(ms):.2f}), over {len(ms)} passes")
    return lines


def _caps(text: str) -> list[int]:
    caps = [int(c) for c in text.split(",") if c]
    if not caps or min(caps) < 1:
        raise argparse.ArgumentTypeError(f"caps must be 1 or more: {text!r}")
    return caps


def parse(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=35, help="the world's seed")
    ap.add_argument("--live", type=int, required=True,
                    help="as spawn_stress --live; needs --elapsed (N - 100) * 4")
    ap.add_argument("--elapsed", type=float, required=True, help="the run clock in seconds")
    ap.add_argument("--dormant", type=int, default=400, help="enemy records on the other islands")
    ap.add_argument("--frames", type=int, default=900, help="frames recorded")
    ap.add_argument("--warm", type=int, default=300,
                    help="frames left out of the averages while the replayed caches fill")
    ap.add_argument("--wash-caps", type=_caps, default=[512, 768, 1024, 1536, 2048])
    ap.add_argument("--tint-caps", type=_caps, default=[128, 256, 512])
    ap.add_argument("--passes", type=int, default=5, help="passes timing a miss and a hit")
    args = ap.parse_args(argv)
    if not 0 <= args.warm < args.frames:
        ap.error("--warm must be 0 or more and below --frames")
    if args.passes < 1:
        ap.error("--passes must be 1 or more")
    return args


def main(argv=None, save_path: str | None = None) -> int:
    args = parse(argv)
    fx, R = _modules()
    _game, ps = LP.packed_scene(args.seed, args.live, args.dormant, args.elapsed, save_path,
                                elements=True)
    rec = record(ps, args.frames)
    print(f"  sprite caches, the hero fighting: {len(ps.enemies)} alive, {args.frames} frames")
    for name, game_cap, caps in (("wash", fx._WASH_CACHE_CAP, args.wash_caps),
                                 ("tint", R._TINT_CACHE_CAP, args.tint_caps)):
        print("\n".join(report(name, rec[name], args.frames, args.warm, game_cap, caps,
                               miss_cost(name, rec["sources"], args.passes),
                               clear_cost(name, rec["sources"], game_cap, args.passes))))
    print(f"  boss at the end: {S.boss_state(ps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
