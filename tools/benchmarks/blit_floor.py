"""What pygame alone costs to put a crowd on screen (RND-010.3,
`crowd_performance_plan.md` appendix A.1): `n` enemy-sized sprites blitted
onto a surface of the given size, with no game logic, sprite only and then
with a shadow under and a bar over each. The floor the draw can be cut
toward, whatever the game's own code costs on top. Every frame starts by
filling the whole surface, as the appendix did, so each row includes that
fill; `--counts 0` times the fill alone, to take it back out.

    python -m tools.benchmarks.blit_floor                         # 1600x900 and 2560x1080, 100 to 300
    SDL_VIDEODRIVER=windows python -m tools.benchmarks.blit_floor --sizes 2560x1080

Headless by default, like the stress harness: the dummy driver's surface,
not the cost on screen (in bash; in PowerShell set
`$env:SDL_VIDEODRIVER = "windows"` first). The sprite is the blue
warrior's first run frame at 112 px, one size among the many the rigs are
drawn at (from small to 467x367 at the owner's zoom), so the floor is
one sprite's; the crowd's positions are seeded (`random.Random(1)`).
Percentiles follow `tools/benchmarks/stats.py` (nearest index, half to
even), where the plan's appendix took `int(q * n)`: the same samples can
read one index apart.
"""
from __future__ import annotations

import argparse
import os
import random
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tools.benchmarks.stats import percentile

SPRITE = "assets/characters/blue/warrior/run.png"
SPRITE_PX = 112


def props():
    """`(sprite, shadow, bar)`: the warrior's first run frame at
    `SPRITE_PX`, a 48 x 20 shadow ellipse and a 40 x 5 bar. Needs a display
    mode set (`convert_alpha`)."""
    import pygame
    sheet = pygame.image.load(SPRITE).convert_alpha()
    fw = sheet.get_height()
    sprite = pygame.transform.smoothscale(sheet.subsurface((0, 0, fw, fw)), (SPRITE_PX, SPRITE_PX))
    shadow = pygame.Surface((48, 20), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 110), shadow.get_rect())
    bar = pygame.Surface((40, 5))
    bar.fill((200, 40, 40))
    return sprite, shadow, bar


def positions(n: int, w: int, h: int, seed: int = 1) -> list[tuple[float, float]]:
    rng = random.Random(seed)
    return [(rng.random() * w, rng.random() * h) for _ in range(n)]


def frame_times(screen, sprite, shadow, bar, pos, frames: int, extras: bool) -> list[float]:
    """Milliseconds per frame: clear, then every sprite (with its shadow
    and bar when `extras`), as the appendix does."""
    half = SPRITE_PX // 2
    out = []
    for _ in range(frames):
        t0 = time.perf_counter()
        screen.fill((20, 20, 30))
        for x, y in pos:
            sx, sy = int(x) - half, int(y) - half
            if extras:
                screen.blit(shadow, (sx + 32, sy + 92))
            screen.blit(sprite, (sx, sy))
            if extras:
                screen.blit(bar, (sx + 36, sy - 6))
        out.append((time.perf_counter() - t0) * 1000.0)
    return out


def line(w: int, h: int, n: int, extras: bool, times: list[float]) -> str:
    s = sorted(times)
    label = "sprite+shadow+bar" if extras else "sprite only"
    return (f"{w}x{h}  n={n:3d}  {label:18s}  p50 {percentile(s, 0.5):6.2f}  "
            f"p90 {percentile(s, 0.9):6.2f} ms")


def parse(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sizes", default="1600x900,2560x1080",
                    help="surface sizes, WxH, comma separated")
    ap.add_argument("--counts", default="100,200,300", help="sprites per frame, comma separated")
    ap.add_argument("--frames", type=int, default=120, help="frames timed per row")
    args = ap.parse_args(argv)
    try:
        args.sizes = [tuple(int(v) for v in s.lower().split("x")) for s in args.sizes.split(",")]
        args.counts = [int(c) for c in args.counts.split(",")]
    except ValueError:
        ap.error("--sizes takes WxH,WxH and --counts N,N")
    if any(len(s) != 2 or min(s) < 1 for s in args.sizes) or min(args.counts) < 0 or args.frames < 1:
        ap.error("sizes and frames must be positive, counts 0 or more")
    return args


def main(argv=None) -> int:
    import pygame
    args = parse(argv)
    pygame.init()
    for w, h in args.sizes:
        screen = pygame.display.set_mode((w, h))
        sprite, shadow, bar = props()
        for n in args.counts:
            pos = positions(n, w, h)
            for extras in (False, True):
                print(line(w, h, n, extras, frame_times(screen, sprite, shadow, bar, pos,
                                                        args.frames, extras)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
