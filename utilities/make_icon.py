"""Build the application icon from Aegis's idle sheet.

Writes two files, both from the same crop so the window and the executable show
the same picture:

    assets/ui/icon.ico   multi-size, for the packaged exe (desktop/*.spec)
    assets/ui/icon.png   96x96 native, for `pygame.display.set_icon`

Run it from the repo root with either interpreter -- it needs pygame and the
standard library, no numpy:

    .venv\\Scripts\\python.exe utilities/make_icon.py

**The crop is tight on the ink, not the whole frame.** Aegis is `hero_aegis` ->
`characters/blue/warrior/idle.png`, a 1536x192 strip of eight 192 px frames, and
the warrior occupies only 79x89 of frame 0 -- the rest is transparent margin the
pack ships for animation headroom. Cropping the full frame (or the rig's 120x112
`content` box) spends most of a 16 px icon on nothing, and the figure dissolves
into disconnected blocks. Squaring up on the ink instead keeps the plume, the
shield cross and the sword readable all the way down. Measured side by side
before choosing; the difference at 16 and 32 px is not subtle.

Every size is `pygame.transform.scale` -- nearest neighbour. `smoothscale` was
tried and is worse at every size here: it blurs pixel art, and at 16 px it turns
the knight into a smudge. The 2.67x upscale to 256 leaves some pixel blocks a
column wider than others, which is invisible at that size and a far better trade
than an illegible taskbar icon.
"""
import os
import struct
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

SRC = "assets/characters/blue/warrior/idle.png"
ICO_OUT = "assets/ui/icon.ico"
PNG_OUT = "assets/ui/icon.png"

FRAME_PX = 192          # the sheet's cell; 1536 wide == 8 frames
FRAME = 0               # the most upright idle pose (the idle is a subtle bob)
SNAP = 8                # square the ink up to a multiple of this

# Windows asks for these; 256 is the modern large icon, 16 the one you actually
# stare at in the taskbar and title bar.
SIZES = (256, 128, 64, 48, 32, 16)


def _crop_box(frame: pygame.Surface) -> pygame.Rect:
    """A square box centred on the frame's ink, snapped up to a `SNAP` multiple.

    For frame 0 of the current sheet the ink is (62, 48) 79x89, so the centre is
    (101, 92), `max(79, 89)` snaps 89 -> 96, and the box is (53, 44) 96x96.
    Derived rather than hard-coded so a repacked sheet still lands on the
    figure instead of silently cropping its head off.
    """
    ink = frame.get_bounding_rect()
    if not ink.width or not ink.height:
        raise SystemExit(f"{SRC} frame {FRAME} is empty")
    side = -(-max(ink.width, ink.height) // SNAP) * SNAP
    box = pygame.Rect(0, 0, side, side)
    box.center = ink.center
    box.clamp_ip(frame.get_rect())          # stay inside the frame if off-centre
    return box


def _png_bytes(surf: pygame.Surface) -> bytes:
    import io
    buf = io.BytesIO()
    pygame.image.save(surf, buf, "icon.png")
    return buf.getvalue()


def _ico(images: list[tuple[int, bytes]]) -> bytes:
    """Pack (size, PNG bytes) pairs into an .ico container.

    PNG-compressed entries rather than the older BMP+mask form: every Windows
    since Vista reads them, they are a quarter of the size, and they keep the
    alpha channel without a separate 1-bit mask. The format is a 6-byte
    ICONDIR, then one 16-byte ICONDIRENTRY per image, then the blobs; a
    dimension of 0 in an entry means 256.
    """
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
                               len(data), offset)
        offset += len(data)
        blobs += data
    return head + entries + blobs


def main() -> int:
    if not os.path.exists(SRC):
        print(f"missing source sheet: {SRC}", file=sys.stderr)
        return 1

    pygame.init()
    pygame.display.set_mode((32, 32))       # decoding alpha needs a display

    sheet = pygame.image.load(SRC).convert_alpha()
    frame = sheet.subsurface(pygame.Rect(FRAME * FRAME_PX, 0,
                                         FRAME_PX, FRAME_PX))
    box = _crop_box(frame)
    crop = frame.subsurface(box).copy()
    print(f"{SRC} frame {FRAME}: ink {frame.get_bounding_rect()} "
          f"-> crop {box.width}x{box.height} at ({box.x}, {box.y})")

    os.makedirs(os.path.dirname(ICO_OUT), exist_ok=True)

    # Native size, unresampled -- the window icon has no reason to be scaled.
    pygame.image.save(crop, PNG_OUT)

    images = [(n, _png_bytes(pygame.transform.scale(crop, (n, n))))
              for n in SIZES]
    with open(ICO_OUT, "wb") as fh:
        fh.write(_ico(images))

    print(f"{PNG_OUT}  {box.width}x{box.height}  "
          f"{os.path.getsize(PNG_OUT):,} bytes")
    print(f"{ICO_OUT}  {'/'.join(str(n) for n in SIZES)}  "
          f"{os.path.getsize(ICO_OUT):,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
