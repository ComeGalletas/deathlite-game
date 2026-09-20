"""`game/states/end_banner_state.py`: the animated card between the run and
its summary (journal: `documentation/journals/end_banner_journal.md`).

What is pinned: the clock. The owner specified the intermission in seconds
-- 3 s with the world still moving, the sprite once through, 2 s on its
last frame, then the summary -- so the hand-off instant is asserted to the
frame for both outcomes, and so is what the run underneath is allowed to do
in each phase. The sprite itself is a stub here (frame count and fps only);
the real sheets are checked once at the end against the rigs and the cut.

A fake game, as in `test_game_over.py`: the state needs assets that answer
the `Animator`'s four questions, and somewhere to be pushed.
"""
import os
import subprocess
import sys
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import config
from game.state import State, StateMachine
from game.states.end_banner_state import (BANNER, DONE, HOLD, WAIT, EndBannerState)

DT = 1 / 60
CUTTER = os.path.join("tools", "asset_pipeline", "cut_end_banners.py")


def _display():
    pygame.display.init()
    pygame.display.set_mode((64, 64))


class _Assets:
    """The four answers `Animator` needs, plus `rig()` / `frame()` for draw."""

    def __init__(self, frames: int, fps: float = 15.0, size=(416, 128)):
        self.frames_ = frames
        self.fps_ = fps
        self.size = size
        self.asked = []                 # (index, size) of every frame drawn

    def rig(self, name):
        return {"frame": list(self.size)}

    def frame_count(self, rig, anim):
        return self.frames_

    def fps(self, rig, anim):
        return self.fps_

    def loops(self, rig, anim):
        return False

    def frame(self, rig, anim, index, *, size=None, flip=False, tint=None):
        self.asked.append((index, size))
        return pygame.Surface(size or self.size, pygame.SRCALPHA)


class _Counter(State):
    """Stands in for the run: counts the updates it is allowed."""

    def __init__(self, game):
        super().__init__(game)
        self.updates = 0

    def update(self, dt):
        self.updates += 1


def _game(frames=44):
    game = SimpleNamespace(assets=_Assets(frames))
    game.state_machine = StateMachine(game)
    return game


def _banner(game, victory=False):
    done = []
    below = _Counter(game)
    game.state_machine.push(below)
    st = EndBannerState(game)
    game.state_machine.push(st, victory=victory, on_done=lambda: done.append(1))
    return st, below, done


def _run_until_done(game, st, done, limit_s=20.0):
    """Drive the machine until `on_done` fires; the elapsed seconds at that
    frame, or None."""
    n = 0
    while not done and n * DT < limit_s:
        game.state_machine.update(DT)
        n += 1
    return st.elapsed if done else None


class ClockTests(unittest.TestCase):
    def test_a_loss_hands_off_at_wait_plus_one_play_plus_hold(self):
        game = _game(frames=44)                 # GAME OVER: 44 frames at 15 fps
        st, _below, done = _banner(game, victory=False)
        expect = config.END_BANNER_WAIT + 44 / 15 + config.END_BANNER_HOLD   # 7.93 s
        at = _run_until_done(game, st, done)
        self.assertIsNotNone(at, "the banner never handed off")
        self.assertGreaterEqual(at, expect - 1e-6)
        self.assertLess(at, expect + DT + 1e-6)      # the very next frame at the latest
        self.assertEqual(st.phase, DONE)

    def test_a_win_hands_off_on_its_own_frame_count(self):
        game = _game(frames=42)                 # You Won!: 42 frames at 15 fps
        st, _below, done = _banner(game, victory=True)
        expect = config.END_BANNER_WAIT + 42 / 15 + config.END_BANNER_HOLD   # 7.80 s
        at = _run_until_done(game, st, done)
        self.assertGreaterEqual(at, expect - 1e-6)
        self.assertLess(at, expect + DT + 1e-6)

    def test_nothing_happens_a_frame_early(self):
        game = _game(frames=44)
        st, _below, done = _banner(game)
        expect = config.END_BANNER_WAIT + 44 / 15 + config.END_BANNER_HOLD
        while st.elapsed + DT < expect - DT:
            game.state_machine.update(DT)
        self.assertEqual(done, [])
        self.assertEqual(st.phase, HOLD)

    def test_the_phases_come_in_order(self):
        game = _game(frames=44)
        st, _below, _done = _banner(game)
        seen = [st.phase]
        for _ in range(int(9 / DT)):
            game.state_machine.update(DT)
            if st.phase != seen[-1]:
                seen.append(st.phase)
        self.assertEqual(seen, [WAIT, BANNER, HOLD, DONE])

    def test_hand_off_fires_once(self):
        game = _game(frames=44)
        st, _below, done = _banner(game)
        for _ in range(int(12 / DT)):
            game.state_machine.update(DT)
        self.assertEqual(done, [1])

    def test_without_art_the_banner_phase_is_skipped_and_the_waits_remain(self):
        """No assets at all (a stub game, an empty assets/): the words are
        drawn instead, and the clock is the two waits."""
        game = SimpleNamespace()
        game.state_machine = StateMachine(game)
        st, _below, done = _banner(game)
        at = _run_until_done(game, st, done)
        expect = config.END_BANNER_WAIT + config.END_BANNER_HOLD
        self.assertGreaterEqual(at, expect - 1e-6)
        self.assertLess(at, expect + DT + 1e-6)


