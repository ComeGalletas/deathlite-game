"""Recolour `fire.png` blue for the Grave Totem bolt's tail.

The flame is orange, yellow and white (assets journal, "Grave Totem bolt --
rework", 2026-09-12). The loader's multiply `tint` recolours the *white*
`dust_puff` but cannot turn orange into blue -- orange x blue is mud -- so
the recolour is done once here: every pixel keeps its alpha and its
brightness order, and its brightness picks a colour off a blue ramp (dark
navy where the flame was orange, cyan where it was yellow, the white core
kept white). Shape and shading survive; only the hue moves.

    python tools/asset_pipeline/recolour_totem_fire.py            # writes totem_bolt_fire.png
    python tools/asset_pipeline/recolour_totem_fire.py --check    # exits 1 on a drift
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# repo root: this file lives in tools/asset_pipeline/, two folders down
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FOLDER = os.path.join(ROOT, "assets", "effects", "weapons", "grave_totem")
SOURCE_NAME = "fire.png"
TARGET = os.path.join(FOLDER, "totem_bolt_fire.png")
# (luminance 0..1, colour): the ramp, sampled by linear interpolation.
RAMP = ((0.00, (12, 24, 80)), (0.45, (30, 110, 230)), (0.75, (90, 200, 255)),
        (0.92, (190, 240, 255)), (1.00, (255, 255, 255)))


def find_source(name: str) -> str | None:
    """The authoring source, in the folder or archived under `unused/`.

    The sheets the game reads are the cut strips; the big source sheets are
    reference and get moved into `unused/` once they are spent (owner,
    2026-09-12). `--check` still has to find them, so both places are
    searched. `None` means the source is gone entirely -- the strips are
    still what ships, so the caller reports rather than crashes.
    """
    for folder in (FOLDER, os.path.join(FOLDER, "unused")):
        path = os.path.join(folder, name)
        if os.path.exists(path):
            return path
    return None


def ramp(lum: float) -> tuple[int, int, int]:
    lum = min(1.0, max(0.0, lum))
    for (l0, c0), (l1, c1) in zip(RAMP, RAMP[1:]):
        if lum <= l1:
            t = 0.0 if l1 == l0 else (lum - l0) / (l1 - l0)
            return tuple(int(round(a + (b - a) * t)) for a, b in zip(c0, c1))
    return RAMP[-1][1]


def recolour(source: pygame.Surface) -> pygame.Surface:
    w, h = source.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        for x in range(w):
            r, g, b, a = source.get_at((x, y))
            if a == 0:
                continue
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            out.set_at((x, y), (*ramp(lum), a))
    return out


def main(argv) -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    path = find_source(SOURCE_NAME)
    if path is None:
        print(f"{SOURCE_NAME} is not in the folder or in unused/ -- nothing to recolour")
        return 2
    want = recolour(pygame.image.load(path).convert_alpha())
    if "--check" in argv:
        if not os.path.exists(TARGET):
            print("missing totem_bolt_fire.png")
            return 1
        have = pygame.image.load(TARGET).convert_alpha()
        same = (have.get_size() == want.get_size()
                and pygame.image.tostring(have, "RGBA") == pygame.image.tostring(want, "RGBA"))
        print(f"{'ok     ' if same else 'DIFFERS'} totem_bolt_fire.png")
        return 0 if same else 1
    pygame.image.save(want, TARGET)
    print(f"wrote totem_bolt_fire.png  {want.get_width()}x{want.get_height()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
