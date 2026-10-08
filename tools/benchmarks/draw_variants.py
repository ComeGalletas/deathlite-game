"""Throwaway versions of a candidate change to the draw, timed against the
unmodified draw (RND-010.3, `crowd_draw_journal.md`).

    python -m tools.benchmarks.draw_variants --live 150 --elapsed 300
    SDL_VIDEODRIVER=windows python -m tools.benchmarks.draw_variants --live 250 --elapsed 600 --variants rig_frame_cached

The scene is `layer_probes.packed_scene`'s, the `spawn_stress --pack` one.
A variant changes the draw by patching the live objects for as long as it
is on (an instance attribute over a method, or a module attribute the
draw reads at call time) and is taken off after; the game's code is not
touched. A variant is timed only if it is pixel-identical: a whole frame
drawn with it on must equal the frame drawn with it off, byte for byte, or
the variant is reported as differing and skipped. Each variant is then
timed against the draw in ABBA blocks over one crowd, the hero on one
anchor, as `layer_probes bias` times the headline: `--blocks` pairs of
`--frames` frames, off and on, the order alternating, so a drift inside
a block falls on each side alike. Printed per variant: the draw's p50 off
and on over every block, and the per-block on minus off p50s with the
sign test's interval on their median; then the draw's mean, p90 and p99
on each side, and the per-block on minus off means with the same
interval: what the change would save, before anything is built.

The variants (`VARIANTS`):

* `rig_frame_cached`: `WorldRenderer.rig_frame` with each rig's facing and
  base size, and each strip's frames, fps and loop flag, looked up once
  instead of on every call (`Animator.index` makes three meta lookups and
  `Assets.frame` a fourth, `scale_for` and `face` two more);
* `world_bucketed`: `scene.draw_world` with the scenery and the actors
  sorted onto their terraces in one pass, instead of filtering both lists
  once for every terrace;
* `forwarder_bypassed`: the state's `_draw_one_enemy` bound straight to
  `WorldRenderer.one_enemy`, without the generated forwarder's two
  `getattr`s;
* `wash_lru`: a primed enemy's washed frames (`element_fx.washed`) held
  in an LRU of `WASH_LRU_CAP` entries, where the game's cache emptied
  itself whole once it held 512 (`sprite_caches.py` replays both on a
  fight's own requests). Only a fight washes enough to tell: run it with
  `--elements`. RND-010.4 built it into the game, so against the game
  since then it compares an LRU with an LRU of the same size.

RND-010.6's, the elemental under-layer's (`under_leads.py` splits it); run
them with `--elements`, since only a fight draws auras, marks and
tornadoes:

* `shape_cached`: the slow chevron and the freeze bracket (`layers._shape`)
  drawn once per `(shape, size, colour)` and blitted from the kept copy;
* `ring_cached`: the tornado's ring (`transient._ring`) the same, per
  `(radius, colour, alpha, width)`;
* `aura_rle`: each aura frame blitted from an RLE-accelerated copy that
  keeps its per-pixel alpha, so SDL skips its transparent runs;
* `aura_lookup_once`: `draw_auras` looking each element's frame up once a
  pass per size, not once per body.

`--elements` takes the scene with the hero fighting, as `spawn_stress
--elements` does: every enemy primed and three infused weapons firing.

Headless without `SDL_VIDEODRIVER=windows` (in bash; in PowerShell set it
first), like the harness: the dummy driver's surface, not the cost on
screen.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict

from tools.benchmarks import layer_probes as LP
from tools.benchmarks import spawn_stress as S


def _rig_frame_cached(ps):
    """Patch `ps.renderer.rig_frame` with one that caches what does not
    change between calls; returns the undo."""
    ren = ps.renderer
    assets = ps.game.assets
    rigs: dict = {}      # rig -> (faces right, base width, base height)
    strips: dict = {}    # (rig, anim, size, flip) -> (frames, fps, loops, frame count)

    def rig_frame(anim, facing, scale):
        rig = anim.rig
        r = rigs.get(rig)
        if r is None:
            bw, bh = assets.scale_for(rig)
            r = rigs[rig] = (assets.face(rig) == "right", bw, bh)
        right, bw, bh = r
        flip = facing < 0 and right
        size = (max(1, round(bw * scale)), max(1, round(bh * scale)))
        key = (rig, anim.anim, size, flip)
        s = strips.get(key)
        if s is None:
            s = strips[key] = (assets.frames(rig, anim.anim, size=size, flip=flip),
                               assets.fps(rig, anim.anim), assets.loops(rig, anim.anim),
                               assets.frame_count(rig, anim.anim))
        frs, fps, loops, count = s
        if not frs:
            return None, flip
        # `Animator.index`, then `Assets.frame`'s own wrap or clamp.
        n = max(1, count)
        raw = int(anim.t * fps)
        index = raw % n if loops else min(raw, n - 1)
        m = len(frs)
        return frs[index % m if loops else max(0, min(index, m - 1))], flip

    ren.rig_frame = rig_frame
    return lambda: delattr(ren, "rig_frame")


def _world_bucketed(ps):
    """Patch `scene.draw_world` with a copy that sorts the scenery and the
    actors onto their terraces in one pass; returns the undo."""
    from game.states.playing.visual import elements as element_fx
    from game.states.playing.visual import scene

    original = scene.draw_world

    def draw_world(ps_, surface):
        r = ps_.game_map.renderer
        r.begin_frame()
        r.draw_water(surface, ps_.camera)
        scenery = r.banded_scenery(ps_.camera)
        actors = scene.actor_items(ps_)
        bands: dict = {}
        for lvl, d, f in scenery:                # scenery first, then actors: the
            bands.setdefault(lvl, []).append((d, f))   # order the original's lists keep
        for lvl, d, f in actors:
            bands.setdefault(lvl, []).append((d, f))
        levels = sorted(set(bands) | set(r.ground_levels()))
        elemental = element_fx.bands(ps_.run)
        for level in levels:
            r.draw_ground_band(surface, ps_.camera, level)
            scene.draw_flat_effects(ps_, surface, level, elemental)
            items = bands.get(level, [])
            items.sort(key=lambda t: t[0])
            for _depth, fn in items:
                fn(surface)
        r.ghost_pass(surface, ps_.camera)

    scene.draw_world = draw_world
    return lambda: setattr(scene, "draw_world", original)


def _forwarder_bypassed(ps):
    """Bind `ps._draw_one_enemy` straight to the renderer's method; returns
    the undo."""
    ps._draw_one_enemy = ps.renderer.one_enemy
    return lambda: delattr(ps, "_draw_one_enemy")


WASH_LRU_CAP = 1536
_WASH_LRU: OrderedDict = OrderedDict()   # (id(frame), element) -> (frame, washed copy)


def _wash_lru(ps):
    """Patch `element_fx.washed` with an LRU of `WASH_LRU_CAP` entries in
    place of the game's cache (which emptied itself whole at 512 until
    RND-010.4 made it this same LRU); returns the undo. The LRU is this module's and outlives the undo, so each
    side keeps its own warm cache from part to part. A miss is washed by
    the game's own `washed`, given an empty cache for the call so the
    game's stays as the side without the variant left it."""
    from game.states.playing.visual import elements as fx
    real = fx.washed

    def washed(frame, element, profiles=None):
        if not element or frame is None:
            return frame
        key = (id(frame), int(element))
        hit = _WASH_LRU.get(key)
        if hit is not None and hit[0] is frame:
            _WASH_LRU.move_to_end(key)
            return hit[1]
        game_cache = fx._WASH_CACHE
        fx._WASH_CACHE = type(game_cache)()
        try:
            out = real(frame, element, profiles)
        finally:
            fx._WASH_CACHE = game_cache
        if len(_WASH_LRU) >= WASH_LRU_CAP:
            _WASH_LRU.popitem(last=False)
        _WASH_LRU[key] = (frame, out)
        return out

    fx.washed = washed
    return lambda: setattr(fx, "washed", real)