class WorldUnderneathTests(unittest.TestCase):
    def test_the_run_keeps_updating_through_the_wait_and_freezes_under_the_banner(self):
        game = _game(frames=44)
        st, below, _done = _banner(game)
        frames_in_wait = int(config.END_BANNER_WAIT / DT) - 2      # just short of it
        for _ in range(frames_in_wait):
            game.state_machine.update(DT)
        self.assertEqual(st.phase, WAIT)
        self.assertEqual(below.updates, frames_in_wait)     # every frame reached the run
        while st.phase == WAIT:
            game.state_machine.update(DT)
        frozen_at = below.updates
        for _ in range(int(6 / DT)):
            game.state_machine.update(DT)
        self.assertEqual(below.updates, frozen_at)          # not one more

    def test_input_is_swallowed(self):
        game = _game(frames=44)
        st, below, done = _banner(game)
        for _ in range(30):
            game.state_machine.update(DT)
        for key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
            game.state_machine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
        game.state_machine.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10)))
        self.assertEqual(st.phase, WAIT)
        self.assertEqual(done, [])
        self.assertIs(game.state_machine.current, st)

    def test_the_banner_is_an_overlay_that_fades_the_music(self):
        self.assertTrue(EndBannerState.draw_below)
        self.assertIsNone(EndBannerState.music)


class DrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _display()
        pygame.font.init()

    def test_nothing_is_drawn_over_the_scene_while_waiting(self):
        game = _game(frames=44)
        st, _below, _done = _banner(game)
        game.state_machine.update(DT)
        surface = pygame.Surface((1600, 900), pygame.SRCALPHA)
        st.draw_backdrop(surface)
        st.draw(surface)
        self.assertEqual(pygame.image.tobytes(surface, "RGBA"), bytes(1600 * 900 * 4))
        self.assertEqual(game.assets.asked, [])

    def test_the_sprite_is_drawn_at_the_integer_scale_while_the_banner_plays(self):
        game = _game(frames=44)
        st, _below, _done = _banner(game)
        while st.phase != BANNER:
            game.state_machine.update(DT)
        for _ in range(20):
            game.state_machine.update(DT)
        surface = pygame.Surface((1600, 900), pygame.SRCALPHA)
        st.draw_backdrop(surface)
        st.draw(surface)
        self.assertEqual(len(game.assets.asked), 1)
        index, size = game.assets.asked[0]
        self.assertEqual(size, (416 * config.END_BANNER_SCALE, 128 * config.END_BANNER_SCALE))
        self.assertGreater(index, 0)
        # The dim layer is on: the surface is no longer clear.
        self.assertNotEqual(pygame.image.tobytes(surface, "RGBA"), bytes(1600 * 900 * 4))

    def test_the_hold_keeps_the_dim_and_drops_the_sprite(self):
        game = _game(frames=44)
        st, _below, _done = _banner(game)
        while st.phase != HOLD:
            game.state_machine.update(DT)
        game.assets.asked.clear()
        surface = pygame.Surface((1600, 900), pygame.SRCALPHA)
        st.draw_backdrop(surface)
        st.draw(surface)
        self.assertEqual(game.assets.asked, [])
        self.assertEqual(surface.get_at((0, 0))[3], config.END_BANNER_DIM_ALPHA)

    def test_without_art_the_words_are_drawn(self):
        game = SimpleNamespace()
        game.state_machine = StateMachine(game)
        st, _below, _done = _banner(game, victory=True)
        while st.phase != BANNER:
            game.state_machine.update(DT)
        surface = pygame.Surface((1600, 900), pygame.SRCALPHA)
        st.phase = BANNER               # (with no art the phase passes in one frame)
        st.draw(surface)
        self.assertNotEqual(pygame.image.tobytes(surface, "RGBA"), bytes(1600 * 900 * 4))


class ArtTests(unittest.TestCase):
    """The committed sheets, the rigs that read them and the script that
    cuts them agree with each other and with the owner's choice."""

    @classmethod
    def setUpClass(cls):
        _display()

    def test_the_rigs_name_the_chosen_symbols(self):
        from game.content import get_content
        rigs = get_content().ui_sprites
        loss, win = rigs["end_banner_loss"], rigs["end_banner_win"]
        self.assertEqual(loss["file"], "ui/end_banners/game_over.png")
        self.assertEqual(win["file"], "ui/end_banners/you_won.png")
        for rig, frames in ((loss, 44), (win, 42)):
            show = rig["anims"]["show"]
            self.assertEqual(show["frames"], frames)
            self.assertEqual(show["fps"], 15)
            self.assertFalse(show["loop"])

    def test_every_frame_is_on_the_sheet(self):
        from game.assets import get_assets, reset_assets
        reset_assets()
        assets = get_assets()
        for rig, frames, size in (("end_banner_loss", 44, (416, 128)),
                                  ("end_banner_win", 42, (288, 128))):
            frs = assets.frames(rig, "show")
            self.assertIsNotNone(frs, f"{rig}: sheet missing")
            self.assertEqual(len(frs), frames, f"{rig}: the grid is short")
            self.assertEqual(frs[0].get_size(), size)
            # The middle of the play is the held word: it has pixels.
            mid = frs[frames // 2]
            self.assertTrue(any(mid.get_at((x, mid.get_height() // 2))[3]
                                for x in range(0, mid.get_width(), 4)),
                            f"{rig}: the held frame is blank")

    def test_the_committed_sheets_are_what_the_script_cuts(self):
        """A re-cut can never silently drift from what is committed. The
        pack is untracked and may be absent from a checkout; the script
        then only confirms the sheets are present."""
        done = subprocess.run([sys.executable, CUTTER, "--check"],
                              capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0,
                         f"cut_end_banners.py --check failed:\n{done.stdout}{done.stderr}")


if __name__ == "__main__":
    unittest.main()
