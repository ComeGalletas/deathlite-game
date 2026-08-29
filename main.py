"""Entry point.

    python main.py            # desktop
    python main.py --web      # desktop, but with the browser profile applied
                              # (1280x720 / 60 fps / no save file) for testing

pygbag also runs this file -- its generated `index.html` always loads
`main.py` -- and the `sys.platform == "emscripten"` check below applies the same
browser profile automatically. The web packaging config and build/serve helpers
live in `web/` (see `web/README.md`).

Kept thin: configure logging, apply the browser profile when appropriate, hand
control to `game.game.Game`. The loop is `asyncio`-driven so one code path
serves both builds (`Game.run_async` yields to the host event loop once per
frame). `asyncio.run(...)` is called unguarded at module scope -- pygbag sources
this file with `__name__` set to the module name, not `"__main__"`, so an
`if __name__ == "__main__":` guard would never fire in the browser.
"""
from __future__ import annotations

import asyncio
import logging
import sys

import pygame  # noqa: F401  -- pygbag scans THIS file's imports to preload the
#                                pygame wasm; transitive imports are invisible
#                                to its loader.

from game import config
from game.game import Game


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if sys.platform == "emscripten" or "--web" in sys.argv:
        config.apply_web_profile()

    await Game().run_async()


asyncio.run(main())
