"""Build the sanctuary's heal loop strip from the Super Pixel Effects
Gigapack (journal: key_icons_journal.md, pass 3).

The sanctuary used to be skinned with an 11-frame leaf sweep; the owner
picked `spell_heal_002` (rising green crosses, 36 frames of 128 px at 15
fps) from the reserve art on 2026-09-19. The pack ships every frame as its
own PNG under `PNG/`; the game reads one horizontal strip, the way every
other rig does, so this writes

    assets/terrain/facilities/heal_effect.png      36 x 128 px wide, 128 tall

from

    assets/unused/Super Pixel Effects Gigapack/PNG/Fantasy Spells/
        spell_heal_002/spell_heal_002_large_green/frame0000.png ...

`assets/unused/` is untracked and lives only in the main checkout, so the
source is looked up from the repository root; the strip itself is tracked.
The previous leaf strip is kept beside the source as
`assets/unused/effects/heal_leaves_2026-09.png` the first time this runs.

    python tools/asset_pipeline/cut_heal_effect.py            # writes the strip
    python tools/asset_pipeline/cut_heal_effect.py --check    # exits 1 if it differs
"""
from __future__ import annotations

import glob
import os
import shutil
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _unused_root() -> str:
    """The checkout that holds `assets/unused/`: this one, or -- from a git
    worktree, where the untracked folder does not exist -- the main
    checkout the worktree was made from."""
    if os.path.isdir(os.path.join(ROOT, "assets", "unused")):
        return ROOT
    try:
        import subprocess
        common = subprocess.check_output(["git", "rev-parse", "--git-common-dir"],
                                         cwd=ROOT, text=True).strip()
        main = os.path.dirname(os.path.abspath(os.path.join(ROOT, common)))
        if os.path.isdir(os.path.join(main, "assets", "unused")):
            return main
    except Exception:            # no git, or not a repository
        pass
    return ROOT


UNUSED = os.path.join(_unused_root(), "assets", "unused")
SOURCE_DIR = os.path.join(UNUSED, "Super Pixel Effects Gigapack", "PNG",
                          "Fantasy Spells", "spell_heal_002", "spell_heal_002_large_green")
OUT = os.path.join(ROOT, "assets", "terrain", "facilities", "heal_effect.png")
ARCHIVE = os.path.join(UNUSED, "effects", "heal_leaves_2026-09.png")
FRAME = 128
FRAMES = 36


def build(frames: list[str]) -> pygame.Surface:
    strip = pygame.Surface((FRAME * len(frames), FRAME), pygame.SRCALPHA)
    for i, path in enumerate(frames):
        img = pygame.image.load(path).convert_alpha()
        if img.get_size() != (FRAME, FRAME):
            raise SystemExit(f"{path}: expected {FRAME}x{FRAME}, got {img.get_size()}")
        strip.blit(img, (i * FRAME, 0))
    return strip


def main(argv) -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    frames = sorted(glob.glob(os.path.join(SOURCE_DIR, "frame*.png")))
    if len(frames) != FRAMES:
        print(f"expected {FRAMES} frames under {SOURCE_DIR}, found {len(frames)}")
        return 1
    strip = build(frames)
    if "--check" in argv:
        if not os.path.exists(OUT):
            print("missing", OUT)
            return 1
        have = pygame.image.load(OUT).convert_alpha()
        same = (have.get_size() == strip.get_size()
                and pygame.image.tobytes(have, "RGBA") == pygame.image.tobytes(strip, "RGBA"))
        print("ok" if same else "DIFFERS", OUT)
        return 0 if same else 1
    if os.path.exists(OUT) and not os.path.exists(ARCHIVE):
        old = pygame.image.load(OUT)
        if old.get_size() != strip.get_size():
            os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
            shutil.copyfile(OUT, ARCHIVE)
            print("archived the leaf strip as", ARCHIVE)
    pygame.image.save(strip, OUT)
    print("wrote", OUT, strip.get_size())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
