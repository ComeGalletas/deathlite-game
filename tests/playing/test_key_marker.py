"""The interact keycap over the element it fires (journal:
key_icons_journal.md, pass 2): one cap at most, over the closest usable
chest or special location within reach; the E key fires that same element;
the cap sits above the element's art and shows the pressed frame while the
key is held. Seed 1234 is pinned (it has a shrine)."""
import os
import tempfile
import unittest
from unittest import mock

import pygame

from entities.chest import Chest
from entities.interactable import Interactable
from game import config
from game.content import get_content
from game.game import Game
from game.states.playing.core import interactions
from game.states.playing.core.state import PlayingState
from game.states.playing.visual import key_marker
from progression import chests as chest_rules
from ui import keycap

T = get_content().chests


def _run(seed=1234, *, keep=False):
    """A pinned run with the world's chests and locations cleared, so each
    test seats its own; `keep=True` leaves the generated ones in place."""
    g = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
    p = PlayingState(g)
    p.enter(seed=seed)
    if not keep:
        p.chests = []
        p.interactables = []
    return g, p


def _chest(ps, dx=0.0, dy=0.0, rarity="common"):
    c = Chest(ps.player.pos.x + dx, ps.player.pos.y + dy, rarity,
              radius=chest_rules.radius(T))
    ps.chests.append(c)
    return c


def _shrine(ps, dx=0.0, dy=0.0, kind="shrine"):
    it = Interactable(kind, ps.player.pos.x + dx, ps.player.pos.y + dy)
    ps.interactables.append(it)
    return it


class NearestTests(unittest.TestCase):
    def test_nothing_in_reach_is_none(self):
        _g, p = _run()
        _chest(p, dx=400)
        _shrine(p, dx=-400)
        self.assertIsNone(interactions.nearest(p))

    def test_the_closer_element_wins_whichever_list_it_is_in(self):
        _g, p = _run()
        shrine = _shrine(p, dx=30)
        chest = _chest(p, dx=10)
        self.assertIs(interactions.nearest(p), chest)
        chest.pos.x += 40                       # now the shrine is closer
        self.assertIs(interactions.nearest(p), shrine)

    def test_used_and_opened_elements_are_skipped(self):
        _g, p = _run()
        chest = _chest(p, dx=10)
        shrine = _shrine(p, dx=30)
        chest.opened = True
        self.assertIs(interactions.nearest(p), shrine)
        shrine.used = True
        self.assertIsNone(interactions.nearest(p))

    def test_a_tie_goes_to_the_location(self):
        _g, p = _run()
        chest = _chest(p, dx=20)
        shrine = _shrine(p, dx=-20)
        self.assertIs(interactions.nearest(p), shrine)
        self.assertFalse(chest.opened)

    def test_the_key_fires_the_marked_element(self):
        _g, p = _run()
        chest = _chest(p, dx=10)
        shrine = _shrine(p, dx=30)
        self.assertIs(interactions.nearest(p), chest)
        p.handle_event(pygame.event.Event(pygame.KEYDOWN, key=config.KEY_INTERACT))
        self.assertTrue(chest.opened)
        self.assertFalse(shrine.used)
        # The chest is spent; the shrine is the next closest.
        self.assertIs(interactions.nearest(p), shrine)
        p.handle_event(pygame.event.Event(pygame.KEYDOWN, key=config.KEY_INTERACT))
        self.assertTrue(shrine.used)

    def test_kind_of(self):
        _g, p = _run()
        self.assertEqual(interactions.kind_of(_chest(p)), "chest")
        self.assertEqual(interactions.kind_of(_shrine(p, kind="forge")), "forge")


