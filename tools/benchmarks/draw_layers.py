"""`PlayingState.draw`, timed layer by layer (RND-010.2, `crowd_draw_journal.md`).

    python -m tools.benchmarks.spawn_stress --live 200 --elapsed 400 --pack --layers

(`--elapsed`: the director seats 100 + 5 per 20 s of run clock on normal,
so a crowd of N needs `(N - 100) * 4` s; the harness says when it seated
fewer.)

`LayerTimer.install(ps)` wraps each layer's entry point on the live objects
(the painters `PlayingState` forwards to, the terrain renderer's passes, the
module functions the scene calls) and `uninstall` puts every one back. Each
wrapper records the time spent in its layer *excluding* the layers it calls.
A nested layer is named under its nearest named caller, one level up only:
`enemies/shade` is the tree shade laid over enemies, `player/shade` over the
hero, and a layer three deep (`flat` > `elemental` > `particles`) reads
`elemental/particles`. The root (`draw`) and the world (`world`) are left out
of names. What is not inside a named layer falls to its caller, so a
frame's parts add up to its whole draw time exactly:

* `draw`: the camera shake, `element_fx.begin_frame` and the dev overlays;
* `world`: the scene's lists and sorts (the actors', the per-terrace
  filtering and sorting); an items entry point's own list is its
  `<label>_list` row (`scenery_list`: the terrain's);
* `flat`: the painters lying on the ground (interactables, chests, hazards,
  cast markers, slam indicators and impacts, gems, potions, explosions,
  the sword's swing, dust trails);
* `player`: the hero's buff activation strips (`hero_fx`) and the
  invulnerability ring (on every frame in the stress harness, whose hero is
  invulnerable); the buff marks and banners over the hero are in
  `feedback`, with the hurt flash and the buff tint;
* `enemies`: each enemy's record for the ghost pass (and the copy of a
  shaded frame it keeps).

The wrappers cost time of their own: a call, two clock reads, the name and
the bookkeeping, much of it landing in the caller's row (`enemies` carries
its three nested wrappers per enemy, `world` each enemy wrapper's own
bookkeeping and the closures that wrap the items' draw functions). A no-op timed alone would
understate it, so nothing is calibrated: `spawn_stress --layers` draws every other
frame without the timers (`Alternate`), and the report states what the
timers added against those bare frames of the same crowd, and what that is
per timed call, measured in place for that run.
"""
from __future__ import annotations

import gc
import time
from collections import defaultdict

from tools.benchmarks.stats import percentile

# `(label, where, attribute)`: `where` names the object the attribute is
# looked up on at call time. Instance attributes shadow the class (the
# painters `PlayingState` forwards, the renderers' passes); module
# attributes are read by their callers at call time (`health_bars.draw`).
# Ordered roughly as a frame paints them; the report sorts by cost.
LAYERS = (
    ("draw", "ps", "draw"),
    ("world", "ps", "_draw_world"),
    ("water", "terrain", "draw_water"),
    ("ground", "terrain", "draw_ground_band"),
    ("scenery", "terrain", "banded_scenery"),         # ITEMS: its draw functions are timed
    ("villagers", "npcs", "actor_items"),             # ITEMS
    ("huts", "huts", "actor_items"),                  # ITEMS: fish huts and boats
    ("elemental_sort", "element_fx", "bands"),
    ("flat", "scene", "draw_flat_effects"),
    ("player_shots", "ps", "_draw_player_projectiles"),
    ("elemental", "element_fx", "draw_under"),
    ("enemies", "ps", "_draw_one_enemy"),
    ("boss", "ps", "_draw_boss"),
    ("player", "ps", "_draw_player"),
    ("summons", "ps", "_draw_one_summon"),
    ("death_fx", "ps", "_draw_death_fx"),
    ("spawn_fx", "ps", "_draw_spawn_fx"),
    ("shade", "terrain", "shade_character_frame"),
    ("hpbar", "health_bars", "draw"),
    ("marks", "status_marks", "draw"),
    ("ghost", "terrain", "ghost_pass"),
    ("projectiles", "ps", "_draw_hostile_projectiles"),
    ("particles", "particles", "draw"),
    ("numbers", "numbers", "draw"),
    ("reactions", "element_fx", "draw_reactions"),
    ("key_marker", "key_marker", "draw"),
    ("hints", "hints_draw", "draw"),
    ("hud", "hud", "draw"),
    ("feedback", "renderer", "feedback_overlays"),
)
# The layers whose entry point returns `(level, depth, draw_fn)` items the
# scene calls in its sort: the draw functions are timed as the layer, and
# the list's building as `<layer>_list`.
ITEMS = frozenset({"scenery", "villagers", "huts"})


