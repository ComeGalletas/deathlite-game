"""Cut the four treasure-chest strips out of `assets/items/chests/chests.png`.

The pack sheet is 384 x 256 at 32 px cells -- 12 x 8 -- but the three columns
of every family are **pixel-identical**, so the real content is 4 column
families x 2 row groups = **8 chest skins, 4 frames each**. The four frames of
a skin are an open animation: `closed`, `squash` (wide and low, the
anticipation), `stretch` (tall, the lid snapping up), `open`.

CB-9 (`journals/combat_balance_journal.md`) uses four of the eight skins, one
per chest rarity, chosen to match the rarity ink the game already uses:
wood = common (neutral), vine = uncommon (green), royal blue = rare (blue),
purple = epic (purple). Each is written as a horizontal 4-frame strip, the way
`cut_totem_sheets.py` writes the totem's actions, so the rig names one file
instead of reaching into the big sheet with offsets. The sheet stays in the
folder as the source; nothing reads it.

    python utilities/cut_chest_sheets.py            # writes the four strips
    python utilities/cut_chest_sheets.py --check    # exits 1 if any differs
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "assets", "items", "chests")
SOURCE = os.path.join(FOLDER, "chests.png")
CELL = 32
FRAMES = 4
# (output file, column family 0-3, row group 0-1, what it looks like).
# Column family f occupies source columns 3f..3f+2 (identical); row group g
# occupies rows 4g..4g+3, which are the four animation frames.
STRIPS = (
    ("chest_common.png", 1, 1, "plain wood"),
    ("chest_uncommon.png", 1, 0, "overgrown vine"),
    ("chest_rare.png", 2, 0, "royal blue + gold"),
    ("chest_epic.png", 0, 1, "purple + gold"),
)


def cut(source: pygame.Surface, family: int, group: int) -> pygame.Surface:
    """The four frames of one skin, side by side."""
    strip = pygame.Surface((CELL * FRAMES, CELL), pygame.SRCALPHA)
    for i in range(FRAMES):
        src = pygame.Rect(family * 3 * CELL, (group * 4 + i) * CELL, CELL, CELL)
        strip.blit(source, (i * CELL, 0), src)
    return strip


def main(argv) -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    source = pygame.image.load(SOURCE).convert_alpha()
    check = "--check" in argv
    bad = 0
    for name, family, group, look in STRIPS:
        strip = cut(source, family, group)
        path = os.path.join(FOLDER, name)
        if check:
            if not os.path.exists(path):
                print(f"missing {name}")
                bad += 1
                continue
            have = pygame.image.load(path).convert_alpha()
            same = (have.get_size() == strip.get_size()
                    and pygame.image.tostring(have, "RGBA")
                    == pygame.image.tostring(strip, "RGBA"))
            print(f"{'ok     ' if same else 'DIFFERS'} {name}")
            bad += 0 if same else 1
        else:
            pygame.image.save(strip, path)
            print(f"wrote {name}  {strip.get_width()}x{strip.get_height()}"
                  f"  ({look}, family {family}, rows {group * 4}-{group * 4 + 3})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
