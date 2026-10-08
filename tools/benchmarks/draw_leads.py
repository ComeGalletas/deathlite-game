"""What each piece of an enemy's draw costs, timed in isolation on the live
crowd (RND-010.3, `crowd_draw_journal.md`).

    python -m tools.benchmarks.draw_leads --live 150 --elapsed 300
    SDL_VIDEODRIVER=windows python -m tools.benchmarks.draw_leads --live 250 --elapsed 600

The scene is `layer_probes.packed_scene`'s, the `spawn_stress --pack` one.
The enemies are the ones `actor_items` lists and `one_enemy` would draw (in
the padded view, not still inside their spawn burst). Each piece of
`WorldRenderer.one_enemy` is then called on its own over those enemies,
with the arguments the frame gives it, `--rounds` times; the rounds rotate
the pieces' order so a drift falls on all of them alike. A piece's cost is
the p50 over the rounds of its time per enemy. No wrapper sits in any of
it, which is why it can split the row `draw_layers` leaves whole
(RND-010.D1).

The pieces, in the order the draw runs them:

* `spawn_veiled`, then `world_to_screen` (`one_enemy`'s own);
* `rig_frame` and `aura_colour` (`enemy_sprite`);
* `anchor_for`, `world_to_screen` again and `sprite_drop` (`blit_rig`);
* the tree-shade walk (`shade_character_frame`), the sprite's blit, the
  copy a shaded sprite pays for the ghost queue, and the queue's record
  itself (`record_character`; all `_blit_character`);
* the marks (`status_marks.draw`) and the health bar (`health_bars.draw`);
* a subset, not a piece of its own (RND-010.7): the shade walk again over
  the drawn enemies no shade falls on, the bodies its skip is for; listed
  after the scene's rows and left out of the glue;

and outside `one_enemy`, the scene's per-enemy work that the layer tool
puts in `world`: the cull test (over every live enemy, not only the drawn
ones), the terrace lookup, the lambda and the state's generated
forwarder. `one_enemy` itself is timed whole too, and
what the pieces leave of it is the glue between them.

What isolation does to the numbers: every piece runs warm, over and over
on the same arguments, which is kind to caches and branches, and the
pieces are summed rather than run in their real interleaving; a sum that
falls short of the whole is the glue, not an error. Blits land on the
display's surface, so the pixel pieces read the on-screen cost only with
`SDL_VIDEODRIVER=windows` (in bash; in PowerShell set it first); headless,
they are the dummy driver's.
"""
from __future__ import annotations

import argparse
import time

from tools.benchmarks import layer_probes as LP
from tools.benchmarks import spawn_stress as S
from tools.benchmarks.stats import percentile


def drawn_enemies(ps) -> list:
    """The enemies this frame's `one_enemy` draws: in the padded view
    `actor_items` culls to, and out of their spawn burst."""
    from game import config
    pad = config.RENDER_ACTOR_CULL_PAD
    view = ps.camera.visible_rect().inflate(2 * pad, 2 * pad)
    ren = ps.renderer
    return [e for e in ps.run.enemies
            if view.collidepoint(e.pos.x, e.pos.y) and not ren.spawn_veiled(e)]