# --- RND-010.6: the elemental under-layer's candidates ---------------------------
# Each cache is this module's, bounded, and cleared by its undo so the side
# without the variant pays nothing for it.
UNDER_CAP = 256
# `aura_rle`'s own cap. A packed fight asks for 342 distinct aura frames at
# 150 and 456 at 250 (four elements, their animation frames, a size per body
# radius); at 256 the variant emptied itself over and over in sitting 1 and
# timed its own re-encoding, not the RLE blit.
RLE_CAP = 2048


def _bounded(cache: dict, key, make, cap: int = UNDER_CAP):
    hit = cache.get(key)
    if hit is None:
        if len(cache) >= cap:
            cache.clear()
        hit = cache[key] = make()
    return hit


def _shape_cached(ps):
    """`layers._shape` (the slow chevron, the freeze bracket) drawn once per
    `(shape, size, colour)` and blitted from the kept copy. The layer does
    not depend on where it lands: its points are `(x - 0.5) * size` plus
    half the box, and the box is `int(size) + 4` square."""
    import pygame

    from game.states.playing.visual.elements import layers
    real = layers._shape
    cache: dict = {}

    def shape(surface, shp, cx, cy, size, colour):
        if size < 2:
            return
        side = int(size) + 4

        def make():
            layer = pygame.Surface((side, side), pygame.SRCALPHA)
            local = [((x - 0.5) * size + side / 2, (y - 0.5) * size + side / 2) for x, y in shp]
            pygame.draw.polygon(layer, (*colour, layers._STATUS_ALPHA), local)
            pygame.draw.polygon(layer, (18, 16, 24, layers._STATUS_ALPHA), local, 1)
            return layer

        surface.blit(_bounded(cache, (shp, size, colour), make),
                     (int(cx - side / 2), int(cy - side / 2)))

    layers._shape = shape

    def undo():
        layers._shape = real
        cache.clear()
    return undo


