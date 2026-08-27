"""Entry point. Run with:  python main.py

Kept intentionally thin -- all it does is configure logging and hand control to
game.game.Game (spec rule 1.2: no giant main.py).
"""
from __future__ import annotations

import logging

from game.game import Game


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    Game().run()


if __name__ == "__main__":
    main()
