"""Cut the enemy spawn burst out of `77.png`.

`77.png` is a 12 x 9 grid of 64 x 64 frames, one coloured effect per row --
the same pack and layout as the totem bolt's `proyectile.png` (assets
journal, "Enemy spawn burst", 2026-09-12). Only the **bottom row, the dark
purple one**, is used, and the owner wants it as its own sheet so nothing
reads the grid at run time:

* `enemy_spawn.png` -- the whole bottom row, 12 frames in order: a spark
  that swells into a ball, the ball breaking into a ring of shards, and the
  stray specks it leaves. Played once, sized to the enemy it announces.

    python tools/asset_pipeline/cut_spawn_sheet.py            # writes the strip
    python tools/asset_pipeline/cut_spawn_sheet.py --check    # exits 1 on a drift
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# repo root: this file lives in tools/asset_pipeline/, two folders down
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FOLDER = os.path.join(ROOT, "assets", "effects", "spawn")
SOURCE_NAME = "77.png"
STRIP_NAME = "enemy_spawn.png"
FRAME = 64
PURPLE_ROW = 8                     # the bottom row of nine
ROW_FRAMES = 12


def find_source(name: str) -> str | None:
    """The authoring source, in the folder or archived under `unused/`.

    The sheet the game reads is the cut strip; the grid is authoring input
    and is archived under `unused/` once spent (owner, 2026-09-12). `--check`
    still has to find it, so both places are searched. `None` means the
    source is gone entirely -- the strip is still what ships, so the caller
    reports rather than crashes.
    """
    for folder in (FOLDER, os.path.join(FOLDER, "unused")):
        path = os.path.join(folder, name)
        if os.path.exists(path):
            return path
    return None


def purple_row(source: pygame.Surface) -> pygame.Surface:
    out = pygame.Surface((FRAME * ROW_FRAMES, FRAME), pygame.SRCALPHA)
    out.blit(source, (0, 0), pygame.Rect(0, PURPLE_ROW * FRAME, FRAME * ROW_FRAMES, FRAME))
    return out


def main(argv) -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    path = find_source(SOURCE_NAME)
    if path is None:
        print(f"{SOURCE_NAME} is not in the folder or in unused/ -- nothing to cut from")
        return 2
    want = purple_row(pygame.image.load(path).convert_alpha())
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
    print(f"wrote {STRIP_NAME}  {want.get_width()}x{want.get_height()}  row {PURPLE_ROW}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