class LayerTimer:
    """Exclusive draw time per layer, per frame. Install it on a built
    `PlayingState`, call `ps.draw` as usual, then `frame()` after each
    draw; `uninstall` restores every wrapped attribute. A draw that raises
    leaves nothing behind: its partial times are dropped."""

    def __init__(self) -> None:
        self.frames: list[dict] = []           # one {layer: ms} per frame
        self.calls: list[dict] = []            # one {layer: calls} per frame
        self._current: dict = defaultdict(float)
        self._count: dict = defaultdict(int)
        self._names: list[str] = []            # the open layers, outermost first
        self._child: list[float] = []          # time spent in each open layer's callees
        self._undo: list[tuple] = []           # (object, attribute, had its own, value)

    # --- wiring --------------------------------------------------------
    @staticmethod
    def _targets(ps) -> dict:
        from game.states.playing.visual import elements as element_fx
        from game.states.playing.visual import (
            health_bars,
            key_marker,
            scene,
            status_marks,
        )
        from game.states.playing.visual import hints as hints_draw
        return {"ps": ps, "terrain": ps.game_map.renderer, "renderer": ps.renderer,
                "element_fx": element_fx, "scene": scene, "health_bars": health_bars,
                "status_marks": status_marks, "particles": ps.run.particles,
                "numbers": ps.run.damage_numbers, "key_marker": key_marker,
                "hints_draw": hints_draw, "hud": ps.hud, "npcs": ps.npc_manager,
                "huts": ps.fish_hut_manager}

    @property
    def installed(self) -> bool:
        return bool(self._undo)

    def install(self, ps) -> LayerTimer:
        if self._undo:
            raise RuntimeError("already installed")
        targets = self._targets(ps)
        try:
            for label, where, attr in LAYERS:
                obj = targets[where]
                own = attr in vars(obj)
                original = getattr(obj, attr)
                self._undo.append((obj, attr, own, vars(obj)[attr] if own else None))
                wrap = self._wrap_items if label in ITEMS else self._wrap
                setattr(obj, attr, wrap(label, original))
        except BaseException:
            self.uninstall()                   # none of it half on
            raise
        return self

    def uninstall(self) -> None:
        for obj, attr, own, value in reversed(self._undo):
            if own:
                setattr(obj, attr, value)
            else:
                delattr(obj, attr)             # back to the class's own
        self._undo.clear()

    def _wrap(self, label: str, fn):
        clock = time.perf_counter

        def timed(*args, **kwargs):
            self._names.append(label)
            self._child.append(0.0)
            start = clock()
            failed = False
            try:
                return fn(*args, **kwargs)
            except BaseException:
                failed = True
                raise
            finally:
                spent = clock() - start
                inner = self._child.pop()
                key = "/".join(self._path())
                self._names.pop()
                self._current[key] += (spent - inner) * 1000.0
                self._count[key] += 1
                if self._child:
                    self._child[-1] += spent
                elif failed:
                    self._drop_partial()
        timed.__wrapped__ = fn
        return timed

    def _wrap_items(self, label: str, items_fn):
        """An entry point that returns `(level, depth, draw_fn)` items: each
        draw function is wrapped as `label` as the list is returned, and
        building the list is timed as `label_list` (the scenery's is the
        terrain's work, not the scene's)."""
        build = self._wrap(f"{label}_list", items_fn)

        def wrapped(*args, **kwargs):
            return [(lvl, depth, self._wrap(label, fn))
                    for lvl, depth, fn in build(*args, **kwargs)]
        wrapped.__wrapped__ = items_fn
        return wrapped

    def _path(self) -> list[str]:
        """The open layer's name under its nearest named caller, the root
        (`draw`) and the world (`world`) left out: `enemies/shade`, not
        `draw/world/enemies/shade`."""
        names = [n for n in self._names if n not in ("draw", "world")]
        if not names:
            return [self._names[-1]]
        return names[-2:] if len(names) > 1 else names

    def _drop_partial(self) -> None:
        self._current = defaultdict(float)
        self._count = defaultdict(int)

    # --- per frame ----------------------------------------------------
    def frame(self) -> dict:
        """Close the frame just drawn: its `{layer: exclusive ms}`."""
        if self._names:
            raise RuntimeError("frame() inside a draw")
        done = dict(self._current)
        self.frames.append(done)
        self.calls.append(dict(self._count))
        self._drop_partial()
        return done

    # --- the answer ---------------------------------------------------
    def summary(self) -> list[tuple]:
        """`(layer, p50, p90, mean)` per layer over the recorded frames, in
        ms, largest mean first; a layer absent from a frame counts 0 there."""
        keys = {k for f in self.frames for k in f}
        n = len(self.frames)
        out = []
        for k in keys:
            vals = sorted(f.get(k, 0.0) for f in self.frames)
            out.append((k, percentile(vals, 0.5), percentile(vals, 0.9), sum(vals) / n))
        out.sort(key=lambda row: (-row[3], row[0]))
        return out

    def calls_per_frame(self, key: str) -> float:
        return sum(c.get(key, 0) for c in self.calls) / len(self.calls) if self.calls else 0.0

    def totals(self) -> list[float]:
        """Each frame's whole draw, the sum of its parts."""
        return [sum(f.values()) for f in self.frames]


