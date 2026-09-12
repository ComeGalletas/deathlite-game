"""Cut the Grave Totem bolt's strips out of `proyectile.png`.

`proyectile.png` is a 12 x 9 grid of 64 x 64 frames, one coloured effect per
row (assets journal, "Grave Totem bolt -- rework", 2026-09-12). Only the
blue row (the third from the top) is used, and the owner wants it as its
own sheet so nothing reads the big one at run time:

* `totem_bolt_blue.png`  -- the whole blue row, 12 frames: the source the
  two strips below are taken from (and a reference for anyone re-cutting).
* `totem_bolt_orb.png`   -- frames 3 4 5 6 5 4: the ball, authored as a
  pulse so the loader's plain forward loop breathes.
* `totem_bolt_burst.png` -- frames 6..11: the ball breaking into shards,
  played once where a bolt lands.

    python utilities/cut_totem_bolt_sheets.py            # writes the three
    python utilities/cut_totem_bolt_sheets.py --check    # exits 1 on a drift
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "assets", "effects", "weapons", "grave_totem")
SOURCE_NAME = "proyectile.png"
FRAME = 64
BLUE_ROW = 2                       # third from the top
ROW_FRAMES = 12
# (output file, frame indices into the blue row)
STRIPS = (
    ("totem_bolt_blue.png", tuple(range(ROW_FRAMES))),
    ("totem_bolt_orb.png", (3, 4, 5, 6, 5, 4)),
    ("totem_bolt_burst.png", (6, 7, 8, 9, 10, 11)),
)


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


def blue_row(source: pygame.Surface) -> list[pygame.Surface]:
    return [source.subsurface(pygame.Rect(i * FRAME, BLUE_ROW * FRAME, FRAME, FRAME)).copy()
            for i in range(ROW_FRAMES)]


def strip(frames: list[pygame.Surface], indices) -> pygame.Surface:
    out = pygame.Surface((FRAME * len(indices), FRAME), pygame.SRCALPHA)
    for k, i in enumerate(indices):
        out.blit(frames[i], (k * FRAME, 0))
    return out


def main(argv) -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    path = find_source(SOURCE_NAME)
    if path is None:
        print(f"{SOURCE_NAME} is not in the folder or in unused/ -- nothing to cut from")
        return 2
    frames = blue_row(pygame.image.load(path).convert_alpha())
    check = "--check" in argv
    bad = 0
    for name, indices in STRIPS:
        want = strip(frames, indices)
        path = os.path.join(FOLDER, name)
        if check:
            if not os.path.exists(path):
                print(f"missing {name}")
                bad += 1
                continue
            have = pygame.image.load(path).convert_alpha()
            same = (have.get_size() == want.get_size()
                    and pygame.image.tostring(have, "RGBA") == pygame.image.tostring(want, "RGBA"))
            print(f"{'ok     ' if same else 'DIFFERS'} {name}")
            bad += 0 if same else 1
        else:
            pygame.image.save(want, path)
            print(f"wrote {name}  {want.get_width()}x{want.get_height()}  frames {list(indices)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
