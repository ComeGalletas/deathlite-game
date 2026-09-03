"""CB-1: incoming contact / hazard damage lands as timed "bites", so flat armor
subtracts a meaningful chunk per hit instead of nullifying a per-frame sliver
(journals/BUG_JOURNAL.md #1).

  bite (pre-armor) = rate * interval          # rate = contact_damage or dps
  dealt            = max(0, bite * bulwark - armor)   # once per `interval`
"""
import os
import tempfile
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.hazard import Hazard
from entities.player import Player
from game import config
from game.game import Game
from game.states.menu_state import MenuState
from game.states.playing_state import PlayingState

DT = 1.0 / 120.0
T = config.INCOMING_TICK_INTERVAL          # 0.5 by default


def _key(game, k):
    game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k))


_STUB_DIRECTOR = None


def _run(hero_index=0):
    game = Game(save_path=os.path.join(tempfile.mkdtemp(), "save.json"))
    game.state_machine.change(MenuState(game))
    _key(game, pygame.K_RETURN)               # -> character select
    for _ in range(hero_index):
        _key(game, pygame.K_RIGHT)
    _key(game, pygame.K_RETURN)               # -> playing
    from tests.boot import settle
    p = settle(game)                  # through the loading screen
    assert isinstance(p, PlayingState)
    p.player.weapons = []                     # silence the hero's own attacks
    p.player.invulnerable = False
    p.player.trait = "none"                   # drop Bulwark / Windborne hooks
    p.director = types.SimpleNamespace(       # freeze the spawn director
        should_spawn_boss=lambda e: False,
        update=lambda dt, e, n: [],
        stat_multipliers=lambda t: (1.0, 1.0),
        enemy_count_cap=lambda t: config.ENEMY_COUNT_HARD_CAP,
        mark_boss_spawned=lambda: None)
    return game, p


def _advance(game, seconds):
    for _ in range(int(seconds / DT) + 1):
        game.state_machine.update(DT)


# --------------------------------------------------------------------------
class HazardDueDamageTests(unittest.TestCase):
    def test_default_interval_comes_from_config(self):
        h = Hazard(0, 0, 100, 20, 10)
        self.assertEqual(h.tick_interval, config.INCOMING_TICK_INTERVAL)

    def test_accumulates_then_pays_one_bite_per_interval(self):
        h = Hazard(0, 0, 100, dps=20, duration=10)     # bite = 20 * 0.5 = 10
        for _ in range(4):
            self.assertEqual(h.due_damage(0.1), 0.0)   # 0.4 s piled up, nothing due
        self.assertEqual(h.due_damage(0.1), 10.0)      # crosses 0.5 s
        self.assertEqual(h.due_damage(0.1), 0.0)

    def test_custom_interval_bites_sooner_and_smaller(self):
        h = Hazard(0, 0, 100, dps=20, duration=10, tick_interval=0.25)
        self.assertEqual(h.due_damage(0.2), 0.0)
        self.assertEqual(h.due_damage(0.1), 5.0)       # 20 * 0.25

    def test_a_big_frame_flushes_every_whole_interval(self):
        h = Hazard(0, 0, 100, dps=20, duration=10, tick_interval=0.1)
        self.assertAlmostEqual(h.due_damage(0.35), 3 * (20 * 0.1))   # 3 whole ticks

    def test_reset_ticks_clears_partial_exposure(self):
        h = Hazard(0, 0, 100, 20, 10)
        h.due_damage(0.4)
        h.reset_ticks()
        self.assertEqual(h.due_damage(0.2), 0.0)       # would have been due without reset


# --------------------------------------------------------------------------
class PlayerTakeDamageUnchangedTests(unittest.TestCase):
    def test_flat_armor_still_subtracts_from_a_single_hit(self):
        p = Player(0, 0)
        p.stats["armor"] = 3.0
        self.assertEqual(p.take_damage(10.0), 7.0)