class MarkerTests(unittest.TestCase):
    def setUp(self):
        self.g, self.p = _run()
        self.surface = pygame.Surface(self.g.screen.get_size(), pygame.SRCALPHA)

    def test_no_element_draws_no_cap(self):
        with mock.patch.object(keycap, "draw_keycap") as m:
            key_marker.draw(self.surface, self.p)
        m.assert_not_called()

    def test_one_cap_over_the_closest_element(self):
        p = self.p
        chest = _chest(p, dx=10)
        _shrine(p, dx=30)
        with mock.patch.object(keycap, "draw_keycap") as m:
            key_marker.draw(self.surface, p)
        self.assertEqual(m.call_count, 1)
        self.assertEqual(m.call_args[0][2], key_marker.anchor(p, chest))
        self.assertEqual(m.call_args[0][3], "E")
        self.assertEqual(m.call_args[1]["state"], "raised")

    def test_the_cap_sits_clear_above_the_chest_lid(self):
        """Pass 3: measured from the drawn chest, not a table -- the cap's
        bottom is `CLEAR_PX` above the closed chest's ink, centred on the
        lid's peak, for every tier."""
        p = self.p
        for rarity in ("common", "uncommon", "rare", "epic"):
            with self.subTest(rarity=rarity):
                p.chests = []
                chest = _chest(p, rarity=rarity)
                box, peak = key_marker.art_box(p, chest)
                ax, ay = key_marker.anchor(p, chest)
                self.assertEqual(ax, peak)
                self.assertEqual(ay + keycap.cap_rect((0, 0)).bottom,
                                 box.top - key_marker.CLEAR_PX)
                # The lid's peak is the chest's centre column, give or take a pixel.
                self.assertLessEqual(abs(peak - box.centerx), 1)

    def test_the_forge_cap_sits_over_the_chimney(self):
        """The forge's art is wider to the left (the bellows), so its peak --
        the chimney -- is right of the interactable's point."""
        g, full = _run(keep=True)
        forge = next(i for i in full.interactables if i.kind == "forge")
        full.player.pos.update(forge.pos)
        full.camera.snap_to(forge.pos)
        full.draw(g.screen)                  # the skins are baked on the first frame
        found = key_marker.art_box(full, forge)
        self.assertIsNotNone(found, "the forge skin was not baked")
        box, peak = found
        sx, sy = full.camera.world_to_screen(forge.pos)
        self.assertGreater(peak, sx + 5)
        self.assertLess(box.top, sy)
        ax, ay = key_marker.anchor(full, forge)
        self.assertEqual(ax, peak)
        self.assertEqual(ay + keycap.cap_rect((0, 0)).bottom, box.top - key_marker.CLEAR_PX)

    def test_a_ring_falls_back_to_the_kind_lift(self):
        p = self.p
        shrine = _shrine(p)
        self.assertIsNone(key_marker.art_box(p, shrine))
        sx, sy = p.camera.world_to_screen(shrine.pos)
        ax, ay = key_marker.anchor(p, shrine)
        self.assertEqual(ax, round(sx))
        lift = key_marker.KEY_LIFT["shrine"] * p.camera.zoom
        self.assertEqual(ay + keycap.cap_rect((0, 0)).bottom,
                         round(sy - lift - key_marker.CLEAR_PX))

    def test_the_cap_follows_the_element_not_the_hero(self):
        p = self.p
        chest = _chest(p, dx=20)
        a = key_marker.anchor(p, chest)
        p.player.pos.x -= 10                   # hero moves, chest does not
        self.assertEqual(key_marker.anchor(p, chest), a)

    def test_held_key_shows_the_pressed_frame(self):
        p = self.p
        _chest(p)
        with mock.patch.object(key_marker, "interact_held", return_value=True), \
             mock.patch.object(keycap, "draw_keycap") as m:
            key_marker.draw(self.surface, p)
        self.assertEqual(m.call_args[1]["state"], "pressed")

    def test_the_frame_paints_the_cap_and_no_bottom_prompt(self):
        """A whole frame through `PlayingState.draw` reaches the marker, and
        nothing is written where the old prompt sat."""
        p = self.p
        chest = _chest(p)
        with mock.patch.object(keycap, "draw_keycap", wraps=keycap.draw_keycap) as m:
            p.draw(self.surface)
        self.assertEqual(m.call_count, 1)
        self.assertEqual(m.call_args[0][2], key_marker.anchor(p, chest))


if __name__ == "__main__":
    unittest.main()
