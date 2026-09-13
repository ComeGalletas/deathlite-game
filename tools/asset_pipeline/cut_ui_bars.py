"""Cut the HUD bar and level-gem pieces out of the big UI pack sheets.

`assets/ui/base/04.png` is a 336 x 240 sheet on a uniform 48 x 16 grid --
seven columns by fifteen rows -- holding three families of horizontal bar
(slab, hexagon, capsule) plus a vertical section. The game uses the **hexagon**
family, rows 4-7: column 0 carries the housings (silver, grey, copper), column
1 the full fills (red, yellow, blue, green) and column 6 the empty trough.
`base/01.png` is 272 x 144 and holds the gem medallions; the game uses the blue
socket ring and the blue gem body, which are concentric inside their own 48 x 48
cells.

Every piece below is written to its own file **named exactly after the rig that
draws it**, so `data/ui/ui_sprites.json` names one file instead of reaching into a
big sheet with offsets, and "which pixels is this rig?" is answerable from the
filename alone (owner, 2026-09-12). The rects are the tight art boxes measured
off the sheets, which is why the rigs no longer need a `content` crop -- the
file *is* the crop. `caps` and `well` stay in the rig: they describe how the
art is rebuilt, not where it lives.

The big sheets stay in `assets/ui/base/` as the source; nothing reads them.

    python tools/asset_pipeline/cut_ui_bars.py            # writes the ten pieces
    python tools/asset_pipeline/cut_ui_bars.py --check    # exits 1 if any differs
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# repo root: this file lives in tools/asset_pipeline/, two folders down
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.join(ROOT, "assets", "ui", "base")
OUT = os.path.join(ROOT, "assets", "ui", "hud")

# (output file / rig name, source sheet, (x, y, w, h) art box, what it is).
# The hex family sits at rows 4-7 of 04.png: y 64, 80, 96, 112. A housing's art
# box is 42 x 11 inside its cell; a fill's is 34 x 5, and it drops into the
# housing at offset (0, 0) because both carry their own rails on the same
# scanlines -- which is what the rig's `well` records.
PIECES = (
    ("bar_hex_frame_silver.png", "04.png", (3, 67, 42, 11), "hex housing, silver"),
    ("bar_hex_frame_grey.png", "04.png", (3, 83, 42, 11), "hex housing, grey"),
    ("bar_hex_frame_copper.png", "04.png", (3, 99, 42, 11), "hex housing, copper"),
    ("bar_hex_fill_red.png", "04.png", (55, 70, 34, 5), "hex fill, red"),
    ("bar_hex_fill_yellow.png", "04.png", (55, 86, 34, 5), "hex fill, yellow"),
    ("bar_hex_fill_blue.png", "04.png", (55, 102, 34, 5), "hex fill, blue"),
    ("bar_hex_fill_green.png", "04.png", (55, 118, 34, 5), "hex fill, green"),
    # Column 6 of the same family: the trough with no fill in it. Identical in
    # all four colour rows, so one file serves every bar.
    ("bar_hex_empty.png", "04.png", (295, 70, 34, 5), "hex empty trough"),
    # Whole 48 x 48 cells, not the tight ink: the ring and the gem are
    # concentric within their cells, and cropping each to its own ink would
    # throw away exactly the offset that seats one inside the other.
    ("gem_socket_blue.png", "01.png", (176, 0, 48, 48), "gem socket ring, blue"),
    ("gem_core_blue.png", "01.png", (176, 48, 48, 48), "gem body, blue"),
)


def cut(sheets: dict, sheet: str, rect) -> pygame.Surface:
    return sheets[sheet].subsurface(pygame.Rect(*rect)).copy()


def main(argv) -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    sheets = {name: pygame.image.load(os.path.join(BASE, name)).convert_alpha()
              for name in {s for _n, s, _r, _d in PIECES}}
    os.makedirs(OUT, exist_ok=True)
    check = "--check" in argv
    bad = 0
    for name, sheet, rect, what in PIECES:
        piece = cut(sheets, sheet, rect)
        path = os.path.join(OUT, name)
        if check:
            if not os.path.exists(path):
                print(f"missing {name}")
                bad += 1
                continue
            have = pygame.image.load(path).convert_alpha()
            same = (have.get_size() == piece.get_size()
                    and pygame.image.tostring(have, "RGBA")
                    == pygame.image.tostring(piece, "RGBA"))
            print(f"{'ok     ' if same else 'DIFFERS'} {name}")
            bad += 0 if same else 1
        else:
            pygame.image.save(piece, path)
            print(f"wrote {name:<28} {piece.get_width():>2}x{piece.get_height():<2}"
                  f"  ({what}, {sheet} at {rect[0]},{rect[1]})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
