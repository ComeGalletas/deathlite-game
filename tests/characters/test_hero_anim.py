"""Six-weapon system P5 (design §20): the hero's attack sheets alternate
(attack 1, attack 2, attack 1 ...) and Aegis plays the guard sheet while
Bulwark is up."""
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.player import Player
from game.content import get_content
from game.states.playing.state import PlayingState


def fake_state(anims=("idle", "walk", "attack", "attack2", "guard"), **player_over):
    player = SimpleNamespace(alive=True, _hurt_t=0.0, _attack_t=0.0, _attack_cycle=0,
                             _move_dir=pygame.Vector2(), bulwark_active=False)
    for k, v in player_over.items():
        setattr(player, k, v)
    assets = SimpleNamespace(frame_count=lambda rig, name: 4 if name in anims else 0)
    fake = SimpleNamespace(player=player, _hero_has_hurt=False,
                           _hero_anim=SimpleNamespace(rig="hero_aegis"),
                           game=SimpleNamespace(assets=assets))
    fake._hero_has_anim = lambda name: PlayingState._hero_has_anim(fake, name)
    return fake


def name(fake):
    return PlayingState._hero_anim_name(fake)


class AttackCycleTests(unittest.TestCase):
    def test_odd_swings_play_attack_and_even_ones_attack2(self):
        self.assertEqual(name(fake_state(_attack_t=0.3, _attack_cycle=0)), "attack")
        self.assertEqual(name(fake_state(_attack_t=0.3, _attack_cycle=1)), "attack")   # 1st swing
        self.assertEqual(name(fake_state(_attack_t=0.3, _attack_cycle=2)), "attack2")  # 2nd
        self.assertEqual(name(fake_state(_attack_t=0.3, _attack_cycle=3)), "attack")   # 3rd
        self.assertEqual(name(fake_state(_attack_t=0.3, _attack_cycle=4)), "attack2")

    def test_a_rig_without_a_second_sheet_keeps_attack(self):
        f = fake_state(anims=("idle", "walk", "attack"), _attack_t=0.3, _attack_cycle=2)
        self.assertEqual(name(f), "attack")

    def test_the_cycle_advances_once_per_fresh_attack(self):
        p = Player(0, 0)
        self.assertEqual(p._attack_cycle, 0)
        p.trigger_attack_anim()                  # a fresh attack
        self.assertEqual(p._attack_cycle, 1)
        p.trigger_attack_anim()                  # re-triggered mid-swing: same attack
        self.assertEqual(p._attack_cycle, 1)
        p._attack_t = 0.0                        # the swing played out
        p.trigger_attack_anim()
        self.assertEqual(p._attack_cycle, 2)


class GuardTests(unittest.TestCase):
    def test_guard_while_still_with_bulwark_up(self):
        self.assertEqual(name(fake_state(bulwark_active=True)), "guard")

    def test_walking_or_attacking_beats_the_guard(self):
        self.assertEqual(name(fake_state(bulwark_active=True,
                                         _move_dir=pygame.Vector2(1, 0))), "walk")
        self.assertEqual(name(fake_state(bulwark_active=True, _attack_t=0.2)), "attack")

    def test_no_guard_without_bulwark_or_without_the_sheet(self):
        self.assertEqual(name(fake_state()), "idle")
        f = fake_state(anims=("idle", "walk", "attack"), bulwark_active=True)
        self.assertEqual(name(f), "idle")

    def test_hurt_and_death_still_win(self):
        self.assertEqual(name(fake_state(alive=False, bulwark_active=True)), "death")
        f = fake_state(bulwark_active=True, _hurt_t=0.2)
        f._hero_has_hurt = True
        self.assertEqual(name(f), "hurt")


class RigDataTests(unittest.TestCase):
    def test_aegis_has_both_attack_sheets_and_the_guard(self):
        anims = get_content().sprites["hero_aegis"]["anims"]
        self.assertEqual(anims["attack2"]["frames"], 4)
        self.assertFalse(anims["attack2"]["loop"])
        self.assertEqual(anims["guard"]["frames"], 6)
        self.assertTrue(anims["guard"]["loop"])

    def test_the_sheets_exist_and_match_their_frame_counts(self):
        rig = get_content().sprites["hero_aegis"]
        fw = rig["frame"][0]
        root = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
        for key in ("attack", "attack2", "guard"):
            a = rig["anims"][key]
            path = os.path.join(root, a["file"])
            self.assertTrue(os.path.exists(path), path)
            w = pygame.image.load(path).get_width()
            self.assertEqual(w // fw, a["frames"], key)


if __name__ == "__main__":
    unittest.main()
