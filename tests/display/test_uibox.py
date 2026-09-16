"""`game/display/uibox.py` and the state machine's use of it (journal
"Dynamic window scaling", "Ultrawide render extent", 2026-09-15): on a
2100x900 render the interface draws in the centred 1600x900 box, mouse
events reach a box state in box coordinates, and the run keeps the whole
surface."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.display import fit, uibox
from game.state import State, StateMachine
from systems.camera import Camera

WIDE = (2100, 900)


class BoxGeometryTests(unittest.TestCase):
    def test_on_a_16_9_render_the_box_is_the_surface(self):
        s = pygame.Surface((config.UI_WIDTH, config.UI_HEIGHT))
        self.assertEqual(uibox.rect(s), s.get_rect())
        self.assertIs(uibox.box(s), s)
        self.assertEqual(uibox.offset(s), (0, 0))

    def test_on_a_21_9_render_the_box_is_the_centred_middle(self):
        s = pygame.Surface(WIDE)
        self.assertEqual(uibox.rect(s), pygame.Rect(250, 0, 1600, 900))
        b = uibox.box(s)
        self.assertEqual(b.get_size(), (1600, 900))
        self.assertEqual(b.get_offset(), (250, 0))
        self.assertEqual(uibox.offset(s), (250, 0))

    def test_a_surface_smaller_than_the_box_is_its_own_box(self):
        s = pygame.Surface((320, 180))
        self.assertIs(uibox.box(s), s)

    def test_drawing_on_the_box_lands_in_the_middle_of_the_surface(self):
        s = pygame.Surface(WIDE)
        s.fill((0, 0, 0))
        uibox.box(s).fill((255, 255, 255))
        self.assertEqual(s.get_at((249, 450))[:3], (0, 0, 0))
        self.assertEqual(s.get_at((250, 450))[:3], (255, 255, 255))
        self.assertEqual(s.get_at((1849, 450))[:3], (255, 255, 255))
        self.assertEqual(s.get_at((1850, 450))[:3], (0, 0, 0))


class EventTranslationTests(unittest.TestCase):
    def test_a_click_is_shifted_by_the_box_offset(self):
        s = pygame.Surface(WIDE)
        e = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(1050, 450), button=1)
        t = uibox.translate_event(e, s)
        self.assertEqual(t.pos, (800, 450))
        self.assertEqual(t.button, 1)
        self.assertEqual(t.type, pygame.MOUSEBUTTONDOWN)
        self.assertEqual(e.pos, (1050, 450))                 # the original is untouched

    def test_nothing_changes_on_a_16_9_render_or_without_a_position(self):
        s = pygame.Surface((1600, 900))
        e = pygame.event.Event(pygame.MOUSEMOTION, pos=(10, 10), rel=(1, 1), buttons=(0, 0, 0))
        self.assertIs(uibox.translate_event(e, s), e)
        k = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)
        self.assertIs(uibox.translate_event(k, pygame.Surface(WIDE)), k)


class _Recorder(State):
    ui_box = True

    def __init__(self, game=None):
        self.drawn = []
        self.backdrops = []
        self.events = []

    def draw_backdrop(self, surface):
        self.backdrops.append(surface.get_size())

    def draw(self, surface):
        self.drawn.append((surface.get_size(), surface.get_offset()))

    def handle_event(self, event):
        self.events.append(event)


class _World(_Recorder):
    ui_box = False


class StateMachineBoxTests(unittest.TestCase):
    def test_a_box_state_draws_on_the_box_and_a_world_state_on_the_surface(self):
        sm = StateMachine(game=None)
        world, overlay = _World(), _Recorder()
        overlay.draw_below = True
        sm.push(world)
        sm.push(overlay)
        sm.draw(pygame.Surface(WIDE))
        self.assertEqual(world.drawn, [(WIDE, (0, 0))])
        self.assertEqual(overlay.drawn, [((1600, 900), (250, 0))])
        # The backdrop hook always sees the whole surface.
        self.assertEqual(overlay.backdrops, [WIDE])
        self.assertEqual(world.backdrops, [WIDE])

    def test_events_reach_a_box_state_in_box_coordinates(self):
        pygame.display.init()
        pygame.display.set_mode(WIDE)
        try:
            sm = StateMachine(game=None)
            st = _Recorder()
            sm.push(st)
            sm.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(250, 0), button=1))
            self.assertEqual(st.events[-1].pos, (0, 0))
            world = _World()
            sm.push(world)
            sm.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(250, 0), button=1))
            self.assertEqual(world.events[-1].pos, (250, 0))
        finally:
            pygame.display.set_mode((config.UI_WIDTH, config.UI_HEIGHT))


class RenderWidthTests(unittest.TestCase):
    def test_the_camera_shows_more_world_at_the_same_zoom(self):
        wide = Camera(10000, 10000, 2100, 900, zoom=config.CAMERA_ZOOM)
        narrow = Camera(10000, 10000, 1600, 900, zoom=config.CAMERA_ZOOM)
        self.assertEqual(wide.world_span(), (1400.0, 600.0))
        self.assertEqual(narrow.world_span()[1], wide.world_span()[1])
        self.assertEqual(wide.zoom, narrow.zoom)

    def test_the_aspect_class(self):
        self.assertEqual(fit.aspect_class((1920, 1080)), "16:9")
        self.assertEqual(fit.aspect_class((1920, 1200)), "16:9")      # 16:10 -> bars
        self.assertEqual(fit.aspect_class((1400, 1000)), "16:9")
        self.assertEqual(fit.aspect_class((2560, 1080)), "21:9")
        self.assertEqual(fit.aspect_class((3440, 1440)), "21:9")
        self.assertEqual(fit.aspect_class((5120, 1440)), "21:9")      # 32:9 -> pillars
        self.assertEqual(fit.aspect_class((100, 0)), "16:9")

    def test_the_render_widths_are_the_two_the_ui_box_expects(self):
        self.assertEqual(config.RENDER_WIDTHS["16:9"], config.UI_WIDTH)
        self.assertGreater(config.RENDER_WIDTHS["21:9"], config.UI_WIDTH)
        self.assertEqual(config.SCREEN_HEIGHT, config.UI_HEIGHT)


if __name__ == "__main__":
    unittest.main()
