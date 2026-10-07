"""What each piece of the elemental under-layer costs, timed in isolation on
the live fight (RND-010.6, `crowd_draw_journal.md`).

    python -m tools.benchmarks.under_leads --live 150 --elapsed 200
    SDL_VIDEODRIVER=windows python -m tools.benchmarks.under_leads --live 250 --elapsed 600

`draw_layers` splits `draw_under` into its passes (`elemental/auras`,
`/statuses`, `/areas`); this splits each pass into lookups and pixels, as
`draw_leads` does for an enemy's draw. The scene is
`layer_probes.packed_scene(elements=True)`: the crowd primed and the
weapons infused, as `spawn_stress --elements`, then frozen. Each piece is
called on its own over the frame's own items, with the arguments the pass
would give it, `--rounds` times, the pieces' order rotated each round. A
piece's cost is the p50 over the rounds of its time per item; times the
items, that is its share of a frame. Each pass is also timed whole, over
the same items, and what its pieces leave of it is the glue.

The pieces:

* **auras**, over the primed bodies in the padded view: the state's
  element (`state.element`), `world_to_screen`, `aura_size`, the frame's
  lookup (`aura_frame`, an asset cache hit) and the blit;
* **statuses**, over the bodies with a status: for the chilled, the slow
  chevron's new SRCALPHA surface, its two polygons and its blit (all of
  `_shape`); for the burning, the flame's lookup and scaled copy (a cache
  hit) and its blit;
* a **candidate**, not part of any pass: the aura's blit from an
  RLE-accelerated copy of its frame (`set_alpha(255, RLEACCEL)`, which
  keeps the per-pixel alpha; a frame with translucent pixels keeps the
  plain blit, as `draw_variants.aura_rle`), beside the real blit;
* **areas**, over the live Wind tornadoes: the ring's new surface, its
  circle and its blit (`_ring`), and the turning arcs as one piece
  (`_arc_ring`).

The fight runs between measured frames (`--snapshots` of them, `--gap`
drawn frames apart): a single frozen frame holds whatever statuses and
tornadoes it happens to, so each piece's ms a frame is the mean over the
snapshots.

What isolation does: every piece runs warm on the same arguments, kind to
caches; summed, they leave out the interleaving. Blits land on the
display's surface, so the pixel pieces read the on-screen cost only with
`SDL_VIDEODRIVER=windows`; headless they are the dummy driver's.
"""
from __future__ import annotations

import argparse
import time

from tools.benchmarks import layer_probes as LP
from tools.benchmarks.draw_variants import binary_alpha
from tools.benchmarks.stats import percentile


def items(ps) -> dict:
    """`pass -> list`: the items each pass draws this frame. `auras`, the
    primed bodies in the padded view (`layers.in_band`); `statuses`, those
    with a status; `chilled` and `burning` among them; `areas`, the live
    tornadoes."""
    from game.states.playing.visual.elements import layers
    run = ps.run
    now = run.stats["time"]
    bodies = layers.in_band(run, None)
    primed = [b for b in bodies if getattr(b, "elemental", None) is not None
              and b.elemental.element(now)]
    status = [b for b in bodies if getattr(b, "status", None) is not None and len(layers._marks(b.status))]
    return {
        "auras": primed,
        "statuses": [b for b in bodies if getattr(b, "status", None) is not None],
        "chilled": [b for b in status if "chill" in b.status and "freeze" not in b.status],
        "burning": [b for b in status if "burn" in b.status],
        "areas": [a for a in run.wind_areas if a.remaining(now) > 0.0],
    }