def pieces(ps, surface) -> dict:
    """`name -> (fn(e), per)`: each piece as a call on one enemy, and what
    it is counted per: `"enemy"`, a drawn enemy; `"shaded"`, a shaded one
    (the ghost copy); `"call"`, each `world_to_screen` call; `"live"`,
    every live enemy (the scene's cull test). The arguments are worked out once per
    enemy, as the draw would on this frame, so a piece's time is its own."""
    from game.states.playing.visual import health_bars, status_marks
    from game.states.playing.visual.rendering import aura_colour

    ren = ps.renderer
    run = ps.run
    cam = run.camera
    z = cam.zoom
    terrain = run.game_map.renderer
    lvl, top = terrain.level_at, terrain.top_level_at
    from game import config
    pad = config.RENDER_ACTOR_CULL_PAD
    view = cam.visible_rect().inflate(2 * pad, 2 * pad)

    args = {}
    for e in drawn_enemies(ps):
        frame, flip = ren.rig_frame(e.anim, e._facing, z)
        ax, ay = ren.anchor_for(e.anim.rig, flip)
        sx, sy = cam.world_to_screen(e.pos)
        dest = (sx - ax * z, sy - ay * z + ren.sprite_drop(e.radius))
        drawn = terrain.shade_character_frame(frame, dest, cam, e.pos.y)
        args[id(e)] = (frame, flip, dest, drawn)

    def band(e):
        if getattr(e, "flying", False):
            return top(e.pos.x, e.pos.y)
        return lvl(e.pos.x, e.pos.y)

    def lam(e):
        f = (lambda s, e=e: None)
        f(surface)

    def blit(e):
        _f, _fl, dest, drawn = args[id(e)]
        surface.blit(drawn, dest)

    def copy(e):
        _f, _fl, _d, drawn = args[id(e)]
        if drawn is not args[id(e)][0]:
            drawn.copy()

    def record(e):
        frame, _fl, dest, drawn = args[id(e)]
        if drawn is frame:
            terrain.record_character(frame, dest, e.pos.y)
        else:
            terrain.record_character(drawn, dest, e.pos.y, cacheable=False)

    def shade(e):
        frame, _fl, dest, _d = args[id(e)]
        terrain.shade_character_frame(frame, dest, cam, e.pos.y)

    class _NoPaint:
        def one_enemy(self, s, e):
            pass

    class _State:
        renderer = _NoPaint()

    forward = type(ps)._draw_one_enemy
    state = _State()

    return {
        "one_enemy, whole": (lambda e: ren.one_enemy(surface, e), "enemy"),
        "spawn_veiled": (ren.spawn_veiled, "enemy"),
        "world_to_screen": (lambda e: cam.world_to_screen(e.pos), "call"),
        "rig_frame": (lambda e: ren.rig_frame(e.anim, e._facing, z), "enemy"),
        "aura_colour": (lambda e: aura_colour(run, e), "enemy"),
        "anchor_for": (lambda e: ren.anchor_for(e.anim.rig, args[id(e)][1]), "enemy"),
        "sprite_drop": (lambda e: ren.sprite_drop(e.radius), "enemy"),
        "shade walk": (shade, "enemy"),
        "subset: shade walk, unshaded": (shade, "unshaded"),
        "sprite blit": (blit, "enemy"),
        "ghost copy": (copy, "shaded"),
        "ghost record": (record, "enemy"),
        "marks": (lambda e: status_marks.draw(ren, surface, e), "enemy"),
        "health bar": (lambda e: health_bars.draw(surface, ren, e), "enemy"),
        "scene: cull test": (lambda e: view.collidepoint(e.pos.x, e.pos.y), "live"),
        "scene: terrace lookup": (band, "enemy"),
        "scene: lambda": (lam, "enemy"),
        "scene: forwarder": (lambda e: forward(state, surface, e), "enemy"),
    }


def world_to_screen_calls(ps, surface) -> float:
    """`world_to_screen` calls a drawn enemy costs in this frame: counted
    by a counting stand-in on the camera over one pass of `one_enemy`."""
    cam = ps.run.camera
    enemies = drawn_enemies(ps)
    real = cam.world_to_screen
    count = [0]

    def counted(pos):
        count[0] += 1
        return real(pos)

    cam.world_to_screen = counted
    try:
        ps.game_map.renderer.begin_frame()
        for e in enemies:
            ps.renderer.one_enemy(surface, e)
    finally:
        del cam.world_to_screen
    return count[0] / len(enemies) if enemies else 0.0


def measure(ps, rounds: int) -> dict:
    """Each piece's per-call times over `rounds` rounds, the pieces'
    order rotated each round. Returns the per-round µs per call of each
    piece, the drawn enemies, the shaded ones and the `world_to_screen`
    calls an enemy costs."""
    import pygame
    surface = pygame.display.get_surface()
    if surface is None:                          # no display yet: an off-screen stand-in
        surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    enemies = drawn_enemies(ps)
    table = pieces(ps, surface)
    shaded = [e for e in enemies if _shaded(ps, e)]
    unshaded = [e for e in enemies if e not in shaded]
    live = list(ps.run.enemies)
    names = list(table)
    samples = {n: [] for n in names}
    terrain = ps.game_map.renderer
    for r in range(rounds):
        order = names[r % len(names):] + names[:r % len(names)]
        for name in order:
            fn, per = table[name]
            over = {"shaded": shaded, "live": live, "unshaded": unshaded}.get(per, enemies)
            if not over:
                continue
            terrain.begin_frame()                # the ghost queue, as each frame starts it
            t0 = time.perf_counter()
            for e in over:
                fn(e)
            samples[name].append((time.perf_counter() - t0) * 1e6 / len(over))
    return {"samples": samples, "per": {n: table[n][1] for n in names}, "enemies": len(enemies),
            "shaded": len(shaded), "live": len(live), "w2s": world_to_screen_calls(ps, surface)}


