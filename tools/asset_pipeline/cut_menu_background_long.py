"""Cut the ultrawide menu backdrop to 1920x800 from the delivered strip.

The delivered `menu_background_long_source.png` is 2496x800, a 3.12:1 strip
with clouds at both ends and a plain sea band in the middle (measured: no
cloud pixel between x 703 and x 1797). An ultrawide screen needs 800 x
aspect: 1867 for 21:9 nominal, 1911 for 3440x1440, 1920 for 3840x1600. The
owner picked 1920 (2.4:1, the widest of the common ultrawides, 2026-09-16):
the menu's cover scaling (`MenuState.draw_backdrop`) then shows the whole
strip on 3840x1600 and crops 4 px a side on 3440x1440.

So `CUT` = 576 px are removed from the centre of the plain band -- x 960 to
1535 -- and the two halves are joined: 359 px of plain sea remain either side
of the seam, well clear of the clouds, so nothing shows. The source stays in
`unused/` beside the strip (the project's rule for delivered art); the game
reads `menu_background_long.png` only.

    python tools/asset_pipeline/cut_menu_background_long.py            # writes the strip
    python tools/asset_pipeline/cut_menu_background_long.py --check    # exits 1 if it differs
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# repo root: this file lives in tools/asset_pipeline/, two folders down
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FOLDER = os.path.join(ROOT, "assets", "ui", "start_screen")
SOURCE = os.path.join(FOLDER, "unused", "menu_background_long_source.png")
OUT = os.path.join(FOLDER, "menu_background_long.png")

SOURCE_SIZE = (2496, 800)
WIDTH = 1920                 # the owner's pick: 2.4:1
CUT = SOURCE_SIZE[0] - WIDTH  # 576 px out of the middle
LEFT = (SOURCE_SIZE[0] - CUT) // 2       # 960: the first removed column
RIGHT = LEFT + CUT                       # 1536: the first kept column after the cut


def cut(source: pygame.Surface) -> pygame.Surface:
    if source.get_size() != SOURCE_SIZE:
        raise SystemExit(f"source is {source.get_size()}, expected {SOURCE_SIZE}")
    w, h = SOURCE_SIZE
    out = pygame.Surface((WIDTH, h), pygame.SRCALPHA)
    out.blit(source, (0, 0), pygame.Rect(0, 0, LEFT, h))
    out.blit(source, (LEFT, 0), pygame.Rect(RIGHT, 0, w - RIGHT, h))
    return out


def main(argv) -> int:
    pygame.init()
    want = cut(pygame.image.load(SOURCE))
    if "--check" in argv:
        if not os.path.exists(OUT):
            print("missing", OUT)
            return 1
        have = pygame.image.load(OUT)
        same = (have.get_size() == want.get_size()
                and pygame.image.tostring(have, "RGBA") == pygame.image.tostring(want, "RGBA"))
        print("ok" if same else "differs", OUT)
        return 0 if same else 1
    pygame.image.save(want, OUT)
    print("wrote", OUT, want.get_size())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
