"""Cut the Grave Totem's action strips out of `Fire_Totem_blue-Sheet.png`.

The blue sheet is a 14 x 5 grid of 64 x 96 frames, one action per row
(assets journal, "Grave Totem sprite -- wiring", 2026-09-12). The rig
(`data/weapon_sprites.json`, `grave_totem`) names one file per action rather
than the big sheet with row offsets, so the strips are cut once here and
committed. Row 2 (`attack`: eight idle frames then the burst) is not cut --
`idle` + `attack` (row 3, the burst alone) cover it.

    python utilities/cut_totem_sheets.py            # writes the four strips
    python utilities/cut_totem_sheets.py --check    # exits 1 if any differs
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "assets", "effects", "weapons", "grave_totem")
SOURCE_NAME = "Fire_Totem_blue-Sheet.png"
FRAME_W, FRAME_H = 64, 96
# (output file, source row, frame count) -- the owner keeps the lift-off at
# the start of `disappear` (2026-09-12), so that row is cut whole.
STRIPS = (
    ("totem_appear.png", 0, 8),
    ("totem_idle.png", 1, 7),
    ("totem_attack.png", 3, 7),
    ("totem_disappear.png", 4, 14),
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


def cut(source: pygame.Surface, row: int, frames: int) -> pygame.Surface:
    strip = pygame.Surface((FRAME_W * frames, FRAME_H), pygame.SRCALPHA)
    strip.blit(source, (0, 0), pygame.Rect(0, row * FRAME_H, FRAME_W * frames, FRAME_H))
    return strip


def main(argv) -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    path = find_source(SOURCE_NAME)
    if path is None:
        print(f"{SOURCE_NAME} is not in the folder or in unused/ -- nothing to cut from")
        return 2
    source = pygame.image.load(path).convert_alpha()
    check = "--check" in argv
    bad = 0
    for name, row, frames in STRIPS:
        strip = cut(source, row, frames)
        path = os.path.join(FOLDER, name)
        if check:
            if not os.path.exists(path):
                print(f"missing {name}")
                bad += 1
                continue
            have = pygame.image.load(path).convert_alpha()
            same = (have.get_size() == strip.get_size()
                    and pygame.image.tostring(have, "RGBA") == pygame.image.tostring(strip, "RGBA"))
            print(f"{'ok     ' if same else 'DIFFERS'} {name}")
            bad += 0 if same else 1
        else:
            pygame.image.save(strip, path)
            print(f"wrote {name}  {strip.get_width()}x{strip.get_height()}  ({frames} frames, row {row})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