def _shaded(ps, e) -> bool:
    ren = ps.renderer
    cam = ps.run.camera
    z = cam.zoom
    frame, flip = ren.rig_frame(e.anim, e._facing, z)
    ax, ay = ren.anchor_for(e.anim.rig, flip)
    sx, sy = cam.world_to_screen(e.pos)
    dest = (sx - ax * z, sy - ay * z + ren.sprite_drop(e.radius))
    return ps.game_map.renderer.shade_character_frame(frame, dest, cam, e.pos.y) is not frame


def per_frame(result: dict) -> dict:
    """`name -> (µs a call p50, calls a frame, ms a frame)`."""
    out = {}
    for name, vals in result["samples"].items():
        if not vals:
            continue
        us = percentile(sorted(vals), 0.5)
        per = result["per"][name]
        calls = {"shaded": result["shaded"], "live": result["live"],
                 "unshaded": result["enemies"] - result["shaded"],
                 "call": result["enemies"] * result["w2s"]}.get(per, result["enemies"])
        out[name] = (us, calls, us * calls / 1000.0)
    return out


def report(result: dict) -> str:
    rows = per_frame(result)
    whole = rows.get("one_enemy, whole")
    lines = [(f"  draw leads: {result['live']} alive, {result['enemies']} drawn, "
             f"{result['shaded']} of them shaded, "
             f"{result['w2s']:.1f} world_to_screen calls an enemy; "
             f"{max(len(v) for v in result['samples'].values())} rounds")]
    parts = [(n, v) for n, v in rows.items()
             if n != "one_enemy, whole" and not n.startswith(("scene:", "subset:"))]
    scene = [(n, v) for n, v in rows.items() if n.startswith("scene:")]
    subset = [(n, v) for n, v in rows.items() if n.startswith("subset:")]
    if whole:
        lines.append(f"    {'one_enemy, whole':24s} {whole[0]:7.2f} us a call  x {whole[1]:6.1f}  "
                     f"= {whole[2]:6.2f} ms a frame")
    for name, (us, calls, ms) in sorted(parts, key=lambda kv: -kv[1][2]):
        share = f"   {100 * ms / whole[2]:5.1f} % of the whole" if whole and whole[2] else ""
        lines.append(f"    {name:24s} {us:7.2f} us a call  x {calls:6.1f}  = {ms:6.2f} ms a frame{share}")
    if whole:
        rest = whole[2] - sum(ms for _n, (_u, _c, ms) in parts)
        lines.append(f"    {'(the glue between them)':24s} {'':27s} = {rest:6.2f} ms a frame")
    for name, (us, calls, ms) in scene + subset:
        lines.append(f"    {name:24s} {us:7.2f} us a call  x {calls:6.1f}  = {ms:6.2f} ms a frame")
    return "\n".join(lines)


def parse(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=35, help="the world's seed")
    ap.add_argument("--live", type=int, required=True,
                    help="as spawn_stress --live; needs --elapsed (N - 100) * 4")
    ap.add_argument("--elapsed", type=float, required=True, help="the run clock in seconds")
    ap.add_argument("--dormant", type=int, default=400, help="enemy records on the other islands")
    ap.add_argument("--rounds", type=int, default=200, help="rounds over the drawn enemies, per piece")
    args = ap.parse_args(argv)
    if args.rounds < 1:
        ap.error("--rounds must be 1 or more")
    return args


def main(argv=None, save_path: str | None = None) -> int:
    args = parse(argv)
    _game, ps = LP.packed_scene(args.seed, args.live, args.dormant, args.elapsed, save_path)
    print(report(measure(ps, args.rounds)))
    print(f"  boss at the end: {S.boss_state(ps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
