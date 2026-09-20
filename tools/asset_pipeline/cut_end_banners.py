"""Cut the two end banners out of the Super Pixel Effects Gigapack.

The "GAME OVER" and "You Won!" text animations shown between the run and its
summary screen (journal: `documentation/journals/end_banner_journal.md`,
2026-09-19). The pack ships every symbol as a folder of per-frame PNGs in six
colourways and two sizes; the game reads one grid sheet per banner, so the
pack itself (untracked, under `assets/unused/`) is never read at run time:

* `game_over.png` -- `symbol_game_over_text_001`, large, red: 44 frames of
  416 x 128, five per row (2080 x 1152).
* `you_won.png` -- `symbol_you_won_text_001`, large, yellow: 42 frames of
  288 x 128, seven per row (2016 x 768).

Both play at the pack's 15 FPS, once: letters fly in, hold, fly out. The
rigs in `data/ui/ui_sprites.json` (`end_banner_loss` / `end_banner_win`)
declare the frame size, count and `cols` so `Assets` can walk the grid.

    python tools/asset_pipeline/cut_end_banners.py            # writes the sheets
    python tools/asset_pipeline/cut_end_banners.py --check    # exits 1 on a drift
    python tools/asset_pipeline/cut_end_banners.py --source DIR   # the pack elsewhere
"""
from __future__ import annotations

import glob
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

# repo root: this file lives in tools/asset_pipeline/, two folders down
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(ROOT, "assets", "ui", "end_banners")
PACK = os.path.join(ROOT, "assets", "unused", "Super Pixel Effects Gigapack")

# (output name, symbol, colourway, frame size, frames, columns)
BANNERS = (
    ("game_over.png", "symbol_game_over_text_001", "red", (416, 128), 44, 5),
    ("you_won.png", "symbol_you_won_text_001", "yellow", (288, 128), 42, 7),
)


def frame_files(pack: str, symbol: str, colour: str) -> list[str]:
    folder = os.path.join(pack, "PNG", "Symbols", symbol, f"{symbol}_large_{colour}")
    return sorted(glob.glob(os.path.join(folder, "frame*.png")))


def grid(files: list[str], frame: tuple[int, int], count: int, cols: int) -> pygame.Surface:
    fw, fh = frame
    rows = -(-count // cols)
    out = pygame.Surface((fw * cols, fh * rows), pygame.SRCALPHA)
    for i, path in enumerate(files[:count]):
        img = pygame.image.load(path)
        if img.get_size() != (fw, fh):
            raise ValueError(f"{path}: {img.get_size()} is not {frame}")
        out.blit(img, ((i % cols) * fw, (i // cols) * fh))
    return out


def same(a: pygame.Surface, b: pygame.Surface) -> bool:
    return (a.get_size() == b.get_size()
            and pygame.image.tobytes(a, "RGBA") == pygame.image.tobytes(b, "RGBA"))


def main(argv) -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    check = "--check" in argv
    pack = PACK
    if "--source" in argv:
        pack = argv[argv.index("--source") + 1]
    status = 0
    for name, symbol, colour, frame, count, cols in BANNERS:
        files = frame_files(pack, symbol, colour)
        target = os.path.join(OUT_DIR, name)
        if len(files) < count:
            # The pack is authoring input and may not be beside this checkout;
            # the sheet is what ships, so report rather than crash.
            print(f"{name}: source frames not found under {pack} "
                  f"({len(files)} of {count}); sheet "
                  f"{'present' if os.path.exists(target) else 'MISSING'}")
            if not os.path.exists(target):
                status = 1
            continue
        fresh = grid(files, frame, count, cols)
        if check:
            if not os.path.exists(target):
                print(f"{name}: missing")
                status = 1
                continue
            have = pygame.image.load(target)
            if same(fresh, have):
                print(f"{name}: ok")
            else:
                print(f"{name}: DIFFERS from a fresh cut")
                status = 1
        else:
            os.makedirs(OUT_DIR, exist_ok=True)
            pygame.image.save(fresh, target)
            print(f"wrote {target} {fresh.get_size()}")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