def _ring_cached(ps):
    """The tornado's ring (`transient._ring`) drawn once per `(radius,
    colour, alpha, width)` and blitted from the kept copy."""
    import pygame

    from game.states.playing.visual.elements import transient
    real = transient._ring
    cache: dict = {}

    def ring(surface, center, radius, colour, alpha, width):
        alpha = min(255, int(alpha))
        if alpha <= 0 or radius <= 0:
            return
        size = radius * 2 + width * 2 + 2

        def make():
            layer = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(layer, (*colour, alpha), (size // 2, size // 2), radius, max(1, width))
            return layer

        surface.blit(_bounded(cache, (radius, tuple(colour), alpha, width), make),
                     (center[0] - size // 2, center[1] - size // 2))

    transient._ring = ring

    def undo():
        transient._ring = real
        cache.clear()
    return undo


def binary_alpha(frame) -> bool:
    """Is every pixel of `frame` either clear (alpha 0) or opaque (255)?
    The pixels over alpha 0 counted against those over 254, by
    `pygame.mask` (no numpy in the game)."""
    import pygame
    return (pygame.mask.from_surface(frame, 0).count()
            == pygame.mask.from_surface(frame, 254).count())


def _aura_rle(ps):
    """Each aura frame blitted from an RLE-accelerated copy
    (`set_alpha(255, RLEACCEL)`, which keeps the per-pixel alpha): SDL skips
    the frame's transparent runs instead of blending them. Exact only for a
    frame whose alpha is all 0 or 255: SDL's RLE path blends a translucent
    pixel by its own formula, off by one in a channel against the plain
    blit, so a frame with any is left to the plain blit (`binary_alpha`).
    Every aura frame shipped is binary. The copies are kept per frame, the
    frame held in the entry so its id is not reused."""
    import pygame

    from game.states.playing.visual.elements.profiles import ElementVisualProfile
    real = ElementVisualProfile.aura_frame          # the class's: profiles have slots
    copies: dict = {}

    def aura_frame(self, size=None):
        frame = real(self, size=size)
        if frame is None:
            return None

        def make():
            if not binary_alpha(frame):
                return (frame, frame)                # translucent pixels: the plain blit
            out = frame.copy()
            out.set_alpha(255, pygame.RLEACCEL)
            return (frame, out)

        hit = _bounded(copies, id(frame), make, RLE_CAP)
        return hit[1] if hit[0] is frame else frame

    ElementVisualProfile.aura_frame = aura_frame

    def undo():
        ElementVisualProfile.aura_frame = real
        copies.clear()
    return undo


def _aura_lookup_once(ps):
    """`layers.draw_auras` with each element's frame looked up once per size
    in a pass instead of once per body: every body of an element shares its
    profile's animator, so the frame at a size is the same for all of them."""
    from game.states.playing.visual.elements import layers
    real = layers.draw_auras

    def draw_auras(surface, run, visuals, now, level=None, bodies=None):
        cam = run.camera
        style = visuals.aura
        frames: dict = {}
        drawn = 0
        for body in layers.in_band(run, level) if bodies is None else bodies:
            state = getattr(body, "elemental", None)
            if state is None:
                continue
            element = state.element(now)
            if element:
                profile = visuals[element]
                sx, sy = cam.world_to_screen(body.pos)
                radius = (body.radius + style.ring_pad) * cam.zoom
                size = profile.aura_size(radius * 2.0 * style.rig_scale)
                key = (element, size)
                frame = frames.get(key, frames)
                if frame is frames:
                    frame = frames[key] = profile.aura_frame(size=size) if size else None
                if frame is not None:
                    surface.blit(frame, frame.get_rect(center=(int(sx), int(sy))))
                else:
                    layers._aura(surface, cam, body, profile, style)
                drawn += 1
            elif state.is_locked(now):
                layers._locked(surface, cam, body, style)
        return drawn

    layers.draw_auras = draw_auras
    return lambda: setattr(layers, "draw_auras", real)


VARIANTS = {"rig_frame_cached": _rig_frame_cached, "world_bucketed": _world_bucketed,
            "forwarder_bypassed": _forwarder_bypassed, "wash_lru": _wash_lru,
            "shape_cached": _shape_cached, "ring_cached": _ring_cached,
            "aura_rle": _aura_rle, "aura_lookup_once": _aura_lookup_once}


def picture(ps, surface) -> bytes:
    """One frame of `ps` drawn into `surface`, as bytes."""
    import pygame
    ps.draw(surface)
    return pygame.image.tobytes(surface, "RGBA")


def identical(ps, name: str, surface) -> bool:
    """Is the frame with `name` on the frame without it, byte for byte?
    The terrain's clock (the water and foam animate on the wall clock) is
    held at 0 for the comparison and put back after. Drawn off, on twice,
    then off again: both frames with it on must equal the first (a
    variant that caches is checked filling its cache and then using it),
    and the last must too, or the scene itself is not still and the answer
    would mean nothing."""
    terrain = ps.game_map.renderer
    clock = terrain.clock
    terrain.clock = lambda: 0.0
    try:
        before = picture(ps, surface)
        undo = VARIANTS[name](ps)
        try:
            with_it = [picture(ps, surface), picture(ps, surface)]
        finally:
            undo()
        after = picture(ps, surface)
    finally:
        terrain.clock = clock
    if after != before:
        raise RuntimeError("the scene moved between two draws: no comparison possible")
    return all(frame == before for frame in with_it)


def timed(ps, name: str, blocks: int, frames: int) -> dict:
    """ABBA blocks of `frames` frames, the variant off then on in even
    blocks and on then off in odd ones, the hero put back on one anchor
    before every part. Returns both sides' draw times and each block's
    on minus off p50 (`diffs`) and mean (`mean_diffs`): a change whose
    cost comes in bursts, a cache emptying every few dozen frames, shows
    in the mean and the tail before it shows in a p50."""
    from tools.benchmarks.stats import percentile
    anchor = ps.player.pos.copy()
    out = {"off": [], "on": [], "diffs": [], "mean_diffs": []}

    def part(on: bool):
        ps.player.pos.update(anchor)
        undo = VARIANTS[name](ps) if on else None
        try:
            return S.run(ps, frames, render=True)[1]
        finally:
            if undo is not None:
                undo()

    for block in range(blocks):
        if block % 2 == 0:
            off, on = part(False), part(True)
        else:
            on = part(True)
            off = part(False)
        out["off"] += off
        out["on"] += on
        out["diffs"].append(percentile(sorted(on), 0.5) - percentile(sorted(off), 0.5))
        out["mean_diffs"].append(sum(on) / len(on) - sum(off) / len(off))
    ps.player.pos.update(anchor)
    return out


def format_timed(name: str, result: dict) -> str:
    from tools.benchmarks.stats import percentile
    diffs = sorted(result["diffs"])
    means = sorted(result["mean_diffs"])
    p = lambda v, q=0.5: percentile(sorted(v), q)
    mean = lambda v: sum(v) / len(v)
    lines = [(f"  {name}: draw p50 off {p(result['off']):.2f} ms, on {p(result['on']):.2f} ms "
             f"({len(result['off'])} frames each); per block, on minus off p50: p50 "
             f"{percentile(diffs, 0.5):+.2f} ms, from {diffs[0]:+.2f} to {diffs[-1]:+.2f}")]
    interval = LP.sign_interval(len(diffs))
    if interval is None:
        lines.append("    too few blocks for a sign-test interval on the median")
    else:
        k, coverage = interval
        lines.append(f"    the median saving lies in {diffs[k - 1]:+.2f} to {diffs[-k]:+.2f} ms "
                     f"({100 * coverage:.1f} % sign-test interval; negative is faster)")
    lines.append(f"    the draw's mean off {mean(result['off']):.2f} ms, on {mean(result['on']):.2f} ms; "
                 f"p90 off {p(result['off'], 0.9):.2f}, on {p(result['on'], 0.9):.2f}; "
                 f"p99 off {p(result['off'], 0.99):.2f}, on {p(result['on'], 0.99):.2f}")
    if interval is not None:
        k, coverage = interval
        lines.append(f"    per block, on minus off mean: p50 {percentile(means, 0.5):+.2f} ms; the median "
                     f"lies in {means[k - 1]:+.2f} to {means[-k]:+.2f} ms ({100 * coverage:.1f} %)")
    return "\n".join(lines)


def parse(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=35, help="the world's seed")
    ap.add_argument("--live", type=int, required=True,
                    help="as spawn_stress --live; needs --elapsed (N - 100) * 4")
    ap.add_argument("--elapsed", type=float, required=True, help="the run clock in seconds")
    ap.add_argument("--dormant", type=int, default=400, help="enemy records on the other islands")
    ap.add_argument("--elements", action="store_true",
                    help="the hero fighting, as spawn_stress --elements")
    ap.add_argument("--variants", default=",".join(VARIANTS),
                    help=f"comma separated, of: {', '.join(VARIANTS)}")
    ap.add_argument("--blocks", type=int, default=16,
                    help="pairs of an off and an on block, an even number: the order alternates")
    ap.add_argument("--frames", type=int, default=40, help="frames in each block")
    args = ap.parse_args(argv)
    args.variants = [v for v in args.variants.split(",") if v]
    unknown = [v for v in args.variants if v not in VARIANTS]
    if unknown or not args.variants:
        ap.error(f"unknown or no variants: {', '.join(unknown) or '(none)'}")
    if args.blocks < 2 or args.blocks % 2 or args.frames < 1:
        ap.error("--blocks must be even and 2 or more, --frames 1 or more")
    return args


def main(argv=None, save_path: str | None = None) -> int:
    import pygame
    args = parse(argv)
    _game, ps = LP.packed_scene(args.seed, args.live, args.dormant, args.elapsed, save_path,
                                elements=args.elements)
    surface = pygame.display.get_surface()
    for name in args.variants:
        if not identical(ps, name, surface):
            print(f"  {name}: the frame differs with it on; not timed")
            continue
        print(format_timed(name, timed(ps, name, args.blocks, args.frames)))
    print(f"  boss at the end: {S.boss_state(ps)}")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