def pieces(ps, surface) -> dict:
    """`name -> (pass, over, fn(item))`: each piece as a call on one item of
    the list named by `over` (see `items`). Arguments are worked out once per
    item, as the pass would on this frame, so a piece's time is its own.
    A name ending `, whole` is the pass itself, `fn` taking the whole list."""
    import pygame

    from game.states.playing.visual.elements import layers, transient
    run = ps.run
    cam = run.camera
    z = cam.zoom
    now = run.stats["time"]
    visuals = run.element_visuals.profiles
    style = visuals.aura
    lists = items(ps)

    aura_args = {}
    for b in lists["auras"]:
        profile = visuals[b.elemental.element(now)]
        sx, sy = cam.world_to_screen(b.pos)
        radius = (b.radius + style.ring_pad) * z
        width = radius * 2.0 * style.rig_scale
        size = profile.aura_size(width)
        frame = profile.aura_frame(size=size)
        aura_args[id(b)] = (profile, width, size, frame, frame.get_rect(center=(int(sx), int(sy))))
    rle = {}                     # the candidate: an RLE copy of each binary frame, as `aura_rle`
    for _p, _w, _s, frame, _r in aura_args.values():
        if id(frame) not in rle:
            if binary_alpha(frame):
                rle[id(frame)] = frame.copy()
                rle[id(frame)].set_alpha(255, pygame.RLEACCEL)
            else:
                rle[id(frame)] = frame

    shape_args = {}
    for b in lists["chilled"]:
        sx, sy = cam.world_to_screen(b.pos)
        top = sy - (b.radius + layers._STATUS_LIFT) * z
        marks = layers._marks(b.status)
        cy = top - marks.index(layers._slow_mark) * layers._STATUS_STEP * z
        size = 7 * z
        pts = [(sx + (x - 0.5) * size, cy + (y - 0.5) * size) for x, y in layers._SLOW_SHAPE]
        box = pygame.Rect(0, 0, int(size) + 4, int(size) + 4)
        local = [(x - sx + box.width / 2, y - cy + box.height / 2) for x, y in pts]
        layer = pygame.Surface(box.size, pygame.SRCALPHA)
        shape_args[id(b)] = (sx, cy, size, box, local, layer,
                             (int(sx - box.width / 2), int(cy - box.height / 2)))

    burn_args = {}
    flame = visuals.status_frame("burn")
    for b in lists["burning"]:
        if flame is None:
            break
        sx, sy = cam.world_to_screen(b.pos)
        top = sy - (b.radius + layers._STATUS_LIFT) * z
        size = (max(4, int(flame.get_width() * 0.34 * z)), max(6, int(flame.get_height() * 0.34 * z)))
        scaled = layers._scaled(flame, size)
        burn_args[id(b)] = (size, scaled, scaled.get_rect(midbottom=(int(sx), int(top))))

    area_args = {}
    for a in lists["areas"]:
        left = a.remaining(now)
        colour = transient._area_colour(visuals, a)
        sx, sy = cam.world_to_screen(a.pos)
        radius = max(2, int(a.radius * z))
        alpha = min(255, int(110 * min(1.0, left / 0.4)))
        size = radius * 2 + 3 * 2 + 2
        area_args[id(a)] = ((int(sx), int(sy)), radius, colour, alpha, size,
                            pygame.Surface((size, size), pygame.SRCALPHA),
                            int(radius * 0.62), int(150 * min(1.0, left / 0.4)), now * 5.0)

    def aura_state(b):
        b.elemental.element(now)

    def aura_w2s(b):
        cam.world_to_screen(b.pos)

    def aura_size(b):
        p, width, _s, _f, _r = aura_args[id(b)]
        p.aura_size(width)

    def aura_lookup(b):
        p, _w, size, _f, _r = aura_args[id(b)]
        p.aura_frame(size=size)

    def aura_blit_rle(b):
        _p, _w, _s, frame, rect = aura_args[id(b)]
        surface.blit(rle[id(frame)], rect)

    def aura_blit(b):
        _p, _w, _s, frame, rect = aura_args[id(b)]
        surface.blit(frame, rect)

    def shape_surface(b):
        box = shape_args[id(b)][3]
        pygame.Surface(box.size, pygame.SRCALPHA)

    def shape_polygons(b):
        _x, _y, _s, _box, local, layer, _d = shape_args[id(b)]
        pygame.draw.polygon(layer, (*layers._SLOW_COLOUR, layers._STATUS_ALPHA), local)
        pygame.draw.polygon(layer, (18, 16, 24, layers._STATUS_ALPHA), local, 1)

    def shape_blit(b):
        layer, dest = shape_args[id(b)][5], shape_args[id(b)][6]
        surface.blit(layer, dest)

    def burn_lookup(b):
        visuals.status_frame("burn")
        layers._scaled(flame, burn_args[id(b)][0])

    def burn_blit(b):
        _s, scaled, rect = burn_args[id(b)]
        surface.blit(scaled, rect)

    def ring_surface(a):
        size = area_args[id(a)][4]
        pygame.Surface((size, size), pygame.SRCALPHA)

    def ring_circle(a):
        _c, radius, colour, alpha, size, layer, *_ = area_args[id(a)]
        pygame.draw.circle(layer, (*colour, alpha), (size // 2, size // 2), radius, 3)

    def ring_blit(a):
        centre, _r, _c, _a, size, layer, *_ = area_args[id(a)]
        surface.blit(layer, (centre[0] - size // 2, centre[1] - size // 2))

    def arc_ring(a):
        centre, _r, colour, _a, _s, _l, inner, alpha, spin = area_args[id(a)]
        if inner > 2:
            transient._arc_ring(surface, centre, inner, colour, alpha, spin)

    return {
        "auras, whole": ("auras", "auras",
                         lambda bs: layers.draw_auras(surface, run, visuals, now, None, bs)),
        "aura: state": ("auras", "auras", aura_state),
        "aura: world_to_screen": ("auras", "auras", aura_w2s),
        "aura: size": ("auras", "auras", aura_size),
        "aura: frame lookup": ("auras", "auras", aura_lookup),
        "aura: blit": ("auras", "auras", aura_blit),
        "aura: blit, RLE copy": ("candidates", "auras", aura_blit_rle),
        "statuses, whole": ("statuses", "statuses",
                            lambda bs: layers.draw_statuses(surface, run, visuals, now, None, bs)),
        "chill: new surface": ("statuses", "chilled", shape_surface),
        "chill: polygons": ("statuses", "chilled", shape_polygons),
        "chill: blit": ("statuses", "chilled", shape_blit),
        "burn: lookup": ("statuses", "burning", burn_lookup),
        "burn: blit": ("statuses", "burning", burn_blit),
        "areas, whole": ("areas", "areas",
                         lambda _as: transient.draw_areas(surface, run, visuals, now, None)),
        "ring: new surface": ("areas", "areas", ring_surface),
        "ring: circle": ("areas", "areas", ring_circle),
        "ring: blit": ("areas", "areas", ring_blit),
        "arcs: whole ring": ("areas", "areas", arc_ring),
    }


def snapshot(ps, surface, rounds: int) -> dict:
    """One frame's pieces: each one's per-item µs over `rounds` rounds, the
    order rotated each round, and the frame's item counts."""
    lists = items(ps)
    table = pieces(ps, surface)
    names = list(table)
    samples = {n: [] for n in names}
    for r in range(rounds):
        order = names[r % len(names):] + names[:r % len(names)]
        for name in order:
            _pass, over, fn = table[name]
            its = lists[over]
            if not its:
                continue
            t0 = time.perf_counter()
            if name.endswith(", whole"):
                fn(its)
            else:
                for it in its:
                    fn(it)
            samples[name].append((time.perf_counter() - t0) * 1e6 / len(its))
    return {"samples": samples, "pass": {n: table[n][0] for n in names},
            "over": {n: table[n][1] for n in names},
            "counts": {k: len(v) for k, v in lists.items()}}


def measure(ps, rounds: int, snapshots: int = 1, gap: int = 30, advance=None) -> list[dict]:
    """`snapshots` frames of the running fight, `gap` drawn fight frames
    apart (the first at once), each measured by `snapshot`. A frozen frame
    holds whatever statuses and tornadoes it happens to; the fight's mix
    shows only over several. `advance(ps, frames)` steps the fight
    (`spawn_stress.run`, drawn, by default)."""
    import pygame

    from tools.benchmarks import spawn_stress as S
    if advance is None:
        def advance(p, frames):
            S.run(p, frames, render=True)
    surface = pygame.display.get_surface()
    if surface is None:                          # no display yet: an off-screen stand-in
        surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    out = []
    for i in range(snapshots):
        if i:
            advance(ps, gap)
        out.append(snapshot(ps, surface, rounds))
    return out


def per_frame(shots: list[dict]) -> dict:
    """`name -> (µs an item, items a frame, ms a frame)` over the snapshots:
    each snapshot's p50 an item times its items is its ms a frame; the ms
    and the items are the snapshots' means (a snapshot with no such item
    counts as 0 ms), and the µs an item is their ratio."""
    names = list(shots[0]["samples"]) if shots else []
    out = {}
    for name in names:
        ms, n = 0.0, 0
        seen = False
        for shot in shots:
            vals = shot["samples"][name]
            count = shot["counts"][shot["over"][name]]
            n += count
            if vals:
                seen = True
                ms += percentile(sorted(vals), 0.5) * count / 1000.0
        if not seen:
            continue
        k = len(shots)
        out[name] = (1000.0 * ms / n, n / k, ms / k)
    return out


def report(shots: list[dict]) -> str:
    rows = per_frame(shots)
    k = len(shots)

    def mean(key):
        return sum(s["counts"][key] for s in shots) / k

    passes = shots[0]["pass"]
    rounds = max((len(v) for s in shots for v in s["samples"].values()), default=0)
    lines = [(f"  under leads, a mean over {k} fight frame(s): {mean('auras'):.1f} auras, "
              f"{mean('statuses'):.1f} with a status ({mean('chilled'):.1f} chilled, "
              f"{mean('burning'):.1f} burning), {mean('areas'):.1f} tornadoes; {rounds} rounds a frame")]
    for name, (us, n, ms) in rows.items():
        if passes[name] == "candidates":
            lines.append(f"    candidate {name:22s} {us:7.2f} us an item  x {n:6.1f}  = {ms:6.3f} ms a frame")
    for p in ("auras", "statuses", "areas"):
        whole = rows.get(f"{p}, whole")
        parts = [(n, v) for n, v in rows.items() if passes[n] == p and not n.endswith(", whole")]
        if whole is None:
            lines.append(f"    {p}: nothing to draw")
            continue
        lines.append(f"    {p + ', whole':24s} {whole[0]:7.2f} us an item  x {whole[1]:6.1f}  "
                     f"= {whole[2]:6.3f} ms a frame")
        for name, (us, n, ms) in sorted(parts, key=lambda kv: -kv[1][2]):
            share = f"   {100 * ms / whole[2]:5.1f} %" if whole[2] else ""
            lines.append(f"      {name:22s} {us:7.2f} us an item  x {n:6.1f}  = {ms:6.3f} ms a frame{share}")
        rest = whole[2] - sum(ms for _n, (_u, _c, ms) in parts)
        lines.append(f"      {'(the glue)':22s} {'':29s} = {rest:6.3f} ms a frame")
    return "\n".join(lines)


def parse(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=35, help="the world's seed")
    ap.add_argument("--live", type=int, required=True,
                    help="as spawn_stress --live; needs --elapsed (N - 100) * 4")
    ap.add_argument("--elapsed", type=float, required=True, help="the run clock in seconds")
    ap.add_argument("--dormant", type=int, default=400, help="enemy records on the other islands")
    ap.add_argument("--rounds", type=int, default=50, help="rounds over a frame's items, per piece")
    ap.add_argument("--snapshots", type=int, default=10, help="fight frames measured")
    ap.add_argument("--gap", type=int, default=30, help="fight frames run between two measured")
    args = ap.parse_args(argv)
    for name in ("rounds", "snapshots", "gap"):
        if getattr(args, name) < 1:
            ap.error(f"--{name} must be 1 or more")
    return args


def main(argv=None, save_path: str | None = None) -> int:
    args = parse(argv)
    _game, ps = LP.packed_scene(args.seed, args.live, args.dormant, args.elapsed, save_path,
                                elements=True)
    print(report(measure(ps, args.rounds, args.snapshots, args.gap)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
