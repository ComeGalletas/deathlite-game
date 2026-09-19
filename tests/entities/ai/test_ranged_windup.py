"""The telegraphed kiter: a shot the player can see coming, and the attack
art finally reaching the screen.

Owner, 2026-09-19. `kite_shoot` was a single `move` state -- `MaintainRange`
plus `FireProjectile` on a bare timer -- and that one fact had three
consequences worth pinning against regression:

* **the attack strip never played.** `Enemy._anim_name()` returns "attack"
  only while the machine sits in `telegraph`/`attack`, and a one-state
  behaviour never does, so the `shoot.png` / `throw.png` every kiter ships
  had not been drawn once since delivery;
* **the shot had no tell**, which matters much more now that the interval
  is 1.6x longer -- a rare unannounced shot is worse than a frequent one;
* **its reach was implicit**, `prefer_distance * 1.8`, so a weapon's range
  was a side effect of where the body liked to stand.

`attack_range` is now the reach, `shoot_interval` is the true shot-to-shot
gap rather than the cooldown, and the shot leaves on the wind-up's end
transition so the animation and the projectile are one event.
"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.ai import build_behavior
from entities.enemy import Enemy
from game.content import get_content

KITERS = ("slingshot_gnome", "bomb_fish", "gnoll", "harpoon_shark")


def _cfg(eid):
    return get_content().enemy(eid)


class ShapeTests(unittest.TestCase):
    def test_every_kiter_reaches_a_telegraph_and_an_attack_state(self):
        """The fix itself. Without these two states the attack strip is
        unreachable however good the art is."""
        for eid in KITERS:
            with self.subTest(enemy=eid):
                cfg = _cfg(eid)
                states = set(build_behavior(cfg["behavior"], cfg).states)
                self.assertIn("telegraph", states)
                self.assertIn("attack", states)

    def test_a_kiter_with_no_wind_up_keeps_the_old_single_state(self):
        """Opt-in: a kiter that declares no `attack_telegraph` is unmoved,
        so nothing outside the four shipped ones changed."""
        beh = build_behavior("kite_shoot", {"prefer_distance": 240,
                                            "shoot_interval": 2.0})
        self.assertEqual(set(beh.states), {"move"})

    def test_the_declared_gap_is_the_whole_cycle_not_the_cooldown(self):
        """`shoot_interval` is what a player could measure with a stopwatch
        (owner, 2026-09-19), so the wind-up, the strike and the recovery
        come out of it rather than being added on top."""
        for eid in KITERS:
            cfg = _cfg(eid)
            with self.subTest(enemy=eid):
                parts = (cfg["attack_telegraph"] + cfg["attack_active"]
                         + cfg["attack_recover"])
                self.assertLess(parts, cfg["shoot_interval"],
                                "the cycle does not fit inside the gap")

    def test_every_kiter_can_reach_from_where_it_chooses_to_stand(self):
        """`prefer_distance` must sit inside `attack_range` or the body
        kites to a spot it can never shoot from -- which is exactly what a
        300 px reach would have done to Gaffjaw at its 360 px stand-off."""
        for eid in KITERS:
            cfg = _cfg(eid)
            with self.subTest(enemy=eid):
                self.assertLessEqual(cfg["prefer_distance"], cfg["attack_range"])

    def test_the_reach_is_declared_rather_than_derived(self):
        for eid in KITERS:
            with self.subTest(enemy=eid):
                self.assertIn("attack_range", _cfg(eid))


class FiringTests(unittest.TestCase):
    """Driven through a real run, because the thing being checked is that
    the animation and the shot are the same event -- which only the live
    machine can show."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from game.game import Game
        from game.states.menu_state import MenuState
        from tests import worlds as W
        from tests.boot import start_run
        cls.game = Game(save_path=os.path.join(tempfile.mkdtemp(), "s.json"))
        cls.game.state_machine.change(MenuState(cls.game))
        cls.ps = start_run(cls.game, W.pinned(0))
        cls.ps.player.invulnerable = True
        cls.ps._dev_no_attack = True
        cls.ps.spawn.master.frozen = True

    def _watch(self, eid, distance, seconds=9.0):
        ps = self.ps
        ps.enemies.clear()
        spot = pygame.Vector2(ps.player.pos) + pygame.Vector2(distance, 0)
        e = ps.spawn.spawn_enemy(eid, at=spot, owner="dev")
        ps.fx.update_spawn_fx(1e9)
        anims = set()
        for _ in range(int(seconds * 60)):
            ps.update(1 / 60)
            if not getattr(e, "alive", True):
                break
            anims.add(e._anim_name())
        return e, anims

    def test_the_attack_strip_actually_plays(self):
        """The art had never been drawn. One assertion per kiter, through
        the run rather than through the builder."""
        for eid, d in (("slingshot_gnome", 250), ("bomb_fish", 200),
                       ("gnoll", 180), ("harpoon_shark", 350)):
            with self.subTest(enemy=eid):
                _e, anims = self._watch(eid, d)
                self.assertIn("attack", anims,
                              f"{eid} never played its attack strip")

    def test_a_body_out_of_reach_never_winds_up(self):
        """`attack_range` is the cycle's trigger, so a kiter the hero has
        noticed but cannot be shot by shows no tell at all."""
        cfg = _cfg("gnoll")
        far = cfg["attack_range"] + 400
        self.assertLess(far, cfg["aggro_range"], "it must still be aggroed")
        _e, anims = self._watch("gnoll", far, seconds=4.0)
        self.assertNotIn("attack", anims)


if __name__ == "__main__":
    unittest.main()
