"""Driving the title screen and the hero select headless: a booted `Game` on
the menu, key and mouse events, and a text-pixel count. Shared by
`test_menu.py` and `test_character_select.py`, which were one module until
TST-004.5 split them by subject.
"""
import os
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.game import Game
from game.states.menu_state import MenuState


def menu():
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    game.running = True
    return game, game.state_machine.current


def key(game, k):
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


def mouse(game, event_type, pos, button=1):
    kw = {"pos": pos}
    if event_type == pygame.MOUSEMOTION:
        kw.update(rel=(0, 0), buttons=(0, 0, 0))
    else:
        kw["button"] = button
    game.state_machine.handle_event(pygame.event.Event(event_type, **kw))


def bright_pixels(surface, rect):
    """Count non-background (text) pixels in `rect`, sampling every 3px."""
    n = 0
    for x in range(rect.left, rect.right, 3):
        for y in range(rect.top, rect.bottom, 3):
            r, g, b = surface.get_at((x, y))[:3]
            if r + g + b > 240:
                n += 1
    return n
