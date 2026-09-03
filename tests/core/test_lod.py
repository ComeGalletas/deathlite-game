"""The tick LOD (spawn master S7): an enemy that is neither chasing nor on
screen updates every `config.ENEMY_LOD_SKIP` frames with a `dt` spanning
the gap; anything the player can see or is fighting updates every frame."""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from entities.ai.components.aggro import _slot
from entities.enemy import Enemy
from game import config
from game.game import Game
from game.states.loading_state import LoadingState
from tests.boot import settle


def _run():
    game = Game()
    game.state_machine.change(LoadingState(game), seed=35, dev=True)
    ps = settle(game)
    ps.player.invulnerable = True
    ps._dev_no_attack = True
    ps.spawn.master.frozen = True
    return ps


def _far_spot(ps):
    """A floor spot on the start island well outside the padded view."""
    lay = ps.game_map.layout
    view = ps.camera.visible_rect().inflate(2 * config.ENEMY_LOD_VIEW_PAD + 200,
                                            2 * config.ENEMY_LOD_VIEW_PAD + 200)
    for p in lay.spawn_points:
        if p.room_id == lay.start_id and not view.collidepoint(p.x, p.y):
            return pygame.Vector2(p.x, p.y)
    raise AssertionError("no far point")


class TickLodTests(unittest.TestCase):
    def _count(self, ps, frames: int = 40) -> dict:
        counts: dict = {}
        dts: dict = {}
        real = Enemy.update

        def counting(self_, ctx):
            counts[id(self_)] = counts.get(id(self_), 0) + 1
            dts.setdefault(id(self_), set()).add(round(ctx.dt, 6))
            return real(self_, ctx)

        with mock.patch.object(Enemy, "update", counting):
            for _ in range(frames):
                ps.update(1 / 60)
        return counts, dts

    def test_far_idle_enemies_tick_every_other_frame_with_a_doubled_dt(self):
        ps = _run()
        far = ps.spawn.spawn_enemy("chaser", at=_far_spot(ps))
        near = ps.spawn.spawn_enemy("chaser", at=ps.player.pos + pygame.Vector2(200, 0))
        with mock.patch.object(config, "ENEMY_LOD_SKIP", 2):
            counts, dts = self._count(ps, 40)
        self.assertEqual(counts[id(near)], 40)
        self.assertEqual(counts[id(far)], 20)
        self.assertEqual(dts[id(near)], {round(1 / 60, 6)})
        self.assertEqual(dts[id(far)], {round(2 / 60, 6)})

    def test_a_chasing_enemy_far_away_still_ticks_every_frame(self):
        ps = _run()
        far = ps.spawn.spawn_enemy("chaser", at=_far_spot(ps))
        _slot(far)["until"] = ps.stats["time"] + 1000.0        # aggro timer running
        with mock.patch.object(config, "ENEMY_LOD_SKIP", 2):
            counts, _ = self._count(ps, 40)
        self.assertEqual(counts[id(far)], 40)

    def test_lod_one_ticks_everyone_every_frame(self):
        ps = _run()
        far = ps.spawn.spawn_enemy("chaser", at=_far_spot(ps))
        with mock.patch.object(config, "ENEMY_LOD_SKIP", 1):
            counts, dts = self._count(ps, 30)
        self.assertEqual(counts[id(far)], 30)
        self.assertEqual(dts[id(far)], {round(1 / 60, 6)})

    def test_eligibility_is_the_padded_view_and_pursuit(self):
        ps = _run()
        e = ps.spawn.spawn_enemy("chaser", at=_far_spot(ps))
        view = ps.camera.visible_rect().inflate(config.ENEMY_LOD_VIEW_PAD,
                                                config.ENEMY_LOD_VIEW_PAD)
        self.assertTrue(ps.spawn.lod_eligible(e, view))
        huge = ps.camera.visible_rect().inflate(20000, 20000)
        self.assertFalse(ps.spawn.lod_eligible(e, huge))
        _slot(e)["until"] = ps.stats["time"] + 5.0
        self.assertFalse(ps.spawn.lod_eligible(e, view))


if __name__ == "__main__":
    unittest.main()
