"""Ship the buff buildings, their dressing and their feedback effects
(journal: buff_buildings_journal.md).

Everything the buff buildings draw comes from the reserve art under
`assets/unused/` (untracked, main checkout only -- see `_unused_root`), so
this script is the record of what was taken from where, and re-running it
reproduces every tracked file it writes:

    assets/buildings/general/<kind>.png       the five buildings (+ the mine's used state)
    assets/buildings/dressing/*.png           gold stones, wood, tools, bones, skull spikes
    assets/effects/buffs/<kind>.png           the Gigapack spell strips, one per buff
    assets/ui/hud/buffs/<kind>.png            a 32 px still per buff for the HUD row
    assets/projectiles/pinball.png            the pinball (the pack's yellow orb)

The Tiny Swords pieces are copied as they are. The Gigapack ships every
frame as its own PNG; the game reads one horizontal strip, so those are
packed the way `cut_heal_effect.py` packs the sanctuary loop.

    python tools/asset_pipeline/cut_buff_buildings.py           # writes everything
    python tools/asset_pipeline/cut_buff_buildings.py --meta    # prints the rig metadata
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
    if os.path.isdir(os.path.join(ROOT, "assets", "unused")):
        return ROOT
    try:
        import subprocess
        common = subprocess.check_output(["git", "rev-parse", "--git-common-dir"],
                                         cwd=ROOT, text=True).strip()
        main = os.path.dirname(os.path.abspath(os.path.join(ROOT, common)))
        if os.path.isdir(os.path.join(main, "assets", "unused")):
            return main
    except Exception:
        pass
    return ROOT


UNUSED = os.path.join(_unused_root(), "assets", "unused")
GIGA = os.path.join(UNUSED, "Super Pixel Effects Gigapack", "PNG")

KINDS = ("magnet", "turbo", "haste", "pinball", "vampire")

# destination under assets/ -> source under assets/unused/
COPIES = {
    "buildings/general/magnet.png": "buildings/general/gold_mine/goldmine_active.png",
    "buildings/general/magnet_used.png": "buildings/general/gold_mine/goldmine_inactive.png",
    "buildings/general/turbo.png": "enemies/extra/goblin_hut/goblin_hut.png",
    "buildings/general/haste.png": "enemies/extra/gnome_buildings/gnome_tower.png",
    "buildings/general/pinball.png": "enemies/extra/cave/cave_idle.png",
    "buildings/general/vampire.png": "enemies/extra/dead_tree/dead_tree.png",
    "projectiles/pinball.png": "orbs/orb_yellow.png",
    "buildings/dressing/wood.png": "terrain/resources/wood/wood_resource.png",
}
for _i in range(1, 7):
    COPIES[f"buildings/dressing/gold_{_i}.png"] = f"terrain/resources/gold/gold_stone_{_i}.png"
for _i in range(1, 5):
    COPIES[f"buildings/dressing/tool_{_i}.png"] = f"terrain/resources/tools/tool_{_i}.png"
for _i in range(1, 4):
    COPIES[f"buildings/dressing/bones_{_i}.png"] = f"enemies/extra/skull_decorations/bones_{_i}.png"
for _i in range(1, 3):
    COPIES[f"buildings/dressing/skull_spike_{_i}.png"] = f"enemies/extra/skull_decorations/skull_spike_{_i}.png"

# The frame width of each building sheet (every frame is the sheet's height).
# The dead tree is one 384 px frame, not two of 192; the goblin hut (Turbo,
# owner, 2026-09-20, replacing the pirate tower) is sixteen of 192.
FRAME_W = {"magnet": 192, "turbo": 192, "haste": 128, "pinball": 192, "vampire": 384}

# buff -> (Gigapack effect folder, colour theme). All 128 px "large" strips.
STRIPS = {
    "magnet": ("Fantasy Spells/spell_absorb_001", "yellow"),
    "turbo": ("Fantasy Spells/spell_buff_001", "orange"),
    "haste": ("Fantasy Spells/spell_haste_001", "blue"),
    "pinball": ("Fantasy Spells/spell_dispel_001", "violet"),
    "vampire": ("Fantasy Spells/spell_attack_up_001", "red"),
}
FRAME = 128

# buff -> (Gigapack effect folder, colour, frame index, size variant) for the
# HUD icon: one still, squared and scaled to ICON px. The two Symbols are
# drawn as icons already; the other three take the frame of their own
# effect that reads best.
ICONS = {
    "magnet": ("Fantasy Spells/spell_absorb_001", "yellow", 14, "large"),
    "turbo": ("Symbols/symbol_defense_up_001", "orange", 20, "small"),
    "haste": ("Fantasy Spells/spell_haste_001", "blue", 4, "large"),
    "pinball": ("Fantasy Spells/spell_dispel_001", "violet", 10, "large"),
    "vampire": ("Symbols/symbol_attack_up_001", "red", 20, "small"),
}
ICON = 32


def _frames(folder: str, colour: str, size: str = "large") -> list[str]:
    name = os.path.basename(folder)
    d = os.path.join(GIGA, folder, f"{name}_{size}_{colour}")
    frames = sorted(glob.glob(os.path.join(d, "frame*.png")))
    if not frames:
        raise SystemExit(f"no frames under {d}")
    return frames


def _strip(frames: list[str]) -> pygame.Surface:
    strip = pygame.Surface((FRAME * len(frames), FRAME), pygame.SRCALPHA)
    for i, path in enumerate(frames):
        img = pygame.image.load(path).convert_alpha()
        if img.get_size() != (FRAME, FRAME):
            raise SystemExit(f"{path}: expected {FRAME}x{FRAME}, got {img.get_size()}")
        strip.blit(img, (i * FRAME, 0))
    return strip


def _icon(path: str) -> pygame.Surface:
    img = pygame.image.load(path).convert_alpha()
    box = img.get_bounding_rect(min_alpha=8)
    if box.width == 0:
        raise SystemExit(f"{path}: empty frame")
    side = max(box.width, box.height)
    square = pygame.Surface((side, side), pygame.SRCALPHA)
    square.blit(img, ((side - box.width) // 2 - box.x, (side - box.height) // 2 - box.y))
    return pygame.transform.smoothscale(square, (ICON, ICON))


def meta() -> None:
    """Print the rig metadata (`frame`, `anchor`, `paint`, `footprint`) for
    each building sheet, measured from its first frame the way the house
    rigs are: the anchor is the painted box's bottom centre."""
    import json
    for kind in KINDS:
        path = os.path.join(ROOT, "assets", "buildings", "general", f"{kind}.png")
        img = pygame.image.load(path)
        w, h = img.get_size()
        fw = FRAME_W[kind]
        first = img.subsurface((0, 0, fw, h))
        box = first.get_bounding_rect(min_alpha=8)
        print(kind, json.dumps({"frame": [fw, h], "anchor": [box.centerx, box.bottom],
                                "paint": [box.x, box.y, box.w, box.h],
                                "footprint": box.w, "frames": w // fw}))
    for name in sorted(os.listdir(os.path.join(ROOT, "assets", "buildings", "dressing"))):
        img = pygame.image.load(os.path.join(ROOT, "assets", "buildings", "dressing", name))
        box = img.get_bounding_rect(min_alpha=8)
        print(name, img.get_size(), "anchor", [box.centerx, box.bottom], "paint", list(box))


def main(argv) -> int:
    pygame.init()
    pygame.display.set_mode((1, 1))
    if "--meta" in argv:
        meta()
        return 0
    for dst, src in COPIES.items():
        out = os.path.join(ROOT, "assets", dst)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copyfile(os.path.join(UNUSED, src), out)
        print("copied", dst)
    for kind, (folder, colour) in STRIPS.items():
        strip = _strip(_frames(folder, colour))
        out = os.path.join(ROOT, "assets", "effects", "buffs", f"{kind}.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        pygame.image.save(strip, out)
        print("wrote", out, strip.get_size())
    for kind, (folder, colour, index, size) in ICONS.items():
        frames = _frames(folder, colour, size)
        icon = _icon(frames[min(index, len(frames) - 1)])
        out = os.path.join(ROOT, "assets", "ui", "hud", "buffs", f"{kind}.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        pygame.image.save(icon, out)
        print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