# --------------------------------------------------------------------------
class ContactBiteTests(unittest.TestCase):
    def test_armored_hero_now_takes_contact_damage(self):
        """Regression for BUG_JOURNAL #1: Aegis (armor 4) was fully immune."""
        game, p = _run(hero_index=0)                    # Aegis, armor 4
        self.assertEqual(p.player.stats["armor"], 4.0)
        p._spawn_enemy("swarm", at=p.player.pos.copy())  # contact_damage 9
        hp0 = p.player.hp
        game.state_machine.update(DT)                   # one frame -> one bite
        bite = 9 * T - 4                                # 9*0.5 - armor = 0.5
        self.assertAlmostEqual(hp0 - p.player.hp, bite, places=3)
        self.assertGreater(hp0 - p.player.hp, 0.0)

    def test_at_most_one_bite_per_interval_then_another(self):
        game, p = _run(hero_index=1)                    # Kestrel, armor 0
        p._spawn_enemy("swarm", at=p.player.pos.copy())
        hp0 = p.player.hp
        _advance(game, T * 0.6)                         # < one interval past the first
        one_bite = hp0 - p.player.hp
        self.assertAlmostEqual(one_bite, 9 * T, places=2)   # exactly one bite (armor 0)
        _advance(game, T)                              # cross the next boundary
        self.assertAlmostEqual(hp0 - p.player.hp, 2 * (9 * T), places=1)

    def test_two_enemies_bite_on_independent_timers(self):
        game, p = _run(hero_index=1)                    # armor 0
        p._spawn_enemy("swarm", at=p.player.pos.copy())
        p._spawn_enemy("swarm", at=p.player.pos.copy())
        hp0 = p.player.hp
        game.state_machine.update(DT)                   # both bite once this frame
        self.assertAlmostEqual(hp0 - p.player.hp, 2 * (9 * T), places=3)

    def test_entering_the_attack_state_clears_the_contact_cooldown(self):
        """A charge / blink is a discrete impact -- it must land on first overlap
        even if the enemy bit the hero moments earlier."""
        game, p = _run(hero_index=1)
        p._spawn_enemy("charger", at=p.player.pos.copy())
        charger = p.enemies[-1]

        def state():
            return charger.bb.slot("__machine__").get("state")

        for _ in range(900):                           # run up to the wind-up
            charger.update(p._enemy_context(DT))
            if charger.telegraphing:
                break
        self.assertTrue(charger.telegraphing)
        charger.contact_cd = 5.0                        # would normally block a bite
        for _ in range(180):                            # ... through to the dash
            charger.update(p._enemy_context(DT))
            if state() == "attack":
                break
        self.assertEqual(state(), "attack")
        self.assertEqual(charger.contact_cd, 0.0)       # cleared on attack entry


# --------------------------------------------------------------------------
class HazardBiteTests(unittest.TestCase):
    def test_total_over_a_pool_life_is_dps_times_duration(self):
        game, p = _run(hero_index=1)                    # armor 0, no trait
        p.player.hp = 1000.0
        p._spawn_hazard(p.player.pos.copy(), 120, 23, 3.5)   # dps 23, 3.5 s
        hp0 = p.player.hp
        _advance(game, 3.6)
        # bites at 0.5,1.0,...,3.5 -> 7 * (23*0.5) = 80.5
        self.assertAlmostEqual(hp0 - p.player.hp, 7 * (23 * T), delta=23 * T)

    def test_same_total_faster_hazard(self):
        # (dps 23, dur 3.5, tick 0.5) vs (dps 46, dur 1.75, tick 0.25):
        # identical bite size, identical bite count, delivered in half the time.
        def total(dps, dur, tick):
            game, p = _run(hero_index=1)
            p.player.hp = 1000.0
            p._spawn_hazard(p.player.pos.copy(), 120, dps, dur, tick_interval=tick)
            hp0 = p.player.hp
            _advance(game, dur + 0.2)
            return hp0 - p.player.hp
        a = total(23, 3.5, 0.5)
        b = total(46, 1.75, 0.25)
        self.assertAlmostEqual(a, b, delta=12.0)

    def test_spawn_hazard_forwards_the_tick_interval(self):
        game, p = _run()
        p._spawn_hazard(p.player.pos.copy(), 90, 20, 3.0, tick_interval=0.25)
        self.assertEqual(p.hazards[-1].tick_interval, 0.25)
        p._spawn_hazard(p.player.pos.copy(), 90, 20, 3.0)
        self.assertEqual(p.hazards[-1].tick_interval, config.INCOMING_TICK_INTERVAL)

    def test_stepping_out_does_not_bank_partial_exposure(self):
        game, p = _run(hero_index=1)
        p.player.hp = 1000.0
        hz = Hazard(p.player.pos.x + 5000, p.player.pos.y, 120, 40, 10)  # far away
        p.hazards.append(hz)
        hp0 = p.player.hp
        _advance(game, 2.0)                             # never inside it
        self.assertEqual(hp0, p.player.hp)
        self.assertEqual(hz._tick_accum, 0.0)


if __name__ == "__main__":
    unittest.main()
