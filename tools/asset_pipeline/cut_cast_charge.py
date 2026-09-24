"""Join the Hexcaller's cast wind-up into the strip the game reads (ENT-013).

The source is the Super Pixel Effects Gigapack's
`Sci-fi/scifi_charge_up_003/scifi_charge_up_003_small_violet` -- 16 loose
64 x 64 frames: a pink-violet ring with orbs gathering and pulsing inside
it. They are archived, tracked, in `assets/enemies/hex_shaman/unused/
cast_charge/` (the reserve they came from is untracked), so the check below
always has its input:

* `hex_shaman_cast_charge.png` -- the 16 frames in order, one row, 1024 x 64.
  Played at the spot the Hexcaller's cast will land, for its whole wind-up.

    python tools/asset_pipeline/cut_cast_charge.py            # writes the strip
    python tools/asset_pipeline/cut_cast_charge.py --check    # exits 1 on a drift
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# repo root: this file lives in tools/asset_pipeline/, two folders down
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FOLDER = os.path.join(ROOT, "assets", "enemies", "hex_shaman")
SOURCE = os.path.join(FOLDER, "unused", "cast_charge")
STRIP_NAME = "hex_shaman_cast_charge.png"
FRAME = 64


def frames() -> list[str]:
    """The archived source frames, in order (`frame0000.png` ...)."""
    if not os.path.isdir(SOURCE):
        return []
    return sorted(f for f in os.listdir(SOURCE) if f.lower().endswith(".png"))


def strip(names: list[str]) -> pygame.Surface:
    out = pygame.Surface((FRAME * len(names), FRAME), pygame.SRCALPHA)
    for i, name in enumerate(names):
        img = pygame.image.load(os.path.join(SOURCE, name)).convert_alpha()
        if img.get_size() != (FRAME, FRAME):
            raise ValueError(f"{name} is {img.get_size()}, expected {FRAME} x {FRAME}")
        out.blit(img, (i * FRAME, 0))
    return out


def main(argv) -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    names = frames()
    if not names:
        print(f"no source frames in {SOURCE} -- nothing to join")
        return 2
    want = strip(names)
    out = os.path.join(FOLDER, STRIP_NAME)
    if "--check" in argv:
        if not os.path.exists(out):
            print(f"missing {STRIP_NAME}")
            return 1
        have = pygame.image.load(out).convert_alpha()
        same = (have.get_size() == want.get_size()
                and pygame.image.tostring(have, "RGBA") == pygame.image.tostring(want, "RGBA"))
        print(f"{'ok     ' if same else 'DIFFERS'} {STRIP_NAME}")
        return 0 if same else 1
    pygame.image.save(want, out)
    print(f"wrote {STRIP_NAME}  {want.get_width()}x{want.get_height()}  {len(names)} frames")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