def format_layers(timer: LayerTimer, bare: list[float] | None = None) -> str:
    """The breakdown as text: one line per layer and, when `bare` is given
    (the draw times of the frames drawn between the timed ones,
    `Alternate`), what the timers added at p50 and what that is per timed
    call."""
    if not timer.frames:
        return "  draw by layer: no timed frames (--layers needs --frames 2 or more)"
    totals = sorted(timer.totals())
    mean_total = sum(totals) / len(totals)
    lines = [(f"  draw by layer, exclusive ms over {len(totals)} timed frames "
              "(p50 / p90 / mean, share of the mean draw, calls a frame):")]
    calls = 0.0
    for key, p50, p90, mean in timer.summary():
        share = 100.0 * mean / mean_total if mean_total else 0.0
        per_frame = timer.calls_per_frame(key)
        calls += per_frame
        lines.append(f"    {key:22s} {p50:6.2f} / {p90:6.2f} / {mean:6.2f}   {share:5.1f} %"
                     f"   {per_frame:7.1f}")
    lines.append(f"    {'(all layers)':22s} {percentile(totals, 0.5):6.2f} / "
                 f"{percentile(totals, 0.9):6.2f} / {mean_total:6.2f}")
    if bare:
        b = sorted(bare)
        added = percentile(totals, 0.5) - percentile(b, 0.5)
        per_call = 1000.0 * added / calls if calls else 0.0
        lines.append(f"  the {len(b)} frames between, drawn without the timers: draw p50 "
                     f"{percentile(b, 0.5):.2f} ms; the timers add {added:+.2f} ms at p50, "
                     f"{calls:.0f} timed calls a frame, {per_call:.2f} us a call in place")
    return "\n".join(lines)


def bare_frames(alternate: Alternate, *seqs) -> list[list]:
    """Each of `seqs` (per-frame lists from `spawn_stress.run`) cut down
    to the frames drawn without the timers."""
    return [[seq[i] for i in alternate.bare] for seq in seqs]


class Alternate:
    """`after_draw` for `spawn_stress.run`: the timers on every other frame,
    so timed and bare frames interleave over the same crowd (the RND-008
    rule: before and after back to back, alternating). The first frame is
    bare. `bare` and `timed` are the indices of each kind in `run`'s draw
    times."""

    def __init__(self, timer: LayerTimer, ps) -> None:
        self.timer, self.ps = timer, ps
        self.bare: list[int] = []
        self.timed: list[int] = []
        self._i = 0

    def __call__(self) -> None:
        if self.timer.installed:
            self.timer.frame()
            self.timer.uninstall()
            # The timed frame's garbage (the wrappers allocate) is collected
            # here, outside any timed span, so it does not fall into the
            # bare frame that follows.
            gc.collect(0)
            self.timed.append(self._i)
        else:
            self.bare.append(self._i)
            self.timer.install(self.ps)
        self._i += 1

    def close(self) -> None:
        """Take the timers off, whatever frame the run stopped on."""
        if self.timer.installed:
            self.timer.uninstall()
